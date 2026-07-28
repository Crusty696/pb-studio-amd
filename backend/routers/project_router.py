"""
Project Router – CRUD Operationen für PB Studio Projekte.

Endpoints:
  POST /project/create — Neues Projekt erstellen
  POST /project/open   — Bestehendes Projekt öffnen
  POST /project/save   — Aktuelles Projekt speichern
  POST /project/close  — Aktuelles Projekt schließen
  GET  /project/info   — Projekt-Informationen abrufen
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state, resolve_project_db_id
from pb_studio.data.repositories.project_repository import ProjectRepository
from ..config import config
from ..schemas.common import StatusResponse, validate_timeline
from ..schemas.project_schemas import ProjectCreate, ProjectOpen, ProjectInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project", tags=["Project"])

_PROJECT_META_FILE = "project.json"
_TIMELINE_FILE = "timeline.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bind_brain_to_project(project_path: Path) -> None:
    """Bind Brain to this project's state.db before switching runtime state."""
    try:
        from .._brain_singleton import set_project_state
        state_db = project_path / "state.db"
        set_project_state(state_db)
        logger.info(f"Brain bound to {state_db}")
    except Exception as e:
        logger.error("Brain bind fehlgeschlagen: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Brain-State konnte nicht an das Projekt gebunden werden: {e}",
        ) from e


def _project_meta_path(project_path: Path) -> Path:
    return project_path / _PROJECT_META_FILE


def _timeline_path(project_path: Path) -> Path:
    return project_path / _TIMELINE_FILE


def _find_or_create_project_db_record(project_path: Path, project_name: str, meta: dict | None = None) -> int:
    repo = ProjectRepository()
    normalized_path = str(project_path.resolve())
    for row in repo.get_all():
        data = row.get("data") or {}
        if data.get("path") == normalized_path:
            if row.get("name") != project_name or not data.get("path"):
                updated = dict(data)
                updated["path"] = normalized_path
                repo.update_project(int(row["id"]), name=project_name, data=updated)
            return int(row["id"])

    payload = dict(meta or {})
    payload["path"] = normalized_path
    project_id = repo.create_project(project_name, payload)
    if project_id <= 0:
        raise RuntimeError(f"Projekt-DB-Record konnte nicht erstellt werden: {project_name}")
    return int(project_id)


def _read_project_meta(project_path: Path) -> dict:
    meta_path = _project_meta_path(project_path)
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Projekt-Metadaten konnten nicht gelesen werden: {meta_path} ({e})")
        return {}


