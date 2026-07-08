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


def test_concurrent_patterns(tmp_path: Path):
    import threading
    import time
    
    brain = tmp_path / "brain"
    store = BrainStore(brain)
    errors = []

    def run_queries():
        for i in range(100):
            try:
                # Concurrently execute queries under patterns_lock
                with store._patterns_lock:
                    if store.patterns_conn is not None:
                        store.patterns_conn.execute(
                            "INSERT OR REPLACE INTO pattern_correlations (audio_profile_hash, video_profile_hash, last_seen) "
                            "VALUES (?, ?, ?)",
                            (f"audio_{i}", f"video_{i}", "2026-07-08T12:00:00")
                        )
                        store.patterns_conn.execute("SELECT * FROM pattern_correlations").fetchall()
            except Exception as e:
                errors.append(e)
                break
            time.sleep(0.001)


    def run_close():
        time.sleep(0.01)
        store.close()

    threads = [
        threading.Thread(target=run_queries),
        threading.Thread(target=run_queries),
        threading.Thread(target=run_close),
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # We expect this assert to fail when there are errors (collisions / db closed)
    assert len(errors) == 0, f"Concurrent operations failed: {errors}"

