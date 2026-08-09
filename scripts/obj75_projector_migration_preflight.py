"""Create and restore-verify the OBJ-75 pre-migration backup generation.

This script never modifies a source database or source file. SQLite sources are
copied with the online backup API; the dry run restores only into the new backup
directory. It uses only the Python 3.11 standard library.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _logical_db_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for statement in connection.iterdump():
        digest.update(statement.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _inspect_db(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        row_counts = {
            table: int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                ).fetchone()[0]
            )
            for table in tables
        }
        return {
            "quick_check": quick_check,
            "user_version": user_version,
            "tables": tables,
            "row_counts": row_counts,
            "logical_sha256": _logical_db_digest(connection),
        }
    finally:
        connection.close()


def _backup_db(source: Path, target: Path, restore_target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    restore_target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=ro", uri=True
    )
    target_connection = sqlite3.connect(str(target))
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()

    backup_connection = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro", uri=True
    )
    restore_connection = sqlite3.connect(str(restore_target))
    try:
        backup_connection.backup(restore_connection)
        restore_connection.commit()
    finally:
        restore_connection.close()
        backup_connection.close()

    source_info = _inspect_db(source)
    backup_info = _inspect_db(target)
    restore_info = _inspect_db(restore_target)
    if source_info != backup_info or backup_info != restore_info:
        raise RuntimeError(f"SQLite logical parity failed for {source}")
    return {
        "kind": "sqlite",
        "source": str(source),
        "backup": str(target),
        "restore_dry_run": str(restore_target),
        "backup_sha256": _sha256(target),
        "restore_sha256": _sha256(restore_target),
        **backup_info,
    }


def _backup_file(source: Path, target: Path, restore_target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    restore_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    shutil.copy2(target, restore_target)
    source_hash = _sha256(source)
    backup_hash = _sha256(target)
    restore_hash = _sha256(restore_target)
    if len({source_hash, backup_hash, restore_hash}) != 1:
        raise RuntimeError(f"File parity failed for {source}")
    return {
        "kind": "file",
        "source": str(source),
        "backup": str(target),
        "restore_dry_run": str(restore_target),
        "size": source.stat().st_size,
        "sha256": source_hash,
    }


def _resolve_main_db(config: dict[str, Any]) -> Path:
    raw = config.get("paths", {}).get("db_path", "./data/pb_studio.db")
    path = Path(str(raw))
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _project_roots(main_db: Path) -> list[tuple[int, Path]]:
    connection = sqlite3.connect(
        f"file:{main_db.as_posix()}?mode=ro", uri=True
    )
    try:
        result: list[tuple[int, Path]] = []
        for project_id, raw_json in connection.execute(
            "SELECT id, json_data FROM projects ORDER BY id"
        ):
            try:
                payload = json.loads(raw_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            raw_path = payload.get("path") if isinstance(payload, dict) else None
            if raw_path:
                result.append((int(project_id), Path(str(raw_path)).resolve()))
        return result
    finally:
        connection.close()


def _default_output_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is required on Windows")
    return Path(local_app_data) / "PB_Studio" / "recovery-control" / "v1" / "preflight"


def run(output_parent: Path) -> dict[str, Any]:
    config_path = REPO_ROOT / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    main_db = _resolve_main_db(config)
    if not main_db.is_file():
        raise FileNotFoundError(main_db)

    generation_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid4().hex[:8]
    )
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = output_parent / f".{generation_id}.staging"
    final = output_parent / generation_id
    staging.mkdir(parents=False, exist_ok=False)
    artifacts_root = staging / "artifacts"
    restore_root = staging / "restore-dry-run"

    records: list[dict[str, Any]] = []

    def backup_db(logical: str, source: Path) -> None:
        if not source.is_file():
            records.append({"logical_id": logical, "kind": "sqlite", "status": "absent", "source": str(source)})
            return
        relative = Path(*logical.split("/"))
        records.append(
            {
                "logical_id": logical,
                "status": "verified",
                **_backup_db(
                    source,
                    artifacts_root / relative,
                    restore_root / relative,
                ),
            }
        )

    def backup_file(logical: str, source: Path) -> None:
        if not source.is_file():
            records.append({"logical_id": logical, "kind": "file", "status": "absent", "source": str(source)})
            return
        relative = Path(*logical.split("/"))
        records.append(
            {
                "logical_id": logical,
                "status": "verified",
                **_backup_file(
                    source,
                    artifacts_root / relative,
                    restore_root / relative,
                ),
            }
        )

    backup_db("catalog/pb_studio.db", main_db)
    backup_file("config/config.json", config_path)

    project_roots = _project_roots(main_db)
    for project_id, project_root in project_roots:
        prefix = f"projects/{project_id}"
        backup_db(f"{prefix}/state.db", project_root / "state.db")
        for name in (
            "project.json",
            "timeline.json",
            "anchors.json",
            "chat_history.json",
            "state.db.brain-feedback-outbox.json",
        ):
            backup_file(f"{prefix}/{name}", project_root / name)

    app_data = os.environ.get("APPDATA")
    if not app_data:
        raise RuntimeError("APPDATA is required on Windows")
    brain_root = Path(app_data) / "PB_Studio" / "brain"
    for name in ("weights.db", "patterns.db", "embedding_cache.db"):
        backup_db(f"brain/{name}", brain_root / name)
    for name in (
        "feedback_outbox.json",
        "feedback_receipts.json",
        "cross_modal_projector.npz",
    ):
        backup_file(f"brain/{name}", brain_root / name)
    embeddings_root = brain_root / "embeddings"
    if embeddings_root.is_dir():
        for source in sorted(path for path in embeddings_root.rglob("*") if path.is_file()):
            relative = source.relative_to(embeddings_root).as_posix()
            backup_file(f"brain/embeddings/{relative}", source)

    wpf_settings = Path(app_data) / "PBStudio" / "settings.json"
    backup_file("config/wpf-settings.json", wpf_settings)

    manifest = {
        "schema_version": 1,
        "generation_id": generation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": os.environ.get("OBJ75_GIT_HEAD", "f8e1ad67750f3f2490e6ca5a09f5eff54093b847"),
        "source_main_db": str(main_db),
        "project_count": len(project_roots),
        "backend_was_manually_verified_stopped": True,
        "migration_executed": False,
        "records": records,
    }
    manifest_path = staging / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest["manifest_payload_sha256"] = _sha256(manifest_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    staging.replace(final)
    manifest["output"] = str(final)
    manifest["verified_records"] = sum(
        record.get("status") == "verified" for record in records
    )
    manifest["absent_records"] = sum(
        record.get("status") == "absent" for record in records
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-parent",
        type=Path,
        default=_default_output_root(),
    )
    args = parser.parse_args()
    result = run(args.output_parent.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
