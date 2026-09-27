"""Regressions for truthful event-driven long-mix structure analysis."""

import numpy as np
import pytest

from pb_studio.audio.structure_analyzer import StructureAnalyzer


def test_streaming_structure_boundaries_follow_energy_changes_not_minute_marks():
    duration = 300.0
    sample_rate = 5
    energy = np.concatenate(
        [
            np.full(73 * sample_rate, 0.10),
            np.full((187 - 73) * sample_rate, 0.85),
            np.full((300 - 187) * sample_rate, 0.15),
        ]
    )

    segments = StructureAnalyzer().analyze_streaming_energy(
        energy.tolist(), duration
    )["segments"]

    boundaries = [segment["end_time"] for segment in segments[:-1]]
    assert len(boundaries) == 2
    assert boundaries == pytest.approx([73.0, 187.0], abs=3.0)


def test_streaming_structure_does_not_assign_intro_outro_by_position_alone():
    energy = np.full(300 * 5, 0.70)

    segments = StructureAnalyzer().analyze_streaming_energy(
        energy.tolist(), 300.0
    )["segments"]

    assert len(segments) == 1
    assert segments[0]["label"] == "section"


def test_streaming_intro_and_outro_require_observed_edge_transitions():
    sample_rate = 5
    energy = np.concatenate(
        [
            np.full(30 * sample_rate, 0.03),
            np.full(230 * sample_rate, 0.75),
            np.linspace(0.75, 0.02, 40 * sample_rate),
        ]
    )

    segments = StructureAnalyzer().analyze_streaming_energy(
        energy.tolist(), 300.0
    )["segments"]

    assert segments[0]["label"] == "intro"
    assert segments[-1]["label"] == "outro"
    assert segments[0]["start_time"] == 0.0
    assert segments[-1]["end_time"] == pytest.approx(300.0)