def _write_project_meta(project_path: Path, meta: dict) -> None:
    import os
    meta_path = _project_meta_path(project_path)
    tmp_path = meta_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(meta_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _normalize_timeline_entries(timeline: list[dict]) -> list[dict]:
    """Normalisiert Legacy-/flache Timeline-Einträge auf das kanonische Runtime-Format."""
    normalized: list[dict] = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue

        metadata = dict(entry.get("metadata") or {})
        flat_fields = {
            "file_path": entry.get("file_path"),
            "clip_start": entry.get("clip_start"),
            "clip_name": entry.get("clip_name"),
            "trigger_type": entry.get("trigger_type"),
            "trigger_strength": entry.get("trigger_strength"),
            "segment_type": entry.get("segment_type"),
        }
        for key, value in flat_fields.items():
            if metadata.get(key) in (None, "") and value not in (None, ""):
                metadata[key] = value

        normalized.append({
            "clip_id": entry.get("clip_id", ""),
            "start_time": entry.get("start_time", 0.0),
            "end_time": entry.get("end_time", 0.0),
            "metadata": metadata,
        })
    return normalized


def _load_timeline_into_state(project_path: Path, state: AppState) -> bool:
    timeline_path = _timeline_path(project_path)
    if not timeline_path.exists():
        state.set_timeline([])
        state.current_audio_path = None
        return False

    try:
        payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline = payload.get("timeline", [])
        audio_path = payload.get("audio_path")
        if not isinstance(timeline, list):
            raise ValueError("timeline ist keine Liste")

        timeline = _normalize_timeline_entries(timeline)
        warnings, errors = validate_timeline(timeline)
        for w in warnings:
            logger.warning(f"Projekt-Timeline Warnung beim Laden: {w}")
        for e in errors:
            logger.warning(f"Projekt-Timeline Fehler beim Laden: {e}")

        state.set_timeline(timeline)
        state.current_audio_path = audio_path if isinstance(audio_path, str) and audio_path else None
        return True
    except Exception as e:
        logger.warning(f"Timeline konnte nicht geladen werden: {timeline_path} ({e})")
        state.set_timeline([])
        state.current_audio_path = None
        return False


@router.post("/create", response_model=ProjectInfo)
async def create_project(
    request: ProjectCreate,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Erstellt ein neues Projekt."""

    project_path = (Path(request.path) / request.name).resolve()
    # SEC-001: Path-Traversal-Schutz — Create/Open immer gegen globalen Basis-Ordner prüfen
    # (nicht gegen aktuelles Projekt, sonst kann man kein neues erstellen während eines offen ist)
    allowed_base = Path(config.project_dir).resolve()
    if not project_path.is_relative_to(allowed_base):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    try:
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "audio").mkdir(exist_ok=True)
        (project_path / "video").mkdir(exist_ok=True)
        (project_path / "output").mkdir(exist_ok=True)
        (project_path / "cache").mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"Ordner nicht erstellbar: {e}")

    created_at = _utc_now_iso()
    project_data = {
        "name": request.name,
        "path": str(project_path),
        "audio_count": 0,
        "video_count": 0,
        "has_timeline": False,
        "created_at": created_at,
        "modified_at": created_at,
    }
    project_data["db_project_id"] = _find_or_create_project_db_record(project_path, request.name, project_data)
    _write_project_meta(project_path, project_data)

    # Brain zuerst binden: bei Fehler bleibt der bisherige Runtime-State unverändert.
    _bind_brain_to_project(project_path)

    # Neues Projekt muss immer mit sauberem Runtime-State starten.
    # Sonst übernimmt ein frisch erstelltes Projekt Clips/Timeline/Render-Tasks aus dem vorherigen Projekt.
    state.reset()
    state.current_project = project_data
    logger.info(f"Projekt erstellt: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path).resolve()
    # SEC-001: Path-Traversal-Schutz für Open (gegen globalen Basis-Ordner)
    allowed_base = Path(config.project_dir).resolve()
    if not project_path.is_relative_to(allowed_base):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Projekt nicht gefunden: {request.path}")

    meta = _read_project_meta(project_path)
    db_project_id = _find_or_create_project_db_record(project_path, meta.get("name", project_path.name), meta)

    # Medienkatalog isoliert vorladen. DB-/Schemafehler dürfen weder das aktive
    # Runtime-Projekt leeren noch Brain auf das neue Projekt umbiegen.
    candidate_project = {"path": str(project_path), "db_project_id": db_project_id}
    candidate_state = AppState(current_project=candidate_project)
    catalog_loaded = await asyncio.to_thread(
        candidate_state.load_from_db,
        project_id=db_project_id,
    )
    if not catalog_loaded:
        raise HTTPException(
            status_code=500,
            detail="Projekt-Medienkatalog konnte nicht aus der Datenbank geladen werden",
        )

    # Brain-Preflight vor Live-State-Wechsel: ein Bind-Fehler lässt das bisher
    # aktive Runtime-Projekt weiterhin unverändert.
    _bind_brain_to_project(project_path)

    # Erst nach beiden erfolgreichen Preflights den Live-State ersetzen.
    state.reset()
    with state._state_lock:
        with state._lock:
            state.current_project = candidate_project
            state.audio_clips.update(candidate_state.audio_clips)
            state.audio_analysis_cache.update(candidate_state.audio_analysis_cache)
            state.video_clips.update(candidate_state.video_clips)
            state.video_analysis_cache.update(candidate_state.video_analysis_cache)
            state._audio_next_id = candidate_state._audio_next_id
            state._video_next_id = candidate_state._video_next_id

    meta = _read_project_meta(project_path)
    has_timeline = _load_timeline_into_state(project_path, state)

    # Fallback: lokale Projektordner zählen, falls keine Metadaten vorhanden.
    audio_count = int(meta.get("audio_count") or 0)
    video_count = int(meta.get("video_count") or 0)
    if audio_count == 0 and (project_path / "audio").exists():
        audio_count = sum(1 for f in (project_path / "audio").glob("*") if f.is_file())
    if video_count == 0 and (project_path / "video").exists():
        video_count = sum(1 for f in (project_path / "video").glob("*") if f.is_file())

    project_data = {
        "name": meta.get("name", project_path.name),
        "path": str(project_path),
        "db_project_id": db_project_id,
        "audio_count": audio_count,
        "video_count": video_count,
        "has_timeline": bool(meta.get("has_timeline", has_timeline)),
        "created_at": meta.get("created_at"),
        "modified_at": meta.get("modified_at"),
    }
    state.current_project = project_data
    logger.info(f"Projekt geöffnet: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/save", response_model=StatusResponse)
async def save_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Speichert das aktuelle Projekt."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")

    project_path = Path(state.current_project["path"]).resolve()
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Projektpfad nicht gefunden: {project_path}")

    timeline = _normalize_timeline_entries(state.get_timeline_snapshot())
    state.set_timeline(timeline)
    timeline_path = _timeline_path(project_path)
    if timeline:
        timeline_payload = {
            "audio_path": state.current_audio_path,
            "timeline": timeline,
            "saved_at": _utc_now_iso(),
        }
        # R17/FINDING-5: Atomic write — crash during save must not corrupt timeline.json.
        # Same tmp+os.replace pattern used by _write_project_meta.
        tmp_tl = timeline_path.with_suffix(".tmp")
        try:
            tmp_tl.write_text(json.dumps(timeline_payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp_tl), str(timeline_path))
        finally:
            if tmp_tl.exists():
                tmp_tl.unlink(missing_ok=True)
    else:
        timeline_path.unlink(missing_ok=True)

    existing_meta = _read_project_meta(project_path)
    project_data = {
        "name": state.current_project.get("name", project_path.name),
        "path": str(project_path),
        "db_project_id": resolve_project_db_id(state.current_project),
        "audio_count": len(state.get_audio_clips_snapshot()),
        "video_count": len(state.get_video_clips_snapshot()),
        "has_timeline": bool(timeline),
        "created_at": existing_meta.get("created_at") or state.current_project.get("created_at") or _utc_now_iso(),
        "modified_at": _utc_now_iso(),
    }
    _write_project_meta(project_path, project_data)
    state.current_project = project_data
    state.sync_project_db_record()

    logger.info(f"Projekt gespeichert: {project_path}")
    return StatusResponse(success=True, message="Projekt gespeichert")


@router.post("/close", response_model=StatusResponse)
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    name = state.current_project.get("name", "Unbekannt")
    # In-flight Render-Tasks abbrechen bevor State geleert wird (verhindert GPU-Lock Stall)
    # Snapshot der Task-IDs unter Lock nehmen um Race-Condition beim Iterieren zu verhindern.
    with state._state_lock:
        task_ids = list(state.render_tasks.keys())
    for task_id in task_ids:
        state.set_cancel_flag(task_id, True)
    # Reset BEVOR current_project = None (reset() leert alle Caches)
    state.reset()
    # L-STATE-4: Brain-State-Connection vom alten Projekt loesen, sonst
    # schreiben /brain/feedback Calls weiter in die alte state.db
    # (Cross-Project-Leak). Best-effort: bricht den Close nicht ab.
    try:
        from backend._brain_singleton import clear_project_state
        clear_project_state()
    except Exception as e:
        logger.warning("Brain-State-Unbind beim Close fehlgeschlagen: %s", e)
    logger.info(f"Projekt geschlossen: {name}")
    return StatusResponse(success=True, message=f"Projekt '{name}' geschlossen")


@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    project_data = dict(state.current_project)
    project_data["audio_count"] = len(state.get_audio_clips_snapshot())
    project_data["video_count"] = len(state.get_video_clips_snapshot())
    return ProjectInfo(**project_data)
