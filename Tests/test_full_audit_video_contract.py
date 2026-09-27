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
