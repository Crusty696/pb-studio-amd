"""Explicit, receipt-bound OBJ77 migration runner for fixture copies only.

Real targets are deliberately unsupported until a separate user approval is
bound to a real-scope receipt and an offline maintenance window.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from typing import Any, Iterable
import uuid

from pb_studio.data.database_core import DatabaseCore
from pb_studio.storage.migration_authorization import (
    MigrationApprovalError,
    MigrationAuthorization,
    canonical_json_sha256,
    read_approval,
    sha256_file,
    sqlite_bundle_sha256,
    validate_migration_approval,
)
from pb_studio.storage.migration_runner import split_sql_statements


EMBEDDINGS_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pb_studio"
    / "storage"
    / "migrations"
    / "embeddings"
    / "002_obj77_projected_brain_vectors.sql"
)


class MigrationExecutionError(RuntimeError):
    """The authorized migration failed and its fixture bundle was restored."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _sandbox_root(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if candidate.name == ".obj77-migration-sandbox":
            return candidate.resolve()
    raise MigrationApprovalError("Fixture target is outside .obj77-migration-sandbox")


def _journal_path(authorizations: list[MigrationAuthorization]) -> Path:
    roots = {_sandbox_root(item.target_path) for item in authorizations}
    if len(roots) != 1:
        raise MigrationApprovalError("All fixture targets must share one sandbox")
    return roots.pop() / f"obj77-migration-{authorizations[0].bundle_id}.journal.json"


def _write_json_durable(path: Path, payload: dict[str, Any]) -> None:
    sealed = dict(payload)
    sealed.pop("journal_sha256", None)
    sealed["journal_sha256"] = canonical_json_sha256(sealed)
    payload.clear()
    payload.update(sealed)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_journal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationExecutionError(f"migration journal is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise MigrationExecutionError("migration journal must be an object")
    expected = payload.get("journal_sha256")
    unsigned = dict(payload)
    unsigned.pop("journal_sha256", None)
    if expected != canonical_json_sha256(unsigned):
        raise MigrationExecutionError("migration journal hash mismatch")
    return payload


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        exit_code = ctypes.c_ulong()
        try:
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                process, ctypes.byref(exit_code)
            ):
                return False
            return exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, SystemError):
        return False


