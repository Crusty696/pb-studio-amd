"""Regression contracts for the video findings in full audit T002."""

from __future__ import annotations

import asyncio
import importlib
import subprocess
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.unauthorized_backend


def _router():
    return importlib.import_module("backend.routers.video_router")


def test_unavailable_analysis_stage_is_failed_and_retryable():
    router = _router()
    result = router._empty_video_analysis_result(1)
    result["stage_status"] = {"motion": "unavailable"}

    assert router._derive_video_analysis_status(result["stage_status"]) == "failed"
    assert router._video_stage_should_run("motion", True, False, result)


def test_partial_frame_caption_coverage_cannot_be_completed(monkeypatch):
    router = _router()

    class Capture:
        def get(self, prop):
            import cv2

            return 12 if prop == cv2.CAP_PROP_FRAME_COUNT else 0

        def set(self, *_args):
            return True

        def read(self):
            if not hasattr(self, "count"):
                self.count = 0
            self.count += 1
            return (True, np.zeros((16, 16, 3), dtype=np.uint8)) if self.count <= 3 else (False, None)

        def release(self):
            pass

    async def tags_for_first_frame(_frame, mode):
        tags_for_first_frame.calls += 1
        return (["stage"] if tags_for_first_frame.calls == 1 else []), "test-model"

    tags_for_first_frame.calls = 0
    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr("cv2.VideoCapture", lambda _path: Capture())
    monkeypatch.setattr(
        "pb_studio.video.lmstudio_vision_wrapper.extract_tags_and_model_via_lmstudio_async",
        tags_for_first_frame,
    )
    monkeypatch.setattr("pb_studio.video.moondream.onnx_models_available", lambda: False)
    monkeypatch.setattr(router, "publish_event", no_event)
    monkeypatch.setattr(router, "CAPTION_HEARTBEAT_INTERVAL_SECONDS", 0.01)

    result = asyncio.run(router._run_color_and_caption_analysis(
        "clip.mp4", 1, generate_captions=True, analyze_colors=False
    ))

    assert result["tags"] == ["stage"]
    assert result["stage_status"]["captions"] == "partial"


@pytest.mark.parametrize("failed_operation", ["seek", "read"])
def test_unread_sampled_frame_is_in_caption_coverage_denominator(
    monkeypatch,
    failed_operation,
):
    router = _router()

    class OneUnreadSample:
        def get(self, prop):
            import cv2

            return 12 if prop == cv2.CAP_PROP_FRAME_COUNT else 0

        def set(self, _prop, frame_index):
            self.frame_index = int(frame_index)
            return not (failed_operation == "seek" and self.frame_index == 6)

        def read(self):
            if failed_operation == "read" and self.frame_index == 6:
                return False, None
            return True, np.zeros((16, 16, 3), dtype=np.uint8)

        def release(self):
            pass

    async def tags_for_every_decoded_frame(_frame, mode):
        return ["stage"], "test-model"

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr("cv2.VideoCapture", lambda _path: OneUnreadSample())
    monkeypatch.setattr(
        "pb_studio.video.lmstudio_vision_wrapper.extract_tags_and_model_via_lmstudio_async",
        tags_for_every_decoded_frame,
    )
    monkeypatch.setattr("pb_studio.video.moondream.onnx_models_available", lambda: False)
    monkeypatch.setattr(router, "publish_event", no_event)
    monkeypatch.setattr(router, "CAPTION_HEARTBEAT_INTERVAL_SECONDS", 0.01)

    result = asyncio.run(router._run_color_and_caption_analysis(
        "clip.mp4", 2, generate_captions=True, analyze_colors=False
    ))

    assert result["stage_status"]["captions"] == "partial"
    assert "2/3" in result["stage_errors"]["captions"]
    assert "6" in result["stage_errors"]["captions"]
    assert result["tags"] == ["stage"]

    aggregate = router._empty_video_analysis_result(2)
    aggregate["stage_status"]["scenes"] = "completed"
    router._merge_video_stage_outcome(aggregate, result, "captions")
    assert aggregate["stage_status"]["captions"] == "partial"
    assert aggregate["tags"] == ["stage"]
    assert router._derive_video_analysis_status(aggregate["stage_status"]) == "partial"


def test_ffprobe_failure_is_not_reported_as_missing_audio(monkeypatch, tmp_path):
    from pb_studio.video import audio_key_detector

    media = tmp_path / "probe.mp4"
    media.write_bytes(b"fixture")
    monkeypatch.setattr(
        audio_key_detector.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "probe failed"),
    )

    with pytest.raises(RuntimeError, match="ffprobe"):
        audio_key_detector.has_video_audio_stream(media)


