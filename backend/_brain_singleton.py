"""BrainService accessor for FastAPI routers (Plan Phase 4).

Single-process singleton. Project state.db is bound when the app sets the
current project; brain_router falls back to a 409 if not bound yet.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pb_studio.brain.brain_service import (
    BrainProjectIdentity,
    BrainService,
    BrainStateLease,
)

logger = logging.getLogger(__name__)

_PROJECT_STATE_PATH: Optional[Path] = None


def get_brain_service() -> BrainService:
    return BrainService.get()


def set_project_state(
    path: str | Path,
    *,
    project_epoch: Optional[int] = None,
    project_id: Optional[int] = None,
    project_uuid: Optional[str] = None,
) -> BrainProjectIdentity:
    global _PROJECT_STATE_PATH
    new_path = Path(path).resolve()
    identity_kwargs = {}
    if project_epoch is not None:
        identity_kwargs["project_epoch"] = project_epoch
    if project_id is not None:
        identity_kwargs["project_id"] = project_id
    if project_uuid is not None:
        identity_kwargs["project_uuid"] = project_uuid
    identity = BrainService.get().bind_project_state(new_path, **identity_kwargs)
    _PROJECT_STATE_PATH = new_path
    return identity


def project_state_lease(
    *,
    path: Optional[str | Path] = None,
    project_epoch: Optional[int] = None,
    project_id: Optional[int] = None,
) -> BrainStateLease:
    """Lease the active Brain state connection for one project operation."""
    return BrainService.get().project_state_lease(
        state_db_path=path,
        project_epoch=project_epoch,
        project_id=project_id,
    )


acquire_project_state_lease = project_state_lease


def current_project_state_path() -> Optional[Path]:
    return _PROJECT_STATE_PATH


def current_project_state_identity() -> Optional[BrainProjectIdentity]:
    return BrainService.get().project_state_identity


def clear_project_state() -> None:
    """L-STATE-4: unbind state.db nach /project/close - verhindert dass
    /brain/feedback weiter in die alte state.db schreibt (Cross-Project-Leak).

    Wird vom project_router.close_project gerufen. Wirft nicht, damit der
    App-Lifecycle nicht crashed - meldet den Fehlschlag aber laut und loest
    den Brain-State fail-closed hart: bleibt die Bindung bestehen, waehrend
    _PROJECT_STATE_PATH schon None ist, schreibt jedes folgende
    /brain/feedback Lerndaten in das geschlossene Projekt."""
    global _PROJECT_STATE_PATH
    _PROJECT_STATE_PATH = None

    try:
        service = BrainService.get()
    except Exception:
        logger.error(
            "BrainService.get() beim Projekt-Close fehlgeschlagen - es gibt "
            "keine Instanz, an der ein Brain-State geloest werden koennte",
            exc_info=True,
        )
        return

    try:
        service.unbind_project_state()
        return
    except Exception:
        logger.error(
            "unbind_project_state fehlgeschlagen - Brain-State wird "
            "fail-closed hart geloest, um Schreibzugriffe auf das "
            "geschlossene Projekt zu verhindern",
            exc_info=True,
        )

    try:
        cleaned_up = service.force_unbind_project_state()
    except Exception:
        logger.critical(
            "Brain-State konnte nicht fail-closed geloest werden - "
            "/brain/feedback kann in das geschlossene Projekt schreiben",
            exc_info=True,
        )
        return

    if not cleaned_up:
        logger.critical(
            "Brain-State-Bindung wurde gekappt, der Slot konnte aber nicht "
            "unter dem Lock aufgeraeumt werden - die state.db-Verbindung "
            "bleibt offen und haelt die Datei unter Windows fest"
        )
