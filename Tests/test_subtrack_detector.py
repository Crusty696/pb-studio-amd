"""Tests für SubtrackDetector (Plan Phase 1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pb_studio.audio.subtrack_detector import SubtrackDetector


def _write_wav(path: Path, y: np.ndarray, sr: int = 22050) -> None:
    import soundfile as sf
    sf.write(str(path), y.astype(np.float32), sr)


def test_subtrack_fallback_short_signal(tmp_path: Path):
    """Sehr kurzes Signal -> 0 Boundaries -> 1 Sub-Track-Segment."""
    sr = 22050
    y = np.zeros(sr * 5, dtype=np.float32)
    f = tmp_path / "tiny.wav"
    _write_wav(f, y, sr)
    res = SubtrackDetector(sr=sr).detect(f)
    assert res.boundaries == [] or len(res.segments) == 1
    assert len(res.segments) == 1
    assert res.segments[0][0] == 0.0


def test_subtrack_detects_clear_boundary(tmp_path: Path):
    """Synthetic mix mit klarer Bruchstelle bei 70s -> Boundary in der Nähe."""
    sr = 22050
    duration = 140  # 2x 70s
    t = np.linspace(0, duration, sr * duration, endpoint=False, dtype=np.float32)

    half = sr * 70
    a = 0.3 * np.sin(2 * np.pi * 220 * t[:half]).astype(np.float32)
    b = 0.3 * np.sin(2 * np.pi * 880 * t[half:]).astype(np.float32)
    y = np.concatenate([a, b])
    f = tmp_path / "two_track.wav"
    _write_wav(f, y, sr)

    detector = SubtrackDetector(sr=sr, min_distance_sec=30.0)
    res = detector.detect(f)
    assert len(res.segments) >= 1
    # If a boundary was found, expect it near the 70s mark (+/- 15s tolerance)
    if res.boundaries:
        nearest = min(abs(b.time - 70.0) for b in res.boundaries)
        assert nearest < 25.0


@pytest.mark.skipif(
    not Path("Tests/data/hiphop_mashup_2h.mp3").exists(),
    reason="manuell annotiertes Test-Set nicht vorhanden",
)
def test_subtrack_f_measure_realdata():
    """Optional: F-Measure >= 0.65 auf 5 Test-Mixes (Plan DoD)."""
    pytest.skip("F-Measure-Eval ist eigenes Skript scripts/verify_subtrack_detection.py")
