"""Tests fuer pb_studio.video.ollama_vision_wrapper."""
from __future__ import annotations

import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import numpy as np
import pytest

from pb_studio.video.ollama_vision_wrapper import (
    _parse_tags,
    clear_tag_cache,
    extract_tags_via_ollama,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_tag_cache()
    yield
    clear_tag_cache()


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


# ======================================================================
# extract_tags_via_ollama — Eingabe-Validierung
# ======================================================================
def test_extract_tags_none_returns_empty():
    assert extract_tags_via_ollama(None) == []


def test_extract_tags_empty_array_returns_empty():
    assert extract_tags_via_ollama(np.array([])) == []


# ======================================================================
# extract_tags_via_ollama — Happy path mit Mock-Transport
# ======================================================================
def _make_vision_transport(model_name: str, content: str) -> httpx.MockTransport:
    """Erzeugt MockTransport, der /api/tags + /api/chat sauber bedient."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": model_name,
                            "size": 9_000_000_000,
                            "modified_at": "2026-05-15",
                        }
                    ]
                },
            )
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": model_name,
                    "message": {"role": "assistant", "content": content},
                    "done": True,
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _patch_client_factory(transport: httpx.MockTransport):
    """Patcht OllamaClient so dass jeder Aufruf den MockTransport nutzt."""
    from pb_studio.ai import ollama_client as oc_mod

    orig = oc_mod.OllamaClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    return patch.object(oc_mod, "OllamaClient", side_effect=factory)


def test_extract_tags_via_ollama_happy_path():
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    frame[:, :, 0] = 180  # red

    transport = _make_vision_transport(
        "gemma4:latest", "tanzen, club, neonlicht, gruppe, energetisch"
    )
    with _patch_client_factory(transport):
        tags = extract_tags_via_ollama(frame, mode="balance")
    assert tags[:3] == ["tanzen", "club", "neonlicht"]


def test_extract_tags_via_ollama_no_models_installed_returns_empty():
    """Wenn /api/tags leer ist -> NoSuitableModelError -> [] (Fallback fuer Caller)."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with _patch_client_factory(transport):
        tags = extract_tags_via_ollama(frame, mode="balance")
    assert tags == []


def test_extract_tags_via_ollama_ollama_down_returns_empty():
    """ConnectError -> [] (Caller faellt auf Moondream zurueck)."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    # Patche zusaetzlich retry_attempts=1 indirekt: wir koennen OllamaClient
    # nicht in extract_tags_via_ollama veraendern, also nur ueber factory.
    from pb_studio.ai import ollama_client as oc_mod

    orig = oc_mod.OllamaClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        kwargs["retry_attempts"] = 1
        kwargs["retry_backoff_seconds"] = 0.01
        return orig(*args, **kwargs)

    with patch.object(oc_mod, "OllamaClient", side_effect=factory):
        tags = extract_tags_via_ollama(frame, mode="balance")
    assert tags == []


def test_extract_tags_via_ollama_uses_model_override():
    """Mit model_override skippen wir die Auto-Selection (Tags-Endpoint trotzdem fuer Registry-Refresh)."""
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    transport = _make_vision_transport("llava:13b", "tanzen, club, neonlicht")
    with _patch_client_factory(transport):
        tags = extract_tags_via_ollama(
            frame, model_override="llava:13b", mode="balance"
        )
    assert "tanzen" in tags


def test_extract_tags_via_ollama_cache_hits():
    """Zweiter Aufruf mit gleichem Frame liefert gecachte Tags ohne HTTP-Hit."""
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    call_count = {"chat": 0, "tags": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            call_count["tags"] += 1
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "gemma4:latest", "size": 1, "modified_at": "x"}
                    ]
                },
            )
        if request.url.path == "/api/chat":
            call_count["chat"] += 1
            return httpx.Response(
                200, json={"message": {"content": "tanzen, club"}, "done": True}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with _patch_client_factory(transport):
        first = extract_tags_via_ollama(frame, mode="balance")
        second = extract_tags_via_ollama(frame, mode="balance")
    assert first == second == ["tanzen", "club"]
    assert call_count["chat"] == 1  # Cache hit beim 2. Aufruf
