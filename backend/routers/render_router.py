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
    STATE_INTERRUPTED as _RQ_INTERRUPTED,
    get_render_queue as _get_render_queue,
)

logger = logging.getLogger(__name__)

_QUALITY_PRESETS = {
    "preview": "speed",
    "standard": "balanced",
    "high": "quality",
    "ultra": "quality",
}

_render_runtime_tasks: dict[str, asyncio.Task[None]] = {}
_shutdown_cancelled_task_ids: set[str] = set()
_render_shutdown_requested = False


def _reset_render_runtime_for_startup() -> None:
    """Setzt den pro Prozess-Lifespan geltenden Shutdown-Zustand zurück."""
    global _render_shutdown_requested
    _render_shutdown_requested = False
    _shutdown_cancelled_task_ids.clear()


def _track_render_runtime_task(
    task_id: str,
    task: asyncio.Task[None],
) -> None:
    """Hält Render-Tasks bis zu ihrem tatsächlichen Ende stark referenziert."""
    _render_runtime_tasks[task_id] = task

    def _forget(finished: asyncio.Task[None]) -> None:
        if _render_runtime_tasks.get(task_id) is finished:
            _render_runtime_tasks.pop(task_id, None)

    task.add_done_callback(_forget)


async def _shutdown_active_renders(
    state: AppState,
    *,
    cooperative_timeout: float = 2.0,
    forced_timeout: float = 3.0,
) -> dict[str, int]:
    """Unterbricht aktive Render sauber und verhindert verwaiste FFmpeg-Prozesse."""
    global _render_shutdown_requested
    _render_shutdown_requested = True

    active = {
        task_id: task
        for task_id, task in list(_render_runtime_tasks.items())
        if not task.done()
    }
    for task_id in active:
        _shutdown_cancelled_task_ids.add(task_id)
        state.set_cancel_flag(task_id, True)
        task_meta = state.get_render_task(task_id) or {}
        _safe_queue_update(
            task_meta.get("queue_job_id"),
            _RQ_INTERRUPTED,
            error="Backend shutdown during render",
        )

    pending: set[asyncio.Task[None]] = set(active.values())
    if pending:
        _, pending = await asyncio.wait(
            pending,
            timeout=max(cooperative_timeout, 0.0),
        )

    terminated_processes = 0
    if pending:
        from pb_studio.rendering.render_service import RenderService

        terminated_processes = await asyncio.to_thread(
            RenderService.terminate_active_processes,
            1.0,
        )
        _, pending = await asyncio.wait(
            pending,
            timeout=max(forced_timeout, 0.0),
        )

    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    return {
        "tasks": len(active),
        "forced_tasks": len(pending),
        "terminated_processes": terminated_processes,
    }


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


_RENDER_RESUME_PAYLOAD_VERSION = 1


