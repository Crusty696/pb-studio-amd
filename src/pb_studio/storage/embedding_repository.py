"""sqlite-vec embedding repository (Plan Phase 2).

Repository pattern: this module is the ONLY one importing sqlite_vec.
KNN search via vec0 virtual tables. WAL-mode connection.
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import numpy as np

from .migration_runner import migrate
from .sqlite_init import init_connection
from .embedding_contract import (
    EmbeddingMigrationRequiredError,
    get_embedding_contract,
    validate_embedding,
)

logger = logging.getLogger(__name__)

AUDIO_DIM = get_embedding_contract("raw_audio").dimension
VIDEO_DIM = get_embedding_contract("raw_video").dimension


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

    def __init__(
        self,
        db_path: str | Path,
        *,
        project_uuid: str | None = None,
        owner_uuid: str | None = None,
        _migration_fault_injector: Callable[[str], None] | None = None,
    ):
        self.db_path = Path(db_path)
        existed_nonempty = self.db_path.is_file() and self.db_path.stat().st_size > 0
        self.project_uuid = self._optional_uuid(project_uuid, "project_uuid")
        self.owner_uuid = self._optional_uuid(owner_uuid, "owner_uuid")
        if not existed_nonempty and self.project_uuid is None:
            raise ValueError("New embeddings.db requires immutable project_uuid")
        if self.project_uuid is not None and self.owner_uuid is None:
            self.owner_uuid = self.project_uuid
        self._ensure_schema(
            project_uuid=self.project_uuid,
            owner_uuid=self.owner_uuid,
            fault_injector=_migration_fault_injector,
        )
        stored_project, stored_owner = self._read_store_identity()
        if self.project_uuid is not None and stored_project != self.project_uuid:
            raise EmbeddingMigrationRequiredError("Embedding project identity mismatch")
        if self.owner_uuid is not None and stored_owner != self.owner_uuid:
            raise EmbeddingMigrationRequiredError("Embedding owner identity mismatch")
        self.project_uuid = stored_project
        self.owner_uuid = stored_owner
        self._vec_dimensions = self._read_vec_dimensions()
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

    @staticmethod
    def _optional_uuid(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"{field} must be a UUID") from exc

    def _ensure_schema(
        self,
        *,
        project_uuid: str | None,
        owner_uuid: str | None,
        fault_injector: Callable[[str], None] | None,
    ) -> None:
        """Run combined embeddings migrations (audio+video share embeddings.db)."""
        existed_nonempty = self.db_path.is_file() and self.db_path.stat().st_size > 0
        safe_empty = False
        if existed_nonempty:
            safe_empty = self._preflight_existing_schema_read_only()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_with_vec(
            _migrations_root() / "embeddings",
            allow_obj77_migration=not existed_nonempty or safe_empty,
            project_uuid=project_uuid,
            owner_uuid=owner_uuid,
            fault_injector=fault_injector,
        )

    def _read_store_identity(self) -> tuple[str, str]:
        connection = sqlite3.connect(str(self.db_path), isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            rows = connection.execute(
                "SELECT project_uuid,owner_uuid FROM embedding_store_identity"
            ).fetchall()
        finally:
            connection.close()
        if len(rows) != 1:
            raise EmbeddingMigrationRequiredError(
                "Embedding store identity is missing or ambiguous; migration_required"
            )
        try:
            return str(uuid.UUID(str(rows[0][0]))), str(uuid.UUID(str(rows[0][1])))
        except (TypeError, ValueError, AttributeError) as exc:
            raise EmbeddingMigrationRequiredError(
                "Embedding store identity is invalid; migration_required"
            ) from exc

    def _preflight_existing_schema_read_only(self) -> bool:
        """Reject pending OBJ77 migrations before WAL/DDL or directory writes."""
        migrations = _migrations_root() / "embeddings"
        versions = [
            int(match.group(1))
            for path in migrations.glob("*.sql")
            if (match := re.match(r"^(\d+)", path.name))
        ]
        latest = max(versions, default=0)
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            product_tables = int(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') "
                    "AND name NOT LIKE 'sqlite_%'"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        if current == 0 and product_tables == 0:
            return True
        if current < latest:
            raise EmbeddingMigrationRequiredError(
                f"Existing embeddings.db schema {current} requires approved "
                f"schema {latest}; migration_required"
            )
        return False

    def _read_vec_dimensions(self) -> dict[str, int]:
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        init_connection(conn)
        try:
            dimensions: dict[str, int] = {}
            for table in ("audio_embeddings", "video_embeddings"):
                row = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if row is None or not isinstance(row[0], str):
                    raise EmbeddingMigrationRequiredError(
                        f"Missing sqlite-vec table {table}"
                    )
                match = re.search(r"FLOAT\s*\[\s*(\d+)\s*\]", row[0], re.I)
                if match is None:
                    raise EmbeddingMigrationRequiredError(
                        f"Cannot determine sqlite-vec dimension for {table}"
                    )
                dimensions[table] = int(match.group(1))
            return dimensions
        finally:
            conn.close()

    def _require_vec_dimension(
        self,
        table: str,
        *,
        expected_dimension: int,
    ) -> None:
        actual = self._vec_dimensions.get(table)
        if actual != expected_dimension:
            raise EmbeddingMigrationRequiredError(
                f"{table} uses legacy FLOAT[{actual}], expected "
                f"FLOAT[{expected_dimension}]; migration_required"
            )

    def _migrate_with_vec(
        self,
        migrations_dir: Path,
        *,
        allow_obj77_migration: bool = False,
        project_uuid: str | None = None,
        owner_uuid: str | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        """Like migration_runner.migrate but loads sqlite-vec first."""
        import sqlite_vec
        from .migration_runner import split_sql_statements
        # B-9 FIX: isolation_level=None
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
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

            pending_obj77 = any(version >= 2 and version > current for version, _ in parsed_scripts)
            if pending_obj77 and not allow_obj77_migration:
                raise EmbeddingMigrationRequiredError(
                    "Existing embeddings.db requires explicit OBJ77 migration; "
                    "migration_required"
                )
            init_connection(conn)
            conn.create_function(
                "sha256_blob",
                1,
                lambda value: hashlib.sha256(bytes(value)).hexdigest(),
            )
            conn.create_function(
                "obj77_utc_now",
                0,
                lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            )

            atomic_initialization = current == 0 and allow_obj77_migration
            try:
                if atomic_initialization:
                    conn.execute("BEGIN")
                for version, script in parsed_scripts:
                    if version <= current:
                        continue
                    sql = script.read_text(encoding="utf-8")
                    statements = split_sql_statements(sql)
                    if not atomic_initialization:
                        conn.execute("BEGIN")
                    for stmt in statements:
                        conn.execute(stmt)
                    if version == 2:
                        if project_uuid is None or owner_uuid is None:
                            raise ValueError(
                                "Schema v2 creation requires project and owner UUID"
                            )
                        conn.execute(
                            "INSERT INTO embedding_store_identity "
                            "(singleton_id,project_uuid,owner_uuid,schema_version) "
                            "VALUES (1,?,?,2)",
                            (project_uuid, owner_uuid),
                        )
                    conn.execute(f"PRAGMA user_version = {version}")
                    if fault_injector is not None:
                        fault_injector(f"after_schema:{version}")
                    if not atomic_initialization:
                        conn.execute("COMMIT")
                    logger.info(
                        "Applied migration %s in %s -> %d",
                        script.name, migrations_dir.name, version,
                    )
                if atomic_initialization:
                    conn.execute("COMMIT")
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
        self._require_vec_dimension(
            "audio_embeddings",
            expected_dimension=AUDIO_DIM,
        )
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
        self._require_vec_dimension(
            "audio_embeddings",
            expected_dimension=AUDIO_DIM,
        )
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
        self._require_vec_dimension(
            "video_embeddings",
            expected_dimension=VIDEO_DIM,
        )
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
        self._require_vec_dimension(
            "video_embeddings",
            expected_dimension=VIDEO_DIM,
        )
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
        prepared = [
            (item, self._coerce_embedding(item["embedding"], VIDEO_DIM))
            for item in units_data
        ]
        self._require_vec_dimension(
            "video_embeddings",
            expected_dimension=VIDEO_DIM,
        )
        inserted_ids = []
        try:
            self.conn.execute("BEGIN")
            for item, emb in prepared:
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
        prepared = [
            (item, self._coerce_embedding(item["embedding"], AUDIO_DIM))
            for item in units_data
        ]
        self._require_vec_dimension(
            "audio_embeddings",
            expected_dimension=AUDIO_DIM,
        )
        inserted_ids = []
        try:
            self.conn.execute("BEGIN")
            for item, emb in prepared:
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
        return validate_embedding(
            vec,
            expected_dimension=dim,
            contract_name="sqlite-vec",
        )
