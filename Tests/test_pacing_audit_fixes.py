"""Regressions for spec 00029: verified Pacing/Director audit findings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.routers.pacing_router import _collect_runtime_degradations
from backend.routers.render_router import _finalize_timeline_for_render
from backend.schemas.pacing_schemas import PacingConfigSchema
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.clip_selector import ClipSelector
from pb_studio.pacing.pacing_models import CutListEntry, PacingCut
from pb_studio.services.pacing_service import PacingService


def _source_cut(start: float, end: float, source_duration: float) -> CutListEntry:
    return CutListEntry(
        clip_id="clip_1",
        start_time=start,
        end_time=end,
        metadata={
            "file_path": r"C:\media\short.mp4",
            "clip_start": 0.0,
            "source_duration": source_duration,
        },
    )


def test_finalizer_reuses_short_source_without_outpoint_overflow() -> None:
    cuts = [_source_cut(0.0, 2.0, 2.0)]

    finalized = PacingService()._finalize_cut_list(cuts, 12.0)

    assert finalized[0].start_time == pytest.approx(0.0)
    assert finalized[-1].end_time == pytest.approx(12.0)
    assert all(
        float(cut.metadata["clip_start"]) + cut.end_time - cut.start_time
        <= float(cut.metadata["source_duration"]) + 1e-6
        for cut in finalized
    )
    assert all(
        left.end_time == pytest.approx(right.start_time)
        for left, right in zip(finalized, finalized[1:])
    )


def test_render_finalizer_preserves_appended_source_safe_segments() -> None:
    timeline = [{
        "clip_id": "clip_1",
        "start_time": 0.0,
        "end_time": 2.0,
        "metadata": {
            "file_path": r"C:\media\short.mp4",
            "clip_start": 0.0,
            "source_duration": 2.0,
        },
    }]

    finalized = _finalize_timeline_for_render(timeline, 6.0)

    assert len(finalized) == 3
    assert finalized[-1]["end_time"] == pytest.approx(6.0)


def test_expected_bpm_changes_active_beat_grid() -> None:
    engine = AdvancedPacingEngine(trigger_settings={"beat_weight": 1.0})
    measured = [0.0, 0.5, 1.0, 1.5, 2.0]

    slow, _ = engine._apply_expected_bpm_grid(
        measured, [], expected_bpm=60.0, detected_bpm=120.0, duration=2.0
    )
    fast, _ = engine._apply_expected_bpm_grid(
        measured, [], expected_bpm=180.0, detected_bpm=120.0, duration=2.0
    )

    assert slow != fast
    assert slow == pytest.approx([0.0, 1.0, 2.0])
    assert len(fast) > len(slow)


def test_expected_bpm_near_detected_preserves_measured_grid() -> None:
    engine = AdvancedPacingEngine(trigger_settings={"beat_weight": 1.0})
    beats = [0.03, 0.51, 1.01, 1.49]
    downbeats = [0.03]

    corrected, corrected_downbeats = engine._apply_expected_bpm_grid(
        beats, downbeats, expected_bpm=121.0, detected_bpm=120.0, duration=2.0
    )

    assert corrected == beats
    assert corrected_downbeats == downbeats


@pytest.mark.parametrize(
    "trigger_settings_data,top_min",
    [
        ({"min_cut_interval": 5.0, "max_cut_interval": 1.0}, 0.5),
        ({"max_clip_length": 2.0, "max_cut_interval": 2.0}, 5.0),
    ],
)
def test_schema_rejects_contradictory_interval_constraints(
    trigger_settings_data: dict,
    top_min: float,
) -> None:
    with pytest.raises(ValidationError):
        PacingConfigSchema(
            audio_clip_id=1,
            trigger_settings=trigger_settings_data,
            min_cut_interval=top_min,
        )


def test_engine_uses_same_effective_minimum_for_auto_splits() -> None:
    engine = AdvancedPacingEngine(trigger_settings={
        "min_clip_length": 1.0,
        "min_cut_interval": 5.0,
        "max_clip_length": 8.0,
        "max_cut_interval": 8.0,
    })
    effective_min, effective_max = engine._effective_cut_intervals(0.5)
    cuts = engine._enforce_clip_lengths(
        [PacingCut(0.0), PacingCut(20.0)],
        min_length=effective_min,
        max_length=effective_max,
        audio_duration=20.0,
    )

    assert all(
        right.time - left.time >= effective_min - 1e-6
        for left, right in zip(cuts, cuts[1:])
    )


def test_runtime_degradations_are_compact_and_mode_specific() -> None:
    cuts = [
        {"metadata": {"selection_provenance": {
            "fallback_reason": "semantic_query_embedding_unavailable"
        }}},
        {"metadata": {"selection_provenance": {
            "fallback_reason": "brain_error:RuntimeError"
        }, "semantic_status": "partial"}},
        {"metadata": {"trigger_type": "manual_anchor"}},
    ]

    degradations = _collect_runtime_degradations(
        cuts,
        use_semantic_matching=True,
        use_brain=True,
    )

    assert [item.mode for item in degradations] == [
        "semantic_matching", "brain_reranking"
    ]
    assert degradations[0].scored_clips == 0
    assert degradations[0].total_clips == 2
    assert degradations[1].scored_clips == 1
    assert degradations[1].total_clips == 2


def test_brain_requested_but_unavailable_is_recorded() -> None:
    selector = ClipSelector(strategy="round_robin")
    selector.brain_requested = True

    selected = selector.select_clip([
        {"id": "1", "file_path": "one.mp4", "motion_score": 0.5}
    ])

    provenance = selected.metadata["selection_provenance"]
    assert provenance["fallback_reason"] == "brain_unavailable"


def test_director_formats_each_runtime_degradation_with_own_counts() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "PBStudio.UI" / "ViewModels" / "DirectorViewModel.cs"
    ).read_text(encoding="utf-8")

    assert '"semantic_matching" => "Semantik-Matching"' in source
    assert '"brain_reranking" => "Brain-Auswahl"' in source
    assert "d.ScoredClips" in source
    assert "d.TotalClips" in source
