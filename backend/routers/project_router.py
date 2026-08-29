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
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from pb_studio.storage.recovery_barrier import recovery_write_operation

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
from pb_studio.data.repositories.project_repository import ProjectRepository
from ..config import config
from ..media_path_policy import (
    MediaPathPolicyError,
    validate_media_catalog,
    validate_registered_media_path,
    validate_timeline_media_paths,
)
from ..schemas.common import StatusResponse, validate_timeline
from ..schemas.project_schemas import ProjectCreate, ProjectOpen, ProjectInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project", tags=["Project"])

_PROJECT_META_FILE = "project.json"
_TIMELINE_FILE = "timeline.json"
_CREATE_OWNER_FILE = ".pb-studio-create-owner.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bind_brain_to_project(
    project_path: Path,
    *,
    project_epoch: int,
    project_id: int,
    project_uuid: str,
) -> None:
    """Bind Brain to this project's state.db before switching runtime state."""
    try:
        from .._brain_singleton import set_project_state
        state_db = project_path / "state.db"
        set_project_state(
            state_db,
            project_epoch=project_epoch,
            project_id=project_id,
            project_uuid=project_uuid,
        )
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


def _write_creation_owner(
    staging_path: Path,
    *,
    owner_token: str,
    target_path: Path,
) -> None:
    marker = {
        "schema_version": 1,
        "owner_token": owner_token,
        "target_path": str(target_path),
        "created_at": _utc_now_iso(),
    }
    (staging_path / _CREATE_OWNER_FILE).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _prepare_project_state_db(staging_path: Path) -> None:
    """Create and migrate state.db before the directory is published."""
    from pb_studio.storage import migration_runner

    migrations_dir = (
        Path(migration_runner.__file__).resolve().parent
        / "migrations"
        / "state"
    )
    migration_runner.migrate(staging_path / "state.db", migrations_dir)


def _remove_owned_creation_directory(
    path: Path,
    *,
    owner_token: str,
    allowed_base: Path,
) -> bool:
    """Remove only a staging/final directory carrying the exact owner token."""
    if not path.exists():
        return False
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(allowed_base):
        raise RuntimeError(
            f"Refusing creation compensation outside project base: {resolved_path}"
        )
    marker_path = resolved_path / _CREATE_OWNER_FILE
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Refusing creation compensation without readable owner marker: "
            f"{resolved_path}"
        ) from exc
    if marker.get("owner_token") != owner_token:
        raise RuntimeError(
            f"Refusing creation compensation for foreign directory: {resolved_path}"
        )
    shutil.rmtree(resolved_path)
    return True


def _compensate_project_creation(
    *,
    staging_path: Path,
    project_path: Path,
    published: bool,
    project_id: int | None,
    owner_token: str,
    allowed_base: Path,
) -> list[str]:
    """Best-effort compensation restricted to artifacts owned by this call."""
    errors: list[str] = []
    if project_id is not None:
        try:
            ProjectRepository().delete_owned_project(project_id, owner_token)
        except Exception as exc:
            errors.append(f"DB compensation failed: {exc}")
    owned_path = project_path if published else staging_path
    try:
        _remove_owned_creation_directory(
            owned_path,
            owner_token=owner_token,
            allowed_base=allowed_base,
        )
    except Exception as exc:
        errors.append(f"directory compensation failed: {exc}")
    return errors


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


def _find_project_db_record_id(project_path: Path) -> int | None:
    normalized_path = str(project_path.resolve())
    for row in ProjectRepository().get_all():
        data = row.get("data") or {}
        if data.get("path") == normalized_path:
            return int(row["id"])
    return None


def _catalog_project_uuid(
    project_id: int,
    project_path: Path,
    *,
    fallback_uuid: str | None = None,
) -> str:
    row = ProjectRepository().get_by_id(int(project_id))
    if row is not None:
        value = row.get("project_uuid") or (row.get("data") or {}).get(
            "project_uuid"
        )
        if value:
            return str(uuid.UUID(str(value)))
    if fallback_uuid:
        return str(uuid.UUID(str(fallback_uuid)))
    fallback = str(uuid.uuid5(uuid.NAMESPACE_URL, project_path.resolve().as_uri()))
    logger.warning(
        "Project %s has no catalog project_uuid; using standalone identity %s",
        project_id,
        fallback,
    )
    return fallback


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


