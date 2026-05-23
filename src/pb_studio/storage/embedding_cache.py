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

        self.conn = sqlite3.connect(
            str(self.db_path), isolation_level=None, check_same_thread=False
        )
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

        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO media_embedding_index "
                "(media_hash, media_type, embedding_path, model_name, "
                "model_version, computed_at, file_size_bytes) "
                "VALUES (?,?,?,?,?,?,?)",
                (media_hash, media_type, str(target), model_name,
                 model_version, now, size),
            )
        except Exception as e:
            try:
                target.unlink(missing_ok=True)
            except Exception as unlink_err:
                logger.warning("EmbeddingCache: failed to delete orphan file %s: %s", target, unlink_err)
            raise e

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

    # M7-Fix (I-M1, 2026-05-20): LRU-size-bounded cleanup
    # Vor Fix: embedding_cache wuchs unbegrenzt — kein TTL, keine Size-Limits.
    # Nach Fix: enforce_size_limit(max_bytes) entfernt aelteste Embeddings
    # bis Gesamtgroesse unter limit. Wird typischerweise beim Backend-Start
    # ODER nach storage_full-Events aufgerufen.

    def total_size_bytes(self) -> int:
        """Gesamtgroesse aller Embedding-Files in bytes."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(file_size_bytes), 0) FROM media_embedding_index"
        ).fetchone()
        return int(row[0] or 0)

    def enforce_size_limit(self, max_bytes: int) -> int:
        """Loescht aelteste Embeddings (LRU via computed_at) bis Gesamtgroesse <= max_bytes.

        Args:
            max_bytes: Hard-Limit in bytes (z.B. 5GB = 5 * 1024**3).

        Returns:
            Anzahl entfernter Embeddings.
        """
        if max_bytes <= 0:
            return 0
        current = self.total_size_bytes()
        if current <= max_bytes:
            return 0
        # Aelteste zuerst — computed_at ASC
        rows = self.conn.execute(
            "SELECT media_hash, model_name, model_version, embedding_path, file_size_bytes "
            "FROM media_embedding_index ORDER BY computed_at ASC"
        ).fetchall()
        removed = 0
        for media_hash, model_name, model_version, path_str, size_bytes in rows:
            if current <= max_bytes:
                break
            try:
                Path(path_str).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("LRU-Eviction: konnte %s nicht löschen: %s", path_str, exc)
                continue
            self.conn.execute(
                "DELETE FROM media_embedding_index WHERE media_hash=? "
                "AND model_name=? AND model_version=?",
                (media_hash, model_name, model_version),
            )
            current -= int(size_bytes or 0)
            removed += 1
        if removed:
            logger.info("LRU-Eviction: %d Embeddings entfernt, Cache-Size %d → %d bytes",
                        removed, current + sum(int(r[4] or 0) for r in rows[:removed]), current)
        return removed
