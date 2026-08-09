from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain.cross_modal_projector import (
    CrossModalProjector,
    DEFAULT_AUDIO_DIM,
    DEFAULT_VIDEO_DIM,
    get_default_projector,
    publish_default_projector,
    reset_default_projector,
    restore_v1_projector,
)
from pb_studio.brain.projector_trainer import (
    ProjectTrainingSource,
    run_v2_fit_step,
)
from pb_studio.storage.migration_runner import migrate, migrate_project_state


STATE_MIGRATIONS = (
    Path(__file__).resolve().parents[1]
    / "src" / "pb_studio" / "storage" / "migrations" / "state"
)


def _state_with_event(path: Path, project_uuid: str, event_uuid: str):
    migrate(path, STATE_MIGRATIONS)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute(
        "INSERT INTO timelines(id,name,audio_clip_id,created_at,is_current) "
        "VALUES(1,'t',10,'2026-08-09T00:00:00Z',1)"
    )
    conn.execute(
        "INSERT INTO timeline_cuts(id,timeline_id,position_idx,clip_id,"
        "start_time,end_time) VALUES(1,1,0,'clip_20',0,1)"
    )
    conn.execute(
        "INSERT INTO feedback_events(cut_id,rating,alpha_delta,beta_delta,"
        "context_keys_json,timestamp,project_uuid,event_uuid) "
        "VALUES(1,'perfect',1,0,'[]','2026-08-09T00:00:01Z',?,?)",
        (project_uuid, event_uuid),
    )
    conn.execute(
        "INSERT INTO project_identity(singleton_id,project_uuid) VALUES(1,?)",
        (project_uuid,),
    )
    return conn


def test_state_identity_backfill_is_stable_and_project_scoped(tmp_path: Path):
    event_ids = []
    for index in (1, 2):
        path = tmp_path / f"p{index}.db"
        migrate(path, STATE_MIGRATIONS)
        conn = sqlite3.connect(str(path), isolation_level=None)
        conn.execute(
            "INSERT INTO timelines(id,name,audio_clip_id,created_at,is_current) "
            "VALUES(1,'t',10,'2026-08-09',1)"
        )
        conn.execute(
            "INSERT INTO timeline_cuts(id,timeline_id,position_idx,clip_id,"
            "start_time,end_time) VALUES(1,1,0,'clip_20',0,1)"
        )
        conn.execute(
            "INSERT INTO feedback_events(id,cut_id,rating,alpha_delta,beta_delta,"
            "context_keys_json,timestamp) VALUES(7,1,'fits',1,0,'[]','x')"
        )
        conn.close()
        project_uuid = str(uuid.uuid4())
        migrate_project_state(
            path,
            STATE_MIGRATIONS,
            project_uuid=project_uuid,
        )
        migrate_project_state(
            path,
            STATE_MIGRATIONS,
            project_uuid=project_uuid,
        )
        check = sqlite3.connect(str(path))
        row = check.execute(
            "SELECT project_uuid,event_uuid FROM feedback_events WHERE id=7"
        ).fetchone()
        check.close()
        assert row[0] == project_uuid
        assert row[1] == str(
            uuid.uuid5(uuid.UUID(project_uuid), "legacy-feedback:7")
        )
        event_ids.append(row[1])
    assert event_ids[0] != event_ids[1]


def test_catalog_v4_backfills_deterministic_unique_project_uuid(tmp_path: Path):
    from pb_studio.data.database_core import DatabaseCore, legacy_project_uuid

    path = tmp_path / "catalog.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE projects(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,"
        "created_at TIMESTAMP,last_modified TIMESTAMP,json_data TEXT)"
    )
    conn.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,"
        "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.executemany(
        "INSERT INTO schema_migrations(version,name) VALUES(?,?)",
        ((1, "core_schema"), (2, "media_import_guard"), (3, "vector_outbox")),
    )
    conn.execute(
        "INSERT INTO projects(id,name,created_at,json_data) VALUES(7,'legacy','2026-08-09','{}')"
    )
    conn.commit()
    DatabaseCore._apply_migrations(DatabaseCore.__new__(DatabaseCore), conn)
    value = conn.execute(
        "SELECT project_uuid FROM projects WHERE id=7"
    ).fetchone()[0]
    assert value == legacy_project_uuid(7, "2026-08-09")
    assert conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()[0] == 4
    conn.close()


def test_v2_artifact_roundtrip_contains_checkpoint_and_pending(tmp_path: Path):
    weights = tmp_path / "projector.npz"
    project_uuid = str(uuid.uuid4())
    applied = str(uuid.uuid4())
    pending = str(uuid.uuid4())
    projector = CrossModalProjector(weights_path=weights)
    projector.generation_uuid = str(uuid.uuid4())
    projector.applied_event_uuids = (applied,)
    projector.pending_events = {
        pending: {"project_uuid": project_uuid, "reason": "missing_video_embedding"}
    }
    projector.project_checkpoints = {
        project_uuid: {"events": 2, "status": "ready"}
    }
    projector.inventory_digest = "a" * 64
    projector.save_v2_atomic()

    loaded = CrossModalProjector(weights_path=weights)
    assert loaded.artifact_version == 2
    assert loaded.applied_event_uuids == (applied,)
    assert loaded.pending_events[pending]["reason"] == "missing_video_embedding"
    assert loaded.project_checkpoints[project_uuid]["events"] == 2


