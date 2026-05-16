"""Tests fuer pb_studio.ai.ollama_client (HTTP-only, gemocked via httpx.MockTransport)."""
from __future__ import annotations

import asyncio
import json

import httpx
import numpy as np
import pytest

from pb_studio.ai.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaResponseError,
    _encode_image_payload,
)


# ----------------------------------------------------------------------
# Helper: build MockTransport with route dispatch
# ----------------------------------------------------------------------
def _make_transport(handler):
    return httpx.MockTransport(handler)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ======================================================================
# /api/tags
# ======================================================================
def test_list_models_parses_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "gemma4:latest",
                        "model": "gemma4:latest",
                        "size": 9_600_000_000,
                        "modified_at": "2026-05-15T10:00:00Z",
                        "digest": "abc123",
                        "details": {
                            "family": "gemma",
                            "parameter_size": "9B",
                            "quantization_level": "Q4_0",
                        },
                    },
                    {
                        "name": "llava:13b",
                        "size": 8_000_000_000,
                        "modified_at": "2026-05-10T08:00:00Z",
                    },
                ]
            },
        )

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            models = await client.list_models()
        return models

    models = _run(go())
    assert len(models) == 2
    assert models[0].name == "gemma4:latest"
    assert models[0].size_gb > 8.0
    assert models[0].family == "gemma"
    assert models[1].name == "llava:13b"
    assert models[1].family is None


def test_list_models_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.list_models()

    assert _run(go()) == []


def test_list_models_handles_http_500_with_retry_then_fail():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    async def go():
        async with OllamaClient(
            transport=_make_transport(handler),
            retry_attempts=3,
            retry_backoff_seconds=0.01,
        ) as client:
            await client.list_models()

    with pytest.raises(OllamaResponseError):
        _run(go())
    assert calls["n"] == 3  # 3 attempts


# ======================================================================
# /api/chat (+ Vision)
# ======================================================================
def test_chat_basic_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "model": "gemma4:latest",
                "message": {"role": "assistant", "content": "hello back"},
                "done": True,
            },
        )

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="gemma4:latest",
                messages=[{"role": "user", "content": "hi"}],
            )

    result = _run(go())
    assert result["message"]["content"] == "hello back"
    assert captured["body"]["model"] == "gemma4:latest"
    assert captured["body"]["stream"] is False


def test_chat_with_numpy_image_attaches_base64():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"message": {"content": "tag1, tag2, tag3"}, "done": True},
        )

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[:, :, 0] = 200  # red

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="gemma4:latest",
                messages=[{"role": "user", "content": "tag this"}],
                images=[frame],
            )

    result = _run(go())
    assert result["message"]["content"].startswith("tag1")
    images = captured["body"]["messages"][-1]["images"]
    assert len(images) == 1
    assert isinstance(images[0], str) and len(images[0]) > 50  # base64 payload


def test_chat_with_options_and_keep_alive():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="m",
                messages=[{"role": "user", "content": "x"}],
                options={"temperature": 0.5},
                keep_alive="5m",
            )

    _run(go())
    assert captured["body"]["options"] == {"temperature": 0.5}
    assert captured["body"]["keep_alive"] == "5m"


def test_chat_raises_on_4xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad model")

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            await client.chat(model="m", messages=[{"role": "user", "content": "x"}])

    with pytest.raises(OllamaResponseError):
        _run(go())


# ======================================================================
# /api/generate
# ======================================================================
def test_generate_single_prompt():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["prompt"] == "hello"
        assert body["stream"] is False
        return httpx.Response(200, json={"response": "hi there", "done": True})

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.generate(model="m", prompt="hello")

    out = _run(go())
    assert out["response"] == "hi there"


# ======================================================================
# /api/pull (Streaming)
# ======================================================================
def test_pull_model_yields_progress_events():
    events = [
        {"status": "pulling manifest"},
        {"status": "pulling", "completed": 100, "total": 200, "digest": "sha256:x"},
        {"status": "pulling", "completed": 200, "total": 200, "digest": "sha256:x"},
        {"status": "success"},
    ]
    body = "\n".join(json.dumps(e) for e in events).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pull"
        return httpx.Response(200, content=body, headers={"content-type": "application/x-ndjson"})

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            collected = []
            async for ev in client.pull_model("gemma4:latest"):
                collected.append(ev)
            return collected

    received = _run(go())
    assert received[0]["status"] == "pulling manifest"
    assert received[-1]["status"] == "success"
    assert any(ev.get("completed") == 100 for ev in received)


def test_pull_model_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async def go():
        async with OllamaClient(
            transport=_make_transport(handler), retry_attempts=1
        ) as client:
            async for _ in client.pull_model("x"):
                pass

    with pytest.raises(OllamaConnectionError):
        _run(go())


# ======================================================================
# /api/delete
# ======================================================================
def test_delete_model_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"name": "foo:latest"}
        return httpx.Response(200, text="")

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.delete_model("foo:latest")

    assert _run(go()) is True


def test_delete_model_404_returns_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.delete_model("ghost")

    assert _run(go()) is False


# ======================================================================
# is_alive convenience
# ======================================================================
def test_is_alive_true():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    async def go():
        async with OllamaClient(transport=_make_transport(handler)) as client:
            return await client.is_alive()

    assert _run(go()) is True


def test_is_alive_false_on_connect_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    async def go():
        async with OllamaClient(
            transport=_make_transport(handler),
            retry_attempts=1,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.is_alive()

    assert _run(go()) is False


# ======================================================================
# Retry on ConnectError -> eventual success
# ======================================================================
def test_connect_error_retries_then_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("transient")
        return httpx.Response(200, json={"models": []})

    async def go():
        async with OllamaClient(
            transport=_make_transport(handler),
            retry_attempts=3,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.list_models()

    assert _run(go()) == []
    assert calls["n"] == 2


# ======================================================================
# Image encoder
# ======================================================================
def test_encode_image_payload_accepts_bytes():
    out = _encode_image_payload(b"\x89PNG\r\n")
    assert isinstance(out, str)
    assert len(out) > 0


def test_encode_image_payload_passes_through_string():
    s = "AAAA"
    assert _encode_image_payload(s) == s


def test_encode_image_payload_rejects_bad_shape():
    bad = np.zeros((10, 10), dtype=np.uint8)  # 2D, not 3D
    with pytest.raises(OllamaError):
        _encode_image_payload(bad)


def test_encode_image_payload_handles_uint16_clip():
    arr = np.full((4, 4, 3), 500, dtype=np.uint16)
    out = _encode_image_payload(arr)
    assert isinstance(out, str) and len(out) > 0
