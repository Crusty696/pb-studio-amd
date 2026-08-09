from __future__ import annotations

import asyncio
from dataclasses import replace
import importlib
import inspect
import json
from pathlib import Path
import sqlite3
import uuid

import numpy as np
import pytest


PROJECT_UUID = "98cbb214-5438-4701-a96b-5c1220901ce4"


def _api():
    return importlib.import_module("pb_studio.storage.recovery_adapters")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _create_sqlite(path: Path, statements: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        for statement in statements:
            connection.execute(statement)
        connection.commit()
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def _sql_text(value: object) -> str:
    return str(value).replace("'", "''")


def _create_catalog(path: Path, project_root: Path, external_media: Path) -> None:
    project_payload = json.dumps(
        {
            "id": 1,
            "name": "Recovery fixture",
            "path": str(project_root.resolve()),
            "project_uuid": PROJECT_UUID,
        }
    )
    _create_sqlite(
        path,
        (
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT, json_data TEXT, project_uuid TEXT UNIQUE)",
            "CREATE TABLE media (id INTEGER PRIMARY KEY, project_id INTEGER, "
            "file_path TEXT NOT NULL, file_hash TEXT)",
            "CREATE TABLE vector_map (faiss_id INTEGER PRIMARY KEY, media_id INTEGER)",
            "INSERT INTO projects VALUES "
            f"(1, 'Recovery fixture', '2026-08-09T00:00:00Z', "
            f"'{project_payload}', '{PROJECT_UUID}')",
            "INSERT INTO media VALUES "
            f"(1, 1, '{_sql_text(external_media.resolve())}', 'media-hash')",
            "INSERT INTO vector_map VALUES (0, 1)",
        ),
    )


def _create_state_db(path: Path) -> None:
    _create_sqlite(
        path,
        (
            "CREATE TABLE project_identity "
            "(singleton_id INTEGER PRIMARY KEY, project_uuid TEXT NOT NULL UNIQUE)",
            "CREATE TABLE feedback_events "
            "(id INTEGER PRIMARY KEY, project_uuid TEXT, event_uuid TEXT UNIQUE)",
            f"INSERT INTO project_identity VALUES (1, '{PROJECT_UUID}')",
        ),
    )


def _create_brain_db(path: Path, table: str) -> None:
    _create_sqlite(
        path,
        (
            f"CREATE TABLE {table} (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            f"INSERT INTO {table} VALUES ('fixture', 'complete')",
        ),
    )


def _create_faiss_triplet(data_dir: Path) -> tuple[Path, Path, Path]:
    faiss = pytest.importorskip("faiss")
    index_path = data_dir / "video_index.faiss"
    metadata_path = data_dir / "video_index_meta.json"
    tombstones_path = data_dir / "video_index_tombstones.json"
    index = faiss.IndexFlatIP(4)
    index.add(np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))
    faiss.write_index(index, str(index_path))
    _write_json(metadata_path, {"0": {"media_id": 1, "project_id": 1}})
    _write_json(tombstones_path, [])
    return index_path, metadata_path, tombstones_path


def _create_project(project_root: Path) -> dict[str, Path]:
    project_root.mkdir(parents=True)
    paths = {
        "project": project_root / "project.json",
        "timeline": project_root / "timeline.json",
        "anchors": project_root / "anchors.json",
        "chat": project_root / "chat_history.json",
        "state": project_root / "state.db",
        "project_outbox": project_root / "state.db.brain-feedback-outbox.json",
    }
    _write_json(
        paths["project"],
        {
            "id": 1,
            "name": "Recovery fixture",
            "path": str(project_root.resolve()),
            "project_uuid": PROJECT_UUID,
        },
    )
    _write_json(paths["timeline"], {"project_uuid": PROJECT_UUID, "clips": []})
    _write_json(paths["anchors"], {"project_uuid": PROJECT_UUID, "anchors": []})
    _write_json(paths["chat"], {"project_uuid": PROJECT_UUID, "messages": []})
    _create_state_db(paths["state"])
    _write_json(paths["project_outbox"], {})
    return paths


