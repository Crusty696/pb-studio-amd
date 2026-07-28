import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from pb_studio.config_manager import ConfigManager
from pb_studio.data.database_core import DatabaseCore
from pb_studio.data.vector_operation_outbox import VectorOperationOutbox


class _TempConfig:
    def __init__(self, db_path: Path):
        self._config = {"paths": {"db_path": str(db_path)}}

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def resolve_path(self, value: str) -> Path:
        return Path(value).resolve()


class _FakeVectorStore:
    def __init__(self, tombstone_path: Path):
        self._lock = threading.Lock()
        self.tombstone_path = tombstone_path
        self._tombstoned_ids = set()
        if tombstone_path.exists():
            self._tombstoned_ids.update(
                int(value)
                for value in json.loads(tombstone_path.read_text(encoding="utf-8"))
            )

    def _ensure_open(self):
        return None

    def _save_unlocked(self, force=False):
        assert force is True
        temp = self.tombstone_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(sorted(self._tombstoned_ids)),
            encoding="utf-8",
        )
        os.replace(temp, self.tombstone_path)


@pytest.fixture
def outbox_db(tmp_path, monkeypatch):
    db_path = tmp_path / "outbox-copy.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    DatabaseCore._instance = None
    DatabaseCore._local = threading.local()
    DatabaseCore._all_connections = []

    db = DatabaseCore()
    with db.transaction(immediate=True) as conn:
        conn.execute(
            """
            INSERT INTO media (
                id, project_id, file_path, status, metadata_json
            ) VALUES (10, 1, ?, 'ready', '{}')
            """,
            (str(tmp_path / "clip.mp4"),),
        )
        conn.executemany(
            """
            INSERT INTO vector_map (
                faiss_id, media_id, segment_start, segment_end, description
            ) VALUES (?, 10, 0.0, 1.0, 'old')
            """,
            [(41,), (42,)],
        )

    yield db, tmp_path / "video_index_tombstones.json"

    db.shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_media_delete_recovers_after_sqlite_failure(outbox_db, monkeypatch):
    db, tombstone_path = outbox_db
    vector_store = _FakeVectorStore(tombstone_path)
    outbox = VectorOperationOutbox(
        db=db,
        vector_store_factory=lambda: vector_store,
    )
    real_transaction = db.transaction
    calls = {"count": 0}

    @contextmanager
    def fail_relational_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("forced sqlite delete failure")
        with real_transaction(*args, **kwargs) as conn:
            yield conn

    monkeypatch.setattr(db, "transaction", fail_relational_once)
    with pytest.raises(RuntimeError, match="forced sqlite delete failure"):
        outbox.delete_media(10)

    conn = db.get_connection()
    assert conn.execute("SELECT 1 FROM media WHERE id = 10").fetchone() is not None
    assert conn.execute(
        "SELECT COUNT(*) FROM vector_map WHERE media_id = 10"
    ).fetchone()[0] == 2
    assert json.loads(tombstone_path.read_text(encoding="utf-8")) == [41, 42]
    pending = conn.execute(
        "SELECT stage FROM vector_operation_outbox WHERE media_id = 10"
    ).fetchone()
    assert pending["stage"] == "prepared"

    monkeypatch.setattr(db, "transaction", real_transaction)
    restarted_store = _FakeVectorStore(tombstone_path)
    restarted = VectorOperationOutbox(
        db=db,
        vector_store_factory=lambda: restarted_store,
    )
    assert restarted.recover_pending(project_id=1) == 1
    assert conn.execute("SELECT 1 FROM media WHERE id = 10").fetchone() is None
    assert conn.execute(
        "SELECT COUNT(*) FROM vector_map WHERE media_id = 10"
    ).fetchone()[0] == 0
    assert restarted.recover_pending(project_id=1) == 0
    assert conn.execute(
        "SELECT stage FROM vector_operation_outbox WHERE media_id = 10"
    ).fetchone()["stage"] == "completed"


def test_vector_dedupe_recovery_never_exposes_unmapped_active_vector(
    outbox_db,
    monkeypatch,
):
    db, tombstone_path = outbox_db
    vector_store = _FakeVectorStore(tombstone_path)
    outbox = VectorOperationOutbox(
        db=db,
        vector_store_factory=lambda: vector_store,
    )
    real_set_stage = outbox._set_stage
    failed = {"done": False}

    def crash_before_completion(operation_id, stage):
        if stage == "completed" and not failed["done"]:
            failed["done"] = True
            raise RuntimeError("forced crash after relational commit")
        real_set_stage(operation_id, stage)

    monkeypatch.setattr(outbox, "_set_stage", crash_before_completion)
    with pytest.raises(RuntimeError, match="forced crash after relational commit"):
        outbox.dedupe_media_vectors(10)

    conn = db.get_connection()
    assert conn.execute(
        "SELECT COUNT(*) FROM vector_map WHERE media_id = 10"
    ).fetchone()[0] == 0
    assert set(json.loads(tombstone_path.read_text(encoding="utf-8"))) == {41, 42}
    assert conn.execute(
        "SELECT stage FROM vector_operation_outbox WHERE media_id = 10"
    ).fetchone()["stage"] == "relational_applied"

    restarted = VectorOperationOutbox(
        db=db,
        vector_store_factory=lambda: _FakeVectorStore(tombstone_path),
    )
    assert restarted.recover_pending(project_id=1) == 1
    assert restarted.recover_pending(project_id=1) == 0
    assert conn.execute(
        "SELECT stage FROM vector_operation_outbox WHERE media_id = 10"
    ).fetchone()["stage"] == "completed"
