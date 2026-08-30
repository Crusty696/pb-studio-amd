"""Immutable product-generation snapshots for PB Studio recovery.

The module owns only generation creation. Product owners must quiesce their
writes before calling :class:`RecoveryGenerationWriter`; live restore remains a
bootstrap-only operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any, Callable, Literal
import uuid


CONTROL_ROOT_PARTS = ("PB_Studio", "recovery-control", "v1")
MANIFEST_SCHEMA_VERSION = 1
JOURNAL_SCHEMA_VERSION = 1
_GENERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


class RecoveryGenerationError(RuntimeError):
    """A generation could not be created or validated safely."""


class RecoveryGenerationValidationError(RecoveryGenerationError):
    """An immutable generation or one of its receipts is invalid."""


@dataclass(frozen=True)
class CommittedGeneration:
    generation_id: str
    generation_dir: Path
    manifest_path: Path
    manifest_sha256: str


@dataclass(frozen=True)
class RetentionPlan:
    """Read-only retention decision; callers must perform deletion separately."""

    protected: tuple[str, ...]
    retained: tuple[str, ...]
    delete_candidates: tuple[str, ...]
    unreadable: tuple[str, ...]


def request_restore_generation(
    generation_id: str,
    *,
    control_root: str | Path | None = None,
) -> Path:
    """Durably request a bootstrap-only restore for the next process start."""
    root = Path(control_root or fixed_control_root()).resolve()
    selected = _validate_generation_id(generation_id)
    manifest = validate_generation(root, selected)
    selected_hash = _sha256(_generation_dir(root, selected) / "manifest.json")

    journal_path = root / "journal.json"
    if journal_path.is_file():
        existing = _read_json(journal_path)
        if existing.get("state") != "COMMITTED":
            raise RecoveryGenerationError(
                "Pending recovery journal must converge before restore"
            )
        validate_committed_journal(root, existing)
    current_generation: str | None = None
    current_hash: str | None = None
    current = load_current_generation(root)
    if current is not None:
        current_generation, current_hash, _manifest = current
    _atomic_write_json(
        journal_path,
        {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "operation": "restore",
            "state": "STAGED",
            "previous_generation": current_generation,
            "previous_manifest_sha256": current_hash,
            "next_generation": selected,
            "next_manifest_sha256": selected_hash,
            "applied": [],
            "external_reference_count": len(manifest.get("external_references", [])),
            "updated_at": _utc_now(),
        },
    )
    return journal_path


@dataclass(frozen=True)
class _ArtifactSpec:
    logical_id: str
    group: str
    owner: str
    source_path: Path
    absolute_target: Path
    required: bool
    adapter: Literal["file", "sqlite_backup"]
    restore_policy: str
    schema_version: int | None
    owner_scope: Path | None


@dataclass(frozen=True)
class _ExternalReferenceSpec:
    logical_id: str
    group: str
    owner: str
    absolute_path: Path
    required: bool
    degraded_mode_policy: str


def fixed_control_root() -> Path:
    """Return the non-configurable recovery root without consulting Config."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RecoveryGenerationError("LOCALAPPDATA is unavailable")
    return Path(local_app_data).joinpath(*CONTROL_ROOT_PARTS)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_generation_id(generation_id: str) -> str:
    if (
        generation_id in {".", ".."}
        or not _GENERATION_ID_RE.fullmatch(generation_id)
        or Path(generation_id).name != generation_id
    ):
        raise RecoveryGenerationError("Invalid recovery generation ID")
    return generation_id


