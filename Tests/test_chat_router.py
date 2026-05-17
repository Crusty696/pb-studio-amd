"""Tests fuer backend.routers.chat_router — Endpoint-Smoke-Tests via FastAPI TestClient.

Mockt den ChatAgent in chat_router auf einen Stub, damit kein echter Ollama
gebraucht wird.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app():
    """Importiert die FastAPI-App lazy (vermeidet Bootstrap-Side-Effects bei Collection)."""
    from backend.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


# ======================================================================
# GET /chat/tools
# ======================================================================
def test_get_tools_returns_inventory(client):
    r = client.get("/chat/tools")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 20
    assert isinstance(body["tools"], list)
    names = {t["name"] for t in body["tools"]}
    assert "audio.list_clips" in names
    assert "pacing.generate" in names
    assert "brain.suggest" in names


def test_get_tools_inventory_has_required_fields(client):
    r = client.get("/chat/tools")
    body = r.json()
    for entry in body["tools"]:
        assert {"name", "llm_name", "description", "category", "destructive", "parameters"} <= entry.keys()


# ======================================================================
# History endpoints
# ======================================================================
def test_clear_history(client):
    r = client.delete("/chat/history")
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"


def test_get_empty_history_after_clear(client):
    client.delete("/chat/history")
    r = client.get("/chat/history")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["entries"] == []


# ======================================================================
# POST /chat/message — SSE-Stream
# ======================================================================
class _FakeAgent:
    """Stand-In fuer ChatAgent, der vorgefertigte Events emittiert."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def process_message(self, user_text, history=None, *, mode="balance", model_override=None):
        from pb_studio.ai.chat_agent import ChatEvent

        yield ChatEvent("model", {"model": "fake:test", "reason": "stub", "mode": mode})
        yield ChatEvent("text", {"content": f"Echo: {user_text}"})
        yield ChatEvent("done", {"final_text": f"Echo: {user_text}"})


def _parse_sse(text: str) -> list[dict[str, Any]]:
    """Parsed SSE-Stream-Text in eine Liste von {event, data}."""
    out: list[dict[str, Any]] = []
    current_event = None
    data_lines: list[str] = []
    for line in text.split("\n"):
        if not line.strip():
            if data_lines:
                data_str = "\n".join(data_lines)
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = {"_raw": data_str}
                out.append({"event": current_event, "data": data})
            current_event = None
            data_lines = []
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
    return out


def test_post_message_streams_events(client):
    # ChatAgent wird in post_message lazy aus pb_studio.ai.chat_agent importiert.
    from pb_studio.ai import chat_agent
    original = chat_agent.ChatAgent
    chat_agent.ChatAgent = _FakeAgent
    try:
        r = client.post("/chat/message", json={"message": "Hallo Welt"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse(r.text)
        event_types = [e["event"] for e in events]
        assert "model" in event_types
        assert "text" in event_types
        assert "done" in event_types
        text_event = next(e for e in events if e["event"] == "text")
        assert "Hallo Welt" in text_event["data"]["content"]
    finally:
        chat_agent.ChatAgent = original


def test_post_message_validates_input(client):
    r = client.post("/chat/message", json={})
    assert r.status_code == 422


def test_post_message_validates_mode(client):
    r = client.post("/chat/message", json={"message": "hi", "mode": "invalid_mode"})
    assert r.status_code == 422


def test_post_message_accepts_explicit_history(client):
    from pb_studio.ai import chat_agent
    original = chat_agent.ChatAgent

    captured: dict[str, Any] = {}

    class CaptureAgent(_FakeAgent):
        async def process_message(self, user_text, history=None, *, mode="balance", model_override=None):
            captured["history"] = history
            captured["user_text"] = user_text
            captured["mode"] = mode
            from pb_studio.ai.chat_agent import ChatEvent
            yield ChatEvent("text", {"content": "ok"})
            yield ChatEvent("done", {"final_text": "ok"})

    chat_agent.ChatAgent = CaptureAgent
    try:
        r = client.post("/chat/message", json={
            "message": "go on",
            "history": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "second"},
            ],
            "mode": "speed",
            "save_history": False,
        })
        assert r.status_code == 200
        # Den Stream konsumieren damit handler durchlaufen
        _ = r.text
        assert captured["history"] is not None
        assert len(captured["history"]) == 2
        assert captured["user_text"] == "go on"
        assert captured["mode"] == "speed"
    finally:
        chat_agent.ChatAgent = original
