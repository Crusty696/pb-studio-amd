from __future__ import annotations

import json

from backend.app_state import AppState
from pb_studio.core.stage_receipts import (
    create_stage_receipt,
    receipt_to_dict,
    transition_stage_receipt,
)


def _completed_receipt(stage: str, artifact: dict) -> dict:
    receipt = create_stage_receipt(
        stage,
        requested=True,
        input_identity={"media": "video-sha"},
        config_identity={"stage": stage},
    )
    receipt = transition_stage_receipt(receipt, "running")
    return receipt_to_dict(
        transition_stage_receipt(
            receipt,
            "completed",
            artifact_ref=f"ai_data_json.stage_artifacts.{stage}",
            artifact=artifact,
        )
    )


def test_load_from_db_restores_full_partial_video_truth(monkeypatch, tmp_path):
    video_path = tmp_path / "partial.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftyp")
    scenes_artifact = {
        "scene_count": 1,
        "scenes": [{"start": 0.0, "end": 1.0}],
    }
    captions_artifact = {
        "tags": ["neon", "club"],
        "tag_source": "lmstudio:qwen-vl",
    }
    stage_artifacts = {
        "scenes": scenes_artifact,
        "captions": captions_artifact,
    }
    stage_receipts = {
        "scenes": _completed_receipt("scenes", scenes_artifact),
        "captions": _completed_receipt("captions", captions_artifact),
    }
    ai_data = {
        "analysis_status": "partial",
        "is_analyzed": False,
        "stage_status": {"scenes": "completed", "captions": "completed", "motion": "failed"},
        "stage_errors": {"motion": "raft unavailable"},
        "stage_receipts": stage_receipts,
        "stage_artifacts": stage_artifacts,
        "scene_count": 1,
        "scenes": scenes_artifact["scenes"],
        "avg_motion": 0.2,
        "motion": {"motion_curve": [0.2]},
        "has_embedding": True,
        "embedding_dim": 1152,
        "embedding_samples": 2,
        "dominant_colors": [[10, 20, 30]],
        "tags": ["neon", "club"],
        "tag_source": "lmstudio:qwen-vl",
        "audio_key": "Am",
        "avg_brightness": 0.3,
        "avg_saturation": 0.8,
        "avg_color_temp": -0.1,
        "mood_tags": ["dark"],
        "media_sha256": "a" * 64,
    }
    row = {
        "id": 71,
        "project_id": 42,
        "file_path": str(video_path),
        "file_hash": "video-sha",
        "duration_sec": 10.0,
        "metadata_json": json.dumps({
            "clip_type": "video",
            "clip_id": 7,
            "name": "partial.mp4",
            "video_hash": "video-sha",
        }),
        "ai_data_json": json.dumps(ai_data),
    }

    class FakeRepo:
        db = None

        def recover_analysis_receipts(self, project_id):
            assert project_id == 42
            return 0

        def get_by_project(self, project_id):
            assert project_id == 42
            return [row]

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )
    state = AppState(current_project={"db_project_id": 42, "path": str(tmp_path)})

    assert state.load_from_db() is True

    clip = state.video_clips[7]
    cached = state.video_analysis_cache[7]
    assert clip["tags"] == ["neon", "club"]
    assert clip["tag_source"] == "lmstudio:qwen-vl"
    assert clip["analysis_status"] == "partial"
    assert clip["stage_receipts"] == stage_receipts
    assert cached["analysis_status"] == "partial"
    assert cached["stage_receipts"] == stage_receipts
    assert cached["stage_artifacts"] == stage_artifacts
    assert cached["scenes"] == scenes_artifact["scenes"]
    assert cached["tags"] == ["neon", "club"]


def test_load_from_db_failure_preserves_complete_old_generation(monkeypatch, tmp_path):
    bad_path = tmp_path / "bad.mp4"
    bad_path.write_bytes(b"\x00\x00\x00\x18ftyp")

    class FakeRepo:
        db = None

        def recover_analysis_receipts(self, project_id):
            return 0

        def get_by_project(self, project_id):
            return [{
                "id": 1,
                "project_id": project_id + 1,
                "file_path": str(bad_path),
                "metadata_json": json.dumps({
                    "clip_type": "video",
                    "clip_id": 1,
                    "name": "bad.mp4",
                }),
                "ai_data_json": "{}",
            }]

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )
    state = AppState(
        current_project={"db_project_id": 8, "path": str(tmp_path)},
        audio_clips={9: {"id": 9, "name": "old"}},
        audio_analysis_cache={9: {"bpm": 123.0}},
        video_clips={10: {"id": 10, "name": "old-video"}},
        video_analysis_cache={10: {"analysis_status": "completed"}},
    )
    state._audio_next_id = 20
    state._video_next_id = 30

    assert state.load_from_db() is False
    assert state.audio_clips == {9: {"id": 9, "name": "old"}}
    assert state.audio_analysis_cache == {9: {"bpm": 123.0}}
    assert state.video_clips == {10: {"id": 10, "name": "old-video"}}
    assert state.video_analysis_cache == {10: {"analysis_status": "completed"}}
    assert state._audio_next_id == 20
    assert state._video_next_id == 30


def test_load_from_db_never_publishes_quarantined_caption_payload(monkeypatch, tmp_path):
    video_path = tmp_path / "quarantined.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftyp")
    ai_data = {
        "analysis_status": "partial",
        "is_analyzed": False,
        "stage_status": {"scenes": "completed", "captions": "failed"},
        "stage_errors": {"captions": "artifact invalid"},
        "stage_receipts": {},
        "stage_artifacts": {
            "scenes": {"scene_count": 1, "scenes": [{"start": 0.0, "end": 1.0}]},
        },
        "scene_count": 1,
        "scenes": [{"start": 0.0, "end": 1.0}],
    }
    row = {
        "id": 88,
        "project_id": 5,
        "file_path": str(video_path),
        "file_hash": "video-sha",
        "duration_sec": 2.0,
        "metadata_json": json.dumps({
            "clip_type": "video",
            "clip_id": 8,
            "name": "quarantined.mp4",
        }),
        "ai_data_json": json.dumps(ai_data),
    }

    class FakeRepo:
        db = None

        def recover_analysis_receipts(self, project_id):
            return 1

        def get_by_project(self, project_id):
            return [row]

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )
    state = AppState(current_project={"db_project_id": 5, "path": str(tmp_path)})

    assert state.load_from_db() is True
    assert state.video_clips[8]["tags"] == []
    assert state.video_clips[8]["tag_source"] == "none"
    assert state.video_analysis_cache[8]["tags"] == []
    assert state.video_analysis_cache[8]["tag_source"] == "none"
    assert state.video_analysis_cache[8]["scene_count"] == 1
    assert state.video_analysis_cache[8]["scenes"] == [{"start": 0.0, "end": 1.0}]
