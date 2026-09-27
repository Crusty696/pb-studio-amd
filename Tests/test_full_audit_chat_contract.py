"""Regression contracts for chat audit findings C01-C03."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from pb_studio.ai.tool_registry import build_default_registry


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.unauthorized_backend


def test_render_status_with_null_error_is_successful_tool_result(monkeypatch):
    registry = build_default_registry()
    tool = registry.get("render.status")
    assert tool is not None
    from pb_studio.ai import tool_registry

    async def fake_call(method, path, *, http_client, **kwargs):
        assert method == "GET"
        assert path == "/render/status/task-1"
        return {"status": "completed", "percent": 100, "error": None}

    monkeypatch.setattr(tool_registry, "_call", fake_call)

    async def invoke():
        async with httpx.AsyncClient(base_url="http://test") as client:
            return await tool.handler({"task_id": "task-1"}, http_client=client)

    result = asyncio.run(invoke())
    assert result == {"status": "completed", "percent": 100, "error": None}

    source = (ROOT / "src/pb_studio/ai/chat_agent.py").read_text(encoding="utf-8")
    assert 'result.get("error") is not None' in source


def test_video_only_chat_render_does_not_require_audio_path(monkeypatch):
    registry = build_default_registry()
    tool = registry.get("render.start")
    assert tool is not None
    captured = {}

    from pb_studio.ai import tool_registry

    async def fake_call(method, path, *, http_client, json_body=None, **kwargs):
        captured["body"] = json_body
        assert method == "POST"
        assert path == "/render/start"
        return {"task_id": "task-1"}

    monkeypatch.setattr(tool_registry, "_call", fake_call)

    async def invoke():
        async with httpx.AsyncClient(
            base_url="http://test"
        ) as client:
            return await tool.handler(
                {"output_path": "C:/out.mp4", "include_audio": False},
                http_client=client,
            )

    assert asyncio.run(invoke()) == {"task_id": "task-1"}
    assert captured["body"]["audio_path"] == ""
    assert captured["body"]["include_audio"] is False
    schema = tool.parameters
    assert "audio_path" not in schema.get("required", [])


def test_clear_history_response_is_project_generation_guarded():
    source = (ROOT / "PBStudio.UI/ViewModels/ChatViewModel.cs").read_text(
        encoding="utf-8"
    )
    clear = source[source.index("public async Task ClearAsync()"):]
    assert "var expectedProjectPath = _projectPath;" in clear
    assert "var expectedGeneration = Volatile.Read(ref _streamGeneration);" in clear
    assert "expectedGeneration != Volatile.Read(ref _streamGeneration)" in clear
    guard = clear.index("expectedProjectPath,")
    assert clear.index("Messages.Clear();") > guard
