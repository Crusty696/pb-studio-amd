"""Tests fuer pb_studio.brain.llm_narrator.

Verifiziert:
* erfolgreicher Aufruf liefert Narrativ-Text (kein Format-Noise)
* Cache trifft beim zweiten Call mit identischen Inputs
* Cache bricht bei geaenderten Inputs auf
* leere Antwort vom Modell -> ``None``
* OllamaError beim /api/tags -> ``None`` (Fallback)
* NoSuitableModelError -> ``None``
* Post-Processing kuerzt auf max 3 Saetze und entfernt Praefixe/Bullets

Wir injecten einen ``OllamaClient`` mit ``httpx.MockTransport`` damit kein
echter Ollama-Daemon laufen muss.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx
import pytest

from pb_studio.ai.ollama_client import OllamaClient
from pb_studio.brain import llm_narrator
from pb_studio.brain.llm_narrator import (
    _post_process_narrative,
    clear_narrative_cache,
    generate_explanation,
)


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def _client(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaClient:
    return OllamaClient(transport=httpx.MockTransport(handler))


def _make_handler(
    *,
    models: list[str] | None = None,
    chat_content: str = "Dieser Cut sitzt auf dem Beat. Die Stimmung koennte etwas dichter sein.",
    chat_status: int = 200,
    tags_status: int = 200,
) -> Callable[[httpx.Request], httpx.Response]:
    """Erzeugt einen MockTransport-Handler fuer /api/tags + /api/chat."""
    models_list = models or ["gemma4:latest"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            if tags_status >= 400:
                return httpx.Response(tags_status, text="boom")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": n,
                            "size": 9_000_000_000,
                            "modified_at": "2026-05-15",
                        }
                        for n in models_list
                    ]
                },
            )
        if request.url.path == "/api/chat":
            if chat_status >= 400:
                return httpx.Response(chat_status, text="bad")
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": chat_content},
                    "done": True,
                },
            )
        return httpx.Response(404)

    return handler


def _sample_inputs(**overrides: Any) -> dict[str, Any]:
    base = dict(
        cut_id=42,
        segment_type="drop",
        top_axes=[
            {"axis": "beat_align_strength", "score": 0.92},
            {"axis": "motion_match", "score": 0.81},
            {"axis": "energy_match", "score": 0.74},
        ],
        bottom_axes=[
            {"axis": "mood_match", "score": 0.21},
            {"axis": "color_match", "score": 0.30},
        ],
        cold_start_axes=[],
        final_score=0.66,
    )
    base.update(overrides)
    return base


# ======================================================================
# Happy path
# ======================================================================
def test_generate_explanation_returns_text_from_model():
    clear_narrative_cache()
    client = _client(_make_handler(chat_content="Der Schnitt sitzt sauber auf dem Beat. Die Stimmung koennte dichter sein."))

    async def go():
        return await generate_explanation(client=client, **_sample_inputs())

    text = asyncio.run(go())
    assert text is not None
    assert "Beat" in text or "beat" in text.lower()
    assert text.count("\n") == 0  # einzeilig nach post-processing


def test_generate_explanation_uses_cache_on_second_call():
    clear_narrative_cache()
    call_counter = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "gemma4:latest", "size": 1, "modified_at": ""}]},
            )
        if request.url.path == "/api/chat":
            call_counter["chat"] += 1
            return httpx.Response(
                200,
                json={"message": {"content": "Der Cut wirkt stimmig."}, "done": True},
            )
        return httpx.Response(404)

    client = _client(handler)
    inputs = _sample_inputs()

    async def go():
        first = await generate_explanation(client=client, **inputs)
        second = await generate_explanation(client=client, **inputs)
        return first, second

    a, b = asyncio.run(go())
    assert a is not None and b is not None
    assert a == b
    assert call_counter["chat"] == 1, f"chat should be hit once, was {call_counter['chat']}"


def test_generate_explanation_cache_invalidated_when_scores_change():
    clear_narrative_cache()
    call_counter = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "gemma4:latest", "size": 1, "modified_at": ""}]},
            )
        if request.url.path == "/api/chat":
            call_counter["chat"] += 1
            return httpx.Response(
                200,
                json={"message": {"content": f"Antwort {call_counter['chat']}."}, "done": True},
            )
        return httpx.Response(404)

    client = _client(handler)

    async def go():
        a = await generate_explanation(client=client, **_sample_inputs())
        # andere Top-Score -> anderer content_hash
        b = await generate_explanation(
            client=client,
            **_sample_inputs(top_axes=[{"axis": "beat_align_strength", "score": 0.55}]),
        )
        return a, b

    a, b = asyncio.run(go())
    assert call_counter["chat"] == 2
    assert a != b


# ======================================================================
# Error / Fallback
# ======================================================================
def test_generate_explanation_returns_none_on_ollama_unreachable():
    clear_narrative_cache()
    # tags_status=500 -> Retries scheitern -> OllamaConnectionError
    client = _client(_make_handler(tags_status=500))

    async def go():
        return await generate_explanation(client=client, **_sample_inputs())

    text = asyncio.run(go())
    assert text is None


def test_generate_explanation_returns_none_when_no_model_installed():
    clear_narrative_cache()
    # Tags-Endpoint liefert ein nicht-praeferiertes Modell
    client = _client(_make_handler(models=["llama2-uncensored:nope"]))

    async def go():
        return await generate_explanation(client=client, **_sample_inputs())

    text = asyncio.run(go())
    assert text is None


def test_generate_explanation_returns_none_on_empty_chat_response():
    clear_narrative_cache()
    client = _client(_make_handler(chat_content=""))

    async def go():
        return await generate_explanation(client=client, **_sample_inputs())

    text = asyncio.run(go())
    assert text is None


def test_generate_explanation_returns_none_on_chat_5xx():
    clear_narrative_cache()
    client = _client(_make_handler(chat_status=500))

    async def go():
        return await generate_explanation(client=client, **_sample_inputs())

    text = asyncio.run(go())
    assert text is None


# ======================================================================
# Post-Processing
# ======================================================================
def test_post_process_strips_prefixes():
    out = _post_process_narrative("Antwort: Der Cut wirkt knackig.")
    assert out.startswith("Der Cut")
    assert "Antwort" not in out


def test_post_process_strips_quotes_and_codeblock():
    out = _post_process_narrative('"Der Cut wirkt knackig."')
    assert out == "Der Cut wirkt knackig."

    out2 = _post_process_narrative("`Der Cut wirkt knackig.`")
    assert out2 == "Der Cut wirkt knackig."


def test_post_process_removes_bullets():
    out = _post_process_narrative("- Der Cut sitzt auf dem Beat.\n* Die Stimmung wirkt dicht.")
    assert not out.startswith(("-", "*", "•"))
    assert "Der Cut sitzt auf dem Beat" in out
    assert "Die Stimmung wirkt dicht" in out


def test_post_process_caps_at_three_sentences():
    raw = "Erster Satz. Zweiter Satz. Dritter Satz. Vierter Satz. Fuenfter Satz."
    out = _post_process_narrative(raw)
    # erlaubt sind maximal 3
    sentence_count = sum(1 for ch in out if ch in ".!?")
    assert sentence_count <= 3
    assert "Fuenfter" not in out


def test_post_process_handles_empty():
    assert _post_process_narrative("") == ""
    assert _post_process_narrative("   ") == ""


# ======================================================================
# clear_narrative_cache
# ======================================================================
def test_clear_narrative_cache_forces_new_call():
    clear_narrative_cache()
    call_counter = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "gemma4:latest", "size": 1, "modified_at": ""}]},
            )
        if request.url.path == "/api/chat":
            call_counter["chat"] += 1
            return httpx.Response(
                200,
                json={"message": {"content": "Stimmig."}, "done": True},
            )
        return httpx.Response(404)

    client = _client(handler)

    async def go():
        await generate_explanation(client=client, **_sample_inputs())
        clear_narrative_cache()
        await generate_explanation(client=client, **_sample_inputs())

    asyncio.run(go())
    assert call_counter["chat"] == 2
