"""Test: _run_video_analysis befuellt dominant_colors + tags (L-K2)."""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def test_video_analysis_populates_dominant_colors(tmp_path):
    """Phase 4: result["dominant_colors"] + result["tags"] sind nach Analyse gesetzt."""
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "MoondreamTest",
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
            "peak_motion": 0.0,
            "avg_motion": 0.0,
            "motion_curve": [],
            "peak_frames": [],
            "motion_category": "low"
        },
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False
    }
    
    async def fake_color(
        video_path,
        clip_id,
        generate_captions,
        analyze_colors=True,
    ):
        if generate_captions:
            return {
                "dominant_colors": ["#ff0000"],
                "tags": ["red", "static"],
                "tag_source": "mock",
                "stage_status": {"colors": "completed", "captions": "completed"},
                "stage_errors": {},
            }
        else:
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
                "analyze_motion": False,
                "generate_embeddings": False,
                "generate_captions": True
            })
    finally:
        video_mod._run_scene_detection = orig_scene
        video_mod._run_video_gpu_analysis = orig_gpu
        video_mod._run_color_and_caption_analysis = orig_color
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "dominant_colors" in body
    assert body["dominant_colors"] == ["#ff0000"]
    assert "tags" in body
    assert body["tags"] == ["red", "static"]


def test_video_analysis_skips_phase4_when_captions_disabled(tmp_path):
    """generate_captions=False -> dominant_colors + tags sind leere Listen."""
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "MoondreamTest",
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
            "clip_id": 2,
            "peak_motion": 0.0,
            "avg_motion": 0.0,
            "motion_curve": [],
            "peak_frames": [],
            "motion_category": "low"
        },
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False
    }
    
    async def fake_color(
        video_path,
        clip_id,
        generate_captions,
        analyze_colors=True,
    ):
        if generate_captions:
            return {
                "dominant_colors": ["#ff0000"],
                "tags": ["red", "static"],
                "tag_source": "mock",
                "stage_status": {"colors": "completed", "captions": "completed"},
                "stage_errors": {},
            }
        else:
            return {
                "dominant_colors": [],
                "tags": [],
                "tag_source": "mock",
                "stage_status": {"colors": "completed", "captions": "skipped"},
                "stage_errors": {},
            }
    video_mod._run_color_and_caption_analysis = fake_color

    clip = {
        "id": 2, "name": "clip_2", "path": "C:/clip.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(2, clip)

    from pathlib import Path as _Path
    try:
        with patch.object(_Path, "exists", return_value=True):
            r = client.post("/video/analyze", json={
                "clip_id": 2,
                "detect_scenes": False,
                "analyze_motion": False,
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
    assert body["dominant_colors"] == []
    assert body["tags"] == []


def test_extract_dominant_colors_red_image():
    """Red-only image -> dominant_colors enthaelt rote Tones."""
    from pb_studio.video.moondream_wrapper import extract_dominant_colors

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :, 0] = 200  # red channel (RGB konvention)
    colors = extract_dominant_colors(frame, k=3)

    assert len(colors) >= 1
    assert all(c.startswith("#") for c in colors)
    # Erste (haeufigste) Farbe sollte hohen R-Wert haben
    first_r = int(colors[0][1:3], 16)
    assert first_r > 100, f"Expected red-dominant, got {colors[0]}"


def test_extract_dominant_colors_empty_returns_empty():
    """Leerer / None Frame -> [] (kein Crash)."""
    from pb_studio.video.moondream_wrapper import extract_dominant_colors

    assert extract_dominant_colors(np.array([])) == []
    assert extract_dominant_colors(None) == []


def test_extract_tags_falls_back_when_moondream_unavailable():
    """Bei fehlendem Moondream-ONNX-Modell -> leere Liste, kein Crash."""
    from pb_studio.video.moondream_wrapper import extract_tags_via_moondream

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    tags = extract_tags_via_moondream(frame)
    assert isinstance(tags, list)


def test_extract_tags_empty_input_returns_empty():
    """None / leeres Array -> [] ohne Moondream-Aufruf."""
    from pb_studio.video.moondream_wrapper import extract_tags_via_moondream

    assert extract_tags_via_moondream(None) == []
    assert extract_tags_via_moondream(np.array([])) == []


# ======================================================================
# onnx_models_available — Decoder-Pflicht (Audit 2026-08-07)
#
# Frueher genuegte der Encoder. Tag-Generierung braucht aber den Decoder:
# mit reinem Encoder reservierte jeder Clip 1800 MB und den GPU-Lock fuer
# einen Load, der garantiert null Tags liefert (logs/backend.log 2026-08-07).
# ======================================================================
def test_onnx_models_available_verlangt_decoder(tmp_path):
    from pb_studio.video.moondream import onnx_models_available

    (tmp_path / "moondream_encoder.onnx").write_bytes(b"x")
    assert onnx_models_available(str(tmp_path)) is False, (
        "Encoder allein darf keinen GPU-Task rechtfertigen"
    )

    (tmp_path / "moondream_decoder.onnx").write_bytes(b"x")
    assert onnx_models_available(str(tmp_path)) is True


def test_onnx_models_available_akzeptiert_kombiniertes_modell(tmp_path):
    from pb_studio.video.moondream import onnx_models_available

    assert onnx_models_available(str(tmp_path)) is False
    (tmp_path / "moondream.onnx").write_bytes(b"x")
    assert onnx_models_available(str(tmp_path)) is True
