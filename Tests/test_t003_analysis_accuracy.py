"""Regressionen zu T003 (Spec 00035, 2026-09-30): Tonart, Beat-Phase, Mix-Grenzen.

Die Messungen gegen echte Musik (rekordbox-Referenz, konstruierte Referenzmixe)
stehen in specs/00035-full-audit-remediation/evidence/t003-fixes-20260930.md.
Diese Tests halten die drei Mechanismen an synthetischem Material fest und
pruefen jeweils die Gegenprobe: mit abgeschaltetem Mechanismus tritt der
alte Fehler wieder auf.
"""
from __future__ import annotations

import numpy as np
import pytest

from pb_studio.audio import beat_grid as bg
from pb_studio.audio import subtrack_detector as sd
from pb_studio.audio.key_detector import _MAJOR_PROFILE, _MINOR_PROFILE, KeyDetector

SR = 22050


# --------------------------------------------------------------------------- Tonart

def _ambiguous_c_chroma() -> np.ndarray:
    """Mischung aus C-Dur- und c-Moll-Profil, bei der Dur knapp vorne liegt."""
    for weight in np.linspace(0.5, 0.9, 81):
        vector = weight * _MAJOR_PROFILE + (1.0 - weight) * _MINOR_PROFILE
        major = np.corrcoef(vector, _MAJOR_PROFILE)[0, 1]
        minor = np.corrcoef(vector, _MINOR_PROFILE)[0, 1]
        if 0.0 < major - minor < 0.05:
            return vector
    raise AssertionError("kein knapper Dur/Moll-Fall konstruierbar")


def test_minor_prior_resolves_near_tie_towards_minor() -> None:
    vector = _ambiguous_c_chroma()
    assert KeyDetector(minor_prior=0.0).detect_key_from_chroma(vector) == "C major"
    assert KeyDetector().detect_key_from_chroma(vector) == "C minor"


def test_minor_prior_keeps_a_clear_major_key() -> None:
    assert KeyDetector().detect_key_from_chroma(np.roll(_MAJOR_PROFILE, 7)) == "G major"
    assert KeyDetector().detect_key_from_chroma(np.roll(_MINOR_PROFILE, 9)) == "A minor"


def test_audio_and_chroma_paths_share_one_decision() -> None:
    """Vorher zwei Kopien derselben Schleife - jetzt eine gemeinsame."""
    detector = KeyDetector()
    vector = _ambiguous_c_chroma()
    assert detector._best_key(vector)[0] == detector.detect_key_from_chroma(vector)


# --------------------------------------------------------------------------- Beat-Phase

def _kick_offbeat_signal(bpm: float = 138.0, duration: float = 30.0, offset: float = 0.2):
    """Kick (50 Hz) auf dem Schlag, lautere Hi-Hat-Rauschstoesse auf dem Off-Beat.

    Nachbildung des gemessenen Psytrance-Falls: die Vollband-Onset-Huellkurve
    ist auf dem Off-Beat staerker als auf dem Kick.
    """
    rng = np.random.default_rng(20260930)
    y = rng.normal(0.0, 0.0005, int(SR * duration)).astype(np.float32)
    interval = 60.0 / bpm
    n_kick = int(0.12 * SR)
    t_kick = np.arange(n_kick) / SR
    kick = (np.sin(2 * np.pi * 50.0 * t_kick) * np.exp(-t_kick * 25.0)).astype(np.float32)
    n_hat = int(0.04 * SR)
    hat = (rng.normal(0.0, 1.0, n_hat) * np.exp(-np.arange(n_hat) / (0.008 * SR))).astype(np.float32)
    kicks = []
    position = offset
    while position + interval < duration:
        start = int(position * SR)
        y[start:start + n_kick] += 0.8 * kick
        off = int((position + interval / 2) * SR)
        y[off:off + n_hat] += 0.9 * hat
        kicks.append(position)
        position += interval
    return y, kicks, interval


def _phase_error(anchor: float, reference: float, interval: float) -> float:
    return abs((anchor - reference + interval / 2) % interval - interval / 2)


def test_grid_sits_on_the_kick_not_on_the_offbeat() -> None:
    y, kicks, interval = _kick_offbeat_signal()
    grid = bg.estimate_beat_grid(y, SR)
    assert abs(grid.bpm - 138.0) / 138.0 < 0.02
    assert _phase_error(grid.anchor_s, kicks[0], interval) < 0.15 * interval, grid


def test_offbeat_grid_returns_without_half_beat_resolution(monkeypatch) -> None:
    """Gegenprobe: ohne die Sub-Bass-Pruefung landet das Raster auf dem Off-Beat."""
    y, kicks, interval = _kick_offbeat_signal()
    monkeypatch.setattr(bg, "HALF_BEAT_MARGIN", float("inf"))
    grid = bg.estimate_beat_grid(y, SR)
    assert _phase_error(grid.anchor_s, kicks[0] + interval / 2, interval) < 0.15 * interval, grid
    assert "half_beat_corrected" not in grid.method