def _restore_file_snapshot(path: Path, snapshot: bytes | None) -> None:
    """Restore one save-owned file to its exact pre-save bytes."""
    rollback_path = path.with_suffix(f"{path.suffix}.rollback.tmp")
    try:
        if snapshot is None:
            path.unlink(missing_ok=True)
            return
        rollback_path.write_bytes(snapshot)
        os.replace(str(rollback_path), str(path))
    finally:
        rollback_path.unlink(missing_ok=True)


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
        timeline = validate_timeline_media_paths(
            timeline,
            state.get_video_clips_snapshot(),
        )
        if audio_path:
            audio_path = validate_registered_media_path(
                audio_path,
                (
                    clip.get("path", "")
                    for clip in state.get_audio_clips_snapshot().values()
                ),
                label="Projekt-Timeline audio_path",
            )
        warnings, errors = validate_timeline(timeline)
        for w in warnings:
            logger.warning(f"Projekt-Timeline Warnung beim Laden: {w}")
        for e in errors:
            logger.warning(f"Projekt-Timeline Fehler beim Laden: {e}")

        state.set_timeline(timeline)
        state.current_audio_path = audio_path if isinstance(audio_path, str) and audio_path else None
        return True
    except MediaPathPolicyError as e:
        logger.warning(
            "Projekt-Timeline wegen unsicherem Medienpfad verworfen: %s (%s)",
            timeline_path,
            e,
        )
        state.set_timeline([])
        state.current_audio_path = None
        return False
    except Exception as e:
        logger.warning(f"Timeline konnte nicht geladen werden: {timeline_path} ({e})")
        state.set_timeline([])
        state.current_audio_path = None
        return False


def _timeline_payload(timeline: list[dict], audio_path: str | None) -> dict:
    """Einziges Dateiformat fuer timeline.json — von /project/save und vom Close-Pfad geteilt.

    Der einzige Leser (``_load_timeline_into_state``) erwartet ein Dict. Eine
    nackte Liste wuerde dort still verworfen, deshalb darf das Format nur an
    dieser einen Stelle entstehen.
    """
    return {
        "audio_path": audio_path,
        "timeline": timeline,
        "saved_at": _utc_now_iso(),
    }


