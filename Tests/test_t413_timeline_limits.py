"""T413: Manual timeline requests have bounded entries and raw request bytes."""

from __future__ import annotations

import asyncio
import importlib
from contextlib import AsyncExitStack

import pytest
from pydantic import ValidationError
from starlette.requests import Request

pacing_router = importlib.import_module("backend.routers.pacing_router")
from backend.schemas.pacing_schemas import (
    TIMELINE_UPDATE_MAX_ENTRIES,
    TimelineUpdateRequest,
)


def _entry() -> dict[str, object]:
    return {
        "clip_id": "clip_1",
        "clip_name": "clip",
        "file_path": r"C:\\media\\clip.mp4",
        "start_time": 0.0,
        "end_time": 0.1,
    }


def _timeline_post_route():
    return next(
        route
        for route in pacing_router.router.routes
        if route.path == "/pacing/timeline" and "POST" in route.methods
    )


def _request(headers: list[tuple[bytes, bytes]], receive) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/pacing/timeline",
            "raw_path": b"/pacing/timeline",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 8765),
            "server": ("testserver", 80),
        },
        receive=receive,
    )


async def _run_route_handler(request: Request):
    async with AsyncExitStack() as stack:
        request.scope["fastapi_middleware_astack"] = stack
        return await _timeline_post_route().get_route_handler()(request)


def test_timeline_schema_rejects_more_than_documented_four_hour_maximum():
    # Product scope: 4 hours; WPF MinClipDuration: 0.1s => 144,000 cuts.
    with pytest.raises(ValidationError):
        TimelineUpdateRequest.model_validate(
            {"entries": [_entry()] * (TIMELINE_UPDATE_MAX_ENTRIES + 1)}
        )


def test_timeline_schema_accepts_valid_entry_shape():
    request = TimelineUpdateRequest.model_validate({"entries": [_entry()]})
    assert len(request.entries) == 1


def test_content_length_limit_rejects_before_fastapi_body_parse():
    async def receive():
        raise AssertionError("Body must not be read when Content-Length exceeds cap")

    request = _request(
        [
            (
                b"content-length",
                str(pacing_router.TIMELINE_UPDATE_MAX_BODY_BYTES + 1).encode("ascii"),
            )
        ],
        receive,
    )

    response = asyncio.run(_run_route_handler(request))

    assert response.status_code == 413


def test_chunked_body_limit_rejects_before_pydantic_parse(monkeypatch):
    monkeypatch.setattr(pacing_router, "TIMELINE_UPDATE_MAX_BODY_BYTES", 64)
    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 65, "more_body": False},
        ]
    )

    async def receive():
        return next(messages)

    request = _request([], receive)
    response = asyncio.run(_run_route_handler(request))

    assert response.status_code == 413
