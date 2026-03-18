import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

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
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        init_conn = None
        try:
            # Create initial connection nur fuer Schema-Setup
            init_conn = sqlite3.connect(str(self.db_path), check_same_thread=True, timeout=30.0)
            self._configure_connection(init_conn)

            self._create_schema(init_conn)

            self._initialized = True
            logger.info(f"Database initialized at: {self.db_path}")

        except sqlite3.Error as e:
            logger.critical(f"Database initialization failed: {e}")
            raise
        finally:
            if init_conn is not None:
                init_conn.close()

    def _create_schema(self, conn):
        self._apply_migrations(conn)
        self._backfill_media_import_guard(conn)
        conn.commit()

        cursor = conn.cursor()
        res = cursor.execute("SELECT count(*) FROM projects").fetchone()
        if res[0] == 0:
            cursor.execute("INSERT INTO projects (name) VALUES ('Default Project')")
            conn.commit()
            logger.info("Created 'Default Project' (ID: 1)")

    def _configure_connection(self, conn):
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        # ⚡ Bolt: Optimize SQLite performance. When using WAL mode, synchronous=NORMAL
        # is safe and provides a significant write throughput boost by avoiding a disk flush on every commit.
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=30000;")
        self._register_sql_functions(conn)

    def _register_sql_functions(self, conn):
        try:
            conn.create_function("normalize_media_path", 1, normalize_media_path, deterministic=True)
        except TypeError:
            conn.create_function("normalize_media_path", 1, normalize_media_path)

    def _ensure_migration_table(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _apply_migrations(self, conn):
        self._ensure_migration_table(conn)
        applied_versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for version, name, sql in SCHEMA_MIGRATIONS:
            if version in applied_versions:
                continue

            with conn:
                conn.executescript(sql)
                if version == 2:
                    self._backfill_media_import_guard(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, name),
                )
            logger.info("Applied schema migration %s (%s)", version, name)

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

    def get_connection(self):
        """
        Returns a thread-local database connection.
        Each thread gets its own connection for thread-safety.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=True,  # Thread-safe!
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
            logger.info("DatabaseCore._instance zurückgesetzt — Neuinitialisierung möglich")
