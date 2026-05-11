"""Test L-N8: BeatData.strength via librosa.onset.onset_strength.

Verifies that:
1. Beat-strength values are computed from librosa.onset.onset_strength
   (not the hardcoded 1.0) — different audio events at different beats
   produce different strengths.
2. Strength values lie in the normalized [0, 1] range.
3. pacing_service preserves the per-beat strength values when injecting
   into the engine.
4. The pacing engine consumes per-beat strength as a multiplier on the
   trigger strength.
"""
from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helper: build a synthetic kick pattern with three beats of different loudness
# ---------------------------------------------------------------------------
def _make_kick_audio(sr: int = 22050, duration: float = 5.0) -> np.ndarray:
    """Build 5s audio with 3 kick-like onsets at t=1.0, 2.5, 4.0 with
    decreasing amplitude (loud / mid / quiet)."""
    n = int(sr * duration)
    audio = np.zeros(n, dtype=np.float32)
    kick_len = 1500  # ~68 ms

    for t_sec, amp in [(1.0, 0.9), (2.5, 0.5), (4.0, 0.1)]:
        idx = int(t_sec * sr)
        env = np.exp(-np.arange(kick_len) / (sr * 0.04))
        tone = np.sin(2 * np.pi * 60 * np.arange(kick_len) / sr)
        audio[idx : idx + kick_len] = (amp * env * tone).astype(np.float32)
    return audio


# ---------------------------------------------------------------------------
# Test 1: compute_beat_strengths is a real per-beat sampling of onset_env
# ---------------------------------------------------------------------------
def test_compute_beat_strengths_distribution():
    """Different beat-positions yield distinct strengths (no constant 1.0)."""
    from pb_studio.audio.beat_detector import BeatDetector

    sr = 22050
    audio = _make_kick_audio(sr=sr)

    # Beats at the three kick positions
    beat_times = [1.0, 2.5, 4.0]

    strengths = BeatDetector.compute_beat_strengths(audio, sr, beat_times)

    assert isinstance(strengths, list), "strengths must be a list"
    assert len(strengths) == 3, "one strength value per beat-time"

    # Not all identical (loud > quiet)
    unique = {round(s, 3) for s in strengths}
    assert len(unique) >= 2, f"All strengths identical (no real onset sampling): {strengths}"

    # Loud kick at t=1.0 should outweigh the quiet kick at t=4.0
    assert strengths[0] > strengths[2], (
        f"Loud kick should have higher strength than quiet kick: {strengths}"
    )


# ---------------------------------------------------------------------------
# Test 2: strengths always lie within the normalized [0, 1] range
# ---------------------------------------------------------------------------
def test_compute_beat_strengths_range():
    """All strength values must be in [0.0, 1.0]."""
    from pb_studio.audio.beat_detector import BeatDetector

    sr = 22050
    audio = _make_kick_audio(sr=sr)
    beat_times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]

    strengths = BeatDetector.compute_beat_strengths(audio, sr, beat_times)
    assert len(strengths) == len(beat_times)
    for s in strengths:
        assert 0.0 <= s <= 1.0, f"Strength out of [0,1]: {s}"


# ---------------------------------------------------------------------------
# Test 3: empty / silent audio degrades gracefully (no crash, fallback values)
# ---------------------------------------------------------------------------
def test_compute_beat_strengths_silent_audio_safe():
    """Silent audio must not crash — returns finite values in [0,1]."""
    from pb_studio.audio.beat_detector import BeatDetector

    sr = 22050
    audio = np.zeros(sr * 2, dtype=np.float32)
    strengths = BeatDetector.compute_beat_strengths(audio, sr, [0.5, 1.0])

    assert len(strengths) == 2
    for s in strengths:
        assert np.isfinite(s)
        assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Test 4: pacing_service preserves the per-beat strength from cached_analysis
# ---------------------------------------------------------------------------
def test_pacing_service_preserves_beat_strengths(tmp_path):
    """When cached_analysis["beats"] contains per-beat strength values,
    pacing_service must forward them as engine._pre_cached_beat_strengths."""
    from pb_studio.services.pacing_service import PacingService
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    cached_analysis = {
        "beats": [
            {"time": 0.5, "strength": 0.2},
            {"time": 1.0, "strength": 0.9},
            {"time": 1.5, "strength": 0.5},
        ],
        "bpm": 120.0,
        "duration_seconds": 2.0,
    }

    service = PacingService.__new__(PacingService)
    # Minimal init for the helper we want to call
    service._last_used_cached_energy = False
    service._last_used_cached_bass = False
    service._last_used_cached_subtracks = False
    service._last_used_cached_tempo = False

    engine = AdvancedPacingEngine()
    service._inject_cached_into_engine(
        engine,
        audio_path=str(tmp_path / "dummy.wav"),
        cached_analysis=cached_analysis,
    )

    assert hasattr(engine, "_pre_cached_beats")
    assert engine._pre_cached_beats == [0.5, 1.0, 1.5]
    assert hasattr(engine, "_pre_cached_beat_strengths"), (
        "pacing_service must preserve per-beat strengths as _pre_cached_beat_strengths"
    )
    assert engine._pre_cached_beat_strengths == [0.2, 0.9, 0.5]


# ---------------------------------------------------------------------------
# Test 5: engine consumes per-beat strength as multiplier on trigger.strength
# ---------------------------------------------------------------------------
def test_engine_uses_beat_strength_as_multiplier():
    """Engine must scale trigger.strength by the per-beat onset strength.

    With pre-cached beats + matching pre-cached strengths, beats with higher
    onset-strength should produce higher trigger-strength than weaker beats
    (all other settings being equal).
    """
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    engine._pre_cached_beats = [1.0, 2.0]
    engine._pre_cached_beat_strengths = [0.2, 0.9]
    engine._pre_cached_bpm = 60.0
    engine._pre_cached_duration = 5.0

    triggers = engine._build_beat_triggers(
        beats=engine._pre_cached_beats,
        downbeats=[],
    )

    assert len(triggers) == 2
    weak, strong = triggers[0], triggers[1]
    assert strong.strength > weak.strength, (
        f"Beat at t=2.0 (strength=0.9) must outweigh beat at t=1.0 (strength=0.2): "
        f"{weak.strength} vs {strong.strength}"
    )


# ---------------------------------------------------------------------------
# Test 6: backward compat — engine still works when no beat-strengths injected
# ---------------------------------------------------------------------------
def test_engine_backward_compat_no_strengths():
    """If _pre_cached_beat_strengths absent, engine falls back to constant
    weighting (no regression for old callers)."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    engine._pre_cached_beats = [1.0, 2.0]
    engine._pre_cached_bpm = 60.0
    engine._pre_cached_duration = 5.0
    # NO _pre_cached_beat_strengths attribute

    triggers = engine._build_beat_triggers(beats=[1.0, 2.0], downbeats=[])
    assert len(triggers) == 2
    # Without strengths both regular beats are equal weight (0.7 * beat_weight)
    assert triggers[0].strength == pytest.approx(triggers[1].strength)
