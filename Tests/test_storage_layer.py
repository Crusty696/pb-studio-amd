"""Tests für storage-Layer (Plan Phase 2/3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pb_studio.storage.brain_store import BrainStore
from pb_studio.storage.embedding_cache import EmbeddingCache
from pb_studio.storage.embedding_repository import (
    AUDIO_DIM,
    VIDEO_DIM,
    EmbeddingRepository,
)
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import PRAGMA_INIT, init_connection


def test_pragma_init_sets_wal(tmp_path: Path):
    db = tmp_path / "x.db"
    conn = sqlite3.connect(str(db))
    init_connection(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()


def test_migration_runner_idempotent(tmp_path: Path):
    mig = tmp_path / "mig"
    mig.mkdir()
    (mig / "001_initial.sql").write_text("CREATE TABLE x (id INTEGER);")
    db = tmp_path / "y.db"
    v1 = migrate(db, mig)
    v2 = migrate(db, mig)
    assert v1 == 1
    assert v2 == 1


def test_embedding_repository_audio_roundtrip(tmp_path: Path):
    repo = EmbeddingRepository(tmp_path / "emb.db")
    try:
        rng = np.random.default_rng(42)
        emb = rng.standard_normal(AUDIO_DIM).astype(np.float32)
        unit_id = repo.add_audio_unit(
            parent_id=None,
            level="window",
            media_id=1,
            media_hash="deadbeef",
            start_time=0.0,
            end_time=10.0,
            embedding=emb,
            metadata={"sub_bpm": 128.0},
        )
        assert unit_id > 0
        hits = repo.search_audio(emb, level="window", limit=5)
        assert hits and hits[0].unit_id == unit_id
    finally:
        repo.close()


def test_embedding_repository_video_roundtrip(tmp_path: Path):
    repo = EmbeddingRepository(tmp_path / "emb.db")
    try:
        rng = np.random.default_rng(7)
        emb = rng.standard_normal(VIDEO_DIM).astype(np.float32)
        unit_id = repo.add_video_unit(
            parent_id=None,
            level="scene",
            media_id=42,
            media_hash="cafebabe",
            start_time=0.0,
            end_time=2.5,
            embedding=emb,
            motion_score=0.42,
            brightness=0.6,
            saturation=0.3,
            color_temp=0.1,
        )
        hits = repo.search_video(emb, level="scene", limit=5)
        assert hits and hits[0].unit_id == unit_id
    finally:
        repo.close()


def test_embedding_repository_dim_mismatch(tmp_path: Path):
    repo = EmbeddingRepository(tmp_path / "emb.db")
    try:
        with pytest.raises(ValueError):
            repo.add_audio_unit(
                parent_id=None,
                level="window",
                media_id=1,
                media_hash="x",
                start_time=0.0,
                end_time=1.0,
                embedding=np.zeros(99, dtype=np.float32),
            )
    finally:
        repo.close()


def test_embedding_cache_store_and_lookup(tmp_path: Path):
    cache = EmbeddingCache(tmp_path / "cache.db", tmp_path / "embeddings")
    try:
        emb = np.ones(512, dtype=np.float32)
        cache.store(
            media_hash="ABC",
            media_type="audio",
            embedding=emb,
            model_name="laion/larger_clap_music",
            model_version="1.0",
        )
        entry = cache.lookup("ABC", "laion/larger_clap_music", "1.0")
        assert entry is not None
        loaded = cache.load_array(entry)
        assert loaded.shape == (512,)

        miss = cache.lookup("DEF", "laion/larger_clap_music", "1.0")
        assert miss is None

        version_miss = cache.lookup("ABC", "laion/larger_clap_music", "2.0")
        assert version_miss is None
    finally:
        cache.close()


def test_brain_store_initializes_three_dbs(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        for db in ("weights.db", "patterns.db", "embedding_cache.db"):
            assert (Path(tmp_path / "brain") / db).is_file()

        # weights.db should expose axis_weights table
        rows = store.weights_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert "axis_weights" in names
    finally:
        store.close()


def test_brain_store_recovers_corrupt_weights(tmp_path: Path):
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "weights.db").write_bytes(b"not a sqlite file")

    store = BrainStore(brain)
    try:
        rows = store.weights_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "axis_weights" in {r[0] for r in rows}
        assert (brain / "weights.db.corrupt").is_file()
    finally:
        store.close()


def test_migration_runner_numerical_prefix(tmp_path: Path):
    mig = tmp_path / "mig"
    mig.mkdir()
    (mig / "10_second.sql").write_text("CREATE TABLE x2 (id INTEGER);")
    (mig / "2_first.sql").write_text("CREATE TABLE x1 (id INTEGER);")
    db = tmp_path / "y.db"
    
    # 2_first.sql has version 2, 10_second.sql has version 10.
    # They should be applied in numerical order: 2, then 10.
    # If list index or string order was used, "10_second.sql" (string comparison "10" < "2")
    # might be run first. But numerically, 2 is run first, then 10.
    v = migrate(db, mig)
    assert v == 10
    
    conn = sqlite3.connect(str(db))
    # Both tables should exist
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cursor.fetchall()}
    assert "x1" in tables
    assert "x2" in tables
    
    # Version should be set to 10
    (user_version,) = conn.execute("PRAGMA user_version").fetchone()
    assert user_version == 10
    conn.close()


def test_embedding_repository_close_reinitializes_local(tmp_path: Path):
    repo = EmbeddingRepository(tmp_path / "emb.db")
    # Access connection to initialize it in thread local
    conn = repo.conn
    assert conn is not None
    repo.close()
    
    # Thread local should be reinitialized
    assert not hasattr(repo._local, "conn")


def test_dead_thread_connections_are_pruned(tmp_path):
    """Review-Fix MEDIUM (2026-07-09): Conns toter Threads werden beim
    naechsten Conn-Aufbau geschlossen und aus _all_conns entfernt."""
    import threading

    from pb_studio.storage.embedding_repository import EmbeddingRepository

    repo = EmbeddingRepository(tmp_path / "emb.db")
    try:
        def use_repo():
            _ = repo.conn  # erzeugt Thread-Conn

        for _ in range(5):
            t = threading.Thread(target=use_repo)
            t.start()
            t.join()

        _ = repo.conn  # Main-Thread-Conn -> triggert Pruning
        assert len(repo._all_conns) <= 2  # main + max. 1 Nachzuegler
    finally:
        repo.close()


def test_migration_unparsable_name_warns(tmp_path, caplog):
    """Review-Fix MEDIUM (2026-07-09): nicht-numerische Praefixe -> Warning statt silent skip."""
    import logging

    from pb_studio.storage.migration_runner import migrate

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "001_ok.sql").write_text("CREATE TABLE a (x INT);", encoding="utf-8")
    (mig / "notes.sql").write_text("CREATE TABLE b (x INT);", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        migrate(tmp_path / "m.db", mig)
    assert any("notes.sql" in r.message for r in caplog.records)


def test_migration_duplicate_prefix_raises(tmp_path):
    """Review-Fix MEDIUM (2026-07-09): doppelter Versions-Praefix -> harter Fehler."""
    import pytest

    from pb_studio.storage.migration_runner import migrate

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "001_a.sql").write_text("CREATE TABLE a (x INT);", encoding="utf-8")
    (mig / "001_b.sql").write_text("CREATE TABLE b (x INT);", encoding="utf-8")

    with pytest.raises(ValueError, match="[Dd]oppelt"):
        migrate(tmp_path / "m.db", mig)