def persist_timeline_for_context(state: AppState, project_root: Path) -> bool:
    """Sichert die RAM-Timeline nach timeline.json, bevor der State verworfen wird.

    Die Pacing-Engine schreibt ihr Ergebnis nur ueber ``state.set_timeline(...)``.
    Ohne diesen Aufruf verliert jeder Projektwechsel und jedes Close die
    generierte Timeline ersatzlos.

    Bewusst OHNE ``state.project_commit(...)``-Guard: an beiden Aufrufstellen
    (``close_project``, ``_activate_project``) existiert kein
    ``ProjectOperationContext`` — der Kontext wird dort gerade invalidiert. Der
    Schreibvorgang gehoert zum alten Projekt und darf deshalb nicht an dessen
    Epoch-Guard haengen, sonst waere er per Konstruktion immer blockiert.

    Bewusste Asymmetrie zu ``_save_project_in_context``: bei leerer Timeline
    loescht der Save-Pfad die Datei, dieser Pfad laesst sie stehen. Ein leerer
    ``current_timeline`` entsteht auch nach einem fehlgeschlagenen Pacing-Lauf
    oder vor dem Laden eines Projekts; ein Close-Pfad, der daraufhin still
    Nutzdaten loescht, waere der schlimmere Fehler. Die Falle bleibt: wer alle
    Cuts entfernt und dann nur schliesst, findet die alte Timeline wieder —
    zum Loeschen ist ``/project/save`` zustaendig.

    Legt bewusst KEIN Verzeichnis an (anders als ``set_anchors``, das unter
    ``project_operation()`` laeuft und dessen Existenz garantiert ist). Sonst
    liesse ein extern geloeschter Projektordner sich hier als Geisterprojekt
    mit einer einsamen timeline.json wiederauferstehen.

    Returns:
        True wenn geschrieben wurde, False wenn es nichts zu sichern gab.
    """
    # Timeline und audio_path gehoeren zusammen und werden in EINER
    # Lock-Akquise gelesen; zwei getrennte Snapshots waeren nicht konsistent.
    with state._state_lock:
        raw_timeline = list(state.current_timeline)
        audio_path = state.current_audio_path

    timeline = _normalize_timeline_entries(raw_timeline)
    if not timeline:
        if _timeline_path(project_root).exists():
            logger.info(
                "Leere RAM-Timeline: vorhandene timeline.json in %s bleibt erhalten. "
                "Zum Loeschen /project/save verwenden.",
                project_root,
            )
        return False

    if not project_root.is_dir():
        logger.warning(
            "Timeline nicht gesichert: Projektordner fehlt (%s)",
            project_root,
        )
        return False

    path = _timeline_path(project_root)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(
            json.dumps(
                _timeline_payload(timeline, audio_path),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(path))
    finally:
        tmp.unlink(missing_ok=True)

    logger.info("Timeline gesichert: %d Cuts in %s", len(timeline), path)
    return True


async def _activate_project(
    state: AppState,
    project_path: Path,
    project_data: dict,
    candidate_state: AppState | None = None,
) -> None:
    """Serialisiert Brain-Bind, Epoch-Wechsel, Task-Drain und State-Swap."""
    async with state.project_lifecycle_lock:
        # Timeline des NOCH aktiven alten Projekts sichern, bevor der Kontext
        # invalidiert und der Runtime-State ersetzt wird. current_project zeigt
        # hier noch auf A; genullt wird es erst in state.reset().
        with state._state_lock:
            previous_project = dict(state.current_project or {})
        previous_root = previous_project.get("path")
        # Reopen desselben Projekts ist KEIN Wechsel: open_project hat die alte
        # timeline.json bereits in candidate_state geladen und wuerde sie
        # gleich in den RAM setzen. Ein Schreiben des neuen RAM-Stands liesse
        # Datei und UI auseinanderlaufen. Es gibt keinen Same-Path-Guard in
        # open_project, dieser Fall ist also real erreichbar.
        if previous_root and Path(previous_root).resolve() != project_path.resolve():
            try:
                persist_timeline_for_context(state, Path(previous_root))
            except Exception as exc:
                logger.error(
                    "Timeline des vorherigen Projekts konnte vor dem Wechsel "
                    "nicht gesichert werden: %s",
                    exc,
                    exc_info=True,
                )
        # Alte Commits zuerst sperren und registrierte Tasks beenden. Dadurch
        # kann während des externen Brain-Rebinds kein A-Job mehr nach B schreiben.
        state.invalidate_project_context()
        _, pending = await state.cancel_and_drain_project_tasks()
        # Ein Bind-Fehler lässt den bisherigen Runtime-State erhalten; dessen
        # alte Tasks bleiben jedoch bewusst invalidiert und beendet.
        _bind_brain_to_project(
            project_path,
            project_epoch=state.project_epoch,
            project_id=int(project_data["db_project_id"]),
            project_uuid=str(
                project_data.get("project_uuid")
                or uuid.uuid5(uuid.NAMESPACE_URL, project_path.resolve().as_uri())
            ),
        )
        state.reset(invalidate_context=False)
        state.install_project_state(project_data, candidate_state)
        if pending:
            logger.warning(
                "Projektwechsel mit %d noch auslaufenden stale Task(s); "
                "Epoch-Guard blockiert deren Commit",
                pending,
            )


@router.post("/create", response_model=ProjectInfo)
@recovery_write_operation("project-files")
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
    if project_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Projekt existiert bereits: {project_path}",
        )

    owner_token = uuid.uuid4().hex
    staging_path: Path | None = None
    project_id: int | None = None
    published = False
    project_data: dict | None = None

    try:
        project_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path = Path(
            tempfile.mkdtemp(
                prefix=".pb-studio-create-",
                dir=str(project_path.parent),
            )
        ).resolve()
        _write_creation_owner(
            staging_path,
            owner_token=owner_token,
            target_path=project_path,
        )
        for directory_name in ("audio", "video", "output", "cache"):
            (staging_path / directory_name).mkdir()
        _prepare_project_state_db(staging_path)

        created_at = _utc_now_iso()
        project_data = {
            "name": request.name,
            "path": str(project_path),
            "project_uuid": str(uuid.uuid4()),
            "audio_count": 0,
            "video_count": 0,
            "has_timeline": False,
            "created_at": created_at,
            "modified_at": created_at,
        }
        project_id = ProjectRepository().create_owned_project(
            request.name,
            project_data,
            owner_token,
        )
        project_data["db_project_id"] = project_id
        _write_project_meta(staging_path, project_data)

        # Same-volume rename publishes the fully prepared directory atomically.
        os.replace(str(staging_path), str(project_path))
        published = True

        # Neues Projekt startet nach serialisiertem Brain-/Epoch-Wechsel mit
        # sauberem Runtime-State. Bind-Fehler werden unten kompensiert.
        await _activate_project(state, project_path, project_data)
    except asyncio.CancelledError:
        if staging_path is not None:
            cleanup_errors = _compensate_project_creation(
                staging_path=staging_path,
                project_path=project_path,
                published=published,
                project_id=project_id,
                owner_token=owner_token,
                allowed_base=allowed_base,
            )
            if cleanup_errors:
                logger.critical(
                    "Projekt-Erstellung abgebrochen; Kompensation unvollstaendig: %s",
                    "; ".join(cleanup_errors),
                )
        raise
    except Exception as exc:
        cleanup_errors = []
        if staging_path is not None:
            cleanup_errors = _compensate_project_creation(
                staging_path=staging_path,
                project_path=project_path,
                published=published,
                project_id=project_id,
                owner_token=owner_token,
                allowed_base=allowed_base,
            )
        if cleanup_errors:
            logger.critical(
                "Projekt-Erstellung und Kompensation fehlgeschlagen: %s",
                "; ".join(cleanup_errors),
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Projekt konnte nicht atomar erstellt werden; "
                    + "; ".join(cleanup_errors)
                ),
            ) from exc
        if isinstance(exc, OSError) and project_path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Projekt existiert bereits: {project_path}",
            ) from exc
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Projekt konnte nicht erstellt werden: {exc}",
        ) from exc

    if project_data is None:
        raise HTTPException(
            status_code=500,
            detail="Projekt konnte nicht initialisiert werden",
        )
    try:
        (project_path / _CREATE_OWNER_FILE).unlink()
    except OSError as exc:
        logger.warning(
            "Creation-Owner-Marker konnte nach Erfolg nicht entfernt werden: %s",
            exc,
        )
    logger.info(f"Projekt erstellt: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/open", response_model=ProjectInfo)
