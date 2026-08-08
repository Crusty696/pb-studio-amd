"""Test: motion.peak_motion wird berechnet (L-K3)."""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np


def test_run_video_analysis_sets_peak_motion(tmp_path):
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "MotionTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    app.dependency_overrides[get_app_state] = lambda: state
    client = TestClient(app)

    video_mod = sys.modules.get("backend.routers.video_router")
    if video_mod is None:
        import importlib
        video_mod = importlib.import_module("backend.routers.video_router")

    orig_scene = video_mod._run_scene_detection
    orig_gpu = video_mod._run_video_gpu_analysis
    orig_color = video_mod._run_color_and_caption_analysis

    video_mod._run_scene_detection = lambda *a, **kw: {"scene_count": 0, "scenes": []}
    video_mod._run_video_gpu_analysis = lambda *a, **kw: {
        "avg_motion": 5.0,
        "motion": {
            "clip_id": 1,
            "avg_motion": 5.0,
            "motion_curve": [1.0, 2.0, 3.0, 99.5, 4.0, 2.0],
            "peak_frames": [],
            "motion_category": "medium",
            "peak_motion": 99.5,
        },
        "embedding_dim": 512,
        "embedding_samples": 1,
        "has_embedding": True,
        "stage_status": {"motion": "completed", "embedding": "skipped"},
        "stage_errors": {},
    }
    
    async def fake_color(
        video_path,
        clip_id,
        generate_captions,
        analyze_colors=True,
    ):
        return {
            "dominant_colors": [],
            "tags": [],
            "tag_source": "mock",
            "stage_status": {"colors": "completed", "captions": "skipped"},
            "stage_errors": {},
        }
    video_mod._run_color_and_caption_analysis = fake_color

    clip = {
        "id": 1, "name": "clip_1", "path": "C:/clip.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(1, clip)

    from pathlib import Path as _Path
    try:
        with patch.object(_Path, "exists", return_value=True):
            r = client.post("/video/analyze", json={
                "clip_id": 1,
                "detect_scenes": False,
                "analyze_motion": True,
                "generate_embeddings": False,
                "generate_captions": False
            })
    finally:
        video_mod._run_scene_detection = orig_scene
        video_mod._run_video_gpu_analysis = orig_gpu
        video_mod._run_color_and_caption_analysis = orig_color
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "motion" in body
    assert "peak_motion" in body["motion"]
    assert body["motion"]["peak_motion"] == pytest.approx(99.5, abs=0.1)


def test_peak_motion_zero_when_empty(tmp_path):
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "MotionTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    app.dependency_overrides[get_app_state] = lambda: state
    client = TestClient(app)

    video_mod = sys.modules.get("backend.routers.video_router")
    if video_mod is None:
        import importlib
        video_mod = importlib.import_module("backend.routers.video_router")

    orig_scene = video_mod._run_scene_detection
    orig_gpu = video_mod._run_video_gpu_analysis
    orig_color = video_mod._run_color_and_caption_analysis

    video_mod._run_scene_detection = lambda *a, **kw: {"scene_count": 0, "scenes": []}
    video_mod._run_video_gpu_analysis = lambda *a, **kw: {
        "avg_motion": 0.0,
        "motion": {
            "clip_id": 1,
            "avg_motion": 0.0,
            "motion_curve": [],
            "peak_frames": [],
            "motion_category": "low",
            "peak_motion": 0.0,
        },
        "embedding_dim": 512,
        "embedding_samples": 0,
        "has_embedding": False,
        "stage_status": {"motion": "completed", "embedding": "skipped"},
        "stage_errors": {},
    }
    
    async def fake_color(
        video_path,
        clip_id,
        generate_captions,
        analyze_colors=True,
    ):
        return {
            "dominant_colors": [],
            "tags": [],
            "tag_source": "mock",
            "stage_status": {"colors": "completed", "captions": "skipped"},
            "stage_errors": {},
        }
    video_mod._run_color_and_caption_analysis = fake_color

    clip = {
        "id": 1, "name": "clip_1", "path": "C:/clip.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(1, clip)

    from pathlib import Path as _Path
    try:
        with patch.object(_Path, "exists", return_value=True):
            r = client.post("/video/analyze", json={
                "clip_id": 1,
                "detect_scenes": False,
                "analyze_motion": True,
                "generate_embeddings": False,
                "generate_captions": False
            })
    finally:
        video_mod._run_scene_detection = orig_scene
        video_mod._run_video_gpu_analysis = orig_gpu
        video_mod._run_color_and_caption_analysis = orig_color
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["motion"]["peak_motion"] == 0.0
