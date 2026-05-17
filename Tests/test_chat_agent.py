"""Tests fuer pb_studio.ai.chat_agent — Multi-Turn Tool-Use-Loop mit Mock-Ollama."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

import httpx
import pytest

from pb_studio.ai.chat_agent import ChatAgent, ChatEvent
from pb_studio.ai.model_registry import ModelRegistry, NoSuitableModelError
from pb_studio.ai.ollama_client import OllamaClient, OllamaError, OllamaModelInfo
from pb_studio.ai.tool_registry import build_default_registry


def _run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------------
# Mock-OllamaClient — simuliert /api/chat-Responses (inkl. tool_calls).
# ----------------------------------------------------------------------
class FakeOllamaClient(OllamaClient):
    """Test-Subclass: liefert vor-konfigurierte Responses, ruft kein echtes HTTP."""

    def __init__(self, responses: list[dict[str, Any]], *, installed: Optional[list[str]] = None):
        super().__init__(base_url="http://fake")
        self._responses = list(responses)
        # ACHTUNG: NICHT `installed or [...]` — wir wollen empty-list erhalten koennen.
        self._installed = installed if installed is not None else ["llama3.1:8b"]
        self.chat_calls: list[dict[str, Any]] = []

    async def list_models(self) -> list[OllamaModelInfo]:
        return [
            OllamaModelInfo(name=n, size_bytes=1, modified_at="", digest="")
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


# ----------------------------------------------------------------------
# Mock-Backend fuer Tool-Handler
# ----------------------------------------------------------------------
def _mock_backend(routes: dict[tuple[str, str], dict[str, Any]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        spec = routes.get(key, {"status": 404, "json": {"detail": "mock-miss"}})
        return httpx.Response(spec.get("status", 200), json=spec.get("json", {}))

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")


# ======================================================================
# Tests
# ======================================================================
def test_agent_handles_no_installed_model():
    """Wenn kein Modell installiert ist, muss der Agent ein error-Event liefern."""
    fake = FakeOllamaClient(responses=[], installed=[])
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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
    fake = FakeOllamaClient(
        responses=[{
            "message": {
                "role": "assistant",
                "content": "Hallo! Ich kann dir bei PB Studio helfen.",
            }
        }],
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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
    """Modell verlangt Tool-Call → Agent dispatched → Modell antwortet mit Text."""
    # Erste Response: Tool-Call. Zweite Response: Finaler Text.
    fake = FakeOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "audio_list_clips",
                            "arguments": {"page": 1, "limit": 10},
                        }
                    }],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Du hast 2 Audio-Clips: 'track1.mp3' und 'track2.mp3'.",
                }
            },
        ],
        installed=["llama3.1:8b"],
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
            ollama_client=fake,
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

    tr = next(e for e in events if e.type == "tool_result")
    assert tr.payload["name"] == "audio_list_clips"
    # Helper wraps Listen in {items, count}
    assert tr.payload["result"]["count"] == 2

    # Modell sollte 2x aufgerufen worden sein (Tool-Call + Final)
    assert len(fake.chat_calls) == 2
    # Beim 2. Aufruf war eine role=tool Message in der History
    second_call_msgs = fake.chat_calls[1]["messages"]
    assert any(m.get("role") == "tool" for m in second_call_msgs)


def test_agent_passes_tools_schema_to_ollama():
    """Sicherstellen dass der Agent das tools-Inventar an Ollama uebergibt."""
    fake = FakeOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Ok"}}],
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({})

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
    assert fake.chat_calls[0]["tools_passed"] is True
    assert fake.chat_calls[0]["n_tools"] >= 20


def test_agent_preserves_history():
    """Vorherige Messages aus history werden korrekt vor die neue User-Message gestellt."""
    fake = FakeOllamaClient(
        responses=[{"message": {"role": "assistant", "content": "Ja."}}],
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({})

    async def go():
        async with ChatAgent(
            ollama_client=fake,
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
            "tool_calls": [{
                "function": {"name": "system_health", "arguments": {}},
            }],
        }
    }
    fake = FakeOllamaClient(
        responses=[tool_call_response] * 20,  # mehr als max_tool_turns
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({
        ("GET", "/health"): {"status": 200, "json": {"status": "ok"}},
    })

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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
    fake = FakeOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {"name": "nonexistent_tool", "arguments": {}},
                    }],
                }
            },
            {"message": {"role": "assistant", "content": "Tool kaputt, sorry."}},
        ],
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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


def test_agent_handles_ollama_error():
    """Ollama wirft einen Fehler — Agent muss sauber error-Event + done liefern."""
    class CrashClient(FakeOllamaClient):
        async def chat(self, *args, **kwargs):
            raise OllamaError("simulated outage")

    fake = CrashClient(responses=[], installed=["llama3.1:8b"])
    http = _mock_backend({})

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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
    """Manche Modelle schicken arguments als JSON-String statt dict."""
    fake = FakeOllamaClient(
        responses=[
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "audio_get_beats",
                            "arguments": '{"clip_id": 42}',
                        }
                    }],
                }
            },
            {"message": {"role": "assistant", "content": "Done."}},
        ],
        installed=["llama3.1:8b"],
    )
    http = _mock_backend({
        ("GET", "/audio/beats/42"): {"status": 200, "json": []},
    })

    async def go():
        events = []
        async with ChatAgent(
            ollama_client=fake,
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
    # Mock liefert leere Liste -> wrap in items/count
    assert tr.payload["result"]["count"] == 0