def _process_start_token(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return None
        creation = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        try:
            if not ctypes.windll.kernel32.GetProcessTimes(
                process,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            return str(creation.value)
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()[21]
    except (OSError, IndexError):
        return None


def _lock_owner_is_live(lock_path: Path) -> bool:
    try:
        owner = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(owner["pid"])
        token = str(owner["process_start_token"])
        nonce = str(uuid.UUID(str(owner["nonce"])))
        del nonce
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return True
    return _pid_is_alive(pid) and _process_start_token(pid) == token


@contextmanager
def _exclusive_bundle_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    owner = {
        "pid": os.getpid(),
        "process_start_token": _process_start_token(os.getpid()),
        "nonce": str(uuid.uuid4()),
        "created_at_utc": _utc_now(),
    }
    temporary = lock_path.with_name(f".{lock_path.name}.{owner['nonce']}.tmp")
    with temporary.open("xb") as handle:
        handle.write(json.dumps(owner, sort_keys=True).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    descriptor: int | None = None
    lock_error: Exception | None = None
    for attempt in range(12):
        try:
            os.link(temporary, lock_path)
            descriptor = os.open(str(lock_path), os.O_RDONLY)
            break
        except FileExistsError as exc:
            if _lock_owner_is_live(lock_path):
                if attempt < 3:
                    time.sleep(0.05)
                    continue
                lock_error = exc
                break
            lock_path.unlink(missing_ok=True)
    temporary.unlink(missing_ok=True)
    if descriptor is None:
        if lock_error is not None:
            raise MigrationExecutionError(
                f"migration lock already held: {lock_path}"
            ) from lock_error
        raise MigrationExecutionError(f"cannot acquire migration lock: {lock_path}")
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _require_closed_fixture_bundle(auth: MigrationAuthorization) -> None:
    for suffix in ("-wal", "-shm"):
        if Path(str(auth.target_path) + suffix).exists():
            raise MigrationApprovalError(
                f"Fixture SQLite sidecar must be checkpointed and absent: {suffix}"
            )


def _copy_exclusive(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def _restore(auth: MigrationAuthorization) -> None:
    if not auth.backup_path.is_file():
        raise MigrationExecutionError(f"backup missing: {auth.backup_path}")
    if sha256_file(auth.backup_path) != auth.backup_sha256:
        raise MigrationExecutionError(f"backup hash mismatch: {auth.backup_path}")
    temporary = auth.target_path.with_suffix(auth.target_path.suffix + ".rollback.tmp")
    with auth.backup_path.open("rb") as incoming, temporary.open("wb") as handle:
        shutil.copyfileobj(incoming, handle, length=1024 * 1024)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, auth.target_path)
    for suffix in ("-wal", "-shm"):
        Path(str(auth.target_path) + suffix).unlink(missing_ok=True)
    if sha256_file(auth.target_path) != auth.source_sha256:
        raise MigrationExecutionError(f"rollback hash mismatch: {auth.target_path}")


def _load_vec(connection: sqlite3.Connection) -> None:
    import sqlite_vec

    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)


def _read_embedding_inventory(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    _load_vec(connection)
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        units = int(connection.execute("SELECT COUNT(*) FROM video_units").fetchone()[0])
        vectors = int(
            connection.execute("SELECT COUNT(*) FROM video_embeddings").fetchone()[0]
        )
        return {
            "source_schema_version": version,
            "legacy_video_units": units,
            "legacy_video_rows": vectors,
            "required_regeneration": vectors,
        }
    finally:
        connection.close()


def _read_catalog_version(path: Path) -> int:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(version),0) FROM schema_migrations"
        ).fetchone()
        return int(row[0])
    finally:
        connection.close()


def dry_run_target(receipt: dict[str, Any]) -> dict[str, Any]:
    auth = validate_migration_approval(receipt, allowed_scope="fixture")
    _require_closed_fixture_bundle(auth)
    if auth.target_kind == "embeddings":
        inventory = _read_embedding_inventory(auth.target_path)
        if inventory["source_schema_version"] != auth.source_schema_version:
            raise MigrationApprovalError("Embedding source schema does not match receipt")
        return {
            "status": "migration_required",
            "target_kind": auth.target_kind,
            "target_path": str(auth.target_path),
            "target_schema_version": auth.target_schema_version,
            **inventory,
        }
    version = _read_catalog_version(auth.target_path)
    if version != auth.source_schema_version:
        raise MigrationApprovalError("Catalog source schema does not match receipt")
    return {
        "status": "migration_required",
        "target_kind": auth.target_kind,
        "target_path": str(auth.target_path),
        "source_schema_version": version,
        "target_schema_version": auth.target_schema_version,
    }


def _migrate_embeddings(
    auth: MigrationAuthorization,
    fault_at: str | None,
    connection: sqlite3.Connection,
) -> None:
    before = {
        "source_schema_version": int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        ),
        "legacy_video_units": int(
            connection.execute("SELECT COUNT(*) FROM video_units").fetchone()[0]
        ),
        "legacy_video_rows": int(
            connection.execute("SELECT COUNT(*) FROM video_embeddings").fetchone()[0]
        ),
    }
    if before["source_schema_version"] != 1:
        raise MigrationExecutionError("embedding fixture is not schema v1")
    connection.create_function(
        "sha256_blob",
        1,
        lambda value: __import__("hashlib").sha256(bytes(value)).hexdigest(),
    )
    connection.create_function("obj77_utc_now", 0, _utc_now)
    statements = split_sql_statements(EMBEDDINGS_MIGRATION.read_text(encoding="utf-8"))
    for statement in statements:
        connection.execute(statement)
        if (
            fault_at == "after_archive"
            and statement.lstrip().upper().startswith(
                "INSERT INTO VIDEO_EMBEDDINGS_LEGACY_768_ARCHIVE"
            )
        ):
            raise MigrationExecutionError("fault injection: after_archive")
    connection.execute(
        "INSERT INTO embedding_store_identity "
        "(singleton_id,project_uuid,owner_uuid,schema_version) VALUES (1,?,?,2)",
        (auth.project_uuid, auth.project_uuid),
    )
    connection.execute("PRAGMA user_version=2")

    archived_units = int(
        connection.execute(
            "SELECT COUNT(*) FROM video_units_legacy_768_archive"
        ).fetchone()[0]
    )
    archived_vectors = int(
        connection.execute(
            "SELECT COUNT(*) FROM video_embeddings_legacy_768_archive"
        ).fetchone()[0]
    )
    bad_hashes = int(
        connection.execute(
            "SELECT COUNT(*) FROM video_embeddings_legacy_768_archive "
            "WHERE embedding_sha256<>sha256_blob(embedding)"
        ).fetchone()[0]
    )
    if (
        archived_units != before["legacy_video_units"]
        or archived_vectors != before["legacy_video_rows"]
        or bad_hashes
    ):
        raise MigrationExecutionError("legacy embedding archive verification failed")
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise MigrationExecutionError("embedding quick_check failed")


