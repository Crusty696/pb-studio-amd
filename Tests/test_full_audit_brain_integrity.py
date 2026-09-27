"""Regressions for full-audit Brain findings 47–49."""

from __future__ import annotations

import numpy as np
import pytest

from pb_studio.brain.post_processor import annotate_cuts_with_brain
from pb_studio.brain.projector_trainer import (
    ProjectTrainingSource,
    collect_training_pairs,
    run_v2_fit_step,
)


class _Weights:
    def get_posterior_mean(self, axis, context_keys):
        return 1.0


def test_failed_analysis_stage_cannot_contribute_default_features():
    cuts = [{
        "clip_id": "clip_a",
        "start_time": 2.0,
        "end_time": 3.0,
        "metadata": {"trigger_type": "beat", "trigger_strength": 1.0,
                     "clip_start": 12.0},
    }]

    annotated = annotate_cuts_with_brain(
        cuts,
        weight_store=_Weights(),
        audio_analysis={"analysis_status": "failed", "is_analyzed": True,
                        "energy_curve": [1.0] * 20, "duration_seconds": 20.0},
        video_analysis_by_clip={"clip_a": {
            "analysis_status": "unavailable", "is_analyzed": True,
            "avg_motion": 1.0, "scenes": [{"time": 12.0}],
        }},
    )[0]

    meta = annotated["metadata"]
    assert "beat_weight" not in meta["bridge_values"]
    assert "motion_match_weight" not in meta["bridge_values"]
    assert meta["brain_axis_status"]["beat_weight"]["status"] == "unavailable"
    assert meta["brain_axis_status"]["scene_cut_weight"]["status"] == "unavailable"


def test_failed_individual_stages_cannot_reuse_stale_brain_features():
    cuts = [{
        "clip_id": "clip_a",
        "start_time": 2.0,
        "end_time": 3.0,
        "metadata": {"trigger_type": "beat", "trigger_strength": 1.0,
                     "clip_start": 12.0},
    }]
    annotated = annotate_cuts_with_brain(
        cuts,
        weight_store=_Weights(),
        audio_analysis={
            "analysis_status": "partial",
            "stage_status": {
                "beats": "failed", "spectral": "failed", "structure": "failed",
            },
            "is_analyzed": True,
            "duration_seconds": 20.0,
            "energy_curve": [1.0] * 20,
            "spectral_data": {"centroids": [500.0] * 20},
            "structure_segments": [{"start_time": 0.0, "end_time": 20.0,
                                    "label": "drop"}],
        },
        video_analysis_by_clip={"clip_a": {
            "analysis_status": "partial",
            "stage_status": {
                "motion": "failed", "scenes": "failed", "colors": "failed",
                "captions": "failed",
            },
            "is_analyzed": True,
            "avg_motion": 1.0,
            "scenes": [{"time": 12.0}],
            "avg_brightness": 0.9,
            "avg_color_temp": 0.8,
            "mood_tags": ["energetic"],
        }, "failed_clip": {
            "analysis_status": "partial",
            "stage_status": {"motion": "failed"},
            "avg_motion": 1e9,
            "motion_curve": [1e9],
        }},
    )[0]

    meta = annotated["metadata"]
    for axis in (
        "beat_weight", "energy_threshold", "onset_sensitivity",
        "motion_match_weight", "scene_cut_weight", "brightness_match_weight",
        "color_temp_match_weight", "pace_match_weight", "mood_match_weight",
    ):
        assert axis not in meta["bridge_values"], axis
        assert meta["brain_axis_status"][axis]["status"] == "unavailable", axis
    assert meta["segment_type"] == "transition"


def test_completed_individual_stages_remain_eligible_in_partial_analysis():
    cut = {
        "clip_id": "clip_a",
        "start_time": 2.0,
        "end_time": 3.0,
        "clip_start": 2.0,
        "metadata": {"trigger_type": "beat", "trigger_strength": 0.8},
    }
    annotated = annotate_cuts_with_brain(
        [cut],
        weight_store=_Weights(),
        audio_analysis={
            "analysis_status": "partial",
            "stage_status": {
                "beats": "completed", "spectral": "completed",
                "structure": "completed", "key": "failed",
            },
            "duration_seconds": 20.0,
            "energy_curve": [0.8] * 20,
            "spectral_data": {"centroids": [500.0] * 20},
            "structure_segments": [{"start_time": 0.0, "end_time": 20.0,
                                    "label": "drop"}],
            "mood_tags": ["energetic"],
        },
        video_analysis_by_clip={
            "clip_a": {
                "analysis_status": "partial",
                "stage_status": {
                    "motion": "completed", "scenes": "completed",
                    "colors": "completed", "captions": "completed",
                    "embedding": "failed",
                },
                "avg_motion": 1.0,
                "scenes": [{"time": 2.0}],
                "avg_brightness": 0.8,
                "avg_color_temp": 0.8,
                "mood_tags": ["energetic"],
            },
            "failed_clip": {
                "analysis_status": "partial",
                "stage_status": {"motion": "failed"},
                "avg_motion": 1e9,
                "motion_curve": [1e9],
            },
        },
    )[0]

    meta = annotated["metadata"]
    assert "beat_weight" in meta["bridge_values"]
    assert "energy_threshold" in meta["bridge_values"]
    assert "onset_sensitivity" in meta["bridge_values"]
    assert "motion_match_weight" in meta["bridge_values"]
    assert "scene_cut_weight" in meta["bridge_values"]
    assert "brightness_match_weight" in meta["bridge_values"]
    assert "color_temp_match_weight" in meta["bridge_values"]
    assert "pace_match_weight" in meta["bridge_values"]
    assert "mood_match_weight" in meta["bridge_values"]
    assert meta["segment_type"] == "drop"
    assert meta["feature_provenance"]["motion"]["scale"] == 1.0


