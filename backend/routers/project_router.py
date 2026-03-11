"""
Project Router – CRUD Operationen für PB Studio Projekte.

Endpoints:
  POST /project/create — Neues Projekt erstellen
  POST /project/open   — Bestehendes Projekt öffnen
  POST /project/save   — Aktuelles Projekt speichern
  POST /project/close  — Aktuelles Projekt schließen
  GET  /project/info   — Projekt-Informationen abrufen
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state, resolve_active_project_root
from ..config import config
from ..schemas.common import StatusResponse, validate_timeline
from ..schemas.project_schemas import ProjectCreate, ProjectOpen, ProjectInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project", tags=["Project"])

_PROJECT_META_FILE = "project.json"
_TIMELINE_FILE = "timeline.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_meta_path(project_path: Path) -> Path:
    return project_path / _PROJECT_META_FILE


def _timeline_path(project_path: Path) -> Path:
    return project_path / _TIMELINE_FILE


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
    meta_path = _project_meta_path(project_path)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


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

        warnings = validate_timeline(timeline)
        for w in warnings:
            logger.warning(f"Projekt-Timeline Warnung beim Laden: {w}")

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
    # SEC-001: Path-Traversal-Schutz — nur innerhalb des aktiven Projektroots bzw. Fallback-Basisordners erlaubt
    allowed_base = resolve_active_project_root(state, config.project_dir)
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
    _write_project_meta(project_path, project_data)
    state.current_project = project_data
    state.set_timeline([])
    state.current_audio_path = None
    logger.info(f"Projekt erstellt: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path).resolve()
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Projekt nicht gefunden: {request.path}")

    # State frisch laden: erst reset, dann kanonische Clip-Kataloge aus DB wiederherstellen.
    state.reset()
    state.load_from_db()

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

    timeline = state.get_timeline_snapshot()
    timeline_path = _timeline_path(project_path)
    if timeline:
        timeline_payload = {
            "audio_path": state.current_audio_path,
            "timeline": timeline,
            "saved_at": _utc_now_iso(),
        }
        timeline_path.write_text(json.dumps(timeline_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        timeline_path.unlink(missing_ok=True)

    existing_meta = _read_project_meta(project_path)
    project_data = {
        "name": state.current_project.get("name", project_path.name),
        "path": str(project_path),
        "audio_count": len(state.get_audio_clips_snapshot()),
        "video_count": len(state.get_video_clips_snapshot()),
        "has_timeline": bool(timeline),
        "created_at": existing_meta.get("created_at") or state.current_project.get("created_at") or _utc_now_iso(),
        "modified_at": _utc_now_iso(),
    }
    _write_project_meta(project_path, project_data)
    state.current_project = project_data

    logger.info(f"Projekt gespeichert: {project_path}")
    return StatusResponse(success=True, message="Projekt gespeichert")


@router.post("/close", response_model=StatusResponse)
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    name = state.current_project["name"]
    # Reset BEVOR current_project = None (reset() leert alle Caches)
    state.reset()
    logger.info(f"Projekt geschlossen: {name}")
    return StatusResponse(success=True, message=f"Projekt '{name}' geschlossen")


@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    return ProjectInfo(**state.current_project)
