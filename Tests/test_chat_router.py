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


@pytest.fixture(autouse=True)
def active_chat_project(tmp_path):
    """Chat-Turns besitzen immer eine vollständige Projektidentität."""
    from backend.app_state import get_app_state

    state = get_app_state()
    project_root = tmp_path / "active-project"
    project_root.mkdir()
    with state._state_lock:
        previous_project = state.current_project
        state._project_epoch += 1
        state._project_capabilities.clear()
        state.current_project = {
            "db_project_id": 7001,
            "name": "Chat Test",
            "path": str(project_root),
        }
    yield state
    with state._state_lock:
        state._project_epoch += 1
        state._project_capabilities.clear()
        state.current_project = previous_project


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


def test_history_store_keeps_request_project_after_active_project_changes(
    tmp_path,
):
    from backend.routers.chat_router import _ChatHistoryStore

    async def run() -> None:
        store = _ChatHistoryStore()
        project_a = await store.bind_project(str(tmp_path / "a"))
        await store.append("user", "question-a", project_key=project_a)

        project_b = await store.bind_project(str(tmp_path / "b"))
        await store.append("user", "question-b", project_key=project_b)
        await store.append("assistant", "answer-a", project_key=project_a)

        assert await store.snapshot(project_a) == [
            {"role": "user", "content": "question-a"},
            {"role": "assistant", "content": "answer-a"},
        ]
        assert await store.snapshot(project_b) == [
            {"role": "user", "content": "question-b"},
        ]

    asyncio.run(run())


def test_client_supplied_history_is_trimmed_to_server_token_budget():
    from backend.routers.chat_router import _ChatHistoryStore

    store = _ChatHistoryStore()
    entries = [
        {"role": "assistant", "content": "x" * 6000},
        {"role": "user", "content": "newest"},
    ]

    trimmed = store.trim_for_llm(
        entries,
        max_tokens=2048,
        reserved_tokens=500,
    )

    assert trimmed == [{"role": "user", "content": "newest"}]


def test_project_switch_cancels_stream_with_typed_event_and_no_b_history(
    active_chat_project,
    tmp_path,
):
    from backend.routers import chat_router
    from backend.routers.chat_router import ChatMessageRequest
    from pb_studio.ai import chat_agent
    from pb_studio.ai.chat_agent import ChatEvent

    state = active_chat_project
    project_a = str(state.capture_project_context().project_root)
    project_b_path = tmp_path / "project-b"
    project_b_path.mkdir()
    started = asyncio.Event()

    class SlowToolAgent(_FakeAgent):
        async def process_message(self, *args, **kwargs):
            yield ChatEvent("tool_call", {"name": "audio_list_clips", "id": "slow"})
            started.set()
            await asyncio.Event().wait()

    async def run() -> list[dict[str, Any]]:
        original = chat_agent.ChatAgent
        chat_agent.ChatAgent = SlowToolAgent
        try:
            response = await chat_router.post_message(
                ChatMessageRequest(message="slow tool")
            )

            async def consume() -> str:
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(
                        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                    )
                return "".join(chunks)

            consumer = asyncio.create_task(consume())
            await asyncio.wait_for(started.wait(), timeout=2.0)
            state.invalidate_project_context()
            await state.cancel_and_drain_project_tasks(timeout_seconds=2.0)
            with state._state_lock:
                state.current_project = {
                    "db_project_id": 7002,
                    "name": "Project B",
                    "path": str(project_b_path),
                }
            events = _parse_sse(await asyncio.wait_for(consumer, timeout=2.0))

            project_a_entries = await chat_router._history_store.snapshot(project_a)
            project_b = await chat_router._history_store.bind_project(
                str(project_b_path)
            )
            project_b_entries = await chat_router._history_store.snapshot(project_b)
            assert project_a_entries == [{"role": "user", "content": "slow tool"}]
            assert project_b_entries == []
            return events
        finally:
            chat_agent.ChatAgent = original

    events = asyncio.run(run())
    error = next(event for event in events if event["event"] == "error")
    assert error["data"]["code"] == "project_context_changed"
    assert error["data"]["status_code"] == 409
    assert events[-1] == {
        "event": "done",
        "data": {"reason": "project_context_changed"},
    }
    assert state._project_capabilities == {}
    assert state._project_tasks == {}


def test_client_disconnect_revokes_turn_capability(
    active_chat_project,
):
    from backend.routers import chat_router
    from backend.routers.chat_router import ChatMessageRequest
    from pb_studio.ai import chat_agent
    from pb_studio.ai.chat_agent import ChatEvent

    exited = False

    class WaitingAgent(_FakeAgent):
        async def __aexit__(self, *args):
            nonlocal exited
            exited = True

        async def process_message(self, *args, **kwargs):
            yield ChatEvent("tool_confirmation_required", {
                "confirmation_id": "pending",
                "name": "render_start",
            })
            await asyncio.Event().wait()

    async def run() -> None:
        original = chat_agent.ChatAgent
        chat_agent.ChatAgent = WaitingAgent
        try:
            response = await chat_router.post_message(
                ChatMessageRequest(message="wait for confirmation")
            )
            iterator = response.body_iterator
            first = await iterator.__anext__()
            first_text = first.decode("utf-8") if isinstance(first, bytes) else first
            assert _parse_sse(first_text)[0]["event"] == "tool_confirmation_required"
            await iterator.aclose()
        finally:
            chat_agent.ChatAgent = original

    asyncio.run(run())
    assert exited is True
    assert active_chat_project._project_capabilities == {}
    assert active_chat_project._project_tasks == {}


def test_loopback_project_capability_is_valid_then_returns_409_when_stale(
    client,
    active_chat_project,
):
    from backend.app_state import PROJECT_CAPABILITY_HEADER

    state = active_chat_project
    capability = state.issue_project_capability(state.capture_project_context())
    headers = {PROJECT_CAPABILITY_HEADER: capability}

    assert client.get("/health", headers=headers).status_code == 200

    state.invalidate_project_context()
    stale = client.get("/health", headers=headers)
    assert stale.status_code == 409
    assert stale.json()["code"] == "project_context_changed"
