"""Release-readiness regressions for truthful video-pipeline results."""

from __future__ import annotations

import asyncio
import importlib

import numpy as np
import pytest


def _video_module():
    return importlib.import_module("backend.routers.video_router")


def test_raft_init_failure_is_not_a_static_zero_flow(monkeypatch):
    from pb_studio.video.raft import MotionAnalyzer

    analyzer = MotionAnalyzer()
    monkeypatch.setattr(analyzer, "_init_model", lambda: False)
    frame = np.zeros((16, 16, 3), dtype=np.uint8)

    with pytest.raises(RuntimeError, match="RAFT"):
        analyzer.calculate_flow(frame, frame)


def test_gpu_stage_failures_are_explicit(monkeypatch):
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    video_router = _video_module()
    class FakeCapture:
        def isOpened(self):
            return True

        def get(self, prop):
            import cv2

            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return 30
            if prop == cv2.CAP_PROP_FPS:
                return 30.0
            return 0

        def set(self, prop, value):
            return True

        def read(self):
            return True, np.zeros((32, 32, 3), dtype=np.uint8)

        def release(self):
            pass

    class FailedMotionAnalyzer:
        def analyze_video_segment(self, *args, **kwargs):
            raise RuntimeError("RAFT DML inference failed")

        def unload(self):
            pass

    class FailedSiglip:
        is_ready = False

        def __init__(self, *args, **kwargs):
            pass

        def unload(self):
            pass

    monkeypatch.setattr("cv2.VideoCapture", lambda _: FakeCapture())
    monkeypatch.setattr("pb_studio.video.raft.MotionAnalyzer", FailedMotionAnalyzer)
    monkeypatch.setattr("pb_studio.ai.siglip_wrapper.SigLIPWrapper", FailedSiglip)
    monkeypatch.setattr(
        video_router,
        "_get_reusable_embedding_metadata",
        lambda *args, **kwargs: None,
        raising=False,
    )

    result = video_router._run_video_gpu_analysis(
        "clip.mp4",
        7,
        VideoAnalyzeRequest(clip_id=7, analyze_motion=True, generate_embeddings=True),
    )

    assert result["stage_status"] == {"motion": "failed", "embedding": "failed"}
    assert "RAFT DML inference failed" in result["stage_errors"]["motion"]
    assert result["has_embedding"] is False


def test_color_analysis_runs_when_captions_are_disabled(monkeypatch):
    video_router = _video_module()
    class FakeCapture:
        def get(self, prop):
            import cv2

            return 12 if prop == cv2.CAP_PROP_FRAME_COUNT else 0

        def set(self, prop, value):
            return True

        def read(self):
            return True, np.zeros((16, 16, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr("cv2.VideoCapture", lambda _: FakeCapture())
    monkeypatch.setattr(
        "pb_studio.video.moondream_wrapper.extract_dominant_colors",
        lambda frame, k=5: ["#112233"],
    )

    result = asyncio.run(
        video_router._run_color_and_caption_analysis(
            "clip.mp4",
            3,
            generate_captions=False,
        )
    )

    assert result["dominant_colors"] == ["#112233"]
    assert result["tags"] == []
    assert result["tag_source"] == "skipped"


def test_representative_indices_are_bounded_and_span_video():
    from backend.routers.video_router import _representative_frame_indices

    indices = _representative_frame_indices(
        total_frames=1_000_000,
        desired_samples=500_000,
        max_samples=120,
        min_samples=2,
    )

    assert len(indices) == 120
    assert indices[0] == 0
    assert indices[-1] == 999_999
    assert indices == sorted(set(indices))


def test_motion_peaks_come_from_motion_curve():
    from backend.routers.video_router import _select_motion_peak_frames

    peaks = _select_motion_peak_frames(
        motion_values=[1.0, 9.0, 2.0, 7.0, 1.0],
        sampled_frame_indices=[0, 10, 20, 30, 40, 50],
        fps=10.0,
        max_peaks=2,
    )

    assert [peak["frame_index"] for peak in peaks] == [20, 40]
    assert peaks[0]["motion"] == 9.0
    assert peaks[0]["confidence"] == 1.0


def test_embedding_hash_hit_skips_siglip(monkeypatch):
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    video_router = _video_module()
    monkeypatch.setattr(
        video_router,
        "_get_reusable_embedding_metadata",
        lambda *args, **kwargs: {"embedding_dim": 1152, "embedding_samples": 24},
    )

    class MustNotLoad:
        def __init__(self, *args, **kwargs):
            raise AssertionError("SigLIP must not load on verified hash hit")

    monkeypatch.setattr("pb_studio.ai.siglip_wrapper.SigLIPWrapper", MustNotLoad)

    result = video_router._run_video_gpu_analysis(
        "clip.mp4",
        9,
        VideoAnalyzeRequest(
            clip_id=9,
            analyze_motion=False,
            generate_embeddings=True,
        ),
        video_hash="same-content-hash",
    )

    assert result["has_embedding"] is True
    assert result["embedding_dim"] == 1152
    assert result["embedding_samples"] == 24
    assert result["stage_status"]["embedding"] == "completed"
    assert result["embedding_reused"] is True


def test_scene_confidence_is_nullable_without_detector_score(monkeypatch):
    video_router = _video_module()
    class FakeDetector:
        def detect_scenes(self, path):
            return [(0.0, 2.5)]

    monkeypatch.setattr("pb_studio.video.scene_detect.SceneDetector", FakeDetector)

    result = video_router._run_scene_detection("clip.mp4", True)

    assert result["scenes"][0]["confidence"] is None


def test_import_progress_uses_input_position_for_skips(monkeypatch, tmp_path):
    from backend.schemas.video_schemas import VideoImportRequest

    video_router = _video_module()
    class FakeState:
        def require_current_project_db_id(self):
            return 1

    events = []

    async def capture_event(name, payload):
        events.append((name, payload))

    monkeypatch.setattr(video_router, "publish_event", capture_event)
    missing_a = tmp_path / "missing-a.mp4"
    missing_b = tmp_path / "missing-b.mp4"

    result = asyncio.run(
        video_router.import_videos(
            VideoImportRequest(paths=[str(missing_a), str(missing_b)]),
            FakeState(),
        )
    )

    input_events = [
        payload
        for name, payload in events
        if name == "import_progress" and payload.get("step") == "input"
    ]
    assert result == []
    assert [event["percent"] for event in input_events] == [50.0, 100.0]


def test_video_schema_exposes_truthful_stage_and_color_controls():
    from backend.schemas.video_schemas import (
        SceneInfo,
        VideoAnalyzeRequest,
        VideoAnalysisResult,
    )

    request = VideoAnalyzeRequest(clip_id=1)
    result = VideoAnalysisResult(
        clip_id=1,
        status="partial",
        stage_status={"motion": "failed"},
        stage_errors={"motion": "DML failure"},
    )

    assert request.analyze_colors is True
    assert SceneInfo(start_time=0.0, end_time=1.0).confidence is None
    assert result.status == "partial"
    assert result.stage_status["motion"] == "failed"
