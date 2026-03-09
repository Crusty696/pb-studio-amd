# Data Persistence Skill (SQLite & FAISS Vector)

## Trigger
Aktiviere diesen Skill automatisch bei:
- "SQLite", "Database", "FAISS", "Vector", "Embedding", "Query"
- Arbeit an `src/pb_studio/data/`, `database*.py`, `vector*.py`
- Fragen zu Datenbankoperationen, Transaktionen, Indizes

## Cross-References
- → `ai-inference.md` (Embeddings generieren)
- → `python-backend.md` (Error Handling, Async)
- → `service-architecture.md` (Singleton Pattern)
- → `debugging.md` (Query Performance)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Hybrid Storage** | SQLite für relational, FAISS für Vektoren |
| **Transaction Safety** | DB nie in inkonsistentem Zustand lassen |
| **Thread Safety** | Explizites Locking für Schreiboperationen |

---

## 1. SQLite Connection Management

```python
import sqlite3
from pathlib import Path
from typing import Optional
import threading
import logging

logger = logging.getLogger(__name__)

class DatabaseCore:
    """Thread-safe SQLite Singleton mit WAL Mode."""
    
    _instance: Optional['DatabaseCore'] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Path = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Path = None):
        if self._initialized:
            return
        
        self.db_path = db_path or Path("data/pb_studio.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection: Optional[sqlite3.Connection] = None
        self._write_lock = threading.Lock()
        self._initialized = True
        
        self._init_db()
    
    def _init_db(self):
        """Initialisiert Datenbank mit WAL Mode und Schema."""
        conn = self.get_connection()
        
        # WAL Mode für bessere Concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        
        # Schema erstellen
        self._create_tables(conn)
        conn.commit()
        
        logger.info(f"Database initialisiert: {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Gibt Thread-lokale Connection zurück."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Erstellt alle Tabellen."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('audio', 'video', 'image')),
                duration_sec REAL,
                metadata TEXT,
                embedding_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_media_project ON media_files(project_id);
            CREATE INDEX IF NOT EXISTS idx_media_type ON media_files(type);
            CREATE INDEX IF NOT EXISTS idx_media_embedding ON media_files(embedding_id);
        """)
    
    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Thread-safe Write Operation."""
        with self._write_lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"DB Write Error: {e}")
                raise
    
    def execute_read(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Read Operation (kein Lock nötig bei WAL)."""
        conn = self.get_connection()
        return conn.execute(query, params).fetchall()
    
    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """Batch Insert für Performance."""
        with self._write_lock:
            conn = self.get_connection()
            try:
                cursor = conn.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"DB Batch Error: {e}")
                raise
```

---

## 2. Repository Pattern

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MediaFile:
    id: Optional[int] = None
    project_id: int = 0
    path: str = ""
    type: str = "audio"
    duration_sec: float = 0.0
    metadata: Optional[dict] = None
    embedding_id: Optional[str] = None
    created_at: Optional[datetime] = None