def _request_settings_dict(
    request: RenderRequest,
    *,
    timeline_snapshot: Optional[list[dict[str, Any]]] = None,
    project_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Render-Settings als reines Dict für die Queue-Persistenz."""
    settings = {
        "resolution_width": request.resolution_width,
        "resolution_height": request.resolution_height,
        "fps": request.fps,
        "bitrate_mbps": request.bitrate_mbps,
        "encoder": request.encoder.value if request.encoder is not None else None,
        "include_audio": request.include_audio,
        "quality": request.quality.value if request.quality is not None else None,
    }
    if timeline_snapshot is not None and project_root is not None:
        settings["_resume"] = {
            "version": _RENDER_RESUME_PAYLOAD_VERSION,
            "request": request.model_dump(mode="json"),
            "timeline_snapshot": timeline_snapshot,
            "project_root": str(Path(project_root).resolve()),
        }
    return settings


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


def _find_runtime_task_for_queue_job(
    state: AppState,
    queue_job_id: str,
) -> Optional[dict[str, Any]]:
    """Findet den bereits geplanten Runtime-Task eines Queue-Jobs."""
    with state._state_lock:
        for task in state.render_tasks.values():
            if task.get("queue_job_id") == queue_job_id:
                return dict(task)
    return None


async def _preflight_render_request(
    request: RenderRequest,
    timeline_snapshot: list[dict[str, Any]],
) -> None:
    """Prüft Clips und expliziten AMF-Override vor Queue-/Task-Erzeugung."""
    from pb_studio.rendering.render_service import RenderService

    try:
        RenderService._validate_timeline_clips(timeline_snapshot)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.encoder is None:
        return

    encoder = request.encoder.value
    functional = await asyncio.to_thread(RenderService.probe_encoder, encoder)
    if functional:
        return

    if encoder == "av1_amf":
        detail = "AV1 AMF ist auf dieser AMD-GPU/FFmpeg-Konfiguration nicht verfügbar"
    else:
        detail = f"AMF-Encoder {encoder} ist nicht funktionsfähig"
    raise HTTPException(status_code=503, detail=detail)


async def _resume_render_queue_on_startup(
    state: AppState,
    *,
    queue=None,
) -> list[str]:
    """Reconstruct and schedule queued/interrupted jobs from persisted payloads."""
    if _render_shutdown_requested:
        return []
    render_queue = queue or _get_render_queue()
    render_queue.restore_running_as_interrupted()
    resumed_job_ids: list[str] = []

    for job in render_queue.list_pending():
        try:
            payload = job.settings.get("_resume")
            if (
                not isinstance(payload, dict)
                or payload.get("version") != _RENDER_RESUME_PAYLOAD_VERSION
            ):
                raise ValueError("Resume-Payload fehlt oder hat unbekannte Version")

            request_data = payload.get("request")
            timeline_snapshot = payload.get("timeline_snapshot")
            project_root_raw = payload.get("project_root")
            if not isinstance(request_data, dict):
                raise ValueError("Resume-Payload enthält keinen RenderRequest")
            if not isinstance(timeline_snapshot, list) or not timeline_snapshot:
                raise ValueError("Resume-Payload enthält keine Timeline")
            if not project_root_raw:
                raise ValueError("Resume-Payload enthält keine Projektwurzel")

            request = RenderRequest.model_validate(request_data)
            project_root = Path(project_root_raw).resolve()
            output_path = Path(request.output_path).resolve()
            if output_path != Path(job.output_path).resolve():
                raise ValueError("Resume-Output stimmt nicht mit Queue-Job überein")
            if not output_path.is_relative_to(project_root):
                raise ValueError("Resume-Output liegt außerhalb der Projektwurzel")

            base_task_id = f"resume-{job.job_id[:8]}"
            task_id = base_task_id
            suffix = 2
            while state.get_render_task(task_id) is not None:
                task_id = f"{base_task_id}-{suffix}"
                suffix += 1

            total_seconds = sum(
                max(
                    float(entry.get("end_time", 0.0))
                    - float(entry.get("start_time", 0.0)),
                    0.0,
                )
                for entry in timeline_snapshot
                if isinstance(entry, dict)
            )
            task_data = {
                "task_id": task_id,
                "status": TaskStatus.PENDING.value,
                "percent": 0.0,
                "current_frame": 0,
                "total_frames": max(int(round(total_seconds * request.fps)), 0),
                "fps": 0.0,
                "elapsed_seconds": 0.0,
                "eta_seconds": 0.0,
                "output_path": request.output_path,
                "error": None,
                "queue_job_id": job.job_id,
            }
            state.set_render_task(task_id, task_data)
            state.set_cancel_flag(task_id, False)
            render_queue.update_status(
                job.job_id,
                job.status,
                progress_percent=0.0,
                error="",
            )

            task = asyncio.create_task(
                _run_render_task(task_id, request, state, timeline_snapshot)
            )
            _track_render_runtime_task(task_id, task)

            def _on_resumed_done(
                finished: asyncio.Task,
                *,
                runtime_task_id: str = task_id,
                queue_job_id: str = job.job_id,
            ) -> None:
                if finished.cancelled():
                    _safe_queue_update(
                        queue_job_id,
                        (
                            _RQ_INTERRUPTED
                            if runtime_task_id in _shutdown_cancelled_task_ids
                            else _RQ_FAILED
                        ),
                        error=(
                            "Backend shutdown during resumed render"
                            if runtime_task_id in _shutdown_cancelled_task_ids
                            else "Resumed render task cancelled unexpectedly"
                        ),
                    )
                    return
                exc = finished.exception()
                if exc is not None:
                    logger.error(
                        "Resumed render %s unerwartet fehlgeschlagen: %s",
                        runtime_task_id,
                        exc,
                    )
                    state.update_render_task(runtime_task_id, {
                        "status": TaskStatus.FAILED.value,
                        "error": str(exc),
                    })
                    _safe_queue_update(queue_job_id, _RQ_FAILED, error=str(exc))

            task.add_done_callback(_on_resumed_done)
            resumed_job_ids.append(job.job_id)
        except Exception as exc:
            logger.error(
                "RenderQueue Resume für %s nicht möglich: %s",
                job.job_id,
                exc,
            )
            render_queue.update_status(
                job.job_id,
                _RQ_FAILED,
                error=f"Resume-Payload ungültig: {exc}",
            )

    await asyncio.sleep(0)
    return resumed_job_ids


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
    if _render_shutdown_requested:
        raise HTTPException(status_code=503, detail="Backend wird heruntergefahren")

    # Contract-Guard: Render darf nur mit vorhandener Timeline starten.
    timeline_snapshot = state.get_timeline_snapshot()
    if not timeline_snapshot:
        raise HTTPException(status_code=400, detail="Keine Timeline für Rendering vorhanden")

    # SEC-002: Path-Traversal-Schutz für output_path
    output_p_check = Path(request.output_path).resolve()
    allowed_render = resolve_active_project_root(state, config.project_dir)
    if not output_p_check.is_relative_to(allowed_render):
        raise HTTPException(status_code=403, detail="Output-Pfad außerhalb des erlaubten Verzeichnisses")

    await _preflight_render_request(request, timeline_snapshot)

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
        candidate_queue_job_id = str(uuid.uuid4())
        queue_job = _get_render_queue().enqueue(
            media_hash=media_hash,
            output_path=request.output_path,
            settings=_request_settings_dict(
                request,
                timeline_snapshot=timeline_snapshot,
                project_root=allowed_render,
            ),
            job_id=candidate_queue_job_id,
        )
        queue_job_id = queue_job.job_id
        if queue_job_id != candidate_queue_job_id:
            existing_task = _find_runtime_task_for_queue_job(state, queue_job_id)
            if existing_task is not None:
                return RenderProgress(**existing_task)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Identischer Render-Job existiert bereits "
                    f"(queue_job_id={queue_job_id}, status={queue_job.status})"
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning("RenderQueue.enqueue fehlgeschlagen (unkritisch): %s", exc)

    while True:
        task_id = str(uuid.uuid4())[:8]
        if state.get_render_task(task_id) is None:
            break

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
    _track_render_runtime_task(task_id, task)

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
    """Entfernt abgeschlossene Render-Tasks wenn mehr als max_tasks vorhanden.

    P-H1 (Audit V2): Time-Gate fuer cancel_flags pop — nur Tasks loeschen die
    TERMINAL + >1h alt sind. Sonst Race: aktive Render-Threads pruefen ihren
    Flag und kriegen False statt True nach pop. (MEDIUM-015 Kommentar in
    app_state.py war bekannt, Fix-Implementation jetzt komplett.)
    """
    import time as _t
    with state._state_lock:
        if len(state.render_tasks) <= max_tasks:
            return
        # Sortiere nach Status: completed/failed/cancelled zuerst entfernen
        terminal_statuses = {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}
        now = _t.monotonic()
        removable = [
            tid for tid, t in state.render_tasks.items()
            if t.get("status") in terminal_statuses
        ]
        # Älteste zuerst entfernen (bis max_tasks erreicht)
        to_remove = len(state.render_tasks) - max_tasks
        for tid in removable[:to_remove]:
            task = state.render_tasks.get(tid, {})
            del state.render_tasks[tid]
            # P-H1: nur Flag poppen wenn Task >1h alt (race-safe).
            # finished_at als monotonic-timestamp gesetzt beim Übergang in terminal.
            finished_at = task.get("finished_at")
            if finished_at is not None and (now - finished_at) > 3600:
                state.cancel_flags.pop(tid, None)
            # Sonst Flag stehen lassen — Memory-Leak ist akzeptabel (max 50 keys),
            # vermeidet Race wo aktive Thread False statt True sieht.
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

    try:
        if state.get_cancel_flag(task_id):
            raise _RenderCancelled()
        await _acquire_gpu_lock_or_cancel(task_id, state)
        try:
            logger.info(f"GPU-Lock erworben für Render {task_id}")

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
        finally:
            gpu_lock.release()

        elapsed = time.monotonic() - start_time
        state.update_render_task(task_id, {
            "status": TaskStatus.COMPLETED.value,
            "percent": 100.0,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
            "finished_at": time.monotonic(),  # P-H1: enable time-gated cancel_flag cleanup
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
        shutdown_interrupted = task_id in _shutdown_cancelled_task_ids
        state.update_render_task(task_id, {
            "status": TaskStatus.CANCELLED.value,
            "elapsed_seconds": round(elapsed, 1),
            "finished_at": time.monotonic(),  # P-H1
        })
        # Shutdown bleibt restartbar; ein User-Cancel bleibt terminal.
        if shutdown_interrupted:
            _safe_queue_update(
                queue_job_id,
                _RQ_INTERRUPTED,
                error="Backend shutdown during render",
            )
        else:
            _safe_queue_update(queue_job_id, _RQ_FAILED, error="cancelled")
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
        state.update_render_task(task_id, {
            "status": TaskStatus.FAILED.value,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
            "finished_at": time.monotonic(),  # P-H1
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


async def _acquire_gpu_lock_or_cancel(
    task_id: str,
    state: AppState,
    *,
    poll_seconds: float = 0.1,
) -> None:
    """Erwirbt den GPU-Lock kooperativ abbrechbar."""
    while True:
        if state.get_cancel_flag(task_id):
            raise _RenderCancelled()
        try:
            await asyncio.wait_for(gpu_lock.acquire(), timeout=poll_seconds)
            return
        except TimeoutError:
            continue


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
    preset = _QUALITY_PRESETS[request.quality.value]
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

    # C1-Fix (P-C1, 2026-05-19): validate_timeline mit audio_duration aufrufen,
    # damit Audio-Overflow-Check (Timeline > Audio = Error) auch im Render-Pfad
    # greift. pacing_router macht das richtig (siehe pacing_router.py:261-263),
    # render_router rief vorher OHNE audio_duration auf → Audio-Overflow-Check
    # übersprungen. L-TI-5 Iron Audit-Lesson 2026-05-11.
    from pb_studio.rendering.render_service import RenderService as _RenderServiceForAudio
    try:
        audio_duration = _RenderServiceForAudio()._get_audio_duration(audio_path) or 0.0
    except Exception as exc:
        logger.warning(f"audio_duration via ffprobe fehlgeschlagen ({exc}) — overflow-check skipped")
        audio_duration = 0.0
    warnings, errors = validate_timeline(timeline, audio_duration=audio_duration)
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
            preset=preset,
            progress_callback=on_progress,
            cancel_callback=is_cancelled,
            include_audio=request.include_audio,
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
            "finished_at": time.monotonic(),  # P-H1
        })
        return {"output_path": result_path}
    except RenderCancelledError as exc:
        raise _RenderCancelled() from exc
