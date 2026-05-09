"""Test: _run_pacing_generation reicht volle video_analysis Daten an Engine durch (Audit A4)."""
import pytest
from unittest.mock import patch, MagicMock


def test_clip_data_includes_motion_curve_dominant_colors_tags_has_embedding():
    """video_analysis_cache mit motion_curve/dominant_colors/tags/has_embedding muss in clip_data landen."""
    from backend.routers.pacing_router import _run_pacing_generation
    from backend.schemas.pacing_schemas import PacingConfigSchema, TriggerSettingsSchema

    audio_clips = {
        1: {"id": 1, "name": "a1", "path": "/tmp/a.wav", "duration_seconds": 5.0, "bpm": 120.0},
    }
    video_clips = {
        10: {"id": 10, "name": "v1", "path": "/tmp/v1.mp4", "duration_seconds": 10.0},
    }
    video_analysis = {
        10: {
            "avg_motion": 5.0,
            "motion": {
                "motion_curve": [1.0, 2.0, 3.0],
                "peak_frames": [{"frame": 5, "score": 0.8}],
                "avg_motion": 5.0,
            },
            "dominant_colors": ["#FF0000", "#00FF00"],
            "tags": ["nature", "outdoor"],
            "scenes": [{"start_time": 0.0, "end_time": 5.0}],
            "has_embedding": True,
        },
    }

    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        expected_bpm=120.0,
        use_motion_matching=True,
        trigger_settings=TriggerSettingsSchema(),
    )

    captured_clips = []
    with patch("pb_studio.services.pacing_service.PacingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        # PacingService.generate_cut_list returns iterable cut-objects
        mock_svc.generate_cut_list.return_value = []

        # Run
        _run_pacing_generation(
            config, audio_clips, video_clips, cached_analysis=None,
            video_analysis_cache=video_analysis,
        )

        # Inspect captured clips arg
        call_args = mock_svc.generate_cut_list.call_args
        captured_clips = call_args.kwargs.get("clips") or call_args.args[1]

    assert len(captured_clips) == 1
    clip = captured_clips[0]

    assert clip["id"] == 10
    assert clip["motion_curve"] == [1.0, 2.0, 3.0]
    assert clip["dominant_colors"] == ["#FF0000", "#00FF00"]
    assert clip["tags"] == ["nature", "outdoor"]
    assert clip["has_embedding"] is True
    # Sanity-check existing forwarding still works
    assert clip["motion_score"] == 5.0
    assert clip["scene_changes"] == [{"start_time": 0.0, "end_time": 5.0}]


def test_clip_data_no_video_analysis_no_extras():
    """Ohne video_analysis_cache bleiben extras absent (kein crash)."""
    from backend.routers.pacing_router import _run_pacing_generation
    from backend.schemas.pacing_schemas import PacingConfigSchema, TriggerSettingsSchema

    audio_clips = {1: {"id": 1, "name": "a1", "path": "/tmp/a.wav", "duration_seconds": 5.0}}
    video_clips = {10: {"id": 10, "name": "v1", "path": "/tmp/v1.mp4", "duration_seconds": 10.0}}

    config = PacingConfigSchema(
        audio_clip_id=1, video_clip_ids=[10], expected_bpm=120.0,
        trigger_settings=TriggerSettingsSchema(),
    )

    with patch("pb_studio.services.pacing_service.PacingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.generate_cut_list.return_value = []

        _run_pacing_generation(config, audio_clips, video_clips, cached_analysis=None, video_analysis_cache=None)

        captured = mock_svc.generate_cut_list.call_args.kwargs.get("clips") or mock_svc.generate_cut_list.call_args.args[1]

    assert len(captured) == 1
    clip = captured[0]
    # Ohne cache: KEINE motion_curve/colors/tags/has_embedding keys
    assert "motion_curve" not in clip
    assert "dominant_colors" not in clip
    assert "tags" not in clip
    assert "has_embedding" not in clip
    # Aber Basis-Felder present
    assert clip["id"] == 10
    assert clip["file_path"] == "/tmp/v1.mp4"
