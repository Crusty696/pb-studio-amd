"""Tests fuer pb_studio.video.lmstudio_vision_wrapper.

LM Studio Refactor 2026-05-17: Mocks gegen LM-Studio-REST (OpenAI-kompatibel).
Endpunkte: GET /v1/models, POST /v1/chat/completions.
"""
from __future__ import annotations

import asyncio
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
