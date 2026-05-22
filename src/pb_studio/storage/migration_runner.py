"""Lightweight SQLite migrations via PRAGMA user_version (Plan Phase 3).

Numbered *.sql scripts in a directory get applied in order.
Each migration runs in its own transaction. user_version bumps on success.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .sqlite_init import init_connection

logger = logging.getLogger(__name__)


def migrate(db_path: str | Path, migrations_dir: str | Path) -> int:
    """Apply pending migrations. Returns the new user_version."""
    db_path = Path(db_path)
    migrations_dir = Path(migrations_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # B-9 FIX: isolation_level=None verhindert implizites auto-commit von executescript()
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        init_connection(conn)
        (current,) = conn.execute("PRAGMA user_version").fetchone()
        scripts = sorted(migrations_dir.glob("*.sql"))
        applied = current
        for i, script in enumerate(scripts, start=1):
            if i <= current:
                continue
            sql = script.read_text(encoding="utf-8")
            try:
                conn.execute("BEGIN")
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {i}")
                conn.commit()
                applied = i
                logger.info("Applied migration %s -> user_version=%d", script.name, i)
            except Exception:
                conn.rollback()
                raise
        return applied
    finally:
        conn.close()
