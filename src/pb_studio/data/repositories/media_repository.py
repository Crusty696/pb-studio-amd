import logging
import json
import sqlite3
from typing import List, Optional, Dict

from pb_studio.data.database_core import DatabaseCore, normalize_media_path

logger = logging.getLogger(__name__)

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

    def add_media(self, project_id: int, file_path: str, file_hash: str, duration: float, meta: Dict = None) -> int:
        """Add a media file to the database with idempotent project+path semantics."""
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
                
        except Exception as e:
            logger.error(f"Update Status failed for media {media_id}: {e}", exc_info=True)
            raise

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
                
        except Exception as e:
            logger.error(f"Update Metadata failed for media {media_id}: {e}", exc_info=True)
            raise

    def delete_media(self, media_id: int):
        """Delete a media file from the database."""
        try:
            with self.db.transaction() as conn:
                # Foreign key cascade will delete related vector_map entries
                conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
                logger.info(f"Deleted media {media_id}")
                
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
                
        except Exception as e:
            logger.error(f"Bulk update failed: {e}", exc_info=True)
            raise