def test_training_pair_producer_excludes_zero_norm_embeddings():
    class _Rows:
        def execute(self, _sql):
            return self

        def fetchall(self):
            return [("perfect", "clip_a", 7, "now")]

    pairs = collect_training_pairs(
        state_conn=_Rows(),
        embedding_cache=None,
        audio_hash_for_clip_id=lambda _clip: "audio-hash",
        video_hash_for_clip_id=lambda _clip: "video-hash",
        audio_load_fn=lambda _hash: np.zeros(4, dtype=np.float32),
        video_load_fn=lambda _hash: np.ones(4, dtype=np.float32),
    )

    assert pairs == []


@pytest.mark.parametrize("audio_vector", [
    np.zeros(4, dtype=np.float32),
    np.full(4, 1e-8, dtype=np.float32),
])
def test_v2_training_does_not_acknowledge_unusable_norm_event(
    monkeypatch, audio_vector,
):
    import sqlite3
    import uuid

    from pb_studio.brain.cross_modal_projector import CrossModalProjector
    import pb_studio.brain.post_processor as post_processor

    project_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    state = sqlite3.connect(":memory:")
    state.executescript(
        "CREATE TABLE feedback_events(event_uuid, project_uuid, rating, cut_id);"
        "CREATE TABLE timeline_cuts(id, timeline_id, clip_id);"
        "CREATE TABLE timelines(id, audio_clip_id);"
        "INSERT INTO timelines VALUES(1, 7);"
        "INSERT INTO timeline_cuts VALUES(3, 1, 'clip_a');"
    )
    state.execute(
        "INSERT INTO feedback_events VALUES(?, ?, 'perfect', 3)",
        (event_id, project_id),
    )
    monkeypatch.setattr(
        post_processor, "_load_audio_embedding",
        lambda *_args: audio_vector,
    )
    monkeypatch.setattr(
        post_processor, "_load_video_embedding",
        lambda *_args: np.ones(5, dtype=np.float32),
    )
    projector = CrossModalProjector(audio_dim=4, video_dim=5, common_dim=2)
    source = ProjectTrainingSource(
        project_uuid=project_id,
        state_conn=state,
        audio_hash_for_clip_id=lambda _clip: "audio",
        video_hash_for_clip_id=lambda _clip: "video",
    )

    result = run_v2_fit_step(
        projector,
        sources=[source],
        embedding_cache=None,
        publish_fn=lambda _candidate: pytest.fail("invalid event was published"),
    )

    assert result["n_pairs"] == 0
    assert result["new_events"] == 0
    assert result["applied_events"] == 0
    assert result["pending_events"] == 1
    assert result["saved"] is False
    state.close()


def test_v2_training_does_not_publish_when_fit_rejects_prefiltered_pair(
    monkeypatch,
):
    import sqlite3
    import uuid

    from pb_studio.brain.cross_modal_projector import CrossModalProjector
    import pb_studio.brain.post_processor as post_processor

    project_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    state = sqlite3.connect(":memory:")
    state.executescript(
        "CREATE TABLE feedback_events(event_uuid, project_uuid, rating, cut_id);"
        "CREATE TABLE timeline_cuts(id, timeline_id, clip_id);"
        "CREATE TABLE timelines(id, audio_clip_id);"
        "INSERT INTO timelines VALUES(1, 7);"
        "INSERT INTO timeline_cuts VALUES(3, 1, 'clip_a');"
    )
    state.execute(
        "INSERT INTO feedback_events VALUES(?, ?, 'perfect', 3)",
        (event_id, project_id),
    )
    monkeypatch.setattr(
        post_processor, "_load_audio_embedding",
        lambda *_args: np.ones(4, dtype=np.float32),
    )
    monkeypatch.setattr(
        post_processor, "_load_video_embedding",
        lambda *_args: np.ones(5, dtype=np.float32),
    )
    monkeypatch.setattr(
        CrossModalProjector,
        "fit_pairs",
        lambda *_args, **_kwargs: {
            "loss_before": 0.0, "loss_after": 0.0,
            "n_pairs": 0, "n_steps": 0,
        },
    )
    projector = CrossModalProjector(audio_dim=4, video_dim=5, common_dim=2)
    source = ProjectTrainingSource(
        project_uuid=project_id,
        state_conn=state,
        audio_hash_for_clip_id=lambda _clip: "audio",
        video_hash_for_clip_id=lambda _clip: "video",
    )

    result = run_v2_fit_step(
        projector,
        sources=[source],
        embedding_cache=None,
        publish_fn=lambda _candidate: pytest.fail(
            "projector must not publish when fit rejects accepted pairs"
        ),
    )

    assert result["n_pairs"] == 0
    assert result["new_events"] == 0
    assert result["applied_events"] == 0
    assert result["pending_events"] == 1
    assert result["saved"] is False
    state.close()


def test_annotation_uses_source_media_time_for_scene_provenance():
    cut = {
        "clip_id": "clip_a",
        "start_time": 2.0,
        "end_time": 3.0,
        "metadata": {"clip_start": 12.0},
    }
    annotated = annotate_cuts_with_brain(
        [cut],
        weight_store=_Weights(),
        video_analysis_by_clip={"clip_a": {
            "analysis_status": "completed",
            "scenes": [{"time": 12.0}],
        }},
    )[0]

    assert annotated["metadata"]["bridge_values"]["scene_cut_weight"] == 1.0
    assert annotated["metadata"]["feature_provenance"]["source_media_time"] == {
        "seconds": 12.0,
        "source": "cut.metadata.clip_start",
    }
