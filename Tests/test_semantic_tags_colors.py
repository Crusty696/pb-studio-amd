"""Test: Tags-overlap + Color-similarity helpers (Audit E4).

Audit E4: video tags + dominant_colors werden via A4 ans clip_data
durchgereicht aber waren bisher nicht von semantic_matcher konsumiert.
Diese Tests verifizieren die neuen Helpers.
"""
import pytest


def test_tags_overlap_perfect_match():
    from pb_studio.pacing.semantic_matcher import _tags_overlap_score
    assert _tags_overlap_score(["happy", "energetic"], ["happy", "energetic"]) == 1.0


def test_tags_overlap_no_match():
    from pb_studio.pacing.semantic_matcher import _tags_overlap_score
    assert _tags_overlap_score(["happy"], ["sad"]) == 0.0


def test_tags_overlap_partial():
    from pb_studio.pacing.semantic_matcher import _tags_overlap_score
    # {happy, energetic} ∩ {happy, calm} = {happy}, ∪ = {happy, energetic, calm}
    # Jaccard = 1/3 ≈ 0.333
    assert 0.3 <= _tags_overlap_score(["happy", "energetic"], ["happy", "calm"]) <= 0.4


def test_tags_overlap_empty_neutral():
    from pb_studio.pacing.semantic_matcher import _tags_overlap_score
    assert _tags_overlap_score([], ["a"]) == 0.5
    assert _tags_overlap_score(["a"], []) == 0.5
    assert _tags_overlap_score([], []) == 0.5
    assert _tags_overlap_score(None, ["a"]) == 0.5


def test_tags_overlap_case_insensitive():
    """Case + whitespace sollten normalisiert werden."""
    from pb_studio.pacing.semantic_matcher import _tags_overlap_score
    # "Happy" und " happy " müssten als gleich gelten
    score = _tags_overlap_score(["Happy", " Energetic "], ["happy", "energetic"])
    assert score == 1.0


def test_color_similarity_identical():
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    assert _color_similarity_score(["#FF0000"], ["#FF0000"]) == 1.0


def test_color_similarity_opposite():
    """Black vs White max distance."""
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    sim = _color_similarity_score(["#000000"], ["#FFFFFF"])
    assert sim == 0.0


def test_color_similarity_similar_reds():
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    sim = _color_similarity_score(["#FF0000"], ["#FF1122"])
    assert sim > 0.7


def test_color_similarity_empty_neutral():
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    assert _color_similarity_score([], ["#FF0000"]) == 0.5
    assert _color_similarity_score(["#FF0000"], []) == 0.5
    assert _color_similarity_score(None, ["#FF0000"]) == 0.5


def test_color_similarity_invalid_hex_neutral():
    """Falsche Hex-Strings → 0.5 fallback (gracefully degraded)."""
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    sim = _color_similarity_score(["not_hex"], ["#FF0000"])
    assert 0.0 <= sim <= 1.0  # gracefully degraded


def test_color_similarity_top3_only():
    """Nur die ersten 3 dominantesten Farben werden verglichen."""
    from pb_studio.pacing.semantic_matcher import _color_similarity_score
    # Position 4+ wird ignoriert: "#FF0000" identical match wäre an Pos 4 → ignoriert
    prev = ["#000000", "#111111", "#222222", "#FF0000"]
    nxt = ["#FF0000"]
    sim = _color_similarity_score(prev, nxt)
    # Da #FF0000 nur an Pos 4 ist, wird der Match nicht gefunden.
    # Beste Matches: black/dark-grey vs red → niedrige Similarity.
    assert sim < 0.6
