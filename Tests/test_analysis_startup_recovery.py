from __future__ import annotations

import json
from pathlib import Path

import pytest

from pb_studio.config_manager import ConfigManager
from pb_studio.core.stage_receipts import (
    create_stage_receipt,
    receipt_to_dict,
    transition_stage_receipt,
)
from pb_studio.data.database_core import DatabaseCore
from pb_studio.data.repositories.media_repository import MediaRepository


RECOVERED_AT = "2026-08-12T14:30:00Z"
PROJECT_UUID = "75efc170-823d-4874-962e-5e472becaf8f"


class _TempConfig:
    def __init__(self, db_path: Path):
        self._config = {"paths": {"db_path": str(db_path)}}

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def resolve_path(self, value: str) -> Path:
        return Path(value).resolve()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    db_path = tmp_path / "analysis-recovery.db"
    monkeypatch.setattr(
        ConfigManager,
        "_instance",
        _TempConfig(db_path),
        raising=False,
    )
    DatabaseCore._instance = None
    DatabaseCore._local = type(DatabaseCore._local)()
    DatabaseCore._all_connections = []
    repo = MediaRepository()
    yield repo
    repo.db.shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def _running_receipt(stage_id: str) -> dict:
    receipt = create_stage_receipt(
        stage_id,
        requested=True,
        input_identity={"media": stage_id},
        config_identity={"stage": stage_id},
    )
    return receipt_to_dict(
        transition_stage_receipt(
            receipt,
            "running",
            timestamp_utc="2026-08-12T14:00:00Z",
        )
    )


def _completed_receipt(stage_id: str, artifact_ref: str, artifact) -> dict:
    receipt = create_stage_receipt(
        stage_id,
        requested=True,
        input_identity={"media": stage_id},
        config_identity={"stage": stage_id},
    )
    receipt = transition_stage_receipt(
        receipt,
        "running",
        timestamp_utc="2026-08-12T14:00:00Z",
    )
    return receipt_to_dict(
        transition_stage_receipt(
            receipt,
            "completed",
            artifact_ref=artifact_ref,
            artifact=artifact,
            timestamp_utc="2026-08-12T14:10:00Z",
        )
    )


def _partial_receipt(stage_id: str, artifact_ref: str, artifact) -> dict:
    receipt = create_stage_receipt(
        stage_id,
        requested=True,
        input_identity={"media": stage_id},
        config_identity={"stage": stage_id},
    )
    receipt = transition_stage_receipt(
        receipt,
        "running",
        timestamp_utc="2026-08-12T14:00:00Z",
    )
    return receipt_to_dict(
        transition_stage_receipt(
            receipt,
            "partial",
            artifact_ref=artifact_ref,
            artifact=artifact,
            error_code="stage_partial",
            error_message=f"{stage_id} produced partial output",
            timestamp_utc="2026-08-12T14:10:00Z",
        )
    )


def _insert_media(
    repo: MediaRepository,
    project_id: int,
    path: Path,
    ai_data: dict,
    *,
    clip_id: int = 1,
) -> int:
    path.write_bytes(b"media")
    media_id = repo.add_media(
        project_id,
        str(path),
        "a" * 64,
        1.0,
        {
            "clip_type": "video" if path.suffix == ".mp4" else "audio",
            "clip_id": clip_id,
            "name": path.name,
        },
    )
    repo.update_status(media_id, "running", ai_data=ai_data)
    return media_id