class MediaRepository:
    """Repository für MediaFile CRUD Operationen."""
    
    def __init__(self, db: DatabaseCore = None):
        self.db = db or DatabaseCore()
    
    def create(self, media: MediaFile) -> int:
        """Erstellt neuen MediaFile Eintrag."""
        import json
        
        return self.db.execute_write(
            """INSERT INTO media_files 
               (project_id, path, type, duration_sec, metadata, embedding_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                media.project_id,
                media.path,
                media.type,
                media.duration_sec,
                json.dumps(media.metadata) if media.metadata else None,
                media.embedding_id
            )
        )
    
    def get_by_id(self, media_id: int) -> Optional[MediaFile]:
        """Holt MediaFile nach ID."""
        rows = self.db.execute_read(
            "SELECT * FROM media_files WHERE id = ?",
            (media_id,)
        )
        return self._row_to_media(rows[0]) if rows else None
    
    def get_by_project(self, project_id: int, type: str = None) -> list[MediaFile]:
        """Holt alle MediaFiles eines Projekts."""
        if type:
            rows = self.db.execute_read(
                "SELECT * FROM media_files WHERE project_id = ? AND type = ?",
                (project_id, type)
            )
        else:
            rows = self.db.execute_read(
                "SELECT * FROM media_files WHERE project_id = ?",
                (project_id,)
            )
        return [self._row_to_media(row) for row in rows]
    
    def update_embedding(self, media_id: int, embedding_id: str) -> bool:
        """Aktualisiert Embedding-Referenz."""
        affected = self.db.execute_write(
            "UPDATE media_files SET embedding_id = ? WHERE id = ?",
            (embedding_id, media_id)
        )
        return affected > 0
    
    def delete(self, media_id: int) -> bool:
        """Löscht MediaFile."""
        affected = self.db.execute_write(
            "DELETE FROM media_files WHERE id = ?",
            (media_id,)
        )
        return affected > 0
    
    def _row_to_media(self, row: sqlite3.Row) -> MediaFile:
        """Konvertiert DB Row zu MediaFile."""
        import json
        return MediaFile(
            id=row["id"],
            project_id=row["project_id"],
            path=row["path"],
            type=row["type"],
            duration_sec=row["duration_sec"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            embedding_id=row["embedding_id"],
            created_at=row["created_at"]
        )
```

---

## 3. FAISS Vector Store

```python
import faiss
import numpy as np
from pathlib import Path
from typing import Optional
import json

class VectorStore:
    """FAISS Vector Store für Embeddings."""
    
    def __init__(
        self,
        dimension: int = 768,  # SigLIP/Moondream default
        index_path: Path = None
    ):
        self.dimension = dimension
        self.index_path = index_path or Path("data/vectors.faiss")
        self.metadata_path = self.index_path.with_suffix(".json")
        
        self.index: Optional[faiss.IndexFlatIP] = None
        self.id_map: dict[int, str] = {}  # FAISS ID -> External ID
        
        self._load_or_create()
    
    def _load_or_create(self):
        """Lädt existierenden Index oder erstellt neuen."""
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            
            if self.metadata_path.exists():
                with open(self.metadata_path) as f:
                    self.id_map = {int(k): v for k, v in json.load(f).items()}
            
            logger.info(f"VectorStore geladen: {self.index.ntotal} Vektoren")
        else:
            # Inner Product für Cosine Similarity (mit normalisierten Vektoren)
            self.index = faiss.IndexFlatIP(self.dimension)
            logger.info(f"VectorStore erstellt: Dimension {self.dimension}")
    
    def add(self, embedding: np.ndarray, external_id: str) -> int:
        """Fügt Embedding hinzu."""
        # L2-Normalisierung für Cosine Similarity
        embedding = self._normalize(embedding.astype(np.float32))
        
        # Reshape falls nötig
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        # FAISS ID ist der aktuelle Index
        faiss_id = self.index.ntotal
        
        self.index.add(embedding)
        self.id_map[faiss_id] = external_id
        
        return faiss_id
    
    def add_batch(self, embeddings: np.ndarray, external_ids: list[str]) -> list[int]:
        """Batch-Add für Performance."""
        embeddings = self._normalize(embeddings.astype(np.float32))
        
        start_id = self.index.ntotal
        self.index.add(embeddings)
        
        faiss_ids = []
        for i, ext_id in enumerate(external_ids):
            faiss_id = start_id + i
            self.id_map[faiss_id] = ext_id
            faiss_ids.append(faiss_id)
        
        return faiss_ids
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        threshold: float = 0.5
    ) -> list[tuple[str, float]]:
        """Sucht ähnliche Vektoren."""
        query = self._normalize(query_embedding.astype(np.float32))
        
        if query.ndim == 1:
            query = query.reshape(1, -1)
        
        distances, indices = self.index.search(query, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and dist >= threshold:  # FAISS gibt -1 für nicht gefunden
                external_id = self.id_map.get(int(idx))
                if external_id:
                    results.append((external_id, float(dist)))
        
        return results
    
    def save(self):
        """Speichert Index und Metadata."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        faiss.write_index(self.index, str(self.index_path))
        
        with open(self.metadata_path, 'w') as f:
            json.dump({str(k): v for k, v in self.id_map.items()}, f)
        
        logger.info(f"VectorStore gespeichert: {self.index.ntotal} Vektoren")
    
    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """L2-Normalisierung für Cosine Similarity."""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Division by zero vermeiden
        return vectors / norms
    
    @property
    def count(self) -> int:
        """Anzahl der Vektoren im Index."""
        return self.index.ntotal if self.index else 0
```

---

## 4. Schema Migration

```python
def migrate_schema(db: DatabaseCore, version: int = 1):
    """Einfache Schema-Migration ohne externe Tools."""
    
    conn = db.get_connection()
    
    # Aktuelle Version holen
    try:
        result = conn.execute(
            "SELECT value FROM settings WHERE key = 'schema_version'"
        ).fetchone()
        current_version = int(result["value"]) if result else 0
    except sqlite3.OperationalError:
        # settings Tabelle existiert nicht
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        current_version = 0
    
    # Migrationen ausführen
    migrations = {
        1: """
            ALTER TABLE media_files ADD COLUMN analyzed_at TIMESTAMP;
        """,
        2: """
            CREATE INDEX IF NOT EXISTS idx_media_analyzed 
            ON media_files(analyzed_at);
        """
    }
    
    for v in range(current_version + 1, version + 1):
        if v in migrations:
            try:
                conn.executescript(migrations[v])
                logger.info(f"Migration {v} ausgeführt")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    logger.debug(f"Migration {v} bereits angewendet")
                else:
                    raise
    
    # Version aktualisieren
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("schema_version", str(version))
    )
    conn.commit()
```

---

## 5. Transaction Context Manager

```python
from contextlib import contextmanager

@contextmanager
def transaction(db: DatabaseCore):
    """Context Manager für sichere Transaktionen."""
    conn = db.get_connection()
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction rollback: {e}")
        raise
```

---

## Checkliste: Data Persistence

### SQLite
- [ ] WAL Mode aktiviert?
- [ ] Write-Lock für Schreiboperationen?
- [ ] Row Factory auf `sqlite3.Row` gesetzt?
- [ ] Indizes für häufige Queries erstellt?
- [ ] Foreign Keys mit ON DELETE CASCADE?

### FAISS
- [ ] Dimension passt zum Model (768 für SigLIP)?
- [ ] Vektoren vor Add normalisiert?
- [ ] `save()` nach Batch-Updates aufgerufen?
- [ ] Threshold für Suche sinnvoll gewählt?

### Allgemein
- [ ] Fehlerbehandlung mit Rollback?
- [ ] Logging für wichtige Operationen?
- [ ] Backup-Strategie definiert?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `database is locked` | Concurrent Writes ohne Lock | `execute_write` mit Lock verwenden |
| `FAISS dimension mismatch` | Embedding-Größe falsch | Model-Output-Dimension prüfen |
| `no such table` | Schema nicht initialisiert | `_create_tables()` aufrufen |
| `foreign key mismatch` | Referenzierte ID existiert nicht | CASCADE oder vorher prüfen |
| `disk I/O error` | DB-Datei korrupt | Backup wiederherstellen, WAL-Checkpoint |