@recovery_write_operation("project-files")
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
    existing_project_id = _find_project_db_record_id(project_path)
    candidate_project_id = (
        existing_project_id if existing_project_id is not None else -1
    )

    # Medienkatalog isoliert vorladen. DB-/Schemafehler dürfen weder das aktive
    # Runtime-Projekt leeren noch Brain auf das neue Projekt umbiegen.
    candidate_project = {
        "path": str(project_path),
        "db_project_id": candidate_project_id,
    }
    candidate_state = AppState(current_project=candidate_project)
    catalog_loaded = await asyncio.to_thread(
        candidate_state.load_from_db,
        project_id=candidate_project_id,
    )
    if not catalog_loaded:
        raise HTTPException(
            status_code=500,
            detail="Projekt-Medienkatalog konnte nicht aus der Datenbank geladen werden",
        )

    try:
        candidate_state.audio_clips = validate_media_catalog(
            candidate_state.get_audio_clips_snapshot(),
            label="Audio-Katalog",
        )
        candidate_state.video_clips = validate_media_catalog(
            candidate_state.get_video_clips_snapshot(),
            label="Video-Katalog",
        )
    except MediaPathPolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Projekt-Medienkatalog enthaelt unsichere Pfade: {exc}",
        ) from exc

    meta = _read_project_meta(project_path)
    has_timeline = _load_timeline_into_state(project_path, candidate_state)

    # Fallback: lokale Projektordner zählen, falls keine Metadaten vorhanden.
    audio_count = int(meta.get("audio_count") or 0)
    video_count = int(meta.get("video_count") or 0)
    if audio_count == 0 and (project_path / "audio").exists():
        audio_count = sum(1 for f in (project_path / "audio").glob("*") if f.is_file())
    if video_count == 0 and (project_path / "video").exists():
        video_count = sum(1 for f in (project_path / "video").glob("*") if f.is_file())

    db_project_id = (
        existing_project_id
        if existing_project_id is not None
        else _find_or_create_project_db_record(
            project_path,
            meta.get("name", project_path.name),
            meta,
        )
    )
    project_data = {
        "name": meta.get("name", project_path.name),
        "path": str(project_path),
        "db_project_id": db_project_id,
        "project_uuid": _catalog_project_uuid(
            db_project_id,
            project_path,
            fallback_uuid=meta.get("project_uuid"),
        ),
        "audio_count": audio_count,
        "video_count": video_count,
        # I-1: `or` statt Default — create_project schreibt den Schluessel IMMER
        # als False, der Default griff daher nie. Wurde eine timeline.json
        # tatsaechlich geladen, gewinnt diese Beobachtung gegen stale Metadaten
        # (Close ohne Save, manuell kopierte Projekte).
        "has_timeline": bool(meta.get("has_timeline") or has_timeline),
        "created_at": meta.get("created_at"),
        "modified_at": meta.get("modified_at"),
    }
    try:
        await _activate_project(
            state,
            project_path,
            project_data,
            candidate_state,
        )
    except BaseException:
        if existing_project_id is None:
            try:
                ProjectRepository().delete_project(db_project_id)
            except Exception as compensation_error:
                logger.critical(
                    "Projekt-Open fehlgeschlagen; DB-Kompensation fuer %s "
                    "ebenfalls fehlgeschlagen: %s",
                    db_project_id,
                    compensation_error,
                    exc_info=True,
                )
        raise
    logger.info(f"Projekt geöffnet: {project_path}")
    return ProjectInfo(**project_data)


