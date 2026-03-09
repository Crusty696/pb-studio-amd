import sqlite3
import threading
from pathlib import Path

import pytest

from pb_studio.config_manager import ConfigManager
from pb_studio.data.database_core import DatabaseCore
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
    assert versions == [1, 2]

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
