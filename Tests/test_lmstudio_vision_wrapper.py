"""Tests fuer pb_studio.video.lmstudio_vision_wrapper.

LM Studio Refactor 2026-05-17: Mocks gegen LM-Studio-REST (OpenAI-kompatibel).
Endpunkte: GET /v1/models, POST /v1/chat/completions.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import numpy as np
import pytest

from pb_studio.video.lmstudio_vision_wrapper import (
    _parse_tags,
    clear_tag_cache,
    extract_tags_via_lmstudio,
    set_status_publisher,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    from pb_studio.ai.model_inventory import get_model_inventory_service

    clear_tag_cache()
    inventory = get_model_inventory_service()
    inventory.invalidate()
    yield
    clear_tag_cache()
    inventory.invalidate()


DEFAULT_VISION_MODEL = "qwen/qwen3-vl-8b"


# ======================================================================
# _parse_tags
# ======================================================================
def test_parse_tags_basic_comma_separated():
    out = _parse_tags("tanzen, club, neonlicht, gruppe, energetisch")
    assert out == ["tanzen", "club", "neonlicht", "gruppe", "energetisch"]


def test_parse_tags_strips_prefix_and_punctuation():
    out = _parse_tags("Tags: tanzen, club, neonlicht.")
    assert "tanzen" in out
    assert "club" in out
    assert "neonlicht" in out


def test_parse_tags_handles_bullet_list():
    raw = "- tanzen\n- club\n- neonlicht\n- gruppe"
    out = _parse_tags(raw)
    assert set(out) >= {"tanzen", "club", "neonlicht", "gruppe"}


def test_parse_tags_handles_numbered_list():
    raw = "1. tanzen\n2. club\n3. neonlicht"
    out = _parse_tags(raw)
    assert set(out) >= {"tanzen", "club", "neonlicht"}


def test_parse_tags_filters_stopwords_and_shorts():
    out = _parse_tags("und, im, ab, tanzen, ja")
    # 'und' (stopword), 'im' (stopword), 'ab' (<3), 'ja' (<3) -> nur tanzen
    assert out == ["tanzen"]


def test_parse_tags_dedup():
    out = _parse_tags("tanzen, tanzen, club, club")
    assert out == ["tanzen", "club"]


def test_parse_tags_max_limit():
    raw = ", ".join(f"tag{i:02d}" for i in range(20))
    out = _parse_tags(raw, max_tags=5)
    assert len(out) == 5


def test_parse_tags_empty_returns_empty():
    assert _parse_tags("") == []
    assert _parse_tags("   ") == []


def test_parse_tags_drops_long_multiword():
    out = _parse_tags("tanzen, ein satz mit fuenf woertern hier, club")
    assert "tanzen" in out and "club" in out
    # 5-word chunk should be dropped
    assert not any(len(t.split()) > 4 for t in out)

def test_parse_tags_falls_back_to_keywords_for_vision_prose():
    out = _parse_tags(
        "The flag is a square with a white center, surrounded by red and blue stripes."
    )
    assert out[:6] == ["flag", "square", "white", "center", "surrounded", "red"]


def test_parse_tags_tokenizes_comma_prose():
    out = _parse_tags(
        "A dancer in a red jacket, illuminated by neon lights in a crowded nightclub."
    )
    assert out == [
        "dancer", "red", "jacket", "illuminated", "neon",
        "lights", "crowded", "nightclub",
    ]


def test_parse_tags_tokenizes_german_prose_without_boilerplate():
    out = _parse_tags(
        "Das Bild zeigt eine tanzende Frau in einem hellen Club mit rotem Neonlicht."
    )
    assert out == ["tanzende", "frau", "hellen", "club", "rotem", "neonlicht"]


def test_parse_tags_rejects_refusals_and_errors():
    assert _parse_tags("Sorry, I cannot analyze this image.") == []
    assert _parse_tags("Es tut mir leid, ich kann dieses Bild nicht analysieren.") == []
    assert _parse_tags("Error: no image was provided.") == []


def test_parse_tags_tokenizes_mixed_prose_instead_of_dropping_long_chunk():
    out = _parse_tags(
        "dancer, while bright red lights illuminate the crowded nightclub"
    )
    assert out == [
        "dancer", "bright", "red", "lights",
        "illuminate", "crowded", "nightclub",
    ]


# ======================================================================
# extract_tags_via_lmstudio — Eingabe-Validierung
# ======================================================================
def test_extract_tags_none_returns_empty():
    assert extract_tags_via_lmstudio(None) == []


def test_extract_tags_empty_array_returns_empty():
    assert extract_tags_via_lmstudio(np.array([])) == []


# ======================================================================
# extract_tags_via_lmstudio — Happy path mit Mock-Transport
# ======================================================================
def _make_vision_transport(model_name: str, content: str) -> httpx.MockTransport:
    """MockTransport fuer /v1/models + /v1/chat/completions."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/v0/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": model_name,
                            "type": "vlm",
                            "state": "loaded",
                        }
                    ]
                },
            )
        if path.endswith("/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": model_name, "object": "model", "owned_by": "test"}
                    ],
                    "object": "list",
                },
            )
        if path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-vision",
                    "object": "chat.completion",
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _patch_client_factory(transport: httpx.MockTransport):
    """Patcht LMStudioClient so dass jeder Aufruf den MockTransport nutzt."""
    from pb_studio.ai import lmstudio_client as lm_mod
    from pb_studio.ai import llm_provider as llm_mod
    import contextlib

    orig = lm_mod.LMStudioClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    @contextlib.contextmanager
    def _cm():
        with patch.object(lm_mod, "LMStudioClient", side_effect=factory), \
             patch.object(llm_mod, "LMStudioClient", side_effect=factory):
            yield
    return _cm()


