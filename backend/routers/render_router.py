"""
Render Router – Video-Rendering starten, Status abrufen, abbrechen.

Endpoints:
  POST /render/start      — Rendering starten (Background Task)
  GET  /render/status/{id} — Render-Fortschritt abrufen
  POST /render/cancel/{id} — Rendering abbrechen
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state, resolve_active_project_root
from ..config import config
from ..dependencies import gpu_lock, publish_event, publish_log
from ..schemas.common import validate_timeline
from ..schemas.render_schemas import (
    RenderRequest, RenderProgress,
)
from ..schemas.common import TaskStatus

# Aufgabe I: Render-Queue-Persistenz — minimal-invasive Anbindung.
# Der in-memory render_tasks-State bleibt Source-of-Truth für Live-Progress;
# zusätzlich spiegeln wir die Lifecycle-Übergänge (queued → running → terminal)
# in die persistente RenderQueue, damit Jobs einen Backend-Crash überleben.
from pb_studio.rendering.render_queue import (
    STATE_QUEUED as _RQ_QUEUED,
    STATE_RUNNING as _RQ_RUNNING,
    STATE_COMPLETED as _RQ_COMPLETED,
    STATE_FAILED as _RQ_FAILED,
    get_render_queue as _get_render_queue,
)

logger = logging.getLogger(__name__)


def _compute_render_media_hash(audio_path: str, timeline: list[dict[str, Any]]) -> str:
    """Stabiler Identitäts-Hash über die Render-Eingaben.

    Zweck: Grundlage für die Idempotency der RenderQueue. Zwei /render/start
    Requests mit demselben Audio + identischer Timeline + identischem Output
    erzeugen denselben job_hash und daher nur einen einzigen Queue-Eintrag.
    """
    try:
        canonical = json.dumps(
            {
                "audio_path": str(audio_path or ""),
                "timeline": timeline or [],
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        canonical = f"audio={audio_path};timeline_len={len(timeline or [])}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _request_settings_dict(request: RenderRequest) -> dict[str, Any]:
    """Render-Settings als reines Dict für die Queue-Persistenz."""
    return {
        "resolution_width": request.resolution_width,
        "resolution_height": request.resolution_height,
        "fps": request.fps,
        "bitrate_mbps": request.bitrate_mbps,
        "encoder": request.encoder.value if request.encoder is not None else None,
        "include_audio": request.include_audio,
        "quality": request.quality.value if request.quality is not None else None,
    }


def _safe_queue_update(queue_job_id: Optional[str], status: str, **kwargs: Any) -> None:
    """Update der persistenten Queue, das niemals den Render-Task crasht."""
    if not queue_job_id:
        return
    try:
        _get_render_queue().update_status(queue_job_id, status, **kwargs)
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning(
            "RenderQueue.update_status fehlgeschlagen für %s (%s): %s",
            queue_job_id, status, exc,
        )
router = APIRouter(prefix="/render", tags=["Render"])


@router.post(
    "/start",
    response_model=RenderProgress,
    summary="Rendering starten",
    description=(
        "Startet das Rendering der aktuellen Timeline als Background Task. "
        "Gibt sofort eine task_id zurück — Fortschritt via GET /render/status/{task_id} "
        "oder via SSE /events/progress abrufbar. "
        "Benötigt eine vorhandene Timeline via POST /pacing/generate."
    ),
)
async def start_render(
    request: RenderRequest,
    state: AppState = Depends(get_app_state),
) -> RenderProgress:
    """Startet ein Rendering als Background Task."""
    while True:
        task_id = str(uuid.uuid4())[:8]
        if state.get_render_task(task_id) is None:
            break

    # Contract-Guard: Render darf nur mit vorhandener Timeline starten.
    timeline_snapshot = state.get_timeline_snapshot()
    if not timeline_snapshot:
        raise HTTPException(status_code=400, detail="Keine Timeline für Rendering vorhanden")

    # SEC-002: Path-Traversal-Schutz für output_path
    output_p_check = Path(request.output_path).resolve()
    allowed_render = resolve_active_project_root(state, config.project_dir)
    if not output_p_check.is_relative_to(allowed_render):
        raise HTTPException(status_code=403, detail="Output-Pfad außerhalb des erlaubten Verzeichnisses")

    # Render-Task Cleanup: alte abgeschlossene Tasks entfernen (max 50)
    _cleanup_old_render_tasks(state)

    timeline_total_seconds = 0.0
    for entry in timeline_snapshot:
        try:
            timeline_total_seconds += max(float(entry.get("end_time", 0.0)) - float(entry.get("start_time", 0.0)), 0.0)
        except (TypeError, ValueError):
            continue
    estimated_total_seconds = max(timeline_total_seconds, 0.0)
    estimated_total_frames = max(int(round(estimated_total_seconds * max(request.fps, 0.0))), 0)

    # Aufgabe I: Job in der persistenten Queue idempotent registrieren.
    # Bei Crash bleibt der Eintrag erhalten; Resume-on-Startup im Lifespan
    # überführt 'running' → 'interrupted'. Fehler hier werden nicht hochgereicht
    # (in-memory Render-Lifecycle ist die Source-of-Truth für die HTTP-Antwort).
    queue_job_id: Optional[str] = None
    try:
        media_hash = _compute_render_media_hash(request.audio_path, timeline_snapshot)
        queue_job = _get_render_queue().enqueue(
            media_hash=media_hash,
            output_path=request.output_path,
            settings=_request_settings_dict(request),
        )
        queue_job_id = queue_job.job_id
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning("RenderQueue.enqueue fehlgeschlagen (unkritisch): %s", exc)

    task_data = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "percent": 0.0,
        "current_frame": 0,
        "total_frames": estimated_total_frames,
        "fps": 0.0,
        "elapsed_seconds": 0.0,
        "eta_seconds": 0.0,
        "output_path": request.output_path,
        "error": None,
        "queue_job_id": queue_job_id,
    }
    state.set_render_task(task_id, task_data)
    state.set_cancel_flag(task_id, False)

    # R14/HIGH-004: Snapshot beim Start übergeben — _run_render_task darf den State nicht
    # erneut lesen, damit kein Stale-Timeline-Race zwischen start_render und Task-Ausführung entsteht.
    task = asyncio.create_task(_run_render_task(task_id, request, state, timeline_snapshot))

    def _on_task_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(f"Render-Task {task_id} unerwartete Exception: {exc}", exc_info=exc)
            try:
                state.update_render_task(task_id, {
                    "status": "failed",
                    "error": str(exc),
                })
            except Exception:
                pass
            # Auch in der persistenten Queue als failed markieren.
            _safe_queue_update(queue_job_id, _RQ_FAILED, error=str(exc))

    task.add_done_callback(_on_task_done)

    logger.info(f"Render-Task gestartet: {task_id}")
    await publish_log(
        f"Render gestartet: {task_id}",
        level="info",
        source="render.start",
        detail=f"output={request.output_path}",
    )
    return RenderProgress(**task_data)


@router.get(
    "/status/{task_id}",
    response_model=RenderProgress,
    summary="Render-Fortschritt abrufen",
    description=(
        "Gibt den aktuellen Status und Fortschritt eines Render-Tasks zurück. "
        "Status: pending → running → completed | failed | cancelled."
    ),
)
async def render_status(
    task_id: str,
    state: AppState = Depends(get_app_state),
) -> RenderProgress:
    """Gibt den aktuellen Render-Fortschritt zurück."""
    task = state.get_render_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Render-Task {task_id} nicht gefunden")
    return RenderProgress(**task)


def _cleanup_old_render_tasks(state: AppState, max_tasks: int = 50) -> None:
    """Entfernt abgeschlossene Render-Tasks wenn mehr als max_tasks vorhanden."""
    with state._state_lock:
        if len(state.render_tasks) <= max_tasks:
            return
        # Sortiere nach Status: completed/failed/cancelled zuerst entfernen
        terminal_statuses = {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}
        removable = [
            tid for tid, t in state.render_tasks.items()
            if t.get("status") in terminal_statuses
        ]
        # Älteste zuerst entfernen (bis max_tasks erreicht)
        to_remove = len(state.render_tasks) - max_tasks
        for tid in removable[:to_remove]:
            del state.render_tasks[tid]
            state.cancel_flags.pop(tid, None)
        if to_remove > 0:
            logger.info(f"Render-Task Cleanup: {min(to_remove, len(removable))} alte Tasks entfernt")


@router.post(
    "/cancel/{task_id}",
    summary="Rendering abbrechen",
    description=(
        "Setzt das Cancel-Flag für einen laufenden Render-Task. "
        "Das tatsächliche Abbrechen erfolgt beim nächsten Frame-Check im Render-Thread."
    ),
)
async def cancel_render(
    task_id: str,
    state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    """Bricht ein laufendes Rendering ab."""
    task = state.get_render_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Render-Task {task_id} nicht gefunden")

    terminal_statuses = {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}
    if task.get("status") in terminal_statuses:
        return {"cancelled": False, "task_id": task_id, "status": task.get("status")}

    state.set_cancel_flag(task_id, True)
    logger.info(f"Render-Task Cancel angefordert: {task_id}")
    return {"cancelled": True, "task_id": task_id}


async def _run_render_task(
    task_id: str,
    request: RenderRequest,
    state: AppState,
    timeline_snapshot: list[dict[str, Any]],
) -> None:
    """Background-Task für Rendering mit Cancel-Support.

    timeline_snapshot wird von start_render übergeben — wird hier NICHT erneut aus dem
    State gelesen (R14/HIGH-004: Race zwischen Snapshot-Check und Task-Start vermeiden).
    """
    state.update_render_task(task_id, {"status": TaskStatus.RUNNING.value})
    # Persistente Queue parallel auf 'running' setzen (Aufgabe I).
    _task_meta = state.get_render_task(task_id) or {}
    queue_job_id: Optional[str] = _task_meta.get("queue_job_id")
    _safe_queue_update(queue_job_id, _RQ_RUNNING)
    start_time = time.monotonic()

    # Record the output file's mtime BEFORE the render starts.
    # _cleanup_render_temps will only delete it if it was modified DURING this render
    # — protecting any previously completed output file at the same path.
    _output_p = Path(request.output_path)
    _output_mtime_before: float | None = _output_p.stat().st_mtime if _output_p.exists() else None

    try:
        async with gpu_lock:
            logger.info(f"GPU-Lock erworben für Render {task_id}")

            # Cancel-Check vor Start
            if state.get_cancel_flag(task_id):
                raise _RenderCancelled()

            result = await asyncio.to_thread(
                _execute_render,
                task_id,
                request,
                state,
                timeline_snapshot,
                asyncio.get_running_loop(),
            )

        # Finaler Cancel-Check
        if state.get_cancel_flag(task_id):
            raise _RenderCancelled()

        elapsed = time.monotonic() - start_time
        state.update_render_task(task_id, {
            "status": TaskStatus.COMPLETED.value,
            "percent": 100.0,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
        })
        _safe_queue_update(queue_job_id, _RQ_COMPLETED)

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 100.0,
            "status": "completed",
            "message": "Rendering abgeschlossen",
        })
        await publish_log(
            f"Render abgeschlossen: {task_id}",
            level="info",
            source="render.run",
            detail=f"elapsed={elapsed:.1f}s output={request.output_path}",
        )

        logger.info(f"Render {task_id} abgeschlossen: {elapsed:.1f}s")

    except _RenderCancelled:
        elapsed = time.monotonic() - start_time
        state.update_render_task(task_id, {
            "status": TaskStatus.CANCELLED.value,
            "elapsed_seconds": round(elapsed, 1),
        })
        # Cancelled wird in der persistenten Queue als 'failed' mit Cancel-Hinweis markiert.
        # (Die RenderQueue-Schemata wären strenger; failed deckt 'nicht erfolgreich abgeschlossen'
        #  korrekt ab und blockiert Auto-Retry — exakt was wir bei einem User-Cancel wollen.)
        _safe_queue_update(queue_job_id, _RQ_FAILED, error="cancelled")
        # Temp-Files aufräumen (schützt vorherige Outputs durch mtime-Check)
        _cleanup_render_temps(request.output_path, _output_mtime_before)
        logger.info(f"Render {task_id} abgebrochen nach {elapsed:.1f}s")

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 0.0,
            "status": "cancelled",
            "message": "Rendering abgebrochen",
        })
        await publish_log(
            f"Render abgebrochen: {task_id}",
            level="warning",
            source="render.run",
            detail=f"elapsed={elapsed:.1f}s",
        )

    except Exception as e:
        elapsed = time.monotonic() - start_time
        _cleanup_render_temps(request.output_path, _output_mtime_before)
        state.update_render_task(task_id, {
            "status": TaskStatus.FAILED.value,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
        })
        _safe_queue_update(queue_job_id, _RQ_FAILED, error=str(e))
        logger.error(f"Render {task_id} fehlgeschlagen: {e}", exc_info=True)

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 0.0,
            "status": "failed",
            "message": str(e),
        })
        await publish_log(
            f"Render fehlgeschlagen: {task_id}",
            level="error",
            source="render.run",
            detail=str(e),
        )


class _RenderCancelled(Exception):
    """Interne Exception für abgebrochenes Rendering."""
    pass


def _cleanup_render_temps(
    output_path: str,
    output_mtime_before: "float | None" = None,
) -> None:
    """Räumt temporäre Render-Dateien auf.

    Args:
        output_path:         Pfad zur Output-Datei.
        output_mtime_before: Mtime der Output-Datei VOR dem Render-Start (None = Datei
                             existierte vorher nicht).  Die Output-Datei wird NUR gelöscht,
                             wenn sie NACH dem Render-Start geschrieben wurde — d.h.
                             eine vorherige erfolgreiche Render-Ausgabe an demselben Pfad
                             bleibt erhalten.
    """
    try:
        output_p = Path(output_path)
        if output_p.exists():
            current_mtime = output_p.stat().st_mtime
            # Delete only if the file was created or modified during this render task
            if output_mtime_before is None or current_mtime > output_mtime_before:
                output_p.unlink(missing_ok=True)
                logger.debug(f"Unvollständige Render-Ausgabe gelöscht: {output_p.name}")
            else:
                logger.debug(f"Vorherige Render-Ausgabe beibehalten (nicht von diesem Task): {output_p.name}")
        # Temp-Dir immer aufräumen
        temp_dir = output_p.parent / ".temp_render"
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Cleanup nach Cancel fehlgeschlagen: {e}")


def _execute_render(
    task_id: str,
    request: RenderRequest,
    state: "AppState",
    timeline: list[dict[str, Any]],
    event_loop: asyncio.AbstractEventLoop,
) -> dict[str, Any]:
    """Führt das Rendering durch (blockierend, GPU).

    Verwendet state.update_render_task() und state.get_cancel_flag() für
    thread-sichere Dict-Zugriffe statt direkter Mutation.
    """
    from pathlib import Path as _Path
    from pb_studio.rendering.render_service import RenderService, RenderCancelledError

    # BUG-025 Fix: Schema-Felder nutzen statt hardcodierter quality_map
    target_width = request.resolution_width
    target_height = request.resolution_height
    bitrate = f"{request.bitrate_mbps:.0f}M"
    audio_path = request.audio_path

    output_p = _Path(request.output_path)
    # R01/FIX-4: Encoder-Override als Konstruktor-Parameter übergeben (kein GlobalSeiteneffekt)
    encoder_override = request.encoder.value if request.encoder is not None else None
    service = RenderService(output_dir=str(output_p.parent), encoder_override=encoder_override)
    if encoder_override is not None:
        logger.info(f"Render {task_id}: Encoder-Override via Request: {encoder_override}")

    progress_publish_lock = threading.Lock()
    progress_state = {"percent": -1.0, "message": "", "at": 0.0}

    def is_cancelled() -> bool:
        return state.get_cancel_flag(task_id)

    def publish_progress_event(message: str, percent: float) -> None:
        task_snapshot = state.get_render_task(task_id) or {}
        payload = {
            "task_id": task_id,
            "percent": round(percent, 1),
            "status": task_snapshot.get("status", TaskStatus.RUNNING.value),
            "message": message,
            "output_path": str(output_p),
            "current_frame": task_snapshot.get("current_frame", 0),
            "total_frames": task_snapshot.get("total_frames", 0),
            "fps": task_snapshot.get("fps", 0.0),
            "elapsed_seconds": task_snapshot.get("elapsed_seconds", 0.0),
            "eta_seconds": task_snapshot.get("eta_seconds", 0.0),
        }
        future = asyncio.run_coroutine_threadsafe(
            publish_event("render_progress", payload),
            event_loop,
        )

        def _log_publish_failure(done: Any) -> None:
            try:
                error = done.exception()
            except Exception as exc:
                logger.debug("Render progress future inspection failed: %s", exc)
                return
            if error:
                logger.debug("Render progress publish failed for %s: %s", task_id, error)

        future.add_done_callback(_log_publish_failure)

    def on_progress(message: str, percent: float, telemetry: Optional[dict[str, Any]] = None) -> None:
        # Cancel-Check bei jedem Progress-Callback
        if is_cancelled():
            raise _RenderCancelled()

        percent = round(float(percent), 1)
        telemetry = telemetry or {}
        updates = {
            "status": TaskStatus.RUNNING.value,
            "percent": percent,
            "fps": round(float(telemetry.get("fps", 0.0) or 0.0), 2),
            "current_frame": max(int(telemetry.get("current_frame", 0) or 0), 0),
            "total_frames": max(int(telemetry.get("total_frames", 0) or 0), 0),
            "elapsed_seconds": round(float(telemetry.get("elapsed_seconds", 0.0) or 0.0), 1),
            "eta_seconds": round(float(telemetry.get("eta_seconds", 0.0) or 0.0), 1),
            "output_path": str(output_p),
        }
        state.update_render_task(task_id, updates)

        now = time.monotonic()
        with progress_publish_lock:
            last_percent = progress_state["percent"]
            last_message = progress_state["message"]
            last_at = progress_state["at"]
            should_publish = (
                percent >= 100.0
                or last_percent < 0.0
                or percent - last_percent >= 1.0
                or message != last_message
                or (now - last_at) >= 1.0
            )
            if should_publish:
                progress_state.update({"percent": percent, "message": message, "at": now})

        if should_publish:
            publish_progress_event(message, percent)

    if not timeline:
        raise RuntimeError("Keine Timeline für Rendering vorhanden")

    # Timeline validieren
    warnings, errors = validate_timeline(timeline)
    if errors:
        raise RuntimeError(f"Ungültige Timeline: {'; '.join(errors)}")
    for w in warnings:
        logger.warning(f"Render-Timeline Warnung: {w}")

    # Timeline-Einträge in Render-Service-Format konvertieren
    # Pacing: {clip_id, start_time, end_time, metadata: {file_path, clip_start, ...}}
    # Render: {file_path, in_point, out_point}
    render_timeline = []
    for entry in timeline:
        meta = entry.get("metadata", {})
        fp = meta.get("file_path") or entry.get("file_path") or entry.get("path", "")
        clip_start = meta.get("clip_start", 0.0)
        duration = entry.get("end_time", 0.0) - entry.get("start_time", 0.0)
        render_timeline.append({
            "file_path": fp,
            "in_point": clip_start,
            "out_point": clip_start + duration,
            "clip_name": meta.get("clip_name", ""),
            "trigger_type": meta.get("trigger_type", ""),
        })
    timeline = render_timeline

    try:
        result_path = service.render_timeline(
            timeline=timeline,
            audio_path=audio_path,
            output_filename=output_p.name,
            target_width=target_width,
            target_height=target_height,
            target_fps=request.fps,   # BUG-006 Fix: fps aus Request übergeben
            bitrate=bitrate,
            progress_callback=on_progress,
            cancel_callback=is_cancelled,
        )
        # Realtest-Härtung: Status direkt im synchronen Worker auf completed setzen,
        # damit /render/status nicht auf "running" hängen bleibt, falls der Async-
        # Wrapper den finalen State erst verzögert nachzieht.
        state.update_render_task(task_id, {
            "status": TaskStatus.COMPLETED.value,
            "percent": 100.0,
            "eta_seconds": 0.0,
            "output_path": str(output_p),
            "error": None,
        })
        return {"output_path": result_path}
    except RenderCancelledError as exc:
        raise _RenderCancelled() from exc
