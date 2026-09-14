"""Waechter gegen den Kollaps dichter Trigger-Ketten in der Streaming-Dedup.

Befund 2026-08-30: `_BeatAccumulator.get_deduplicated` verglich jeden Wert gegen
das LETZTE Element der laufenden Gruppe. Damit kollabierte jede Kette, deren
Nachbarabstaende einzeln unter der Schwelle liegen, zu genau EINEM Wert -
unabhaengig von ihrer Laenge. Dieselbe Klasse fuehrt neben den Beats auch die
Trigger-Listen (Onset/Kick/Snare/HiHat), fuer die 150 ms viel zu grob sind:

    120 BPM 16tel = 125 ms     174 BPM 16tel = 86 ms

Eine durchgehende 16tel-HiHat war im Streaming-Pfad also auf einen einzigen
Zeitpunkt reduziert. Zwei Aenderungen beheben das: Vergleich gegen das ERSTE
Gruppenelement und eine eigene, kleinere Schwelle fuer Trigger.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from pb_studio.audio.streaming_analyzer import (  # noqa: E402
    _BeatAccumulator,
    StreamingAudioAnalyzer,
)

BEAT_THRESHOLD = StreamingAudioAnalyzer.BEAT_DEDUP_THRESHOLD_SEC
TRIGGER_THRESHOLD = StreamingAudioAnalyzer.TRIGGER_DEDUP_THRESHOLD_SEC


def _dedup_count(interval: float, count: int, threshold: float) -> int:
    accumulator = _BeatAccumulator(threshold)
    accumulator.add_chunk_beats([index * interval for index in range(count)])
    return len(accumulator.get_deduplicated())


@pytest.mark.parametrize("bpm", [120.0, 128.0, 140.0, 174.0])
@pytest.mark.parametrize("subdivision", [2, 4, 8])
def test_trigger_chain_survives_dedup(bpm: float, subdivision: int) -> None:
    """Achtel, Sechzehntel und Zweiunddreissigstel bleiben vollstaendig."""
    interval = 60.0 / bpm / subdivision
    assert _dedup_count(interval, 64, TRIGGER_THRESHOLD) == 64, (
        f"{bpm} BPM, 1/{subdivision * 4}-Raster ({interval * 1000:.0f} ms) "
        f"wurde von der Trigger-Dedup zusammengefasst"
    )


def test_seam_jitter_still_collapses() -> None:
    """Der eigentliche Zweck bleibt erhalten: Naht-Jitter faellt zusammen.

    Zwei Detektorlaeufe an einer Fenstergrenze liefern denselben Anschlag
    typischerweise um eine Hop-Laenge versetzt (512/44100 = 11.6 ms).
    """
    accumulator = _BeatAccumulator(TRIGGER_THRESHOLD)
    accumulator.add_chunk_beats([10.000, 10.012])
    assert len(accumulator.get_deduplicated()) == 1


def test_trigger_threshold_is_below_fastest_musical_subdivision() -> None:
    """Die Schwelle muss unter dem engsten realistischen Raster liegen.

    Schnellster hier beruecksichtigter Fall: 174 BPM in Zweiunddreissigsteln.
    """
    fastest_interval = 60.0 / 174.0 / 8
    assert TRIGGER_THRESHOLD < fastest_interval, (
        f"Trigger-Schwelle {TRIGGER_THRESHOLD} s liegt nicht unter dem "
        f"engsten Raster {fastest_interval:.4f} s"
    )


def test_beat_threshold_stays_coarse() -> None:
    """Beats behalten die grobe Schwelle - dort ist sie richtig.

    Selbst 300 BPM halten 200 ms Abstand, deutlich ueber 150 ms.
    """
    assert BEAT_THRESHOLD > TRIGGER_THRESHOLD
    assert _dedup_count(60.0 / 300.0, 32, BEAT_THRESHOLD) == 32


def test_chained_grouping_no_longer_collapses_whole_chain() -> None:
    """Kern des Fixes, unabhaengig von der gewaehlten Schwelle.

    Eine Kette mit Nachbarabstaenden knapp unter der Schwelle darf nicht mehr
    auf einen einzigen Wert zusammenfallen. Vor dem Fix ergab dieser Aufbau
    genau 1 Wert.
    """
    interval = TRIGGER_THRESHOLD * 0.9
    result = _dedup_count(interval, 50, TRIGGER_THRESHOLD)
    assert result > 1, "gesamte Kette zu einem Wert kollabiert"
    assert result >= 25, f"Kette auf {result} von 50 Werten zusammengefasst"