def _migrate_catalog(
    auth: MigrationAuthorization,
    fault_at: str | None,
    connection: sqlite3.Connection,
) -> None:
    from pb_studio.data.database_core import SCHEMA_MIGRATIONS, _iter_sql_statements

    core = object.__new__(DatabaseCore)
    core._register_sql_functions(connection)
    version, name, sql = next(item for item in SCHEMA_MIGRATIONS if item[0] == 5)
    for index, statement in enumerate(_iter_sql_statements(sql), start=1):
        connection.execute(statement)
        if fault_at == f"catalog_after_alter:{index}":
            raise MigrationExecutionError(
                f"fault injection: catalog_after_alter:{index}"
            )
        if fault_at == f"hard_exit:catalog_after_alter:{index}":
            os._exit(97)
    core._backfill_vector_ownership(connection)
    if fault_at == "catalog_after_backfill":
        raise MigrationExecutionError("fault injection: catalog_after_backfill")
    if fault_at == "hard_exit:catalog_after_backfill":
        os._exit(97)
    connection.execute(
        "INSERT INTO schema_migrations (version,name) VALUES (?,?)",
        (version, name),
    )
    if fault_at == "catalog_before_version_receipt":
        raise MigrationExecutionError("fault injection: catalog_before_version_receipt")
    current = int(
        connection.execute(
            "SELECT COALESCE(MAX(version),0) FROM schema_migrations"
        ).fetchone()[0]
    )
    if current != 5 or connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise MigrationExecutionError("catalog migration verification failed")


def _receipt_digest(receipts: Iterable[dict[str, Any]]) -> str:
    return canonical_json_sha256(
        {"receipts": sorted(canonical_json_sha256(item) for item in receipts)}
    )


def _journal_identity_matches(
    journal: dict[str, Any],
    authorizations: list[MigrationAuthorization],
    receipt_digest: str,
) -> bool:
    records = journal.get("targets")
    if (
        journal.get("schema_version") != 1
        or journal.get("bundle_id") != authorizations[0].bundle_id
        or journal.get("receipt_digest") != receipt_digest
        or not isinstance(records, list)
        or len(records) != len(authorizations)
    ):
        return False
    return all(
        record.get("operation_id") == auth.operation_id
        and record.get("kind") == auth.target_kind
        and record.get("path") == str(auth.target_path)
        and record.get("before_sha256") == auth.source_sha256
        and record.get("backup_path") == str(auth.backup_path)
        for record, auth in zip(records, authorizations)
    )


def _converge_existing_journal(
    journal_path: Path,
    authorizations: list[MigrationAuthorization],
    receipt_digest: str,
) -> tuple[dict[str, Any] | None, bool]:
    if not journal_path.is_file():
        return None, False
    journal = _read_journal(journal_path)
    if not _journal_identity_matches(journal, authorizations, receipt_digest):
        raise MigrationExecutionError("existing migration journal identity mismatch")
    records = journal["targets"]
    if journal.get("state") == "COMMITTED":
        if any(
            not isinstance(record.get("after_sha256"), str)
            or sha256_file(auth.target_path) != record["after_sha256"]
            or sqlite_bundle_sha256(auth.target_path)
            != record.get("after_bundle_sha256")
            for record, auth in zip(records, authorizations)
        ):
            raise MigrationExecutionError("committed migration journal target mismatch")
        return journal, True
    if journal.get("state") not in {
        "VALIDATED",
        "BACKED_UP",
        "MIGRATING",
        "ROLLED_BACK",
        "ROLLBACK_FAILED",
    }:
        raise MigrationExecutionError("unknown nonterminal migration journal state")

    errors: list[str] = []
    for auth in reversed(authorizations):
        try:
            if auth.backup_path.is_file():
                _restore(auth)
            elif sha256_file(auth.target_path) != auth.source_sha256:
                raise MigrationExecutionError(
                    f"partial target lacks recovery backup: {auth.target_path}"
                )
        except Exception as exc:
            errors.append(str(exc))
    journal["state"] = "ROLLBACK_FAILED" if errors else "ROLLED_BACK"
    journal["finished_at_utc"] = _utc_now()
    if errors:
        journal["rollback_errors"] = errors
    _write_json_durable(journal_path, journal)
    if errors:
        raise MigrationExecutionError(
            f"nonterminal migration rollback failed: {'; '.join(errors)}"
        )
    return journal, False


