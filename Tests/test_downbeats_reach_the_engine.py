"""Gemessene Downbeats muessen bis in die Pacing-Engine durchkommen.

Audit 2026-08-29/30 (C-01): `beat_trigger_mode="downbeat_only"` lieferte
garantiert eine leere Cut-Liste. Die Kette war an vier Stellen zugleich
durchtrennt:

1. `BeatDetector.get_downbeats()` und `.scan()` hatten null Aufrufer.
2. `audio_router` initialisierte `downbeats = []` und wies nie etwas zu.
3. Alle Schreibstellen von `downbeat_provenance` setzten `"unavailable"`,
   waehrend `pacing_service.py:389` auf `"measured"` prueft.
4. Jeder Beat bekam hart `beat_type="beat"`, waehrend `pacing_service.py:369`
   nach `downbeat|bar` sucht.

Zwei Eigenschaften sichern diese Tests ab, die beim naheliegenden Fix leicht
verloren gehen:

- **Ein Durchlauf.** `get_downbeats(audio_path)` haette einen ZWEITEN
  vollstaendigen BeatNet-Lauf ueber dieselbe Datei ausgeloest.
- **Der Langdatei-Schutz bleibt.** `detect_beats` weicht ueber 600 s bewusst
  auf librosa aus, weil BeatNet dort haengt. Genau der Fall, fuer den dieses
  Produkt gebaut ist (DJ-Mixes).
"""

from pathlib import Path

import pytest

from pb_studio.audio import beat_detector as bd_mod
from pb_studio.audio.beat_detector import BeatDetector


class _FakeEstimator:
    """Liefert das BeatNet-Ausgabeformat: Spalte 0 Zeit, Spalte 1 Beat-Position."""

    def __init__(self) -> None:
        self.calls = 0

    def process(self, audio_path):
        self.calls += 1
        import numpy as np
        # Vier Beats, davon zwei Downbeats (Spalte 1 == 1.0).
        return np.array(
            [
                [0.00, 1.0],
                [0.50, 2.0],
                [1.00, 3.0],
                [1.50, 1.0],
            ],
            dtype=float,
        )


