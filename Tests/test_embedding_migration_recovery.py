from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import numpy as np
import pytest
import sqlite_vec


PROJECT_UUID = "98cbb214-5438-4701-a96b-5c1220901ce4"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_vec(connection: sqlite3.Connection) -> None:
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)


def _legacy_embeddings(path: Path) -> bytes:
    connection = sqlite3.connect(str(path), isolation_level=None)
    _load_vec(connection)
    migration = Path("src/pb_studio/storage/migrations/embeddings/001_initial.sql")
    connection.executescript(migration.read_text(encoding="utf-8"))
    raw = np.linspace(-1.0, 1.0, 768, dtype=np.float32).tobytes()
    connection.execute(
        "INSERT INTO video_units(id,parent_id,level,media_id,media_hash,start_time,end_time) "
        "VALUES (7,NULL,'scene',42,'media-hash',0.0,2.0)"
    )
    connection.execute(
        "INSERT INTO video_embeddings(rowid,embedding) VALUES (?,?)",
        (7, raw),
    )
    connection.execute("PRAGMA user_version=1")
    connection.close()
    return raw


def _legacy_embeddings_wal(path: Path) -> bytes:
    connection = sqlite3.connect(str(path), isolation_level=None)
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    _load_vec(connection)
    migration = Path("src/pb_studio/storage/migrations/embeddings/001_initial.sql")
    connection.executescript(migration.read_text(encoding="utf-8"))
    raw = np.linspace(-1.0, 1.0, 768, dtype=np.float32).tobytes()
    connection.execute(
        "INSERT INTO video_units(id,parent_id,level,media_id,media_hash,start_time,end_time) "
        "VALUES (7,NULL,'scene',42,'media-hash',0.0,2.0)"
    )
    connection.execute("INSERT INTO video_embeddings(rowid,embedding) VALUES(7,?)", (raw,))
    connection.execute("PRAGMA user_version=1")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    return raw


def _approval(target: Path, backup: Path, *, kind: str = "embeddings") -> dict:
    from pb_studio.storage.migration_authorization import prepare_fixture_approval

    return prepare_fixture_approval(
        target_path=target,
        target_kind=kind,
        source_schema_version=1 if kind == "embeddings" else 4,
        target_schema_version=2 if kind == "embeddings" else 5,
        project_uuid=PROJECT_UUID,
        backup_path=backup,
        approved_at_utc="2026-08-12T12:00:00Z",
        approval_source="user_explicit_turn",
    )


def test_existing_legacy_embedding_constructor_fails_before_mutation(tmp_path: Path):
    from pb_studio.storage.embedding_contract import EmbeddingMigrationRequiredError
    from pb_studio.storage.embedding_repository import EmbeddingRepository

    target = tmp_path / "embeddings.db"
    _legacy_embeddings(target)
    before = _sha256(target)

    with pytest.raises(EmbeddingMigrationRequiredError, match="migration_required"):
        EmbeddingRepository(target)

    assert _sha256(target) == before
    assert not Path(str(target) + "-wal").exists()
    assert not Path(str(target) + "-shm").exists()
    connection = sqlite3.connect(str(target))
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        connection.close()


