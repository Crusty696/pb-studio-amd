"""Test: use_stem_pacing routet zu generate_cut_list_with_stems (L-K5)."""
import pytest
from unittest.mock import patch, MagicMock


def test_pacing_router_calls_stem_branch_when_flag_set(tmp_path, monkeypatch):
    from backend.routers.pacing_router import _run_pacing_generation
    from backend.schemas.pacing_schemas import PacingConfigSchema, TriggerSettingsSchema
    from pb_studio.config_manager import ConfigManager

    audio_path = tmp_path / "a.wav"
    vocals_path = tmp_path / "vocals.wav"
    drums_path = tmp_path / "drums.wav"
    video_path = tmp_path / "v.mp4"
    for path in (audio_path, vocals_path, drums_path, video_path):
        path.write_bytes(b"media")
    monkeypatch.setattr(ConfigManager, "resolve_path", lambda self, _path: tmp_path)
    audio_clips = {1: {"id": 1, "name": "a", "path": str(audio_path), "duration_seconds": 5.0,
                       "stems_paths": {"vocals": str(vocals_path), "drums": str(drums_path)}}}
    video_clips = {10: {"id": 10, "name": "v", "path": str(video_path), "duration_seconds": 10.0}}

    config = PacingConfigSchema(
        audio_clip_id=1, video_clip_ids=[10], expected_bpm=120.0,
        use_stem_pacing=True,
        trigger_settings=TriggerSettingsSchema(),
    )

    with patch("pb_studio.services.pacing_service.PacingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.generate_cut_list.return_value = []
        mock_svc.generate_cut_list_with_stems.return_value = []
        mock_svc_cls.return_value = mock_svc

        _run_pacing_generation(config, audio_clips, video_clips,
                               cached_analysis=None, video_analysis_cache=None)

    assert mock_svc.generate_cut_list_with_stems.called, "Stem-Branch nicht erreicht"
    assert not mock_svc.generate_cut_list.called, "Standard-Pfad statt Stem-Pfad gerufen"


def test_pacing_router_default_uses_standard_branch():
    from backend.routers.pacing_router import _run_pacing_generation
    from backend.schemas.pacing_schemas import PacingConfigSchema, TriggerSettingsSchema

    audio_clips = {1: {"id": 1, "name": "a", "path": "/tmp/a.wav", "duration_seconds": 5.0}}
    video_clips = {10: {"id": 10, "name": "v", "path": "/tmp/v.mp4", "duration_seconds": 10.0}}

    config = PacingConfigSchema(
        audio_clip_id=1, video_clip_ids=[10], expected_bpm=120.0,
        use_stem_pacing=False,
        trigger_settings=TriggerSettingsSchema(),
    )

    with patch("pb_studio.services.pacing_service.PacingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.generate_cut_list.return_value = []
        mock_svc_cls.return_value = mock_svc

        _run_pacing_generation(config, audio_clips, video_clips,
                               cached_analysis=None, video_analysis_cache=None)

    assert mock_svc.generate_cut_list.called
    assert not mock_svc.generate_cut_list_with_stems.called


def test_pacing_router_stem_flag_no_stems_falls_back():
    """use_stem_pacing=True + keine stems_paths -> fallback zu standard branch."""
    from backend.routers.pacing_router import _run_pacing_generation
    from backend.schemas.pacing_schemas import PacingConfigSchema, TriggerSettingsSchema

    audio_clips = {1: {"id": 1, "name": "a", "path": "/tmp/a.wav", "duration_seconds": 5.0}}
    video_clips = {10: {"id": 10, "name": "v", "path": "/tmp/v.mp4", "duration_seconds": 10.0}}

    config = PacingConfigSchema(
        audio_clip_id=1, video_clip_ids=[10], expected_bpm=120.0,
        use_stem_pacing=True,
        trigger_settings=TriggerSettingsSchema(),
    )

    with patch("pb_studio.services.pacing_service.PacingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.generate_cut_list.return_value = []
        mock_svc_cls.return_value = mock_svc

        _run_pacing_generation(config, audio_clips, video_clips,
                               cached_analysis=None, video_analysis_cache=None)

    # Fallback: standard wird gerufen
    assert mock_svc.generate_cut_list.called
    assert not mock_svc.generate_cut_list_with_stems.called