def _validate_digest(value: str | None, field_name: str) -> str | None:
    if value is not None and not _DIGEST_RE.fullmatch(value):
        raise RecoveryGenerationError(f"{field_name} must be a SHA-256 digest")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(handle: Any) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _fsync_parent(path: Path) -> None:
    """Best-effort directory sync; mandatory file fsync happens separately."""
    flags = getattr(os, "O_RDONLY", 0)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(path.parent), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            _fsync_file(handle)
        os.replace(temporary, path)
        _fsync_parent(path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryGenerationValidationError(
            f"Unreadable recovery JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecoveryGenerationValidationError(
            f"Recovery JSON is not an object: {path}"
        )
    return value


def _volume_id(path: Path) -> str:
    resolved = path.resolve()
    return (resolved.drive or resolved.anchor or "unknown").casefold()


def _generation_dir(control_root: Path, generation_id: str) -> Path:
    safe_id = _validate_generation_id(generation_id)
    generations_root = (control_root / "generations").resolve()
    result = (generations_root / safe_id).resolve()
    if not result.is_relative_to(generations_root):
        raise RecoveryGenerationError("Generation path escapes control root")
    return result


def _artifact_relpath(index: int, logical_id: str, source: Path) -> Path:
    identity = hashlib.sha256(logical_id.encode("utf-8")).hexdigest()[:16]
    suffix = "".join(source.suffixes)[-32:]
    return Path("artifacts") / f"{index:04d}-{identity}{suffix}"


def _copy_file_durable(source: Path, destination: Path) -> None:
    before = source.stat()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle, 1024 * 1024)
        _fsync_file(output_handle)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RecoveryGenerationError(f"Artifact changed while copied: {source}")
    _fsync_parent(destination)


def _backup_sqlite(source: Path, destination: Path) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(str(source), timeout=30.0)
        destination_connection = sqlite3.connect(str(destination), timeout=30.0)
        source_connection.backup(destination_connection)
        destination_connection.commit()
        # integrity_check statt quick_check: quick_check prueft die
        # Uebereinstimmung von Tabelle und Index NICHT. Genau diese
        # Fehlerklasse ("row N missing from index") lag am 2026-08-29 im
        # Snapshot der Produktionsdatenbank vor, kam durch dieses Gatter und
        # wurde beim naechsten Recovery-Restore in die Live-Datenbank
        # zurueckgespielt. Auf der 29-MB-Datenbank gemessen kosten beide
        # Pragmas dasselbe (je 14,5 ms) - die laxere Pruefung kaufte nichts.
        findings = [
            str(row[0])
            for row in destination_connection.execute("PRAGMA integrity_check")
        ]
        integrity_check = findings[0] if findings else "unknown"
        if findings != ["ok"]:
            raise RecoveryGenerationValidationError(
                f"SQLite backup failed integrity_check: {source}: "
                + "; ".join(findings[:5])
            )
        user_version = int(
            destination_connection.execute("PRAGMA user_version").fetchone()[0]
        )
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
    # Windows rejects FlushFileBuffers for a read-only descriptor. The backup
    # is closed above, so opening it read/write here cannot race SQLite.
    with destination.open("r+b") as handle:
        os.fsync(handle.fileno())
    _fsync_parent(destination)
    return user_version, integrity_check


