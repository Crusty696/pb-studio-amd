"""Neutral long-mix sections are not filed as transitions (T013, 2026-09-30)."""

from pb_studio.brain.feature_adapter import _canonical_segment


def test_neutral_section_stays_section():
    assert _canonical_segment("section") == "section"


def test_semantic_labels_unchanged():
    assert _canonical_segment("breakdown") == "break"
    assert _canonical_segment("buildup") == "build"
    assert _canonical_segment("bridge") == "transition"
    assert _canonical_segment(None) == "transition"
    assert _canonical_segment("peak") == "transition"
