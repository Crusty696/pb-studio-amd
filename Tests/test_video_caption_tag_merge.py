"""Caption tags from all sampled frames reach the clip (T013, 2026-09-30).

First-come order let frame 1 fill all ten slots; frames 2 and 3 were
captioned and then discarded.
"""

from backend.routers.video_router import _merge_frame_tags
from pb_studio.video import lmstudio_vision_wrapper as w


def test_later_frames_contribute():
    f1 = [f"a{i}" for i in range(10)]
    f2 = ["taenzerinnen"] + [f"b{i}" for i in range(9)]
    f3 = ["feuer"] + [f"c{i}" for i in range(9)]
    merged = _merge_frame_tags([f1, f2, f3])
    assert "taenzerinnen" in merged and "feuer" in merged
    assert len(merged) == 10


def test_tags_seen_in_several_frames_rank_first():
    merged = _merge_frame_tags([["wald", "nebel"], ["frau", "wald"], ["wald", "frau"]])
    assert merged[:2] == ["wald", "frau"]


def test_near_duplicates_collapse_to_most_specific():
    merged = _merge_frame_tags([
        ["frau in weißem kleid", "nebel", "dunkle kleidung"],
        ["frau in weißem gewand", "steinerner kreis mit runen", "dunkle kleidung mit hörnern"],
        ["steinerne kreise mit runen", "frau", "wald"],
    ])
    assert sum(t.startswith("frau in weißem") for t in merged) == 1
    assert sum("runen" in t for t in merged) == 1
    assert "dunkle kleidung mit hörnern" in merged and "dunkle kleidung" not in merged
    assert "frau" in merged and "nebel" in merged and "wald" in merged


def test_different_tags_with_shared_word_stay():
    merged = _merge_frame_tags([["dunkle kleidung", "dunkle farben", "dunkler wald"]])
    assert merged == ["dunkle kleidung", "dunkle farben", "dunkler wald"]


def test_word_order_variants_collapse():
    # Live 2026-09-30 (qwen3.5-9b): 'arme ausgestreckt' and 'ausgestreckte arme'
    # both reached the clip.
    merged = _merge_frame_tags([
        ["arme ausgestreckt", "nebel"],
        ["ausgestreckte arme", "wald"],
    ])
    assert sum("arme" in t for t in merged) == 1
    assert "nebel" in merged and "wald" in merged


# Real per-frame lists from the T014 re-run 2026-10-01 (qwen3.5-9b, project 10).

def test_negation_only_survives_if_every_frame_agrees():
    # clip 954: frame 1 empty grotto, frames 2+3 show a person
    merged = _merge_frame_tags([
        ["keine personen", "mystische grotte", "wasserfall im hintergrund"],
        ["person", "zwei beine", "barfuß"],
        ["person mit federkronenkleidung", "stehend am wasser"],
    ])
    assert "keine personen" not in merged
    assert "mystische grotte" in merged
    # a negation all frames agree on is a fact about the clip
    assert "keine personen" in _merge_frame_tags([["keine personen", "wald"], ["keine personen"]])


def test_conflicting_counts_collapse_to_one_tag():
    # clip 924: frame-dependent head counts both reached the clip
    merged = _merge_frame_tags([
        ["hornträgerin", "elfenohren"],
        ["vier frauen mit hörnern", "tanzende pose"],
        ["drei horntragende frauen", "nebliger wald"],
    ])
    assert sum(t.startswith(("vier ", "drei ")) for t in merged) == 1


def test_english_tags_dropped_when_german_ones_exist():
    # clip 949: frames 2 and 3 came back in English
    merged = _merge_frame_tags([
        ["leuchtende pflanzen", "große blätter", "nächtliche landschaft"],
        ["glowing green leaves", "distant city lights", "night scene"],
        ["glowing plants", "purple sky", "night garden"],
    ])
    assert merged == ["leuchtende pflanzen", "große blätter", "nächtliche landschaft"]
    # an all-English answer is kept rather than leaving the clip without tags
    assert _merge_frame_tags([["glowing plants", "night garden"]]) == ["glowing plants", "night garden"]


def test_article_and_generic_person_variants_collapse():
    # clip 964: one woman, four tags
    merged = _merge_frame_tags([
        ["eine frau", "barfuß", "leuchtende pilze"],
        ["frau", "person", "leuchtende pilze"],
        ["frau", "silhouette", "barfuß"],
    ])
    assert sum(t in ("frau", "eine frau") for t in merged) == 1
    assert "person" not in merged
    assert "silhouette" in merged


def test_single_words_sharing_a_stem_stay_separate():
    # 5-letter stems must not merge different single words.
    assert _merge_frame_tags([["wasser", "wasserfall", "blume", "blumenwiese"]]) == [
        "wasser", "wasserfall", "blume", "blumenwiese",
    ]


def test_skin_tone_tags_are_never_kept():
    # David 2026-10-01: guessed under coloured light / backlight (969, 974, 935, 927)
    out = w._parse_tags(
        "eine frau, dunkle haut, schwarze haut, helle Haut, dunkelhäutige frau, "
        "hautfarbe hell, tätowierte haut, schwarze bikini-top, mystischer wald"
    )
    assert out == ["eine frau", "tätowierte haut", "schwarze bikini-top", "mystischer wald"]


def test_counts_above_three_become_group():
    out = w._parse_tags("vier figuren, drei frauen, sechs tänzerinnen im kreis, vier säulen")
    assert out == [
        "gruppe von figuren", "drei frauen", "gruppe von tänzerinnen im kreis", "vier säulen",
    ]
    # the merge still collapses frame-dependent counts of one subject
    merged = _merge_frame_tags([["gruppe von frauen mit hörnern"], ["drei horntragende frauen"]])
    assert len(merged) == 1


def test_prompt_asks_not_to_describe_skin_tone():
    assert "Keine Hautfarbe" in w.DEFAULT_PROMPT
    assert "gruppe" in w.DEFAULT_PROMPT


def test_single_frame_keeps_order():
    assert _merge_frame_tags([["x", "y", "z"]]) == ["x", "y", "z"]


def test_comma_list_with_one_long_item_keeps_multiword_tags():
    out = w._parse_tags(
        "fuenf frauen, traditionelle kleidung, tanzend, "
        "schattenfiguren mit hoernern im dichten nebel, wald."
    )
    # 'fuenf frauen' -> 'gruppe von frauen' since 2026-10-01 (counts above three)
    assert "traditionelle kleidung" in out and "gruppe von frauen" in out
    assert "kleidung" not in out


def test_prompt_asks_for_figures_without_feature_bait():
    assert "Personen oder Wesen" in w.DEFAULT_PROMPT
    assert "Fluegel" not in w.DEFAULT_PROMPT
