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
DELETE_IF_PRESENT = "delete_if_present"
RUNTIME_DIRTY_NAME = "RUNTIME_DIRTY"


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
    restore_policy = str(artifact.get("restore_policy", "replace"))
    if restore_policy not in {"replace", DELETE_IF_PRESENT}:
        raise RecoveryBootstrapError(
            f"Unsupported recovery restore policy: {restore_policy}"
        )
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
    if restore_policy == DELETE_IF_PRESENT:
        _validate_delete_scope(artifact, target)
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


def _validate_delete_scope(artifact: dict[str, Any], target: Path) -> None:
    raw_scope = Path(str(artifact.get("owner_scope", "")))
    if not raw_scope.is_absolute():
        raise RecoveryBootstrapError("Delete artifact lacks an absolute owner scope")
    scope = raw_scope.resolve()
    target = target.resolve()
    if not target.is_relative_to(scope):
        raise RecoveryBootstrapError("Delete artifact escapes its owner scope")
    owner = str(artifact.get("owner", ""))
    name = target.name
    allowed = False
    if owner == "ProjectLifecycle":
        allowed = name in {"timeline.json", "anchors.json", "chat_history.json"} or (
            name.endswith(".brain-feedback-outbox.json")
        )
    elif owner == "BrainStore":
        allowed = name in {
            "feedback_outbox.json",
            "feedback_receipts.json",
            "cross_modal_projector.npz",
        } or (scope.name.casefold() == "embeddings" and target.suffix.casefold() == ".npy")
    elif owner == "AudioStemOwner":
        allowed = _is_stem_owner_name(name)
    elif owner == "VectorStore":
        allowed = (
            target.suffix.casefold() == ".faiss"
            or name.casefold().endswith("_meta.json")
            or name.casefold().endswith("_tombstones.json")
        )
    elif owner == "SettingsService":
        allowed = name.casefold() == "settings.json"
    if not allowed:
        raise RecoveryBootstrapError(
            f"Delete artifact owner/pattern is not allowed: {owner}:{name}"
        )


def _is_stem_owner_name(name: str) -> bool:
    path = Path(name)
    normalized = path.stem.casefold()
    roles = {"vocals", "instrumental", "drums", "bass", "other"}
    if path.suffix.casefold() == ".wav":
        return normalized in roles or any(
            normalized.endswith(f"({role})") for role in roles
        )
    lowered = name.casefold()
    return (
        lowered.startswith(".")
        and (
            lowered.endswith(".stems-complete.json")
            or lowered.endswith(".stems-partial.json")
        )
    )


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


def _delete_owned_target(target: Path) -> None:
    if not target.exists() and not target.is_symlink():
        return
    if not target.is_file() and not target.is_symlink():
        raise RecoveryBootstrapError(
            f"Recovery delete target is not a file: {target}"
        )
    try:
        target.unlink()
    except OSError as exc:
        raise RecoveryBootstrapError(
            f"Recovery delete target is busy or unavailable: {target}"
        ) from exc
    _fsync_parent(target)


def _artifact_target_matches(target: Path, artifact: dict[str, Any]) -> bool:
    if str(artifact.get("restore_policy", "replace")) == DELETE_IF_PRESENT:
        return not target.exists() and not target.is_symlink()
    return target.is_file() and _sha256(target) == str(artifact.get("sha256", ""))


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
        restore_policy = str(artifact.get("restore_policy", "replace"))
        if restore_policy == DELETE_IF_PRESENT:
            _delete_owned_target(target)
        elif source.is_file():
            expected_hash = str(artifact["sha256"])
            if not _artifact_target_matches(target, artifact):
                _replace_target(source, target, expected_hash)
        if logical_id not in applied:
            applied.add(logical_id)
            journal["applied"] = sorted(applied)
            journal["state"] = "APPLYING"
            _atomic_write_json(control_root / "journal.json", journal)

    degraded = _validate_external_references(manifest)
    for artifact in artifacts:
        _source, target = _validate_artifact_record(generation_dir, artifact)
        if not _artifact_target_matches(target, artifact):
            raise RecoveryBootstrapError(f"Restored target failed validation: {target}")
    return manifest, degraded


