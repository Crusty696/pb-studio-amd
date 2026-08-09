"""T413: Chat content must remain in chat SSE/history, never live logs."""

from __future__ import annotations

import asyncio
import logging

import pytest


@pytest.fixture
def active_chat_project(tmp_path):
    from backend.app_state import get_app_state

    state = get_app_state()
    project_root = (tmp_path / "active-chat-project").resolve()
    project_root.mkdir()
    with state._state_lock:
        previous_project = state.current_project
        state._project_epoch += 1
        state._project_capabilities.clear()
        state.current_project = {
            "db_project_id": 7413,
            "name": "T413 Chat Privacy",
            "path": str(project_root),
        }
    yield state, str(project_root)
    with state._state_lock:
        state._project_epoch += 1
        state._project_capabilities.clear()
        state.current_project = previous_project


def test_chat_content_is_not_copied_to_live_log_events(
    monkeypatch,
    caplog,
    active_chat_project,
):
    from backend.routers import chat_router
    from pb_studio.ai import chat_agent
    from pb_studio.ai.chat_agent import ChatEvent

    prompt = r"secret-prompt C:\Users\david\private.txt"
    answer = "secret-answer token=do-not-log"
    captured_logs: list[dict[str, str | None]] = []
    _, project_key = active_chat_project

    class FakeAgent:
        def __init__(self, *unused, **unused_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *unused):
            return None

        async def process_message(self, *unused, **kwargs):
            yield ChatEvent("text", {"content": answer})
            yield ChatEvent("tool_call", {"name": answer})
            yield ChatEvent("tool_result", {"name": prompt})
            yield ChatEvent("error", {"message": answer})
            yield ChatEvent("done", {"final_text": answer})

    async def capture_log(message, *, level="info", detail=None, source=None):
        captured_logs.append(
            {
                "message": message,
                "level": level,
                "detail": detail,
                "source": source,
            }
        )

    async def run() -> str:
        await chat_router._history_store.bind_project(project_key)
        await chat_router._history_store.clear(project_key)
        response = await chat_router.post_message(
            chat_router.ChatMessageRequest(message=prompt)
        )
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        history = await chat_router._history_store.snapshot(project_key)
        assert history == [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]
        await chat_router._history_store.clear(project_key)
        return "".join(chunks)

    monkeypatch.setattr(chat_agent, "ChatAgent", FakeAgent)
    monkeypatch.setattr(chat_router, "publish_log", capture_log)
    caplog.set_level(logging.INFO, logger=chat_router.logger.name)

    stream = asyncio.run(run())

    assert answer in stream
    serialized_logs = repr(captured_logs)
    assert prompt not in serialized_logs
    assert answer not in serialized_logs
    assert prompt not in caplog.text
    assert answer not in caplog.text
    assert {entry["source"] for entry in captured_logs} == {
        "chat.user",
        "chat.error",
        "chat.assistant",
        "chat.tool",
    }
    assert any(entry["detail"] == f"characters={len(prompt)}" for entry in captured_logs)
    assert any(entry["detail"] == f"characters={len(answer)}" for entry in captured_logs)


def test_chat_exception_text_is_not_written_to_backend_logs(
    monkeypatch,
    caplog,
    active_chat_project,
):
    from backend.routers import chat_router
    from pb_studio.ai import chat_agent

    secret = "exception-secret-do-not-log"

    class CrashingAgent:
        def __init__(self, *unused, **unused_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *unused):
            return None

        async def process_message(self, *unused, **kwargs):
            raise RuntimeError(secret)
            yield  # pragma: no cover

    async def run() -> None:
        response = await chat_router.post_message(
            chat_router.ChatMessageRequest(message="safe prompt")
        )
        async for _ in response.body_iterator:
            pass

    monkeypatch.setattr(chat_agent, "ChatAgent", CrashingAgent)
    caplog.set_level(logging.ERROR, logger=chat_router.logger.name)

    asyncio.run(run())

    assert secret not in caplog.text
