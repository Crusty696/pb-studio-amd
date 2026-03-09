"""
Render Router – Video-Rendering starten, Status abrufen, abbrechen.

Endpoints:
  POST /render/start      — Rendering starten (Background Task)
  GET  /render/status/{id} — Render-Fortschritt abrufen
  POST /render/cancel/{id} — Rendering abbrechen
"""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state
from ..config import config
from ..dependencies import gpu_lock, publish_event
from ..schemas.common import validate_timeline
from ..schemas.render_schemas import (
    RenderRequest, RenderProgress, RenderResult,
    RenderQuality, RenderEncoder,
)
from ..schemas.common import TaskStatus

logger = logging.getLogger(__name__)
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
    task_id = str(uuid.uuid4())[:8]

    # SEC-002: Path-Traversal-Schutz für output_path
    output_p_check = Path(request.output_path).resolve()
    allowed_render = Path(config.project_dir).resolve()
    if not output_p_check.is_relative_to(allowed_render):
        raise HTTPException(status_code=403, detail="Output-Pfad außerhalb des erlaubten Verzeichnisses")

    # Render-Task Cleanup: alte abgeschlossene Tasks entfernen (max 50)
    _cleanup_old_render_tasks(state)

    task_data = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "percent": 0.0,
        "current_frame": 0,
        "total_frames": 0,
        "fps": 0.0,
        "elapsed_seconds": 0.0,
        "eta_seconds": 0.0,
        "output_path": request.output_path,
        "error": None,
    }
    state.set_render_task(task_id, task_data)
    state.set_cancel_flag(task_id, False)

    asyncio.create_task(_run_render_task(task_id, request, state))

    logger.info(f"Render-Task gestartet: {task_id}")
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

    state.set_cancel_flag(task_id, True)
    logger.info(f"Render-Task Cancel angefordert: {task_id}")
    return {"cancelled": True, "task_id": task_id}


async def _run_render_task(task_id: str, request: RenderRequest, state: AppState) -> None:
    """Background-Task für Rendering mit Cancel-Support."""
    state.update_render_task(task_id, {"status": TaskStatus.RUNNING.value})
    start_time = time.monotonic()

    # Timeline-Snapshot aus AppState (thread-safe)
    timeline_snapshot = state.get_timeline_snapshot()

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
                state.render_tasks,
                state.cancel_flags,
                timeline_snapshot,
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

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 100.0,
            "status": "completed",
            "message": "Rendering abgeschlossen",
        })

        logger.info(f"Render {task_id} abgeschlossen: {elapsed:.1f}s")

    except _RenderCancelled:
        elapsed = time.monotonic() - start_time
        state.update_render_task(task_id, {
            "status": TaskStatus.CANCELLED.value,
            "elapsed_seconds": round(elapsed, 1),
        })
        # Temp-Files aufräumen
        _cleanup_render_temps(request.output_path)
        logger.info(f"Render {task_id} abgebrochen nach {elapsed:.1f}s")

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 0.0,
            "status": "cancelled",
            "message": "Rendering abgebrochen",
        })

    except Exception as e:
        elapsed = time.monotonic() - start_time
        state.update_render_task(task_id, {
            "status": TaskStatus.FAILED.value,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 1),
        })
        logger.error(f"Render {task_id} fehlgeschlagen: {e}", exc_info=True)

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 0.0,
            "status": "failed",
            "message": str(e),
        })


class _RenderCancelled(Exception):
    """Interne Exception für abgebrochenes Rendering."""
    pass


def _cleanup_render_temps(output_path: str) -> None:
    """Räumt temporäre Render-Dateien auf."""
    try:
        output_p = Path(output_path)
        # Unvollständige Output-Datei löschen
        if output_p.exists():
            output_p.unlink(missing_ok=True)
        # Temp-Dir aufräumen
        temp_dir = output_p.parent / ".temp_render"
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Cleanup nach Cancel fehlgeschlagen: {e}")


def _execute_render(
    task_id: str,
    request: RenderRequest,
    render_tasks: dict[str, dict[str, Any]],
    cancel_flags: dict[str, bool],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    """Führt das Rendering durch (blockierend, GPU).

    Erhält render_tasks, cancel_flags und timeline als Parameter.
    Prüft periodisch cancel_flags[task_id] und bricht bei Cancel ab.
    """
    from pathlib import Path as _Path
    from pb_studio.rendering.render_service import RenderService, RenderCancelledError

    # BUG-025 Fix: Schema-Felder nutzen statt hardcodierter quality_map
    target_width = request.resolution_width
    target_height = request.resolution_height
    bitrate = f"{request.bitrate_mbps:.0f}M"
    audio_path = request.audio_path

    output_p = _Path(request.output_path)
    service = RenderService(output_dir=str(output_p.parent))

    def is_cancelled() -> bool:
        return cancel_flags.get(task_id, False)

    def on_progress(message: str, percent: float) -> None:
        # Cancel-Check bei jedem Progress-Callback
        if is_cancelled():
            raise _RenderCancelled()
        render_tasks[task_id].update({
            "percent": percent,
            "fps": 0.0,
        })

    if not timeline:
        raise RuntimeError("Keine Timeline für Rendering vorhanden")

    # Timeline validieren
    warnings = validate_timeline(timeline)
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
        return service.render_timeline(
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
    except RenderCancelledError as exc:
        raise _RenderCancelled() from exc
