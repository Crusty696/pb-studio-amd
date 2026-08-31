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
    _chance_rates,
    _kick_tolerance,
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


def test_grid_below_chance_agreement_is_not_called_plausible() -> None:
    """Kernbefund vom 2026-08-31: Kontrast allein darf nicht ueber `status` entscheiden.

    An echtem Material (Antinomy - Imagination (Kalki remix), 544 s, 143 BPM
    laut Auszeichnung) meldete der Schaetzer 94,67 BPM mit Kontrast 4,44 als
    `plausible` - bei Trefferquote 0,0339 und Praezision 0,0349. Ein Raster,
    dessen unabhaengige Gegenprobe unter dem Zufallsniveau liegt, behauptet
    mit `plausible` etwas, das seine eigenen Messwerte widerlegen.

    Nachgestellt wird der Fall, den der Befund als Ursache nennt: ein
    systematischer Versatz zwischen den beiden Ketten. Die Kicks liegen hier
    110 ms hinter den Anschlaegen - mehr als die Toleranz von 69,7 ms, und zwar
    fuer jede Oktave, die der Schaetzer von 174 BPM aus erreicht (58 / 116 /
    174 BPM, Intervalle 1,034 / 0,517 / 0,345 s). Der Bereich ist an dieser
    Stelle eng: ab etwa 130 ms faengt das 116-BPM-Raster jeden dritten Kick
    ein, weil es zu den Anschlaegen im Verhaeltnis 2:3 steht. 100 und 120 ms
    wurden gegengeprueft und verhalten sich wie 110 ms. Der Kontrast bleibt
    dabei hoch, weil das Signal selbst sauber gepulst ist.
    """
    signal, times = _click_track(174.0, duration=30.0)
    offset_kicks = [t + 0.110 for t in times]

    grid = estimate_beat_grid(signal, SR, kick_times=offset_kicks)

    assert grid.contrast >= GRID_CONTRAST_MIN, (
        "Vorbedingung verletzt: das Signal muss einen klaren Puls tragen, "
        f"Kontrast ist aber nur {grid.contrast}"
    )
    assert grid.octave_checked is True
    assert grid.kick_recall == 0.0 and grid.kick_precision == 0.0, (
        f"Aufbau greift nicht: recall={grid.kick_recall} "
        f"precision={grid.kick_precision} - der Versatz muss jede Oktave "
        f"verfehlen"
    )
    assert grid.status != "plausible", (
        f"Raster mit Trefferquote {grid.kick_recall} und Praezision "
        f"{grid.kick_precision} wurde als {grid.status} gemeldet"
    )
    assert "below_chance" in grid.method, (
        f"der Grund fehlt in der Herkunftsangabe: {grid.method}"
    )
    assert grid.kick_recall_chance is not None, (
        "die Zufallserwartung muss mitgeliefert werden, sonst ist das Urteil "
        "nicht nachrechenbar"
    )


def test_a_clean_grid_stays_plausible_under_the_new_check() -> None:
    """Gegenprobe zum Test darueber: die Pruefung darf nicht alles verwerfen."""
    signal, times = _click_track(128.0, duration=30.0)
    grid = estimate_beat_grid(signal, SR, kick_times=times)
    assert grid.status == "plausible", (
        f"sauberes Raster als {grid.status} verworfen "
        f"(recall={grid.kick_recall}, chance={grid.kick_recall_chance})"
    )
    assert grid.kick_recall > (grid.kick_recall_chance or 0.0)


def test_chance_level_is_the_null_hypothesis_not_a_read_off_number() -> None:
    """Die Schwelle ist gerechnet, nicht gesetzt: 2*Toleranz/Abstand."""
    tolerance = 3 * 512 / 22050  # 69,7 ms
    # 143 BPM -> Beat-Intervall 0,4196 s; 100 Kicks ueber 40 s -> 0,404 s
    chance_recall, chance_precision = _chance_rates(143.0, 100, 40.0, tolerance)
    assert chance_recall == pytest.approx(2 * tolerance / (60.0 / 143.0), rel=1e-9)
    assert chance_precision == pytest.approx(2 * tolerance / (40.0 / 99.0), rel=1e-9)
    # Ein doppelt so schnelles Raster hat die doppelte Zufallserwartung - genau
    # deshalb ist eine feste Schwelle fuer alle Tempi unbrauchbar.
    faster, _ = _chance_rates(286.0, 100, 40.0, tolerance)
    assert faster == pytest.approx(2 * chance_recall, rel=1e-9)
    # Nie ueber 1.0, auch wenn die Toleranz den Abstand uebersteigt.
    saturated, _ = _chance_rates(60.0, 100, 40.0, 5.0)
    assert saturated == 1.0
    # Ohne verwertbare Gegenseite gibt es keine Erwartung.
    assert _chance_rates(143.0, 1, 40.0, tolerance) == (0.0, 0.0)
    assert _chance_rates(0.0, 100, 40.0, tolerance) == (0.0, 0.0)


