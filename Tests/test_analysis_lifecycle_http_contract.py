"""OBJ-74 lifecycle contracts found by the live interruption run."""

from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request


class _LifecycleState:
    def __init__(self, *, current: bool) -> None:
        self.current = current
        self.context = SimpleNamespace(project_id=74, epoch=1)

    @asynccontextmanager
    async def project_operation(self):
        yield self.context

    def is_project_context_current(self, context) -> bool:
        assert context is self.context
        return self.current


@pytest.mark.parametrize(
    ("module_name", "entrypoint", "request_factory"),
    [
        (
            "backend.routers.audio_router",
            "analyze_audio",
            lambda: importlib.import_module(
                "backend.schemas.audio_schemas"
            ).AudioAnalyzeRequest(clip_id=1),
        ),
        (
            "backend.routers.video_router",
            "analyze_video",
            lambda: importlib.import_module(
                "backend.schemas.video_schemas"
            ).VideoAnalyzeRequest(clip_id=1),
        ),
    ],
)
def test_project_lifecycle_cancellation_returns_conflict(
    monkeypatch,
    module_name: str,
    entrypoint: str,
    request_factory,
) -> None:
    router = importlib.import_module(module_name)
    state = _LifecycleState(current=False)
    inner_name = (
        "_analyze_audio_in_context"
        if entrypoint == "analyze_audio"
        else "_analyze_video_in_project"
    )

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(router, inner_name, cancelled)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            getattr(router, entrypoint)(
                request_factory(),
                state,
                Request({"type": "http", "method": "POST", "path": "/analyze"}),
            )
        )

    assert exc_info.value.status_code == 409
    assert "Projektwechsel" in str(exc_info.value.detail)


@pytest.mark.parametrize(
    ("module_name", "entrypoint", "request_factory"),
    [
        (
            "backend.routers.audio_router",
            "analyze_audio",
            lambda: importlib.import_module(
                "backend.schemas.audio_schemas"
            ).AudioAnalyzeRequest(clip_id=1),
        ),
        (
            "backend.routers.video_router",
            "analyze_video",
            lambda: importlib.import_module(
                "backend.schemas.video_schemas"
            ).VideoAnalyzeRequest(clip_id=1),
        ),
    ],
)
def test_external_cancellation_still_propagates(
    monkeypatch,
    module_name: str,
    entrypoint: str,
    request_factory,
) -> None:
    router = importlib.import_module(module_name)
    state = _LifecycleState(current=True)
    inner_name = (
        "_analyze_audio_in_context"
        if entrypoint == "analyze_audio"
        else "_analyze_video_in_project"
    )

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(router, inner_name, cancelled)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(getattr(router, entrypoint)(request_factory(), state))


def test_shutdown_drains_project_operations_before_starting_timer(monkeypatch) -> None:
    main = importlib.import_module("backend.main")
    app_state = importlib.import_module("backend.app_state")
    calls: list[str] = []

    class _State:
        async def cancel_and_drain_project_tasks(self):
            calls.append("drain")
            return 2, 0

    class _Timer:
        def __init__(self, _seconds, _callback) -> None:
            self.daemon = False

        def start(self) -> None:
            calls.append("timer")

    monkeypatch.setattr(main, "authorize_owner", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_state, "get_app_state", lambda: _State())
    monkeypatch.setattr(main.threading, "Timer", _Timer)

    response = asyncio.run(main.shutdown("test-owner"))

    assert response == {"status": "shutting_down"}
    assert calls == ["drain", "timer"]
