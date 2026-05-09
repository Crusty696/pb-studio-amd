"""Test: _run_video_analysis befuellt dominant_colors + tags (L-K2)."""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def test_video_analysis_populates_dominant_colors():
    """Phase 4: result["dominant_colors"] + result["tags"] sind nach Analyse gesetzt."""
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    # Roter Mid-Frame (480x640 RGB)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    fake_frame[:, :, 2] = 255  # OpenCV BGR -> red channel index 2

    # Mocke cv2.VideoCapture global (wird in Phase 2 motion + Phase 4 L-K2 verwendet)
    mock_cap_instance = MagicMock()
    # CAP_PROP_FRAME_COUNT=10, CAP_PROP_FPS=30 — wird mehrfach abgefragt.
    # side_effect rotiert; um beide Phasen zu bedienen verwende return-cycle:
    mock_cap_instance.get.side_effect = lambda *a, **k: 10
    mock_cap_instance.read.return_value = (True, fake_frame)
    mock_cap_instance.set.return_value = None
    mock_cap_instance.release.return_value = None

    with patch("cv2.VideoCapture", return_value=mock_cap_instance), \
         patch("pb_studio.video.scene_detect.SceneDetector") as mock_scene, \
         patch("pb_studio.video.raft.MotionAnalyzer") as mock_motion_cls:

        mock_scene.return_value.detect_scenes.return_value = []
        mock_motion = mock_motion_cls.return_value
        mock_motion.analyze_video_segment.return_value = {
            "avg_motion": 5.0,
            "frame_motions": [1.0, 2.0],
            "scene_changes": [],
        }
        mock_motion.unload = lambda: None

        req = VideoAnalyzeRequest(
            clip_id=1,
            detect_scenes=True,
            analyze_motion=True,
            generate_embeddings=False,
            generate_captions=True,
        )
        result = _run_video_analysis("/tmp/fake.mp4", 1, req)

    assert "dominant_colors" in result
    assert isinstance(result["dominant_colors"], list)
    assert "tags" in result
    assert isinstance(result["tags"], list)


def test_video_analysis_skips_phase4_when_captions_disabled():
    """generate_captions=False -> dominant_colors + tags sind leere Listen."""
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    req = VideoAnalyzeRequest(
        clip_id=2,
        detect_scenes=False,
        analyze_motion=False,
        generate_embeddings=False,
        generate_captions=False,
    )
    result = _run_video_analysis("/tmp/fake.mp4", 2, req)

    assert result["dominant_colors"] == []
    assert result["tags"] == []


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