@pytest.fixture
def detector_with_fake_beatnet(monkeypatch, tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\0")
    monkeypatch.setattr(bd_mod, "BEATNET_AVAILABLE", True)
    monkeypatch.setattr(bd_mod.librosa, "get_duration", lambda **kw: 30.0)
    detector = BeatDetector(mode="offline", inference_model="DBN")
    fake = _FakeEstimator()
    monkeypatch.setattr(detector, "_init_estimator", lambda: True)
    detector._estimator = fake
    return detector, str(audio), fake


def test_downbeats_come_from_the_same_pass_as_the_beats(detector_with_fake_beatnet):
    """Der springende Punkt: EIN BeatNet-Lauf, nicht zwei."""
    detector, audio, fake = detector_with_fake_beatnet

    beats, downbeats = detector.detect_beats_with_downbeats(audio)

    assert beats == [0.0, 0.5, 1.0, 1.5]
    assert downbeats == [0.0, 1.5]
    assert fake.calls == 1, (
        "Downbeats muessen aus demselben Durchlauf stammen wie die Beats - "
        f"BeatNet lief {fake.calls}x"
    )


def test_downbeats_are_a_subset_of_the_beats(detector_with_fake_beatnet):
    """Downbeats tragen dieselben Zeitstempel wie Beats.

    Deshalb duerfen sie der Beat-Liste NICHT angehaengt werden - das
    verdoppelte jeden Taktanfang. Der Konsument markiert stattdessen.
    """
    detector, audio, _ = detector_with_fake_beatnet
    beats, downbeats = detector.detect_beats_with_downbeats(audio)
    assert set(downbeats) <= set(beats)


def test_detect_beats_keeps_its_contract(detector_with_fake_beatnet):
    """Die bestehenden Aufrufer bekommen unveraendert eine flache Liste."""
    detector, audio, _ = detector_with_fake_beatnet
    assert detector.detect_beats(audio) == [0.0, 0.5, 1.0, 1.5]


def test_long_file_guard_survives(monkeypatch, tmp_path):
    """Ueber 600 s bleibt es bei librosa - BeatNet haengt dort.

    Ohne diese Zusicherung waere der Downbeat-Fix genau fuer lange DJ-Mixes
    ein Haenger, also fuer den Hauptanwendungsfall.
    """
    audio = tmp_path / "long.wav"
    audio.write_bytes(b"\0")
    monkeypatch.setattr(bd_mod, "BEATNET_AVAILABLE", True)
    monkeypatch.setattr(bd_mod.librosa, "get_duration", lambda **kw: 4000.0)

    detector = BeatDetector(mode="offline", inference_model="DBN")
    fake = _FakeEstimator()
    monkeypatch.setattr(detector, "_init_estimator", lambda: True)
    detector._estimator = fake
    monkeypatch.setattr(
        detector, "_detect_beats_librosa", lambda *a, **kw: [1.0, 2.0]
    )

    beats, downbeats = detector.detect_beats_with_downbeats(str(audio))

    assert beats == [1.0, 2.0]
    assert downbeats == [], "librosa kennt keine Downbeats - nichts erfinden"
    assert fake.calls == 0, "BeatNet darf bei langen Dateien gar nicht erst laufen"


def test_progress_is_still_reported(detector_with_fake_beatnet):
    """Der Fortschrittskanal darf beim Umbau nicht verloren gehen."""
    detector, audio, _ = detector_with_fake_beatnet
    seen: list[float] = []
    detector.detect_beats_with_downbeats(audio, on_progress=seen.append)
    assert seen, "on_progress wurde nie gerufen"
    assert seen[0] == 0.0 and seen[-1] == 100.0
    assert all(0.0 <= p <= 100.0 for p in seen)


# ---------------------------------------------------------------------------
# Die Kette vom Router-Ergebnis bis in die Engine
# ---------------------------------------------------------------------------


def _router_shaped_analysis(*, provenance_status: str) -> dict:
    """Ein Analyse-Cache in genau der Form, die audio_router persistiert."""
    return {
        "bpm": 120.0,
        "duration": 2.0,
        "beats": [
            {"time": 0.0, "strength": 1.0, "beat_type": "downbeat"},
            {"time": 0.5, "strength": 0.8, "beat_type": "beat"},
            {"time": 1.0, "strength": 0.8, "beat_type": "beat"},
            {"time": 1.5, "strength": 1.0, "beat_type": "downbeat"},
        ],
        "downbeats": [0.0, 1.5],
        "downbeat_provenance": {
            "status": provenance_status,
            "method": "beatnet_native",
            "synthetic": False,
            "measured_count": 2,
        },
    }


def _inject(cached: dict):
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.services.pacing_service import PacingService

    engine = AdvancedPacingEngine()
    service = PacingService.__new__(PacingService)
    service._inject_cached_into_engine(engine, "irrelevant.wav", cached)
    return engine


def test_measured_downbeats_reach_the_engine():
    """Der eigentliche Zweck der ganzen Kette."""
    engine = _inject(_router_shaped_analysis(provenance_status="measured"))
    assert getattr(engine, "_pre_cached_downbeats", []) == [0.0, 1.5]


def test_the_status_word_is_load_bearing():
    """Gegenprobe: mit jedem anderen Statuswort bleiben die Downbeats liegen.

    Genau hier war die Kette durchtrennt - der Router schrieb "available"
    bzw. "unavailable", der Konsument prueft auf "measured".
    """
    engine = _inject(_router_shaped_analysis(provenance_status="available"))
    assert getattr(engine, "_pre_cached_downbeats", []) == []


def test_downbeat_only_mode_produces_cuts():
    """Das gemeldete Symptom: der Modus lieferte garantiert eine leere Liste."""
    engine = _inject(_router_shaped_analysis(provenance_status="measured"))
    beats = list(getattr(engine, "_pre_cached_beats", []))
    downbeats = list(getattr(engine, "_pre_cached_downbeats", []))

    assert beats, "Vorbedingung: Beats muessen im Cache liegen"
    kept = [t for t in beats if t in set(downbeats)]
    assert kept == [0.0, 1.5], (
        "downbeat_only filtert auf die Taktanfaenge - ohne befuellte "
        "Downbeat-Menge bleibt nichts uebrig"
    )


def test_downbeats_are_not_appended_as_extra_beats():
    """Beats und Strengths muessen gleich lang bleiben.

    advanced_pacing_engine verwirft die Strengths bei Laengenungleichheit
    (Logzeile "length mismatch") und faellt still auf konstante Gewichte
    zurueck. Ein Anhaengen der Downbeats haette genau das ausgeloest.
    """
    cached = _router_shaped_analysis(provenance_status="measured")
    engine = _inject(cached)
    beats = getattr(engine, "_pre_cached_beats", [])
    strengths = getattr(engine, "_pre_cached_beat_strengths", [])
    assert len(beats) == len(cached["beats"]) == 4
    assert len(strengths) == len(beats)
    assert len(beats) == len(set(beats)), "kein Zeitstempel doppelt"
