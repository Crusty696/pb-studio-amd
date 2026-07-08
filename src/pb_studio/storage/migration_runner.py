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


def split_sql_statements(sql: str) -> list[str]:
    """Robustly splits a SQL script into individual statements, respecting comments and strings."""
    statements = []
    current = []
    in_string = False
    string_char = None
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        # Check for line comments
        if not in_string and char == '-' and i + 1 < n and sql[i+1] == '-':
            # Skip until newline
            while i < n and sql[i] != '\n':
                i += 1
            continue
        
        # Check for block comments /* ... */
        if not in_string and char == '/' and i + 1 < n and sql[i+1] == '*':
            i += 2
            while i + 1 < n and not (sql[i] == '*' and sql[i+1] == '/'):
                i += 1
            i += 2
            continue
            
        if char in ("'", '"'):
            if not in_string:
                in_string = True
                string_char = char
            elif string_char == char:
                # Check for escaped quote inside string (e.g. '', "")
                if i + 1 < n and sql[i+1] == char:
                    current.append(char)
                    current.append(char)
                    i += 2
                    continue
                else:
                    in_string = False
                    string_char = None
                    
        current.append(char)
        
        if not in_string and char == ';':
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            
        i += 1
        
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
        
    return statements


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
        import re
        parsed_scripts = []
        seen_versions: dict[int, str] = {}
        for script in scripts:
            m = re.match(r"^(\d+)", script.name)
            if not m:
                # Review-Fix MEDIUM (2026-07-09): vorher silent skip
                logger.warning(
                    "Migration %s hat keinen numerischen Praefix und wird IGNORIERT",
                    script.name,
                )
                continue
            version = int(m.group(1))
            if version in seen_versions:
                raise ValueError(
                    f"Doppelter Migrations-Praefix {version}: "
                    f"{seen_versions[version]} vs {script.name}"
                )
            seen_versions[version] = script.name
            parsed_scripts.append((version, script))
        parsed_scripts.sort(key=lambda x: x[0])

        applied = current
        for version, script in parsed_scripts:
            if version <= current:
                continue
            sql = script.read_text(encoding="utf-8")
            statements = split_sql_statements(sql)
            try:
                conn.execute("BEGIN")
                for stmt in statements:
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version = {version}")
                conn.execute("COMMIT")
                applied = version
                logger.info("Applied migration %s -> user_version=%d", script.name, version)
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise
        return applied
    finally:
        conn.close()
