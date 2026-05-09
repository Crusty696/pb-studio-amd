"""Test: PacingService nutzt cached energy_curve statt RMS-Neuberechnung (Audit A2)."""
import pytest
from pathlib import Path
import numpy as np


def _default_pacing_config():
    """Minimal-Config mit trigger_settings (pacing_service.py:180 erwartet diesen Key)."""
    return {
        "expected_bpm": 120,
        "use_motion_matching": False,
        "use_semantic_matching": False,
        "use_structure_awareness": False,
        "trigger_settings": {
            "beat_weight": 1.0,
            "onset_weight": 0.5,
            "kick_weight": 1.2,
            "snare_weight": 1.0,
            "hihat_weight": 0.3,
            "energy_weight": 0.8,
            "energy_threshold": 0.6,
        },
    }


def _make_silence_wav(tmp_path, name="test.wav", seconds=1.0, sample_rate=22050):
    import soundfile as sf
    audio_path = tmp_path / name
    silence = np.zeros(int(seconds * sample_rate), dtype=np.float32)
    sf.write(str(audio_path), silence, sample_rate)
    return audio_path


def test_pacing_uses_cached_energy_curve_when_provided(tmp_path):
    """Wenn cached_analysis['energy_curve'] geliefert wird, nutzt Engine die cached Werte."""
    from pb_studio.services.pacing_service import PacingService

    audio_path = _make_silence_wav(tmp_path)
    fake_video = tmp_path / "v1.mp4"
    fake_video.touch()

    cached = {
        "beats": [{"time": 0.1, "strength": 1.0}, {"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "energy_curve": [0.1, 0.5, 0.9, 0.5, 0.1] * 100,
        "duration_seconds": 1.0,
    }

    svc = PacingService()
    # generate_cut_list darf werfen (kein echtes Video), aber die Injection muss VOR
    # dem Werfen passieren — daher in try/except wrappen.
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(),
            total_duration=1.0,
            cached_analysis=cached,
        )
    except Exception:
        pass  # ffprobe schlaegt evtl. fehl - egal, Injection-Flag wurde vorher gesetzt.

    # Engine MUSS cached energy genutzt haben
    assert hasattr(svc, "_last_used_cached_energy"), (
        "PacingService.__init__ muss _last_used_cached_energy initialisieren"
    )
    assert svc._last_used_cached_energy is True, "cached energy_curve wurde NICHT genutzt"


def test_pacing_no_cached_energy_falls_back_to_rms(tmp_path):
    """Wenn kein energy_curve in cached_analysis, _last_used_cached_energy bleibt False."""
    from pb_studio.services.pacing_service import PacingService

    audio_path = _make_silence_wav(tmp_path)
    fake_video = tmp_path / "v1.mp4"
    fake_video.touch()

    cached_no_energy = {
        "beats": [{"time": 0.1, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 1.0,
    }

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(),
            total_duration=1.0,
            cached_analysis=cached_no_energy,
        )
    except Exception:
        pass

    assert svc._last_used_cached_energy is False


def test_pacing_simple_path_skips_librosa_rms_when_cached(tmp_path, monkeypatch):
    """Hot-path: librosa.feature.rms NICHT aufrufen wenn cached energy_curve da.

    Audit A2 Follow-up: _extract_other_triggers + _extract_bass_triggers_from_stem
    haben fruher librosa.feature.rms() neu berechnet, auch wenn cached energy_curve
    via _pre_cached_energy injiziert war. Dieser Test verifiziert die Bypass-Logik
    indem librosa.feature.rms gemonkeypatcht und auf 0 Aufrufe verifiziert wird.
    """
    import librosa
    from pb_studio.services.pacing_service import PacingService

    rms_call_count = {"n": 0}
    original_rms = librosa.feature.rms

    def counting_rms(*args, **kwargs):
        rms_call_count["n"] += 1
        return original_rms(*args, **kwargs)

    monkeypatch.setattr(librosa.feature, "rms", counting_rms)

    audio_path = _make_silence_wav(tmp_path)
    fake_video = tmp_path / "v1.mp4"
    fake_video.touch()

    cached = {
        "beats": [{"time": 0.1, "strength": 1.0}, {"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "energy_curve": [0.1, 0.5, 0.9, 0.5, 0.1] * 100,
        "duration_seconds": 1.0,
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
        pass  # ffprobe schlaegt evtl. fehl - egal, Bypass-Logik wurde vorher exercised.

    # Pre-condition: cached energy_curve wurde tatsaechlich injiziert
    assert svc._last_used_cached_energy is True, (
        "Test-Setup falsch: cached energy_curve wurde nicht injiziert"
    )
    # Hauptverifikation: 0 librosa.feature.rms Aufrufe innerhalb pacing-flow
    assert rms_call_count["n"] == 0, (
        f"librosa.feature.rms wurde {rms_call_count['n']}x aufgerufen "
        "trotz cached energy_curve (Audit A2 Follow-up Regression)"
    )
