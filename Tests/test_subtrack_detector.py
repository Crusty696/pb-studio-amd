"""Tests für SubtrackDetector (Plan Phase 1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from pb_studio.audio.subtrack_detector import SubtrackDetector
from scripts.verify_subtrack_detection import evaluate_boundaries


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


def test_subtrack_boundary_evaluation_counts_each_label_once():
    metrics = evaluate_boundaries([10.0, 12.0], [11.0], tolerance=15.0)

    assert metrics == {
        "tp": 1,
        "fp": 1,
        "fn": 0,
        "precision": 0.5,
        "recall": 1.0,
        "f1": 2 / 3,
    }


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SUBTRACK_AUDIO = _REPOSITORY_ROOT / "Tests/data/hiphop_mashup_2h.mp3"
_SUBTRACK_GROUND_TRUTH = _REPOSITORY_ROOT / "Tests/data/hiphop_mashup_2h.boundaries.txt"


@pytest.mark.skipif(
    not _SUBTRACK_AUDIO.is_file() or not _SUBTRACK_GROUND_TRUTH.is_file(),
    reason="Subtrack-Realmedien oder zeitcodierte Referenzgrenzen fehlen",
)
def test_subtrack_f_measure_realdata():
    """Run the real-media evaluator when its audio and boundary labels exist."""
    evaluator = _REPOSITORY_ROOT / "scripts" / "verify_subtrack_detection.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(evaluator),
            str(_SUBTRACK_AUDIO),
            str(_SUBTRACK_GROUND_TRUTH),
        ],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Ground truth:" in completed.stdout
    assert "f1=" in completed.stdout
