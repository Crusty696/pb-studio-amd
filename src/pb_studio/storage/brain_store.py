"""3-DB Hirn-Store unter %APPDATA%\\PB_Studio\\brain\\ (Plan Phase 3).

Verwaltet:
- weights.db   — gelernte Achsen-Gewichte (Beta-Bernoulli)
- patterns.db  — Audio↔Video Profil-Korrelationen
- embedding_cache.db — Hash-Lookup, Embedding-Cache
- embeddings/  — physische .npy-Dateien

Recovery: Bei Korruption von weights.db wird automatisch ein leeres
Schema neu angelegt; embedding_cache bleibt unangetastet.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from .embedding_cache import EmbeddingCache
from .migration_runner import migrate
from .sqlite_init import init_connection

logger = logging.getLogger(__name__)

_MIG_ROOT = Path(__file__).parent / "migrations"


def default_brain_dir() -> Path:
    """%APPDATA%\\PB_Studio\\brain\\ on Windows, ~/.pb_studio/brain elsewhere."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PB_Studio" / "brain"
    return Path.home() / ".pb_studio" / "brain"


class BrainStore:
    """Bündelt die drei Hirn-Store-DBs + Embedding-Files."""

    def __init__(self, brain_dir: Optional[str | Path] = None):
        self.brain_dir = Path(brain_dir) if brain_dir else default_brain_dir()
        self.brain_dir.mkdir(parents=True, exist_ok=True)

        self.weights_path = self.brain_dir / "weights.db"
        self.patterns_path = self.brain_dir / "patterns.db"
        self.cache_path = self.brain_dir / "embedding_cache.db"
        self.embeddings_dir = self.brain_dir / "embeddings"

        self._ensure_or_recover(self.weights_path, _MIG_ROOT / "weights")
        self._ensure_or_recover(self.patterns_path, _MIG_ROOT / "patterns")

        self.weights_conn = sqlite3.connect(
            str(self.weights_path),
            isolation_level=None,
            check_same_thread=False,
        )
        init_connection(self.weights_conn)
        self._weights_lock = __import__("threading").Lock()

        self.patterns_conn = sqlite3.connect(
            str(self.patterns_path),
            isolation_level=None,
            check_same_thread=False,
        )
        init_connection(self.patterns_conn)
        # AP5.5 (Audit 2026-06-10): patterns_conn ist check_same_thread=False,
        # hatte aber im Gegensatz zu weights_conn keinen Lock — konkurrierende
        # Cursor-Nutzung derselben sqlite3-Connection ist nicht thread-safe.
        self._patterns_lock = __import__("threading").Lock()

        self.cache = EmbeddingCache(self.cache_path, self.embeddings_dir)

    def _ensure_or_recover(self, db_path: Path, mig_dir: Path) -> None:
        try:
            migrate(db_path, mig_dir)
        except sqlite3.DatabaseError as e:
            logger.error("Brain-Store DB %s korrupt: %s — Neuanlage", db_path, e)
            corrupt = db_path.with_suffix(db_path.suffix + ".corrupt")
            try:
                db_path.replace(corrupt)
            except Exception:
                db_path.unlink(missing_ok=True)
            migrate(db_path, mig_dir)

    def close(self) -> None:
        with self._weights_lock:
            if self.weights_conn is not None:
                try:
                    self.weights_conn.close()
                except Exception:
                    pass
                self.weights_conn = None

        with self._patterns_lock:
            if self.patterns_conn is not None:
                try:
                    self.patterns_conn.close()
                except Exception:
                    pass
                self.patterns_conn = None

        self.cache.close()

