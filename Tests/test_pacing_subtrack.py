"""Test: cached subtrack_segments wird injiziert (Audit E3)."""
import pytest
import numpy as np


def _default_pacing_config(**overrides):
    cfg = {
        "expected_bpm": 120,
        "use_motion_matching": False,
        "use_semantic_matching": False,
        "use_structure_awareness": False,
        "min_cut_interval": 0.5,
        "trigger_settings": {
            "beat_weight": 1.0, "onset_weight": 0.5, "kick_weight": 1.2,
            "snare_weight": 1.0, "hihat_weight": 0.3, "energy_weight": 0.8,
            "energy_threshold": 0.6, "min_clip_length": 1.0, "max_clip_length": 8.0,
            "onset_sensitivity": 0.5,
        },
    }
    cfg.update(overrides)
    return cfg


def _make_audio(tmp_path):
    import soundfile as sf
    audio = tmp_path / "test.wav"
    sf.write(str(audio), np.zeros(22050, dtype=np.float32), 22050)
    return audio


def test_pacing_uses_cached_subtracks(tmp_path):
    from pb_studio.services.pacing_service import PacingService
    audio_path = _make_audio(tmp_path)
    fake_video = tmp_path / "v.mp4"; fake_video.touch()

    cached = {
        "beats": [{"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 1.0,
        "subtrack_segments": [
            {"start_time": 0.0, "end_time": 60.0, "confidence": 0.9},
            {"start_time": 60.0, "end_time": 180.0, "confidence": 0.85},
            {"start_time": 180.0, "end_time": 300.0, "confidence": 0.8},
        ],
    }

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(),
            total_duration=1.0,
            cached_analysis=cached,
        )
    except Exception:
        pass

    assert svc._last_used_cached_subtracks is True


def test_pacing_no_subtracks_default_false(tmp_path):
    from pb_studio.services.pacing_service import PacingService
    audio_path = _make_audio(tmp_path)
    fake_video = tmp_path / "v.mp4"; fake_video.touch()

    cached = {"beats": [], "bpm": 120.0, "duration_seconds": 1.0}

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(),
            total_duration=1.0,
            cached_analysis=cached,
        )
    except Exception:
        pass

    assert svc._last_used_cached_subtracks is False


def test_subtrack_boundary_anchors():
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    engine._pre_cached_subtracks = [
        {"start_time": 0.0, "end_time": 60.0, "confidence": 0.9},
        {"start_time": 60.0, "end_time": 180.0, "confidence": 0.85},
    ]
    anchors = engine._subtrack_boundary_anchors()
    assert anchors == [60.0, 180.0]


def test_subtrack_boundary_anchors_empty():
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    # KEIN _pre_cached_subtracks
    assert engine._subtrack_boundary_anchors() == []
