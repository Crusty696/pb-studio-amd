"""Lightweight SQLite migrations via PRAGMA user_version (Plan Phase 3).

Numbered *.sql scripts in a directory get applied in order.
Each migration runs in its own transaction. user_version bumps on success.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
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

        expected_version = current + 1
        for version, script in parsed_scripts:
            if version <= current:
                continue
            if version != expected_version:
                raise ValueError(
                    "Migrationsluecke: "
                    f"erwartet Version {expected_version}, gefunden "
                    f"{version} ({script.name})"
                )
            expected_version += 1

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


def migrate_project_state(
    db_path: str | Path,
    migrations_dir: str | Path,
    *,
    project_uuid: str,
) -> int:
    """Migrate one project State DB and bind every feedback row to its UUID.

    The schema upgrade is additive. The idempotent data backfill is completed
    before callers may publish the connection to the running application.
    """
    normalized_project_uuid = str(uuid.UUID(str(project_uuid)))
    applied = migrate(db_path, migrations_dir)
    conn = sqlite3.connect(str(Path(db_path)), isolation_level=None)
    try:
        init_connection(conn)
        conn.execute("BEGIN IMMEDIATE")
        identity_rows = conn.execute(
            "SELECT project_uuid FROM project_identity"
        ).fetchall()
        if len(identity_rows) > 1:
            raise RuntimeError("State DB contains multiple project identities")
        if identity_rows:
            stored = str(uuid.UUID(str(identity_rows[0][0])))
            if stored != normalized_project_uuid:
                raise RuntimeError(
                    "State DB project_uuid conflicts with the project catalog"
                )
        else:
            conn.execute(
                "INSERT INTO project_identity(singleton_id, project_uuid) "
                "VALUES (1, ?)",
                (normalized_project_uuid,),
            )

        rows = conn.execute(
            "SELECT id, project_uuid, event_uuid FROM feedback_events ORDER BY id"
        ).fetchall()
        for event_id, row_project_uuid, row_event_uuid in rows:
            if row_project_uuid:
                existing_project_uuid = str(uuid.UUID(str(row_project_uuid)))
                if existing_project_uuid != normalized_project_uuid:
                    raise RuntimeError(
                        f"Feedback event {event_id} belongs to another project"
                    )
            event_uuid = (
                str(uuid.UUID(str(row_event_uuid)))
                if row_event_uuid
                else str(
                    uuid.uuid5(
                        uuid.UUID(normalized_project_uuid),
                        f"legacy-feedback:{int(event_id)}",
                    )
                )
            )
            conn.execute(
                "UPDATE feedback_events SET project_uuid=?, event_uuid=? "
                "WHERE id=?",
                (normalized_project_uuid, event_uuid, int(event_id)),
            )

        incomplete = conn.execute(
            "SELECT COUNT(*) FROM feedback_events WHERE project_uuid IS NULL "
            "OR event_uuid IS NULL"
        ).fetchone()[0]
        duplicates = conn.execute(
            "SELECT COUNT(*) FROM (SELECT event_uuid FROM feedback_events "
            "GROUP BY event_uuid HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if incomplete or duplicates:
            raise RuntimeError("State feedback identity backfill is incomplete")
        conn.execute("COMMIT")
        return applied
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        conn.close()
