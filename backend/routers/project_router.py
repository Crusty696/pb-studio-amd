"""
Project Router – CRUD Operationen für PB Studio Projekte.

Endpoints:
  POST /project/create — Neues Projekt erstellen
  POST /project/open   — Bestehendes Projekt öffnen
  POST /project/save   — Aktuelles Projekt speichern
  POST /project/close  — Aktuelles Projekt schließen
  GET  /project/info   — Projekt-Informationen abrufen
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state
from ..config import config
from ..schemas.common import StatusResponse
from ..schemas.project_schemas import ProjectCreate, ProjectOpen, ProjectInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project", tags=["Project"])


@router.post("/create", response_model=ProjectInfo)
async def create_project(
    request: ProjectCreate,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Erstellt ein neues Projekt."""

    project_path = (Path(request.path) / request.name).resolve()
    # SEC-001: Path-Traversal-Schutz — nur innerhalb des konfigurierten Projektverzeichnisses erlaubt
    allowed_base = Path(config.project_dir).resolve()
    if not str(project_path).startswith(str(allowed_base)):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    try:
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "audio").mkdir(exist_ok=True)
        (project_path / "video").mkdir(exist_ok=True)
        (project_path / "output").mkdir(exist_ok=True)
        (project_path / "cache").mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"Ordner nicht erstellbar: {e}")

    project_data = {
        "name": request.name,
        "path": str(project_path),
        "audio_count": 0,
        "video_count": 0,
        "has_timeline": False,
    }
    state.current_project = project_data
    logger.info(f"Projekt erstellt: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Projekt nicht gefunden: {request.path}")

    # Audio/Video Dateien zählen
    audio_count = sum(1 for f in (project_path / "audio").glob("*") if f.is_file()) if (project_path / "audio").exists() else 0
    video_count = sum(1 for f in (project_path / "video").glob("*") if f.is_file()) if (project_path / "video").exists() else 0

    project_data = {
        "name": project_path.name,
        "path": str(project_path),
        "audio_count": audio_count,
        "video_count": video_count,
        "has_timeline": (project_path / "timeline.json").exists(),
    }
    state.current_project = project_data
    logger.info(f"Projekt geöffnet: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/save", response_model=StatusResponse)
async def save_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Speichert das aktuelle Projekt."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    logger.info(f"Projekt gespeichert: {state.current_project['path']}")
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
