"""Tests fuer pb_studio.ai.lmstudio_client (HTTP-only, gemocked via httpx.MockTransport).

LM Studio Refactor 2026-05-17: deckt die OpenAI-kompatiblen Endpunkte ab —
GET /v1/models, POST /v1/chat/completions (non-streaming + streaming),
POST /v1/embeddings, NotImplementedError fuer pull_model/delete_model.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import numpy as np
import pytest

from pb_studio.ai.lmstudio_client import (
    LMStudioClient,
    LMStudioConnectionError,
    LMStudioError,
    LMStudioResponseError,
)


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def _make_transport(handler):
    return httpx.MockTransport(handler)


def _run(coro):
    return asyncio.run(coro)


# ======================================================================
# /v1/models
# ======================================================================
def test_list_models_parses_data_array():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/models")
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "qwen/qwen3-vl-8b", "object": "model", "owned_by": "test"},
                    {"id": "google/gemma-4-e4b", "object": "model", "owned_by": "test"},
                ],
                "object": "list",
            },
        )

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.list_models()

    models = _run(go())
    assert len(models) == 2
    assert models[0].name == "qwen/qwen3-vl-8b"
    assert models[1].name == "google/gemma-4-e4b"


def test_list_models_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "object": "list"})

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.list_models()

    assert _run(go()) == []


def test_list_models_retries_then_fails_with_5xx():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    async def go():
        async with LMStudioClient(
            transport=_make_transport(handler),
            retry_attempts=3,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.list_models()

    with pytest.raises(LMStudioError):
        _run(go())
    # retried at least once
    assert calls["n"] >= 2


def test_list_models_handles_connect_error_retries_then_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async def go():
        async with LMStudioClient(
            transport=_make_transport(handler),
            retry_attempts=2,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.list_models()

    with pytest.raises(LMStudioConnectionError):
        _run(go())


def test_lmstudio_capabilities_distinguish_embedding_from_chat_and_vision():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/v0/models"):
            return httpx.Response(200, json={"data": [
                {"id": "embed-only", "type": "embeddings"},
                {"id": "chat-model", "type": "llm"},
                {"id": "vision-model", "type": "vlm"},
            ]})
        return httpx.Response(200, json={"data": [
            {"id": "embed-only"},
            {"id": "chat-model"},
            {"id": "vision-model"},
        ]})

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            capabilities = await client.get_model_capabilities()
            has_chat = await client.supports_capability("chat")
            has_vision = await client.supports_capability("vision")
            return capabilities, has_chat, has_vision

    capabilities, has_chat, has_vision = _run(go())
    assert capabilities["embed-only"] == {"embedding"}
    assert capabilities["chat-model"] == {"chat"}
    assert capabilities["vision-model"] == {"chat", "vision"}
    assert has_chat is True
    assert has_vision is True


def test_embedding_only_provider_is_alive_but_not_chat_or_vision_capable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/v0/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": "embed-only", "type": "embeddings"}]},
            )
        return httpx.Response(200, json={"data": [{"id": "embed-only"}]})

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return (
                await client.is_alive(),
                await client.supports_capability("chat"),
                await client.supports_capability("vision"),
            )

    assert _run(go()) == (True, False, False)


# ======================================================================
# /v1/chat/completions  (non-streaming)
# ======================================================================
def _chat_response(content: str = "Hi.", *, tool_calls=None, reasoning: str = "") -> dict:
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [{
            "index": 0,
            "message": msg,
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


def test_chat_returns_ollama_style_message():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "test-model"
        assert body["messages"][0]["role"] == "user"
        return httpx.Response(200, json=_chat_response("Antwort"))

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="test-model",
                messages=[{"role": "user", "content": "Hallo"}],
            )

    resp = _run(go())
    assert resp["message"]["role"] == "assistant"
    assert resp["message"]["content"] == "Antwort"
    assert resp["done"] is True
    assert resp["usage"]["total_tokens"] == 8


def test_chat_with_tools_passes_tools_param():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured["body"] = body
        return httpx.Response(
            200,
            json=_chat_response(
                "",
                tool_calls=[{
                    "id": "call_42",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city":"Berlin"}'},
                }],
            ),
        )

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="x",
                messages=[{"role": "user", "content": "Wetter"}],
                tools=[{"type": "function", "function": {"name": "get_weather"}}],
            )

    resp = _run(go())
    assert captured["body"]["tools"][0]["function"]["name"] == "get_weather"
    tcs = resp["message"]["tool_calls"]
    assert len(tcs) == 1
    assert tcs[0]["id"] == "call_42"
    assert tcs[0]["function"]["name"] == "get_weather"


def test_chat_with_images_converts_to_openai_image_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        captured["body"] = body
        return httpx.Response(200, json=_chat_response("ok"))

    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[:, :, 0] = 255

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="x",
                messages=[{"role": "user", "content": "What is this?"}],
                images=[frame],
            )

    _run(go())
    last_msg = captured["body"]["messages"][-1]
    # OpenAI Vision-Format: content ist eine Liste mit text + image_url parts
    assert isinstance(last_msg["content"], list)
    types = [p["type"] for p in last_msg["content"]]
    assert "image_url" in types


def test_chat_options_mapped_to_openai_fields():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_chat_response("ok"))

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="x",
                messages=[{"role": "user", "content": "Hi"}],
                options={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "num_predict": 100,
                    "stop": ["\n"],
                    "seed": 42,
                },
            )

    _run(go())
    body = captured["body"]
    assert body["temperature"] == 0.7
    assert body["top_p"] == 0.95
    assert body["max_tokens"] == 100  # num_predict -> max_tokens
    assert body["stop"] == ["\n"]
    assert body["seed"] == 42


def test_chat_5xx_raises_response_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server boom")

    async def go():
        async with LMStudioClient(
            transport=_make_transport(handler),
            retry_attempts=1,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.chat(
                model="x",
                messages=[{"role": "user", "content": "Hi"}],
            )

    with pytest.raises(LMStudioError):
        _run(go())


def test_chat_format_json_sets_response_format():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_chat_response('{"x":1}'))

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.chat(
                model="x",
                messages=[{"role": "user", "content": "JSON bitte"}],
                format="json",
            )

    _run(go())
    assert captured["body"]["response_format"]["type"] == "json_object"


# ======================================================================
# /v1/chat/completions  (streaming)
# ======================================================================
def test_chat_stream_yields_events():
    """LM Studio liefert SSE-Chunks im OpenAI-Streaming-Format."""
    chunks = [
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"Hel"}}]}\n\n',
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"lo"}}]}\n\n',
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
        b'data: [DONE]\n\n',
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=httpx.ByteStream(b"".join(chunks)),
            headers={"content-type": "text/event-stream"},
        )

    async def go():
        events = []
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            async for ev in client.chat_stream(
                model="x",
                messages=[{"role": "user", "content": "Hi"}],
            ):
                events.append(ev)
        return events

    events = _run(go())
    # min 1 content-event + 1 done-event
    assert any(ev.get("done") for ev in events), f"no done event: {events}"
    # akkumulierter Content
    contents = [ev.get("message", {}).get("content", "") for ev in events if not ev.get("done")]
    assert "".join(contents).endswith("lo") or "Hello" in "".join(contents)


# ======================================================================
# /v1/embeddings
# ======================================================================
def test_embeddings_returns_vectors():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/embeddings")
        body = json.loads(request.content.decode())
        n = 1 if isinstance(body["input"], str) else len(body["input"])
        return httpx.Response(
            200,
            json={
                "data": [
                    {"object": "embedding", "embedding": [0.1, 0.2, 0.3], "index": i}
                    for i in range(n)
                ],
                "object": "list",
                "model": body["model"],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.embeddings(
                model="text-embedding-nomic-embed-text-v1.5",
                input="hello world",
            )

    out = _run(go())
    assert len(out) == 1
    assert out[0] == [0.1, 0.2, 0.3]


# ======================================================================
# pull_model / delete_model — NICHT unterstuetzt
# ======================================================================
def test_pull_model_raises_not_implemented():
    async def go():
        async with LMStudioClient(base_url="http://fake/v1") as client:
            await client.pull_model("some-model")

    with pytest.raises(NotImplementedError):
        _run(go())


def test_delete_model_raises_not_implemented():
    async def go():
        async with LMStudioClient(base_url="http://fake/v1") as client:
            await client.delete_model("some-model")

    with pytest.raises(NotImplementedError):
        _run(go())


# ======================================================================
# is_alive
# ======================================================================
def test_is_alive_true_when_models_endpoint_returns_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "object": "list"})

    async def go():
        async with LMStudioClient(transport=_make_transport(handler)) as client:
            return await client.is_alive()

    assert _run(go()) is True


def test_is_alive_false_when_server_down():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async def go():
        async with LMStudioClient(
            transport=_make_transport(handler),
            retry_attempts=1,
            retry_backoff_seconds=0.01,
        ) as client:
            return await client.is_alive()

    assert _run(go()) is False
