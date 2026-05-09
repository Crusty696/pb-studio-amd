"""Test: cached bass_curve wird ins Pacing injiziert (Audit E2)."""
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


def test_pacing_uses_cached_bass_curve(tmp_path):
    """Wenn cached_analysis['spectral_data']['bands']['low'] da ist,
    wird _last_used_cached_bass=True gesetzt."""
    from pb_studio.services.pacing_service import PacingService
    audio_path = _make_audio(tmp_path)
    fake_video = tmp_path / "v.mp4"
    fake_video.touch()

    cached = {
        "beats": [{"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 1.0,
        "spectral_data": {
            "clip_id": 1,
            "times": [0.0, 0.5, 1.0],
            "bands": {
                "low": [0.1, 0.9, 0.5],
                "mid": [0.3, 0.5, 0.4],
                "high": [0.2, 0.3, 0.4],
            },
            "centroids": [1500, 2000, 1800],
        },
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
        pass  # ffprobe darf wegen fake-video schmeissen — Injection ist vorher passiert.

    assert hasattr(svc, "_last_used_cached_bass")
    assert svc._last_used_cached_bass is True


def test_pacing_no_spectral_data_no_bass_inject(tmp_path):
    """Ohne spectral_data bleibt _last_used_cached_bass=False."""
    from pb_studio.services.pacing_service import PacingService
    audio_path = _make_audio(tmp_path)
    fake_video = tmp_path / "v.mp4"
    fake_video.touch()

    cached = {
        "beats": [{"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 1.0,
        # KEIN spectral_data
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

    assert svc._last_used_cached_bass is False


def test_bass_weight_at_time_returns_multiplier():
    """_bass_weight_at_time multiplier liegt in 1.0..2.0."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    engine._pre_cached_bass_curve = np.array([0.0, 0.5, 1.0], dtype=np.float32)
    engine._pre_cached_duration = 1.0

    assert engine._bass_weight_at_time(0.0) == 1.0  # 0.0 bass -> 1.0 base
    assert 1.4 <= engine._bass_weight_at_time(0.5) <= 1.6  # 0.5 bass -> ~1.5
    assert engine._bass_weight_at_time(1.0) == 2.0  # 1.0 bass -> 2.0 max


def test_bass_weight_at_time_no_curve_returns_1():
    """Ohne injizierte bass_curve gibt _bass_weight_at_time 1.0 zurueck."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    # KEIN _pre_cached_bass_curve
    assert engine._bass_weight_at_time(0.5) == 1.0
