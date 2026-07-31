"""
Render-Queue mit SQLite-Persistenz.

Persistiert Render-Jobs in der vorhandenen `pb_studio.db` (DatabaseCore-Singleton),
sodass laufende Renders bei Backend-Crash nicht verloren gehen.

States:
    queued       — eingereiht, wartet auf Worker
    running      — wird gerade gerendert
    completed    — erfolgreich abgeschlossen
    failed       — abgebrochen mit Fehler
    cancelled    — vom Benutzer abgebrochen
    interrupted  — war beim Backend-Restart "running" und wurde re-queued

Resume on startup:
    `restore_running_as_interrupted()` setzt alle "running"-Zeilen auf
    "interrupted". Worker akzeptieren sowohl "queued" als auch "interrupted"
    als laufbereit — "interrupted" bleibt damit eine sichtbare Diagnose-Spur,
    blockiert aber den automatischen Retry nicht.

Idempotency:
    Aktive Attempts werden über `(media_hash, output_path, settings_hash)`
    dedupliziert. Nach `completed`/`failed`/`cancelled` erzeugt ein Retry eine
    neue job_id und einen neuen, weiterhin UNIQUE `job_hash`.

Iron Rules respected:
    R1 AMD only — kein GPU-spezifischer Code hier.
    R6 pathlib.Path — kein os.path / Windows-spezifisches String-Handling.
    R8 Tests/ Großbuchstabe — siehe pytest.ini.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"
STATE_INTERRUPTED = "interrupted"

VALID_STATES: frozenset[str] = frozenset({
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_CANCELLED,
    STATE_INTERRUPTED,
})

# "queued" und "interrupted" sind beide laufbereit — interrupted ist ein
# automatisch wiederbelebter Job nach Backend-Restart.
RESTARTABLE_STATES: frozenset[str] = frozenset({STATE_QUEUED, STATE_INTERRUPTED})
ACTIVE_STATES: frozenset[str] = frozenset({
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_INTERRUPTED,
})
TERMINAL_STATES: frozenset[str] = frozenset({
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_CANCELLED,
})


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS render_queue (
    job_id TEXT PRIMARY KEY,
    job_hash TEXT NOT NULL UNIQUE,
    media_hash TEXT NOT NULL,
    output_path TEXT NOT NULL,
    settings_hash TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress_percent REAL NOT NULL DEFAULT 0.0,
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL
)
"""

_INDEX_STATUS_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_render_queue_status ON render_queue(status)"
)
_INDEX_HASH_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_render_queue_hash ON render_queue(job_hash)"
)


# ---------------------------------------------------------------------------
# Hash-Berechnung
# ---------------------------------------------------------------------------

def _normalize_settings(settings: dict[str, Any]) -> str:
    """Reproduzierbare JSON-Repräsentation für settings_hash."""
    return json.dumps(settings or {}, sort_keys=True, separators=(",", ":"))


def compute_settings_hash(settings: dict[str, Any]) -> str:
    """sha256 über die normalisierten Settings."""
    payload = _normalize_settings(settings).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_job_hash(media_hash: str, output_path: str, settings_hash: str) -> str:
    """sha256 über (media_hash | output_path | settings_hash) — Idempotenz-Key."""
    output_norm = str(Path(output_path)).replace("\\", "/").casefold()
    payload = f"{media_hash}|{output_norm}|{settings_hash}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# RenderJob (Read-Model)
# ---------------------------------------------------------------------------

class RenderJob(dict):
    """Schmaler Wrapper über die SQLite-Row.

    Bewusst ein dict, damit publish_event/publish_log sie direkt serialisieren
    können und bestehende Router-Helfer wie `RenderProgress(**task_data)` weiter
    funktionieren. Verlust-tolerant für unbekannte Spalten.
    """

    @property
    def job_id(self) -> str:
        return self["job_id"]

    @property
    def status(self) -> str:
        return self["status"]

    @property
    def output_path(self) -> str:
        return self["output_path"]

    @property
    def settings(self) -> dict[str, Any]:
        raw = self.get("settings_json") or "{}"
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}


