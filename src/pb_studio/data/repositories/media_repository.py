import logging
import json
import gzip
import base64
import sqlite3
import time
import functools
from typing import List, Optional, Dict, Callable

from pb_studio.data.database_core import DatabaseCore, normalize_media_path

logger = logging.getLogger(__name__)

# Exponential backoff schedule for transient SQLite lock contention.
# Total wall-clock budget across the 5 retries: 50+100+200+400+800 = 1550 ms.
# After the 5th retry the original OperationalError is propagated.
_LOCK_RETRY_DELAYS = (0.05, 0.10, 0.20, 0.40, 0.80)

# Compressed depth-metadata (Spec 00009 T006, P2.2).
# meta-JSON payloads above the threshold are gzip+base64 encoded with a
# magic prefix so disk usage drops by ~50% on depth-heavy projects.
# Decoding is transparent inside _row_to_dict so external callers that do
# ``json.loads(row["metadata_json"])`` keep working unchanged. The TEXT
# column is preserved by base64-wrapping the gzip bytes.
_META_COMPRESS_THRESHOLD_BYTES = 10 * 1024  # 10 KB
_META_GZIP_MAGIC = "GZ1:"
_VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv")


def _is_video_path(file_path: str) -> bool:
    return str(file_path).lower().endswith(_VIDEO_EXTENSIONS)


def _migrate_metadata_for_path(file_path: str, metadata: Optional[Dict]) -> Dict:
    from pb_studio.data.schemas.media_json_schema import (
        migrate_audio_metadata,
        migrate_video_metadata,
    )

    payload = dict(metadata or {})
    migrator = migrate_video_metadata if _is_video_path(file_path) else migrate_audio_metadata
    return migrator(payload)


def _migrate_ai_data_for_path(file_path: str, ai_data: Optional[Dict]) -> Dict:
    from pb_studio.data.schemas.media_json_schema import (
        migrate_audio_ai_data,
        migrate_video_ai_data,
    )

    payload = dict(ai_data or {})
    migrator = migrate_video_ai_data if _is_video_path(file_path) else migrate_audio_ai_data
    return migrator(payload)


def _serialize_meta(meta: Optional[Dict]) -> str:
    """Encode ``meta`` for storage in the ``metadata_json`` TEXT column.

    Payloads larger than :data:`_META_COMPRESS_THRESHOLD_BYTES` (10 KB) are
    gzip-compressed and base64-encoded with the :data:`_META_GZIP_MAGIC`
    prefix so the column remains UTF-8 TEXT-safe. Smaller payloads are
    stored as plain JSON for cheap inspectability and migration-free
    rollback.
    """
    if meta is None:
        return "{}"
    json_text = json.dumps(meta)
    raw = json_text.encode("utf-8")
    if len(raw) <= _META_COMPRESS_THRESHOLD_BYTES:
        return json_text
    packed = gzip.compress(raw)
    return _META_GZIP_MAGIC + base64.b64encode(packed).decode("ascii")


def _deserialize_meta_str(raw: Optional[str]) -> str:
    """Return a plain JSON string for ``metadata_json`` regardless of
    whether the row was stored compressed or plain.

    External callers (e.g. ``backend/app_state.py``) do
    ``json.loads(row["metadata_json"])`` directly, so the repository must
    hand back a JSON-string -- not a dict. ``None``/empty maps to ``"{}"``.
    """
    if raw is None:
        return "{}"
    if not isinstance(raw, str):
        # Defensive: sqlite3 row factory yields str for TEXT columns; if a
        # downstream caller mutates the row to bytes, normalize here.
        try:
            raw = raw.decode("utf-8")  # type: ignore[union-attr]
        except Exception:
            return "{}"
    if not raw:
        return "{}"
    if raw.startswith(_META_GZIP_MAGIC):
        try:
            packed = base64.b64decode(raw[len(_META_GZIP_MAGIC):].encode("ascii"))
            return gzip.decompress(packed).decode("utf-8")
        except Exception:
            logger.warning(
                "MediaRepository: failed to decode compressed metadata_json; "
                "returning empty meta. prefix=%r", raw[:32],
            )
            return "{}"
    return raw



def _is_retryable_lock_error(exc: sqlite3.OperationalError) -> bool:
    """Return True only for transient SQLite BUSY/LOCKED errors.

    SQLite raises ``OperationalError`` with two messages we treat as transient:
      * ``"database is locked"``       (SQLITE_BUSY)
      * ``"database table is locked"`` (SQLITE_LOCKED)

    Any other ``OperationalError`` (malformed SQL, missing column, syntax
    error, ``no such table``, etc.) is a real bug -- retrying would only
    hide it. ``IntegrityError`` (UNIQUE/FK/CHECK violations and the
    ``trg_media_guard_*`` ABORT in migration 2) is *also* not retryable
    because it is deterministic and is already handled in :meth:`add_media`.
    """
    msg = str(exc).lower()
    return ("database is locked" in msg) or ("database table is locked" in msg)