def test_dry_run_reports_without_mutating_source_or_creating_backup(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import dry_run_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings(target)
    backup = sandbox / "backup.db"
    receipt = _approval(target, backup)
    before = _sha256(target)

    report = dry_run_target(receipt)

    assert report["status"] == "migration_required"
    assert report["source_schema_version"] == 1
    assert report["target_schema_version"] == 2
    assert report["legacy_video_rows"] == 1
    assert report["required_regeneration"] == 1
    assert _sha256(target) == before
    assert not backup.exists()


def test_wal_mode_fixture_migrates_without_self_generated_bundle_drift(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings_wal(target)
    result = migrate_target(_approval(target, sandbox / "wal-backup.db"))

    assert result["status"] == "migrated"
    connection = sqlite3.connect(str(target), isolation_level=None)
    _load_vec(connection)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_approved_embedding_migration_archives_bytes_and_creates_new_contracts(
    tmp_path: Path,
):
    from pb_studio.storage.embedding_repository import EmbeddingRepository, VIDEO_DIM
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    legacy = _legacy_embeddings(target)
    backup = sandbox / "backup.db"
    source_hash = _sha256(target)

    result = migrate_target(_approval(target, backup))

    assert result["status"] == "migrated"
    assert _sha256(backup) == source_hash
    connection = sqlite3.connect(str(target), isolation_level=None)
    _load_vec(connection)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        archived = connection.execute(
            "SELECT embedding,embedding_sha256,regeneration_required FROM "
            "video_embeddings_legacy_768_archive WHERE rowid=7"
        ).fetchone()
        assert bytes(archived[0]) == legacy
        assert archived[1] == hashlib.sha256(legacy).hexdigest()
        assert archived[2] == 1
        unit = connection.execute(
            "SELECT media_id,media_hash,start_time,end_time FROM "
            "video_units_legacy_768_archive WHERE id=7"
        ).fetchone()
        assert unit == (42, "media-hash", 0.0, 2.0)
        assert connection.execute("SELECT COUNT(*) FROM video_units").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM video_embeddings").fetchone()[0] == 0
        video_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='video_embeddings'"
        ).fetchone()[0]
        brain_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='brain_embeddings'"
        ).fetchone()[0]
        assert "FLOAT[1152]" in video_sql
        assert "FLOAT[256]" in brain_sql
        assert "distance_metric=cosine" in brain_sql
        identity = connection.execute(
            "SELECT project_uuid,schema_version FROM embedding_store_identity"
        ).fetchone()
        assert identity == (PROJECT_UUID, 2)
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()

    repo = EmbeddingRepository(target)
    try:
        vector = np.ones(VIDEO_DIM, dtype=np.float32)
        unit_id = repo.add_video_unit(
            parent_id=None,
            level="scene",
            media_id=99,
            media_hash="new-1152",
            start_time=0.0,
            end_time=1.0,
            embedding=vector,
        )
        assert repo.search_video(vector, limit=1)[0].unit_id == unit_id
    finally:
        repo.close()