def test_tolerance_does_not_depend_on_the_load_rate() -> None:
    """Derselbe Track darf nicht je nach `spectral_analysis`-Flag anders bewertet werden.

    Der Router laedt mit 44100 Hz, wenn `spectral_analysis` gesetzt ist, sonst
    mit 22050 (audio_router.py:2136). Die Toleranz wurde mit der tatsaechlichen
    Rate gerechnet und war deshalb bei 44100 nur halb so gross. An der echten
    Datei gemessen: dasselbe Signal, dieselbe Kick-Kette, dasselbe
    94,67-BPM-Raster -> Trefferquote 0,0339 gegen 0,3054. Faktor 9 allein aus
    einem Flag, das mit Beats nichts zu tun hat.
    """
    assert _kick_tolerance(44100) == pytest.approx(_kick_tolerance(22050))
    assert _kick_tolerance(22050) == pytest.approx(3 * 512 / 22050)
    assert _kick_tolerance(48000) == pytest.approx(3 * 512 / 22050)
    # Wird groeber geladen, zaehlt die groebere Hop-Dauer - darunter misst man
    # wieder Quantisierungsrauschen.
    assert _kick_tolerance(11025) == pytest.approx(3 * 512 / 11025)
    assert _kick_tolerance(0) == pytest.approx(3 * 512 / 22050)


@pytest.mark.parametrize("sr", [22050, 44100])
def test_same_material_is_judged_the_same_at_both_load_rates(sr: int) -> None:
    """Verhaltensprobe zur Toleranz: Kicks 55 ms neben dem Anschlag.

    55 ms liegt unter der Toleranz von 69,7 ms und ueber der halbierten von
    34,8 ms. Vor der Korrektur trennte genau dieser Bereich die beiden
    Laderaten; danach faellt das Urteil an beiden gleich aus.
    """
    rng = np.random.default_rng(20260831)
    duration = 30.0
    signal = rng.normal(0.0, 0.001, int(sr * duration)).astype(np.float32)
    click = np.exp(-np.linspace(0.0, 12.0, int(sr * 0.02))).astype(np.float32)
    interval = 60.0 / 128.0
    times: list[float] = []
    position = 0.0
    while position < duration - 0.05:
        start = int(position * sr)
        signal[start:start + click.size] += click * 0.8
        times.append(position)
        position += interval

    grid = estimate_beat_grid(signal, sr, kick_times=[t + 0.055 for t in times])

    assert grid.kick_recall is not None and grid.kick_recall > 0.9, (
        f"bei sr={sr} nur Trefferquote {grid.kick_recall} - die Toleranz haengt "
        f"noch an der Laderate"
    )
    assert grid.status == "plausible"


def test_a_cross_check_that_hits_nothing_is_reported_not_swallowed() -> None:
    """Null Treffer ist ein Messwert, kein Grund zum Ueberspringen.

    Die Oktavschleife uebersprang Versuche mit Trefferquote UND Praezision
    gleich null. Traf keine einzige Oktave einen Kick, blieben beide Felder
    deshalb `None` - und das ungepruefte Raster ging als `plausible` durch.
    Der unguenstigste Fall wurde als der beste ausgegeben.
    """
    signal, times = _click_track(174.0, duration=30.0)
    grid = estimate_beat_grid(signal, SR, kick_times=[t + 0.110 for t in times])
    assert grid.kick_recall is not None and grid.kick_precision is not None, (
        "Nullergebnis wurde verschluckt statt gemeldet"
    )


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
