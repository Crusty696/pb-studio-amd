"""Spec 00035: caption progress must not misidentify a selectable provider."""

from __future__ import annotations

import asyncio
import importlib

import numpy as np
import pytest

pytestmark = pytest.mark.unauthorized_backend


@pytest.mark.parametrize("timed_out", [False, True])
def test_caption_progress_uses_provider_neutral_labels(monkeypatch, timed_out):
    router = importlib.import_module("backend.routers.video_router")

    class ThreeFrames:
        def get(self, prop):
            import cv2

            return 12 if prop == cv2.CAP_PROP_FRAME_COUNT else 0

        def set(self, *_args):
            return True

        def read(self):
            return True, np.zeros((16, 16, 3), dtype=np.uint8)

        def release(self):
            pass

    events = []

    async def caption_frame(*_args, **_kwargs):
        await asyncio.sleep(0.8 if timed_out else 0.005)
        return ["stage"], "qwen3.5:9b"

    async def capture_event(name, payload):
        events.append((name, payload))

    monkeypatch.setattr("cv2.VideoCapture", lambda _path: ThreeFrames())
    monkeypatch.setattr(
        "pb_studio.video.lmstudio_vision_wrapper.extract_tags_and_model_via_lmstudio_async",
        caption_frame,
    )
    monkeypatch.setattr(
        "pb_studio.video.moondream.onnx_models_available", lambda: False
    )
    monkeypatch.setattr(router, "publish_event", capture_event)
    monkeypatch.setattr(router, "CAPTION_HEARTBEAT_INTERVAL_SECONDS", 0.001)
    if timed_out:
        monkeypatch.setattr(router, "CAPTION_STAGE_TIMEOUT_SECONDS", 0.7)

    result = asyncio.run(
        router._run_color_and_caption_analysis(
            "clip.mp4", 35, generate_captions=True, analyze_colors=False
        )
    )

    progress = [payload for name, payload in events if name == "analysis_progress"]
    assert progress
    assert any("Vision-Analyse Vision-Provider" in p["message"] for p in progress)
    assert all("LM Studio" not in p["message"] for p in progress)
    if timed_out:
        timeout_messages = [
            p["message"] for p in progress if p["step"] == "captions_primary_timeout"
        ]
        assert timeout_messages
        assert "Vision-Provider" in timeout_messages[0]
        assert "LM Studio" not in timeout_messages[0]
        assert result["stage_status"]["captions"] == "failed"
    else:
        idle = [
            payload
            for name, payload in events
            if name == "llm_status" and payload.get("status") == "idle"
        ]
        assert idle
        assert idle[-1]["provider"] == "Vision Provider"
        assert result["stage_status"]["captions"] == "completed"