@router.post("/save", response_model=StatusResponse)
@recovery_write_operation("project-files")
async def save_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Persist the current project without reporting false success."""
    try:
        async with state.project_operation() as context:
            return _save_project_in_context(state, context)
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _save_project_in_context(
    state: AppState,
    context: ProjectOperationContext,
) -> StatusResponse:
    project_path = context.project_root
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Projektpfad nicht gefunden: {project_path}")

    timeline = _normalize_timeline_entries(state.get_timeline_snapshot())
    timeline_path = _timeline_path(project_path)
    existing_meta = _read_project_meta(project_path)
    with state._state_lock:
        current_project = dict(state.current_project or {})
    project_data = {
        "name": current_project.get("name", project_path.name),
        "path": str(project_path),
        "db_project_id": context.project_id,
        "project_uuid": current_project.get("project_uuid")
        or existing_meta.get("project_uuid")
        or _catalog_project_uuid(context.project_id, project_path),
        "audio_count": len(state.get_audio_clips_snapshot()),
        "video_count": len(state.get_video_clips_snapshot()),
        "has_timeline": bool(timeline),
        "created_at": existing_meta.get("created_at") or current_project.get("created_at") or _utc_now_iso(),
        "modified_at": _utc_now_iso(),
    }

    timeline_payload = (
        _timeline_payload(timeline, state.current_audio_path) if timeline else None
    )
    meta_path = _project_meta_path(project_path)
    try:
        timeline_snapshot = (
            timeline_path.read_bytes() if timeline_path.is_file() else None
        )
        meta_snapshot = meta_path.read_bytes() if meta_path.is_file() else None
    except OSError as exc:
        raise persistence_error(
            "project_save",
            "Bestehende Projektdateien konnten nicht gesichert werden",
            exc,
        ) from exc
    timeline_stage = timeline_path.with_suffix(f"{timeline_path.suffix}.save.tmp")
    meta_stage = meta_path.with_suffix(f"{meta_path.suffix}.save.tmp")
    durable_mutated = False
    try:
        if timeline_payload is not None:
            timeline_stage.write_text(
                json.dumps(timeline_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        meta_stage.write_text(
            json.dumps(project_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if timeline_payload is None:
            if timeline_path.exists():
                timeline_path.unlink()
                durable_mutated = True
        else:
            os.replace(str(timeline_stage), str(timeline_path))
            durable_mutated = True
        os.replace(str(meta_stage), str(meta_path))
        durable_mutated = True

        # SQLite commits last. Any failure restores both files byte-for-byte.
        if not state.sync_project_db_record(project_data):
            raise RuntimeError("Projekt-DB-Sync meldete keinen erfolgreichen Commit")
    except Exception as exc:
        rollback_errors: list[str] = []
        if durable_mutated:
            for path, snapshot in (
                (timeline_path, timeline_snapshot),
                (meta_path, meta_snapshot),
            ):
                try:
                    _restore_file_snapshot(path, snapshot)
                except Exception as rollback_error:
                    rollback_errors.append(f"{path.name}: {rollback_error}")
        detail = "Projektdateien/DB konnten nicht konsistent gespeichert werden"
        if rollback_errors:
            detail += "; Rollback unvollstaendig: " + "; ".join(rollback_errors)
            logger.critical("%s", detail, exc_info=True)
        raise persistence_error(
            "project_save",
            detail,
            exc,
        ) from exc
    finally:
        timeline_stage.unlink(missing_ok=True)
        meta_stage.unlink(missing_ok=True)

    with state.project_commit(context):
        state.set_timeline(timeline)
        state.current_project = project_data

    logger.info(f"Projekt gespeichert: {project_path}")
    return StatusResponse(success=True, message="Projekt gespeichert")


@router.post("/close", response_model=StatusResponse)
@recovery_write_operation("project-files")
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    async with state.project_lifecycle_lock:
        with state._state_lock:
            if not state.current_project:
                raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
            name = state.current_project.get("name", "Unbekannt")
            project_root = state.current_project.get("path")
        # Timeline sichern, bevor state.reset() sie verwirft. Ein Schreibfehler
        # darf das Schliessen nicht verhindern.
        if project_root:
            try:
                persist_timeline_for_context(state, Path(project_root))
            except Exception as exc:
                logger.error(
                    "Timeline konnte vor dem Schliessen nicht gesichert werden: %s",
                    exc,
                    exc_info=True,
                )
        state.invalidate_project_context()
        _, pending = await state.cancel_and_drain_project_tasks()
        # In-flight Render-Threads nutzen weiterhin ihre bestehenden Cancel-Flags.
        with state._state_lock:
            task_ids = list(state.render_tasks.keys())
        for task_id in task_ids:
            state.set_cancel_flag(task_id, True)
        # L-STATE-4: Brain-State-Connection vom alten Projekt loesen, sonst
        # schreiben /brain/feedback Calls weiter in die alte state.db.
        try:
            from backend._brain_singleton import (
                clear_project_state,
                current_project_state_identity,
            )
            clear_project_state()
            if current_project_state_identity() is not None:
                raise RuntimeError("Brain-State ist weiterhin an ein Projekt gebunden")
        except Exception as e:
            logger.error(
                "Brain-State-Unbind beim Close fehlgeschlagen: %s",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Projekt konnte nicht geschlossen werden, weil der "
                    "Brain-State nicht freigegeben wurde"
                ),
            ) from e
        state.reset(invalidate_context=False)
        if pending:
            logger.warning(
                "Projekt-Close mit %d noch auslaufenden stale Task(s); "
                "Epoch-Guard blockiert deren Commit",
                pending,
            )
    logger.info(f"Projekt geschlossen: {name}")
    return StatusResponse(success=True, message=f"Projekt '{name}' geschlossen")


# ---------------------------------------------------------------------------
# Manuelle Anker (Audit 2026-08-06, T4.3)
#
# Der ANCHOR-Tab der WPF hatte KEIN Backend-Gegenstueck: `AddAnchor` mutierte
# nur eine ObservableCollection, es gab weder Route noch Schema noch Persistenz,
# und beim Projektwechsel wurde die Liste geleert. Was der User dort anlegte,
# beeinflusste weder Schnitte noch Render und ueberlebte keinen Tab-Wechsel.
#
# Die Engine kann manuelle Anker laengst — `PacingService.load_canvas_manual_anchors`
# baut aus einem Obsidian-.canvas-File Dicts der Form
# {id, file_path, mix_start, mix_end}. Es fehlte nur der Weg von der UI dorthin.
# Persistenz als anchors.json neben timeline.json, gleiches Muster wie dort.
# ---------------------------------------------------------------------------
_ANCHORS_FILE = "anchors.json"


class AnchorEntry(BaseModel):
    """Ein manueller Anker: fixiert einen Clip auf eine Zeit im Mix."""

    time: float = Field(ge=0.0, description="Position im Mix in Sekunden.")
    label: str = ""
    video_clip_id: Optional[int] = None


class AnchorListResponse(BaseModel):
    anchors: list[AnchorEntry] = Field(default_factory=list)
    count: int = 0


def _anchors_path(project_root: str | Path) -> Path:
    return Path(project_root) / _ANCHORS_FILE


def load_project_anchors(project_root: str | Path) -> list[dict]:
    """Liest die manuellen Anker eines Projekts. Fehler ergeben eine leere Liste."""
    path = _anchors_path(project_root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("anchors.json nicht lesbar: %s", path)
        return []
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            seconds = float(item.get("time", -1.0))
        except (TypeError, ValueError):
            continue
        if seconds < 0.0:
            continue
        result.append({
            "time": seconds,
            "label": str(item.get("label") or ""),
            "video_clip_id": item.get("video_clip_id"),
        })
    result.sort(key=lambda entry: entry["time"])
    return result


@router.get("/anchors", response_model=AnchorListResponse)
async def get_anchors(
    state: AppState = Depends(get_app_state),
) -> AnchorListResponse:
    """Liefert die manuellen Anker des aktiven Projekts."""
    try:
        async with state.project_operation() as context:
            entries = load_project_anchors(context.project_root)
            state.require_project_context_current(context)
            return AnchorListResponse(
                anchors=[AnchorEntry(**entry) for entry in entries],
                count=len(entries),
            )
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/anchors", response_model=AnchorListResponse)
@recovery_write_operation("project-files")
async def set_anchors(
    payload: list[AnchorEntry],
    state: AppState = Depends(get_app_state),
) -> AnchorListResponse:
    """Ersetzt die manuellen Anker des aktiven Projekts."""
    normalized = sorted(
        ({
            "time": float(entry.time),
            "label": entry.label,
            "video_clip_id": entry.video_clip_id,
        } for entry in payload),
        key=lambda entry: entry["time"],
    )
    tmp: Optional[Path] = None
    try:
        async with state.project_operation() as context:
            path = _anchors_path(context.project_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with state.project_commit(context):
                os.replace(tmp, path)
            logger.info("Manuelle Anker gespeichert: %d in %s", len(normalized), path)
    except OSError as exc:
        logger.error("anchors.json nicht schreibbar: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Anker konnten nicht gespeichert werden: {exc}",
        ) from exc
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)

    return AnchorListResponse(
        anchors=[AnchorEntry(**entry) for entry in normalized],
        count=len(normalized),
    )


@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
    try:
        async with state.project_operation() as context:
            with state.project_commit(context):
                project_data = dict(state.current_project or {})
                project_data["audio_count"] = len(state.audio_clips)
                project_data["video_count"] = len(state.video_clips)
            return ProjectInfo(**project_data)
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=400, detail="Kein Projekt geoeffnet") from exc
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