def migrate_bundle(
    receipts: list[dict[str, Any]],
    *,
    fault_at: str | None = None,
) -> list[dict[str, Any]]:
    if not receipts:
        raise MigrationApprovalError("Migration bundle is empty")
    preliminary = [
        validate_migration_approval(item, allowed_scope="fixture", verify_source=False)
        for item in receipts
    ]
    if len({item.bundle_id for item in preliminary}) != 1:
        raise MigrationApprovalError("Migration receipts have different bundle IDs")
    if len({item.target_path for item in preliminary}) != len(preliminary):
        raise MigrationApprovalError("Migration bundle contains duplicate targets")
    if len({item.backup_path for item in preliminary}) != len(preliminary):
        raise MigrationApprovalError("Migration bundle contains duplicate backups")
    if {item.target_path for item in preliminary} & {
        item.backup_path for item in preliminary
    }:
        raise MigrationApprovalError("Migration targets and backups must be disjoint")
    journal_path = _journal_path(preliminary)
    receipt_digest = _receipt_digest(receipts)
    with _exclusive_bundle_lock(journal_path):
        _journal, committed = _converge_existing_journal(
            journal_path,
            preliminary,
            receipt_digest,
        )
        if committed:
            return [
                {"status": "already_migrated", "target_path": str(item.target_path)}
                for item in preliminary
            ]
        authorizations = [
            validate_migration_approval(item, allowed_scope="fixture")
            for item in receipts
        ]
        for auth in authorizations:
            _require_closed_fixture_bundle(auth)
            dry_run_target(receipts[authorizations.index(auth)])

        journal: dict[str, Any] = {
            "schema_version": 1,
            "bundle_id": authorizations[0].bundle_id,
            "receipt_digest": receipt_digest,
            "state": "VALIDATED",
            "started_at_utc": _utc_now(),
            "targets": [
                {
                    "operation_id": item.operation_id,
                    "kind": item.target_kind,
                    "path": str(item.target_path),
                    "before_sha256": item.source_sha256,
                    "backup_path": str(item.backup_path),
                    "state": "VALIDATED",
                }
                for item in authorizations
            ],
        }
        _write_json_durable(journal_path, journal)
        connections: list[sqlite3.Connection | None] = []
        try:
            for auth in authorizations:
                connection = sqlite3.connect(
                    str(auth.target_path),
                    isolation_level=None,
                    timeout=5.0,
                )
                connection.execute("PRAGMA busy_timeout=5000")
                connection.execute("PRAGMA foreign_keys=ON")
                if auth.target_kind == "embeddings":
                    _load_vec(connection)
                else:
                    connection.row_factory = sqlite3.Row
                connection.execute("BEGIN EXCLUSIVE")
                connections.append(connection)

            for auth in authorizations:
                if (
                    sha256_file(auth.target_path) != auth.source_sha256
                ):
                    raise MigrationExecutionError(
                        f"target changed before locked backup: {auth.target_path}"
                    )

            for index, auth in enumerate(authorizations, start=1):
                if auth.backup_path.is_file():
                    if sha256_file(auth.backup_path) != auth.backup_sha256:
                        raise MigrationExecutionError(
                            f"existing backup hash mismatch: {auth.backup_path}"
                        )
                else:
                    _copy_exclusive(auth.target_path, auth.backup_path)
                if sha256_file(auth.backup_path) != auth.backup_sha256:
                    raise MigrationExecutionError(f"backup verification failed: {auth.backup_path}")
                journal["targets"][index - 1]["state"] = "BACKED_UP"
                journal["state"] = "BACKED_UP"
                _write_json_durable(journal_path, journal)
                if fault_at == f"hard_exit:after_backup:{index}":
                    os._exit(97)

            if any(
                sha256_file(auth.target_path) != auth.source_sha256
                for auth in authorizations
            ):
                raise MigrationExecutionError("target changed after locked backup")

            journal["state"] = "MIGRATING"
            _write_json_durable(journal_path, journal)
            for index, (auth, connection) in enumerate(
                zip(authorizations, connections), start=1
            ):
                if auth.target_kind == "embeddings":
                    _migrate_embeddings(auth, fault_at, connection)
                else:
                    _migrate_catalog(auth, fault_at, connection)
                connection.execute("COMMIT")
                if fault_at == f"hard_exit:after_db_commit:{index}":
                    os._exit(97)
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                connection.close()
                connections[index - 1] = None
                if auth.target_kind == "embeddings":
                    from pb_studio.storage.recovery_generation import (
                        validate_sqlite_vec_database,
                    )

                    validate_sqlite_vec_database(auth.target_path)
                journal["targets"][index - 1].update(
                    state="COMMITTED",
                    after_sha256=sha256_file(auth.target_path),
                    after_bundle_sha256=sqlite_bundle_sha256(auth.target_path),
                )
                _write_json_durable(journal_path, journal)
                if fault_at == f"hard_exit:after_target_commit:{index}":
                    os._exit(97)
                if fault_at == f"after_target_commit:{index}":
                    raise MigrationExecutionError(
                        f"fault injection: after_target_commit:{index}"
                    )
            journal["state"] = "COMMITTED"
            journal["finished_at_utc"] = _utc_now()
            _write_json_durable(journal_path, journal)
            for connection in connections:
                if connection is not None:
                    connection.close()
            return [
                {
                    "status": "migrated",
                    "target_kind": item.target_kind,
                    "target_path": str(item.target_path),
                    "backup_path": str(item.backup_path),
                    "journal_path": str(journal_path),
                }
                for item in authorizations
            ]
        except Exception as exc:
            for connection in connections:
                if connection is None:
                    continue
                try:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                finally:
                    connection.close()
            restore_errors: list[str] = []
            for auth in reversed(authorizations):
                if auth.backup_path.is_file():
                    try:
                        _restore(auth)
                    except Exception as restore_exc:
                        restore_errors.append(str(restore_exc))
            journal["state"] = "ROLLBACK_FAILED" if restore_errors else "ROLLED_BACK"
            journal["finished_at_utc"] = _utc_now()
            journal["error"] = str(exc)
            if restore_errors:
                journal["rollback_errors"] = restore_errors
            _write_json_durable(journal_path, journal)
            if restore_errors:
                raise MigrationExecutionError(
                    f"migration failed and rollback failed: {'; '.join(restore_errors)}"
                ) from exc
            if isinstance(exc, MigrationExecutionError):
                raise
            raise MigrationExecutionError(f"migration failed: {exc}") from exc


