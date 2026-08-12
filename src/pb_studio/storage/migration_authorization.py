"""Fail-closed authorization contract for explicit OBJ77 SQLite migrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
import uuid


_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = {"embeddings": (1, 2), "catalog": (4, 5)}
_REQUIRED = {
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


class MigrationApprovalError(RuntimeError):
    """An approval receipt is absent, stale, ambiguous, or out of scope."""


class DatabaseMigrationRequiredError(RuntimeError):
    """An existing catalog requires the separately approved OBJ77 migration."""


@dataclass(frozen=True)
class MigrationAuthorization:
    operation_id: str
    bundle_id: str
    scope: Literal["fixture", "real"]
    target_kind: Literal["embeddings", "catalog"]
    target_path: Path
    source_sha256: str
    source_bundle_sha256: str
    source_schema_version: int
    target_schema_version: int
    project_uuid: str | None
    backup_path: Path
    backup_sha256: str
    backup_bundle_sha256: str
    rollback_command: str
    approved_at_utc: str
    approval_source: str
    receipt_sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sqlite_bundle_sha256(path: str | Path) -> str:
    target = Path(path).resolve()
    digest = hashlib.sha256()
    for suffix in ("", "-wal", "-shm"):
        member = Path(str(target) + suffix)
        digest.update(suffix.encode("ascii"))
        if member.is_file():
            digest.update(str(member.stat().st_size).encode("ascii"))
            digest.update(bytes.fromhex(sha256_file(member)))
        else:
            digest.update(b"absent")
    return digest.hexdigest()


def _rollback_command(backup: Path, target: Path) -> str:
    copied = (
        "Copy-Item -LiteralPath "
        f"'{str(backup).replace(chr(39), chr(39) * 2)}' "
        "-Destination "
        f"'{str(target).replace(chr(39), chr(39) * 2)}' -Force"
    )
    sidecars = ",".join(
        f"'{(str(target) + suffix).replace(chr(39), chr(39) * 2)}'"
        for suffix in ("-wal", "-shm")
    )
    return f"{copied}; Remove-Item -LiteralPath {sidecars} -ErrorAction SilentlyContinue"


def _canonical_uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise MigrationApprovalError(f"{field} must be a UUID") from exc


def _utc(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MigrationApprovalError("approved_at_utc must be canonical UTC-Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MigrationApprovalError("approved_at_utc is invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise MigrationApprovalError("approved_at_utc must be UTC")
    return value


def _absolute_file_path(value: Any, field: str) -> Path:
    if not isinstance(value, str):
        raise MigrationApprovalError(f"{field} must be a path string")
    raw = Path(value)
    if not raw.is_absolute():
        raise MigrationApprovalError(f"{field} must be absolute")
    return raw.resolve()


def _fixture_sandbox(path: Path) -> Path:
    for parent in (path, *path.parents):
        if parent.name == ".obj77-migration-sandbox":
            return parent.resolve()
    raise MigrationApprovalError("Fixture target is outside .obj77-migration-sandbox")


def prepare_fixture_approval(
    *,
    target_path: str | Path,
    target_kind: Literal["embeddings", "catalog"],
    source_schema_version: int,
    target_schema_version: int,
    project_uuid: str | None,
    backup_path: str | Path,
    approved_at_utc: str,
    approval_source: str,
    operation_id: str | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    target = Path(target_path).resolve()
    backup = Path(backup_path).resolve()
    sandbox = _fixture_sandbox(target)
    if not backup.is_relative_to(sandbox) or backup == target:
        raise MigrationApprovalError("Fixture backup must be a distinct sandbox path")
    if not target.is_file():
        raise MigrationApprovalError("Fixture target does not exist")
    source_hash = sha256_file(target)
    bundle_hash = sqlite_bundle_sha256(target)
    return {
        "schema_version": 1,
        "operation_id": str(uuid.UUID(operation_id)) if operation_id else str(uuid.uuid4()),
        "bundle_id": str(uuid.UUID(bundle_id)) if bundle_id else str(uuid.uuid4()),
        "scope": "fixture",
        "target_kind": target_kind,
        "target_path": str(target),
        "source_sha256": source_hash,
        "source_bundle_sha256": bundle_hash,
        "source_schema_version": int(source_schema_version),
        "target_schema_version": int(target_schema_version),
        "project_uuid": _canonical_uuid(project_uuid, "project_uuid") if project_uuid else None,
        "backup_path": str(backup),
        "backup_sha256": source_hash,
        "backup_bundle_sha256": bundle_hash,
        "rollback_command": _rollback_command(backup, target),
        "approved": True,
        "approved_at_utc": _utc(approved_at_utc),
        "approval_source": str(approval_source),
    }


def validate_migration_approval(
    receipt: dict[str, Any],
    *,
    expected_kind: Literal["embeddings", "catalog"] | None = None,
    allowed_scope: Literal["fixture", "real"],
    verify_source: bool = True,
) -> MigrationAuthorization:
    if not isinstance(receipt, dict) or set(receipt) != _REQUIRED:
        raise MigrationApprovalError("Approval receipt fields do not match schema")
    if receipt.get("schema_version") != 1 or receipt.get("approved") is not True:
        raise MigrationApprovalError("Approval receipt is not approved v1")
    scope = receipt.get("scope")
    if scope != allowed_scope:
        raise MigrationApprovalError("Approval scope is not authorized for this run")
    kind = receipt.get("target_kind")
    if kind not in _KINDS or (expected_kind is not None and kind != expected_kind):
        raise MigrationApprovalError("Unexpected migration target kind")
    source_version, target_version = _KINDS[kind]
    if (
        type(receipt.get("source_schema_version")) is not int
        or receipt["source_schema_version"] != source_version
        or type(receipt.get("target_schema_version")) is not int
        or receipt["target_schema_version"] != target_version
    ):
        raise MigrationApprovalError("Approval schema versions are not canonical")
    operation_id = _canonical_uuid(receipt.get("operation_id"), "operation_id")
    bundle_id = _canonical_uuid(receipt.get("bundle_id"), "bundle_id")
    project_uuid = receipt.get("project_uuid")
    normalized_project_uuid = (
        _canonical_uuid(project_uuid, "project_uuid") if project_uuid is not None else None
    )
    if kind == "embeddings" and normalized_project_uuid is None:
        raise MigrationApprovalError("Embedding target requires project_uuid")
    target = _absolute_file_path(receipt.get("target_path"), "target_path")
    backup = _absolute_file_path(receipt.get("backup_path"), "backup_path")
    if target == backup:
        raise MigrationApprovalError("Backup must differ from target")
    if scope == "fixture":
        sandbox = _fixture_sandbox(target)
        if not backup.is_relative_to(sandbox):
            raise MigrationApprovalError("Fixture backup escapes sandbox")
    if not target.is_file():
        raise MigrationApprovalError("Migration target is missing")
    for field in (
        "source_sha256",
        "source_bundle_sha256",
        "backup_sha256",
        "backup_bundle_sha256",
    ):
        if not isinstance(receipt.get(field), str) or not _DIGEST_RE.fullmatch(receipt[field]):
            raise MigrationApprovalError(f"{field} is not SHA-256")
    if verify_source and receipt["source_sha256"] != sha256_file(target):
        raise MigrationApprovalError("Migration target hash changed after approval")
    if verify_source and receipt["source_bundle_sha256"] != sqlite_bundle_sha256(target):
        raise MigrationApprovalError("Migration SQLite bundle changed after approval")
    if receipt["backup_sha256"] != receipt["source_sha256"]:
        raise MigrationApprovalError("Closed fixture backup hash must equal source hash")
    if receipt["backup_bundle_sha256"] != receipt["source_bundle_sha256"]:
        raise MigrationApprovalError("Backup bundle hash must equal source bundle hash")
    rollback = receipt.get("rollback_command")
    if rollback != _rollback_command(backup, target):
        raise MigrationApprovalError("Rollback command does not match exact paths")
    approved_at = _utc(receipt.get("approved_at_utc"))
    approval_source = receipt.get("approval_source")
    if not isinstance(approval_source, str) or len(approval_source.strip()) < 3:
        raise MigrationApprovalError("approval_source is missing")
    return MigrationAuthorization(
        operation_id=operation_id,
        bundle_id=bundle_id,
        scope=scope,
        target_kind=kind,
        target_path=target,
        source_sha256=receipt["source_sha256"],
        source_bundle_sha256=receipt["source_bundle_sha256"],
        source_schema_version=source_version,
        target_schema_version=target_version,
        project_uuid=normalized_project_uuid,
        backup_path=backup,
        backup_sha256=receipt["backup_sha256"],
        backup_bundle_sha256=receipt["backup_bundle_sha256"],
        rollback_command=rollback,
        approved_at_utc=approved_at,
        approval_source=approval_source.strip(),
        receipt_sha256=canonical_json_sha256(receipt),
    )


def read_approval(path: str | Path) -> tuple[dict[str, Any], str]:
    receipt_path = Path(path).resolve()
    try:
        raw = receipt_path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationApprovalError("Approval receipt is unreadable") from exc
    if not isinstance(value, dict):
        raise MigrationApprovalError("Approval receipt must be an object")
    return value, hashlib.sha256(raw).hexdigest()
