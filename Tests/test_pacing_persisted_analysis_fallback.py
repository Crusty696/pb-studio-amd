from __future__ import annotations

import json
import importlib
from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from backend.schemas.pacing_schemas import PacingConfigSchema
from pb_studio.core.stage_receipts import (
    create_stage_receipt,
    receipt_to_dict,
    transition_stage_receipt,
)

pacing_router = importlib.import_module("backend.routers.pacing_router")


def _completed_receipt(stage: str, artifact: dict) -> dict:
    receipt = create_stage_receipt(
        stage,
        requested=True,
        input_identity={"project": 42, "media": "video-sha"},
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


def _persisted_motion_payload() -> dict:
    motion_artifact = {
        "avg_motion": 0.7,
        "motion": {
            "avg_motion": 0.7,
            "peak_motion": 0.9,
            "motion_curve": [0.2, 0.7],
        },
    }
    return {
        "analysis_status": "partial",
        "is_analyzed": False,
        "stage_status": {"motion": "completed", "captions": "failed"},
        "stage_errors": {"captions": "caption provider unavailable"},
        "stage_receipts": {
            "motion": _completed_receipt("motion", motion_artifact),
        },
        "stage_artifacts": {"motion": motion_artifact},
        **motion_artifact,
        # These fields have no completed V1 receipt and must never leak into Pacing.
        "tags": ["stale-tag"],
        "tag_source": "stale-provider",
        "has_embedding": True,
        "embedding_dim": 1152,
        "embedding_samples": 4,
    }


@dataclass(frozen=True)
class _Context:
    project_id: int = 42


class _State:
    def __init__(self, snapshot: dict[int, dict] | None = None):
        self.snapshot = snapshot or {}
        self.context_checks = 0

    def get_video_analysis_snapshot(self):
        return dict(self.snapshot)

    def require_project_context_current(self, context):
        assert context.project_id == 42
        self.context_checks += 1


def _motion_config() -> PacingConfigSchema:
    return PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        use_motion_matching=True,
    )


def _valid_audio() -> dict:
    return {
        "bpm": 120.0,
        "beat_count": 1,
        "beats": [0.0],
        "energy_curve": [0.5],
        "downbeats": [0.0],
        "onset_times": [],
        "kick_times": [],
        "snare_times": [],
        "hihat_times": [],
        "downbeat_provenance": {"status": "measured"},
        "stage_status": {"beats": "completed"},
    }


def _row(payload: dict, *, project_id: int = 42, clip_id: int = 10) -> dict:
    return {
        "id": 700,
        "project_id": project_id,
        "file_path": r"C:\media\clip10.mp4",
        "metadata_json": json.dumps({
            "clip_type": "video",
            "clip_id": clip_id,
            "name": "clip10.mp4",
        }),
        "ai_data_json": json.dumps(payload),
    }


def test_project_bound_ram_snapshot_wins_without_sqlite_access(monkeypatch):
    cached = {
        "stage_status": {"motion": "completed"},
        "motion": {"motion_curve": [0.4]},
    }
    state = _State({10: cached})

    class RepositoryMustNotBeConstructed:
        def __init__(self):
            raise AssertionError("SQLite fallback used despite project RAM truth")

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        RepositoryMustNotBeConstructed,
    )

    resolved = pacing_router._resolve_pacing_video_analysis(
        _motion_config(),
        state,
        _Context(),
        {10: {"id": 10, "path": r"C:\media\clip10.mp4"}},
    )

    assert resolved == {10: cached}


def test_sqlite_fallback_is_project_media_bound_and_matches_restart_truth(monkeypatch):
    payload = _persisted_motion_payload()
    calls: list[tuple[int, str]] = []

    class FakeRepository:
        def find_by_project_and_path(self, project_id, file_path):
            calls.append((project_id, file_path))
            return _row(payload)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepository,
    )
    state = _State()
    clips = {10: {"id": 10, "path": r"C:\media\clip10.mp4"}}

    resolved = pacing_router._resolve_pacing_video_analysis(
        _motion_config(), state, _Context(), clips
    )

    assert calls == [(42, r"C:\media\clip10.mp4")]
    assert state.context_checks == 2
    assert resolved[10]["motion"] == payload["motion"]
    assert resolved[10]["avg_motion"] == 0.7
    assert "tags" not in resolved[10]
    assert "has_embedding" not in resolved[10]
    pacing_router._validate_pacing_analysis_preflight(
        _motion_config(), _valid_audio(), resolved
    )


def test_sqlite_fallback_rejects_project_or_clip_identity_mismatch(monkeypatch):
    payload = _persisted_motion_payload()

    class WrongProjectRepository:
        def find_by_project_and_path(self, project_id, file_path):
            return _row(payload, project_id=project_id + 1, clip_id=99)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        WrongProjectRepository,
    )

    resolved = pacing_router._resolve_pacing_video_analysis(
        _motion_config(),
        _State(),
        _Context(),
        {10: {"id": 10, "path": r"C:\media\clip10.mp4"}},
    )

    assert "motion" not in resolved[10]
    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(
            _motion_config(), _valid_audio(), resolved
        )
    missing = caught.value.detail["missing"]["video"][0]["stages"][0]
    assert missing["status"] == "unavailable"
    assert missing["reason"] == "persisted_project_media_mismatch"


def test_sqlite_fallback_rejects_corrupted_referenced_artifact(monkeypatch):
    payload = _persisted_motion_payload()
    payload["stage_artifacts"]["motion"]["motion"]["motion_curve"] = [999.0]

    class CorruptRepository:
        def find_by_project_and_path(self, project_id, file_path):
            return _row(payload)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        CorruptRepository,
    )

    resolved = pacing_router._resolve_pacing_video_analysis(
        _motion_config(),
        _State(),
        _Context(),
        {10: {"id": 10, "path": r"C:\media\clip10.mp4"}},
    )

    assert "motion" not in resolved[10]
    assert "tags" not in resolved[10]
    assert "has_embedding" not in resolved[10]
    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(
            _motion_config(), _valid_audio(), resolved
        )
    missing = caught.value.detail["missing"]["video"][0]["stages"][0]
    assert missing["status"] == "failed"
    assert missing["reason"] == "persisted_receipt_or_artifact_invalid"
