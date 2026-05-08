import logging
import json
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
        return dict(row) if row else None

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
        json_meta = json.dumps(meta) if meta else "{}"

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
        return [dict(row) for row in rows]

    def get_by_id(self, media_id: int) -> Optional[Dict]:
        """Get a single media file by ID."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE id = ?", (media_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Find media by file hash (duplicate detection)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM media WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @_retry_on_database_lock
    def update_status(self, media_id: int, status: str, ai_data: Dict = None):
        """Update media status and optionally AI analysis data."""
        try:
            with self.db.transaction() as conn:
                if ai_data:
                    json_ai = json.dumps(ai_data)
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
            with self.db.transaction() as conn:
                json_meta = json.dumps(metadata)
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
            with self.db.transaction() as conn:
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
        return [dict(row) for row in rows]

    @_retry_on_database_lock
    def bulk_update_status(self, media_ids: List[int], status: str):
        """Update status for multiple media files in a single transaction."""
        try:
            with self.db.transaction() as conn:
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