def test_audio_key_outcomes_distinguish_no_stream_from_probe_error():
    router = _router()

    no_stream = router._empty_video_analysis_result(3)
    router._set_video_audio_key_outcome(no_stream, None)
    assert no_stream["stage_status"]["audio_key"] == "unavailable"
    assert "audio_key" not in no_stream["stage_errors"]

    probe_failed = router._empty_video_analysis_result(4)
    router._set_video_audio_key_outcome(
        probe_failed,
        None,
        error=RuntimeError("ffprobe timed out"),
    )
    assert probe_failed["stage_status"]["audio_key"] == "failed"
    assert probe_failed["stage_errors"]["audio_key"] == "ffprobe timed out"

    detected = router._empty_video_analysis_result(5)
    router._set_video_audio_key_outcome(detected, "C major")
    assert detected["stage_status"]["audio_key"] == "completed"
    assert detected["audio_key"] == "C major"


def test_caption_provider_outage_is_not_retried_for_every_frame(monkeypatch):
    router = _router()

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

    calls = 0

    async def provider_unavailable(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return [], "none"

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr("cv2.VideoCapture", lambda _path: ThreeFrames())
    monkeypatch.setattr(
        "pb_studio.video.lmstudio_vision_wrapper.extract_tags_and_model_via_lmstudio_async",
        provider_unavailable,
    )
    monkeypatch.setattr("pb_studio.video.moondream.onnx_models_available", lambda: False)
    monkeypatch.setattr(router, "publish_event", no_event)

    result = asyncio.run(router._run_color_and_caption_analysis(
        "clip.mp4", 8, generate_captions=True, analyze_colors=False
    ))

    assert calls == 1
    assert result["stage_status"]["captions"] == "unavailable"
    assert "provider" in result["stage_errors"]["captions"].lower()
    assert router._derive_video_analysis_status(result["stage_status"]) == "failed"


def test_caption_provider_outage_keeps_full_moondream_fallback(monkeypatch):
    router = _router()

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

    calls = 0

    async def provider_unavailable(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return [], "none"

    async def no_event(*_args, **_kwargs):
        return None

    async def gpu_task(function, frames, **_kwargs):
        return function(frames)

    monkeypatch.setattr("cv2.VideoCapture", lambda _path: ThreeFrames())
    monkeypatch.setattr(
        "pb_studio.video.lmstudio_vision_wrapper.extract_tags_and_model_via_lmstudio_async",
        provider_unavailable,
    )
    monkeypatch.setattr("pb_studio.video.moondream.onnx_models_available", lambda: True)
    monkeypatch.setattr(router, "_run_moondream_inference_on_frames", lambda frames: [["fallback"] for _ in frames])
    monkeypatch.setattr(router, "with_gpu_task", gpu_task)
    monkeypatch.setattr(router, "publish_event", no_event)

    result = asyncio.run(router._run_color_and_caption_analysis(
        "clip.mp4", 9, generate_captions=True, analyze_colors=False
    ))

    assert calls == 1
    assert result["tags"] == ["fallback"]
    assert result["tag_source"] == "moondream"
    assert result["stage_status"]["captions"] == "completed"


def test_embedding_resume_checks_vector_link_and_tombstone(monkeypatch):
    router = _router()
    database_core = importlib.import_module("pb_studio.data.database_core")
    media_repository = importlib.import_module(
        "pb_studio.data.repositories.media_repository"
    )
    vector_store = importlib.import_module("pb_studio.data.vector_store")

    class FakeRepo:
        def find_by_project_and_path(self, **_kwargs):
            return {"id": 12, "file_hash": "hash"}

    class FakeConnection:
        def execute(self, *_args):
            return [(41,)]

    class FakeDatabase:
        def get_connection(self):
            return FakeConnection()

    class FakeVectors:
        _lock = __import__("threading").RLock()
        _tombstoned_ids = {41}
        index = type("Index", (), {"ntotal": 50})()
        metadata = {41: {"path": "C:/clip.mp4", "video_hash": "hash"}}

        def __init__(self, **_kwargs):
            pass

        def _ensure_open(self):
            pass

    monkeypatch.setattr(media_repository, "MediaRepository", FakeRepo)
    monkeypatch.setattr(database_core, "DatabaseCore", FakeDatabase)
    monkeypatch.setattr(vector_store, "VectorStore", FakeVectors)

    class State:
        def require_project_context_current(self, _context):
            pass

        def get_video_clip(self, _clip_id):
            return {"video_hash": "hash"}

        def get_video_analysis(self, _clip_id):
            return {"has_embedding": True, "embedding_dim": 1152, "embedding_samples": 1}

    assert router._get_reusable_embedding_metadata(
        "C:/clip.mp4", 1, "hash", State(), type("Context", (), {"project_id": 1})()
    ) is None


def test_video_library_reconciles_later_success_and_shows_partial_scenes():
    source = Path("PBStudio.UI/ViewModels/VideoLibraryViewModel.cs").read_text(encoding="utf-8")

    assert "requestFailures.Remove(target.Id)" in source
    assert "HasCompletedScenes(selectedResult)" in source
    assert "Scenes" in source