def test_extract_tags_via_lmstudio_happy_path():
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    frame[:, :, 0] = 180  # red

    transport = _make_vision_transport(
        DEFAULT_VISION_MODEL, "tanzen, club, neonlicht, gruppe, energetisch"
    )
    with _patch_client_factory(transport):
        tags = extract_tags_via_lmstudio(frame, mode="balance")
    assert tags[:3] == ["tanzen", "club", "neonlicht"]


@pytest.mark.parametrize("content", ["", "Sorry, I cannot analyze this image."])
def test_extract_tags_invalid_response_is_not_cached_or_reported_active(content):
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    transport = _make_vision_transport(DEFAULT_VISION_MODEL, content)
    events: list[tuple[str, dict]] = []
    set_status_publisher(lambda event, payload: events.append((event, payload)))
    try:
        with _patch_client_factory(transport):
            first = extract_tags_via_lmstudio(
                frame, model_override=DEFAULT_VISION_MODEL, mode="balance"
            )
            second = extract_tags_via_lmstudio(
                frame, model_override=DEFAULT_VISION_MODEL, mode="balance"
            )
    finally:
        set_status_publisher(None)

    assert first == second == []
    assert not any(payload["status"] == "active" for _, payload in events)


def test_extract_tags_via_lmstudio_no_models_installed_returns_empty():
    """Wenn /v1/models leer ist -> NoSuitableModelError -> [] (Fallback fuer Caller)."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/models"):
            return httpx.Response(200, json={"data": [], "object": "list"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with _patch_client_factory(transport):
        tags = extract_tags_via_lmstudio(frame, mode="balance")
    assert tags == []


def test_extract_tags_via_lmstudio_server_down_returns_empty():
    """ConnectError -> [] (Caller faellt auf Moondream zurueck)."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    # Patche zusaetzlich retry_attempts=1 indirekt: wir koennen LMStudioClient
    # nicht in extract_tags_via_lmstudio veraendern, also nur ueber factory.
    from pb_studio.ai import lmstudio_client as lm_mod

    orig = lm_mod.LMStudioClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        kwargs["retry_attempts"] = 1
        kwargs["retry_backoff_seconds"] = 0.01
        return orig(*args, **kwargs)

    from pb_studio.ai import llm_provider as llm_mod
    with patch.object(lm_mod, "LMStudioClient", side_effect=factory), \
         patch.object(llm_mod, "LMStudioClient", side_effect=factory):
        tags = extract_tags_via_lmstudio(frame, mode="balance")
    assert tags == []


def test_extract_tags_via_lmstudio_uses_model_override():
    """Mit model_override skippen wir die Auto-Selection."""
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    transport = _make_vision_transport("custom-vision-model", "tanzen, club, neonlicht")
    with _patch_client_factory(transport):
        tags = extract_tags_via_lmstudio(
            frame, model_override="custom-vision-model", mode="balance"
        )
    assert "tanzen" in tags