def test_project_recovery_is_atomic_and_project_scoped(repository, tmp_path):
    conn = repository.db.get_connection()
    conn.execute(
        "INSERT INTO projects (id, name, project_uuid) VALUES (?, ?, ?)",
        (2, "Other", "c6c9198d-e763-4b45-b2f6-2be90be72815"),
    )
    conn.commit()

    project_one_id = _insert_media(
        repository,
        1,
        tmp_path / "one.wav",
        {
            "stage_receipts": {"beats": _running_receipt("beats")},
            "analysis_status": "running",
            "stage_status": {"beats": "running"},
            "stage_errors": {},
            "is_analyzed": False,
        },
    )
    project_two_id = _insert_media(
        repository,
        2,
        tmp_path / "two.wav",
        {
            "stage_receipts": {"beats": _running_receipt("beats")},
            "analysis_status": "running",
            "stage_status": {"beats": "running"},
            "stage_errors": {},
            "is_analyzed": False,
        },
    )

    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    changed_ids = repository.recover_project_analysis(
        1,
        recovered_at_utc=RECOVERED_AT,
    )
    conn.set_trace_callback(None)

    assert changed_ids == [project_one_id]
    assert any(statement == "BEGIN IMMEDIATE" for statement in statements)

    recovered = json.loads(
        conn.execute(
            "SELECT ai_data_json FROM media WHERE id = ?",
            (project_one_id,),
        ).fetchone()[0]
    )
    receipt = recovered["stage_receipts"]["beats"]
    assert receipt["status"] == "interrupted"
    assert receipt["finished_at_utc"] == RECOVERED_AT
    assert receipt["error_code"] == "startup_interrupted"
    assert receipt["error_message"] == "Analysis interrupted by backend restart"
    assert recovered["analysis_status"] == "failed"
    assert recovered["stage_status"] == {"beats": "interrupted"}
    assert recovered["stage_errors"] == {
        "beats": "Analysis interrupted by backend restart"
    }
    assert recovered["is_analyzed"] is False

    other = json.loads(
        conn.execute(
            "SELECT ai_data_json FROM media WHERE id = ?",
            (project_two_id,),
        ).fetchone()[0]
    )
    assert other["stage_receipts"]["beats"]["status"] == "running"


def test_recovery_demotes_invalid_completed_artifact_but_preserves_valid_and_unrequested(
    repository,
    tmp_path,
):
    valid_beats = [0.0, 0.5, 1.0]
    stale_key_receipt = _completed_receipt(
        "key",
        "ai_data_json.key",
        "D minor",
    )
    skipped = receipt_to_dict(create_stage_receipt("spectral", requested=False))
    media_id = _insert_media(
        repository,
        1,
        tmp_path / "truth.wav",
        {
            "beats_json": valid_beats,
            "key": "A major",
            "stage_receipts": {
                "beats": _completed_receipt(
                    "beats",
                    "ai_data_json.beats_json",
                    valid_beats,
                ),
                "key": stale_key_receipt,
                "spectral": skipped,
            },
            "analysis_status": "completed",
            "stage_status": {
                "beats": "completed",
                "key": "completed",
                "spectral": "skipped",
            },
            "stage_errors": {},
            "is_analyzed": True,
        },
    )

    changed_ids = repository.recover_project_analysis(
        1,
        recovered_at_utc=RECOVERED_AT,
    )
    recovered = json.loads(
        repository.db.get_connection()
        .execute("SELECT ai_data_json FROM media WHERE id = ?", (media_id,))
        .fetchone()[0]
    )

    assert changed_ids == [media_id]
    assert recovered["stage_receipts"]["beats"]["status"] == "completed"
    assert recovered["stage_receipts"]["spectral"] == skipped
    invalid = recovered["stage_receipts"]["key"]
    assert invalid["status"] == "failed"
    assert invalid["artifact_valid"] is False
    assert invalid["error_code"] == "artifact_invalid"
    assert invalid["finished_at_utc"] == RECOVERED_AT
    assert recovered["analysis_status"] == "partial"
    assert recovered["stage_status"]["key"] == "failed"
    assert "key" in recovered["stage_errors"]
    assert recovered["is_analyzed"] is False


