"""BrainService accessor for FastAPI routers (Plan Phase 4).

Single-process singleton. Project state.db is bound when the app sets the
current project; brain_router falls back to a 409 if not bound yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pb_studio.brain.brain_service import (
    BrainProjectIdentity,
    BrainService,
    BrainStateLease,
)

_PROJECT_STATE_PATH: Optional[Path] = None


def get_brain_service() -> BrainService:
    return BrainService.get()


def set_project_state(
    path: str | Path,
    *,
    project_epoch: Optional[int] = None,
    project_id: Optional[int] = None,
) -> BrainProjectIdentity:
    global _PROJECT_STATE_PATH
    new_path = Path(path).resolve()
    identity_kwargs = {}
    if project_epoch is not None:
        identity_kwargs["project_epoch"] = project_epoch
    if project_id is not None:
        identity_kwargs["project_id"] = project_id
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
    """L-STATE-4: unbind state.db nach /project/close — verhindert dass
    /brain/feedback weiter in die alte state.db schreibt (Cross-Project-Leak).

    Wird vom project_router.close_project gerufen. Best-effort: schluckt
    Exceptions damit der App-Lifecycle nicht crashed."""
    global _PROJECT_STATE_PATH
    _PROJECT_STATE_PATH = None
    try:
        BrainService.get().unbind_project_state()
    except Exception:
        pass
