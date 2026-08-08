import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from pb_studio.config_manager import ConfigManager
from pb_studio.data.database_core import DatabaseCore
from pb_studio.data.repositories import media_repository as media_repository_module
from pb_studio.data.repositories.media_repository import MediaRepository
from pb_studio.services.media_service import MediaService


class _TempConfig:
    def __init__(self, db_path: Path):
        self._config = {"paths": {"db_path": str(db_path)}}

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def resolve_path(self, value: str) -> Path:
        return Path(value).resolve()


def _reset_db_singletons():
    DatabaseCore._instance = None
    DatabaseCore._local = type(DatabaseCore._local)()
    DatabaseCore._all_connections = []


def _create_legacy_media_db(db_path: Path, media_rows):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            json_data TEXT
        );

        CREATE TABLE media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            file_path TEXT NOT NULL,
            file_hash TEXT,
            duration_sec REAL,
            status TEXT DEFAULT 'pending',
            metadata_json TEXT,
            ai_data_json TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE vector_map (
            faiss_id INTEGER PRIMARY KEY,
            media_id INTEGER,
            segment_start REAL,
            segment_end REAL,
            description TEXT,
            FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
        );

        INSERT INTO projects (id, name) VALUES (1, 'Legacy Project');
        """
    )
    conn.executemany(
        """
        INSERT INTO media (
            id, project_id, file_path, file_hash, duration_sec, status, metadata_json, ai_data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        media_rows,
    )
    conn.commit()
    conn.close()


