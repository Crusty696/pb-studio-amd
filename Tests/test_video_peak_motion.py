"""Test: motion.peak_motion wird berechnet (L-K3)."""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np


def test_run_video_analysis_sets_peak_motion(tmp_path):
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.VideoCapture") as mock_cap, \
         patch("pb_studio.video.scene_detect.SceneDetector"), \
         patch("pb_studio.video.raft.MotionAnalyzer") as mock_motion_cls:

        mock_instance = MagicMock()
        mock_instance.get.side_effect = lambda *a: 100 if a[0] == 7 else 30.0
        mock_instance.read.return_value = (True, fake_frame)
        mock_cap.return_value = mock_instance

        mock_motion = mock_motion_cls.return_value
        mock_motion.analyze_video_segment.return_value = {
            "avg_motion": 5.0,
            "frame_motions": [1.0, 2.0, 3.0, 99.5, 4.0, 2.0],
            "scene_changes": [],
        }
        mock_motion.unload = lambda: None

        req = VideoAnalyzeRequest(
            clip_id=1, detect_scenes=False, analyze_motion=True,
            generate_embeddings=False, generate_captions=False
        )
        result = _run_video_analysis("/tmp/fake.mp4", 1, req)

    assert "motion" in result
    assert "peak_motion" in result["motion"]
    assert result["motion"]["peak_motion"] == pytest.approx(99.5, abs=0.1)


def test_peak_motion_zero_when_empty():
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest

    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.VideoCapture") as mock_cap, \
         patch("pb_studio.video.scene_detect.SceneDetector"), \
         patch("pb_studio.video.raft.MotionAnalyzer") as mock_motion_cls:

        mock_instance = MagicMock()
        mock_instance.get.side_effect = lambda *a: 100 if a[0] == 7 else 30.0
        mock_instance.read.return_value = (True, fake_frame)
        mock_cap.return_value = mock_instance

        mock_motion = mock_motion_cls.return_value
        mock_motion.analyze_video_segment.return_value = {
            "avg_motion": 0.0,
            "frame_motions": [],
            "scene_changes": [],
        }
        mock_motion.unload = lambda: None

        req = VideoAnalyzeRequest(
            clip_id=1, detect_scenes=False, analyze_motion=True,
            generate_embeddings=False, generate_captions=False
        )
        result = _run_video_analysis("/tmp/fake.mp4", 1, req)

    assert result["motion"]["peak_motion"] == 0.0