def test_video_recovery_rejects_stage_artifact_that_disagrees_with_top_level_truth(
    repository,
    tmp_path,
):
    stage_artifact = {"scene_count": 1, "scenes": [{"start": 0.0, "end": 1.0}]}
    media_id = _insert_media(
        repository,
        1,
        tmp_path / "scene.mp4",
        {
            "scene_count": 2,
            "scenes": [
                {"start": 0.0, "end": 0.5},
                {"start": 0.5, "end": 1.0},
            ],
            "stage_artifacts": {"scenes": stage_artifact},
            "stage_receipts": {
                "scenes": _completed_receipt(
                    "scenes",
                    "ai_data_json.stage_artifacts.scenes",
                    stage_artifact,
                )
            },
            "analysis_status": "completed",
            "stage_status": {"scenes": "completed"},
            "stage_errors": {},
            "is_analyzed": True,
        },
    )

    repository.recover_project_analysis(1, recovered_at_utc=RECOVERED_AT)
    recovered = json.loads(
        repository.db.get_connection()
        .execute("SELECT ai_data_json FROM media WHERE id = ?", (media_id,))
        .fetchone()[0]
    )

    assert recovered["stage_receipts"]["scenes"]["status"] == "failed"
    assert recovered["stage_receipts"]["scenes"]["error_code"] == "artifact_invalid"
    assert recovered["analysis_status"] == "failed"


def test_recovery_rolls_back_all_project_rows_on_invalid_json(repository, tmp_path):
    first_id = _insert_media(
        repository,
        1,
        tmp_path / "first.wav",
        {
            "stage_receipts": {"beats": _running_receipt("beats")},
            "analysis_status": "running",
            "stage_status": {"beats": "running"},
            "stage_errors": {},
            "is_analyzed": False,
        },
    )
    second_id = _insert_media(
        repository,
        1,
        tmp_path / "second.wav",
        {"stage_receipts": {}},
    )
    conn = repository.db.get_connection()
    conn.execute(
        "UPDATE media SET ai_data_json = ? WHERE id = ?",
        ("{not-json", second_id),
    )
    conn.commit()

    with pytest.raises(ValueError, match=f"media {second_id}"):
        repository.recover_project_analysis(1, recovered_at_utc=RECOVERED_AT)

    first = json.loads(
        conn.execute(
            "SELECT ai_data_json FROM media WHERE id = ?",
            (first_id,),
        ).fetchone()[0]
    )
    assert first["stage_receipts"]["beats"]["status"] == "running"


def test_recovery_interrupts_projected_legacy_running_stage_and_preserves_completed_sibling(
    repository,
    tmp_path,
):
    media_id = _insert_media(
        repository,
        1,
        tmp_path / "legacy.wav",
        {
            "key": "A minor",
            "analysis_status": "running",
            "stage_status": {"beats": "running", "key": "completed"},
            "stage_errors": {},
            "is_analyzed": False,
        },
    )

    repository.recover_project_analysis(1, recovered_at_utc=RECOVERED_AT)
    recovered = json.loads(
        repository.db.get_connection()
        .execute("SELECT ai_data_json FROM media WHERE id = ?", (media_id,))
        .fetchone()[0]
    )

    assert recovered["stage_receipts"]["beats"]["receipt_version"] == 0
    assert recovered["stage_receipts"]["beats"]["status"] == "interrupted"
    assert recovered["stage_receipts"]["beats"]["error_message"] == (
        "Analysis interrupted by backend restart"
    )
    assert recovered["stage_receipts"]["key"]["receipt_version"] == 0
    assert recovered["stage_receipts"]["key"]["status"] == "completed"
    assert recovered["analysis_status"] == "partial"
    assert recovered["stage_status"] == {
        "beats": "interrupted",
        "key": "completed",
    }


