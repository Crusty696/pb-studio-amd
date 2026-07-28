"""Tests für brain backup + retention (Plan Phase 6)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from pb_studio.storage.backup import backup_brain_store, prune_backups
from pb_studio.storage.brain_store import BrainStore


def test_backup_creates_atomic_copies(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        store.weights_conn.execute(
            "INSERT INTO axis_weights (axis, context_level, context_key, "
            "positive_count, negative_count, last_updated) VALUES (?,?,?,?,?,?)",
            ("kick_weight", 0, "", 5.0, 1.0, "2026-05-06"),
        )
    finally:
        store.close()

    target = backup_brain_store(tmp_path / "brain", tmp_path / "backups")
    for f in ("weights.db", "patterns.db", "embedding_cache.db"):
        assert (target / f).is_file(), f"missing {f}"

    # Verify backup is a valid SQLite file with seeded row
    conn = sqlite3.connect(str(target / "weights.db"))
    try:
        row = conn.execute(
            "SELECT positive_count FROM axis_weights WHERE axis='kick_weight'"
        ).fetchone()
        assert row[0] == 5.0
    finally:
        conn.close()

def test_failed_backup_leaves_no_visible_partial_generation(tmp_path: Path):
    brain = tmp_path / "brain"
    brain.mkdir()
    sqlite3.connect(str(brain / "weights.db")).close()
    (brain / "patterns.db").write_bytes(b"not-a-database")
    backups = tmp_path / "backups"

    with pytest.raises(sqlite3.DatabaseError):
        backup_brain_store(brain, backups, files=("weights.db", "patterns.db"))

    assert not list(backups.glob("brain_backup_*"))
    assert not list(backups.glob(".*.tmp"))


def test_corrupt_store_restores_latest_valid_backup(tmp_path: Path):
    brain = tmp_path / "brain"
    store = BrainStore(brain)
    try:
        store.weights_conn.execute(
            "INSERT INTO axis_weights (axis, context_level, context_key, "
            "positive_count, negative_count, last_updated) VALUES (?,?,?,?,?,?)",
            ("restore_me", 0, "", 7.0, 1.0, "2026-07-28"),
        )
    finally:
        store.close()
    backup_brain_store(brain, tmp_path / "backups")
    (brain / "weights.db").write_bytes(b"corrupt-live-store")

    recovered = BrainStore(brain)
    try:
        row = recovered.weights_conn.execute(
            "SELECT positive_count FROM axis_weights WHERE axis='restore_me'"
        ).fetchone()
        assert row == (7.0,)
    finally:
        recovered.close()


def test_prune_keeps_newest(tmp_path: Path):
    bdir = tmp_path / "backups"
    bdir.mkdir()
    for i in range(6):
        (bdir / f"brain_backup_2026010{i}_000000").mkdir()
        time.sleep(0.001)
    deleted = prune_backups(bdir, keep=3)
    remaining = sorted([p.name for p in bdir.iterdir() if p.is_dir()])
    assert len(remaining) == 3
    assert len(deleted) == 3
    # newest 3 remain
    assert remaining[-1] == "brain_backup_20260105_000000"