def test_add_media_is_idempotent_per_project_and_path(tmp_path, monkeypatch):
    db_path = tmp_path / "media_idempotent.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    first_id = repo.add_media(1, str(media_file), "hash-a", 1.0, {"clip_type": "audio"})
    second_id = repo.add_media(1, str(media_file), "hash-b", 2.5, {"clip_type": "audio", "name": "updated"})

    assert first_id == second_id
    rows = repo.get_by_project(1)
    assert len(rows) == 1
    assert rows[0]["file_hash"] == "hash-b"
    assert rows[0]["duration_sec"] == 2.5

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_wmv_writes_persist_video_schema_versions(tmp_path, monkeypatch):
    db_path = tmp_path / "media_schema_version.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "legacy-video.wmv"
    media_file.write_bytes(b"video")

    media_id = repo.add_media(
        1,
        str(media_file),
        "hash-video",
        2.0,
        {"clip_type": "video"},
    )
    repo.update_status(media_id, "ready", ai_data={"scene_count": 2})

    row = DatabaseCore().get_connection().execute(
        "SELECT metadata_json, ai_data_json FROM media WHERE id = ?",
        (media_id,),
    ).fetchone()
    metadata = __import__("json").loads(row["metadata_json"])
    ai_data = __import__("json").loads(row["ai_data_json"])

    assert metadata["__schema_version"] == 1
    assert metadata["video_hash"] == ""
    assert "audio_hash" not in metadata
    assert ai_data["__schema_version"] == 1
    assert ai_data["has_embedding"] is False
    assert "subtrack_segments" not in ai_data

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_existing_db_is_migrated_and_guard_backfilled(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_media.db"
    legacy_path = tmp_path / "legacy_clip.wav"
    legacy_path.write_bytes(b"legacy")

    _create_legacy_media_db(
        db_path,
        [
            (1, 1, str(legacy_path), "hash-a", 1.0, "pending", "{}", None),
            (2, 1, str(legacy_path), "hash-b", 2.0, "ready", '{"codec":"wav"}', '{"tag":"x"}'),
        ],
    )

    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    canonical = repo.find_by_project_and_path(1, str(legacy_path))
    assert canonical is not None
    assert canonical["id"] == 1

    conn = DatabaseCore().get_connection()
    guard_rows = conn.execute(
        """
        SELECT project_id, normalized_file_path, media_id
        FROM media_import_guard
        ORDER BY project_id, normalized_file_path
        """
    ).fetchall()
    assert len(guard_rows) == 1
    assert guard_rows[0]["media_id"] == 1

    versions = [
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    ]
    assert versions == [1, 2, 3]

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO media (project_id, file_path, file_hash, duration_sec, metadata_json, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (1, str(legacy_path), "hash-c", 3.0, "{}"),
        )

    media_id = repo.add_media(1, str(legacy_path), "hash-updated", 4.0, {"codec": "wav"})
    assert media_id == 1
    updated = repo.get_by_id(media_id)
    assert updated["file_hash"] == "hash-updated"
    assert updated["duration_sec"] == 4.0

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_media_service_reimport_skips_duplicate_rows_for_real_file(tmp_path, monkeypatch):
    db_path = tmp_path / "media_service.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    media_file = tmp_path / "song.mp3"
    media_file.write_bytes(b"ID3" + b"x" * 512)

    service = MediaService()
    monkeypatch.setattr(service, "_get_metadata", lambda path: {"duration": 3.0, "format": "mp3"})

    first = service.import_files(1, [str(media_file)])
    second = service.import_files(1, [str(media_file)])
    rows = service.get_project_files(1)

    assert first == second
    assert len(rows) == 1
    assert Path(rows[0]["file_path"]).resolve() == media_file.resolve()

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_concurrent_reimport_returns_single_canonical_row(tmp_path, monkeypatch):
    db_path = tmp_path / "media_concurrent.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    media_file = tmp_path / "parallel.mp4"
    media_file.write_bytes(b"parallel")

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker(file_hash: str, duration: float):
        try:
            repo = MediaRepository()
            barrier.wait(timeout=5)
            media_id = repo.add_media(1, str(media_file), file_hash, duration, {"duration": duration})
            results.append(media_id)
        except Exception as exc:  # pragma: no cover - assertion below reports details
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("hash-a", 1.0)),
        threading.Thread(target=worker, args=("hash-b", 2.0)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    assert len(results) == 2
    assert results[0] == results[1]

    repo = MediaRepository()
    rows = repo.get_by_project(1)
    guard_rows = DatabaseCore().get_connection().execute(
        "SELECT media_id FROM media_import_guard WHERE project_id = ?",
        (1,),
    ).fetchall()

    assert len(rows) == 1
    assert len(guard_rows) == 1
    assert rows[0]["id"] == guard_rows[0]["media_id"]

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


# ---------------------------------------------------------------------------
# Idempotency hardening: retry on transient SQLite "database is locked"
# errors with exponential backoff (50ms / 100ms / 200ms / 400ms / 800ms).
# ---------------------------------------------------------------------------


def test_add_media_retries_on_database_locked_with_exponential_backoff(tmp_path, monkeypatch):
    """add_media() retries on transient ``database is locked`` errors and
    eventually succeeds. Verifies the exponential backoff schedule
    (50ms, 100ms, 200ms, 400ms, 800ms) is applied in order."""
    db_path = tmp_path / "media_lock_retry.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    sleep_calls: list = []
    monkeypatch.setattr(
        media_repository_module.time, "sleep", lambda d: sleep_calls.append(d)
    )

    db = DatabaseCore()
    real_transaction = db.transaction
    call_counter = {"count": 0}

    @contextmanager
    def flaky_transaction(*args, **kwargs):
        call_counter["count"] += 1
        if call_counter["count"] <= 2:
            raise sqlite3.OperationalError("database is locked")
        with real_transaction(*args, **kwargs) as conn:
            yield conn

    monkeypatch.setattr(db, "transaction", flaky_transaction)

    media_id = repo.add_media(1, str(media_file), "hash-retry", 1.0, {"clip_type": "audio"})

    assert media_id is not None and media_id > 0
    # 1 initial + 2 retries = 3 calls total.
    assert call_counter["count"] == 3
    # Exponential backoff: only the two retries should have slept (50ms, 100ms).
    assert sleep_calls == [0.05, 0.10]

    persisted = repo.get_by_id(media_id)
    assert persisted is not None
    assert persisted["file_hash"] == "hash-retry"

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_add_media_does_not_retry_on_non_lock_operational_error(tmp_path, monkeypatch):
    """A non-lock ``OperationalError`` (e.g. ``no such table``) is a real
    bug and must propagate immediately without retry/backoff."""
    db_path = tmp_path / "media_no_retry.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    sleep_calls: list = []
    monkeypatch.setattr(
        media_repository_module.time, "sleep", lambda d: sleep_calls.append(d)
    )

    db = DatabaseCore()
    call_counter = {"count": 0}

    @contextmanager
    def broken_transaction(*args, **kwargs):
        call_counter["count"] += 1
        raise sqlite3.OperationalError("no such table: bogus")
        yield  # pragma: no cover - keeps the function a generator

    monkeypatch.setattr(db, "transaction", broken_transaction)

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        repo.add_media(1, str(media_file), "hash-broken", 1.0)

    assert call_counter["count"] == 1
    assert sleep_calls == []

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_add_media_exhausts_retries_when_lock_persists(tmp_path, monkeypatch):
    """If the lock is held longer than the entire backoff budget the
    underlying ``OperationalError`` is propagated after 5 retries."""
    db_path = tmp_path / "media_lock_exhaust.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    sleep_calls: list = []
    monkeypatch.setattr(
        media_repository_module.time, "sleep", lambda d: sleep_calls.append(d)
    )

    db = DatabaseCore()
    call_counter = {"count": 0}

    @contextmanager
    def always_locked(*args, **kwargs):
        call_counter["count"] += 1
        raise sqlite3.OperationalError("database is locked")
        yield  # pragma: no cover - keeps the function a generator

    monkeypatch.setattr(db, "transaction", always_locked)

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        repo.add_media(1, str(media_file), "hash-stuck", 1.0)

    # 1 initial + 5 retries == 6 attempts.
    assert call_counter["count"] == 6
    assert sleep_calls == [0.05, 0.10, 0.20, 0.40, 0.80]

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_update_status_also_retries_on_database_locked(tmp_path, monkeypatch):
    """The retry policy also covers other write methods (update_status)."""
    db_path = tmp_path / "media_update_retry.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    media_id = repo.add_media(1, str(media_file), "hash-a", 1.0)
    assert media_id is not None and media_id > 0

    sleep_calls: list = []
    monkeypatch.setattr(
        media_repository_module.time, "sleep", lambda d: sleep_calls.append(d)
    )

    db = DatabaseCore()
    real_transaction = db.transaction
    call_counter = {"count": 0}

    @contextmanager
    def flaky_transaction(*args, **kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            raise sqlite3.OperationalError("database table is locked")
        with real_transaction(*args, **kwargs) as conn:
            yield conn

    monkeypatch.setattr(db, "transaction", flaky_transaction)

    repo.update_status(media_id, "ready")

    assert call_counter["count"] == 2
    assert sleep_calls == [0.05]

    row = repo.get_by_id(media_id)
    assert row["status"] == "ready"

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_add_media_retries_on_real_concurrent_database_lock(tmp_path, monkeypatch):
    """End-to-end: a side-thread holds an EXCLUSIVE write transaction on the
    same DB file. The main connection's busy_timeout is set to 0 so
    ``BEGIN IMMEDIATE`` fails fast with ``database is locked``. A timer
    releases the side lock during the retry window and the operation
    must ultimately succeed."""
    db_path = tmp_path / "media_real_lock.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    # Force the main thread's connection to fail fast on BEGIN IMMEDIATE so
    # the retry path (rather than busy_timeout) handles the lock.
    main_conn = DatabaseCore().get_connection()
    main_conn.execute("PRAGMA busy_timeout=0")

    lock_acquired = threading.Event()
    release_lock = threading.Event()
    holder_done = threading.Event()

    def lock_holder():
        side_conn = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            side_conn.execute("PRAGMA busy_timeout=30000")
            side_conn.execute("BEGIN IMMEDIATE")
            # Actual write upgrades the lock to RESERVED -> blocks BEGIN IMMEDIATE on others.
            side_conn.execute("INSERT INTO projects (name) VALUES (?)", ("locker",))
            lock_acquired.set()
            release_lock.wait(timeout=5)
            side_conn.rollback()
        finally:
            side_conn.close()
            holder_done.set()

    holder = threading.Thread(target=lock_holder, daemon=True)
    holder.start()
    assert lock_acquired.wait(timeout=5), "lock-holder thread failed to acquire write lock"

    # Release during retry window. With schedule (50,100,200,400,800ms) the 4th
    # attempt at t=350ms is comfortably past the 300ms release.
    threading.Timer(0.3, release_lock.set).start()

    media_id = repo.add_media(1, str(media_file), "hash-real", 1.5, {"src": "real"})

    assert media_id is not None and media_id > 0
    holder.join(timeout=5)
    assert holder_done.is_set()

    persisted = repo.get_by_id(media_id)
    assert persisted is not None
    assert persisted["file_hash"] == "hash-real"

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_media_metadata_compression(tmp_path, monkeypatch):
    """Verify that metadata payloads > 10 KB are compressed and base64-encoded with a prefix in SQLite,
    but retrieved transparently decoded."""
    db_path = tmp_path / "media_compression.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    # Create large metadata (> 10 KB) representing spectral/depth data
    large_spectral_data = {
        "song_segments": [{"start": 0.0, "end": 10.0, "label": "Intro", "energy": 0.3}],
        "spectral_data": {
            "timestamps": [float(i) * 0.1 for i in range(1500)],
            "energy": [float(i % 10) / 10.0 for i in range(1500)],
            "centroid": [float(i % 100) * 10 for i in range(1500)],
        }
    }
    
    # Assert that this is indeed larger than 10 KB when dumped as JSON
    import json
    json_len = len(json.dumps(large_spectral_data))
    assert json_len > 10 * 1024  # > 10 KB

    # Save to database
    media_id = repo.add_media(1, str(media_file), "hash-large", 10.0, large_spectral_data)
    assert media_id is not None and media_id > 0

    # 1. Verify DB contains compressed representation starting with 'GZ1:' prefix
    conn = DatabaseCore().get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT metadata_json FROM media WHERE id = ?", (media_id,)).fetchone()
    db_metadata_str = row[0]
    
    assert db_metadata_str.startswith("GZ1:")
    assert len(db_metadata_str) < json_len  # Compression should reduce size significantly

    # 2. Verify transparent retrieval via repo
    retrieved = repo.get_by_id(media_id)
    assert retrieved is not None
    assert retrieved["file_hash"] == "hash-large"
    
    # Transparently deserialized JSON string (external callers do json.loads)
    retrieved_meta_str = retrieved["metadata_json"]
    assert isinstance(retrieved_meta_str, str)
    
    retrieved_meta = json.loads(retrieved_meta_str)
    assert isinstance(retrieved_meta, dict)
    assert "spectral_data" in retrieved_meta
    assert len(retrieved_meta["spectral_data"]["timestamps"]) == 1500
    assert retrieved_meta["spectral_data"]["timestamps"] == large_spectral_data["spectral_data"]["timestamps"]

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_bulk_update_status_empty(tmp_path, monkeypatch):
    """Empty list of media_ids in bulk_update_status should return early and not crash."""
    from pb_studio.data.repositories.media_repository import MediaRepository
    from pb_studio.config_manager import ConfigManager
    from pb_studio.data.database_core import DatabaseCore
    
    # Setup clean db
    db_file = tmp_path / "pb_test_media.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_file), raising=False)
    DatabaseCore._instance = None
    
    repo = MediaRepository()
    # This should not raise sqlite3.OperationalError/SyntaxError
    repo.bulk_update_status([], "completed")
    
    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)
