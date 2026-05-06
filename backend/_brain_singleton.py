"""BrainService accessor for FastAPI routers (Plan Phase 4).

Single-process singleton. Project state.db is bound when the app sets the
current project; brain_router falls back to a 409 if not bound yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pb_studio.brain.brain_service import BrainService

_PROJECT_STATE_PATH: Optional[Path] = None


def get_brain_service() -> BrainService:
    return BrainService.get()


def set_project_state(path: str | Path) -> None:
    global _PROJECT_STATE_PATH
    _PROJECT_STATE_PATH = Path(path)
    BrainService.get().bind_project_state(_PROJECT_STATE_PATH)


def current_project_state_path() -> Optional[Path]:
    return _PROJECT_STATE_PATH
