"""Runtime owner adapter for automatic startup/shutdown recovery snapshots."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3


def _recover_cold_brain_outbox(brain_dir: Path) -> None:
    outbox = brain_dir / "feedback_outbox.json"
    if not outbox.is_file():
        return
    try:
        operation = json.loads(outbox.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Brain feedback outbox is unreadable") from exc
    if operation in ({}, None, []):
        return
    state_path = Path(str(operation.get("state_db_path", "")))
    if not state_path.is_absolute() or not state_path.is_file():
        raise RuntimeError("Brain feedback outbox has no recoverable State DB")

    from pb_studio.brain.feedback_logger import FeedbackLogger
    from pb_studio.brain.weight_store import WeightStore
    from pb_studio.storage.brain_store import BrainStore
    from pb_studio.storage.sqlite_init import init_connection

    store = BrainStore(brain_dir)
    state = sqlite3.connect(str(state_path), isolation_level=None, check_same_thread=False)
    try:
        init_connection(state)
        weights = WeightStore(store.weights_conn, lock=store._weights_lock)
        FeedbackLogger(
            weight_store=weights,
            state_conn=state,
            outbox_path=outbox,
        ).recover_pending()
    finally:
        state.close()
        store.close(create_backup=False)


def create_runtime_recovery_generation(
    *,
    timeout: float = 60.0,
    only_if_uninitialized: bool = False,
):
    """Create one full generation, or return ``None`` for a cold installation."""
    from pb_studio.config_manager import ConfigManager
    from pb_studio.storage.brain_store import default_brain_dir
    from pb_studio.storage.recovery_adapters import (
        RecoveryOwnerSnapshot,
        create_owner_generation,
    )
    from pb_studio.storage.recovery_generation import fixed_control_root

    if only_if_uninitialized and (fixed_control_root() / "CURRENT").is_file():
        return None

    manager = ConfigManager()
    config_path = Path(manager.config_file).resolve()
    db_value = manager.get("paths", {}).get("db_path", "./data/pb_studio.db")
    catalog = Path(manager.resolve_path(db_value)).resolve()
    brain_dir = default_brain_dir().resolve()
    required_brain = tuple(
        brain_dir / name
        for name in ("weights.db", "patterns.db", "embedding_cache.db")
    )
    if not catalog.is_file() or not all(path.is_file() for path in required_brain):
        return None

    vector_index = catalog.parent / "video_index.faiss"
    callbacks = []

    from pb_studio.data.vector_store import VectorStore

    vector = VectorStore._instance
    if vector is not None and not getattr(vector, "_closed", False):
        callbacks.append(vector.save)
        vector_index = Path(vector.index_path).resolve()

    from pb_studio.brain.brain_service import BrainService

    brain = BrainService._instance
    if brain is not None and getattr(brain, "state_conn", None) is not None:
        callbacks.append(brain.feedback_logger.recover_pending)
    else:
        callbacks.append(lambda: _recover_cold_brain_outbox(brain_dir))

    snapshot = RecoveryOwnerSnapshot(
        config_path=config_path,
        catalog_db_path=catalog,
        brain_dir=brain_dir,
        vector_index_path=vector_index if vector_index.is_file() else None,
        quiesce_callbacks=tuple(callbacks),
    )
    return create_owner_generation(snapshot, timeout=timeout)


__all__ = ["create_runtime_recovery_generation"]
