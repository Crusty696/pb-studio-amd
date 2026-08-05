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
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import (
    AppState,
    PersistenceError,
    ProjectContextChangedError,
    ProjectContextUnavailableError,
    ProjectOperationContext,
    get_app_state,
    persistence_error,
    resolve_project_db_id,
)
from ..config import config
from ..dependencies import gpu_lock, publish_event, publish_log
from ..media_path_policy import (
    MediaPathPolicyError,
    canonical_local_media_reference,
    validate_media_catalog,
    validate_registered_media_path,
    validate_timeline_media_paths,
)
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
    STATE_CANCELLED as _RQ_CANCELLED,
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


_RENDER_RESUME_PAYLOAD_VERSION = 1
_RENDER_IDENTITY_VERSION = 1


def _canonical_identity_path(raw_path: str | Path) -> str:
    """Canonical, case-insensitive Windows path representation for hashing."""
    return os.path.normcase(str(Path(raw_path).resolve())).replace("\\", "/")


def _stored_render_media_hashes(
    request: RenderRequest,
    timeline: list[dict[str, Any]],
    state: AppState,
) -> dict[str, Any]:
    """Freeze persisted audio/video content hashes used by this render."""
    def content_hash_or_file_hash(raw_hash: Any, raw_path: str) -> str:
        stored_hash = str(raw_hash or "").strip().lower()
        if stored_hash:
            return stored_hash
        path = Path(raw_path).resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"Render-Medium ist keine Datei: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    audio_path_key = _canonical_identity_path(request.audio_path)
    audio_identity: Optional[dict[str, Any]] = None
    for clip_id, clip in state.get_audio_clips_snapshot().items():
        if _canonical_identity_path(str(clip.get("path") or "")) != audio_path_key:
            continue
        audio_identity = {
            "clip_id": int(clip_id),
            "path": audio_path_key,
            "content_hash": content_hash_or_file_hash(
                clip.get("audio_hash") or clip.get("file_hash"),
                request.audio_path,
            ),
        }
        break
    if audio_identity is None:
        raise ValueError("Render-Audio fehlt im Medienkatalog")

    video_clips = state.get_video_clips_snapshot()
    video_identities: dict[int, dict[str, Any]] = {}
    for entry in timeline:
        clip_id = str(entry.get("clip_id") or "")
        if not clip_id.startswith("clip_"):
            continue
        try:
            video_id = int(clip_id[5:])
        except ValueError:
            continue
        clip = video_clips.get(video_id) or {}
        if not clip:
            raise ValueError(f"Render-Video {clip_id} fehlt im Medienkatalog")
        metadata = entry.get("metadata") or {}
        media_path = str(metadata.get("file_path") or clip.get("path") or "")
        video_identities[video_id] = {
            "clip_id": clip_id,
            "path": _canonical_identity_path(media_path),
            "content_hash": content_hash_or_file_hash(
                clip.get("video_hash") or clip.get("file_hash"),
                media_path,
            ),
        }

    return {
        "audio": audio_identity,
        "video": [
            video_identities[video_id]
            for video_id in sorted(video_identities)
        ],
    }