def test_v2_training_applies_event_once_and_retries_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project_uuid = str(uuid.uuid4())
    event_uuid = str(uuid.uuid4())
    conn = _state_with_event(tmp_path / "state.db", project_uuid, event_uuid)
    source = ProjectTrainingSource(
        project_uuid=project_uuid,
        state_conn=conn,
        audio_hash_for_clip_id=lambda _clip_id: "audio",
        video_hash_for_clip_id=lambda _clip_id: "video",
    )
    audio = np.ones(DEFAULT_AUDIO_DIM, dtype=np.float32)
    video = np.ones(DEFAULT_VIDEO_DIM, dtype=np.float32)
    from pb_studio.brain import post_processor

    monkeypatch.setattr(post_processor, "_load_audio_embedding", lambda *_: audio)
    monkeypatch.setattr(post_processor, "_load_video_embedding", lambda *_: None)
    active = CrossModalProjector(weights_path=tmp_path / "p.npz")
    published = []
    result = run_v2_fit_step(
        active,
        sources=[source],
        embedding_cache=object(),
        publish_fn=published.append,
    )
    assert result["new_events"] == 0
    assert result["pending_events"] == 1
    assert active.applied_event_uuids == ()

    monkeypatch.setattr(post_processor, "_load_video_embedding", lambda *_: video)
    result = run_v2_fit_step(
        published[-1],
        sources=[source],
        embedding_cache=object(),
        publish_fn=published.append,
    )
    assert result["new_events"] == 1
    assert published[-1].applied_event_uuids == (event_uuid,)
    matrix_after = published[-1].W_audio.copy()

    result = run_v2_fit_step(
        published[-1],
        sources=[source],
        embedding_cache=object(),
        publish_fn=published.append,
    )
    assert result["new_events"] == 0
    np.testing.assert_array_equal(published[-1].W_audio, matrix_after)
    conn.close()


def test_v2_replace_failure_keeps_active_file_and_matrices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from pb_studio.brain import cross_modal_projector as module

    weights = tmp_path / "projector.npz"
    active = CrossModalProjector(weights_path=weights)
    active.generation_uuid = str(uuid.uuid4())
    active.save_v2_atomic()
    before_file = weights.read_bytes()
    before_matrix = active.W_audio.copy()
    candidate = active.clone()
    candidate.W_audio[0, 0] += 1.0
    candidate.parent_generation_uuid = active.generation_uuid
    candidate.generation_uuid = str(uuid.uuid4())

    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(
        OSError("replace failed")
    ))
    with pytest.raises(OSError, match="replace failed"):
        candidate.save_v2_atomic()
    assert weights.read_bytes() == before_file
    np.testing.assert_array_equal(active.W_audio, before_matrix)
    assert not list(tmp_path.glob(".*.tmp"))


def test_parallel_readers_observe_only_complete_snapshots(tmp_path: Path):
    weights = tmp_path / "projector.npz"
    reset_default_projector()
    active = get_default_projector(weights_path=weights)
    audio = np.arange(DEFAULT_AUDIO_DIM, dtype=np.float32) + 1.0
    video = np.arange(DEFAULT_VIDEO_DIM, dtype=np.float32) + 1.0
    before = active.project_audio(audio)
    candidate = active.clone()
    candidate.fit_pairs([(audio, video, 1.0)] * 5, lr=0.05, steps=10)
    candidate.parent_generation_uuid = active.generation_uuid
    candidate.generation_uuid = str(uuid.uuid4())
    after = candidate.project_audio(audio)
    observed: list[np.ndarray] = []

    def _reader():
        for _ in range(100):
            observed.append(
                get_default_projector(weights_path=weights).project_audio(audio)
            )

    threads = [threading.Thread(target=_reader) for _ in range(4)]
    for thread in threads:
        thread.start()
    publish_default_projector(candidate)
    for thread in threads:
        thread.join()

    assert observed
    assert all(
        np.allclose(value, before) or np.allclose(value, after)
        for value in observed
    )
    reset_default_projector()


def test_first_v2_publish_preserves_and_restores_v1(tmp_path: Path):
    weights = tmp_path / "projector.npz"
    legacy = CrossModalProjector(seed=7, weights_path=weights)
    assert legacy.save()
    legacy_matrix = legacy.W_audio.copy()
    candidate = legacy.clone()
    candidate.generation_uuid = str(uuid.uuid4())
    candidate.save_v2_atomic()

    archives = list(tmp_path.glob("projector.v1.*.npz"))
    assert len(archives) == 1
    assert CrossModalProjector(weights_path=archives[0]).artifact_version == 1
    assert CrossModalProjector(weights_path=weights).artifact_version == 2

    restored = restore_v1_projector(archives[0], weights)
    assert restored.artifact_version == 1
    np.testing.assert_array_equal(restored.W_audio, legacy_matrix)
