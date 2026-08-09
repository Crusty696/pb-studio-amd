"""Owner inventory and semantic validation for product recovery generations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterable

from .recovery_barrier import RecoveryWriteBarrier, get_recovery_write_barrier
from .recovery_generation import (
    CommittedGeneration,
    RecoveryGenerationWriter,
    load_current_generation,
    validate_generation,
)


class RecoveryOwnerAdapterError(RuntimeError):
    """An owner cannot provide a complete, internally consistent snapshot."""


@dataclass(frozen=True)
class RecoveryOwnerSnapshot:
    config_path: Path
    catalog_db_path: Path
    brain_dir: Path
    project_roots: tuple[Path, ...] = ()
    wpf_settings_path: Path | None = None
    vector_index_path: Path | None = None
    stem_artifacts: tuple[Path, ...] = ()
    render_outputs: tuple[Path, ...] = ()
    external_media: tuple[Path, ...] = ()
    quiesce_callbacks: tuple[Callable[[], None], ...] = ()


@dataclass(frozen=True)
class OwnerGenerationValidation:
    valid: bool
    generation_id: str
    degraded_references: tuple[str, ...]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryOwnerAdapterError(f"Invalid {label} JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RecoveryOwnerAdapterError(f"{label} JSON must be an object: {path}")
    return value


def _json_value(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryOwnerAdapterError(f"Invalid {label} JSON: {path}") from exc


def _sqlite_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RecoveryOwnerAdapterError(f"Required SQLite owner missing: {path}")
    connection = sqlite3.connect(str(path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    try:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RecoveryOwnerAdapterError(f"SQLite quick_check failed: {path}")
    except Exception:
        connection.close()
        raise
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _paths_below_key(value, *, key_contains: str) -> set[Path]:
    result: set[Path] = set()

    def visit(node, active: bool = False) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                visit(child, active or key_contains in str(key).casefold())
        elif isinstance(node, list):
            for child in node:
                visit(child, active)
        elif active and isinstance(node, str):
            path = Path(node)
            if path.is_absolute():
                result.add(path.resolve())

    visit(value)
    return result


def _catalog_inventory(snapshot: RecoveryOwnerSnapshot) -> tuple[
    tuple[tuple[str, Path], ...],
    tuple[Path, ...],
    tuple[int, ...],
    tuple[Path, ...],
    tuple[Path, ...],
]:
    connection = _sqlite_connection(Path(snapshot.catalog_db_path).resolve())
    try:
        projects: list[tuple[str, Path]] = []
        if _table_exists(connection, "projects"):
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(projects)")
            }
            uuid_expr = "project_uuid" if "project_uuid" in columns else "NULL"
            rows = connection.execute(
                f"SELECT id, json_data, {uuid_expr} AS project_uuid FROM projects "
                "ORDER BY id"
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads(row["json_data"] or "{}")
                except (TypeError, json.JSONDecodeError) as exc:
                    raise RecoveryOwnerAdapterError(
                        f"Catalog project {row['id']} has invalid JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise RecoveryOwnerAdapterError("Catalog project payload is not an object")
                project_uuid = str(
                    row["project_uuid"] or payload.get("project_uuid") or row["id"]
                )
                raw_path = payload.get("path")
                if raw_path:
                    path = Path(str(raw_path))
                    if not path.is_absolute():
                        raise RecoveryOwnerAdapterError("Catalog project path is relative")
                    projects.append((project_uuid, path.resolve()))

        media: list[Path] = []
        stems: set[Path] = set()
        if _table_exists(connection, "media"):
            media_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(media)")
            }
            optional_columns = [
                name for name in ("metadata_json", "ai_data_json")
                if name in media_columns
            ]
            select_columns = ", ".join(["file_path", *optional_columns])
            for row in connection.execute(
                f"SELECT {select_columns} FROM media ORDER BY id"
            ):
                path = Path(str(row["file_path"]))
                if not path.is_absolute():
                    raise RecoveryOwnerAdapterError("Catalog media path is relative")
                media.append(path.resolve())
                for column in optional_columns:
                    try:
                        payload = json.loads(row[column] or "{}")
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise RecoveryOwnerAdapterError(
                            f"Catalog media {column} is invalid JSON"
                        ) from exc
                    stems.update(_paths_below_key(payload, key_contains="stem"))

        vector_ids: tuple[int, ...] = ()
        if _table_exists(connection, "vector_map"):
            vector_ids = tuple(
                int(row[0])
                for row in connection.execute(
                    "SELECT faiss_id FROM vector_map ORDER BY faiss_id"
                )
            )
        renders: tuple[Path, ...] = ()
        if _table_exists(connection, "render_queue"):
            renders = tuple(
                Path(str(row[0])).resolve()
                for row in connection.execute(
                    "SELECT output_path FROM render_queue ORDER BY job_id"
                )
                if Path(str(row[0])).is_absolute()
            )
        return (
            tuple(projects),
            tuple(media),
            vector_ids,
            tuple(sorted(stems, key=lambda path: str(path).casefold())),
            renders,
        )
    finally:
        connection.close()


def _resolved_projects(
    snapshot: RecoveryOwnerSnapshot,
    catalog_projects: tuple[tuple[str, Path], ...],
) -> tuple[tuple[str, Path], ...]:
    if not snapshot.project_roots:
        return catalog_projects
    catalog_by_path = {path: project_uuid for project_uuid, path in catalog_projects}
    result: list[tuple[str, Path]] = []
    for root_value in snapshot.project_roots:
        root = Path(root_value).resolve()
        project_json = root / "project.json"
        payload = _json_object(project_json, "project")
        project_uuid = str(payload.get("project_uuid") or catalog_by_path.get(root) or "")
        if not project_uuid:
            raise RecoveryOwnerAdapterError(f"Project identity missing: {root}")
        catalog_uuid = catalog_by_path.get(root)
        if catalog_uuid and catalog_uuid != project_uuid:
            raise RecoveryOwnerAdapterError("Project UUID conflicts with catalog")
        result.append((project_uuid, root))
    return tuple(sorted(result, key=lambda item: (item[0], str(item[1]).casefold())))


def owner_snapshot_digests(snapshot: RecoveryOwnerSnapshot) -> tuple[str, str]:
    config_path = Path(snapshot.config_path).resolve()
    _json_object(config_path, "config")
    catalog_projects, _catalog_media, _vector_ids, _stems, _renders = (
        _catalog_inventory(snapshot)
    )
    projects = _resolved_projects(snapshot, catalog_projects)
    inventory = [
        {"project_uuid": project_uuid, "root": str(root)}
        for project_uuid, root in projects
    ]
    inventory_bytes = json.dumps(
        inventory,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_file(config_path), _sha256_bytes(inventory_bytes)


def _validate_empty_outbox(path: Path) -> None:
    if not path.is_file():
        return
    value = _json_value(path, "Brain outbox")
    if value not in ({}, None, []):
        raise RecoveryOwnerAdapterError(
            f"Brain outbox has a half-applied operation: {path}"
        )


def _vector_triplet(index_path: Path) -> tuple[Path, Path, Path]:
    base = index_path.with_suffix("")
    return (
        index_path,
        base.with_name(base.name + "_meta.json"),
        base.with_name(base.name + "_tombstones.json"),
    )


def _validate_vector(
    index_path: Path | None,
    vector_ids: tuple[int, ...],
) -> tuple[Path, ...]:
    if index_path is None:
        if vector_ids:
            raise RecoveryOwnerAdapterError("vector_map exists without FAISS index")
        return ()
    paths = _vector_triplet(Path(index_path).resolve())
    if not all(path.is_file() for path in paths):
        raise RecoveryOwnerAdapterError("FAISS generation triplet is incomplete")
    journal = Path(str(paths[0]) + ".txn.json")
    if journal.exists():
        raise RecoveryOwnerAdapterError("FAISS journal is not terminal")
    metadata = _json_object(paths[1], "FAISS metadata")
    tombstone_value = _json_value(paths[2], "FAISS tombstones")
    if not isinstance(tombstone_value, list):
        raise RecoveryOwnerAdapterError("FAISS tombstones must be a list")
    try:
        metadata_ids = {int(value) for value in metadata}
        tombstones = {int(value) for value in tombstone_value}
    except (TypeError, ValueError) as exc:
        raise RecoveryOwnerAdapterError("FAISS identities are invalid") from exc
    mapped = set(vector_ids)
    if not mapped.issubset(metadata_ids) or mapped & tombstones:
        raise RecoveryOwnerAdapterError("FAISS metadata conflicts with vector_map")
    try:
        import faiss

        index = faiss.read_index(str(paths[0]))
        if any(value < 0 or value >= int(index.ntotal) for value in metadata_ids):
            raise RecoveryOwnerAdapterError("FAISS metadata ID exceeds index")
    except RecoveryOwnerAdapterError:
        raise
    except Exception as exc:
        raise RecoveryOwnerAdapterError("FAISS index cannot be validated") from exc
    return paths


def _project_files(project_uuid: str, root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        raise RecoveryOwnerAdapterError(f"Registered project root missing: {root}")
    project_json = root / "project.json"
    payload = _json_object(project_json, "project")
    if str(payload.get("project_uuid") or project_uuid) != project_uuid:
        raise RecoveryOwnerAdapterError("Project JSON identity mismatch")
    files: list[Path] = [project_json]
    for name in ("timeline.json", "anchors.json", "chat_history.json"):
        path = root / name
        if path.is_file():
            _json_value(path, name)
            files.append(path)
    state = root / "state.db"
    connection = _sqlite_connection(state)
    try:
        if _table_exists(connection, "project_identity"):
            row = connection.execute(
                "SELECT project_uuid FROM project_identity WHERE singleton_id=1"
            ).fetchone()
            if row is not None and str(row[0]) != project_uuid:
                raise RecoveryOwnerAdapterError("State DB project UUID mismatch")
    finally:
        connection.close()
    files.append(state)
    sidecars = sorted(root.glob("*.brain-feedback-outbox.json"))
    for sidecar in sidecars:
        _validate_empty_outbox(sidecar)
        files.append(sidecar)
    return tuple(files)


def _brain_files(brain_dir: Path) -> tuple[Path, ...]:
    brain_dir = brain_dir.resolve()
    required = tuple(brain_dir / name for name in (
        "weights.db", "patterns.db", "embedding_cache.db"
    ))
    for database in required:
        connection = _sqlite_connection(database)
        connection.close()
    files: list[Path] = list(required)
    for name in ("feedback_outbox.json", "feedback_receipts.json"):
        path = brain_dir / name
        if path.is_file():
            if name == "feedback_outbox.json":
                _validate_empty_outbox(path)
            else:
                _json_object(path, "Brain feedback receipts")
            files.append(path)
    embeddings = brain_dir / "embeddings"
    if embeddings.is_dir():
        files.extend(sorted(path for path in embeddings.rglob("*.npy") if path.is_file()))
    projector = brain_dir / "cross_modal_projector.npz"
    if projector.is_file():
        try:
            import numpy as np

            with np.load(projector, allow_pickle=False) as artifact:
                if int(artifact["format_version"].item()) not in {1, 2}:
                    raise RecoveryOwnerAdapterError("Unsupported Projector format")
        except RecoveryOwnerAdapterError:
            raise
        except Exception as exc:
            raise RecoveryOwnerAdapterError("Projector artifact is invalid") from exc
        files.append(projector)
    return tuple(files)


def _logical_id(prefix: str, path: Path) -> str:
    identity = hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()
    return f"{prefix}:{identity[:24]}:{path.name}"


def _unique_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique = {str(Path(path).resolve()).casefold(): Path(path).resolve() for path in paths}
    return tuple(unique[key] for key in sorted(unique))


def _configured_stem_run_roots(config: Path, payload: dict) -> tuple[Path, ...]:
    paths = payload.get("paths", {})
    raw_temp = paths.get("temp_dir", "./temp") if isinstance(paths, dict) else "./temp"
    temp_dir = Path(str(raw_temp))
    if not temp_dir.is_absolute():
        cleaned = str(raw_temp)
        while cleaned.startswith("./") or cleaned.startswith(".\\"):
            cleaned = cleaned[2:]
        temp_dir = config.parent / cleaned
    return ((temp_dir.resolve() / "stem-runs"),)


def _add_absence_tombstone(
    writer: RecoveryGenerationWriter,
    receipt_source: Path,
    target: Path,
    *,
    prefix: str,
    group: str,
    owner: str,
    owner_scope: Path,
    seen_targets: set[str],
) -> None:
    target = target.resolve()
    target_key = str(target).casefold()
    if target_key in seen_targets or target.exists() or target.is_symlink():
        return
    writer.add_file(
        _logical_id(f"absence:{prefix}", target),
        receipt_source,
        group=group,
        owner=owner,
        absolute_target=target,
        restore_policy="delete_if_present",
        owner_scope=owner_scope.resolve(),
    )
    seen_targets.add(target_key)


def _add_previous_inventory_tombstones(
    writer: RecoveryGenerationWriter,
    receipt_source: Path,
    project_roots: tuple[Path, ...],
    brain_dir: Path,
    stem_run_roots: tuple[Path, ...],
    seen_targets: set[str],
) -> None:
    current = load_current_generation(writer.control_root)
    if current is None:
        return
    _generation_id, _manifest_hash, manifest = current
    previous_project_roots = {
        Path(str(record.get("absolute_target", ""))).resolve().parent
        for record in manifest.get("artifacts", [])
        if isinstance(record, dict)
        and record.get("owner") == "ProjectLifecycle"
        and Path(str(record.get("absolute_target", ""))).name == "project.json"
    }
    safe_project_roots = tuple(
        sorted(
            {*(root.resolve() for root in project_roots), *previous_project_roots},
            key=lambda path: str(path).casefold(),
        )
    )
    embeddings_root = (brain_dir / "embeddings").resolve()
    for record in manifest.get("artifacts", []):
        if not isinstance(record, dict) or record.get("restore_policy") == "delete_if_present":
            continue
        target = Path(str(record.get("absolute_target", "")))
        if not target.is_absolute() or target.exists() or target.is_symlink():
            continue
        target = target.resolve()
        owner = str(record.get("owner", ""))
        scope: Path | None = None
        group = str(record.get("group", ""))
        if owner == "ProjectLifecycle" and target.name.endswith(
            ".brain-feedback-outbox.json"
        ):
            scope = next(
                (root for root in safe_project_roots if target.is_relative_to(root)),
                None,
            )
        elif (
            owner == "BrainStore"
            and target.suffix.casefold() == ".npy"
            and target.is_relative_to(embeddings_root)
        ):
            scope = embeddings_root
        elif owner == "AudioStemOwner" and (
            target.suffix.casefold() == ".wav"
            or (
                target.name.startswith(".")
                and ".stems-" in target.name
                and target.suffix.casefold() == ".json"
            )
        ):
            scope = next(
                (
                    root
                    for root in (*safe_project_roots, *stem_run_roots)
                    if target.is_relative_to(root)
                ),
                None,
            )
        if scope is not None:
            _add_absence_tombstone(
                writer,
                receipt_source,
                target,
                prefix=f"previous:{owner}",
                group=group,
                owner=owner,
                owner_scope=scope,
                seen_targets=seen_targets,
            )


def add_owner_snapshot(
    writer: RecoveryGenerationWriter,
    snapshot: RecoveryOwnerSnapshot,
) -> None:
    config = Path(snapshot.config_path).resolve()
    config_payload = _json_object(config, "config")
    stem_run_roots = _configured_stem_run_roots(config, config_payload)
    catalog = Path(snapshot.catalog_db_path).resolve()
    (
        catalog_projects,
        catalog_media,
        vector_ids,
        catalog_stems,
        catalog_renders,
    ) = _catalog_inventory(snapshot)
    projects = _resolved_projects(snapshot, catalog_projects)
    vector_index = (
        Path(snapshot.vector_index_path).resolve()
        if snapshot.vector_index_path is not None
        else ((catalog.parent / "video_index.faiss") if vector_ids else None)
    )
    vector_files = _validate_vector(vector_index, vector_ids)
    brain_dir = Path(snapshot.brain_dir).resolve()
    brain_files = _brain_files(brain_dir)
    absence_targets: set[str] = set()

    config_digest, inventory_digest = owner_snapshot_digests(snapshot)
    if writer.config_digest != config_digest:
        raise RecoveryOwnerAdapterError("Writer config digest does not match owner state")
    if writer.project_inventory_digest != inventory_digest:
        raise RecoveryOwnerAdapterError("Writer project inventory digest mismatch")

    writer.add_file("config:backend", config, group="global-config", owner="ConfigManager")
    if snapshot.wpf_settings_path is not None:
        settings = Path(snapshot.wpf_settings_path).resolve()
        if settings.is_file():
            _json_object(settings, "WPF settings")
            writer.add_file(
                "config:wpf-settings", settings,
                group="global-config", owner="SettingsService",
                owner_scope=settings.parent,
            )
        else:
            _add_absence_tombstone(
                writer,
                config,
                settings,
                prefix="wpf-settings",
                group="global-config",
                owner="SettingsService",
                owner_scope=settings.parent,
                seen_targets=absence_targets,
            )
    writer.add_sqlite("catalog:pb-studio", catalog, group="global-index", owner="DatabaseCore")
    for path in vector_files:
        writer.add_file(
            _logical_id("vector", path), path,
            group="global-index", owner="VectorStore",
            owner_scope=path.parent,
        )
    if not vector_files:
        vector_target = (
            Path(snapshot.vector_index_path).resolve()
            if snapshot.vector_index_path is not None
            else (catalog.parent / "video_index.faiss").resolve()
        )
        for path in _vector_triplet(vector_target):
            _add_absence_tombstone(
                writer,
                config,
                path,
                prefix="vector",
                group="global-index",
                owner="VectorStore",
                owner_scope=vector_target.parent,
                seen_targets=absence_targets,
            )
    for project_uuid, root in projects:
        project_files = _project_files(project_uuid, root)
        for path in project_files:
            if path.suffix.casefold() == ".db":
                writer.add_sqlite(
                    _logical_id(f"project:{project_uuid}", path), path,
                    group="project", owner="ProjectLifecycle",
                    owner_scope=root,
                )
            else:
                writer.add_file(
                    _logical_id(f"project:{project_uuid}", path), path,
                    group="project", owner="ProjectLifecycle",
                    owner_scope=root,
                )
        present_project_paths = {path.resolve() for path in project_files}
        for path in (
            root / "timeline.json",
            root / "anchors.json",
            root / "chat_history.json",
            root / "state.db.brain-feedback-outbox.json",
        ):
            if path.resolve() not in present_project_paths:
                _add_absence_tombstone(
                    writer,
                    config,
                    path,
                    prefix=f"project:{project_uuid}",
                    group="project",
                    owner="ProjectLifecycle",
                    owner_scope=root,
                    seen_targets=absence_targets,
                )
    for path in brain_files:
        if path.suffix.casefold() == ".db":
            writer.add_sqlite(
                _logical_id("brain", path), path,
                group="brain", owner="BrainStore",
                owner_scope=brain_dir,
            )
        else:
            owner_scope = (
                brain_dir / "embeddings"
                if path.suffix.casefold() == ".npy"
                else brain_dir
            )
            writer.add_file(
                _logical_id("brain", path), path,
                group="brain", owner="BrainStore",
                owner_scope=owner_scope,
            )
    present_brain_paths = {path.resolve() for path in brain_files}
    for path in (
        brain_dir / "feedback_outbox.json",
        brain_dir / "feedback_receipts.json",
        brain_dir / "cross_modal_projector.npz",
    ):
        if path.resolve() not in present_brain_paths:
            _add_absence_tombstone(
                writer,
                config,
                path,
                prefix="brain",
                group="brain",
                owner="BrainStore",
                owner_scope=brain_dir,
                seen_targets=absence_targets,
            )
    for root in stem_run_roots:
        _add_absence_tombstone(
            writer,
            config,
            root / ".pb-studio-recovery-scope.stems-partial.json",
            prefix="stem-run-scope",
            group="project-media",
            owner="AudioStemOwner",
            owner_scope=root,
            seen_targets=absence_targets,
        )
    _add_previous_inventory_tombstones(
        writer,
        config,
        tuple(root for _project_uuid, root in projects),
        brain_dir,
        stem_run_roots,
        absence_targets,
    )
    stem_paths: set[Path] = {
        Path(path).resolve()
        for path in (snapshot.stem_artifacts or catalog_stems)
    }
    for stem in tuple(stem_paths):
        if stem.is_file() and stem.suffix.casefold() == ".wav":
            stem_paths.update(stem.parent.glob(".*.stems-*.json"))
    for path in sorted(stem_paths, key=lambda value: str(value).casefold()):
        if not path.is_file():
            raise RecoveryOwnerAdapterError(f"Stem artifact missing: {path}")
        owner_scope = next(
            (
                root
                for root in (
                    *(root for _project_uuid, root in projects),
                    *stem_run_roots,
                )
                if path.is_relative_to(root)
            ),
            None,
        )
        writer.add_file(
            _logical_id("stem", path), path,
            group="project-media", owner="AudioStemOwner",
            owner_scope=owner_scope,
        )

    media_refs = _unique_paths(
        tuple(Path(path).resolve() for path in snapshot.external_media)
        if snapshot.external_media else catalog_media
    )
    render_refs = _unique_paths(
        Path(path).resolve()
        for path in (snapshot.render_outputs or catalog_renders)
    )
    for prefix, paths, owner in (
        ("media", media_refs, "MediaRepository"),
        ("render", render_refs, "RenderService"),
    ):
        for path in paths:
            writer.add_external_reference(
                _logical_id(prefix, path), path,
                group="project-media" if prefix == "media" else "render",
                owner=owner,
                required=False,
                degraded_mode_policy="report_unavailable",
            )


def create_owner_generation(
    snapshot: RecoveryOwnerSnapshot,
    *,
    control_root: str | Path | None = None,
    barrier: RecoveryWriteBarrier | None = None,
    timeout: float = 60.0,
    generation_id: str | None = None,
) -> CommittedGeneration:
    active_barrier = barrier or get_recovery_write_barrier()
    with active_barrier.snapshot_lease(timeout=timeout):
        for callback in snapshot.quiesce_callbacks:
            callback()
        config_digest, inventory_digest = owner_snapshot_digests(snapshot)
        writer = RecoveryGenerationWriter(
            control_root=control_root,
            generation_id=generation_id,
            config_digest=config_digest,
            project_inventory_digest=inventory_digest,
        )
        add_owner_snapshot(writer, snapshot)
        return writer.commit()


def validate_owner_generation(
    control_root: str | Path,
    generation_id: str,
) -> OwnerGenerationValidation:
    manifest = validate_generation(control_root, generation_id)
    groups = {str(record.get("group", "")) for record in manifest["artifacts"]}
    required_groups = {"global-config", "global-index", "brain"}
    empty_inventory_digest = _sha256_bytes(b"[]")
    if manifest.get("project_inventory_digest") != empty_inventory_digest:
        required_groups.add("project")
    if not required_groups.issubset(groups):
        raise RecoveryOwnerAdapterError("Owner generation lacks a consistency group")
    degraded = tuple(
        sorted(
            str(reference.get("logical_id", "external"))
            for reference in manifest["external_references"]
            if not bool(reference.get("available"))
        )
    )
    return OwnerGenerationValidation(True, generation_id, degraded)


__all__ = [
    "OwnerGenerationValidation",
    "RecoveryOwnerAdapterError",
    "RecoveryOwnerSnapshot",
    "add_owner_snapshot",
    "create_owner_generation",
    "owner_snapshot_digests",
    "validate_owner_generation",
]
