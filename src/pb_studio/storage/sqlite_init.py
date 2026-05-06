"""Standard PRAGMA setup for every SQLite connection (Plan Phase 2/3).

WAL + NORMAL is crash-safe and avoids reader/writer contention.
"""

from __future__ import annotations

import sqlite3

PRAGMA_INIT: list[str] = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA cache_size = -32000",
    "PRAGMA mmap_size = 268435456",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
]


def init_connection(conn: sqlite3.Connection) -> None:
    """Apply standard PRAGMAs to a fresh connection."""
    for pragma in PRAGMA_INIT:
        conn.execute(pragma)


def checkpoint(conn: sqlite3.Connection, mode: str = "PASSIVE") -> None:
    """Force WAL checkpoint. Modes: PASSIVE | RESTART | TRUNCATE."""
    conn.execute(f"PRAGMA wal_checkpoint({mode})")