def test_extract_tags_via_lmstudio_cache_hits():
    """Zweiter Aufruf mit gleichem Frame liefert gecachte Tags ohne HTTP-Hit."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    call_count = {"chat": 0, "models": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/v0/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": DEFAULT_VISION_MODEL,
                            "type": "vlm",
                            "state": "loaded",
                        }
                    ]
                },
            )
        if path.endswith("/models"):
            call_count["models"] += 1
            return httpx.Response(
                200,
                json={
                    "data": [{"id": DEFAULT_VISION_MODEL, "object": "model"}],
                    "object": "list",
                },
            )
        if path.endswith("/chat/completions"):
            call_count["chat"] += 1
            return httpx.Response(
                200,
                json={
                    "id": "x", "object": "chat.completion", "model": DEFAULT_VISION_MODEL,
                    "choices": [{"index": 0,
                                 "message": {"role": "assistant", "content": "tanzen, club"},
                                 "finish_reason": "stop"}],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with _patch_client_factory(transport):
        first = extract_tags_via_lmstudio(frame, mode="balance")
        second = extract_tags_via_lmstudio(frame, mode="balance")
    assert first == second == ["tanzen", "club"]
    assert call_count["chat"] == 1  # Cache hit beim 2. Aufruf


# ======================================================================
# Kaltstart-Ladebudget + Task-Sperre (Audit 2026-08-07)
#
# LM Studio laedt ein Modell erst beim ersten Request (JIT). Live gemessen:
# 15.8 s kalt, 1.2 s warm. Das feste 15-s-Timeout traf damit immer den
# Kaltstart, der Failover probierte drei Kandidaten und jeder Frame zahlte
# erneut — 150.69 s pro Clip mit dem Ergebnis "0 tags".
# ======================================================================
def _record_wait_for_timeouts():
    """Contextmanager, der die Timeouts der Chat-Calls sammelt.

    Nur ``client.chat``-Coroutinen zaehlen — der Inventory-Refresh nutzt
    ebenfalls ``asyncio.wait_for`` (3 s) und wuerde die Liste sonst verwaessern.
    """
    import contextlib

    seen: list[float] = []
    original = asyncio.wait_for

    async def spy(awaitable, timeout=None):
        code = getattr(awaitable, "cr_code", None)
        if code is not None and code.co_name == "chat":
            seen.append(timeout)
        return await original(awaitable, timeout=timeout)

    @contextlib.contextmanager
    def _cm():
        with patch.object(asyncio, "wait_for", spy):
            yield seen

    return _cm()


def test_erster_call_bekommt_ladebudget_zweiter_das_kurze_timeout():
    from pb_studio.video.lmstudio_vision_wrapper import DEFAULT_LOAD_TIMEOUT_SECONDS

    frame_a = np.zeros((32, 32, 3), dtype=np.uint8)
    frame_b = np.full((32, 32, 3), 90, dtype=np.uint8)  # anderer Hash -> kein Cache

    transport = _make_vision_transport(DEFAULT_VISION_MODEL, "tanzen, club")
    with _record_wait_for_timeouts() as timeouts, _patch_client_factory(transport):
        assert extract_tags_via_lmstudio(frame_a, mode="balance") == ["tanzen", "club"]
        assert extract_tags_via_lmstudio(frame_b, mode="balance") == ["tanzen", "club"]

    assert len(timeouts) == 2, timeouts
    assert timeouts[0] == DEFAULT_LOAD_TIMEOUT_SECONDS
    assert timeouts[1] == 60.0  # Default von extract_tags_via_lmstudio


def test_ladebudget_wird_nach_timeout_nicht_erneut_vergeben():
    """Reicht das Ladebudget nicht, bekommt dasselbe Modell keinen zweiten Langlaeufer."""
    from pb_studio.video.lmstudio_vision_wrapper import DEFAULT_LOAD_TIMEOUT_SECONDS

    frame_a = np.zeros((32, 32, 3), dtype=np.uint8)
    frame_b = np.full((32, 32, 3), 90, dtype=np.uint8)
    transport = _make_vision_transport(DEFAULT_VISION_MODEL, "tanzen, club")

    original = asyncio.wait_for
    seen: list[float] = []

    async def spy(awaitable, timeout=None):
        code = getattr(awaitable, "cr_code", None)
        if code is not None and code.co_name == "chat":
            seen.append(timeout)
            awaitable.close()          # Coroutine sauber schliessen
            raise asyncio.TimeoutError()
        return await original(awaitable, timeout=timeout)

    with patch.object(asyncio, "wait_for", spy), _patch_client_factory(transport):
        assert extract_tags_via_lmstudio(frame_a, mode="balance") == []
        assert extract_tags_via_lmstudio(frame_b, mode="balance") == []

    assert seen, "kein Chat-Call beobachtet"
    assert seen[0] == DEFAULT_LOAD_TIMEOUT_SECONDS
    # Jeder weitere Call — auch der des naechsten Frames — nur noch kurz.
    assert all(t == 60.0 for t in seen[1:]), seen


def test_nur_ein_kandidat_pro_frame_bekommt_ladebudget():
    """Sonst kostet ein einziger Frame 3 x Ladebudget."""
    from pb_studio.video.lmstudio_vision_wrapper import DEFAULT_LOAD_TIMEOUT_SECONDS

    frame = np.zeros((32, 32, 3), dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/v0/models") and request.method == "GET":
            return httpx.Response(200, json={"data": [
                {"id": "vlm-a", "type": "vlm", "state": "not-loaded"},
                {"id": "vlm-b", "type": "vlm", "state": "not-loaded"},
                {"id": "vlm-c", "type": "vlm", "state": "not-loaded"},
            ]})
        if path.endswith("/models") and request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [
                {"id": n, "object": "model"} for n in ("vlm-a", "vlm-b", "vlm-c")]})
        if path.endswith("/chat/completions"):
            return httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "vlm-a",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": ""}}]})
        return httpx.Response(404)

    original = asyncio.wait_for
    seen: list[float] = []

    async def spy(awaitable, timeout=None):
        code = getattr(awaitable, "cr_code", None)
        if code is not None and code.co_name == "chat":
            seen.append(timeout)
        return await original(awaitable, timeout=timeout)

    with patch.object(asyncio, "wait_for", spy),          _patch_client_factory(httpx.MockTransport(handler)):
        assert extract_tags_via_lmstudio(frame, mode="balance") == []

    lang = [t for t in seen if t == DEFAULT_LOAD_TIMEOUT_SECONDS]
    assert len(seen) >= 2, seen
    assert len(lang) == 1, f"mehr als ein Ladebudget in einem Frame: {seen}"


def test_task_sperre_verhindert_failover_wiederholung_pro_frame():
    """Nach erschoepftem Failover darf der naechste Frame keinen Call mehr ausloesen."""
    frame_a = np.zeros((32, 32, 3), dtype=np.uint8)
    frame_b = np.full((32, 32, 3), 90, dtype=np.uint8)
    call_count = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/v0/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={"data": [{"id": DEFAULT_VISION_MODEL, "type": "vlm",
                                "state": "not-loaded"}]},
            )
        if path.endswith("/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={"data": [{"id": DEFAULT_VISION_MODEL, "object": "model"}],
                      "object": "list"},
            )
        if path.endswith("/chat/completions"):
            call_count["chat"] += 1
            # Leerer Content -> keine nutzbaren Tags -> Failover bis erschoepft.
            return httpx.Response(
                200,
                json={"id": "x", "object": "chat.completion",
                      "model": DEFAULT_VISION_MODEL,
                      "choices": [{"index": 0,
                                   "message": {"role": "assistant", "content": ""},
                                   "finish_reason": "stop"}]},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with _patch_client_factory(transport):
        assert extract_tags_via_lmstudio(frame_a, mode="balance") == []
        calls_after_first_frame = call_count["chat"]
        assert extract_tags_via_lmstudio(frame_b, mode="balance") == []

    assert calls_after_first_frame >= 1
    assert call_count["chat"] == calls_after_first_frame, (
        "Zweiter Frame hat die erschoepfte Failover-Kette erneut durchlaufen"
    )


def test_parse_tags_bremst_wortschleifen():
    """VLMs geraten bei Tag-Listen in Wortschleifen — live beobachtet."""
    raw = ("dunkel, fetisch, fetischkleidung, fetischmode, fetischlook, "
           "fetischtanz, fetischparty, fetischstimmung, fetischambiente, wasser")
    out = _parse_tags(raw)
    fetisch = [t for t in out if t.startswith("fetisch")]
    assert len(fetisch) <= 2, out
    # Die inhaltlich verschiedenen Tags muessen erhalten bleiben.
    assert "dunkel" in out
    assert "wasser" in out


def test_parse_tags_erlaubt_zwei_aehnliche_stämme():
    """Zwei gleiche Staemme sind erlaubt, der dritte faellt weg."""
    out = _parse_tags("schwarz, schwarzlicht, schwarzweiss, rot")
    assert out == ["schwarz", "schwarzlicht", "rot"], out


def test_parse_tags_kurze_tags_kollidieren_nicht():
    """Tags kuerzer als _STEM_LEN bilden eigene Schluessel."""
    out = _parse_tags("tanz, tanzen, wasser, neonlicht")
    assert out == ["tanz", "tanzen", "wasser", "neonlicht"]


def test_produktionsdefault_ist_45s_nicht_15s():
    """video_router ruft extract_tags_and_model_via_lmstudio ohne Timeout-Argument."""
    from pb_studio.video.lmstudio_vision_wrapper import (
        DEFAULT_LOAD_TIMEOUT_SECONDS,
        extract_tags_and_model_via_lmstudio,
    )

    frame_a = np.zeros((32, 32, 3), dtype=np.uint8)
    frame_b = np.full((32, 32, 3), 90, dtype=np.uint8)
    transport = _make_vision_transport(DEFAULT_VISION_MODEL, "tanzen, club")

    with _record_wait_for_timeouts() as timeouts, _patch_client_factory(transport):
        extract_tags_and_model_via_lmstudio(frame_a, mode="balance")
        extract_tags_and_model_via_lmstudio(frame_b, mode="balance")

    assert timeouts == [DEFAULT_LOAD_TIMEOUT_SECONDS, 45.0], timeouts


def test_warm_status_laeuft_ab_und_gibt_ladebudget_zurueck():
    """LM Studio entlaedt per JIT-TTL — 'warm' darf nicht ewig gelten."""
    import pb_studio.video.lmstudio_vision_wrapper as w

    key = ("lmstudio", "irgendein-vlm")
    w._WARM_MODELS[key] = time.monotonic()
    w._LOAD_BUDGET_SPENT.add(key)
    assert w._ist_warm(key) is True

    w._WARM_MODELS[key] = time.monotonic() - w._WARM_WINDOW_SECONDS - 1.0
    assert w._ist_warm(key) is False
    assert key not in w._WARM_MODELS
    assert key not in w._LOAD_BUDGET_SPENT, "Ladebudget muss nach Abkuehlen neu gelten"


def test_task_sperre_laeuft_ab():
    """Startet der Nutzer LM Studio nach, darf die Sperre nicht kleben bleiben."""
    import pb_studio.video.lmstudio_vision_wrapper as w

    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    transport = _make_vision_transport(DEFAULT_VISION_MODEL, "tanzen, club")

    w._TASK_UNAVAILABLE_UNTIL["video_captioning"] = time.monotonic() + 60.0
    with _patch_client_factory(transport):
        assert extract_tags_via_lmstudio(frame, mode="balance") == []

        w._TASK_UNAVAILABLE_UNTIL["video_captioning"] = time.monotonic() - 1.0
        assert extract_tags_via_lmstudio(frame, mode="balance") == ["tanzen", "club"]
    assert "video_captioning" not in w._TASK_UNAVAILABLE_UNTIL


def test_failed_candidate_lock_does_not_self_block_next_frame(monkeypatch):
    """A receipt lock must end with its attempt, not with the frame-batch task."""
    import pb_studio.ai.model_registry as registry_module
    from pb_studio.ai.model_registry import ModelSelectionReceipt
    from pb_studio.video.lmstudio_vision_wrapper import (
        extract_tags_and_model_via_lmstudio_async,
    )

    receipts = {
        model_id: ModelSelectionReceipt(
            provider="lmstudio",
            model_id=model_id,
            task="video_captioning",
            mode="balance",
            required_capabilities=("vision",),
            verified_capabilities=("vision",),
            source="test",
            reason="test",
            selected_at="2026-08-09T00:00:00Z",
        )
        for model_id in ("vlm-a", "vlm-b")
    }
    calls = {"vlm-a": 0, "vlm-b": 0}

    class FakeClient:
        def __init__(self, model_id):
            self.model_id = model_id

        async def chat(self, **_kwargs):
            calls[self.model_id] += 1
            if self.model_id == "vlm-a" and calls[self.model_id] == 1:
                raise asyncio.TimeoutError
            return {"message": {"content": f"tag-{self.model_id}"}}

    async def fake_failover(_registry, _task, _mode, operation, **_kwargs):
        attempts = []
        for model_id in ("vlm-a", "vlm-b"):
            receipt = receipts[model_id]
            attempts.append(receipt)
            try:
                value = await operation(FakeClient(model_id), receipt)
            except asyncio.TimeoutError:
                continue
            return value, receipt, tuple(attempts)
        raise AssertionError("test failover unexpectedly exhausted")

    monkeypatch.setattr(
        registry_module,
        "execute_with_model_failover",
        fake_failover,
    )

    async def analyze_two_frames():
        first = await extract_tags_and_model_via_lmstudio_async(
            np.zeros((8, 8, 3), dtype=np.uint8),
            load_timeout_seconds=0.1,
        )
        second = await extract_tags_and_model_via_lmstudio_async(
            np.full((8, 8, 3), 1, dtype=np.uint8),
            load_timeout_seconds=0.1,
        )
        return first, second

    first, second = asyncio.run(
        asyncio.wait_for(analyze_two_frames(), timeout=1.0)
    )

    assert first == (["tag-vlm-b"], "vlm-b")
    assert second == (["tag-vlm-a"], "vlm-a")