def _retry_on_database_lock(func: Callable) -> Callable:
    """Decorator: retry method on transient ``database is locked`` errors.

    Uses exponential backoff (50ms, 100ms, 200ms, 400ms, 800ms). Retries
    only on :class:`sqlite3.OperationalError` whose message indicates a
    BUSY/LOCKED condition; all other exceptions (including
    :class:`sqlite3.IntegrityError` from the duplicate-import guard) are
    propagated immediately.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exc: Optional[sqlite3.OperationalError] = None
        max_attempts = len(_LOCK_RETRY_DELAYS) + 1  # 1 initial try + 5 retries
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                if not _is_retryable_lock_error(exc):
                    # Non-lock OperationalError: propagate without retrying.
                    raise
                last_exc = exc
                if attempt >= len(_LOCK_RETRY_DELAYS):
                    logger.error(
                        "MediaRepository.%s: exhausted %d retries -- DB still locked: %s",
                        func.__name__,
                        len(_LOCK_RETRY_DELAYS),
                        exc,
                    )
                    raise
                delay = _LOCK_RETRY_DELAYS[attempt]
                logger.info(
                    "MediaRepository.%s: database locked (attempt %d/%d); "
                    "backing off %.3fs before retry",
                    func.__name__,
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                time.sleep(delay)
        # Defensive fallthrough; the loop always returns or raises.
        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc
        raise RuntimeError(  # pragma: no cover - defensive
            "MediaRepository retry loop exited without success or error"
        )

    return wrapper


class MediaRepository:
    def __init__(self):
        self.db = DatabaseCore()

    @staticmethod
    def _normalize_path(file_path: str) -> str:
        return normalize_media_path(file_path)

    @staticmethod
    def _row_to_dict(row) -> Optional[Dict]:
        if not row:
            return None
        d = dict(row)
        file_path = d.get("file_path", "")
        is_video = _is_video_path(file_path)

        if "metadata_json" in d:
            meta_str = _deserialize_meta_str(d.get("metadata_json"))
            try:
                meta_dict = json.loads(meta_str)
                from pb_studio.data.schemas.media_json_schema import migrate_audio_metadata, migrate_video_metadata
                if is_video:
                    meta_dict = migrate_video_metadata(meta_dict)
                else:
                    meta_dict = migrate_audio_metadata(meta_dict)
                d["metadata_json"] = json.dumps(meta_dict)
            except Exception as exc:
                logger.warning("MediaRepository: failed to migrate metadata_json: %s", exc)
                d["metadata_json"] = meta_str

        if "ai_data_json" in d and d.get("ai_data_json"):
            try:
                ai_dict = json.loads(d["ai_data_json"])
                from pb_studio.data.schemas.media_json_schema import migrate_audio_ai_data, migrate_video_ai_data
                if is_video:
                    ai_dict = migrate_video_ai_data(ai_dict)
                else:
                    ai_dict = migrate_audio_ai_data(ai_dict)
                d["ai_data_json"] = json.dumps(ai_dict)
            except Exception as exc:
                logger.warning("MediaRepository: failed to migrate ai_data_json: %s", exc)

        return d

    def find_by_project_and_path(self, project_id: int, file_path: str) -> Optional[Dict]:
        """Find the canonical media row by project and normalized path."""
        normalized_path = self._normalize_path(file_path)
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT m.*
            FROM media_import_guard mig
            JOIN media m ON m.id = mig.media_id
            WHERE mig.project_id = ? AND mig.normalized_file_path = ?
            """,
            (project_id, normalized_path),
        )
        return self._row_to_dict(cursor.fetchone())

    @_retry_on_database_lock
    def add_media(self, project_id: int, file_path: str, file_hash: str, duration: float, meta: Dict = None) -> int:
        """Add a media file to the database with idempotent project+path semantics.

        Wrapped with :func:`_retry_on_database_lock` -- transient
        ``database is locked`` errors are retried with exponential backoff.
        ``IntegrityError`` (duplicate-import guard) is handled inline and
        is *not* retried.
        """
        normalized_path = self._normalize_path(file_path)
        json_meta = _serialize_meta(
            _migrate_metadata_for_path(normalized_path, meta)
        )

        try:
            with self.db.transaction(immediate=True) as conn:
                cursor = conn.cursor()
                existing = cursor.execute(
                    """
                    SELECT m.id
                    FROM media_import_guard mig
                    JOIN media m ON m.id = mig.media_id
                    WHERE mig.project_id = ? AND mig.normalized_file_path = ?
                    """,
                    (project_id, normalized_path),
                ).fetchone()
                if existing:
                    cursor.execute(
                        """
                        UPDATE media
                        SET file_hash = ?, duration_sec = ?, metadata_json = ?, status = COALESCE(status, 'pending')
                        WHERE id = ?
                        """,
                        (file_hash, duration, json_meta, existing[0]),
                    )
                    logger.info(f"Reused existing media {existing[0]}: {normalized_path}")
                    return existing[0]

                cursor.execute(
                    """
                    INSERT INTO media (project_id, file_path, file_hash, duration_sec, metadata_json, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                    """,
                    (project_id, normalized_path, file_hash, duration, json_meta),
                )

                media_id = cursor.lastrowid
                logger.info(f"Added media {media_id}: {normalized_path}")
                return media_id

        except sqlite3.IntegrityError:
            existing = self.find_by_project_and_path(project_id, normalized_path)
            if existing:
                logger.info("Recovered canonical media after duplicate guard hit: %s", normalized_path)
                return existing["id"]
            logger.error("Duplicate guard fired but canonical media was not found: %s", normalized_path, exc_info=True)
            raise
        except sqlite3.OperationalError:
            # Bubble up unwrapped so @_retry_on_database_lock can apply
            # exponential backoff on transient lock contention. Non-lock
            # OperationalErrors are propagated by the decorator.
            raise
        except Exception as e:
            logger.error(f"Add Media failed: {e}", exc_info=True)
            raise RuntimeError(f"Media-Persistierung fehlgeschlagen: {e}") from e

    def get_by_project(self, project_id: int) -> List[Dict]:
        """Get all media files for a project."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE project_id = ? ORDER BY id DESC", (project_id,))
        rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, media_id: int) -> Optional[Dict]:
        """Get a single media file by ID."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE id = ?", (media_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row)

    def find_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Find media by file hash (duplicate detection)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return self._row_to_dict(row)

    @_retry_on_database_lock
    def update_status(self, media_id: int, status: str, ai_data: Dict = None):
        """Update media status and optionally AI analysis data."""
        try:
            with self.db.transaction(immediate=True) as conn:
                if ai_data:
                    row = conn.execute(
                        "SELECT file_path FROM media WHERE id = ?",
                        (media_id,),
                    ).fetchone()
                    file_path = row[0] if row else ""
                    json_ai = json.dumps(
                        _migrate_ai_data_for_path(file_path, ai_data)
                    )
                    conn.execute(
                        "UPDATE media SET status = ?, ai_data_json = ? WHERE id = ?",
                        (status, json_ai, media_id)
                    )
                else:
                    conn.execute(
                        "UPDATE media SET status = ? WHERE id = ?",
                        (status, media_id)
                    )
                logger.debug(f"Updated media {media_id} status to {status}")

        except sqlite3.OperationalError:
            # Surface to the retry decorator without spurious error logs;
            # only persistent (post-retry) failures get logged as errors.
            raise
        except Exception as e:
            logger.error(f"Update Status failed for media {media_id}: {e}", exc_info=True)
            raise

    @_retry_on_database_lock
    def update_metadata(self, media_id: int, metadata: Dict):
        """Update technical metadata for a media file."""
        try:
            with self.db.transaction(immediate=True) as conn:
                row = conn.execute(
                    "SELECT file_path FROM media WHERE id = ?",
                    (media_id,),
                ).fetchone()
                file_path = row[0] if row else ""
                json_meta = _serialize_meta(
                    _migrate_metadata_for_path(file_path, metadata)
                )
                conn.execute(
                    "UPDATE media SET metadata_json = ? WHERE id = ?",
                    (json_meta, media_id)
                )
                logger.debug(f"Updated metadata for media {media_id}")

        except sqlite3.OperationalError:
            raise
        except Exception as e:
            logger.error(f"Update Metadata failed for media {media_id}: {e}", exc_info=True)
            raise

    @_retry_on_database_lock
    def delete_media(self, media_id: int):
        """Delete a media file from the database."""
        try:
            with self.db.transaction(immediate=True) as conn:
                # Foreign key cascade will delete related vector_map entries
                conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
                logger.info(f"Deleted media {media_id}")

        except sqlite3.OperationalError:
            raise
        except Exception as e:
            logger.error(f"Delete failed for media {media_id}: {e}", exc_info=True)
            raise

    def get_all_pending(self) -> List[Dict]:
        """Get all media files with 'pending' status."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE status = 'pending' ORDER BY id")
        rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    @_retry_on_database_lock
    def bulk_update_status(self, media_ids: List[int], status: str):
        """Update status for multiple media files in a single transaction."""
        if not media_ids:
            return
        try:
            with self.db.transaction(immediate=True) as conn:
                placeholders = ','.join('?' * len(media_ids))
                conn.execute(
                    f"UPDATE media SET status = ? WHERE id IN ({placeholders})",
                    [status] + media_ids
                )
                logger.info(f"Bulk updated {len(media_ids)} media to status {status}")

        except sqlite3.OperationalError:
            raise
        except Exception as e:
            logger.error(f"Bulk update failed: {e}", exc_info=True)
            raise
