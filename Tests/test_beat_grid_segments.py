"""Tests fuer das segmentierte Beatgrid (DJ-Mixe).

Die Tests bilden die Faelle nach, die an echtem Material tatsaechlich
aufgetreten sind - nicht nur die, die leicht zu konstruieren waren. Zwei
Defekte dieses Moduls sind erst bei der Messung an sechs Mixen aufgefallen,
beide waeren gegen synthetische Halb-/Doppeltempo-Faelle gruen geblieben:

1. Beim Falten auf ein Vielfaches wurde der Anker unveraendert uebernommen.
   Bei Faktor 2 faellt das nicht auf, weil jeder Beat des langsameren Rasters
   auch einer des schnelleren ist; erst bei Faktor 1,5 verrutscht das Raster.
2. Tempo- und Phasentoleranz waren unabhaengig gesetzt und widersprachen sich:
   die erlaubte Tempoabweichung erzeugte ueber ein Fenster dreimal so viel
   Drift, wie die Phasenpruefung zuliess.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from pb_studio.audio.beat_grid_segments import (  # noqa: E402
    CONSENSUS_FACTORS,
    MIN_SEGMENT_SECONDS,
    PHASE_MATCH_BEATS,
    GridSegment,
    _chain_windows,
    _consensus_tempo,
    _fold_to_consensus,
    _merge_short_segments,
    _phase_continues,
    _tempo_match_rel,
    segment_beat_grids,
    segments_as_payload,
)
from pb_studio.audio.beat_grid import BeatGrid  # noqa: E402

SR = 22050


def _click_track(bpm: float, seconds: float, offset: float = 0.0) -> np.ndarray:
    """Klickspur mit exakt bekanntem Tempo und Anker."""
    samples = int(seconds * SR)
    signal = np.zeros(samples, dtype=np.float32)
    interval = 60.0 / bpm
    time = offset
    while time < seconds:
        index = int(time * SR)
        if 0 <= index < samples - 64:
            # Kurzer Impuls mit Abklingen - eine reine Eins waere fuer
            # librosa.onset kaum detektierbar.
            envelope = np.exp(-np.arange(64) / 8.0).astype(np.float32)
            signal[index:index + 64] += envelope
        time += interval
    return signal


# ---------------------------------------------------------------------------
# Toleranzen: der Konstruktionsfehler, der die Verkettung ueberall brechen liess
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bpm", [100.0, 120.0, 138.0, 174.0])
@pytest.mark.parametrize("window", [15.0, 30.0, 60.0])
def test_tempo_and_phase_tolerance_are_consistent(bpm: float, window: float) -> None:
    """Die Tempotoleranz darf nicht mehr Drift erzeugen, als die Phase zulaesst.

    Genau dieser Widerspruch liess die Verkettung an der Parametrierung statt
    an Trackwechseln brechen.
    """
    rel = _tempo_match_rel(bpm, window)
    beats_per_window = window / (60.0 / bpm)
    drift = beats_per_window * rel
    assert drift <= PHASE_MATCH_BEATS + 1e-9, (
        f"{bpm} BPM / {window}s: Tempotoleranz {100*rel:.3f} % erzeugt "
        f"{drift:.3f} Beats Drift, erlaubt sind {PHASE_MATCH_BEATS}"
    )


def test_tempo_tolerance_shrinks_with_longer_windows() -> None:
    """Laengere Fenster lassen weniger Tempoabweichung zu - Drift laeuft auf."""
    assert _tempo_match_rel(138.0, 60.0) < _tempo_match_rel(138.0, 30.0)


# ---------------------------------------------------------------------------
# Phasenverkettung
# ---------------------------------------------------------------------------


def test_phase_continues_for_aligned_grids() -> None:
    interval = 60.0 / 120.0
    assert _phase_continues(120.0, 0.25, 0.25 + 10 * interval)


def test_phase_break_is_detected() -> None:
    """Halber Beat Versatz ist ein anderes Raster, kein durchgehendes."""
    interval = 60.0 / 120.0
    assert not _phase_continues(120.0, 0.25, 0.25 + 10 * interval + interval / 2)


def test_phase_wraps_around_the_interval() -> None:
    """Ein Versatz knapp UNTER einem vollen Intervall ist auch klein.

    Ohne die Modulo-Spiegelung wuerde 0,95 Intervall als grosser Versatz
    gelten, obwohl es 0,05 Intervall in die andere Richtung ist.
    """
    interval = 60.0 / 120.0
    assert _phase_continues(120.0, 0.0, 10 * interval - 0.02 * interval)


# ---------------------------------------------------------------------------
# Vielfach-Konsens
# ---------------------------------------------------------------------------


def test_consensus_ignores_octave_confusion() -> None:
    """69 und 138 duerfen nicht zu einem Wert gemittelt werden, den keiner traegt."""
    windows = [
        (0.0, 30.0, BeatGrid(138.0, 0.0, 4.0, "m", "plausible")),
        (30.0, 60.0, BeatGrid(69.0, 0.0, 4.0, "m", "plausible")),
        (60.0, 90.0, BeatGrid(138.0, 0.0, 4.0, "m", "plausible")),
        (90.0, 120.0, BeatGrid(138.0, 0.0, 4.0, "m", "plausible")),
    ]
    consensus = _consensus_tempo(windows)
    assert 137.0 <= consensus <= 139.0, (
        f"Konsens {consensus:.2f} liegt zwischen den Oktaven statt auf einer"
    )


def test_consensus_weights_by_contrast() -> None:
    """Ein Fenster ohne tragendes Raster darf den Konsens nicht verschieben."""
    windows = [
        (0.0, 30.0, BeatGrid(140.0, 0.0, 5.0, "m", "plausible")),
        (30.0, 60.0, BeatGrid(140.0, 0.0, 5.0, "m", "plausible")),
        (60.0, 90.0, BeatGrid(97.0, 0.0, 1.0, "m", "suspect")),
    ]
    assert 139.0 <= _consensus_tempo(windows) <= 141.0


@pytest.mark.parametrize("factor", [2.0, 0.5, 1.5, 2.0 / 3.0])
def test_fold_to_consensus_recognises_simple_ratios(factor: float) -> None:
    folded, applied = _fold_to_consensus(138.0 * factor, 138.0)
    assert applied == pytest.approx(factor, rel=1e-6)
    assert folded == pytest.approx(138.0, rel=1e-6)


def test_fold_leaves_genuine_deviation_alone() -> None:
    """Eine echte Tempoabweichung darf nicht wegdefiniert werden.

    117 BPM steht in keinem der geprueften Verhaeltnisse zu 138 - der Wert
    muss unveraendert bleiben, damit er als eigener Abschnitt sichtbar wird.
    """
    folded, applied = _fold_to_consensus(117.0, 138.0)
    assert applied == 1.0
    assert folded == 117.0


def test_all_consensus_factors_are_musically_simple() -> None:
    """Nur Verhaeltnisse aus kleinen ganzen Zahlen - keine krummen Faktoren."""
    for factor in CONSENSUS_FACTORS:
        assert 1.0 / 3.0 - 1e-9 <= factor <= 3.0 + 1e-9


# ---------------------------------------------------------------------------
# Verkettung und Zusammenfassen
# ---------------------------------------------------------------------------


def test_chain_merges_identical_windows() -> None:
    interval = 60.0 / 120.0
    windows = [
        (float(i * 30), float((i + 1) * 30),
         BeatGrid(120.0, round(i * 30 / interval) * interval, 4.0, "m", "plausible"))
        for i in range(4)
    ]
    segments = _chain_windows(windows, 30.0)
    assert len(segments) == 1
    assert segments[0].window_count == 4
    assert segments[0].end_s == pytest.approx(120.0)


def test_chain_splits_on_tempo_change() -> None:
    windows = [
        (0.0, 30.0, BeatGrid(120.0, 0.0, 4.0, "m", "plausible")),
        (30.0, 60.0, BeatGrid(120.0, 0.0, 4.0, "m", "plausible")),
        (60.0, 90.0, BeatGrid(174.0, 60.0, 4.0, "m", "plausible")),
        (90.0, 120.0, BeatGrid(174.0, 60.0, 4.0, "m", "plausible")),
    ]
    segments = _chain_windows(windows, 30.0)
    assert len(segments) == 2
    assert segments[0].bpm == pytest.approx(120.0)
    assert segments[1].bpm == pytest.approx(174.0)


def test_chain_splits_on_phase_change_at_same_tempo() -> None:
    """Zwei Tracks mit gleichem Tempo, aber eigener Eins - der Mix-Normalfall."""
    interval = 60.0 / 120.0
    windows = [
        (0.0, 30.0, BeatGrid(120.0, 0.0, 4.0, "m", "plausible")),
        (30.0, 60.0, BeatGrid(120.0, 0.0, 4.0, "m", "plausible")),
        (60.0, 90.0, BeatGrid(120.0, interval / 2.0, 4.0, "m", "plausible")),
    ]
    segments = _chain_windows(windows, 30.0)
    assert len(segments) == 2, "Phasensprung bei gleichem Tempo nicht erkannt"


def test_short_segments_are_absorbed() -> None:
    segments = [
        GridSegment(0.0, 120.0, 138.0, 0.0, 4.0, "plausible", 4),
        GridSegment(120.0, 140.0, 95.0, 120.0, 1.2, "suspect", 1),
        GridSegment(140.0, 300.0, 138.0, 140.0, 4.0, "plausible", 5),
    ]
    merged = _merge_short_segments(segments)
    assert all(s.duration_s >= MIN_SEGMENT_SECONDS for s in merged)
    assert len(merged) < len(segments)


def test_merge_keeps_total_span() -> None:
    """Zusammenfassen darf keine Zeit verlieren."""
    segments = [
        GridSegment(0.0, 100.0, 138.0, 0.0, 4.0, "plausible", 3),
        GridSegment(100.0, 120.0, 95.0, 100.0, 1.1, "suspect", 1),
        GridSegment(120.0, 260.0, 138.0, 120.0, 4.0, "plausible", 4),
    ]
    merged = _merge_short_segments(segments)
    assert merged[0].start_s == pytest.approx(0.0)
    assert merged[-1].end_s == pytest.approx(260.0)


# ---------------------------------------------------------------------------
# Gesamtlauf und Ausgabe
# ---------------------------------------------------------------------------


def test_short_signal_yields_single_segment() -> None:
    """Zu kurz zum Segmentieren: ein Abschnitt, ehrlicher als Schein-Genauigkeit."""
    signal = _click_track(128.0, 20.0)
    segments = segment_beat_grids(signal, SR)
    assert len(segments) == 1
    assert segments[0].start_s == 0.0


def test_empty_signal_yields_nothing() -> None:
    assert segment_beat_grids(np.zeros(0, dtype=np.float32), SR) == []


def test_beat_times_follow_the_rule() -> None:
    """Das Grid ist eine Regel - die Beats folgen daraus, sie sind nicht gespeichert."""
    segment = GridSegment(10.0, 12.0, 120.0, 0.25, 4.0, "plausible", 1)
    times = segment.beat_times()
    assert len(times) == 4
    assert np.allclose(np.diff(times), 0.5)
    assert times[0] >= 10.0 and times[-1] < 12.0


def test_payload_reports_dominant_not_average_tempo() -> None:
    """Ein Mittelwert ueber mehrere Tracks gilt in keinem Moment des Mixes."""
    segments = [
        GridSegment(0.0, 600.0, 138.0, 0.0, 4.0, "plausible", 20),
        GridSegment(600.0, 700.0, 174.0, 600.0, 3.0, "plausible", 3),
    ]
    payload = segments_as_payload(segments)
    assert payload["dominant_bpm"] == pytest.approx(138.0)
    assert payload["segment_count"] == 2
    assert sorted(payload["distinct_tempi"]) == [138.0, 174.0]


def test_payload_without_segments_is_honest() -> None:
    payload = segments_as_payload([])
    assert payload["status"] == "unavailable"
    assert payload["segments"] == []
