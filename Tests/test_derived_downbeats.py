"""Abgeleitete Taktanfaenge duerfen nie als gemessen auftreten.

Hintergrund: madmom 0.16.1 kann auf NumPy 1.26.4 keine Downbeats liefern
(`np.asarray` auf eine ungleichfoermige Ergebnisliste, seit NumPy 1.24 ein
Fehler). BeatNet wirft deshalb bei jeder Datei, und die Beats kommen in
Wahrheit von librosa - das kennt keine Taktanfaenge.

Auf Wunsch des Projektinhabers werden Taktanfaenge daher aus den
Anschlagstaerken abgeleitet. FR-317 (T317, QC PASS) verlangt: "Echte Downbeats
von synthetischen Annahmen trennen; keine pauschale 'jeder vierte
Beat'-Behauptung." Beides bleibt gewahrt:

- Die Ableitung meldet `status="derived"` und `synthetic=True`, nie "measured".
- Sie verweigert die Auskunft, wenn die Anschlagstaerken keine Taktstruktur
  hergeben. Genau das ist der Unterschied zu "jeder vierte Beat".
- `AdvancedPacingEngine._identify_downbeats` bleibt unangetastet; der dortige
  T317-Waechter gilt unveraendert.
"""

import pytest

from pb_studio.audio.beat_detector import derive_downbeats_from_strengths


def _accented(n_bars: int, beats_per_bar: int = 4, phase: int = 0):
    """Beats mit klarem Akzent auf einer festen Position im Takt."""
    times, strengths = [], []
    for i in range(n_bars * beats_per_bar):
        times.append(i * 0.5)
        strengths.append(0.95 if i % beats_per_bar == phase else 0.35)
    return times, strengths


def test_derives_the_accented_phase():
    times, strengths = _accented(8, phase=0)
    out = derive_downbeats_from_strengths(times, strengths)
    assert out == [t for i, t in enumerate(times) if i % 4 == 0]


def test_finds_a_shifted_phase():
    """Der Akzent liegt nicht zwangslaeufig auf dem ersten erkannten Beat."""
    times, strengths = _accented(8, phase=2)
    out = derive_downbeats_from_strengths(times, strengths)
    assert out == [t for i, t in enumerate(times) if i % 4 == 2]


def test_refuses_when_there_is_no_discernible_bar():
    """DER Kern von FR-317: ohne Struktur wird nicht geraten.

    Bei durchweg gleichen Anschlagstaerken gibt es keinen Taktanfang. Eine
    Ableitung waere hier exakt die von FR-317 verbotene pauschale
    'jeder vierte Beat'-Behauptung.
    """
    times = [i * 0.5 for i in range(32)]
    flat = [0.6] * 32
    assert derive_downbeats_from_strengths(times, flat) == []


def test_refuses_on_noise_without_a_dominant_phase():
    times = [i * 0.5 for i in range(32)]
    wobbly = [0.60, 0.62, 0.58, 0.61] * 8
    assert derive_downbeats_from_strengths(times, wobbly) == []


def test_refuses_when_there_is_too_little_material():
    times, strengths = _accented(1)
    assert derive_downbeats_from_strengths(times, strengths) == []


def test_refuses_on_mismatched_input():
    assert derive_downbeats_from_strengths([0.0, 0.5], [1.0]) == []
    assert derive_downbeats_from_strengths([], []) == []


def test_result_is_a_subset_of_the_beats():
    times, strengths = _accented(8, phase=1)
    out = derive_downbeats_from_strengths(times, strengths)
    assert set(out) <= set(times)
    assert len(out) == len(set(out))


def test_pacing_service_accepts_derived_but_still_rejects_unavailable():
    """Der Konsument muss den neuen Status kennen - sonst bleibt alles liegen."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.services.pacing_service import PacingService

    def inject(status: str):
        engine = AdvancedPacingEngine()
        service = PacingService.__new__(PacingService)
        service._inject_cached_into_engine(engine, "x.wav", {
            "bpm": 120.0,
            "duration": 2.0,
            "beats": [
                {"time": 0.0, "strength": 1.0, "beat_type": "downbeat"},
                {"time": 0.5, "strength": 0.4, "beat_type": "beat"},
                {"time": 1.0, "strength": 0.4, "beat_type": "beat"},
                {"time": 1.5, "strength": 0.4, "beat_type": "beat"},
            ],
            "downbeats": [0.0],
            "downbeat_provenance": {
                "status": status,
                "method": "onset_strength_phase",
                "synthetic": status == "derived",
                "measured_count": 1,
            },
        })
        return getattr(engine, "_pre_cached_downbeats", [])

    assert inject("derived") == [0.0]
    assert inject("measured") == [0.0]
    assert inject("unavailable") == []


def test_engine_t317_guard_is_untouched():
    """AdvancedPacingEngine._identify_downbeats darf weiterhin nichts erfinden."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine.__new__(AdvancedPacingEngine)
    engine.audio_analysis = {}
    assert engine._identify_downbeats([float(i) for i in range(16)]) == []
    assert engine._last_downbeat_provenance["synthetic"] is False
