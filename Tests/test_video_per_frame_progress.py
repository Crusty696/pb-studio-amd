"""Test: RAFT MotionAnalyzer ruft on_progress per Frame-Pair auf (Audit C1).

Verifiziert:
1. on_progress wird mehrfach aufgerufen (1x pro analysiertes Frame-Pair).
2. Percent-Argument liegt im 0..100 Bereich und ist monoton steigend.
3. Default on_progress=None crasht nicht (Backward Compat).
4. Exception im on_progress Callback bricht Analyse nicht ab.

Mock-Strategie: get_motion_magnitude + detect_scene_change werden gepatcht damit
keine ONNX-Inference (RAFT-Modell auf DirectML) noetig ist. Die Logik der
Loop-Steuerung + on_progress-Aufrufe ist unabhaengig vom Inference-Output.
"""
from unittest.mock import patch

import numpy as np
import pytest


def _make_frames(n: int):
    """Erzeugt n Dummy-Frames (kleine Aufloesung — schneller wenn Mocks fehlschlagen)."""
    return [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(n)]


def test_motion_analyzer_calls_on_progress_per_frame():
    """on_progress callback wird mehrfach aufgerufen, mit monoton steigendem Percent (0..100)."""
    from pb_studio.video.raft import MotionAnalyzer

    frames = _make_frames(5)
    progress_calls: list = []

    analyzer = MotionAnalyzer()
    # Mock Inference-Methoden — wir testen NUR die Loop+Callback-Logik, nicht RAFT/ONNX.
    with patch.object(analyzer, "get_motion_magnitude", return_value=1.5), \
         patch.object(analyzer, "detect_scene_change", return_value=(False, 0.0)):
        try:
            result = analyzer.analyze_video_segment(
                frames, stride=1, on_progress=lambda pct: progress_calls.append(pct)
            )
        finally:
            analyzer.unload()

    # 5 Frames, stride=1 → range(0, 4, 1) → 4 Iterationen
    assert len(progress_calls) == 4, f"Expected 4 callback calls, got {len(progress_calls)}"
    assert all(0.0 <= p <= 100.0 for p in progress_calls), f"Percent out of range: {progress_calls}"
    # Monoton steigend (jeder Call > voriger, da processed inkrementiert)
    for i in range(1, len(progress_calls)):
        assert progress_calls[i] > progress_calls[i - 1], (
            f"Percent must be monotonic increasing, got {progress_calls}"
        )
    # Letzter Call sollte exakt 100.0% sein (4/4 * 100)
    assert progress_calls[-1] == pytest.approx(100.0), (
        f"Last percent must be 100.0, got {progress_calls[-1]}"
    )
    # Result sollte gueltig sein
    assert result is not None
    assert "frame_motions" in result
    assert len(result["frame_motions"]) == 4


def test_motion_analyzer_works_without_callback():
    """Default on_progress=None — keine Crashes (Backward Compat)."""
    from pb_studio.video.raft import MotionAnalyzer

    frames = _make_frames(3)

    analyzer = MotionAnalyzer()
    with patch.object(analyzer, "get_motion_magnitude", return_value=2.0), \
         patch.object(analyzer, "detect_scene_change", return_value=(False, 0.0)):
        try:
            result = analyzer.analyze_video_segment(frames, stride=1)  # KEIN on_progress
        finally:
            analyzer.unload()

    assert result is not None
    assert "frame_motions" in result
    assert "avg_motion" in result
    assert len(result["frame_motions"]) == 2  # 3 Frames → 2 Pairs


def test_motion_analyzer_callback_exception_is_swallowed():
    """Exception im on_progress callback bricht Analyse nicht ab — never let callback break analysis."""
    from pb_studio.video.raft import MotionAnalyzer

    frames = _make_frames(4)
    call_count = {"n": 0}

    def _bad_callback(pct):
        call_count["n"] += 1
        raise RuntimeError("simulated SSE-Publish failure")

    analyzer = MotionAnalyzer()
    with patch.object(analyzer, "get_motion_magnitude", return_value=1.0), \
         patch.object(analyzer, "detect_scene_change", return_value=(False, 0.0)):
        try:
            # Darf NICHT raisen trotz immer crashendem callback
            result = analyzer.analyze_video_segment(frames, stride=1, on_progress=_bad_callback)
        finally:
            analyzer.unload()

    assert call_count["n"] == 3, f"Callback should be called 3x (4 frames, stride=1), got {call_count['n']}"
    assert result is not None
    assert len(result["frame_motions"]) == 3