def test_recovery_rejects_corrupt_partial_audio_artifact(repository, tmp_path):
    original = [0.0, 0.5, 1.0]
    media_id = _insert_media(
        repository,
        1,
        tmp_path / "partial.wav",
        {
            "beats_json": [9.0],
            "bpm": 200.0,
            "beat_count": 1,
            "energy_curve": [1.0],
            "key": "A minor",
            "stage_receipts": {
                "beats": _partial_receipt(
                    "beats",
                    "ai_data_json.beats_json",
                    original,
                ),
                "key": _completed_receipt(
                    "key",
                    "ai_data_json.key",
                    "A minor",
                ),
            },
            "analysis_status": "partial",
            "stage_status": {"beats": "partial", "key": "completed"},
            "stage_errors": {"beats": "beats produced partial output"},
            "is_analyzed": False,
        },
    )

    repository.recover_project_analysis(1, recovered_at_utc=RECOVERED_AT)
    recovered = json.loads(
        repository.db.get_connection()
        .execute("SELECT ai_data_json FROM media WHERE id = ?", (media_id,))
        .fetchone()[0]
    )

    receipt = recovered["stage_receipts"]["beats"]
    assert receipt["status"] == "failed"
    assert receipt["artifact_valid"] is False
    assert receipt["error_code"] == "artifact_invalid"
    assert recovered["analysis_status"] == "partial"
    for field in ("beats_json", "bpm", "beat_count", "energy_curve"):
        assert field not in recovered
    assert recovered["key"] == "A minor"
    assert recovered["stage_receipts"]["key"]["status"] == "completed"

    from backend.app_state import AppState

    state = AppState(
        current_project={
            "db_project_id": 1,
            "project_uuid": PROJECT_UUID,
            "path": str(tmp_path),
        },
    )
    assert state.load_from_db(project_id=1) is True
    clip = state.audio_clips[1]
    cached = state.audio_analysis_cache[1]
    assert clip["bpm"] == 0.0
    assert clip["beat_count"] == 0
    assert clip["key"] == "A minor"
    assert cached["beats"] == []
    assert cached["energy_curve"] == []
    assert cached["key"] == "A minor"
    assert cached["_stage_receipts"]["key"]["status"] == "completed"


def test_recovery_rejects_corrupt_partial_video_artifact(repository, tmp_path):
    original = {"tags": ["neon"], "tag_source": "lmstudio:qwen-vl"}
    scenes = [{"start": 0.0, "end": 1.0}]
    scenes_artifact = {"scene_count": 1, "scenes": scenes}
    media_id = _insert_media(
        repository,
        1,
        tmp_path / "partial.mp4",
        {
            "tags": ["neon"],
            "tag_source": "lmstudio:qwen-vl",
            "scene_count": 1,
            "scenes": scenes,
            "stage_artifacts": {
                "captions": {"tags": ["wrong"], "tag_source": "manual"},
                "scenes": scenes_artifact,
            },
            "stage_receipts": {
                "captions": _partial_receipt(
                    "captions",
                    "ai_data_json.stage_artifacts.captions",
                    original,
                ),
                "scenes": _completed_receipt(
                    "scenes",
                    "ai_data_json.stage_artifacts.scenes",
                    scenes_artifact,
                ),
            },
            "analysis_status": "partial",
            "stage_status": {"captions": "partial", "scenes": "completed"},
            "stage_errors": {"captions": "captions produced partial output"},
            "is_analyzed": False,
        },
    )

    repository.recover_project_analysis(1, recovered_at_utc=RECOVERED_AT)
    recovered = json.loads(
        repository.db.get_connection()
        .execute("SELECT ai_data_json FROM media WHERE id = ?", (media_id,))
        .fetchone()[0]
    )

    receipt = recovered["stage_receipts"]["captions"]
    assert receipt["status"] == "failed"
    assert receipt["artifact_valid"] is False
    assert receipt["error_code"] == "artifact_invalid"
    assert recovered["analysis_status"] == "partial"
    assert "tags" not in recovered
    assert "tag_source" not in recovered
    assert "captions" not in recovered["stage_artifacts"]
    assert recovered["stage_artifacts"]["scenes"] == scenes_artifact
    assert recovered["scenes"] == scenes
    assert recovered["stage_receipts"]["scenes"]["status"] == "completed"

    from backend.app_state import AppState

    state = AppState(
        current_project={
            "db_project_id": 1,
            "project_uuid": PROJECT_UUID,
            "path": str(tmp_path),
        },
    )
    assert state.load_from_db(project_id=1) is True
    clip = state.video_clips[1]
    cached = state.video_analysis_cache[1]
    assert clip["tags"] == []
    assert clip["tag_source"] == "none"
    assert cached["tags"] == []
    assert cached["tag_source"] == "none"
    assert cached["scenes"] == scenes
    assert cached["stage_artifacts"]["scenes"] == scenes_artifact
    assert cached["stage_receipts"]["scenes"]["status"] == "completed"
