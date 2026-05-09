"""Test: cached tempo_curve wird ins Pacing injiziert (L-M1)."""
import pytest
import numpy as np


def test_pacing_uses_cached_tempo_curve(tmp_path):
    """Wenn cached_analysis.tempo_curve gesetzt, _last_used_cached_tempo=True."""
    from pb_studio.services.pacing_service import PacingService
    import soundfile as sf
    audio = tmp_path / "test.wav"
    sf.write(str(audio), np.zeros(22050, dtype=np.float32), 22050)
    fake_video = tmp_path / "v.mp4"; fake_video.touch()

    cached = {
        "beats": [{"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 1.0,
        "tempo_curve": [120.0, 122.0, 125.0, 128.0],
    }

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio),
            clips=[{"id": 1, "name": "v", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config={"expected_bpm": 120, "use_motion_matching": False,
                           "trigger_settings": {"min_clip_length": 1.0, "max_clip_length": 8.0}},
            total_duration=1.0,
            cached_analysis=cached,
        )
    except Exception:
        pass

    assert hasattr(svc, "_last_used_cached_tempo")
    assert svc._last_used_cached_tempo is True


def test_tempo_at_time_helper():
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    engine._pre_cached_tempo_curve = np.array([120.0, 130.0], dtype=np.float32)
    engine._pre_cached_duration = 1.0

    assert engine._tempo_at_time(0.0) == 120.0
    assert engine._tempo_at_time(1.0) == 130.0


def test_tempo_at_time_no_curve_returns_default():
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    engine = AdvancedPacingEngine()
    assert engine._tempo_at_time(0.5) == 120.0