def _compute_render_media_hash(
    audio_path: str,
    timeline: list[dict[str, Any]],
    *,
    render_settings: Optional[dict[str, Any]] = None,
    project_root: Optional[Path] = None,
    project_db_id: Optional[int] = None,
    media_content_hashes: Optional[dict[str, Any]] = None,
) -> str:
    """Stable request/content identity for active render deduplication."""
    canonical = json.dumps(
        {
            "version": _RENDER_IDENTITY_VERSION,
            "audio_path": _canonical_identity_path(audio_path),
            "timeline": timeline or [],
            "render_settings": render_settings or {},
            "project": {
                "root": (
                    _canonical_identity_path(project_root)
                    if project_root is not None
                    else None
                ),
                "db_id": int(project_db_id) if project_db_id is not None else None,
            },
            "media_content_hashes": media_content_hashes or {},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_render_identity(
    request: RenderRequest,
    timeline: list[dict[str, Any]],
    state: AppState,
    *,
    project_root: Path,
    project_db_id: int,
) -> tuple[str, dict[str, Any]]:
    media_content_hashes = _stored_render_media_hashes(request, timeline, state)
    digest = _compute_render_media_hash(
        request.audio_path,
        timeline,
        render_settings=_request_settings_dict(request),
        project_root=project_root,
        project_db_id=project_db_id,
        media_content_hashes=media_content_hashes,
    )
    return digest, {
        "version": _RENDER_IDENTITY_VERSION,
        "digest": digest,
        "media_content_hashes": media_content_hashes,
    }


def _request_settings_dict(
    request: RenderRequest,
    *,
    timeline_snapshot: Optional[list[dict[str, Any]]] = None,
    project_root: Optional[Path] = None,
    project_db_id: Optional[int] = None,
    identity_snapshot: Optional[dict[str, Any]] = None,
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
    if (
        timeline_snapshot is not None
        and project_root is not None
        and project_db_id is not None
    ):
        request_snapshot = request.model_dump(mode="json")
        request_snapshot["output_path"] = str(Path(request.output_path).resolve())
        request_snapshot["audio_path"] = str(Path(request.audio_path).resolve())
        settings["_resume"] = {
            "version": _RENDER_RESUME_PAYLOAD_VERSION,
            "request": request_snapshot,
            "timeline_snapshot": timeline_snapshot,
            "project_root": str(Path(project_root).resolve()),
            "project_db_id": int(project_db_id),
        }
    if identity_snapshot is not None:
        settings["_identity"] = identity_snapshot
    return settings


def _queue_update_or_raise(
    queue_job_id: Optional[str],
    status: str,
    **kwargs: Any,
) -> None:
    """Persist a lifecycle transition before reporting it to the UI."""
    if not queue_job_id:
        raise persistence_error(
            "render_queue",
            f"Render-Queue-ID fehlt für Status {status}",
        )
    try:
        updated = _get_render_queue().update_status(
            queue_job_id,
            status,
            **kwargs,
        )
    except Exception as exc:
        raise persistence_error(
            "render_queue",
            f"Render-Status {status} konnte nicht gespeichert werden",
            exc,
        ) from exc
    if updated is None:
        raise persistence_error(
            "render_queue",
            f"Render-Job {queue_job_id} fehlt für Status {status}",
        )


def _safe_queue_update(queue_job_id: Optional[str], status: str, **kwargs: Any) -> None:
    """Best-effort only while already reporting a terminal failure."""
    try:
        _queue_update_or_raise(queue_job_id, status, **kwargs)
    except PersistenceError as exc:
        logger.error(
            "RenderQueue.update_status fehlgeschlagen für %s (%s): %s",
            queue_job_id, status, exc,
        )


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


def _validate_render_media_contract(
    request: RenderRequest,
    timeline_snapshot: list[dict[str, Any]],
    state: AppState,
) -> tuple[RenderRequest, list[dict[str, Any]]]:
    """Bind all render inputs to canonical files in the active media catalogue."""
    audio_clips = state.get_audio_clips_snapshot()
    validated_audio = validate_registered_media_path(
        request.audio_path,
        (clip.get("path", "") for clip in audio_clips.values()),
        label="Render audio_path",
    )
    if state.current_audio_path:
        active_audio = validate_registered_media_path(
            state.current_audio_path,
            (clip.get("path", "") for clip in audio_clips.values()),
            label="Aktive Timeline audio_path",
        )
        if os.path.normcase(validated_audio) != os.path.normcase(active_audio):
            raise MediaPathPolicyError(
                "Render audio_path gehoert nicht zur aktiven Timeline"
            )

    validated_timeline = validate_timeline_media_paths(
        timeline_snapshot,
        state.get_video_clips_snapshot(),
    )
    return request.model_copy(update={"audio_path": validated_audio}), validated_timeline


def _load_resume_media_state(
    project_root_raw: str,
    project_db_id_raw: Any,
) -> tuple[AppState, Path]:
    """Restore only the persisted project's validated media catalogue for resume."""
    try:
        project_root = canonical_local_media_reference(
            project_root_raw,
            label="Resume-Projektwurzel",
        ).resolve(strict=True)
    except (MediaPathPolicyError, OSError, RuntimeError) as exc:
        raise ValueError(f"Resume-Projektwurzel ist ungueltig: {exc}") from exc
    if not project_root.is_dir():
        raise ValueError("Resume-Projektwurzel ist kein Ordner")

    allowed_root = Path(config.project_dir).resolve(strict=True)
    if not project_root.is_relative_to(allowed_root):
        raise ValueError("Resume-Projektwurzel liegt ausserhalb des Projektordners")

    from pb_studio.data.repositories.project_repository import ProjectRepository

    project_repo = ProjectRepository()
    project_record = None
    if project_db_id_raw not in (None, ""):
        try:
            project_db_id = int(project_db_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Resume-Payload enthaelt keine gueltige Projekt-ID") from exc
        project_record = project_repo.get_by_id(project_db_id)
    else:
        # Backward-compatible lookup for version-1 jobs created before the
        # project_db_id field was added. The registered canonical root remains
        # the trust anchor; the payload path alone is never accepted.
        project_db_id = 0
        for candidate in project_repo.get_all():
            candidate_root_raw = (candidate.get("data") or {}).get("path")
            try:
                candidate_root = canonical_local_media_reference(
                    str(candidate_root_raw or ""),
                    label="Registrierte Resume-Projektwurzel",
                ).resolve(strict=True)
            except (MediaPathPolicyError, OSError, RuntimeError):
                continue
            if os.path.normcase(str(candidate_root)) == os.path.normcase(
                str(project_root)
            ):
                project_record = candidate
                project_db_id = int(candidate["id"])
                break
    if not project_record:
        raise ValueError("Resume-Projekt ist nicht mehr registriert")
    registered_root_raw = (project_record.get("data") or {}).get("path")
    try:
        registered_root = canonical_local_media_reference(
            str(registered_root_raw or ""),
            label="Registrierte Resume-Projektwurzel",
        ).resolve(strict=True)
    except (MediaPathPolicyError, OSError, RuntimeError) as exc:
        raise ValueError(f"Registrierte Resume-Projektwurzel ist ungueltig: {exc}") from exc
    if os.path.normcase(str(registered_root)) != os.path.normcase(str(project_root)):
        raise ValueError("Resume-Projekt-ID und Projektwurzel stimmen nicht ueberein")

    resume_state = AppState(
        current_project={
            "path": str(project_root),
            "db_project_id": project_db_id,
        }
    )
    if not resume_state.load_from_db(project_id=project_db_id):
        raise ValueError("Resume-Medienkatalog konnte nicht geladen werden")
    resume_state.audio_clips = validate_media_catalog(
        resume_state.get_audio_clips_snapshot(),
        label="Resume-Audio-Katalog",
    )
    resume_state.video_clips = validate_media_catalog(
        resume_state.get_video_clips_snapshot(),
        label="Resume-Video-Katalog",
    )
    return resume_state, project_root


async def _resume_render_queue_on_startup(
    state: AppState,
    *,
    queue=None,
) -> list[str]:
    """Reconstruct and schedule queued/interrupted jobs from persisted payloads."""
    _reset_render_runtime_for_startup()
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
            project_db_id_raw = payload.get("project_db_id")
            if not isinstance(request_data, dict):
                raise ValueError("Resume-Payload enthält keinen RenderRequest")
            if not isinstance(timeline_snapshot, list) or not timeline_snapshot:
                raise ValueError("Resume-Payload enthält keine Timeline")
            if not project_root_raw:
                raise ValueError("Resume-Payload enthält keine Projektwurzel")

            resume_media_state, project_root = await asyncio.to_thread(
                _load_resume_media_state,
                str(project_root_raw),
                project_db_id_raw,
            )
            request = RenderRequest.model_validate(request_data)
            request, timeline_snapshot = _validate_render_media_contract(
                request,
                timeline_snapshot,
                resume_media_state,
            )
            output_path = Path(request.output_path).resolve()
            if output_path != Path(job.output_path).resolve():
                raise ValueError("Resume-Output stimmt nicht mit Queue-Job überein")
            if not output_path.is_relative_to(project_root):
                raise ValueError("Resume-Output liegt außerhalb der Projektwurzel")

            identity_snapshot = job.settings.get("_identity")
            if identity_snapshot is not None:
                if (
                    not isinstance(identity_snapshot, dict)
                    or identity_snapshot.get("version") != _RENDER_IDENTITY_VERSION
                    or not identity_snapshot.get("digest")
                ):
                    raise ValueError(
                        "Render-Identitaet fehlt oder hat unbekannte Version"
                    )
                current_digest, _ = await asyncio.to_thread(
                    _build_render_identity,
                    request,
                    timeline_snapshot,
                    resume_media_state,
                    project_root=project_root,
                    project_db_id=resolve_project_db_id(
                        resume_media_state.current_project
                    ),
                )
                if current_digest != identity_snapshot["digest"]:
                    raise ValueError(
                        "Render-Identitaet hat sich seit dem Queueing geaendert"
                    )

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
            updated_job = render_queue.update_status(
                job.job_id,
                job.status,
                progress_percent=0.0,
                error="",
            )
            if updated_job is None:
                raise persistence_error(
                    "render_queue",
                    f"Resume-Job {job.job_id} fehlt vor Task-Start",
                )
            state.set_render_task(task_id, task_data)
            state.set_cancel_flag(task_id, False)

            task = asyncio.create_task(
                _run_render_task(
                    task_id,
                    request,
                    state,
                    timeline_snapshot,
                    job.job_id,
                )
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
    """Startet ein Rendering im unveraenderlichen Projektkontext."""
    if _render_shutdown_requested:
        raise HTTPException(status_code=503, detail="Backend wird heruntergefahren")

    try:
        async with state.project_operation() as context:
            return await _start_render_for_project(
                request,
                state,
                context,
            )
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _start_render_for_project(
    request: RenderRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> RenderProgress:
    """Validiert und publiziert einen Render-Task fuer exakt ein Projekt."""
    # Contract-Guard: Render darf nur mit vorhandener Timeline starten.
    timeline_snapshot = state.get_timeline_snapshot()
    if not timeline_snapshot:
        raise HTTPException(status_code=400, detail="Keine Timeline für Rendering vorhanden")

    try:
        request, timeline_snapshot = _validate_render_media_contract(
            request,
            timeline_snapshot,
            state,
        )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # SEC-002: Path-Traversal-Schutz für output_path
    output_p_check = Path(request.output_path).resolve()
    allowed_render = context.project_root
    if not output_p_check.is_relative_to(allowed_render):
        # Audit 2026-08-05 (C-1): Dieses 403 wurde zuvor ohne jede Logzeile
        # geworfen. Im Backend-Log stand nur das gpu_lock-Paar, der Client
        # verwarf den detail-Body -- der Export war damit fuer den User und
        # fuer die Diagnose grundlos blockiert.
        logger.warning(
            "Render abgelehnt: Output-Pfad ausserhalb der Projektwurzel. "
            "output_path=%s aufgeloest=%s erlaubt=%s",
            request.output_path,
            output_p_check,
            allowed_render,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                f"Output-Pfad liegt ausserhalb des Projektverzeichnisses. "
                f"Gewaehlt: {output_p_check} — erlaubt ist nur: {allowed_render}"
            ),
        )

    project_db_id = context.project_id
    media_hash, identity_snapshot = await asyncio.to_thread(
        _build_render_identity,
        request,
        timeline_snapshot,
        state,
        project_root=allowed_render,
        project_db_id=project_db_id,
    )

    await _preflight_render_request(request, timeline_snapshot)
    state.require_project_context_current(context)

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
        candidate_queue_job_id = str(uuid.uuid4())
        queue_job = _get_render_queue().enqueue(
            media_hash=media_hash,
            output_path=request.output_path,
            settings=_request_settings_dict(
                request,
                timeline_snapshot=timeline_snapshot,
                project_root=allowed_render,
                project_db_id=project_db_id,
                identity_snapshot=identity_snapshot,
            ),
            job_id=candidate_queue_job_id,
        )
        queue_job_id = queue_job.job_id
        if queue_job_id != candidate_queue_job_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Identischer Render-Job existiert bereits "
                    f"(queue_job_id={queue_job_id}, status={queue_job.status})"
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("RenderQueue.enqueue fehlgeschlagen: %s", exc, exc_info=True)
        raise persistence_error(
            "render_queue",
            "Render-Job konnte nicht dauerhaft registriert werden",
            exc,
        ) from exc

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
        "message": "Render-Task registriert",
        "queue_job_id": queue_job_id,
        "progress_end": False,
        "validation_status": None,
    }
    state.set_render_task(task_id, task_data)
    state.set_cancel_flag(task_id, False)

    # R14/HIGH-004: Snapshot beim Start übergeben — _run_render_task darf den State nicht
    # erneut lesen, damit kein Stale-Timeline-Race zwischen start_render und Task-Ausführung entsteht.
    task = asyncio.create_task(
        _run_render_task_bound(
            task_id,
            request,
            state,
            timeline_snapshot,
            context,
            queue_job_id,
        )
    )
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


def _finalize_timeline_for_render(
    timeline: list[dict[str, Any]],
    target_duration: float,
) -> list[dict[str, Any]]:
    """Wendet den kanonischen Pacing-Abschluss auf einen isolierten Snapshot an."""
    from copy import deepcopy

    from pb_studio.pacing.pacing_models import CutListEntry
    from pb_studio.services.pacing_service import PacingService

    eligible = [
        deepcopy(entry)
        for entry in timeline
        if float(entry.get("start_time", 0.0)) < target_duration
    ]
    cut_list = [
        CutListEntry(
            clip_id=str(entry.get("clip_id", "")),
            start_time=float(entry.get("start_time", 0.0)),
            end_time=float(entry.get("end_time", 0.0)),
            metadata=deepcopy(entry.get("metadata") or {}),
        )
        for entry in eligible
    ]
    finalized = PacingService()._finalize_cut_list(
        cut_list,
        target_duration,
    )
    result = []
    for source, cut in zip(eligible, finalized):
        source["start_time"] = cut.start_time
        source["end_time"] = cut.end_time
        source["metadata"] = cut.metadata
        result.append(source)
    return result


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


async def _run_render_task_bound(
    task_id: str,
    request: RenderRequest,
    state: AppState,
    timeline_snapshot: list[dict[str, Any]],
    context: ProjectOperationContext,
    queue_job_id: Optional[str],
) -> None:
    """Bindet den Hintergrund-Render an den beim Start erfassten Kontext."""
    try:
        async with state.project_operation() as active_context:
            if active_context != context:
                raise ProjectContextChangedError(
                    "Projekt wurde vor dem Render-Task-Start gewechselt"
                )
            await _run_render_task(
                task_id,
                request,
                state,
                timeline_snapshot,
                queue_job_id,
            )
    except asyncio.CancelledError:
        state.set_cancel_flag(task_id, True)
        _safe_queue_update(
            queue_job_id,
            _RQ_INTERRUPTED,
            error="Render-Task vor Kontextbindung abgebrochen",
        )
        raise
    except (
        ProjectContextChangedError,
        ProjectContextUnavailableError,
    ) as exc:
        _safe_queue_update(queue_job_id, _RQ_FAILED, error=str(exc))
        state.update_render_task(
            task_id,
            {
                "status": TaskStatus.FAILED.value,
                "error": str(exc),
                "message": "Render-Projektkontext ist nicht mehr aktuell",
                "finished_at": time.monotonic(),
            },
        )


async def _run_render_task(
    task_id: str,
    request: RenderRequest,
    state: AppState,
    timeline_snapshot: list[dict[str, Any]],
    queue_job_id: Optional[str],
) -> None:
    """Background-Task für Rendering mit Cancel-Support.

    timeline_snapshot wird von start_render übergeben — wird hier NICHT erneut aus dem
    State gelesen (R14/HIGH-004: Race zwischen Snapshot-Check und Task-Start vermeiden).
    """
    start_time = time.monotonic()

    try:
        _queue_update_or_raise(queue_job_id, _RQ_RUNNING)
        state.update_render_task(task_id, {"status": TaskStatus.RUNNING.value})
        if state.get_cancel_flag(task_id):
            raise _RenderCancelled()
        await _acquire_gpu_lock_or_cancel(task_id, state)
        try:
            logger.info(f"GPU-Lock erworben für Render {task_id}")

            if state.get_cancel_flag(task_id):
                raise _RenderCancelled()

            render_worker = asyncio.create_task(
                asyncio.to_thread(
                    _execute_render,
                    task_id,
                    request,
                    state,
                    timeline_snapshot,
                    asyncio.get_running_loop(),
                )
            )
            try:
                result = await asyncio.shield(render_worker)
            except asyncio.CancelledError:
                # Ein Projektwechsel cancelt die asyncio-Task. Der physische
                # Thread muss sein Cancel-Flag sehen und enden, bevor GPU-Lock
                # und Projekt-Lifecycle freigegeben werden.
                state.set_cancel_flag(task_id, True)
                try:
                    await asyncio.shield(render_worker)
                except _RenderCancelled as exc:
                    raise exc
                raise _RenderCancelled()
        finally:
            gpu_lock.release()

        elapsed = time.monotonic() - start_time
        _queue_update_or_raise(queue_job_id, _RQ_COMPLETED)
        state.update_render_task(task_id, {
            "status": TaskStatus.COMPLETED.value,
            "percent": 100.0,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
            "message": "Rendering abgeschlossen",
            "progress_end": bool(result.get("progress_end", False)),
            "run_id": result.get("run_id"),
            "evidence_path": result.get("evidence_path"),
            "validation_path": result.get("validation_path"),
            "validation_status": result.get("validation_status"),
            "finished_at": time.monotonic(),  # P-H1: enable time-gated cancel_flag cleanup
        })

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": 100.0,
            "status": "completed",
            "message": "Rendering abgeschlossen",
            "queue_job_id": queue_job_id,
            "run_id": result.get("run_id"),
            "evidence_path": result.get("evidence_path"),
            "validation_path": result.get("validation_path"),
            "progress_end": bool(result.get("progress_end", False)),
            "validation_status": result.get("validation_status"),
        })
        await publish_log(
            f"Render abgeschlossen: {task_id}",
            level="info",
            source="render.run",
            detail=f"elapsed={elapsed:.1f}s output={request.output_path}",
        )

        logger.info(f"Render {task_id} abgeschlossen: {elapsed:.1f}s")

    except _RenderCancelled as exc:
        elapsed = time.monotonic() - start_time
        shutdown_interrupted = task_id in _shutdown_cancelled_task_ids
        task_snapshot = state.get_render_task(task_id) or {}
        target_queue_status = (
            _RQ_INTERRUPTED if shutdown_interrupted else _RQ_CANCELLED
        )
        target_queue_error = (
            "Backend shutdown during render" if shutdown_interrupted else "cancelled"
        )
        try:
            _queue_update_or_raise(
                queue_job_id,
                target_queue_status,
                error=target_queue_error,
            )
        except PersistenceError as persist_exc:
            state.update_render_task(task_id, {
                "status": TaskStatus.FAILED.value,
                "error": str(persist_exc),
                "message": "Render-Abbruch konnte nicht gespeichert werden",
                "elapsed_seconds": round(elapsed, 1),
                "eta_seconds": 0.0,
                "progress_end": False,
                "validation_status": "failed",
                "finished_at": time.monotonic(),
            })
            await publish_event("render_progress", {
                "task_id": task_id,
                "percent": float(task_snapshot.get("percent", 0.0) or 0.0),
                "status": "failed",
                "message": str(persist_exc),
                "error": str(persist_exc),
                "queue_job_id": queue_job_id,
                "progress_end": False,
                "validation_status": "failed",
            })
            return

        state.update_render_task(task_id, {
            "status": TaskStatus.CANCELLED.value,
            "message": "Rendering abgebrochen",
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
            "run_id": exc.run_id,
            "evidence_path": exc.evidence_path,
            "validation_path": exc.validation_path,
            "progress_end": False,
            "validation_status": "cancelled",
            "finished_at": time.monotonic(),  # P-H1
        })
        logger.info(f"Render {task_id} abgebrochen nach {elapsed:.1f}s")

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": float(task_snapshot.get("percent", 0.0) or 0.0),
            "status": "cancelled",
            "message": "Rendering abgebrochen",
            "queue_job_id": queue_job_id,
            "run_id": exc.run_id,
            "evidence_path": exc.evidence_path,
            "validation_path": exc.validation_path,
            "progress_end": False,
            "validation_status": "cancelled",
        })
        await publish_log(
            f"Render abgebrochen: {task_id}",
            level="warning",
            source="render.run",
            detail=f"elapsed={elapsed:.1f}s",
        )

    except Exception as e:
        elapsed = time.monotonic() - start_time
        task_snapshot = state.get_render_task(task_id) or {}
        run_id = getattr(e, "run_id", None)
        evidence_path = getattr(e, "evidence_path", None)
        validation_path = getattr(e, "validation_path", None)
        state.update_render_task(task_id, {
            "status": TaskStatus.FAILED.value,
            "error": str(e),
            "message": "Rendering fehlgeschlagen",
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0.0,
            "run_id": run_id,
            "evidence_path": evidence_path,
            "validation_path": validation_path,
            "progress_end": False,
            "validation_status": "failed",
            "finished_at": time.monotonic(),  # P-H1
        })
        _safe_queue_update(queue_job_id, _RQ_FAILED, error=str(e))
        logger.error(f"Render {task_id} fehlgeschlagen: {e}", exc_info=True)

        await publish_event("render_progress", {
            "task_id": task_id,
            "percent": float(task_snapshot.get("percent", 0.0) or 0.0),
            "status": "failed",
            "message": str(e),
            "error": str(e),
            "queue_job_id": queue_job_id,
            "run_id": run_id,
            "evidence_path": evidence_path,
            "validation_path": validation_path,
            "progress_end": False,
            "validation_status": "failed",
        })
        await publish_log(
            f"Render fehlgeschlagen: {task_id}",
            level="error",
            source="render.run",
            detail=str(e),
        )


