"""H-2: Beats/Trigger duerfen im Chunk-Overlap nicht doppelt gezaehlt werden.

Fenster 30 s, Schritt 25 s, also 5 s Overlap — 20 % der Timeline sind von zwei
Fenstern abgedeckt. Zwei unabhaengige Detektorlaeufe auf gegeneinander
verschobenen Fenstern haben eine beliebige Phase zueinander; liegt der Versatz
ueber BEAT_DEDUP_THRESHOLD_SEC (0,15 s), ueberlebt jeder Beat der Overlap-Zone
doppelt. Genau dieser Fall wird hier erzwungen: der gefakte Detektor liefert
pro ungeradem Fenster einen Phasenversatz von 0,25 s, die 0,15-s-Dedup greift
also bewusst NICHT.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

DURATION = 120.0
WINDOW = 30.0
OVERLAP = 5.0
STEP = WINDOW - OVERLAP
GRID = 0.5              # gleichmaessiges Raster -> 120 BPM
PHASE_SHIFT = 0.25      # > BEAT_DEDUP_THRESHOLD_SEC (0.15)
EXPECTED_BEATS = int(DURATION / GRID)  # 240 Rasterpunkte in [0, 120)


def _detector_grid(chunk_start: float) -> list[float]:
    """Simuliert einen Detektorlauf ueber den GANZEN Chunk inkl. Overlap.

    Der Detektor kennt nur seinen Chunk, liefert also Ergebnisse fuer dessen
    volle Spanne. Ungerade Fenster bekommen einen Phasenversatz, wie ihn zwei
    unabhaengige `beat_track`-Laeufe zueinander haben.
    """
    index = int(round(chunk_start / STEP))
    phase = PHASE_SHIFT if index % 2 else 0.0
    chunk_end = min(chunk_start + WINDOW, DURATION)
    times: list[float] = []
    value = chunk_start + phase
    while value < chunk_end - 1e-9:
        times.append(round(value, 6))
        value += GRID
    return times


def _configure(monkeypatch: pytest.MonkeyPatch, analyzer: StreamingAudioAnalyzer) -> None:
    def load_chunk(_path: Path, _start: float, _duration: float) -> np.ndarray:
        return np.zeros(1024, dtype=np.float32)

    def process_beats(_chunk, start, bpm_est, beat_acc):
        bpm_est.add(60.0 / GRID)
        beat_acc.add_chunk_beats(_detector_grid(start))
        return None

    def process_triggers(_chunk, start, onset_acc, kick_acc, snare_acc, hihat_acc):
        onset_acc.add_chunk_beats(_detector_grid(start))
        kick_acc.add_chunk_beats(_detector_grid(start))
        snare_acc.add_chunk_beats(_detector_grid(start))
        hihat_acc.add_chunk_beats(_detector_grid(start))
        return None

    def representative(_chunk, start, **_kwargs):
        from pb_studio.audio.spectral_analyzer import FREQUENCY_BANDS

        band_names = set(FREQUENCY_BANDS) | {"low", "mid", "high"}
        return {
            "times": [start + 0.5],
            "bands": {name: [1.0] for name in band_names},
            "centroids": [100.0],
            "chroma_mean": [1.0] * 12,
            "chroma_weight": 1,
        }

    monkeypatch.setattr(analyzer, "_load_chunk", load_chunk)
    monkeypatch.setattr(analyzer, "_process_beats", process_beats)
    monkeypatch.setattr(analyzer, "_process_triggers", process_triggers)
    monkeypatch.setattr(analyzer, "_extract_representative_features", representative)
    monkeypatch.setattr(analyzer, "_process_energy", lambda *_a, **_kw: None)


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source = tmp_path / "long-mix.wav"
    source.write_bytes(b"overlap-dedup-source")
    analyzer = StreamingAudioAnalyzer(window_sec=WINDOW, overlap_sec=OVERLAP)
    _configure(monkeypatch, analyzer)
    return analyzer._analyze_streaming_prepared(
        source,
        DURATION,
        on_progress=None,
        energy_only=False,
        native_sr=44100,
        source_identity=analyzer._source_identity(source),
    )


def test_overlap_does_not_inflate_beat_and_trigger_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = _run(monkeypatch, tmp_path)

    # Wahrheit: 240 Rasterpunkte. Ohne den Fix waeren es 280 (20 % Overlap,
    # von der 0,15-s-Dedup wegen 0,25 s Phasenversatz nicht abgefangen).
    assert len(result.beats) == EXPECTED_BEATS
    for name in ("onset_times", "kick_times", "snare_times", "hihat_times"):
        assert len(getattr(result, name)) == EXPECTED_BEATS, name


def test_no_phase_collapse_at_window_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = _run(monkeypatch, tmp_path)

    diffs = np.diff(np.asarray(result.beats, dtype=np.float64))
    n_windows = int(np.ceil((DURATION - OVERLAP) / STEP))

    # Ein Phasensprung an der Naht zwischen zwei Fenstern ist unvermeidbar —
    # aber es darf hoechstens EINER pro Fenstergrenze sein. Ohne den Fix ist
    # jede 5-s-Overlap-Zone komplett doppelt belegt, dort stehen dann ~10
    # zusaetzliche Unterraster-Abstaende je Grenze.
    too_close = int(np.count_nonzero(diffs < GRID - 0.05))
    assert too_close <= n_windows - 1

    # Und keine Luecke groesser als ein Raster plus Phasenversatz —
    # es geht nichts verloren.
    assert float(diffs.max()) <= GRID + PHASE_SHIFT + 1e-6


def test_first_window_is_never_truncated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = _run(monkeypatch, tmp_path)

    # Das erste Fenster hat keinen Vorgaenger — der Anfang des Stuecks muss
    # vollstaendig erhalten bleiben.
    assert result.beats[0] == pytest.approx(0.0, abs=1e-6)
    assert len([t for t in result.beats if t < OVERLAP]) == int(OVERLAP / GRID)


def test_derived_bpm_matches_the_true_grid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = _run(monkeypatch, tmp_path)

    median_interval = float(np.median(np.diff(np.asarray(result.beats))))
    assert 60.0 / median_interval == pytest.approx(60.0 / GRID, rel=0.02)