def _delete_manifest_only_targets(
    control_root: Path,
    removed_generation: str,
    removed_manifest_sha256: str | None,
    retained_manifest: dict[str, Any],
    journal: dict[str, Any],
) -> None:
    if not removed_generation or not removed_manifest_sha256:
        return
    removed_dir, removed_manifest = _load_generation(
        control_root,
        removed_generation,
        removed_manifest_sha256,
    )
    retained_targets = {
        str(Path(str(record.get("absolute_target", ""))).resolve()).casefold()
        for record in retained_manifest.get("artifacts", [])
        if isinstance(record, dict)
    }
    applied = set(str(value) for value in journal.get("applied", []))
    for record in removed_manifest.get("artifacts", []):
        if not isinstance(record, dict):
            continue
        _source, target = _validate_artifact_record(removed_dir, record)
        if str(target.resolve()).casefold() in retained_targets:
            continue
        try:
            _validate_delete_scope(record, target)
        except RecoveryBootstrapError:
            continue
        receipt = f"manifest-only:{record.get('logical_id', '')}"
        _delete_owned_target(target)
        if receipt not in applied:
            applied.add(receipt)
            journal["applied"] = sorted(applied)
            journal["state"] = "APPLYING"
            _atomic_write_json(control_root / "journal.json", journal)


def _delete_dirty_new_targets(
    control_root: Path,
    dirty: dict[str, Any],
    journal: dict[str, Any],
) -> None:
    applied = set(str(value) for value in journal.get("applied", []))
    for entry in dirty.get("variable_inventory", []):
        baseline = {
            str(Path(value).resolve()).casefold()
            for value in entry.get("baseline_targets", [])
        }
        for target in _scan_runtime_variable_targets(entry):
            if str(target).casefold() in baseline:
                continue
            receipt_hash = hashlib.sha256(
                str(target).casefold().encode("utf-8")
            ).hexdigest()[:24]
            receipt = f"runtime-new:{receipt_hash}"
            _delete_owned_target(target)
            if receipt not in applied:
                applied.add(receipt)
                journal["applied"] = sorted(applied)
                journal["state"] = "APPLYING"
                _atomic_write_json(control_root / "journal.json", journal)


def _recover_generation(
    control_root: Path,
    generation_id: str,
    manifest_sha256: str,
    dirty: dict[str, Any],
) -> tuple[str, ...]:
    _generation_dir_path, manifest = _load_generation(
        control_root,
        generation_id,
        manifest_sha256,
    )
    degraded = _validate_external_references(manifest)
    journal = {
        "schema_version": 1,
        "operation": "restore",
        "state": "APPLYING",
        "previous_generation": generation_id,
        "previous_manifest_sha256": manifest_sha256,
        "next_generation": generation_id,
        "next_manifest_sha256": manifest_sha256,
        "applied": [],
    }
    _atomic_write_json(control_root / "journal.json", journal)
    _manifest, degraded = _apply_generation(
        control_root,
        generation_id,
        manifest_sha256,
        journal,
    )
    _delete_dirty_new_targets(control_root, dirty, journal)
    journal["state"] = "VALIDATING"
    _atomic_write_json(control_root / "journal.json", journal)
    _commit_current(control_root, generation_id, manifest_sha256)
    journal["state"] = "COMMITTED"
    journal["committed_generation"] = generation_id
    journal["committed_manifest_sha256"] = manifest_sha256
    _atomic_write_json(control_root / "journal.json", journal)
    _clear_runtime_dirty_file(control_root)
    return degraded


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


def _validated_current(
    control_root: Path,
    current: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any]] | None:
    if current is None:
        return None
    if int(current.get("schema_version", 0)) != 1:
        raise RecoveryBootstrapError("Unsupported CURRENT schema")
    generation_id = str(current.get("generation_id", ""))
    manifest_hash = str(current.get("manifest_sha256", ""))
    if len(manifest_hash) != 64:
        raise RecoveryBootstrapError("CURRENT manifest hash is invalid")
    _generation_path, manifest = _load_generation(
        control_root,
        generation_id,
        manifest_hash,
    )
    return generation_id, manifest_hash, manifest


