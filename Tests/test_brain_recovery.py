"""Recovery tests (Plan Phase 6)."""

from __future__ import annotations

from pathlib import Path

from pb_studio.brain.brain_service import BrainService
from pb_studio.storage.brain_store import BrainStore


def test_brain_starts_when_brain_dir_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    BrainService.reset_singleton()
    svc = BrainService.get()
    try:
        # Cold-start posterior
        pm = svc.weights.get_posterior_mean("kick_weight", [""])
        assert pm > 0
    finally:
        BrainService.reset_singleton()


def test_brain_recovers_when_weights_missing(tmp_path: Path):
    brain = tmp_path / "brain"
    store = BrainStore(brain)
    store.close()
    # Delete weights.db
    (brain / "weights.db").unlink()
    # Re-open should recreate schema
    store2 = BrainStore(brain)
    try:
        rows = store2.weights_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "axis_weights" in {r[0] for r in rows}
    finally:
        store2.close()


def test_brain_handles_corrupt_patterns(tmp_path: Path):
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "patterns.db").write_bytes(b"definitely not a sqlite file")

    store = BrainStore(brain)
    try:
        rows = store.patterns_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "pattern_correlations" in {r[0] for r in rows}
        assert (brain / "patterns.db.corrupt").is_file()
    finally:
        store.close()
