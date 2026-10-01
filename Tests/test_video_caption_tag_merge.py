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


def test_single_frame_keeps_order():
    assert _merge_frame_tags([["x", "y", "z"]]) == ["x", "y", "z"]


def test_comma_list_with_one_long_item_keeps_multiword_tags():
    out = w._parse_tags(
        "fuenf frauen, traditionelle kleidung, tanzend, "
        "schattenfiguren mit hoernern im dichten nebel, wald."
    )
    assert "traditionelle kleidung" in out and "fuenf frauen" in out
    assert "kleidung" not in out


def test_prompt_asks_for_figures_without_feature_bait():
    assert "Personen oder Wesen" in w.DEFAULT_PROMPT
    assert "Fluegel" not in w.DEFAULT_PROMPT