def test_fault_after_archive_restores_byte_identical_source(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import MigrationExecutionError, migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings(target)
    backup = sandbox / "backup.db"
    source = target.read_bytes()

    with pytest.raises(MigrationExecutionError, match="after_archive"):
        migrate_target(_approval(target, backup), fault_at="after_archive")

    assert target.read_bytes() == source
    assert backup.read_bytes() == source


def test_bundle_fault_after_second_target_rolls_every_target_back(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import (
        MigrationExecutionError,
        migrate_bundle,
    )

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    embeddings = sandbox / "embeddings.db"
    _legacy_embeddings(embeddings)
    catalog = sandbox / "pb_studio.db"
    _legacy_catalog(catalog)
    embeddings_before = embeddings.read_bytes()
    catalog_before = catalog.read_bytes()
    bundle_id = "018f7784-69f7-7bf4-b392-838a94ed3fab"
    embedding_receipt = _approval(embeddings, sandbox / "embeddings.backup.db")
    catalog_receipt = _approval(catalog, sandbox / "catalog.backup.db", kind="catalog")
    embedding_receipt["bundle_id"] = bundle_id
    catalog_receipt["bundle_id"] = bundle_id

    with pytest.raises(MigrationExecutionError, match="after_target_commit"):
        migrate_bundle(
            [embedding_receipt, catalog_receipt],
            fault_at="after_target_commit:2",
        )

    assert embeddings.read_bytes() == embeddings_before
    assert catalog.read_bytes() == catalog_before
    journal = sandbox / f"obj77-migration-{bundle_id}.journal.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert payload["state"] == "ROLLED_BACK"


def test_explicit_rollback_restores_original_and_keeps_backup(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import migrate_target, rollback_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    original = _legacy_embeddings(target)
    del original
    source = target.read_bytes()
    backup = sandbox / "backup.db"
    receipt = _approval(target, backup)
    migrate_target(receipt)

    rollback = rollback_target(receipt)

    assert rollback["status"] == "rolled_back"
    assert target.read_bytes() == source
    assert backup.read_bytes() == source
    assert migrate_target(receipt)["status"] == "migrated"


@pytest.mark.parametrize(
    "kind,fault",
    [
        ("embeddings", "hard_exit:after_backup:1"),
        ("embeddings", "hard_exit:after_db_commit:1"),
        ("embeddings", "hard_exit:after_target_commit:1"),
        ("catalog", "hard_exit:catalog_after_alter:1"),
        ("catalog", "hard_exit:catalog_after_backfill"),
    ],
)
def test_hard_kill_journal_converges_then_retries_idempotently(
    tmp_path: Path,
    kind: str,
    fault: str,
):
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / ("embeddings.db" if kind == "embeddings" else "pb_studio.db")
    if kind == "embeddings":
        _legacy_embeddings(target)
    else:
        _legacy_catalog(target)
    original = target.read_bytes()
    receipt = _approval(target, sandbox / f"{kind}.backup.db", kind=kind)
    receipt_path = sandbox / f"{kind}.approval.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    code = (
        "import json; from scripts.requirements.migrate_obj77_embeddings "
        "import migrate_target; "
        f"r=json.load(open(r'{receipt_path}',encoding='utf-8')); "
        f"migrate_target(r,fault_at='{fault}')"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src;."

    child = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert child.returncode == 97
    assert (sandbox / f"{kind}.backup.db").read_bytes() == original
    result = migrate_target(receipt)
    assert result["status"] == "migrated"
    assert migrate_target(receipt)["status"] == "already_migrated"


def test_new_store_hardkill_after_v1_restarts_as_atomic_v2(tmp_path: Path):
    from pb_studio.storage.embedding_repository import EmbeddingRepository

    target = tmp_path / "new" / "embeddings.db"
    code = (
        "import os; from pb_studio.storage.embedding_repository import EmbeddingRepository; "
        f"EmbeddingRepository(r'{target}',project_uuid='{PROJECT_UUID}',"
        "_migration_fault_injector=lambda stage: os._exit(97) "
        "if stage=='after_schema:1' else None)"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src;."
    child = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        timeout=30,
    )
    assert child.returncode == 97

    repository = EmbeddingRepository(target, project_uuid=PROJECT_UUID)
    try:
        assert repository.project_uuid == PROJECT_UUID
    finally:
        repository.close()


def test_parallel_lock_publication_allows_exactly_one_owner(tmp_path: Path):
    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    journal = sandbox / "parallel.journal.json"
    start = sandbox / "start"
    outputs = [sandbox / "worker-1.txt", sandbox / "worker-2.txt"]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src;."
    processes = []
    for output in outputs:
        code = (
            "import time; from pathlib import Path; "
            "from scripts.requirements.migrate_obj77_embeddings import "
            "_exclusive_bundle_lock,MigrationExecutionError; "
            f"start=Path(r'{start}'); out=Path(r'{output}'); "
            "\nwhile not start.exists(): time.sleep(0.01)\n"
            "try:\n"
            f"  with _exclusive_bundle_lock(Path(r'{journal}')):\n"
            "    out.write_text('ACQUIRED',encoding='utf-8'); time.sleep(1.0)\n"
            "except MigrationExecutionError:\n"
            "  out.write_text('BLOCKED',encoding='utf-8')\n"
        )
        processes.append(
            subprocess.Popen(
                [sys.executable, "-c", code],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
            )
        )
    start.write_text("go", encoding="ascii")
    for process in processes:
        assert process.wait(timeout=15) == 0

    assert sorted(path.read_text(encoding="utf-8") for path in outputs) == [
        "ACQUIRED",
        "BLOCKED",
    ]


def _legacy_catalog(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT,applied_at TEXT);
        INSERT INTO schema_migrations(version,name) VALUES
          (1,'core_schema'),(2,'media_import_guard'),(3,'vector_operation_outbox'),(4,'stable_project_uuid');
        CREATE TABLE projects(id INTEGER PRIMARY KEY,name TEXT,project_uuid TEXT);
        CREATE TABLE media(id INTEGER PRIMARY KEY,project_id INTEGER,file_path TEXT,file_hash TEXT);
        CREATE TABLE vector_map(faiss_id INTEGER PRIMARY KEY,media_id INTEGER,segment_start REAL,segment_end REAL,description TEXT);
        INSERT INTO projects VALUES(1,'Project','98cbb214-5438-4701-a96b-5c1220901ce4');
        INSERT INTO media VALUES(10,1,'clip.mp4','media-hash');
        INSERT INTO vector_map VALUES(100,10,0.0,1.0,'provable');
        INSERT INTO vector_map VALUES(101,999,0.0,1.0,'orphan');
        """
    )
    connection.commit()
    connection.close()


def test_catalog_migration_backfills_only_provable_vector_owners(tmp_path: Path):
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "pb_studio.db"
    _legacy_catalog(target)
    backup = sandbox / "catalog-backup.db"

    result = migrate_target(_approval(target, backup, kind="catalog"))

    assert result["status"] == "migrated"
    connection = sqlite3.connect(str(target))
    try:
        rows = connection.execute(
            "SELECT faiss_id,project_id,project_uuid,media_hash,recovery_generation,"
            "verification_status,write_receipt_json FROM vector_map ORDER BY faiss_id"
        ).fetchall()
        assert rows[0][:6] == (
            100,
            1,
            PROJECT_UUID,
            "media-hash",
            None,
            "legacy_unverified",
        )
        assert rows[0][6] is None
        assert rows[1][1:5] == (None, None, None, None)
        assert rows[1][5] == "legacy_unverified"
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=5"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_existing_catalog_preflight_fails_before_any_mutation(tmp_path: Path):
    from pb_studio.data.database_core import DatabaseCore
    from pb_studio.storage.migration_authorization import (
        DatabaseMigrationRequiredError,
    )

    target = tmp_path / "pb_studio.db"
    _legacy_catalog(target)
    before = _sha256(target)
    core = object.__new__(DatabaseCore)
    core.db_path = target

    with pytest.raises(DatabaseMigrationRequiredError, match="migration_required"):
        core._preflight_existing_schema_read_only()

    assert _sha256(target) == before
    assert not Path(str(target) + "-wal").exists()
    assert not Path(str(target) + "-shm").exists()


def test_sqlite_vec_generation_backup_and_restore_are_semantically_verified(
    tmp_path: Path,
):
    from backend.recovery_bootstrap import ensure_recovery_ready
    from pb_studio.storage.embedding_repository import EmbeddingRepository, VIDEO_DIM
    from pb_studio.storage.recovery_generation import (
        RecoveryGenerationWriter,
        request_restore_generation,
        validate_generation,
    )
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings(target)
    migrate_target(_approval(target, sandbox / "pre-v2.db"))
    control = tmp_path / "control"
    digest = "7" * 64

    old_writer = RecoveryGenerationWriter(
        control_root=control,
        generation_id="vec-old",
        config_digest=digest,
        project_inventory_digest=digest,
    )
    old_writer.add_sqlite_vec(
        "project:embeddings",
        target,
        group="project",
        owner="ProjectLifecycle",
        owner_scope=sandbox,
    )
    old = old_writer.commit()
    old_manifest = validate_generation(control, old.generation_id)
    artifact = old_manifest["artifacts"][0]
    assert artifact["adapter"] == "sqlite_vec_backup"
    assert artifact["sqlite_vec_receipt"]["dimensions"] == {
        "brain_embeddings": 256,
        "video_embeddings": 1152,
    }

    repository = EmbeddingRepository(target)
    try:
        vector = np.ones(VIDEO_DIM, dtype=np.float32)
        repository.add_video_unit(
            parent_id=None,
            level="scene",
            media_id=99,
            media_hash="generation-two",
            start_time=0.0,
            end_time=1.0,
            embedding=vector,
        )
    finally:
        repository.close()

    new_writer = RecoveryGenerationWriter(
        control_root=control,
        generation_id="vec-new",
        config_digest=digest,
        project_inventory_digest=digest,
    )
    new_writer.add_sqlite_vec(
        "project:embeddings",
        target,
        group="project",
        owner="ProjectLifecycle",
        owner_scope=sandbox,
    )
    new_writer.commit()

    request_restore_generation(old.generation_id, control_root=control)
    result = ensure_recovery_ready(control)

    assert result.status == "recovered"
    connection = sqlite3.connect(str(target), isolation_level=None)
    _load_vec(connection)
    try:
        assert connection.execute("SELECT COUNT(*) FROM video_units").fetchone()[0] == 0
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_new_store_is_atomically_owner_bound_and_recovery_ready(tmp_path: Path):
    from pb_studio.storage.embedding_repository import EmbeddingRepository
    from pb_studio.storage.recovery_generation import (
        RecoveryGenerationWriter,
        validate_generation,
        validate_sqlite_vec_database,
    )

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    repository = EmbeddingRepository(target, project_uuid=PROJECT_UUID)
    repository.close()

    receipt = validate_sqlite_vec_database(target)
    assert receipt["project_uuid"] == PROJECT_UUID
    assert receipt["owner_uuid"] == PROJECT_UUID
    writer = RecoveryGenerationWriter(
        control_root=tmp_path / "control",
        generation_id="new-owner-store",
        config_digest="8" * 64,
        project_inventory_digest="8" * 64,
    )
    writer.add_sqlite_vec(
        "project:embeddings",
        target,
        group="project",
        owner="ProjectLifecycle",
        owner_scope=sandbox,
    )
    committed = writer.commit()
    manifest = validate_generation(tmp_path / "control", committed.generation_id)
    assert manifest["artifacts"][0]["sqlite_vec_receipt"]["project_uuid"] == PROJECT_UUID


def test_recovery_knn_accepts_identical_vector_ties(tmp_path: Path):
    from pb_studio.storage.embedding_repository import EmbeddingRepository, VIDEO_DIM
    from pb_studio.storage.recovery_generation import validate_sqlite_vec_database

    target = tmp_path / "embeddings.db"
    repository = EmbeddingRepository(target, project_uuid=PROJECT_UUID)
    try:
        vector = np.ones(VIDEO_DIM, dtype=np.float32)
        for media_id in (1, 2):
            repository.add_video_unit(
                parent_id=None,
                level="scene",
                media_id=media_id,
                media_hash=f"same-{media_id}",
                start_time=0.0,
                end_time=1.0,
                embedding=vector,
            )
    finally:
        repository.close()

    assert validate_sqlite_vec_database(target)["counts"]["video_embeddings"] == 2


def test_corrupt_sqlite_vec_archive_fails_recovery_validation(tmp_path: Path):
    from pb_studio.storage.recovery_generation import (
        RecoveryGenerationValidationError,
        validate_sqlite_vec_database,
    )
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings(target)
    migrate_target(_approval(target, sandbox / "pre-v2.db"))

    connection = sqlite3.connect(str(target), isolation_level=None)
    _load_vec(connection)
    try:
        connection.execute(
            "UPDATE video_embeddings_legacy_768_archive "
            "SET embedding_sha256=? WHERE rowid=7",
            ("0" * 64,),
        )
    finally:
        connection.close()

    with pytest.raises(
        RecoveryGenerationValidationError,
        match="legacy archive",
    ):
        validate_sqlite_vec_database(target)


@pytest.mark.parametrize(
    "corruption",
    ["distance_metric", "row_identity", "store_identity", "foreign_key"],
)
def test_sqlite_vec_semantic_corruption_fails_closed(
    tmp_path: Path,
    corruption: str,
):
    from pb_studio.storage.recovery_generation import (
        RecoveryGenerationValidationError,
        validate_sqlite_vec_database,
    )
    from scripts.requirements.migrate_obj77_embeddings import migrate_target

    sandbox = tmp_path / ".obj77-migration-sandbox"
    sandbox.mkdir()
    target = sandbox / "embeddings.db"
    _legacy_embeddings(target)
    migrate_target(_approval(target, sandbox / "pre-v2.db"))
    connection = sqlite3.connect(str(target), isolation_level=None)
    _load_vec(connection)
    try:
        if corruption == "distance_metric":
            connection.execute("PRAGMA writable_schema=ON")
            connection.execute(
                "UPDATE sqlite_master SET sql=replace(sql,' distance_metric=cosine','') "
                "WHERE name='brain_embeddings'"
            )
            connection.execute("PRAGMA writable_schema=OFF")
        elif corruption == "row_identity":
            connection.execute(
                "INSERT INTO video_units(id,parent_id,level,media_id,media_hash,"
                "start_time,end_time) VALUES(8,NULL,'scene',1,'hash',0,1)"
            )
            connection.execute(
                "INSERT INTO video_embeddings(rowid,embedding) VALUES(9,?)",
                (np.ones(1152, dtype=np.float32).tobytes(),),
            )
        elif corruption == "store_identity":
            connection.execute(
                "UPDATE embedding_store_identity SET owner_uuid='not-a-uuid'"
            )
        else:
            blob = np.ones(768, dtype=np.float32).tobytes()
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(
                "INSERT INTO video_embeddings_legacy_768_archive "
                "(rowid,embedding,embedding_sha256,archived_at_utc,regeneration_required) "
                "VALUES(999,?,?,?,1)",
                (blob, hashlib.sha256(blob).hexdigest(), "2026-08-12T12:00:00Z"),
            )
    finally:
        connection.close()

    with pytest.raises(RecoveryGenerationValidationError):
        validate_sqlite_vec_database(target)
