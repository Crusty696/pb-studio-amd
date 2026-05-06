"""Hash-keyed embedding cache (Plan Phase 2/3, Hirn-Store).

Embedding-Files liegen physisch in <brain_dir>/embeddings/<hash>_<model>.npy.
Diese DB ist nur Index. Cross-project Re-Use über media_hash.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .sqlite_init import init_connection

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "embedding_cache"


@dataclass
class CacheEntry:
    media_hash: str
    media_type: str          # "audio" | "video"
    embedding_path: Path
    model_name: str
    model_version: str
    computed_at: str
    file_size_bytes: Optional[int]


class EmbeddingCache:
    """Cross-project hash → embedding lookup."""

    def __init__(self, db_path: str | Path, embeddings_dir: str | Path):
        self.db_path = Path(db_path)
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        init_connection(self.conn)

    def _migrate(self) -> None:
        from .migration_runner import migrate
        migrate(self.db_path, _MIGRATIONS_DIR)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def lookup(
        self, media_hash: str, model_name: str, model_version: str
    ) -> Optional[CacheEntry]:
        row = self.conn.execute(
            "SELECT media_hash, media_type, embedding_path, model_name, "
            "model_version, computed_at, file_size_bytes "
            "FROM media_embedding_index WHERE media_hash=? "
            "AND model_name=? AND model_version=?",
            (media_hash, model_name, model_version),
        ).fetchone()
        if row is None:
            return None
        path = Path(row[2])
        if not path.is_file():
            return None
        return CacheEntry(
            media_hash=row[0],
            media_type=row[1],
            embedding_path=path,
            model_name=row[3],
            model_version=row[4],
            computed_at=row[5],
            file_size_bytes=row[6],
        )

    def store(
        self,
        *,
        media_hash: str,
        media_type: str,
        embedding: np.ndarray,
        model_name: str,
        model_version: str,
    ) -> CacheEntry:
        emb = np.asarray(embedding, dtype=np.float32)
        safe_model = model_name.replace("/", "_").replace(":", "_")
        target = self.embeddings_dir / f"{media_hash[:16]}_{safe_model}_v{model_version}.npy"
        np.save(target, emb)

        now = datetime.now(timezone.utc).isoformat()
        size = target.stat().st_size

        self.conn.execute(
            "INSERT OR REPLACE INTO media_embedding_index "
            "(media_hash, media_type, embedding_path, model_name, "
            "model_version, computed_at, file_size_bytes) "
            "VALUES (?,?,?,?,?,?,?)",
            (media_hash, media_type, str(target), model_name,
             model_version, now, size),
        )
        return CacheEntry(
            media_hash=media_hash,
            media_type=media_type,
            embedding_path=target,
            model_name=model_name,
            model_version=model_version,
            computed_at=now,
            file_size_bytes=size,
        )

    def load_array(self, entry: CacheEntry) -> np.ndarray:
        return np.load(entry.embedding_path)