def test_anchor_compensates_one_frame_envelope_lag() -> None:
    """Anker trifft den Anschlag, nicht den Frame danach (+23,2 ms bei 22,05 kHz)."""
    rng = np.random.default_rng(1)
    y = rng.normal(0.0, 0.001, SR * 30).astype(np.float32)
    click = np.exp(-np.linspace(0.0, 12.0, int(SR * 0.02))).astype(np.float32)
    interval, first = 60.0 / 128.0, 0.31
    t = first
    while t < 29.5:
        s = int(t * SR)
        y[s:s + click.size] += click
        t += interval
    grid = bg.estimate_beat_grid(y, SR)
    assert _phase_error(grid.anchor_s, first, interval) < 0.012, grid


# --------------------------------------------------------------------------- Mix-Grenzen

def test_tempo_step_novelty_ignores_jitter_and_marks_real_step() -> None:
    frame = 4.0
    rng = np.random.default_rng(3)
    tempo = np.concatenate([np.full(60, 128.0), np.full(60, 124.0)]) + rng.normal(0, 0.05, 120)
    tempo[20] = 0.0  # unbekanntes Fenster (Breakdown) darf keine Stufe erzeugen
    novelty = sd.SubtrackDetector._tempo_step_novelty(tempo.astype(np.float32), frame)
    assert int(np.argmax(novelty)) in range(58, 63)
    assert novelty.max() == pytest.approx(1.0)
    assert np.all(novelty[:50] == 0.0) and np.all(novelty[70:] == 0.0)


def _synthetic_mix_features(duration: float = 1800.0, boundaries=(420.0, 900.0, 1380.0)):
    """Sekunden-Features eines 30-min-Mixes: je Titel eigenes Chroma-Muster mit
    Wiederholung, ein Breakdown pro Titel und grosse RMS-/Flux-Spruenge
    innerhalb der Titel (die alte Summenfusion hat genau darauf reagiert)."""
    rng = np.random.default_rng(7)
    n = int(duration)
    edges = [0, *[int(b) for b in boundaries], n]
    chroma = np.zeros((12, n), dtype=np.float32)
    activity = np.abs(rng.normal(0.0, 0.01, n)).astype(np.float32)
    flux = np.abs(rng.normal(0.0, 0.05, n)).astype(np.float32)
    tempo = np.zeros(n, dtype=np.float32)
    for index, (start, end) in enumerate(zip(edges[:-1], edges[1:])):
        motifs = rng.random((4, 12)).astype(np.float32) ** 3
        for second in range(start, end):
            chroma[:, second] = motifs[(second // 8) % 4] + rng.normal(0, 0.02, 12)
        middle = (start + end) // 2
        chroma[:, middle:middle + 30] = rng.random((12, 1)).astype(np.float32)  # Breakdown
        activity[middle] = activity[middle + 30] = 1.0
        flux[middle + 30] = 2.0
        tempo[start:end] = 124.0 + index  # nicht beatgematcht
        tempo[middle:middle + 30] = 0.0   # Breakdown ohne sitzendes Raster
    return np.clip(chroma, 0, None), activity, flux, tempo


def test_long_mix_finds_track_changes_not_breakdowns(monkeypatch, tmp_path) -> None:
    import librosa

    boundaries = (420.0, 900.0, 1380.0)
    features = _synthetic_mix_features(boundaries=boundaries)
    monkeypatch.setattr(librosa, "get_duration", lambda **_kw: 1800.0)
    detector = sd.SubtrackDetector()
    monkeypatch.setattr(detector, "_bounded_chunk_features", lambda *_a: features)
    result = detector.detect(tmp_path / "mix.wav")
    found = [b.time for b in result.boundaries]
    assert len(found) == len(boundaries), found
    for truth in boundaries:
        assert min(abs(f - truth) for f in found) <= 15.0, (truth, found)


def test_long_mix_without_tempo_cue_still_uses_harmonic_repetition(monkeypatch, tmp_path) -> None:
    """Beatgematchter Mix: gleiches Tempo ueberall - die Tempostufe schweigt."""
    import librosa

    chroma, activity, flux, tempo = _synthetic_mix_features()
    tempo = np.where(tempo > 0, 128.0, 0.0).astype(np.float32)
    monkeypatch.setattr(librosa, "get_duration", lambda **_kw: 1800.0)
    detector = sd.SubtrackDetector()
    monkeypatch.setattr(detector, "_bounded_chunk_features", lambda *_a: (chroma, activity, flux, tempo))
    found = [b.time for b in detector.detect(tmp_path / "mix.wav").boundaries]
    assert found and all(b.components["tempo"] == 0.0 for b in detector.detect(tmp_path / "mix.wav").boundaries)
    hits = sum(min(abs(f - t) for f in found) <= 15.0 for t in (420.0, 900.0, 1380.0))
    assert hits >= 2, found