def _runtime_variable_inventory(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = [
        record
        for record in manifest.get("artifacts", [])
        if isinstance(record, dict)
    ]
    project_roots: set[Path] = set()
    brain_roots: set[Path] = set()
    stem_roots: set[Path] = set()
    for record in artifacts:
        target = Path(str(record.get("absolute_target", "")))
        scope = Path(str(record.get("owner_scope", "")))
        if not target.is_absolute() or not scope.is_absolute():
            continue
        target = target.resolve()
        scope = scope.resolve()
        if record.get("owner") == "ProjectLifecycle" and target.name == "project.json":
            if scope == target.parent:
                project_roots.add(scope)
        elif record.get("owner") == "BrainStore" and target.name in {
            "weights.db",
            "patterns.db",
            "embedding_cache.db",
        }:
            if scope == target.parent:
                brain_roots.add(scope)
        elif record.get("owner") == "AudioStemOwner" and target.is_relative_to(scope):
            try:
                _validate_delete_scope(record, target)
            except RecoveryBootstrapError:
                continue
            stem_roots.add(scope)

    entries: list[dict[str, Any]] = []
    scope_specs = [
        *(('ProjectLifecycle', root) for root in project_roots),
        *(('AudioStemOwner', root) for root in (project_roots | stem_roots)),
        *(('BrainStore', root / "embeddings") for root in brain_roots),
    ]
    for owner, scope in sorted(
        scope_specs,
        key=lambda item: (item[0], str(item[1]).casefold()),
    ):
        baseline: list[str] = []
        for record in artifacts:
            if record.get("owner") != owner:
                continue
            target = Path(str(record.get("absolute_target", "")))
            if not target.is_absolute() or not target.resolve().is_relative_to(scope.resolve()):
                continue
            try:
                _validate_delete_scope(
                    {**record, "owner_scope": str(scope.resolve())},
                    target,
                )
            except RecoveryBootstrapError:
                continue
            baseline.append(str(target.resolve()))
        entries.append({
            "owner": owner,
            "owner_scope": str(scope.resolve()),
            "baseline_targets": sorted(set(baseline), key=str.casefold),
        })
    return entries


def _scan_runtime_variable_targets(entry: dict[str, Any]) -> tuple[Path, ...]:
    owner = str(entry.get("owner", ""))
    scope = Path(str(entry.get("owner_scope", ""))).resolve()
    if not scope.is_dir():
        return ()
    if owner == "ProjectLifecycle":
        candidates = scope.glob("*.brain-feedback-outbox.json")
    elif owner == "BrainStore":
        candidates = scope.rglob("*.npy")
    elif owner == "AudioStemOwner":
        candidates = (
            path
            for path in scope.rglob("*")
            if _is_stem_owner_name(path.name)
        )
    else:
        raise RecoveryBootstrapError("Runtime dirty inventory owner is invalid")
    result: list[Path] = []
    for target in candidates:
        if not target.is_file() and not target.is_symlink():
            continue
        _validate_delete_scope(
            {"owner": owner, "owner_scope": str(scope)},
            target,
        )
        result.append(target.resolve())
    return tuple(sorted(set(result), key=lambda path: str(path).casefold()))


def _runtime_dirty(control_root: Path) -> dict[str, Any] | None:
    path = control_root / RUNTIME_DIRTY_NAME
    if not path.is_file():
        return None
    marker = _read_json(path)
    if int(marker.get("schema_version", 0)) != 1:
        raise RecoveryBootstrapError("Unsupported runtime dirty schema")
    generation_id = str(marker.get("base_generation", ""))
    manifest_hash = str(marker.get("base_manifest_sha256", ""))
    if not generation_id or len(manifest_hash) != 64:
        raise RecoveryBootstrapError("Runtime dirty marker is incomplete")
    _generation_path, manifest = _load_generation(
        control_root,
        generation_id,
        manifest_hash,
    )
    expected_inventory = _runtime_variable_inventory(manifest)
    if marker.get("variable_inventory") != expected_inventory:
        raise RecoveryBootstrapError("Runtime dirty inventory does not match its base")
    return marker


def _dirty_matches_current(
    dirty: dict[str, Any],
    current_generation: str,
    current_hash: str,
) -> bool:
    return (
        str(dirty.get("base_generation", "")) == current_generation
        and str(dirty.get("base_manifest_sha256", "")) == current_hash
    )


def _dirty_matches_journal_previous(
    dirty: dict[str, Any],
    journal: dict[str, Any],
) -> bool:
    previous_generation = str(journal.get("previous_generation", ""))
    previous_hash = str(journal.get("previous_manifest_sha256", ""))
    return bool(previous_generation and previous_hash) and (
        str(dirty.get("base_generation", "")) == previous_generation
        and str(dirty.get("base_manifest_sha256", "")) == previous_hash
    )


def _clear_runtime_dirty_file(control_root: Path) -> None:
    path = control_root / RUNTIME_DIRTY_NAME
    if path.exists() or path.is_symlink():
        try:
            path.unlink()
        except OSError as exc:
            raise RecoveryBootstrapError("Runtime dirty marker could not be cleared") from exc
        _fsync_parent(path)


def mark_runtime_dirty(control_root: Path | None = None) -> bool:
    """Durably bind accepted runtime work to the current backup generation."""
    root = (control_root or fixed_control_root()).resolve()
    current = _validated_current(root, _current_pointer(root))
    if current is None:
        return False
    generation_id, manifest_hash, _manifest = current
    _atomic_write_json(
        root / RUNTIME_DIRTY_NAME,
        {
            "schema_version": 1,
            "base_generation": generation_id,
            "base_manifest_sha256": manifest_hash,
            "variable_inventory": _runtime_variable_inventory(_manifest),
        },
    )
    return True


def clear_runtime_dirty(
    control_root: Path | None = None,
    *,
    expected_generation_id: str,
    expected_manifest_sha256: str,
) -> None:
    """Clear DIRTY only after the expected shutdown snapshot is CURRENT."""
    root = (control_root or fixed_control_root()).resolve()
    current = _validated_current(root, _current_pointer(root))
    if current is None or current[:2] != (
        expected_generation_id,
        expected_manifest_sha256,
    ):
        raise RecoveryBootstrapError(
            "Runtime dirty clear does not match the shutdown generation"
        )
    _clear_runtime_dirty_file(root)


def _validate_committed_journal(
    control_root: Path,
    journal: dict[str, Any],
    current: tuple[str, str, dict[str, Any]] | None,
) -> tuple[str, str, dict[str, Any]]:
    if current is None:
        raise RecoveryBootstrapError("Committed recovery journal lacks CURRENT")
    generation_id, manifest_hash, manifest = current
    committed_generation = str(journal.get("committed_generation", ""))
    committed_hash = str(journal.get("committed_manifest_sha256", ""))
    if not committed_hash:
        if committed_generation == str(journal.get("next_generation", "")):
            committed_hash = str(journal.get("next_manifest_sha256", ""))
        elif committed_generation == str(journal.get("previous_generation", "")):
            committed_hash = str(journal.get("previous_manifest_sha256", ""))
    if (
        committed_generation != generation_id
        or committed_hash != manifest_hash
    ):
        raise RecoveryBootstrapError(
            "Committed recovery journal does not match CURRENT"
        )
    return generation_id, manifest_hash, manifest


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
    current = _validated_current(root, _current_pointer(root))
    dirty = _runtime_dirty(root)

    if journal is None:
        if current is None:
            if dirty is not None:
                raise RecoveryBootstrapError("Runtime dirty marker lacks CURRENT")
            return RecoveryBootstrapResult(status="uninitialized")
        generation_id, manifest_hash, manifest = current
        degraded = _validate_external_references(manifest)
        if dirty is None:
            return RecoveryBootstrapResult("ready", generation_id, degraded)
        if not _dirty_matches_current(dirty, generation_id, manifest_hash):
            raise RecoveryBootstrapError("Runtime dirty base does not match CURRENT")
        degraded = _recover_generation(root, generation_id, manifest_hash, dirty)
        return RecoveryBootstrapResult("recovered", generation_id, degraded)

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
                if dirty is not None:
                    raise RecoveryBootstrapError("Runtime dirty marker lacks CURRENT")
                journal_path.unlink(missing_ok=True)
                _fsync_parent(journal_path)
                return RecoveryBootstrapResult("uninitialized")
            current_generation, current_hash, current_manifest = current
            degraded = _validate_external_references(current_manifest)
            if dirty is not None:
                if not _dirty_matches_current(
                    dirty,
                    current_generation,
                    current_hash,
                ):
                    raise RecoveryBootstrapError(
                        "Runtime dirty base does not match CURRENT"
                    )
                degraded = _recover_generation(
                    root,
                    current_generation,
                    current_hash,
                    dirty,
                )
                return RecoveryBootstrapResult(
                    "snapshot_aborted",
                    current_generation,
                    degraded,
                )
            journal["state"] = "COMMITTED"
            journal["snapshot_aborted"] = True
            journal["committed_generation"] = current_generation
            journal["committed_manifest_sha256"] = current_hash
            _atomic_write_json(journal_path, journal)
            return RecoveryBootstrapResult(
                "snapshot_aborted",
                current_generation,
                degraded,
            )
        if state == "STAGED":
            if not next_generation or not next_manifest_hash:
                raise RecoveryBootstrapError("Staged snapshot lacks generation identity")
            current_identity = current[:2] if current is not None else ("", "")
            allowed_current = {
                (previous_generation, previous_manifest_hash or ""),
                (next_generation, next_manifest_hash),
            }
            if current_identity not in allowed_current:
                raise RecoveryBootstrapError(
                    "Staged snapshot CURRENT is neither previous nor next"
                )
            if dirty is not None and not _dirty_matches_journal_previous(
                dirty,
                journal,
            ):
                raise RecoveryBootstrapError(
                    "Runtime dirty base does not match staged snapshot previous"
                )
            _generation_path, next_manifest = _load_generation(
                root,
                next_generation,
                next_manifest_hash,
            )
            degraded = _validate_external_references(next_manifest)
            _commit_current(root, next_generation, next_manifest_hash)
            journal["state"] = "COMMITTED"
            journal["committed_generation"] = next_generation
            journal["committed_manifest_sha256"] = next_manifest_hash
            _atomic_write_json(journal_path, journal)
            _clear_runtime_dirty_file(root)
            return RecoveryBootstrapResult(
                "snapshot_committed",
                next_generation,
                degraded,
            )
        if state == "COMMITTED":
            current_generation, current_hash, current_manifest = (
                _validate_committed_journal(root, journal, current)
            )
            degraded = _validate_external_references(current_manifest)
            if dirty is not None:
                if _dirty_matches_current(dirty, current_generation, current_hash):
                    degraded = _recover_generation(
                        root,
                        current_generation,
                        current_hash,
                        dirty,
                    )
                    return RecoveryBootstrapResult(
                        "recovered",
                        current_generation,
                        degraded,
                    )
                if _dirty_matches_journal_previous(dirty, journal):
                    _clear_runtime_dirty_file(root)
                else:
                    raise RecoveryBootstrapError(
                        "Runtime dirty base matches neither CURRENT nor journal previous"
                    )
            return RecoveryBootstrapResult("ready", current_generation, degraded)
        raise RecoveryBootstrapError(
            f"Snapshot journal cannot enter restore state {state}"
        )
    if operation != "restore":
        raise RecoveryBootstrapError(f"Unknown recovery operation: {operation}")

    if state == "COMMITTED":
        current_generation, current_hash, current_manifest = (
            _validate_committed_journal(root, journal, current)
        )
        degraded = _validate_external_references(current_manifest)
        if dirty is not None:
            if _dirty_matches_current(dirty, current_generation, current_hash):
                degraded = _recover_generation(
                    root,
                    current_generation,
                    current_hash,
                    dirty,
                )
                return RecoveryBootstrapResult(
                    "recovered",
                    current_generation,
                    degraded,
                )
            if _dirty_matches_journal_previous(dirty, journal):
                _clear_runtime_dirty_file(root)
            else:
                raise RecoveryBootstrapError(
                    "Runtime dirty base matches neither CURRENT nor journal previous"
                )
        return RecoveryBootstrapResult("ready", current_generation, degraded)

    use_next = state in {"STAGED", "APPLYING", "VALIDATING"}
    selected_generation = next_generation if use_next else previous_generation
    selected_manifest_hash = (
        next_manifest_hash if use_next else previous_manifest_hash
    )
    if not selected_generation:
        raise RecoveryBootstrapError("Recovery journal has no usable generation")

    selected_manifest_for_rollback: dict[str, Any] | None = None
    try:
        _selected_dir, selected_manifest_for_rollback = _load_generation(
            root,
            selected_generation,
            selected_manifest_hash,
        )
        journal["state"] = "APPLYING" if use_next else "ROLLING_BACK"
        _atomic_write_json(journal_path, journal)
        selected_manifest, degraded = _apply_generation(
            root,
            selected_generation,
            selected_manifest_hash,
            journal,
        )
        _delete_manifest_only_targets(
            root,
            previous_generation,
            previous_manifest_hash,
            selected_manifest,
            journal,
        )
    except RecoveryBootstrapError:
        if not use_next or not previous_generation:
            raise
        journal["state"] = "ROLLING_BACK"
        journal["applied"] = []
        _atomic_write_json(journal_path, journal)
        rollback_manifest, degraded = _apply_generation(
            root,
            previous_generation,
            previous_manifest_hash,
            journal,
        )
        if selected_manifest_for_rollback is not None:
            _delete_manifest_only_targets(
                root,
                selected_generation,
                selected_manifest_hash,
                rollback_manifest,
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
    journal["committed_manifest_sha256"] = selected_manifest_hash
    _atomic_write_json(journal_path, journal)
    _clear_runtime_dirty_file(root)
    return RecoveryBootstrapResult("recovered", selected_generation, degraded)


__all__ = [
    "RecoveryBootstrapError",
    "RecoveryBootstrapResult",
    "ensure_recovery_ready",
    "fixed_control_root",
    "mark_runtime_dirty",
    "clear_runtime_dirty",
]
