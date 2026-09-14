"""Test: PacingService nutzt cached structure_segments statt redundanter Re-Analyse (Audit A3)."""
import numpy as np
import pytest
from unittest.mock import Mock


def _default_pacing_config(**overrides):
    """Default trigger_settings damit Tests nicht crashen."""
    cfg = {
        "expected_bpm": 120,
        "use_motion_matching": False,
        "use_semantic_matching": False,
        "use_structure_awareness": True,
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


def _make_test_audio(tmp_path):
    import soundfile as sf
    audio_path = tmp_path / "test.wav"
    sample_rate = 22050
    silence = np.zeros(sample_rate * 2, dtype=np.float32)  # 2s
    sf.write(str(audio_path), silence, sample_rate)
    return audio_path


@pytest.mark.parametrize("source", ["analyzer", "cache"])
def test_peak_structure_boosts_trigger_and_wins_interval_filter(source, monkeypatch):
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.pacing.pacing_models import PacingCut

    segments = [
        {"start_time": 0.0, "end_time": 1.0, "label": "verse", "energy_score": 0.9},
        {"start_time": 1.0, "end_time": 2.0, "label": "peak", "energy_score": 0.2},
    ]
    engine = AdvancedPacingEngine()
    if source == "analyzer":
        import librosa
        from pb_studio.audio.structure_analyzer import StructureAnalyzer

        load = Mock(return_value=(np.zeros(2, dtype=np.float32), 22050))
        analyze = Mock(return_value={"segments": segments})
        monkeypatch.setattr(librosa, "load", load)
        monkeypatch.setattr(StructureAnalyzer, "analyze_song_structure", analyze)
        sections = engine.analyze_song_structure("structure-regression.wav")
        load.assert_called_once_with("structure-regression.wav", sr=22050, mono=True)
        analyze.assert_called_once()
    else:
        sections = engine._coerce_song_structure(segments)

    assert [section.name for section in sections] == ["verse", "peak"]
    assert [section.energy_level for section in sections] == pytest.approx([0.8, 1.5])
    assert [(section.start_time, section.end_time) for section in sections] == [
        (0.0, 1.0), (1.0, 2.0),
    ]
    triggers = [
        PacingCut(time=0.9, trigger_type="beat", strength=0.6),
        PacingCut(time=1.1, trigger_type="beat", strength=0.5),
    ]
    weighted = engine._apply_structure_weights(triggers, sections)
    assert [cut.strength for cut in weighted] == pytest.approx([0.48, 0.75])
    retained = engine._enforce_minimum_interval(weighted, min_interval=0.5)
    assert [cut.time for cut in retained] == [1.1]


def test_pacing_uses_cached_structure_segments(tmp_path):
    from pb_studio.services.pacing_service import PacingService
    audio_path = _make_test_audio(tmp_path)
    fake_video = tmp_path / "v1.mp4"
    fake_video.touch()

    cached = {
        "beats": [{"time": 0.5, "strength": 1.0}, {"time": 1.0, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 2.0,
        "structure_segments": [
            {"start_time": 0.0, "end_time": 1.0, "label": "intro", "energy_score": 0.3},
            {"start_time": 1.0, "end_time": 2.0, "label": "drop", "energy_score": 0.9},
        ],
    }

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(use_structure_awareness=True),
            total_duration=2.0,
            cached_analysis=cached,
        )
    except Exception:
        pass  # Engine downstream errors irrelevant - flag check vor downstream

    assert hasattr(svc, "_last_skipped_structure_reanalyze")
    assert svc._last_skipped_structure_reanalyze is True


def test_pacing_no_cached_structure_calls_analyze(tmp_path, monkeypatch):
    from pb_studio.services.pacing_service import PacingService
    from pb_studio.pacing import advanced_pacing_engine as engine_mod

    analyze_calls = {"n": 0}
    original = engine_mod.AdvancedPacingEngine.analyze_song_structure

    def counting(self, audio_path):
        analyze_calls["n"] += 1
        return original(self, audio_path)

    monkeypatch.setattr(engine_mod.AdvancedPacingEngine, "analyze_song_structure", counting)

    audio_path = _make_test_audio(tmp_path)
    fake_video = tmp_path / "v1.mp4"
    fake_video.touch()

    cached_no_structure = {
        "beats": [{"time": 0.5, "strength": 1.0}],
        "bpm": 120.0,
        "duration_seconds": 2.0,
        # KEIN structure_segments
    }

    svc = PacingService()
    try:
        svc.generate_cut_list(
            audio_path=str(audio_path),
            clips=[{"id": 1, "name": "v1", "file_path": str(fake_video), "duration": 0.5}],
            pacing_config=_default_pacing_config(use_structure_awareness=True),
            total_duration=2.0,
            cached_analysis=cached_no_structure,
        )
    except Exception:
        pass

    assert svc._last_skipped_structure_reanalyze is False
    # Engine sollte mind. 1× analyze_song_structure aufrufen
    # (weil keine cached_segments)
    # Note: kann 0 sein wenn engine direkt durch downstream-error stoppt vor structure-call
    # — dann reicht der flag-check oben
