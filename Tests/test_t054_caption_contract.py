"""T054: preserve requested caption detail without weakening safety filters.

The V05 response below is the actual first T053 response. It is a parser
fixture, not an assertion that every model-generated tag is visually correct.
"""

import pytest

from pb_studio.video.lmstudio_vision_wrapper import _parse_tags


V05_FIRST_RESPONSE = (
    "Gruppe, Mensch, dunkle Kleidung, steht, Gewitterhimmel, dramatisch, "
    "blau, dunkel, stürmisch, Naturereignis, Blitzschlag"
)
TWELVE_VALID_TAGS = [
    "steinmauer", "tor", "ranken", "dschungel", "violett", "licht",
    "wasser", "nebel", "felsen", "wolken", "blitzschlag", "spiegelungen",
]


def test_t053_v05_observed_eleventh_tag_is_not_silently_lost():
    tags = _parse_tags(V05_FIRST_RESPONSE)
    assert "blitzschlag" in tags
    assert len(tags) == 11


def test_default_preserves_all_twelve_requested_valid_tags():
    assert _parse_tags(", ".join(TWELVE_VALID_TAGS)) == TWELVE_VALID_TAGS


@pytest.mark.parametrize("limit", [1, 5, 10, 11, 12])
def test_explicit_positive_limit_remains_enforced(limit):
    assert _parse_tags(", ".join(TWELVE_VALID_TAGS), max_tags=limit) == (
        TWELVE_VALID_TAGS[:limit]
    )


def test_filtering_does_not_spend_capacity_or_remove_late_scene_details():
    raw = ", ".join([
        "helle haut", "sechs figuren", "gruppe von figuren", "vier figuren",
        "steinmauer", "tor", "ranken", "dschungel", "violett", "licht",
        "wasser", "nebel", "felsen", "blitzschlag", "spiegelungen",
    ])
    assert _parse_tags(raw) == [
        "gruppe von figuren", "steinmauer", "tor", "ranken", "dschungel",
        "violett", "licht", "wasser", "nebel", "felsen", "blitzschlag",
        "spiegelungen",
    ]


def test_repetition_guard_keeps_two_variants_and_late_concrete_tags():
    assert _parse_tags(
        "mystisch, mystische, mystisches, mystischen, steinmauer, blitzschlag"
    ) == ["mystisch", "mystische", "steinmauer", "blitzschlag"]


@pytest.mark.parametrize("raw", [
    "Sorry, I cannot analyze this image.",
    "Error: no image was provided.",
    "keine tags",
])
def test_failed_caption_does_not_become_tags(raw):
    assert _parse_tags(raw) == []


@pytest.mark.parametrize("raw", [
    "dunkle haut", "helle haut", "olivfarbene haut",
    "dunkle haut, helle haut", "Tags: dunkle haut, gebräunte haut",
])
def test_filtered_skin_tone_phrases_cannot_return_as_fallback_words(raw):
    assert _parse_tags(raw) == []


def test_skin_filter_preserves_non_tone_visible_description():
    assert _parse_tags("tätowierte haut") == ["tätowierte haut"]


def test_frame_merge_preserves_twelfth_detail():
    from backend.routers.video_router import _merge_frame_tags

    assert _merge_frame_tags([TWELVE_VALID_TAGS]) == TWELVE_VALID_TAGS


def test_frame_merge_explicit_limit_still_enforced():
    from backend.routers.video_router import _merge_frame_tags

    assert _merge_frame_tags([TWELVE_VALID_TAGS], limit=10) == TWELVE_VALID_TAGS[:10]


def test_v05_lightning_survives_parser_and_frame_merge():
    from backend.routers.video_router import _merge_frame_tags

    assert "blitzschlag" in _merge_frame_tags([_parse_tags(V05_FIRST_RESPONSE)])


@pytest.mark.parametrize("raw", ["5 menschen", "Menschen (5)"])
def test_numeric_person_count_above_three_is_generalized(raw):
    assert _parse_tags(raw) == ["gruppe von menschen"]


def test_non_person_count_is_not_generalized():
    assert _parse_tags("vier saeulen") == ["vier saeulen"]


def test_skin_tone_phrases_with_sentence_punctuation_stay_filtered():
    assert _parse_tags("Dunkle Haut, helle Haut.") == []


@pytest.mark.parametrize("raw, expected", [
    ("2 menschen", ["2 menschen"]),
    ("5 saeulen", ["5 saeulen"]),
    ("1. wald", ["wald"]),
    ("Dunkle Haut, Wasserfall.", ["wasserfall"]),
])
def test_count_bullets_and_safe_clause_survive_filtering(raw, expected):
    assert _parse_tags(raw) == expected


def test_numbered_list_without_spacing_does_not_keep_list_indices():
    assert _parse_tags("1.frau, 2.wald") == ["frau", "wald"]


def test_prefixed_single_prose_response_retains_content_keywords():
    tags = _parse_tags("Tags: Eine Frau steht im Wald und schaut nach oben.")
    assert "frau" in tags
    assert "wald" in tags
    assert "eine" not in tags
    assert "und" not in tags
