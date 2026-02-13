import sqlite3
import logging
import threading
from pathlib import Path
from contextlib import contextmanager
from src.pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

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
                    cls._instance = super(DatabaseCore, cls).__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._init_db()  # Initialize immediately
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
            init_conn = sqlite3.connect(str(self.db_path), check_same_thread=True)
            init_conn.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrency
            init_conn.execute("PRAGMA journal_mode=WAL;")
            init_conn.execute("PRAGMA foreign_keys=ON;")

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
        cursor = conn.cursor()
        
        # 1. Projects Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                json_data TEXT -- Flexible storage for settings/state
            )
        """)
        
        # 2. Media Table (Files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                file_path TEXT NOT NULL,
                file_hash TEXT, -- For duplicate detection
                duration_sec REAL,
                status TEXT DEFAULT 'pending', -- pending, analyzing, ready, error
                metadata_json TEXT, -- Technical metadata (codec, resolution)
                ai_data_json TEXT, -- Analysis results (tags, captions, bpm)
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        
        # 3. Vector Index Table (Mapping FAISS IDs to Media)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_map (
                faiss_id INTEGER PRIMARY KEY,
                media_id INTEGER,
                segment_start REAL,
                segment_end REAL,
                description TEXT,
                FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_hash 
            ON media(file_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_project 
            ON media(project_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_status 
            ON media(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vector_map_media 
            ON vector_map(media_id)
        """)
        
        conn.commit()
        
        # Ensure Default Project Exists
        res = cursor.execute("SELECT count(*) FROM projects").fetchone()
        if res[0] == 0:
            cursor.execute("INSERT INTO projects (name) VALUES ('Default Project')")
            conn.commit()
            logger.info("Created 'Default Project' (ID: 1)")

    def get_connection(self):
        """
        Returns a thread-local database connection.
        Each thread gets its own connection for thread-safety.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=True  # Thread-safe!
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA foreign_keys=ON;")
            # Connection tracken fuer sauberes Shutdown
            with self._conn_lock:
                self._all_connections.append(self._local.conn)
            logger.debug(f"Created new DB connection for thread {threading.current_thread().name}")
        return self._local.conn

    @contextmanager
    def transaction(self):
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
        self._initialized = False
        logger.info("Database shutdown complete - all connections closed")