# ---------------------------------------------------------------------------
# RenderQueue
# ---------------------------------------------------------------------------

class RenderQueue:
    """Persistente Render-Job-Queue auf SQLite.

    Thread-safe für die typischen Operationen (`enqueue`, `update_status`,
    `restore_running_as_interrupted`). Nutzt `DatabaseCore.transaction(immediate=True)`
    für atomare Writes — die WAL+busy_timeout-Konfiguration aus DatabaseCore
    macht concurrent reads parallel zu writes sicher.

    Eigene `_lock`-Instanz dient nur dazu, doppelte Hash-Inserts aus demselben
    Prozess deterministisch zu serialisieren — der UNIQUE-Constraint fängt
    den Cross-Process-Fall trotzdem ab.
    """

    def __init__(self, db_core: Optional[Any] = None) -> None:
        from pb_studio.data.database_core import DatabaseCore

        self._db = db_core or DatabaseCore()
        self._lock = threading.RLock()
        self._ensure_schema()

    # -- Schema ---------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Idempotent: legt Tabelle + Indizes an, falls noch nicht vorhanden."""
        with self._db.transaction(immediate=True) as conn:
            conn.execute(_SCHEMA_SQL)
            conn.execute(_INDEX_STATUS_SQL)
            conn.execute(_INDEX_HASH_SQL)

    # -- Public API -----------------------------------------------------------

    def enqueue(
        self,
        media_hash: str,
        output_path: str,
        settings: dict[str, Any],
        *,
        job_id: Optional[str] = None,
    ) -> RenderJob:
        """Reiht einen Job ein.

        Idempotent nur für aktive Attempts: queued, interrupted oder running
        mit gleichem (media_hash, output_path, settings_hash) wird
        zurückgegeben. Nach einem terminalen Attempt entsteht eine neue job_id.

        Args:
            media_hash:   Hash des Quell-Audios/Timelines (Eindeutigkeit pro Input).
            output_path:  Ziel-Datei (relativ oder absolut, wird normalisiert).
            settings:     Render-Settings (resolution, bitrate, encoder, fps, ...).
            job_id:       Optional vorgegebene ID — sonst neue UUID.

        Returns:
            RenderJob mit dem persistierten Zustand.
        """
        if not media_hash:
            raise ValueError("media_hash darf nicht leer sein")
        if not output_path:
            raise ValueError("output_path darf nicht leer sein")

        settings_hash = compute_settings_hash(settings or {})
        request_hash = compute_job_hash(media_hash, output_path, settings_hash)
        settings_json = _normalize_settings(settings or {})

        with self._lock:
            new_job_id = job_id or str(uuid.uuid4())
            job_hash = hashlib.sha256(
                f"{request_hash}|attempt|{new_job_id}".encode("utf-8")
            ).hexdigest()
            now = time.time()

            # BEGIN IMMEDIATE serialisiert Active-Check und INSERT auch
            # prozessübergreifend, ohne Schemaänderung oder Partial-Index.
            with self._db.transaction(immediate=True) as conn:
                existing = self._find_active_by_identity(
                    conn,
                    media_hash,
                    output_path,
                    settings_hash,
                )
                if existing is not None:
                    logger.debug(
                        "RenderQueue.enqueue: active job %s for request %s..., "
                        "status=%s",
                        existing.job_id,
                        request_hash[:12],
                        existing.status,
                    )
                    return existing
                conn.execute(
                    """
                    INSERT INTO render_queue (
                        job_id, job_hash, media_hash,
                        output_path, settings_hash, settings_json,
                        status, progress_percent,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_job_id, job_hash, media_hash,
                        str(output_path), settings_hash, settings_json,
                        STATE_QUEUED, 0.0,
                        now, now,
                    ),
                )

            logger.info(
                "RenderQueue.enqueue: %s queued (hash=%s..., output=%s)",
                new_job_id, job_hash[:12], Path(output_path).name,
            )

            stored = self.get(new_job_id)
            assert stored is not None, "INSERT erfolgreich aber row nicht abrufbar"
            return stored

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        progress_percent: Optional[float] = None,
        error: Optional[str] = None,
    ) -> Optional[RenderJob]:
        """Setzt Status + optional Fortschritt/Fehler."""
        if status not in VALID_STATES:
            raise ValueError(f"Ungültiger Status: {status!r} (erlaubt: {sorted(VALID_STATES)})")

        now = time.time()
        sets: list[str] = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, now]

        if progress_percent is not None:
            sets.append("progress_percent = ?")
            params.append(float(progress_percent))

        if error is not None:
            sets.append("error = ?")
            params.append(str(error))

        if status == STATE_RUNNING:
            sets.append("started_at = COALESCE(started_at, ?)")
            params.append(now)
        elif status in TERMINAL_STATES:
            sets.append("finished_at = ?")
            params.append(now)
            if status == STATE_COMPLETED:
                sets.append("progress_percent = ?")
                params.append(100.0)

        params.append(job_id)
        sql = f"UPDATE render_queue SET {', '.join(sets)} WHERE job_id = ?"

        with self._db.transaction(immediate=True) as conn:
            cur = conn.execute(sql, params)
            if cur.rowcount == 0:
                logger.warning("RenderQueue.update_status: job_id %s nicht gefunden", job_id)
                return None

        return self.get(job_id)

    def get(self, job_id: str) -> Optional[RenderJob]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM render_queue WHERE job_id = ?", (job_id,),
        ).fetchone()
        return self._row_to_job(row)

    def list_jobs(self, *, status: Optional[str] = None) -> list[RenderJob]:
        """Alle Jobs (optional nach Status gefiltert), sortiert nach created_at."""
        conn = self._db.get_connection()
        if status is not None:
            if status not in VALID_STATES:
                raise ValueError(f"Ungültiger Status-Filter: {status!r}")
            rows = conn.execute(
                "SELECT * FROM render_queue WHERE status = ? ORDER BY created_at ASC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM render_queue ORDER BY created_at ASC",
            ).fetchall()
        return [self._row_to_job(r) for r in rows if r is not None]

    def list_pending(self) -> list[RenderJob]:
        """Alle laufbereit-Jobs (queued ∪ interrupted), älteste zuerst."""
        conn = self._db.get_connection()
        rows = conn.execute(
            """
            SELECT * FROM render_queue
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            """,
            (STATE_QUEUED, STATE_INTERRUPTED),
        ).fetchall()
        return [self._row_to_job(r) for r in rows if r is not None]

    def restore_running_as_interrupted(self) -> list[str]:
        """Resume on startup: alle "running"-Zeilen → "interrupted" requeuen.

        Returns:
            Liste der job_ids, die umgesetzt wurden.

        Begründung Requeue statt nur markieren:
          1. Backend-Crash bedeutet, der gestartete FFmpeg/Render-Subprozess
             wurde mit dem Parent beendet — die Output-Datei ist nie konsistent.
          2. "Nur markieren" würde User mit dauerhaft 'running'/eingefrorenem
             Status sitzen lassen; Requeue gibt automatisch eine zweite Chance,
             ohne manuelle Aktion.
        """
        now = time.time()
        with self._db.transaction(immediate=True) as conn:
            # Erst die IDs einsammeln (für Logging/Return).
            rows = conn.execute(
                "SELECT job_id FROM render_queue WHERE status = ?",
                (STATE_RUNNING,),
            ).fetchall()
            job_ids = [r["job_id"] for r in rows]
            if not job_ids:
                return []

            conn.execute(
                """
                UPDATE render_queue
                SET status = ?,
                    updated_at = ?,
                    error = COALESCE(error, ?)
                WHERE status = ?
                """,
                (STATE_INTERRUPTED, now, "Backend-Restart während running", STATE_RUNNING),
            )

        logger.info(
            "RenderQueue.restore: %d Job(s) running → interrupted requeued: %s",
            len(job_ids), job_ids,
        )
        return job_ids

    def remove(self, job_id: str) -> bool:
        """Entfernt einen Job (nur für Cleanup / Tests gedacht)."""
        with self._db.transaction(immediate=True) as conn:
            cur = conn.execute(
                "DELETE FROM render_queue WHERE job_id = ?", (job_id,),
            )
            return cur.rowcount > 0

    def clear(self) -> int:
        """Entfernt ALLE Jobs (nur Tests / explizites Reset)."""
        with self._db.transaction(immediate=True) as conn:
            cur = conn.execute("DELETE FROM render_queue")
            return cur.rowcount

    def find_by_hash(
        self,
        media_hash: str,
        output_path: str,
        settings: dict[str, Any],
    ) -> Optional[RenderJob]:
        """Lookup über die Idempotenz-Komponenten."""
        settings_hash = compute_settings_hash(settings or {})
        conn = self._db.get_connection()
        active = self._find_active_by_identity(
            conn,
            media_hash,
            output_path,
            settings_hash,
        )
        if active is not None:
            return active
        request_hash = compute_job_hash(media_hash, output_path, settings_hash)
        rows = conn.execute(
            """
            SELECT * FROM render_queue
            WHERE media_hash = ? AND settings_hash = ?
            ORDER BY created_at DESC
            """,
            (media_hash, settings_hash),
        ).fetchall()
        for row in rows:
            row_request_hash = compute_job_hash(
                row["media_hash"],
                row["output_path"],
                row["settings_hash"],
            )
            if row_request_hash == request_hash:
                return self._row_to_job(row)
        return None

    # -- Internals ------------------------------------------------------------

    def _find_active_by_identity(
        self,
        conn: Any,
        media_hash: str,
        output_path: str,
        settings_hash: str,
    ) -> Optional[RenderJob]:
        request_hash = compute_job_hash(media_hash, output_path, settings_hash)
        rows = conn.execute(
            """
            SELECT * FROM render_queue
            WHERE media_hash = ?
              AND settings_hash = ?
              AND status IN (?, ?, ?)
            ORDER BY created_at ASC
            """,
            (
                media_hash,
                settings_hash,
                STATE_QUEUED,
                STATE_RUNNING,
                STATE_INTERRUPTED,
            ),
        ).fetchall()
        for row in rows:
            row_request_hash = compute_job_hash(
                row["media_hash"],
                row["output_path"],
                row["settings_hash"],
            )
            if row_request_hash == request_hash:
                return self._row_to_job(row)
        return None

    def _find_by_hash(self, job_hash: str) -> Optional[RenderJob]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM render_queue WHERE job_hash = ?", (job_hash,),
        ).fetchone()
        return self._row_to_job(row)

    @staticmethod
    def _row_to_job(row: Any) -> Optional[RenderJob]:
        if row is None:
            return None
        return RenderJob({
            "job_id": row["job_id"],
            "job_hash": row["job_hash"],
            "media_hash": row["media_hash"],
            "output_path": row["output_path"],
            "settings_hash": row["settings_hash"],
            "settings_json": row["settings_json"],
            "status": row["status"],
            "progress_percent": row["progress_percent"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        })


# ---------------------------------------------------------------------------
# Modul-Singleton (Lazy)
# ---------------------------------------------------------------------------

_queue_singleton: Optional[RenderQueue] = None
_queue_singleton_lock = threading.Lock()


def get_render_queue() -> RenderQueue:
    """Gibt die prozessweite RenderQueue zurück (lazy init).

    Die Queue lebt parallel zum DatabaseCore-Singleton — bei Tests werden
    beide via isolated_test_database-Fixture zurückgesetzt; reset_for_tests()
    kümmert sich um die RenderQueue-Seite.
    """
    global _queue_singleton
    if _queue_singleton is None:
        with _queue_singleton_lock:
            if _queue_singleton is None:
                _queue_singleton = RenderQueue()
    return _queue_singleton


def reset_for_tests() -> None:
    """Setzt das Modul-Singleton zurück.

    Nötig, damit nach DatabaseCore.shutdown() (durch isolated_test_database)
    eine frische Queue gegen die neue Test-DB instanziert wird.
    """
    global _queue_singleton
    with _queue_singleton_lock:
        _queue_singleton = None
