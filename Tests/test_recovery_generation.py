from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from pb_studio.storage.recovery_generation import (
    RecoveryGenerationError,
    RecoveryGenerationValidationError,
    RecoveryGenerationWriter,
    apply_protected_retention,
    fixed_control_root,
    plan_protected_retention,
    request_restore_generation,
    validate_generation,
)


class InjectedCrash(RuntimeError):
    pass


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _writer(root: Path, generation_id: str, **kwargs) -> RecoveryGenerationWriter:
    return RecoveryGenerationWriter(
        control_root=root,
        generation_id=generation_id,
        config_digest=_digest(b"config"),
        project_inventory_digest=_digest(b"projects"),
        **kwargs,
    )


def _commit_file_generation(
    root: Path,
    source: Path,
    generation_id: str,
    **kwargs,
):
    writer = _writer(root, generation_id, **kwargs)
    writer.add_file(
        "config",
        source,
        group="G1-CONFIG",
        owner="ConfigManager",
    )
    return writer.commit()


def test_fixed_control_root_is_not_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert fixed_control_root() == (
        tmp_path / "PB_Studio" / "recovery-control" / "v1"
    )


def test_commit_publishes_immutable_file_and_external_receipt(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text('{"mode":"quality"}\n', encoding="utf-8")
    external = tmp_path / "source.wav"
    external.write_bytes(b"external media")

    writer = _writer(root, "gen-001")
    writer.add_file(
        "backend-config",
        source,
        group="G1-CONFIG",
        owner="ConfigManager",
        schema_version=3,
    )
    writer.add_external_reference(
        "source-audio",
        external,
        group="REF-MEDIA",
        owner="MediaRepository",
        required=True,
    )

    committed = writer.commit()
    manifest = validate_generation(
        root,
        "gen-001",
        expected_manifest_sha256=committed.manifest_sha256,
        validate_external_references=True,
    )

    assert manifest["schema_version"] == 1
    assert manifest["parent_generation"] is None
    assert manifest["artifacts"][0]["adapter"] == "file"
    assert manifest["artifacts"][0]["absolute_target"] == str(source.resolve())
    assert manifest["external_references"][0]["class"] == "external"
    assert _read_json(root / "CURRENT")["generation_id"] == "gen-001"
    journal = _read_json(root / "journal.json")
    assert journal["operation"] == "snapshot"
    assert journal["state"] == "COMMITTED"
    assert journal["committed_manifest_sha256"] == committed.manifest_sha256

    source.write_text("new live value", encoding="utf-8")
    staged = committed.generation_dir / manifest["artifacts"][0]["generation_relpath"]
    assert staged.read_text(encoding="utf-8") == '{"mode":"quality"}\n'
    with pytest.raises(RecoveryGenerationError, match="immutable"):
        writer.add_external_reference(
            "late",
            external,
            group="REF-MEDIA",
            owner="test",
        )


def test_sqlite_online_backup_records_schema_and_consistent_rows(tmp_path):
    root = tmp_path / "control"
    database = tmp_path / "state.db"
    connection = sqlite3.connect(str(database))
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA user_version=7")
        connection.execute("CREATE TABLE facts(value TEXT NOT NULL)")
        connection.execute("INSERT INTO facts VALUES ('confirmed')")
        connection.commit()

        writer = _writer(root, "gen-sqlite")
        writer.add_sqlite(
            "project-state",
            database,
            group="G5-PROJECT",
            owner="BrainService",
        )
        committed = writer.commit()
    finally:
        connection.close()

    manifest = validate_generation(root, committed.generation_id)
    record = manifest["artifacts"][0]
    assert record["adapter"] == "sqlite_backup"
    assert record["quick_check"] == "ok"
    assert record["user_version"] == 7
    backup = committed.generation_dir / record["generation_relpath"]
    restored = sqlite3.connect(str(backup))
    try:
        assert restored.execute("SELECT value FROM facts").fetchone()[0] == "confirmed"
    finally:
        restored.close()


def test_optional_missing_external_reference_is_explicitly_degraded(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("{}", encoding="utf-8")
    missing = tmp_path / "offline.mp4"
    writer = _writer(root, "gen-degraded")
    writer.add_file("config", source, group="G1", owner="ConfigManager")
    writer.add_external_reference(
        "offline-video",
        missing,
        group="REF-MEDIA",
        owner="MediaRepository",
        required=False,
    )

    committed = writer.commit()
    manifest = validate_generation(root, committed.generation_id)

    receipt = manifest["external_references"][0]
    assert receipt["available"] is False
    assert receipt["sha256"] == ""
    assert receipt["degraded_mode_policy"] == "report_unavailable"


def test_required_missing_external_reference_fails_before_control_publish(tmp_path):
    root = tmp_path / "control"
    writer = _writer(root, "gen-missing")
    writer.add_external_reference(
        "required-source",
        tmp_path / "missing.wav",
        group="REF-MEDIA",
        owner="MediaRepository",
        required=True,
    )

    with pytest.raises(RecoveryGenerationError, match="Required external"):
        writer.commit()

    assert not root.exists()


@pytest.mark.parametrize(
    ("fault_stage", "expected_journal", "new_generation_exists", "current_is_new"),
    [
        ("after_preparing", "PREPARING", False, False),
        ("after_staged", "STAGED", True, False),
        ("after_current", "STAGED", True, True),
    ],
)
def test_fault_injection_leaves_durable_convergence_receipts(
    tmp_path,
    fault_stage,
    expected_journal,
    new_generation_exists,
    current_is_new,
):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("first", encoding="utf-8")
    _commit_file_generation(root, source, "gen-first")
    source.write_text("second", encoding="utf-8")

    def inject(stage: str) -> None:
        if stage == fault_stage:
            raise InjectedCrash(stage)

    with pytest.raises(InjectedCrash, match=fault_stage):
        _commit_file_generation(
            root,
            source,
            "gen-second",
            fault_injector=inject,
        )

    journal = _read_json(root / "journal.json")
    current = _read_json(root / "CURRENT")
    assert journal["operation"] == "snapshot"
    assert journal["state"] == expected_journal
    assert (root / "generations" / "gen-second").exists() is new_generation_exists
    assert (current["generation_id"] == "gen-second") is current_is_new


def test_staged_writer_generation_bootstrap_publishes_without_replaying_target(
    tmp_path,
):
    from backend.recovery_bootstrap import ensure_recovery_ready

    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("first", encoding="utf-8")
    _commit_file_generation(root, source, "gen-first")
    source.write_text("second", encoding="utf-8")

    def inject(stage: str) -> None:
        if stage == "after_staged":
            raise InjectedCrash(stage)

    with pytest.raises(InjectedCrash, match="after_staged"):
        _commit_file_generation(
            root,
            source,
            "gen-second",
            fault_injector=inject,
        )

    source.write_text("newer-live-value", encoding="utf-8")
    result = ensure_recovery_ready(root)

    assert result.status == "snapshot_committed"
    assert result.generation_id == "gen-second"
    assert source.read_text(encoding="utf-8") == "newer-live-value"
    assert _read_json(root / "CURRENT")["generation_id"] == "gen-second"
    assert _read_json(root / "journal.json")["state"] == "COMMITTED"


def test_generation_validation_detects_staged_file_tampering(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "project.json"
    source.write_text("confirmed", encoding="utf-8")
    committed = _commit_file_generation(root, source, "gen-tamper")
    manifest = _read_json(committed.manifest_path)
    staged = committed.generation_dir / manifest["artifacts"][0]["generation_relpath"]
    staged.write_text("tampered", encoding="utf-8")

    with pytest.raises(RecoveryGenerationValidationError, match="size mismatch"):
        validate_generation(root, committed.generation_id)


def test_pending_journal_blocks_a_new_snapshot(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("first", encoding="utf-8")
    _commit_file_generation(root, source, "gen-first")
    journal = _read_json(root / "journal.json")
    journal["state"] = "STAGED"
    (root / "journal.json").write_text(json.dumps(journal), encoding="utf-8")

    with pytest.raises(RecoveryGenerationError, match="must converge"):
        _commit_file_generation(root, source, "gen-second")


def test_retention_plan_protects_current_parent_and_does_not_delete(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("one", encoding="utf-8")
    _commit_file_generation(root, source, "gen-one")
    source.write_text("two", encoding="utf-8")
    _commit_file_generation(root, source, "gen-two")
    source.write_text("three", encoding="utf-8")
    _commit_file_generation(root, source, "gen-three")

    plan = plan_protected_retention(root, keep_latest=0)

    assert set(plan.protected) == {"gen-two", "gen-three"}
    assert plan.delete_candidates == ("gen-one",)
    assert all(
        (root / "generations" / generation_id).is_dir()
        for generation_id in ("gen-one", "gen-two", "gen-three")
    )


def test_retention_requires_exact_confirmation_before_temp_generation_delete(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("one", encoding="utf-8")
    _commit_file_generation(root, source, "gen-one")
    source.write_text("two", encoding="utf-8")
    _commit_file_generation(root, source, "gen-two")
    source.write_text("three", encoding="utf-8")
    _commit_file_generation(root, source, "gen-three")
    plan = plan_protected_retention(root, keep_latest=0)

    with pytest.raises(RecoveryGenerationError, match="changed"):
        apply_protected_retention(
            root,
            keep_latest=0,
            confirmed_delete_candidates=(),
        )

    applied = apply_protected_retention(
        root,
        keep_latest=0,
        confirmed_delete_candidates=plan.delete_candidates,
    )
    assert applied.delete_candidates == ("gen-one",)
    assert not (root / "generations" / "gen-one").exists()
    assert (root / "generations" / "gen-two").is_dir()
    assert (root / "generations" / "gen-three").is_dir()


def test_restore_request_is_durable_and_bootstrap_only(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("old", encoding="utf-8")
    old = _commit_file_generation(root, source, "gen-old")
    source.write_text("new", encoding="utf-8")
    _commit_file_generation(root, source, "gen-new")

    journal_path = request_restore_generation("gen-old", control_root=root)

    assert source.read_text(encoding="utf-8") == "new"
    journal = _read_json(journal_path)
    assert journal["operation"] == "restore"
    assert journal["state"] == "STAGED"
    assert journal["next_manifest_sha256"] == old.manifest_sha256


def test_failed_selected_restore_removes_selected_only_artifact_on_rollback(
    tmp_path,
    monkeypatch,
):
    import backend.recovery_bootstrap as recovery_bootstrap

    root = tmp_path / "control"
    project_root = tmp_path / "project"
    project_root.mkdir()
    common = tmp_path / "config.json"
    common.write_text("old", encoding="utf-8")
    first = _writer(root, "gen-old")
    first.add_file("config", common, group="G1", owner="ConfigManager")
    old = first.commit()

    variable = project_root / "later.brain-feedback-outbox.json"
    variable.write_text("{}", encoding="utf-8")
    common.write_text("new", encoding="utf-8")
    second = _writer(root, "gen-new")
    second.add_file(
        "project-outbox",
        variable,
        group="project",
        owner="ProjectLifecycle",
        owner_scope=project_root,
    )
    second.add_file("config", common, group="G1", owner="ConfigManager")
    new = second.commit()

    request_restore_generation(old.generation_id, control_root=root)
    ensure_recovery_ready = recovery_bootstrap.ensure_recovery_ready
    ensure_recovery_ready(root)
    assert not variable.exists()
    request_restore_generation(new.generation_id, control_root=root)
    real_replace = recovery_bootstrap.os.replace

    def fail_selected_common(source, destination):
        if Path(destination) == common:
            raise PermissionError("simulated selected restore failure")
        return real_replace(source, destination)

    monkeypatch.setattr(recovery_bootstrap.os, "replace", fail_selected_common)

    result = ensure_recovery_ready(root)

    assert result.generation_id == old.generation_id
    assert common.read_text(encoding="utf-8") == "old"
    assert not variable.exists()
    assert _read_json(root / "CURRENT")["generation_id"] == old.generation_id


def test_writer_rejects_control_root_as_an_artifact(tmp_path):
    root = tmp_path / "control"
    source = root / "nested" / "CURRENT-copy"
    source.parent.mkdir(parents=True)
    source.write_text("forbidden", encoding="utf-8")
    writer = _writer(root, "gen-self")

    with pytest.raises(RecoveryGenerationError, match="cannot snapshot itself"):
        writer.add_file("self", source, group="G0", owner="Recovery")


def test_writer_rejects_relative_restore_and_external_targets(tmp_path):
    root = tmp_path / "control"
    source = tmp_path / "config.json"
    source.write_text("{}", encoding="utf-8")
    writer = _writer(root, "gen-relative")

    with pytest.raises(RecoveryGenerationError, match="target must be absolute"):
        writer.add_file(
            "relative-target",
            source,
            group="G1",
            owner="ConfigManager",
            absolute_target=Path("relative.json"),
        )
    with pytest.raises(RecoveryGenerationError, match="must be absolute"):
        writer.add_external_reference(
            "relative-external",
            Path("source.wav"),
            group="REF-MEDIA",
            owner="MediaRepository",
        )
