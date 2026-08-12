import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from pb_studio.config_manager import ConfigManager
from pb_studio.storage.migration_authorization import DatabaseMigrationRequiredError

logger = logging.getLogger(__name__)

PROJECT_UUID_NAMESPACE = uuid.UUID("f81d8514-f593-4b7d-9cb9-551ae763b017")


def legacy_project_uuid(project_id: int, created_at: object) -> str:
    """Return the stable UUID used when upgrading a legacy catalog row."""
    return str(
        uuid.uuid5(
            PROJECT_UUID_NAMESPACE,
            f"legacy-project:{int(project_id)}:{str(created_at or '')}",
        )
    )


def _iter_sql_statements(sql: str):
    """Yield individual SQL statements from a script.

    Uses sqlite3.complete_statement() to correctly handle BEGIN...END blocks
    in CREATE TRIGGER statements (naive semicolon-split would break them).

    R16/CRIT-002: Replaces executescript() which issues an implicit COMMIT,
    breaking migration transaction atomicity.
    """
    current = ""
    for line in sql.splitlines():
        current += line + "\n"
        if sqlite3.complete_statement(current):
            stmt = current.strip()
            if stmt:
                yield stmt
            current = ""
    remainder = current.strip()
    if remainder:
        yield remainder

SCHEMA_MIGRATIONS = (
    (
        1,
        "core_schema",
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            json_data TEXT
        );

        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            file_path TEXT NOT NULL,
            file_hash TEXT,
            duration_sec REAL,
            status TEXT DEFAULT 'pending',
            metadata_json TEXT,
            ai_data_json TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS vector_map (
            faiss_id INTEGER PRIMARY KEY,
            media_id INTEGER,
            segment_start REAL,
            segment_end REAL,
            description TEXT,
            FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_media_hash ON media(file_hash);
        CREATE INDEX IF NOT EXISTS idx_media_project ON media(project_id);
        CREATE INDEX IF NOT EXISTS idx_media_status ON media(status);
        CREATE INDEX IF NOT EXISTS idx_vector_map_media ON vector_map(media_id);
        """,
    ),
    (
        2,
        "media_import_guard",
        """
        CREATE TABLE IF NOT EXISTS media_import_guard (
            project_id INTEGER NOT NULL,
            normalized_file_path TEXT NOT NULL,
            media_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(project_id, normalized_file_path),
            FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_media_import_guard_media
        ON media_import_guard(media_id);

        CREATE TRIGGER IF NOT EXISTS trg_media_guard_prevent_duplicate_insert
        BEFORE INSERT ON media
        WHEN NEW.project_id IS NOT NULL
          AND NEW.file_path IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM media_import_guard
              WHERE project_id = NEW.project_id
                AND normalized_file_path = normalize_media_path(NEW.file_path)
          )
        BEGIN
            SELECT RAISE(ABORT, 'duplicate media import');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_media_guard_register_insert
        AFTER INSERT ON media
        WHEN NEW.project_id IS NOT NULL
          AND NEW.file_path IS NOT NULL
          AND normalize_media_path(NEW.file_path) <> ''
        BEGIN
            INSERT OR IGNORE INTO media_import_guard (
                project_id,
                normalized_file_path,
                media_id
            )
            VALUES (
                NEW.project_id,
                normalize_media_path(NEW.file_path),
                NEW.id
            );
        END;
        """,
    ),
    (
        3,
        "vector_operation_outbox",
        """
        CREATE TABLE IF NOT EXISTS vector_operation_outbox (
            operation_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            operation_type TEXT NOT NULL,
            project_id INTEGER NOT NULL,
            media_id INTEGER NOT NULL,
            faiss_ids_json TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT 'prepared',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK(schema_version = 1),
            CHECK(operation_type IN ('media_delete', 'vector_dedupe')),
            CHECK(stage IN ('prepared', 'relational_applied', 'completed'))
        );

        CREATE INDEX IF NOT EXISTS idx_vector_operation_outbox_pending
        ON vector_operation_outbox(project_id, stage, created_at);
        """,
    ),
    (
        4,
        "stable_project_uuid",
        """
        ALTER TABLE projects ADD COLUMN project_uuid TEXT;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_project_uuid
        ON projects(project_uuid)
        WHERE project_uuid IS NOT NULL;
        """,
    ),
    (
        5,
        "vector_owner_receipts",
        """
        ALTER TABLE vector_map ADD COLUMN project_id INTEGER;
        ALTER TABLE vector_map ADD COLUMN project_uuid TEXT;
        ALTER TABLE vector_map ADD COLUMN owner_uuid TEXT;
        ALTER TABLE vector_map ADD COLUMN media_hash TEXT;
        ALTER TABLE vector_map ADD COLUMN recovery_generation TEXT;
        ALTER TABLE vector_map ADD COLUMN write_receipt_json TEXT;
        ALTER TABLE vector_map ADD COLUMN verification_status TEXT NOT NULL
            DEFAULT 'legacy_unverified'
            CHECK(verification_status IN ('verified_backfill', 'legacy_unverified'));
        ALTER TABLE vector_map ADD COLUMN verification_reason TEXT;

        CREATE INDEX IF NOT EXISTS idx_vector_map_project_owner
        ON vector_map(project_id, project_uuid, media_id);
        """,
    ),
)


def normalize_media_path(file_path: str) -> str:
    """Normalize file paths so imports are idempotent across relative/case variants."""
    if not file_path:
        return ""

    try:
        resolved = Path(file_path).expanduser().resolve(strict=False)
    except Exception:
        resolved = Path(file_path).expanduser()

    return os.path.normcase(os.path.normpath(str(resolved)))

class DatabaseCore:
    _instance = None
    _lock = threading.Lock()  # Thread-safe Singleton
    _local = threading.local()  # Thread-local storage für Connections
    _all_connections = []  # Tracking aller Connections fuer sauberes Shutdown
    _conn_lock = threading.Lock()  # Lock fuer Connection-Liste

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    instance = super(DatabaseCore, cls).__new__(cls)
                    instance._initialized = False
                    try:
                        instance._init_db()
                    except Exception:
                        # Init fehlgeschlagen - Instanz NICHT speichern
                        # damit naechster Aufruf es erneut versucht
                        raise
                    cls._instance = instance  # Erst NACH erfolgreichem Init setzen
        return cls._instance

    def _init_db(self):
        if self._initialized:
            return
            
        config = ConfigManager()
        db_path_str = config.get("paths", {}).get("db_path", "./data/pb_studio.db")
        # Relative Pfade werden ueber ConfigManager aufgeloest
        self.db_path = config.resolve_path(db_path_str)

        existed_nonempty = self.db_path.is_file() and self.db_path.stat().st_size > 0
        if existed_nonempty:
            self._preflight_existing_schema_read_only()
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        init_conn = None
        try:
            # Create initial connection nur fuer Schema-Setup
            init_conn = sqlite3.connect(str(self.db_path), check_same_thread=True, timeout=30.0)
            self._configure_connection(init_conn)

            self._create_schema(init_conn, allow_obj77_migration=not existed_nonempty)

            self._initialized = True
            logger.info(f"Database initialized at: {self.db_path}")

        except sqlite3.Error as e:
            logger.critical(f"Database initialization failed: {e}")
            raise
        finally:
            if init_conn is not None:
                init_conn.close()

    def _preflight_existing_schema_read_only(self) -> None:
        """Reject a pending OBJ77 catalog migration before any RW connection."""
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            has_migrations = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            current = 0
            if has_migrations:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()
                current = int(row[0])
        finally:
            connection.close()
        if current < SCHEMA_MIGRATIONS[-1][0]:
            raise DatabaseMigrationRequiredError(
                f"Existing catalog schema {current} requires approved schema "
                f"{SCHEMA_MIGRATIONS[-1][0]}; migration_required"
            )

    def _create_schema(self, conn, *, allow_obj77_migration: bool = False):
        self._apply_migrations(conn, allow_obj77_migration=allow_obj77_migration)
        conn.commit()

        cursor = conn.cursor()
        res = cursor.execute("SELECT count(*) FROM projects").fetchone()
        if res[0] == 0:
            cursor.execute(
                "INSERT INTO projects (name, project_uuid) VALUES (?, ?)",
                ("Default Project", str(uuid.uuid4())),
            )
            conn.commit()
            logger.info("Created 'Default Project' (ID: 1)")

    def _configure_connection(self, conn):
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        self._register_sql_functions(conn)

    def _register_sql_functions(self, conn):
        # M6-Fix (Pe-M2, 2026-05-20): NICHT mehr deterministic=True. Die Funktion
        # nutzt Path.resolve() + os.path.normcase, beides plattform-abhängig
        # (Windows: \ + lowercase, Linux: / + case-sensitive). Bei deterministic=True
        # cached SQLite das Resultat im query-planner — bei DB-Migration zwischen
        # OS-Plattformen oder bei sqlite-Upgrade kann das zu falschen Ergebnissen
        # führen. Performance-Trade-off vernachlässigbar (Trigger-only-Aufrufe).
        conn.create_function("normalize_media_path", 1, normalize_media_path)

    def _ensure_migration_table(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _apply_migrations(self, conn, *, allow_obj77_migration: bool = False):
        has_migrations = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        current = 0
        if has_migrations:
            current = int(
                conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()[0]
            )
        if current > 0 and current < 5 and not allow_obj77_migration:
            raise DatabaseMigrationRequiredError(
                "Existing catalog requires explicit OBJ77 migration; migration_required"
            )
        self._ensure_migration_table(conn)
        applied_versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for version, name, sql in SCHEMA_MIGRATIONS:
            if version in applied_versions:
                continue

            with conn:
                # R16/CRIT-002: executescript() issues implicit COMMIT before
                # running, which silently breaks the with-conn transaction and
                # makes DDL + backfill + version-recording non-atomic.
                # Fix: execute each statement individually — sqlite3 keeps them
                # in the same transaction. _iter_sql_statements handles
                # BEGIN...END trigger bodies correctly via complete_statement().
                for stmt in _iter_sql_statements(sql):
                    conn.execute(stmt)
                if version == 2:
                    self._backfill_media_import_guard(conn)
                elif version == 4:
                    self._backfill_project_uuids(conn)
                elif version == 5:
                    self._backfill_vector_ownership(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, name),
                )
            logger.info("Applied schema migration %s (%s)", version, name)

    def _backfill_vector_ownership(self, conn):
        """Bind only legacy vectors with complete, unique catalog evidence."""
        rows = conn.execute(
            """
            SELECT vm.faiss_id, vm.media_id, m.project_id, m.file_hash,
                   p.project_uuid
            FROM vector_map AS vm
            LEFT JOIN media AS m ON m.id = vm.media_id
            LEFT JOIN projects AS p ON p.id = m.project_id
            ORDER BY vm.faiss_id
            """
        ).fetchall()
        for row in rows:
            project_id = row["project_id"]
            project_uuid = row["project_uuid"]
            media_hash = row["file_hash"]
            verified = False
            if type(project_id) is int and project_id > 0 and media_hash:
                try:
                    normalized_uuid = str(uuid.UUID(str(project_uuid)))
                    verified = True
                except (TypeError, ValueError, AttributeError):
                    normalized_uuid = None
            else:
                normalized_uuid = None

            if verified and len(str(media_hash).strip()) >= 8:
                conn.execute(
                    """
                    UPDATE vector_map
                    SET project_id=?, project_uuid=?, owner_uuid=NULL, media_hash=?,
                        recovery_generation=NULL, write_receipt_json=NULL,
                        verification_status='legacy_unverified',
                        verification_reason='missing_owner_write_receipt_and_recovery_generation'
                    WHERE faiss_id=?
                    """,
                    (
                        project_id,
                        normalized_uuid,
                        str(media_hash),
                        int(row["faiss_id"]),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE vector_map
                    SET project_id=NULL, project_uuid=NULL, owner_uuid=NULL,
                        media_hash=NULL, recovery_generation=NULL,
                        write_receipt_json=NULL,
                        verification_status='legacy_unverified',
                        verification_reason='insufficient_owner_evidence'
                    WHERE faiss_id=?
                    """,
                    (int(row["faiss_id"]),),
                )

    def _backfill_media_import_guard(self, conn):
        """Backfill canonical media rows without touching existing duplicate rows."""
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT id, project_id, file_path
            FROM media
            WHERE project_id IS NOT NULL AND file_path IS NOT NULL
            ORDER BY id ASC
        """).fetchall()

        inserted = 0
        for row in rows:
            normalized_path = normalize_media_path(row["file_path"])
            if not normalized_path:
                continue

            result = cursor.execute("""
                INSERT OR IGNORE INTO media_import_guard (project_id, normalized_file_path, media_id)
                VALUES (?, ?, ?)
            """, (row["project_id"], normalized_path, row["id"]))
            inserted += result.rowcount

        if inserted:
            logger.info("Backfilled %s canonical media import guard rows", inserted)

    def _backfill_project_uuids(self, conn):
        """Backfill stable identities without using mutable names or paths."""
        rows = conn.execute(
            "SELECT id, created_at, project_uuid FROM projects ORDER BY id"
        ).fetchall()
        for row in rows:
            current = row["project_uuid"]
            if current:
                try:
                    normalized = str(uuid.UUID(str(current)))
                except (TypeError, ValueError, AttributeError) as exc:
                    raise RuntimeError(
                        f"Project {row['id']} has invalid project_uuid"
                    ) from exc
            else:
                normalized = legacy_project_uuid(row["id"], row["created_at"])
            conn.execute(
                "UPDATE projects SET project_uuid=? WHERE id=?",
                (normalized, int(row["id"])),
            )

        invalid = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE project_uuid IS NULL "
            "OR trim(project_uuid)=''"
        ).fetchone()[0]
        duplicates = conn.execute(
            "SELECT COUNT(*) FROM (SELECT project_uuid FROM projects "
            "GROUP BY project_uuid HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if invalid or duplicates:
            raise RuntimeError(
                "Project UUID backfill did not produce a complete unique catalog"
            )

    def get_connection(self):
        """
        Returns a thread-local database connection.
        Each thread gets its own connection for thread-safety.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Thread-safe via thread-local isolation, but allows clean cross-thread shutdown!
                timeout=30.0,
            )
            self._configure_connection(self._local.conn)
            # Connection tracken fuer sauberes Shutdown
            with self._conn_lock:
                self._all_connections.append(self._local.conn)
            logger.debug(f"Created new DB connection for thread {threading.current_thread().name}")
        return self._local.conn

    @contextmanager
    def transaction(self, immediate: bool = False):
        """
        Context manager for atomic transactions.
        
        Usage:
            with db.transaction():
                cursor.execute("INSERT ...")
                cursor.execute("UPDATE ...")
                # Automatic commit on success, rollback on error
        """
        from pb_studio.storage.recovery_barrier import get_recovery_write_barrier

        with get_recovery_write_barrier().write_lease("catalog"):
            conn = self.get_connection()
            try:
                if immediate and not conn.in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed, rolled back: {e}")
                raise

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            with self._conn_lock:
                if self._local.conn in self._all_connections:
                    self._all_connections.remove(self._local.conn)
            self._local.conn.close()
            self._local.conn = None
            logger.debug(f"Closed DB connection for thread {threading.current_thread().name}")

    def shutdown(self):
        """Shutdown ALL connections across all threads. Call this on application exit."""
        self.close()  # Aktuellen Thread schliessen
        with self._conn_lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        with DatabaseCore._lock:
            self._initialized = False
            DatabaseCore._instance = None
            # Pe-H1: re-init thread-local. Otherwise old threads keep stale .conn refs
            # that were closed above — next get_connection() on those threads would
            # short-circuit on the hasattr check and return a closed connection.
            DatabaseCore._local = threading.local()
            logger.info("DatabaseCore._instance zurückgesetzt — Neuinitialisierung möglich")

    @classmethod
    def reset_for_testing(cls):
        """Pe-H1: full reset for pytest fixtures. Closes connections + clears
        thread-local + singleton. Mirrors VRAMBudgetManager.reset_for_testing.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()
            cls._instance = None
            cls._local = threading.local()
