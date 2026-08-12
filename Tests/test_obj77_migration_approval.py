from __future__ import annotations

import json
from pathlib import Path

import pytest


PROJECT_UUID = "98cbb214-5438-4701-a96b-5c1220901ce4"


def test_approval_schema_declares_exact_binding_fields():
    path = Path(
        "specs/00022-complete-requirements-remediation/contracts/"
        "migration-approval.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "operation_id",
        "bundle_id",
        "scope",
        "target_kind",
        "target_path",
        "source_sha256",
        "source_bundle_sha256",
        "source_schema_version",
        "target_schema_version",
        "project_uuid",
        "backup_path",
        "backup_sha256",
        "backup_bundle_sha256",
        "rollback_command",
        "approved",
        "approved_at_utc",
        "approval_source",
    }


def test_fixture_approval_is_bound_to_exact_target_hash_backup_and_rollback(
    tmp_path: Path,
):
    from pb_studio.storage.migration_authorization import (
        prepare_fixture_approval,
        sha256_file,
        validate_migration_approval,
    )

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    target.write_bytes(b"closed fixture database")
    backup = sandbox / "embeddings.pre-v2.db"
    receipt = prepare_fixture_approval(
        target_path=target,
        target_kind="embeddings",
        source_schema_version=1,
        target_schema_version=2,
        project_uuid=PROJECT_UUID,
        backup_path=backup,
        approved_at_utc="2026-08-12T12:00:00Z",
        approval_source="user_explicit_turn",
    )

    assert receipt["source_sha256"] == sha256_file(target)
    assert receipt["backup_sha256"] == receipt["source_sha256"]
    assert receipt["source_bundle_sha256"] == receipt["backup_bundle_sha256"]
    authorization = validate_migration_approval(
        receipt,
        expected_kind="embeddings",
        allowed_scope="fixture",
    )
    assert authorization.target_path == target.resolve()
    assert authorization.backup_path == backup.resolve()
    assert authorization.project_uuid == PROJECT_UUID


@pytest.mark.parametrize(
    "mutation",
    [
        {"approved": False},
        {"source_sha256": "0" * 64},
        {"backup_sha256": "1" * 64},
        {"scope": "real"},
        {"rollback_command": "Remove-Item -Recurse C:\\"},
        {"project_uuid": "not-a-uuid"},
        {"target_path": "relative.db"},
        {"operation_id": "not-a-uuid"},
    ],
)
def test_invalid_or_tampered_approval_fails_closed(tmp_path: Path, mutation):
    from pb_studio.storage.migration_authorization import (
        MigrationApprovalError,
        prepare_fixture_approval,
        validate_migration_approval,
    )

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    target.write_bytes(b"fixture")
    receipt = prepare_fixture_approval(
        target_path=target,
        target_kind="embeddings",
        source_schema_version=1,
        target_schema_version=2,
        project_uuid=PROJECT_UUID,
        backup_path=sandbox / "backup.db",
        approved_at_utc="2026-08-12T12:00:00Z",
        approval_source="user_explicit_turn",
    )
    receipt.update(mutation)

    with pytest.raises(MigrationApprovalError):
        validate_migration_approval(
            receipt,
            expected_kind="embeddings",
            allowed_scope="fixture",
        )


def test_validator_cli_rejects_missing_receipt(tmp_path: Path):
    from scripts.requirements.validate_obj77_migration_approval import main

    assert main(["--receipt", str(tmp_path / "missing.json")]) == 1
