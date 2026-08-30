"""Tests fuer die Beatgrid-Schaetzung (`pb_studio.audio.beat_grid`).

Die Tests arbeiten mit synthetisch erzeugten Klickspuren bekannten Tempos.
Damit laesst sich pruefen, ob der Schaetzer das Tempo trifft, den Anker findet
und Oktavfehler aufloest - unabhaengig von echtem Material.

Was diese Tests ausdruecklich NICHT belegen: dass der Schaetzer auf realer
Musik besser ist als `librosa.beat.beat_track`. Dafuer gibt es eine eigene
Messung gegen Material mit BPM-Referenz.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from pb_studio.audio.beat_grid import (  # noqa: E402
    GRID_CONTRAST_MIN,
    BeatGrid,
    estimate_beat_grid,
)

SR = 22050


def _click_track(
    bpm: float,
    duration: float = 30.0,
    offset: float = 0.0,
    accent_every: int = 0,
) -> tuple[np.ndarray, list[float]]:
    """Klickspur mit exaktem Tempo. Liefert Signal und die Klickzeitpunkte."""
    rng = np.random.default_rng(20260831)
    signal = rng.normal(0.0, 0.001, int(SR * duration)).astype(np.float32)
    interval = 60.0 / bpm
    click = np.exp(-np.linspace(0.0, 12.0, int(SR * 0.02))).astype(np.float32)
    times: list[float] = []
    index = 0
    position = offset
    while position < duration - 0.05:
        start = int(position * SR)
        amplitude = 1.0 if (accent_every and index % accent_every == 0) else 0.7
        signal[start:start + click.size] += click * amplitude
        times.append(position)
        position += interval
        index += 1
    return signal, times


def test_finds_tempo_of_a_clean_click_track() -> None:
    signal, _ = _click_track(128.0)
    grid = estimate_beat_grid(signal, SR)
    assert abs(grid.bpm - 128.0) / 128.0 < 0.02, f"Tempo {grid.bpm} statt 128"
    assert grid.status == "plausible"


@pytest.mark.parametrize("bpm", [92.0, 110.0, 128.0, 145.0, 174.0])
def test_tempo_is_not_pulled_towards_120(bpm: float) -> None:
    """Kernpunkt gegenueber `beat_track`: kein Prior um 120 BPM.

    Gemessen an kommerziellem Material lieferte `beat_track` ueber 104 Fenster
    nur sechs verschiedene Tempowerte. Der Schaetzer hier darf Stuecke abseits
    von 120 BPM nicht dorthin ziehen.
    """
    signal, _ = _click_track(bpm)
    grid = estimate_beat_grid(signal, SR)
    assert abs(grid.bpm - bpm) / bpm < 0.02, f"{bpm} BPM wurde als {grid.bpm} erkannt"


def test_anchor_locates_the_first_beat() -> None:
    signal, times = _click_track(120.0, offset=0.17)
    grid = estimate_beat_grid(signal, SR)
    interval = 60.0 / grid.bpm
    # Der Anker darf um ganze Beat-Intervalle verschoben sein; entscheidend
    # ist die Phase.
    phase_error = abs((grid.anchor_s - times[0] + interval / 2) % interval - interval / 2)
    assert phase_error < interval * 0.15, (
        f"Anker {grid.anchor_s:.3f} passt nicht zur Phase von {times[0]:.3f}"
    )


def test_grid_reproduces_the_click_positions() -> None:
    """Das Raster ist eine Regel - sie muss die echten Anschlaege treffen."""
    signal, times = _click_track(140.0, duration=20.0, offset=0.3)
    grid = estimate_beat_grid(signal, SR)
    produced = grid.beat_times(0.0, 20.0)
    truth = np.asarray(times)
    matched = 0
    for value in truth:
        if produced.size and np.min(np.abs(produced - value)) < 0.05:
            matched += 1
    assert matched / truth.size > 0.9, (
        f"nur {matched}/{truth.size} echte Anschlaege vom Raster getroffen"
    )


def test_half_tempo_is_corrected_using_kicks() -> None:
    """Zu langsames Raster: faellt ueber die Trefferquote auf."""
    signal, times = _click_track(128.0, duration=30.0)
    # Kicks auf jedem Beat - ein 64-BPM-Raster wuerde nur jeden zweiten treffen.
    grid = estimate_beat_grid(signal, SR, kick_times=times)
    assert abs(grid.bpm - 128.0) / 128.0 < 0.03
    assert grid.octave_checked is True
    assert grid.kick_recall is not None and grid.kick_recall > 0.8


def test_double_tempo_is_caught_by_precision_not_recall() -> None:
    """Zu schnelles Raster: die reine Trefferquote sieht es nicht.

    Ein doppeltes Raster enthaelt alle wahren Beats, die Trefferquote bleibt
    also bei ~1,0. Erst die Praezision - Anteil der Beats mit Kick - faellt.
    Dieser Test haelt genau diese Eigenschaft fest.
    """
    _, times = _click_track(128.0, duration=30.0)
    kicks = np.asarray(times)
    true_grid = BeatGrid(128.0, times[0], 0.0, "", "").beat_times(0.0, 30.0)
    double_grid = BeatGrid(256.0, times[0], 0.0, "", "").beat_times(0.0, 30.0)

    from pb_studio.audio.beat_grid import _kick_agreement

    tolerance = 3 * 512 / SR
    recall_true, precision_true = _kick_agreement(true_grid, kicks, tolerance)
    recall_double, precision_double = _kick_agreement(double_grid, kicks, tolerance)

    assert recall_double >= recall_true - 0.05, (
        "Annahme verletzt: das doppelte Raster sollte die Kicks weiter treffen"
    )
    assert precision_double < precision_true * 0.7, (
        f"Praezision trennt die Oktave nicht: {precision_double:.2f} "
        f"gegen {precision_true:.2f}"
    )


def test_noise_is_reported_as_suspect_not_as_a_grid() -> None:
    """Ohne Puls darf kein plausibles Raster behauptet werden."""
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 0.1, SR * 20).astype(np.float32)
    grid = estimate_beat_grid(noise, SR)
    assert grid.status in {"suspect", "unavailable"}, (
        f"Rauschen als {grid.status} mit Kontrast {grid.contrast} gemeldet"
    )
    assert grid.contrast < GRID_CONTRAST_MIN


def test_silence_reports_unavailable() -> None:
    grid = estimate_beat_grid(np.zeros(SR * 5, dtype=np.float32), SR)
    assert grid.status == "unavailable"
    assert grid.bpm == 0.0


def test_beat_times_are_derived_not_stored() -> None:
    """Ein Grid ist eine Regel: beliebige Intervalle, gleichmaessige Abstaende."""
    grid = BeatGrid(120.0, 0.25, 3.0, "test", "plausible")
    times = grid.beat_times(10.0, 20.0)
    assert times.size > 0
    assert np.allclose(np.diff(times), 0.5)
    assert times[0] >= 10.0


def test_provenance_is_serialisable_and_marks_non_synthetic() -> None:
    grid = estimate_beat_grid(_click_track(128.0)[0], SR)
    provenance = grid.as_provenance()
    assert provenance["synthetic"] is False
    assert provenance["method"]
    assert "candidates" not in provenance
    import json

    json.dumps(provenance)