def migrate_target(
    receipt: dict[str, Any],
    *,
    fault_at: str | None = None,
) -> dict[str, Any]:
    return migrate_bundle([receipt], fault_at=fault_at)[0]


def rollback_target(receipt: dict[str, Any]) -> dict[str, Any]:
    auth = validate_migration_approval(
        receipt,
        allowed_scope="fixture",
        verify_source=False,
    )
    journal = _journal_path([auth])
    with _exclusive_bundle_lock(journal):
        _restore(auth)
        if journal.is_file():
            payload = _read_journal(journal)
            if not _journal_identity_matches(
                payload,
                [auth],
                _receipt_digest([receipt]),
            ):
                raise MigrationExecutionError("rollback journal identity mismatch")
            payload["state"] = "ROLLED_BACK"
            payload["finished_at_utc"] = _utc_now()
            _write_json_durable(journal, payload)
        return {
            "status": "rolled_back",
            "target_path": str(auth.target_path),
            "backup_path": str(auth.backup_path),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipts = [read_approval(path)[0] for path in args.receipt]
        if args.dry_run:
            result: Any = [dry_run_target(item) for item in receipts]
        elif args.rollback:
            if len(receipts) != 1:
                raise MigrationApprovalError("Rollback accepts exactly one receipt")
            result = rollback_target(receipts[0])
        else:
            result = migrate_bundle(receipts)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (MigrationApprovalError, MigrationExecutionError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
