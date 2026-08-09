"""Stdlib-only crash recovery bootstrap for PB Studio product generations.

This module must stay importable before backend config, logging, databases and
routers. It performs no work when the fixed control root does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any


CONTROL_ROOT_PARTS = ("PB_Studio", "recovery-control", "v1")
JOURNAL_STATES = {
    "PREPARING",
    "STAGED",
    "APPLYING",
    "VALIDATING",
    "COMMITTED",
    "ROLLING_BACK",
}


class RecoveryBootstrapError(RuntimeError):
    """Product data must remain closed because recovery could not converge."""


@dataclass(frozen=True)
class RecoveryBootstrapResult:
    status: str
    generation_id: str | None = None
    degraded_references: tuple[str, ...] = ()


def fixed_control_root() -> Path:
    """Resolve the non-configurable Windows recovery root."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RecoveryBootstrapError("LOCALAPPDATA is unavailable")
    return Path(local_app_data).joinpath(*CONTROL_ROOT_PARTS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryBootstrapError(f"Unreadable recovery JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RecoveryBootstrapError(f"Recovery JSON is not an object: {path}")
    return value


def _fsync_file(handle: Any) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _fsync_parent(path: Path) -> None:
    """Best-effort directory sync; file fsync remains mandatory on Windows."""
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
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            _fsync_file(handle)
        os.replace(temporary, path)
        _fsync_parent(path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _generation_dir(control_root: Path, generation_id: str) -> Path:
    if not generation_id or Path(generation_id).name != generation_id:
        raise RecoveryBootstrapError("Invalid recovery generation ID")
    path = (control_root / "generations" / generation_id).resolve()
    generations_root = (control_root / "generations").resolve()
    if not path.is_relative_to(generations_root):
        raise RecoveryBootstrapError("Recovery generation escapes control root")
    return path


def _load_generation(
    control_root: Path,
    generation_id: str,
    expected_manifest_sha256: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    generation_dir = _generation_dir(control_root, generation_id)
    manifest_path = generation_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RecoveryBootstrapError(
            f"Missing manifest for generation {generation_id}"
        )
    actual_manifest_hash = _sha256(manifest_path)
    if expected_manifest_sha256 and actual_manifest_hash != expected_manifest_sha256:
        raise RecoveryBootstrapError(
            f"Manifest hash mismatch for generation {generation_id}"
        )
    manifest = _read_json(manifest_path)
    if manifest.get("generation_id") != generation_id:
        raise RecoveryBootstrapError("Manifest generation identity mismatch")
    if int(manifest.get("schema_version", 0)) != 1:
        raise RecoveryBootstrapError("Unsupported recovery manifest schema")
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise RecoveryBootstrapError("Manifest artifacts must be a list")
    logical_ids: set[str] = set()
    targets: set[str] = set()
    for artifact in artifacts:
        source, target = _validate_artifact_record(generation_dir, artifact)
        del source
        logical_id = str(artifact.get("logical_id", ""))
        target_key = str(target.resolve()).casefold()
        if not logical_id or logical_id in logical_ids:
            raise RecoveryBootstrapError("Duplicate recovery artifact identity")
        if target_key in targets:
            raise RecoveryBootstrapError("Duplicate recovery artifact target")
        logical_ids.add(logical_id)
        targets.add(target_key)
    return generation_dir, manifest


def _validate_artifact_record(
    generation_dir: Path,
    artifact: Any,
) -> tuple[Path, Path]:
    if not isinstance(artifact, dict):
        raise RecoveryBootstrapError("Invalid artifact record")
    if artifact.get("class") != "owned":
        raise RecoveryBootstrapError("Only owned artifacts may be restore targets")
    relative = Path(str(artifact.get("generation_relpath", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise RecoveryBootstrapError("Artifact path escapes generation")
    source = (generation_dir / relative).resolve()
    if not source.is_relative_to(generation_dir.resolve()):
        raise RecoveryBootstrapError("Artifact source escapes generation")
    target = Path(str(artifact.get("absolute_target", "")))
    if not target.is_absolute():
        raise RecoveryBootstrapError("Artifact target must be absolute")
    control_root = generation_dir.parents[1].resolve()
    if target.resolve().is_relative_to(control_root):
        raise RecoveryBootstrapError("Recovery control root cannot be a target")
    required = bool(artifact.get("required", True))
    if not source.is_file():
        if required:
            raise RecoveryBootstrapError(f"Required generation artifact missing: {source}")
        return source, target
    expected_hash = str(artifact.get("sha256", ""))
    if len(expected_hash) != 64 or _sha256(source) != expected_hash:
        raise RecoveryBootstrapError(f"Generation artifact hash mismatch: {source}")
    expected_size = artifact.get("size")
    if expected_size is not None and source.stat().st_size != int(expected_size):
        raise RecoveryBootstrapError(f"Generation artifact size mismatch: {source}")
    return source, target


def _replace_target(source: Path, target: Path, expected_hash: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.recovery.tmp")
    try:
        with source.open("rb") as input_handle, temporary.open("wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle, 1024 * 1024)
            _fsync_file(output_handle)
        if _sha256(temporary) != expected_hash:
            raise RecoveryBootstrapError(f"Staged target hash mismatch: {target}")
        try:
            os.replace(temporary, target)
        except OSError as exc:
            raise RecoveryBootstrapError(
                f"Recovery target is busy or unavailable: {target}"
            ) from exc
        _fsync_parent(target)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _apply_generation(
    control_root: Path,
    generation_id: str,
    manifest_sha256: str | None,
    journal: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    generation_dir, manifest = _load_generation(
        control_root,
        generation_id,
        manifest_sha256,
    )
    applied = set(str(value) for value in journal.get("applied", []))
    artifacts = manifest.get("artifacts", [])
    for artifact in artifacts:
        source, target = _validate_artifact_record(generation_dir, artifact)
        logical_id = str(artifact.get("logical_id", ""))
        if not source.is_file():
            continue
        expected_hash = str(artifact["sha256"])
        if not target.is_file() or _sha256(target) != expected_hash:
            _replace_target(source, target, expected_hash)
        if logical_id not in applied:
            applied.add(logical_id)
            journal["applied"] = sorted(applied)
            journal["state"] = "APPLYING"
            _atomic_write_json(control_root / "journal.json", journal)

    degraded = _validate_external_references(manifest)
    for artifact in artifacts:
        _source, target = _validate_artifact_record(generation_dir, artifact)
        if artifact.get("required", True):
            if not target.is_file() or _sha256(target) != artifact.get("sha256"):
                raise RecoveryBootstrapError(f"Restored target failed validation: {target}")
    return manifest, degraded


def _validate_external_references(manifest: dict[str, Any]) -> tuple[str, ...]:
    degraded: list[str] = []
    references = manifest.get("external_references", [])
    if not isinstance(references, list):
        raise RecoveryBootstrapError("External references must be a list")
    for reference in references:
        if not isinstance(reference, dict):
            raise RecoveryBootstrapError("Invalid external reference")
        logical_id = str(reference.get("logical_id", "external"))
        path = Path(str(reference.get("absolute_path", "")))
        expected_hash = str(reference.get("sha256", ""))
        valid = path.is_absolute() and path.is_file()
        if valid and expected_hash:
            valid = _sha256(path) == expected_hash
        if valid:
            continue
        if bool(reference.get("required", False)):
            raise RecoveryBootstrapError(
                f"Required external reference is unavailable: {logical_id}"
            )
        degraded.append(logical_id)
    return tuple(sorted(degraded))


def _current_pointer(control_root: Path) -> dict[str, Any] | None:
    path = control_root / "CURRENT"
    return _read_json(path) if path.is_file() else None


def _commit_current(
    control_root: Path,
    generation_id: str,
    manifest_sha256: str,
) -> None:
    _atomic_write_json(
        control_root / "CURRENT",
        {
            "schema_version": 1,
            "generation_id": generation_id,
            "manifest_sha256": manifest_sha256,
        },
    )


def ensure_recovery_ready(
    control_root: Path | None = None,
) -> RecoveryBootstrapResult:
    """Converge interrupted recovery before any product owner opens data."""
    root = (control_root or fixed_control_root()).resolve()
    if not root.exists():
        return RecoveryBootstrapResult(status="uninitialized")

    journal_path = root / "journal.json"
    journal = _read_json(journal_path) if journal_path.is_file() else None
    current = _current_pointer(root)

    if journal is None:
        if current is None:
            return RecoveryBootstrapResult(status="uninitialized")
        generation_id = str(current.get("generation_id", ""))
        manifest_hash = str(current.get("manifest_sha256", ""))
        _generation_dir_path, manifest = _load_generation(
            root,
            generation_id,
            manifest_hash,
        )
        degraded = _validate_external_references(manifest)
        return RecoveryBootstrapResult("ready", generation_id, degraded)

    state = str(journal.get("state", ""))
    if state not in JOURNAL_STATES:
        raise RecoveryBootstrapError(f"Invalid recovery journal state: {state}")

    next_generation = str(journal.get("next_generation", ""))
    next_manifest_hash = str(journal.get("next_manifest_sha256", "")) or None
    previous_generation = str(journal.get("previous_generation", ""))
    previous_manifest_hash = (
        str(journal.get("previous_manifest_sha256", "")) or None
    )

    operation = str(journal.get("operation", "restore"))
    if operation == "snapshot":
        if state == "PREPARING":
            if current is None:
                journal["state"] = "COMMITTED"
                journal["snapshot_aborted"] = True
                _atomic_write_json(journal_path, journal)
                return RecoveryBootstrapResult("uninitialized")
            current_generation = str(current.get("generation_id", ""))
            current_hash = str(current.get("manifest_sha256", ""))
            _generation_path, current_manifest = _load_generation(
                root,
                current_generation,
                current_hash,
            )
            degraded = _validate_external_references(current_manifest)
            journal["state"] = "COMMITTED"
            journal["snapshot_aborted"] = True
            journal["committed_generation"] = current_generation
            _atomic_write_json(journal_path, journal)
            return RecoveryBootstrapResult(
                "snapshot_aborted",
                current_generation,
                degraded,
            )
        if state == "STAGED":
            if not next_generation or not next_manifest_hash:
                raise RecoveryBootstrapError("Staged snapshot lacks generation identity")
            _generation_path, next_manifest = _load_generation(
                root,
                next_generation,
                next_manifest_hash,
            )
            degraded = _validate_external_references(next_manifest)
            _commit_current(root, next_generation, next_manifest_hash)
            journal["state"] = "COMMITTED"
            journal["committed_generation"] = next_generation
            _atomic_write_json(journal_path, journal)
            return RecoveryBootstrapResult(
                "snapshot_committed",
                next_generation,
                degraded,
            )
        if state == "COMMITTED":
            if current is None:
                raise RecoveryBootstrapError("Committed snapshot lacks CURRENT")
            current_generation = str(current.get("generation_id", ""))
            current_hash = str(current.get("manifest_sha256", ""))
            _generation_path, current_manifest = _load_generation(
                root,
                current_generation,
                current_hash,
            )
            degraded = _validate_external_references(current_manifest)
            return RecoveryBootstrapResult(
                "ready",
                current_generation,
                degraded,
            )
        raise RecoveryBootstrapError(
            f"Snapshot journal cannot enter restore state {state}"
        )
    if operation != "restore":
        raise RecoveryBootstrapError(f"Unknown recovery operation: {operation}")

    if state == "COMMITTED":
        if current is None:
            raise RecoveryBootstrapError("Committed restore lacks CURRENT")
        current_generation = str(current.get("generation_id", ""))
        current_hash = str(current.get("manifest_sha256", ""))
        _generation_path, current_manifest = _load_generation(
            root,
            current_generation,
            current_hash,
        )
        degraded = _validate_external_references(current_manifest)
        return RecoveryBootstrapResult("ready", current_generation, degraded)

    use_next = state in {"STAGED", "APPLYING", "VALIDATING"}
    selected_generation = next_generation if use_next else previous_generation
    selected_manifest_hash = (
        next_manifest_hash if use_next else previous_manifest_hash
    )
    if not selected_generation:
        raise RecoveryBootstrapError("Recovery journal has no usable generation")

    try:
        journal["state"] = "APPLYING" if use_next else "ROLLING_BACK"
        _atomic_write_json(journal_path, journal)
        _manifest, degraded = _apply_generation(
            root,
            selected_generation,
            selected_manifest_hash,
            journal,
        )
    except RecoveryBootstrapError:
        if not use_next or not previous_generation:
            raise
        journal["state"] = "ROLLING_BACK"
        journal["applied"] = []
        _atomic_write_json(journal_path, journal)
        _manifest, degraded = _apply_generation(
            root,
            previous_generation,
            previous_manifest_hash,
            journal,
        )
        selected_generation = previous_generation
        selected_manifest_hash = previous_manifest_hash

    if not selected_manifest_hash:
        manifest_path = _generation_dir(root, selected_generation) / "manifest.json"
        selected_manifest_hash = _sha256(manifest_path)
    journal["state"] = "VALIDATING"
    _atomic_write_json(journal_path, journal)
    _commit_current(root, selected_generation, selected_manifest_hash)
    journal["state"] = "COMMITTED"
    journal["committed_generation"] = selected_generation
    _atomic_write_json(journal_path, journal)
    return RecoveryBootstrapResult("recovered", selected_generation, degraded)


__all__ = [
    "RecoveryBootstrapError",
    "RecoveryBootstrapResult",
    "ensure_recovery_ready",
    "fixed_control_root",
]