def validate_generation(
    control_root: str | Path,
    generation_id: str,
    *,
    expected_manifest_sha256: str | None = None,
    validate_external_references: bool = False,
) -> dict[str, Any]:
    """Validate one immutable generation and return its manifest."""
    root = Path(control_root).resolve()
    generation_dir = _generation_dir(root, generation_id)
    manifest_path = generation_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RecoveryGenerationValidationError(
            f"Missing generation manifest: {generation_id}"
        )
    actual_manifest_hash = _sha256(manifest_path)
    if (
        expected_manifest_sha256 is not None
        and actual_manifest_hash != expected_manifest_sha256
    ):
        raise RecoveryGenerationValidationError("Manifest hash mismatch")
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RecoveryGenerationValidationError("Unsupported manifest schema")
    if manifest.get("generation_id") != generation_id:
        raise RecoveryGenerationValidationError("Manifest generation mismatch")
    if "config_digest" not in manifest or "project_inventory_digest" not in manifest:
        raise RecoveryGenerationValidationError("Manifest inventory digests missing")

    artifacts = manifest.get("artifacts")
    references = manifest.get("external_references")
    if not isinstance(artifacts, list) or not isinstance(references, list):
        raise RecoveryGenerationValidationError("Invalid manifest collections")

    logical_ids: set[str] = set()
    targets: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise RecoveryGenerationValidationError("Invalid artifact record")
        logical_id = str(artifact.get("logical_id", ""))
        if not logical_id or logical_id in logical_ids:
            raise RecoveryGenerationValidationError("Duplicate artifact identity")
        logical_ids.add(logical_id)
        if artifact.get("class") != "owned":
            raise RecoveryGenerationValidationError("Artifact must be owned")
        if artifact.get("adapter") not in {"file", "sqlite_backup"}:
            raise RecoveryGenerationValidationError("Unknown artifact adapter")
        restore_policy = str(artifact.get("restore_policy", "replace"))
        if restore_policy not in {"replace", "delete_if_present"}:
            raise RecoveryGenerationValidationError("Unknown artifact restore policy")
        target = Path(str(artifact.get("absolute_target", "")))
        if not target.is_absolute() or str(target).casefold() in targets:
            raise RecoveryGenerationValidationError("Invalid artifact target")
        targets.add(str(target).casefold())
        if restore_policy == "delete_if_present":
            owner_scope = Path(str(artifact.get("owner_scope", "")))
            if (
                not owner_scope.is_absolute()
                or not target.resolve().is_relative_to(owner_scope.resolve())
            ):
                raise RecoveryGenerationValidationError(
                    "Delete artifact lacks a valid owner scope"
                )
        relative = Path(str(artifact.get("generation_relpath", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise RecoveryGenerationValidationError("Artifact path escapes generation")
        staged = (generation_dir / relative).resolve()
        if not staged.is_relative_to(generation_dir.resolve()) or not staged.is_file():
            raise RecoveryGenerationValidationError("Generation artifact missing")
        if staged.stat().st_size != int(artifact.get("size", -1)):
            raise RecoveryGenerationValidationError("Generation artifact size mismatch")
        if _sha256(staged) != artifact.get("sha256"):
            raise RecoveryGenerationValidationError("Generation artifact hash mismatch")
        if artifact.get("adapter") == "sqlite_backup":
            connection = sqlite3.connect(str(staged))
            try:
                quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
                user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            finally:
                connection.close()
            if quick_check != "ok" or user_version != int(artifact["user_version"]):
                raise RecoveryGenerationValidationError("SQLite receipt mismatch")

    for reference in references:
        if not isinstance(reference, dict):
            raise RecoveryGenerationValidationError("Invalid external reference")
        logical_id = str(reference.get("logical_id", ""))
        if not logical_id or logical_id in logical_ids:
            raise RecoveryGenerationValidationError("Duplicate reference identity")
        logical_ids.add(logical_id)
        if reference.get("class") != "external":
            raise RecoveryGenerationValidationError("Reference must be external")
        path = Path(str(reference.get("absolute_path", "")))
        if not path.is_absolute():
            raise RecoveryGenerationValidationError("External path must be absolute")
        if validate_external_references and bool(reference.get("available")):
            if not path.is_file() or _sha256(path) != reference.get("sha256"):
                raise RecoveryGenerationValidationError(
                    f"External reference changed: {logical_id}"
                )
        if bool(reference.get("required")) and not bool(reference.get("available")):
            raise RecoveryGenerationValidationError(
                f"Required external reference missing: {logical_id}"
            )
    return manifest


def load_current_generation(
    control_root: str | Path,
) -> tuple[str, str, dict[str, Any]] | None:
    """Return the fully validated CURRENT generation, if one exists."""
    root = Path(control_root).resolve()
    current_path = root / "CURRENT"
    if not current_path.is_file():
        return None
    current = _read_json(current_path)
    if current.get("schema_version") != 1:
        raise RecoveryGenerationValidationError("Unsupported CURRENT schema")
    generation_id = _validate_generation_id(str(current.get("generation_id", "")))
    manifest_hash = str(current.get("manifest_sha256", ""))
    _validate_digest(manifest_hash, "CURRENT manifest_sha256")
    manifest = validate_generation(
        root,
        generation_id,
        expected_manifest_sha256=manifest_hash,
    )
    return generation_id, manifest_hash, manifest


def validate_committed_journal(
    control_root: str | Path,
    journal: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Bind a terminal journal receipt exactly to CURRENT."""
    root = Path(control_root).resolve()
    value = journal or _read_json(root / "journal.json")
    if value.get("state") != "COMMITTED":
        raise RecoveryGenerationValidationError("Recovery journal is not committed")
    current = load_current_generation(root)
    if current is None:
        raise RecoveryGenerationValidationError("Committed journal lacks CURRENT")
    current_generation, current_hash, _manifest = current
    committed_generation = _validate_generation_id(
        str(value.get("committed_generation", ""))
    )
    committed_hash = str(value.get("committed_manifest_sha256", ""))
    if not committed_hash:
        if committed_generation == str(value.get("next_generation", "")):
            committed_hash = str(value.get("next_manifest_sha256", ""))
        elif committed_generation == str(value.get("previous_generation", "")):
            committed_hash = str(value.get("previous_manifest_sha256", ""))
    _validate_digest(committed_hash, "committed_manifest_sha256")
    if (
        committed_generation != current_generation
        or committed_hash != current_hash
    ):
        raise RecoveryGenerationValidationError(
            "Committed recovery journal does not match CURRENT"
        )
    return committed_generation, committed_hash


class RecoveryGenerationWriter:
    """Build and publish one immutable recovery generation."""

    def __init__(
        self,
        *,
        control_root: str | Path | None = None,
        generation_id: str | None = None,
        config_digest: str | None = None,
        project_inventory_digest: str | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.control_root = Path(control_root or fixed_control_root()).resolve()
        self.generation_id = _validate_generation_id(
            generation_id
            or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex}"
        )
        self.config_digest = _validate_digest(config_digest, "config_digest")
        self.project_inventory_digest = _validate_digest(
            project_inventory_digest,
            "project_inventory_digest",
        )
        self._fault_injector = fault_injector
        self._artifacts: list[_ArtifactSpec] = []
        self._external_references: list[_ExternalReferenceSpec] = []
        self._logical_ids: set[str] = set()
        self._targets: set[str] = set()
        self._committed = False

    def add_file(
        self,
        logical_id: str,
        source_path: str | Path,
        *,
        group: str,
        owner: str,
        absolute_target: str | Path | None = None,
        required: bool = True,
        restore_policy: str = "replace",
        schema_version: int | None = None,
        owner_scope: str | Path | None = None,
    ) -> None:
        self._add_artifact(
            logical_id,
            source_path,
            group=group,
            owner=owner,
            absolute_target=absolute_target,
            required=required,
            adapter="file",
            restore_policy=restore_policy,
            schema_version=schema_version,
            owner_scope=owner_scope,
        )

    def add_sqlite(
        self,
        logical_id: str,
        source_path: str | Path,
        *,
        group: str,
        owner: str,
        absolute_target: str | Path | None = None,
        required: bool = True,
        restore_policy: str = "replace",
        owner_scope: str | Path | None = None,
    ) -> None:
        self._add_artifact(
            logical_id,
            source_path,
            group=group,
            owner=owner,
            absolute_target=absolute_target,
            required=required,
            adapter="sqlite_backup",
            restore_policy=restore_policy,
            schema_version=None,
            owner_scope=owner_scope,
        )

    def _add_artifact(
        self,
        logical_id: str,
        source_path: str | Path,
        *,
        group: str,
        owner: str,
        absolute_target: str | Path | None,
        required: bool,
        adapter: Literal["file", "sqlite_backup"],
        restore_policy: str,
        schema_version: int | None,
        owner_scope: str | Path | None,
    ) -> None:
        self._require_mutable()
        logical_id = self._validate_new_logical_id(logical_id)
        source = Path(source_path).resolve()
        raw_target = Path(absolute_target) if absolute_target is not None else source
        if not raw_target.is_absolute():
            raise RecoveryGenerationError("Artifact target must be absolute")
        target = raw_target.resolve()
        if source.is_relative_to(self.control_root) or target.is_relative_to(
            self.control_root
        ):
            raise RecoveryGenerationError("The recovery control root cannot snapshot itself")
        target_key = str(target).casefold()
        if target_key in self._targets:
            raise RecoveryGenerationError("Duplicate artifact target")
        group = self._required_text(group, "group")
        owner = self._required_text(owner, "owner")
        restore_policy = self._required_text(restore_policy, "restore_policy")
        resolved_owner_scope: Path | None = None
        if owner_scope is not None:
            raw_scope = Path(owner_scope)
            if not raw_scope.is_absolute():
                raise RecoveryGenerationError("Artifact owner scope must be absolute")
            resolved_owner_scope = raw_scope.resolve()
        if restore_policy == "delete_if_present":
            if resolved_owner_scope is None or not target.is_relative_to(
                resolved_owner_scope
            ):
                raise RecoveryGenerationError(
                    "Delete artifact target must be inside its owner scope"
                )
        self._logical_ids.add(logical_id)
        self._targets.add(target_key)
        self._artifacts.append(
            _ArtifactSpec(
                logical_id=logical_id,
                group=group,
                owner=owner,
                source_path=source,
                absolute_target=target,
                required=bool(required),
                adapter=adapter,
                restore_policy=restore_policy,
                schema_version=schema_version,
                owner_scope=resolved_owner_scope,
            )
        )

    def add_external_reference(
        self,
        logical_id: str,
        absolute_path: str | Path,
        *,
        group: str,
        owner: str,
        required: bool = False,
        degraded_mode_policy: str = "report_unavailable",
    ) -> None:
        self._require_mutable()
        logical_id = self._validate_new_logical_id(logical_id)
        raw_path = Path(absolute_path)
        if not raw_path.is_absolute():
            raise RecoveryGenerationError("External reference must be absolute")
        path = raw_path.resolve()
        group = self._required_text(group, "group")
        owner = self._required_text(owner, "owner")
        degraded_mode_policy = self._required_text(
            degraded_mode_policy,
            "degraded_mode_policy",
        )
        self._logical_ids.add(logical_id)
        self._external_references.append(
            _ExternalReferenceSpec(
                logical_id=logical_id,
                group=group,
                owner=owner,
                absolute_path=path,
                required=bool(required),
                degraded_mode_policy=degraded_mode_policy,
            )
        )

    def commit(self) -> CommittedGeneration:
        self._require_mutable()
        self._validate_sources()
        self._validate_existing_journal()
        previous_generation, previous_manifest_hash = self._read_current()

        generations_root = self.control_root / "generations"
        generation_dir = _generation_dir(self.control_root, self.generation_id)
        staging_dir = generations_root / f".{self.generation_id}.preparing"
        if generation_dir.exists() or staging_dir.exists():
            raise RecoveryGenerationError("Generation ID is not immutable/unique")
        staging_dir.mkdir(parents=True, exist_ok=False)
        _fsync_parent(staging_dir)

        journal = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "operation": "snapshot",
            "state": "PREPARING",
            "previous_generation": previous_generation,
            "previous_manifest_sha256": previous_manifest_hash,
            "next_generation": self.generation_id,
            "next_manifest_sha256": None,
            "applied": [],
            "updated_at": _utc_now(),
        }
        journal_path = self.control_root / "journal.json"
        _atomic_write_json(journal_path, journal)
        self._inject_fault("after_preparing")

        artifact_records = [
            self._stage_artifact(staging_dir, index, artifact)
            for index, artifact in enumerate(self._artifacts, start=1)
        ]
        external_records = [
            self._external_receipt(reference)
            for reference in self._external_references
        ]
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generation_id": self.generation_id,
            "parent_generation": previous_generation,
            "created_at": _utc_now(),
            "config_digest": self.config_digest,
            "project_inventory_digest": self.project_inventory_digest,
            "artifacts": artifact_records,
            "external_references": external_records,
        }
        manifest_path = staging_dir / "manifest.json"
        _atomic_write_json(manifest_path, manifest)
        manifest_hash = _sha256(manifest_path)
        self._validate_staging(staging_dir, manifest)

        os.replace(staging_dir, generation_dir)
        _fsync_parent(generation_dir)
        validate_generation(
            self.control_root,
            self.generation_id,
            expected_manifest_sha256=manifest_hash,
        )
        journal.update(
            state="STAGED",
            next_manifest_sha256=manifest_hash,
            updated_at=_utc_now(),
        )
        _atomic_write_json(journal_path, journal)
        self._inject_fault("after_staged")

        _atomic_write_json(
            self.control_root / "CURRENT",
            {
                "schema_version": 1,
                "generation_id": self.generation_id,
                "manifest_sha256": manifest_hash,
            },
        )
        self._inject_fault("after_current")
        journal.update(
            state="COMMITTED",
            committed_generation=self.generation_id,
            committed_manifest_sha256=manifest_hash,
            updated_at=_utc_now(),
        )
        _atomic_write_json(journal_path, journal)
        self._committed = True
        return CommittedGeneration(
            generation_id=self.generation_id,
            generation_dir=generation_dir,
            manifest_path=generation_dir / "manifest.json",
            manifest_sha256=manifest_hash,
        )

    def _stage_artifact(
        self,
        staging_dir: Path,
        index: int,
        artifact: _ArtifactSpec,
    ) -> dict[str, Any]:
        relative = _artifact_relpath(index, artifact.logical_id, artifact.source_path)
        destination = staging_dir / relative
        user_version: int | None = None
        quick_check: str | None = None
        if artifact.adapter == "sqlite_backup":
            user_version, quick_check = _backup_sqlite(
                artifact.source_path,
                destination,
            )
        else:
            _copy_file_durable(artifact.source_path, destination)
        record: dict[str, Any] = {
            "logical_id": artifact.logical_id,
            "group": artifact.group,
            "owner": artifact.owner,
            "class": "owned",
            "required": artifact.required,
            "absolute_target": str(artifact.absolute_target),
            "volume_id": _volume_id(artifact.absolute_target),
            "generation_relpath": relative.as_posix(),
            "size": destination.stat().st_size,
            "sha256": _sha256(destination),
            "adapter": artifact.adapter,
            "restore_policy": artifact.restore_policy,
            "schema_version": artifact.schema_version,
            "owner_scope": (
                str(artifact.owner_scope)
                if artifact.owner_scope is not None
                else None
            ),
        }
        if artifact.adapter == "sqlite_backup":
            record["user_version"] = user_version
            record["quick_check"] = quick_check
        self._inject_fault(f"after_artifact:{artifact.logical_id}")
        return record

    def _external_receipt(
        self,
        reference: _ExternalReferenceSpec,
    ) -> dict[str, Any]:
        available = reference.absolute_path.is_file()
        if reference.required and not available:
            raise RecoveryGenerationError(
                f"Required external reference missing: {reference.logical_id}"
            )
        stat = reference.absolute_path.stat() if available else None
        content_hash = _sha256(reference.absolute_path) if available else ""
        if available:
            confirmed_stat = reference.absolute_path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (
                confirmed_stat.st_size,
                confirmed_stat.st_mtime_ns,
            ):
                raise RecoveryGenerationError(
                    f"External reference changed while hashed: {reference.logical_id}"
                )
        return {
            "logical_id": reference.logical_id,
            "group": reference.group,
            "owner": reference.owner,
            "class": "external",
            "required": reference.required,
            "absolute_path": str(reference.absolute_path),
            "volume_id": _volume_id(reference.absolute_path),
            "available": available,
            "size": stat.st_size if stat is not None else None,
            "mtime_ns": stat.st_mtime_ns if stat is not None else None,
            "sha256": content_hash,
            "degraded_mode_policy": reference.degraded_mode_policy,
        }

    def _validate_staging(
        self,
        staging_dir: Path,
        manifest: dict[str, Any],
    ) -> None:
        for artifact in manifest["artifacts"]:
            staged = staging_dir / artifact["generation_relpath"]
            if staged.stat().st_size != artifact["size"]:
                raise RecoveryGenerationValidationError("Staged artifact size mismatch")
            if _sha256(staged) != artifact["sha256"]:
                raise RecoveryGenerationValidationError("Staged artifact hash mismatch")
        for reference in manifest["external_references"]:
            if reference["required"] and not reference["available"]:
                raise RecoveryGenerationValidationError(
                    "Required external reference unavailable"
                )

    def _validate_sources(self) -> None:
        for artifact in self._artifacts:
            if not artifact.source_path.is_file():
                if artifact.required:
                    raise RecoveryGenerationError(
                        f"Required artifact source missing: {artifact.logical_id}"
                    )
                raise RecoveryGenerationError(
                    "Optional owned artifacts must be omitted by their owner adapter"
                )
            if artifact.adapter == "sqlite_backup":
                connection = sqlite3.connect(str(artifact.source_path))
                try:
                    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise RecoveryGenerationValidationError(
                            f"SQLite source failed quick_check: {artifact.logical_id}"
                        )
                finally:
                    connection.close()
        for reference in self._external_references:
            if reference.required and not reference.absolute_path.is_file():
                raise RecoveryGenerationError(
                    f"Required external reference missing: {reference.logical_id}"
                )

    def _validate_existing_journal(self) -> None:
        path = self.control_root / "journal.json"
        if not path.is_file():
            return
        journal = _read_json(path)
        if journal.get("state") != "COMMITTED":
            raise RecoveryGenerationError(
                "Pending recovery journal must converge before a new snapshot"
            )
        validate_committed_journal(self.control_root, journal)

    def _read_current(self) -> tuple[str | None, str | None]:
        current = load_current_generation(self.control_root)
        if current is None:
            return None, None
        generation_id, manifest_hash, _manifest = current
        return generation_id, manifest_hash

    def _validate_new_logical_id(self, logical_id: str) -> str:
        normalized = self._required_text(logical_id, "logical_id")
        if normalized in self._logical_ids:
            raise RecoveryGenerationError("Duplicate logical artifact ID")
        return normalized

    def _require_mutable(self) -> None:
        if self._committed:
            raise RecoveryGenerationError("Committed generation writer is immutable")

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise RecoveryGenerationError(f"{field_name} must not be empty")
        return normalized

    def _inject_fault(self, stage: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage)


def plan_protected_retention(
    control_root: str | Path | None = None,
    *,
    keep_latest: int = 4,
    additionally_protected: tuple[str, ...] = (),
) -> RetentionPlan:
    """Return a protected retention plan without deleting any generation."""
    if keep_latest < 0:
        raise ValueError("keep_latest must be non-negative")
    root = Path(control_root or fixed_control_root()).resolve()
    generations_root = root / "generations"
    if not generations_root.is_dir():
        return RetentionPlan((), (), (), ())

    protected = {
        _validate_generation_id(generation_id)
        for generation_id in additionally_protected
    }
    current_path = root / "CURRENT"
    if current_path.is_file():
        current = _read_json(current_path)
        current_id = _validate_generation_id(str(current.get("generation_id", "")))
        protected.add(current_id)
        try:
            current_manifest = validate_generation(root, current_id)
            parent = current_manifest.get("parent_generation")
            if parent:
                protected.add(_validate_generation_id(str(parent)))
        except RecoveryGenerationError:
            protected.add(current_id)

    journal_path = root / "journal.json"
    if journal_path.is_file():
        journal = _read_json(journal_path)
        for key in (
            "previous_generation",
            "next_generation",
            "committed_generation",
        ):
            value = journal.get(key)
            if value:
                protected.add(_validate_generation_id(str(value)))

    sortable: list[tuple[str, str]] = []
    unreadable: set[str] = set()
    for child in generations_root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            generation_id = _validate_generation_id(child.name)
            manifest = validate_generation(root, generation_id)
            sortable.append((str(manifest.get("created_at", "")), generation_id))
        except RecoveryGenerationError:
            unreadable.add(child.name)

    ordered = [generation_id for _created, generation_id in sorted(sortable, reverse=True)]
    retained = protected | set(ordered[:keep_latest]) | unreadable
    known = set(ordered) | unreadable
    return RetentionPlan(
        protected=tuple(sorted(protected)),
        retained=tuple(sorted(retained)),
        delete_candidates=tuple(sorted(known - retained)),
        unreadable=tuple(sorted(unreadable)),
    )


def apply_protected_retention(
    control_root: str | Path | None = None,
    *,
    keep_latest: int = 4,
    additionally_protected: tuple[str, ...] = (),
    confirmed_delete_candidates: tuple[str, ...],
) -> RetentionPlan:
    """Delete only an exact, previously reviewed retention candidate set."""
    root = Path(control_root or fixed_control_root()).resolve()
    plan = plan_protected_retention(
        root,
        keep_latest=keep_latest,
        additionally_protected=additionally_protected,
    )
    confirmed = tuple(sorted(
        _validate_generation_id(value) for value in confirmed_delete_candidates
    ))
    if confirmed != plan.delete_candidates:
        raise RecoveryGenerationError(
            "Retention candidates changed; obtain a new confirmed plan"
        )
    generations_root = (root / "generations").resolve()
    for generation_id in confirmed:
        target = _generation_dir(root, generation_id)
        if not target.is_relative_to(generations_root) or not target.is_dir():
            raise RecoveryGenerationError("Retention target is not a generation")
        shutil.rmtree(target)
        _fsync_parent(target)
    return plan


__all__ = [
    "CommittedGeneration",
    "MANIFEST_SCHEMA_VERSION",
    "RecoveryGenerationError",
    "RecoveryGenerationValidationError",
    "RecoveryGenerationWriter",
    "RetentionPlan",
    "apply_protected_retention",
    "fixed_control_root",
    "load_current_generation",
    "plan_protected_retention",
    "request_restore_generation",
    "validate_committed_journal",
    "validate_generation",
]
