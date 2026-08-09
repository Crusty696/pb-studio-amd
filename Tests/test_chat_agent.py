"""Tests fuer pb_studio.ai.chat_agent — Multi-Turn Tool-Use-Loop mit Mock-LMStudio.

LM Studio Refactor 2026-05-17: Mocks jetzt gegen LMStudioClient + OpenAI-style
``tool_calls`` mit ``id`` und ``function``-Sub-Object. Die ``role=tool``-Reply
trägt ``tool_call_id`` und wird vom Agent automatisch gesetzt.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

import httpx
import pytest

from pb_studio.ai.chat_agent import (
    ChatAgent,
    ChatEvent,
    tool_confirmation_broker,
)
from pb_studio.ai.lmstudio_client import LMStudioClient, LMStudioError, LMStudioConnectionError, LMStudioModelInfo
from pb_studio.ai import model_inventory
from pb_studio.ai.model_inventory import (
    ModelInventoryEntry,
    ModelInventorySnapshot,
    ProviderInventory,
)
from pb_studio.ai.model_registry import ModelRegistry, NoSuitableModelError
from pb_studio.ai.tool_registry import (
    Tool,
    ToolRegistry,
    _owner_headers_for_loopback,
    build_default_registry,
)


def _run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------------
# Mock-LMStudioClient — simuliert /v1/chat/completions-Responses
# (Ollama-style dict — entspricht dem Output von ``_openai_to_ollama_chat_response``).
# ----------------------------------------------------------------------
class FakeLMStudioClient(LMStudioClient):
    """Test-Subclass: liefert vor-konfigurierte Responses, ruft kein echtes HTTP.

    Verwendet das Ollama-Dict-Format welches der echte LMStudioClient.chat()
    intern aus der OpenAI-Response zurueck-mappt — so bleiben Tests unabhaengig
    von der genauen REST-Form.
    """

    def __init__(self, responses: list[dict[str, Any]], *, installed: Optional[list[str]] = None):
        super().__init__(base_url="http://fake/v1")
        self._responses = list(responses)
        # ACHTUNG: NICHT `installed or [...]` — wir wollen empty-list erhalten koennen.
        self._installed = installed if installed is not None else ["qwen3.5-9b-uncensored-hauhaucs-aggressive"]
        self.chat_calls: list[dict[str, Any]] = []

    async def list_models(self) -> list[LMStudioModelInfo]:
        return [
            LMStudioModelInfo(name=n, size_bytes=1, modified_at="", digest="")
            for n in self._installed
        ]

    async def chat(self, model, messages, **kwargs):
        self.chat_calls.append({
            "model": model,
            "messages": list(messages),
            "tools_passed": kwargs.get("tools") is not None,
            "n_tools": len(kwargs.get("tools") or []),
        })
        if not self._responses:
            return {"message": {"role": "assistant", "content": "(no more mock responses)"}}
        return self._responses.pop(0)

    async def aclose(self) -> None:
        return None


class _FrozenInventoryService:
    def __init__(self, snapshot: ModelInventorySnapshot) -> None:
        self.snapshot = snapshot
        self.invalidate_calls = 0
        self.refresh_calls = 0

    def invalidate(self) -> None:
        self.invalidate_calls += 1

    async def refresh(self) -> ModelInventorySnapshot:
        self.refresh_calls += 1
        return self.snapshot


def _chat_model(
    provider: str,
    name: str,
    *,
    loaded: bool = False,
) -> ModelInventoryEntry:
    return ModelInventoryEntry(
        provider=provider,
        name=name,
        installed=True,
        loaded=loaded,
        downloadable=False,
        usable=True,
        capabilities=("chat",),
        inventory_sources=(f"{provider}:frozen",),
        verified_at="2026-07-30T06:00:00+00:00",
        status_reason="frozen chat model",
    )


def _install_chat_inventory(
    monkeypatch: pytest.MonkeyPatch,
    *models: ModelInventoryEntry,
) -> _FrozenInventoryService:
    provider_names = tuple(sorted({model.provider for model in models}))
    snapshot = ModelInventorySnapshot(
        providers=tuple(
            ProviderInventory(
                provider=provider,
                status="ready",
                base_url=(
                    "http://127.0.0.1:1234/v1"
                    if provider == "lmstudio"
                    else "http://127.0.0.1:11434/v1"
                ),
                verified_at="2026-07-30T06:00:00+00:00",
                status_reason="frozen provider",
            )
            for provider in provider_names
        ),
        models=tuple(models),
        verified_at="2026-07-30T06:00:00+00:00",
        generation=1,
    )
    service = _FrozenInventoryService(snapshot)
    monkeypatch.setattr(
        model_inventory,
        "get_model_inventory_service",
        lambda: service,
    )
    return service


@pytest.fixture(autouse=True)
def default_chat_inventory(monkeypatch: pytest.MonkeyPatch):
    """Keep ChatAgent unit tests independent of local provider discovery."""
    return _install_chat_inventory(
        monkeypatch,
        _chat_model(
            "lmstudio",
            "qwen3.5-9b-uncensored-hauhaucs-aggressive",
            loaded=True,
        ),
    )


# ----------------------------------------------------------------------
# Mock-Backend fuer Tool-Handler
# ----------------------------------------------------------------------
def _mock_backend(routes: dict[tuple[str, str], dict[str, Any]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        spec = routes.get(key, {"status": 404, "json": {"detail": "mock-miss"}})
        return httpx.Response(spec.get("status", 200), json=spec.get("json", {}))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")


def _tool_call(name: str, args, *, call_id: str = "call_1"):
    """OpenAI-style tool_call dict mit id."""
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": args if isinstance(args, str) else args,
        },
    }


# ======================================================================
# Tests
# ======================================================================
def test_agent_handles_no_installed_model(monkeypatch):
    """Wenn kein Modell installiert ist, muss der Agent ein error-Event liefern."""
    fake = FakeLMStudioClient(responses=[], installed=[])
    http = _mock_backend({})
    _install_chat_inventory(monkeypatch)

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Hallo"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]
    assert "error" in types
    assert types[-1] == "done"


def test_agent_direct_text_response():
    """Modell antwortet direkt mit Text, ohne Tool-Calls."""
    fake = FakeLMStudioClient(
        responses=[{
            "message": {
                "role": "assistant",
                "content": "Hallo! Ich kann dir bei PB Studio helfen.",
            }
        }],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Hi!"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]
    assert "model" in types
    assert "text" in types
    assert types[-1] == "done"
    text_event = next(e for e in events if e.type == "text")
    assert "Hallo" in text_event.payload["content"]


def test_agent_tool_call_loop():
    """Modell verlangt Tool-Call → Agent dispatched → Modell antwortet mit Text.

    Verifiziert dass die nachfolgende role=tool-Message ``tool_call_id`` hat
    (OpenAI-Format).
    """
    fake = FakeLMStudioClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [_tool_call(
                        "audio_list_clips",
                        {"page": 1, "limit": 10},
                        call_id="call_abc",
                    )],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Du hast 2 Audio-Clips: 'track1.mp3' und 'track2.mp3'.",
                }
            },
        ],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({
        ("GET", "/audio/clips"): {
            "status": 200,
            "json": [
                {"id": 1, "name": "track1.mp3", "path": "/a/track1.mp3", "duration_seconds": 60},
                {"id": 2, "name": "track2.mp3", "path": "/a/track2.mp3", "duration_seconds": 120},
            ],
        },
    })

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Liste meine Audio-Clips"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "text" in types
    assert types[-1] == "done"

    tc = next(e for e in events if e.type == "tool_call")
    assert tc.payload["name"] == "audio_list_clips"
    assert tc.payload["id"] == "call_abc"

    tr = next(e for e in events if e.type == "tool_result")
    assert tr.payload["name"] == "audio_list_clips"
    assert tr.payload["id"] == "call_abc"
    # Helper wraps Listen in {items, count}
    assert tr.payload["result"]["count"] == 2

    # Modell sollte 2x aufgerufen worden sein (Tool-Call + Final)
    assert len(fake.chat_calls) == 2
    # Beim 2. Aufruf war eine role=tool Message in der History MIT tool_call_id
    second_call_msgs = fake.chat_calls[1]["messages"]
    tool_msgs = [m for m in second_call_msgs if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].get("tool_call_id") == "call_abc"


def test_agent_passes_tools_schema_to_lmstudio():
    """Sicherstellen dass der Agent das tools-Inventar an LM Studio uebergibt."""
    fake = FakeLMStudioClient(
        responses=[{"message": {"role": "assistant", "content": "Ok"}}],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({})

    async def go():
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for _ in agent.process_message("Hi"):
                pass
        await http.aclose()

    _run(go())
    assert fake.chat_calls[0]["tools_passed"] is True
    assert fake.chat_calls[0]["n_tools"] >= 20


def test_agent_preserves_history():
    """Vorherige Messages aus history werden korrekt vor die neue User-Message gestellt."""
    fake = FakeLMStudioClient(
        responses=[{"message": {"role": "assistant", "content": "Ja."}}],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({})

    async def go():
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for _ in agent.process_message(
                "Und jetzt?",
                history=[
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hallo"},
                ],
            ):
                pass
        await http.aclose()

    _run(go())
    messages = fake.chat_calls[0]["messages"]
    # system + 2 history + 1 new user = 4
    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "Hi"
    assert messages[2]["content"] == "Hallo"
    assert messages[3]["content"] == "Und jetzt?"


def test_agent_max_tool_turns_limit():
    """Endlos-Tool-Loop muss vom max_tool_turns-Limit gestoppt werden."""
    # Modell will IMMER nur Tool-Calls — never plain text.
    tool_call_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [_tool_call("system_health", {}, call_id="loop_call")],
        }
    }
    fake = FakeLMStudioClient(
        responses=[tool_call_response] * 20,  # mehr als max_tool_turns
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({
        ("GET", "/health"): {"status": 200, "json": {"status": "ok"}},
    })

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
            max_tool_turns=3,
        ) as agent:
            async for ev in agent.process_message("Loop forever"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]
    # Agent darf nicht ewig laufen — muss mit "done" enden
    assert types[-1] == "done"
    # Tool-Calls = max_tool_turns
    tc_count = sum(1 for e in events if e.type == "tool_call")
    assert tc_count <= 3 + 1, f"Zu viele Tool-Calls: {tc_count}"


def test_agent_unknown_tool_returns_error_to_llm():
    """Wenn LLM ein unbekanntes Tool aufruft, kommt der Fehler als tool_result zurueck."""
    fake = FakeLMStudioClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [_tool_call("nonexistent_tool", {})],
                }
            },
            {"message": {"role": "assistant", "content": "Tool kaputt, sorry."}},
        ],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Mach was kaputtes"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    tr = next(e for e in events if e.type == "tool_result")
    assert "error" in tr.payload["result"]
    assert "Unbekanntes Tool" in tr.payload["result"]["error"]


def test_agent_handles_lmstudio_error():
    """LM Studio wirft einen Fehler — Agent muss sauber error-Event + done liefern."""
    class CrashClient(FakeLMStudioClient):
        async def chat(self, *args, **kwargs):
            raise LMStudioError("simulated outage")

    fake = CrashClient(responses=[], installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"])
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Hi"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]
    assert "error" in types
    assert types[-1] == "done"


def test_agent_string_arguments_parsed_as_json():
    """OpenAI/LM-Studio liefert arguments meist als JSON-String."""
    fake = FakeLMStudioClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [_tool_call(
                        "audio_get_beats",
                        '{"clip_id": 42}',
                        call_id="call_42",
                    )],
                }
            },
            {"message": {"role": "assistant", "content": "Done."}},
        ],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({
        ("GET", "/audio/beats/42"): {"status": 200, "json": []},
    })

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for ev in agent.process_message("Beats fuer Clip 42"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    tr = next(e for e in events if e.type == "tool_result")
    assert tr.payload["name"] == "audio_get_beats"
    assert tr.payload["result"]["count"] == 0


def test_agent_legacy_ollama_client_alias_still_works(monkeypatch):
    """Backwards-compat: alte Callsites mit ``ollama_client=...`` funktionieren noch."""
    fake = FakeLMStudioClient(
        responses=[{"message": {"role": "assistant", "content": "OK"}}],
        installed=["qwen3.5-9b-uncensored-hauhaucs-aggressive"],
    )
    http = _mock_backend({})
    _install_chat_inventory(
        monkeypatch,
        _chat_model(
            "ollama",
            "qwen3.5-9b-uncensored-hauhaucs-aggressive",
            loaded=True,
        ),
    )

    async def go():
        async with ChatAgent(
            ollama_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            async for _ in agent.process_message("Hi"):
                pass
        await http.aclose()

    _run(go())
    assert len(fake.chat_calls) == 1


def test_agent_auto_fallback_on_lmstudio_error(monkeypatch):
    """Wenn im Chat ein LMStudioError auftritt, weicht der Agent autonom auf den anderen Provider aus."""
    # Erste Client: wirft Fehler beim chat()
    class FailingLMStudioClient(LMStudioClient):
        def __init__(self):
            super().__init__(base_url="http://127.0.0.1:1234/v1")

        async def list_models(self):
            return [LMStudioModelInfo(name="failed-model", size_bytes=1, modified_at="", digest="")]

        async def chat(self, *args, **kwargs):
            raise LMStudioConnectionError("Connection refused by LM Studio")

        async def aclose(self):
            pass

    failing_client = FailingLMStudioClient()

    # Zweite Client (Ollama): funktioniert
    working_fallback = FakeLMStudioClient(
        responses=[{"message": {"role": "assistant", "content": "Hallo von Ollama! LM Studio hatte ein Problem, aber ich bin da."}}],
        installed=["gemma-4-e4b"],
    )
    # Setze base_url auf Ollama
    working_fallback.base_url = "http://localhost:11434/v1"
    _install_chat_inventory(
        monkeypatch,
        _chat_model("lmstudio", "failed-model", loaded=True),
        _chat_model("ollama", "gemma-4-e4b"),
    )

    # Mocke get_llm_client und get_base_url aus llm_provider
    import pb_studio.ai.llm_provider as llm_provider
    monkeypatch.setattr(llm_provider, "get_base_url", lambda provider: "http://localhost:11434/v1" if provider == "ollama" else "http://127.0.0.1:1234/v1")

    def mock_get_llm_client(provider=None, **kwargs):
        if provider == "ollama":
            return working_fallback
        return failing_client

    monkeypatch.setattr(llm_provider, "get_llm_client", mock_get_llm_client)

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=failing_client,
            http_client=_mock_backend({}),
            model_registry=ModelRegistry({}, client=failing_client),
        ) as agent:
            # We want it to think it owns the LLM so it closes it if needed
            agent._owned_llm = True
            async for ev in agent.process_message("Hallo"):
                events.append(ev)
        return events

    events = _run(go())
    types = [e.type for e in events]

    # Pruefe, ob der Fehler-Event (Fallback-Info) erzeugt wurde
    assert "error" in types
    error_event = next(e for e in events if e.type == "error")
    assert "fallback" in error_event.payload["stage"]
    assert "Wechsle automatisch auf ollama" in error_event.payload["message"]

    # Pruefe, ob das neue Modell vermeldet wurde
    model_events = [e for e in events if e.type == "model"]
    assert len(model_events) >= 2  # Erstes Modell, dann nach Fallback das zweite Modell
    assert model_events[-1].payload["model"] == "gemma-4-e4b"
    assert model_events[-1].payload["provider"] == "ollama"
    assert model_events[-1].payload["selection_receipt"]["provider"] == "ollama"

    # Pruefe, ob der Text von Ollama geliefert wurde
    text_event = next(e for e in events if e.type == "text")
    assert "Hallo von Ollama" in text_event.payload["content"]
    assert events[-1].type == "done"


def test_agent_model_retry_on_non_connection_error(monkeypatch):
    """Wenn ein Modell mit einem nicht-Connection-Fehler fehlschlaegt,
    muss der Agent das naechste Modell versuchen statt Provider-Fallback.

    Simuliert LM Studio mit 2 Modellen: erstes ist 'nicht geladen' (model error),
    zweites funktioniert.
    """
    call_count = 0

    class ModelRetryClient(LMStudioClient):
        def __init__(self):
            super().__init__(base_url="http://127.0.0.1:12341/v1")

        async def list_models(self):
            return [
                LMStudioModelInfo(name="unloaded-model", size_bytes=1, modified_at="", digest=""),
                LMStudioModelInfo(name="loaded-model", size_bytes=1, modified_at="", digest=""),
            ]

        async def chat(self, model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if model == "unloaded-model":
                raise LMStudioError("Model not loaded: unloaded-model")
            return {"message": {"role": "assistant", "content": f"Antwort von {model}!"}}

        async def aclose(self):
            pass

        async def is_alive(self):
            return True

    client = ModelRetryClient()
    http = _mock_backend({})
    _install_chat_inventory(
        monkeypatch,
        _chat_model("lmstudio", "unloaded-model", loaded=True),
        _chat_model("lmstudio", "loaded-model"),
    )

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=client,
            http_client=http,
            model_registry=ModelRegistry({}, client=client),
        ) as agent:
            async for ev in agent.process_message("Hi"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())
    types = [e.type for e in events]

    # Muss model_retry error event haben
    retry_errors = [e for e in events if e.type == "error" and e.payload.get("stage") == "model_retry"]
    assert len(retry_errors) >= 1, f"Erwarte model_retry event, bekommen: {[(e.type, e.payload.get('stage')) for e in events]}"
    assert "nicht verfuegbar" in retry_errors[0].payload["message"]

    # Muss Text-Event mit Antwort vom geladenen Modell haben
    assert "text" in types
    text_event = next(e for e in events if e.type == "text")
    assert "loaded-model" in text_event.payload["content"]
    assert events[-1].type == "done"


def test_agent_readtimeout_does_not_churn_models(monkeypatch):
    """Ein ReadTimeout darf NICHT als 'Modell nicht geladen' interpretiert werden.

    Statt durch alle (evtl. ungeladenen) Modelle zu churnen, muss der Agent
    den Timeout ehrlich melden und mit reason='timeout' abbrechen.
    """
    call_count = 0

    class TimeoutClient(LMStudioClient):
        def __init__(self):
            super().__init__(base_url="http://127.0.0.1:12341/v1")

        async def list_models(self):
            return [
                LMStudioModelInfo(name="loaded-model", size_bytes=1, modified_at="", digest=""),
                LMStudioModelInfo(name="other-model", size_bytes=1, modified_at="", digest=""),
            ]

        async def chat(self, model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            raise LMStudioError(
                "HTTP-Fehler bei POST /chat/completions (http://127.0.0.1:12341/v1): ReadTimeout: ."
            )

        async def aclose(self):
            pass

        async def is_alive(self):
            return True

    client = TimeoutClient()
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            lmstudio_client=client,
            http_client=http,
            model_registry=ModelRegistry({}, client=client),
        ) as agent:
            async for ev in agent.process_message("Hi"):
                events.append(ev)
        await http.aclose()
        return events

    events = _run(go())

    # Kein Durch-Churnen: chat() darf nur EINMAL gerufen werden (kein Modell-Wechsel).
    assert call_count == 1, f"Erwarte 1 chat-Call, bekommen {call_count} (churnte durch Modelle)"

    # Ehrliche Timeout-Meldung, NICHT "nicht geladen" / "nicht verfuegbar".
    err = next(e for e in events if e.type == "error")
    assert "Timeout" in err.payload["message"]
    assert "nicht geladen" not in err.payload["message"]
    assert "nicht verfuegbar" not in err.payload["message"]

    # done mit reason=timeout
    assert events[-1].type == "done"
    assert events[-1].payload.get("reason") == "timeout"


def test_long_running_tool_dispatch_uses_extended_timeout():
    observed: dict[str, float | None] = {}

    async def handler(args, *, http_client):
        observed["read_timeout"] = http_client.timeout.read
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(Tool(
        name="pacing.generate",
        description="test",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
        destructive=False,
        category="pacing",
        long_running=True,
    ))
    fake = FakeLMStudioClient(responses=[])
    http = _mock_backend({})

    async def go():
        async with ChatAgent(
            registry=registry,
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
        ) as agent:
            result = await agent._dispatch_tool(_tool_call("pacing_generate", {}))
        await http.aclose()
        return result

    assert _run(go()) == {"ok": True}
    assert observed["read_timeout"] == 600.0


@pytest.mark.parametrize("long_running", [False, True])
def test_project_capability_is_bound_to_every_loopback_dispatch(long_running):
    from backend.app_state import PROJECT_CAPABILITY_HEADER

    observed: dict[str, str | None] = {}

    async def handler(args, *, http_client):
        headers = _owner_headers_for_loopback("http://127.0.0.1:8765/health")
        observed["capability"] = headers.get(PROJECT_CAPABILITY_HEADER)
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(Tool(
        name="system.health",
        description="test",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
        destructive=False,
        category="system",
        long_running=long_running,
    ))
    fake = FakeLMStudioClient(responses=[])
    http = _mock_backend({})

    async def go():
        async with ChatAgent(
            registry=registry,
            lmstudio_client=fake,
            http_client=http,
            model_registry=ModelRegistry({}, client=fake),
            project_capability="turn-project-capability",
        ) as agent:
            result = await agent._dispatch_tool(_tool_call("system_health", {}))
        await http.aclose()
        return result

    assert _run(go()) == {"ok": True}
    assert observed["capability"] == "turn-project-capability"


def test_confirmation_wait_cancellation_never_dispatches_tool():
    handler_called = False
    confirmation_seen = asyncio.Event()

    async def handler(args, *, http_client):
        nonlocal handler_called
        handler_called = True
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(Tool(
        name="render.start",
        description="test",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
        destructive=True,
        category="render",
    ))
    fake = FakeLMStudioClient(responses=[{
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [_tool_call("render_start", {}, call_id="confirm")],
        }
    }])
    http = _mock_backend({})

    async def go():
        events = []

        async def consume():
            async with ChatAgent(
                registry=registry,
                lmstudio_client=fake,
                http_client=http,
                model_registry=ModelRegistry({}, client=fake),
                confirmation_timeout_seconds=30.0,
                project_capability="turn-project-capability",
            ) as agent:
                async for event in agent.process_message("render"):
                    events.append(event)
                    if event.type == "tool_confirmation_required":
                        confirmation_seen.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(confirmation_seen.wait(), timeout=2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await http.aclose()
        return events

    events = _run(go())
    assert any(event.type == "tool_confirmation_required" for event in events)
    assert handler_called is False
    assert tool_confirmation_broker._entries == {}


def test_project_capability_and_commit_are_stale_after_epoch_change(tmp_path):
    from backend.app_state import AppState, ProjectContextChangedError

    state = AppState(current_project={
        "db_project_id": 1,
        "name": "A",
        "path": str(tmp_path / "a"),
    })
    context = state.capture_project_context()
    capability = state.issue_project_capability(context)

    state.invalidate_project_context()
    with state._state_lock:
        state.current_project = {
            "db_project_id": 2,
            "name": "B",
            "path": str(tmp_path / "b"),
        }

    with pytest.raises(ProjectContextChangedError):
        state.resolve_project_capability(capability)
    with pytest.raises(ProjectContextChangedError):
        with state.project_commit(context):
            state.current_timeline.append({"wrong": "project-b"})
    assert state.current_timeline == []