def _create_projector(path: Path) -> None:
    generation_uuid = str(uuid.UUID("9700974d-c44c-4fa6-8bc7-c8fc6711e492"))
    with path.open("wb") as handle:
        np.savez(
            handle,
            W_audio=np.eye(2, dtype=np.float32),
            W_video=np.eye(2, dtype=np.float32),
            common_dim=np.int32(2),
            audio_dim=np.int32(2),
            video_dim=np.int32(2),
            seed=np.int32(42),
            audio_model_name=np.str_("fixture-audio"),
            audio_model_version=np.str_("1"),
            video_model_name=np.str_("fixture-video"),
            video_model_version=np.str_("1"),
            format_version=np.int32(2),
            generation_uuid=np.str_(generation_uuid),
            parent_generation_uuid=np.str_(""),
            applied_event_uuids=np.asarray([], dtype=np.str_),
            pending_events_json=np.str_("{}"),
            project_checkpoints_json=np.str_("{}"),
            inventory_digest=np.str_("fixture-inventory"),
        )


def _create_complete_workspace(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "workspace"
    data_dir = root / "data"
    brain_dir = root / "brain"
    project_root = root / "projects" / "p1"
    data_dir.mkdir(parents=True)
    brain_dir.mkdir(parents=True)
    external_media = tmp_path / "external" / "source.wav"
    external_media.parent.mkdir(parents=True)
    external_media.write_bytes(b"user-owned original")

    config = root / "config.json"
    _write_json(
        config,
        {
            "paths": {"db_path": "./data/pb_studio.db"},
            "hardware": {"gpu_backend": "directml"},
        },
    )
    wpf_settings = root / "wpf" / "settings.json"
    _write_json(wpf_settings, {"theme": "dark", "backend_port": 8765})
    catalog = data_dir / "pb_studio.db"
    _create_catalog(catalog, project_root, external_media)
    faiss_paths = _create_faiss_triplet(data_dir)
    project_paths = _create_project(project_root)

    brain_paths = {
        "weights": brain_dir / "weights.db",
        "patterns": brain_dir / "patterns.db",
        "cache": brain_dir / "embedding_cache.db",
        "outbox": brain_dir / "feedback_outbox.json",
        "receipts": brain_dir / "feedback_receipts.json",
        "embedding": brain_dir / "embeddings" / "media_fixture.npy",
        "projector": brain_dir / "cross_modal_projector.npz",
    }
    _create_brain_db(brain_paths["weights"], "axis_weights")
    _create_brain_db(brain_paths["patterns"], "patterns")
    brain_paths["embedding"].parent.mkdir(parents=True)
    np.save(brain_paths["embedding"], np.asarray([1.0, 0.0], dtype=np.float32))
    _create_sqlite(
        brain_paths["cache"],
        (
            "CREATE TABLE media_embedding_index (media_hash TEXT, media_type TEXT, "
            "embedding_path TEXT, model_name TEXT, model_version TEXT, "
            "computed_at TEXT, file_size_bytes INTEGER, "
            "PRIMARY KEY(media_hash, model_name, model_version))",
            "INSERT INTO media_embedding_index VALUES "
            f"('media-hash', 'audio', '{_sql_text(brain_paths['embedding'].resolve())}', "
            "'fixture-audio', '1', '2026-08-09T00:00:00Z', 136)",
        ),
    )
    _write_json(brain_paths["outbox"], {})
    _write_json(brain_paths["receipts"], {})
    _create_projector(brain_paths["projector"])

    stems_dir = project_root / "stems"
    stems_dir.mkdir()
    stem = stems_dir / "vocals.wav"
    stem.write_bytes(b"application-owned stem")
    stem_marker = stems_dir / ".source.fixture.stems-complete.json"
    _write_json(stem_marker, {"status": "complete", "stems": [str(stem)]})
    render = project_root / "renders" / "final.mp4"
    render.parent.mkdir()
    render.write_bytes(b"application-owned render")

    return {
        "root": root,
        "config": config,
        "wpf_settings": wpf_settings,
        "catalog": catalog,
        "faiss": faiss_paths,
        "project_root": project_root,
        "project": project_paths,
        "brain_dir": brain_dir,
        "brain": brain_paths,
        "stems": (stem_marker, stem),
        "renders": (render,),
        "external": external_media,
    }


def _owner_snapshot(paths: dict[str, object], *, external_media=None):
    api = _api()
    return api.RecoveryOwnerSnapshot(
        config_path=paths["config"],
        catalog_db_path=paths["catalog"],
        brain_dir=paths["brain_dir"],
        project_roots=(paths["project_root"],),
        wpf_settings_path=paths["wpf_settings"],
        vector_index_path=paths["faiss"][0],
        stem_artifacts=paths["stems"],
        render_outputs=paths["renders"],
        external_media=(
            paths["external"] if external_media is None else external_media,
        ),
    )


def _await_if_needed(value):
    return asyncio.run(value) if inspect.isawaitable(value) else value


def _snapshot(paths: dict[str, object], control_root: Path):
    api = _api()
    return _await_if_needed(
        api.create_owner_generation(
            _owner_snapshot(paths),
            control_root=control_root,
            barrier=None,
            timeout=5.0,
        )
    )


def test_complete_owner_inventory_commits_one_shared_generation(tmp_path):
    api = _api()
    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    snapshot = _owner_snapshot(paths)

    config_digest, inventory_digest = api.owner_snapshot_digests(snapshot)
    committed = _snapshot(paths, control_root)
    validation = api.validate_owner_generation(
        control_root,
        committed.generation_id,
    )
    manifest = json.loads(committed.manifest_path.read_text(encoding="utf-8"))

    assert len(config_digest) == len(inventory_digest) == 64
    assert manifest["config_digest"] == config_digest
    assert manifest["project_inventory_digest"] == inventory_digest
    assert validation.valid is True
    assert validation.degraded_references == ()
    owned_targets = {
        Path(record["absolute_target"]).resolve()
        for record in manifest["artifacts"]
    }
    expected_owned = {
        Path(paths["config"]).resolve(),
        Path(paths["wpf_settings"]).resolve(),
        Path(paths["catalog"]).resolve(),
        *(Path(path).resolve() for path in paths["faiss"]),
        *(Path(path).resolve() for path in paths["project"].values()),
        *(Path(path).resolve() for path in paths["brain"].values()),
        *(Path(path).resolve() for path in paths["stems"]),
    }
    assert expected_owned <= owned_targets
    assert {record["group"] for record in manifest["artifacts"]} >= {
        "global-config",
        "global-index",
        "project",
        "brain",
        "project-media",
    }
    external_targets = [
        Path(reference["absolute_path"]).resolve()
        for reference in manifest["external_references"]
    ]
    assert set(external_targets) == {
        Path(paths["external"]).resolve(),
        *(Path(path).resolve() for path in paths["renders"]),
    }
    assert all(
        reference["class"] == "external"
        for reference in manifest["external_references"]
    )


def test_default_catalog_without_materialized_project_is_valid(tmp_path):
    api = _api()
    root = tmp_path / "workspace"
    config = root / "config.json"
    catalog = root / "data" / "pb_studio.db"
    brain_dir = root / "brain"
    _write_json(config, {"hardware": {"gpu_backend": "directml"}})
    default_payload = json.dumps({"id": 1, "name": "Default", "path": None})
    _create_sqlite(
        catalog,
        (
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "created_at TEXT, json_data TEXT, project_uuid TEXT UNIQUE)",
            "INSERT INTO projects VALUES "
            f"(1, 'Default', '2026-08-09T00:00:00Z', '{default_payload}', NULL)",
        ),
    )
    _create_brain_db(brain_dir / "weights.db", "axis_weights")
    _create_brain_db(brain_dir / "patterns.db", "patterns")
    _create_brain_db(brain_dir / "embedding_cache.db", "media_embedding_index")
    snapshot = api.RecoveryOwnerSnapshot(
        config_path=config,
        catalog_db_path=catalog,
        brain_dir=brain_dir,
    )

    committed = _await_if_needed(
        api.create_owner_generation(snapshot, control_root=tmp_path / "control")
    )
    validation = api.validate_owner_generation(
        tmp_path / "control",
        committed.generation_id,
    )
    manifest = json.loads(committed.manifest_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert "project" not in {record["group"] for record in manifest["artifacts"]}


def test_half_applied_brain_operation_fails_closed_before_publish(tmp_path):
    api = _api()
    paths = _create_complete_workspace(tmp_path)
    _write_json(
        paths["brain"]["outbox"],
        {
            "schema_version": 1,
            "operation_id": "0123456789abcdef",
            "stage": "weights_applied",
            "state_db_path": str(paths["project"]["state"]),
        },
    )
    control_root = tmp_path / "control"

    with pytest.raises(api.RecoveryOwnerAdapterError, match="(?i)brain|outbox|receipt"):
        _snapshot(paths, control_root)

    assert not (control_root / "CURRENT").exists()


def test_catalog_and_faiss_identity_mismatch_fails_closed(tmp_path):
    api = _api()
    paths = _create_complete_workspace(tmp_path)
    _write_json(paths["faiss"][1], {"1": {"media_id": 1, "project_id": 1}})
    control_root = tmp_path / "control"

    with pytest.raises(api.RecoveryOwnerAdapterError, match="(?i)faiss|vector"):
        _snapshot(paths, control_root)

    assert not (control_root / "CURRENT").exists()


def test_invalid_config_fails_closed_before_any_owner_is_published(tmp_path):
    api = _api()
    paths = _create_complete_workspace(tmp_path)
    Path(paths["config"]).write_text("{broken", encoding="utf-8")
    control_root = tmp_path / "control"

    with pytest.raises(api.RecoveryOwnerAdapterError, match="(?i)config|json"):
        _snapshot(paths, control_root)

    assert not (control_root / "CURRENT").exists()


def test_missing_optional_external_media_is_reported_degraded(tmp_path):
    api = _api()
    paths = _create_complete_workspace(tmp_path)
    missing = tmp_path / "offline" / "source.wav"
    control_root = tmp_path / "control"
    snapshot = _owner_snapshot(paths, external_media=missing)

    committed = _await_if_needed(
        api.create_owner_generation(
            snapshot,
            control_root=control_root,
            barrier=None,
            timeout=5.0,
        )
    )
    validation = api.validate_owner_generation(control_root, committed.generation_id)

    assert validation.valid is True
    assert len(validation.degraded_references) == 1
    assert "source.wav" in validation.degraded_references[0]


def test_clean_bootstrap_restart_preserves_newer_live_owner_targets(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    committed = _snapshot(paths, control_root)
    config = Path(paths["config"])
    newer_live_value = b'{"newer":"live"}\n'
    config.write_bytes(newer_live_value)

    first = ensure_recovery_ready(control_root)
    second = ensure_recovery_ready(control_root)

    assert first.status == "ready"
    assert second.status == "ready"
    assert first.generation_id == second.generation_id == committed.generation_id
    assert config.read_bytes() == newer_live_value


def test_dirty_bootstrap_restart_converges_live_owner_targets(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready, mark_runtime_dirty

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    committed = _snapshot(paths, control_root)
    config = Path(paths["config"])
    snapshot_value = config.read_bytes()
    assert mark_runtime_dirty(control_root) is True
    config.write_bytes(b'{"unclean":"work"}\n')

    result = ensure_recovery_ready(control_root)

    assert result.status == "recovered"
    assert result.generation_id == committed.generation_id
    assert config.read_bytes() == snapshot_value


def test_dirty_recovery_removes_only_new_scoped_variable_artifacts(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready, mark_runtime_dirty

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    _snapshot(paths, control_root)
    assert mark_runtime_dirty(control_root) is True

    project_root = Path(paths["project_root"])
    new_outbox = project_root / "runtime.brain-feedback-outbox.json"
    new_embedding = Path(paths["brain_dir"]) / "embeddings" / "new" / "runtime.npy"
    stem_run = Path(paths["root"]) / "temp" / "stem-runs" / "runtime-run"
    new_stem = stem_run / "drums.wav"
    new_marker = stem_run / ".runtime.stems-complete.json"
    _write_json(new_outbox, {})
    new_embedding.parent.mkdir(parents=True)
    np.save(new_embedding, np.asarray([0.0, 1.0], dtype=np.float32))
    stem_run.mkdir(parents=True)
    new_stem.write_bytes(b"runtime stem")
    _write_json(new_marker, {"status": "complete"})
    foreign = project_root / "stems" / "user-recording.wav"
    foreign.write_bytes(b"user file")

    result = ensure_recovery_ready(control_root)

    assert result.status == "recovered"
    assert all(
        not path.exists()
        for path in (new_outbox, new_embedding, new_stem, new_marker)
    )
    assert foreign.read_bytes() == b"user file"


def test_restore_older_generation_removes_later_optional_owner_files(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready
    from pb_studio.storage.recovery_generation import request_restore_generation

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    optional = tuple(
        Path(paths["project"][key])
        for key in ("timeline", "anchors", "chat", "project_outbox")
    )
    for path in optional:
        path.unlink()
    old = _snapshot(paths, control_root)

    for path in optional:
        _write_json(
            path,
            {} if path.name.endswith("brain-feedback-outbox.json") else {"newer": True},
        )
    foreign = Path(paths["project_root"]) / "user-notes.txt"
    foreign.write_text("preserve me", encoding="utf-8")
    _snapshot(paths, control_root)
    request_restore_generation(old.generation_id, control_root=control_root)

    result = ensure_recovery_ready(control_root)

    assert result.status == "recovered"
    assert all(not path.exists() for path in optional)
    assert foreign.read_text(encoding="utf-8") == "preserve me"


def test_restore_older_generation_deletes_previous_only_variable_artifacts(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready
    from pb_studio.storage.recovery_generation import request_restore_generation

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    embedding = Path(paths["brain"]["embedding"])
    stems = tuple(Path(path) for path in paths["stems"])
    saved = {path: path.read_bytes() for path in (embedding, *stems)}
    for path in saved:
        path.unlink()
    old = _await_if_needed(
        _api().create_owner_generation(
            replace(_owner_snapshot(paths), stem_artifacts=()),
            control_root=control_root,
            timeout=5.0,
        )
    )

    variable_outbox = (
        Path(paths["project_root"]) / "later.brain-feedback-outbox.json"
    )
    _write_json(variable_outbox, {})
    for path, content in saved.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _snapshot(paths, control_root)
    foreign = Path(paths["project_root"]) / "user-notes.txt"
    foreign.write_text("preserve me", encoding="utf-8")
    request_restore_generation(old.generation_id, control_root=control_root)

    result = ensure_recovery_ready(control_root)

    assert result.status == "recovered"
    assert not variable_outbox.exists()
    assert not embedding.exists()
    assert all(not path.exists() for path in stems)
    assert foreign.read_text(encoding="utf-8") == "preserve me"


def test_new_generation_tombstones_disappeared_variable_owner_artifacts(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready
    from pb_studio.storage.recovery_generation import request_restore_generation

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    variable_outbox = (
        Path(paths["project_root"]) / "custom.brain-feedback-outbox.json"
    )
    _write_json(variable_outbox, {})
    variable = (
        variable_outbox,
        Path(paths["brain"]["embedding"]),
        *(Path(path) for path in paths["stems"]),
    )
    _snapshot(paths, control_root)
    contents = {path: path.read_bytes() for path in variable}
    for path in variable:
        path.unlink()

    current = _await_if_needed(
        _api().create_owner_generation(
            replace(_owner_snapshot(paths), stem_artifacts=()),
            control_root=control_root,
            timeout=5.0,
        )
    )
    manifest = json.loads(current.manifest_path.read_text(encoding="utf-8"))
    tombstone_targets = {
        Path(record["absolute_target"]).resolve()
        for record in manifest["artifacts"]
        if record["restore_policy"] == "delete_if_present"
    }
    for path, content in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    foreign = Path(paths["project_root"]) / "user-notes.txt"
    foreign.write_text("preserve me", encoding="utf-8")
    request_restore_generation(current.generation_id, control_root=control_root)

    result = ensure_recovery_ready(control_root)

    assert {path.resolve() for path in variable} <= tombstone_targets
    assert result.status == "recovered"
    assert all(not path.exists() for path in variable)
    assert foreign.read_text(encoding="utf-8") == "preserve me"


def test_restore_does_not_delete_external_stem_without_project_scope(tmp_path):
    from backend.recovery_bootstrap import ensure_recovery_ready
    from pb_studio.storage.recovery_generation import request_restore_generation

    paths = _create_complete_workspace(tmp_path)
    control_root = tmp_path / "control"
    old = _snapshot(paths, control_root)
    external_stem = tmp_path / "external-stems" / "vocals.wav"
    external_stem.parent.mkdir()
    external_stem.write_bytes(b"external application output")
    newer = _await_if_needed(
        _api().create_owner_generation(
            replace(
                _owner_snapshot(paths),
                stem_artifacts=(*paths["stems"], external_stem),
            ),
            control_root=control_root,
            timeout=5.0,
        )
    )
    manifest = json.loads(newer.manifest_path.read_text(encoding="utf-8"))
    external_record = next(
        record
        for record in manifest["artifacts"]
        if Path(record["absolute_target"]).resolve() == external_stem.resolve()
    )
    request_restore_generation(old.generation_id, control_root=control_root)

    result = ensure_recovery_ready(control_root)

    assert external_record["owner_scope"] is None
    assert result.status == "recovered"
    assert external_stem.read_bytes() == b"external application output"
