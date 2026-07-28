"""Crash-consistent SQLite/FAISS delete operations.

SQLite and FAISS cannot share a transaction. This module records the intended
operation before changing either store, persists and verifies tombstones, then
applies the relational mutation. Every stage is safe to replay after a crash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from pb_studio.data.database_core import DatabaseCore

logger = logging.getLogger(__name__)

OUTBOX_SCHEMA_VERSION = 1
_OPERATION_LOCK = threading.RLock()


class VectorOperationOutbox:
    """Durable coordinator for media delete and vector dedupe operations."""

    def __init__(
        self,
        db: Optional[DatabaseCore] = None,
        vector_store_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self.db = db or DatabaseCore()
        self._vector_store_factory = vector_store_factory or self._default_vector_store

    @staticmethod
    def _default_vector_store():
        from pb_studio.data.vector_store import VectorStore

        return VectorStore(index_name="video_index")

    def delete_media(self, media_id: int) -> str:
        """Delete media and its vectors through a replayable operation."""
        with _OPERATION_LOCK:
            operation_id = self._prepare("media_delete", int(media_id))
            self._execute(operation_id)
            return operation_id

    def dedupe_media_vectors(self, media_id: int) -> Optional[str]:
        """Remove existing vector links without exposing active unmapped vectors."""
        with _OPERATION_LOCK:
            operation_id = self._prepare("vector_dedupe", int(media_id))
            operation = self._load(operation_id)
            if not operation["faiss_ids"]:
                self._set_stage(operation_id, "completed")
                return None
            self._execute(operation_id)
            return operation_id

    def recover_pending(self, project_id: Optional[int] = None) -> int:
        """Replay incomplete operations, optionally limited to one project."""
        with _OPERATION_LOCK:
            conn = self.db.get_connection()
            if project_id is None:
                rows = conn.execute(
                    """
                    SELECT operation_id
                    FROM vector_operation_outbox
                    WHERE stage <> 'completed'
                    ORDER BY created_at, operation_id
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT operation_id
                    FROM vector_operation_outbox
                    WHERE project_id = ? AND stage <> 'completed'
                    ORDER BY created_at, operation_id
                    """,
                    (int(project_id),),
                ).fetchall()

            recovered = 0
            for row in rows:
                self._execute(str(row[0]))
                recovered += 1
            return recovered

    def _prepare(self, operation_type: str, media_id: int) -> str:
        with self.db.transaction(immediate=True) as conn:
            media_row = conn.execute(
                "SELECT project_id FROM media WHERE id = ?",
                (media_id,),
            ).fetchone()
            project_id = int(media_row[0]) if media_row is not None else 0
            faiss_ids = sorted(
                int(row[0])
                for row in conn.execute(
                    "SELECT faiss_id FROM vector_map WHERE media_id = ? ORDER BY faiss_id",
                    (media_id,),
                ).fetchall()
            )
            operation_id = self._operation_id(operation_type, media_id, faiss_ids)
            payload = json.dumps(faiss_ids, separators=(",", ":"))
            conn.execute(
                """
                INSERT OR IGNORE INTO vector_operation_outbox (
                    operation_id, schema_version, operation_type, project_id,
                    media_id, faiss_ids_json, stage
                ) VALUES (?, ?, ?, ?, ?, ?, 'prepared')
                """,
                (
                    operation_id,
                    OUTBOX_SCHEMA_VERSION,
                    operation_type,
                    project_id,
                    media_id,
                    payload,
                ),
            )
        return operation_id

    def _execute(self, operation_id: str) -> None:
        operation = self._load(operation_id)
        if operation["stage"] == "completed":
            return

        try:
            self._persist_tombstones(operation["faiss_ids"])

            with self.db.transaction(immediate=True) as conn:
                if operation["operation_type"] == "media_delete":
                    conn.execute(
                        "DELETE FROM media WHERE id = ?",
                        (operation["media_id"],),
                    )
                else:
                    faiss_ids = operation["faiss_ids"]
                    if faiss_ids:
                        conn.executemany(
                            """
                            DELETE FROM vector_map
                            WHERE media_id = ? AND faiss_id = ?
                            """,
                            [
                                (operation["media_id"], faiss_id)
                                for faiss_id in faiss_ids
                            ],
                        )
                conn.execute(
                    """
                    UPDATE vector_operation_outbox
                    SET stage = 'relational_applied',
                        attempt_count = attempt_count + 1,
                        last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE operation_id = ?
                    """,
                    (operation_id,),
                )

            # A crash after SQLite commit but before FAISS publication is safe:
            # relational_applied stays pending until this verification succeeds.
            self._persist_tombstones(operation["faiss_ids"])
            self._set_stage(operation_id, "completed")
        except Exception as exc:
            self._record_failure(operation_id, exc)
            raise

    def _persist_tombstones(self, faiss_ids: list[int]) -> None:
        if not faiss_ids:
            return

        vector_store = self._vector_store_factory()
        with vector_store._lock:
            vector_store._ensure_open()
            tombstones = getattr(vector_store, "_tombstoned_ids", None)
            if tombstones is None:
                tombstones = set()
                vector_store._tombstoned_ids = tombstones
            tombstones.update(faiss_ids)
            vector_store._save_unlocked(force=True)

        tombstone_path = Path(vector_store.tombstone_path)
        try:
            persisted = {
                int(value)
                for value in json.loads(tombstone_path.read_text(encoding="utf-8"))
            }
        except Exception as exc:
            raise RuntimeError(
                f"FAISS tombstones konnten nicht verifiziert werden: {tombstone_path}"
            ) from exc
        missing = set(faiss_ids) - persisted
        if missing:
            raise RuntimeError(
                f"FAISS tombstones nicht dauerhaft gespeichert: {sorted(missing)}"
            )

    def _load(self, operation_id: str) -> dict:
        row = self.db.get_connection().execute(
            """
            SELECT operation_id, schema_version, operation_type, project_id,
                   media_id, faiss_ids_json, stage
            FROM vector_operation_outbox
            WHERE operation_id = ?
            """,
            (operation_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Vector-Outbox-Operation fehlt: {operation_id}")
        if int(row["schema_version"]) != OUTBOX_SCHEMA_VERSION:
            raise RuntimeError(
                f"Nicht unterstuetzte Vector-Outbox-Version: {row['schema_version']}"
            )
        faiss_ids = json.loads(row["faiss_ids_json"])
        if not isinstance(faiss_ids, list):
            raise RuntimeError("Ungueltige FAISS-ID-Liste in Vector-Outbox")
        return {
            "operation_id": str(row["operation_id"]),
            "operation_type": str(row["operation_type"]),
            "project_id": int(row["project_id"]),
            "media_id": int(row["media_id"]),
            "faiss_ids": [int(value) for value in faiss_ids],
            "stage": str(row["stage"]),
        }

    def _set_stage(self, operation_id: str, stage: str) -> None:
        with self.db.transaction(immediate=True) as conn:
            conn.execute(
                """
                UPDATE vector_operation_outbox
                SET stage = ?, last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE operation_id = ?
                """,
                (stage, operation_id),
            )

    def _record_failure(self, operation_id: str, exc: Exception) -> None:
        try:
            with self.db.transaction(immediate=True) as conn:
                conn.execute(
                    """
                    UPDATE vector_operation_outbox
                    SET attempt_count = attempt_count + 1,
                        last_error = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE operation_id = ?
                    """,
                    (str(exc)[:1000], operation_id),
                )
        except Exception:
            logger.error(
                "Vector-Outbox-Fehlerstatus konnte nicht gespeichert werden",
                exc_info=True,
            )

    @staticmethod
    def _operation_id(
        operation_type: str,
        media_id: int,
        faiss_ids: list[int],
    ) -> str:
        payload = json.dumps(
            {
                "version": OUTBOX_SCHEMA_VERSION,
                "type": operation_type,
                "media_id": media_id,
                "faiss_ids": faiss_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"vector-op-v{OUTBOX_SCHEMA_VERSION}-{digest}"