class _RenderCancelled(Exception):
    """Internal cancellation carrying any persisted terminal evidence."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        evidence_path: str | None = None,
        validation_path: str | None = None,
    ) -> None:
        super().__init__("Rendering abgebrochen")
        self.run_id = run_id
        self.evidence_path = evidence_path
        self.validation_path = validation_path


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
    task_meta = state.get_render_task(task_id) or {}
    render_job_id = str(task_meta.get("queue_job_id") or task_id)
    service = RenderService(
        output_dir=str(output_p.parent),
        encoder_override=encoder_override,
        job_id=render_job_id,
    )
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
            "message": message,
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
    if request.include_audio and audio_duration > 0.0:
        timeline = _finalize_timeline_for_render(timeline, audio_duration)
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

    def terminal_evidence() -> dict[str, str | None]:
        evidence_dir = (
            output_p.parent
            / ".render_evidence"
            / service.job_token
            / service.run_id
        )
        evidence_path = evidence_dir / "result.json"
        validation_path = evidence_dir / "validation.json"
        return {
            "run_id": service.run_id or None,
            "evidence_path": str(evidence_path) if evidence_path.is_file() else None,
            "validation_path": (
                str(validation_path) if validation_path.is_file() else None
            ),
        }

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
            "message": "Rendering abgeschlossen",
            "run_id": service.run_id,
            "progress_end": True,
            "evidence_path": str(
                output_p.parent
                / ".render_evidence"
                / service.job_token
                / service.run_id
                / "result.json"
            ),
            "validation_path": str(
                output_p.parent
                / ".render_evidence"
                / service.job_token
                / service.run_id
                / "validation.json"
            ),
            "validation_status": "validated",
            "finished_at": time.monotonic(),  # P-H1
        })
        return {
            "output_path": result_path,
            "run_id": service.run_id,
            "progress_end": True,
            "evidence_path": str(
                output_p.parent
                / ".render_evidence"
                / service.job_token
                / service.run_id
                / "result.json"
            ),
            "validation_path": str(
                output_p.parent
                / ".render_evidence"
                / service.job_token
                / service.run_id
                / "validation.json"
            ),
            "validation_status": "validated",
        }
    except RenderCancelledError as exc:
        raise _RenderCancelled(**terminal_evidence()) from exc
    except Exception as exc:
        for key, value in terminal_evidence().items():
            setattr(exc, key, value)
        raise
