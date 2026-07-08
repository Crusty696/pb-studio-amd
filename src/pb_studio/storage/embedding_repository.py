"""sqlite-vec embedding repository (Plan Phase 2).

Repository pattern: this module is the ONLY one importing sqlite_vec.
KNN search via vec0 virtual tables. WAL-mode connection.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from .migration_runner import migrate
from .sqlite_init import init_connection

logger = logging.getLogger(__name__)

AUDIO_DIM = 512
VIDEO_DIM = 768


@dataclass
class AudioUnit:
    id: int
    parent_id: Optional[int]
    level: str  # "mix" | "section" | "window"
    media_id: int
    media_hash: str
    start_time: float
    end_time: float
    metadata: dict[str, Any]


@dataclass
class VideoUnit:
    id: int
    parent_id: Optional[int]
    level: str  # "clip" | "scene" | "frame"
    media_id: int
    media_hash: str
    start_time: float
    end_time: float
    motion_score: Optional[float]
    brightness: Optional[float]
    saturation: Optional[float]
    color_temp: Optional[float]
    metadata: dict[str, Any]


@dataclass
class KnnHit:
    unit_id: int
    media_id: int
    distance: float


def _migrations_root() -> Path:
    return Path(__file__).parent / "migrations"


class EmbeddingRepository:
    """Project-store repository for audio + video embeddings."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()
        self._local = threading.local()
        # Review-Fix MEDIUM (2026-07-09): (thread_ident, conn)-Paare, damit
        # Conns toter Threads beim naechsten Zugriff geprunt werden koennen.
        self._all_conns: list[tuple[int, sqlite3.Connection]] = []
        self._conns_lock = threading.Lock()

    def _prune_dead_locked(self) -> None:
        """Schliesst Conns toter Threads. Caller haelt _conns_lock."""
        alive = {t.ident for t in threading.enumerate()}
        survivors: list[tuple[int, sqlite3.Connection]] = []
        for ident, conn in self._all_conns:
            if ident in alive:
                survivors.append((ident, conn))
            else:
                try:
                    conn.close()
                except Exception:
                    pass
        self._all_conns = survivors

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self.db_path), isolation_level=None, check_same_thread=False
            )
            init_connection(conn)
            self._load_vec(conn)
            with self._conns_lock:
                self._prune_dead_locked()
                self._all_conns.append((threading.get_ident(), conn))
            self._local.conn = conn
        return self._local.conn

    @staticmethod
    def _load_vec(conn: sqlite3.Connection) -> None:
        import sqlite_vec
        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)

    def _ensure_schema(self) -> None:
        """Run combined embeddings migrations (audio+video share embeddings.db)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_with_vec(_migrations_root() / "embeddings")

    def _migrate_with_vec(self, migrations_dir: Path) -> None:
        """Like migration_runner.migrate but loads sqlite-vec first."""
        import sqlite_vec
        from .migration_runner import split_sql_statements
        # B-9 FIX: isolation_level=None
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        init_connection(conn)
        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)
        try:
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
                    logger.info(
                        "Applied migration %s in %s -> %d",
                        script.name, migrations_dir.name, version,
                    )
                except Exception:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.OperationalError:
                        pass
                    raise
        finally:
            conn.close()

    def close(self) -> None:
        with self._conns_lock:
            for _ident, conn in self._all_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_conns.clear()
        self._local = threading.local()

    # ---- Audio ----

    def add_audio_unit(
        self,
        *,
        parent_id: Optional[int],
        level: str,
        media_id: int,
        media_hash: str,
        start_time: float,
        end_time: float,
        embedding: np.ndarray,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        emb = self._coerce_embedding(embedding, AUDIO_DIM)
        try:
            self.conn.execute("BEGIN")
            cur = self.conn.execute(
                "INSERT INTO audio_units (parent_id, level, media_id, media_hash, "
                "start_time, end_time, metadata_json) VALUES (?,?,?,?,?,?,?)",
                (
                    parent_id, level, media_id, media_hash,
                    float(start_time), float(end_time),
                    json.dumps(metadata or {}),
                ),
            )
            unit_id = int(cur.lastrowid)
            self.conn.execute(
                "INSERT INTO audio_embeddings (rowid, embedding) VALUES (?, ?)",
                (unit_id, emb.tobytes()),
            )
            self.conn.commit()
            return unit_id
        except Exception:
            self.conn.rollback()
            raise

    def search_audio(
        self,
        query: np.ndarray,
        *,
        level: Optional[str] = None,
        limit: int = 10,
    ) -> list[KnnHit]:
        emb = self._coerce_embedding(query, AUDIO_DIM)
        if level is None:
            sql = (
                "SELECT u.id, u.media_id, e.distance "
                "FROM audio_embeddings e JOIN audio_units u ON u.id = e.rowid "
                "WHERE e.embedding MATCH ? AND k = ? "
                "ORDER BY e.distance"
            )
            rows = self.conn.execute(sql, (emb.tobytes(), int(limit))).fetchall()
        else:
            sql = (
                "SELECT u.id, u.media_id, e.distance "
                "FROM audio_embeddings e JOIN audio_units u ON u.id = e.rowid "
                "WHERE e.embedding MATCH ? AND k = ? AND u.level = ? "
                "ORDER BY e.distance"
            )
            rows = self.conn.execute(
                sql, (emb.tobytes(), int(limit), level)
            ).fetchall()
        return [KnnHit(int(r[0]), int(r[1]), float(r[2])) for r in rows]

    # ---- Video ----

    def add_video_unit(
        self,
        *,
        parent_id: Optional[int],
        level: str,
        media_id: int,
        media_hash: str,
        start_time: float,
        end_time: float,
        embedding: np.ndarray,
        motion_score: Optional[float] = None,
        brightness: Optional[float] = None,
        saturation: Optional[float] = None,
        color_temp: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        emb = self._coerce_embedding(embedding, VIDEO_DIM)
        try:
            self.conn.execute("BEGIN")
            cur = self.conn.execute(
                "INSERT INTO video_units (parent_id, level, media_id, media_hash, "
                "start_time, end_time, motion_score, brightness, saturation, "
                "color_temp, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    parent_id, level, media_id, media_hash,
                    float(start_time), float(end_time),
                    motion_score, brightness, saturation, color_temp,
                    json.dumps(metadata or {}),
                ),
            )
            unit_id = int(cur.lastrowid)
            self.conn.execute(
                "INSERT INTO video_embeddings (rowid, embedding) VALUES (?, ?)",
                (unit_id, emb.tobytes()),
            )
            self.conn.commit()
            return unit_id
        except Exception:
            self.conn.rollback()
            raise

    def search_video(
        self,
        query: np.ndarray,
        *,
        level: Optional[str] = None,
        limit: int = 10,
    ) -> list[KnnHit]:
        emb = self._coerce_embedding(query, VIDEO_DIM)
        if level is None:
            sql = (
                "SELECT u.id, u.media_id, e.distance "
                "FROM video_embeddings e JOIN video_units u ON u.id = e.rowid "
                "WHERE e.embedding MATCH ? AND k = ? "
                "ORDER BY e.distance"
            )
            rows = self.conn.execute(sql, (emb.tobytes(), int(limit))).fetchall()
        else:
            sql = (
                "SELECT u.id, u.media_id, e.distance "
                "FROM video_embeddings e JOIN video_units u ON u.id = e.rowid "
                "WHERE e.embedding MATCH ? AND k = ? AND u.level = ? "
                "ORDER BY e.distance"
            )
            rows = self.conn.execute(
                sql, (emb.tobytes(), int(limit), level)
            ).fetchall()
        return [KnnHit(int(r[0]), int(r[1]), float(r[2])) for r in rows]

    # ---- Lookup helpers ----

    def has_audio_for_media(self, media_id: int, level: Optional[str] = None) -> bool:
        if level:
            row = self.conn.execute(
                "SELECT 1 FROM audio_units WHERE media_id=? AND level=? LIMIT 1",
                (int(media_id), level),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM audio_units WHERE media_id=? LIMIT 1",
                (int(media_id),),
            ).fetchone()
        return row is not None

    def has_video_for_media(self, media_id: int, level: Optional[str] = None) -> bool:
        if level:
            row = self.conn.execute(
                "SELECT 1 FROM video_units WHERE media_id=? AND level=? LIMIT 1",
                (int(media_id), level),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM video_units WHERE media_id=? LIMIT 1",
                (int(media_id),),
            ).fetchone()
        return row is not None

    def add_video_units_bulk(
        self,
        units_data: list[dict[str, Any]],
    ) -> list[int]:
        """Insert multiple video units and their embeddings in a single transaction."""
        inserted_ids = []
        try:
            self.conn.execute("BEGIN")
            for item in units_data:
                emb = self._coerce_embedding(item["embedding"], VIDEO_DIM)
                cur = self.conn.execute(
                    "INSERT INTO video_units (parent_id, level, media_id, media_hash, "
                    "start_time, end_time, motion_score, brightness, saturation, "
                    "color_temp, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item.get("parent_id"), item["level"], item["media_id"], item["media_hash"],
                        float(item["start_time"]), float(item["end_time"]),
                        item.get("motion_score"), item.get("brightness"),
                        item.get("saturation"), item.get("color_temp"),
                        json.dumps(item.get("metadata") or {}),
                    ),
                )
                unit_id = int(cur.lastrowid)
                self.conn.execute(
                    "INSERT INTO video_embeddings (rowid, embedding) VALUES (?, ?)",
                    (unit_id, emb.tobytes()),
                )
                inserted_ids.append(unit_id)
            self.conn.commit()
            return inserted_ids
        except Exception:
            self.conn.rollback()
            raise

    def add_audio_units_bulk(
        self,
        units_data: list[dict[str, Any]],
    ) -> list[int]:
        """Insert multiple audio units and their embeddings in a single transaction."""
        inserted_ids = []
        try:
            self.conn.execute("BEGIN")
            for item in units_data:
                emb = self._coerce_embedding(item["embedding"], AUDIO_DIM)
                cur = self.conn.execute(
                    "INSERT INTO audio_units (parent_id, level, media_id, media_hash, "
                    "start_time, end_time, metadata_json) VALUES (?,?,?,?,?,?,?)",
                    (
                        item.get("parent_id"), item["level"], item["media_id"], item["media_hash"],
                        float(item["start_time"]), float(item["end_time"]),
                        json.dumps(item.get("metadata") or {}),
                    ),
                )
                unit_id = int(cur.lastrowid)
                self.conn.execute(
                    "INSERT INTO audio_embeddings (rowid, embedding) VALUES (?, ?)",
                    (unit_id, emb.tobytes()),
                )
                inserted_ids.append(unit_id)
            self.conn.commit()
            return inserted_ids
        except Exception:
            self.conn.rollback()
            raise

    @staticmethod
    def _coerce_embedding(vec: np.ndarray, dim: int) -> np.ndarray:
        arr = np.asarray(vec, dtype=np.float32).reshape(-1)
        if arr.size != dim:
            raise ValueError(f"Embedding-Dim {arr.size} != erwartet {dim}")
        norm = np.linalg.norm(arr)
        if norm > 1e-8:
            arr = arr / norm
        return arr
