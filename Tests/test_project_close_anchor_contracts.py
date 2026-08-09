from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import _brain_singleton
from backend.app_state import AppState
from backend.routers.project_router import AnchorEntry, close_project, set_anchors


def _project_state(tmp_path: Path) -> AppState:
    state = AppState()
    state.current_project = {
        "name": "Project A",
        "path": str(tmp_path),
        "db_project_id": 7,
    }
    return state


def test_close_does_not_report_success_when_brain_unbind_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _project_state(tmp_path)

    def fail_unbind() -> None:
        raise RuntimeError("unbind failed")

    monkeypatch.setattr(_brain_singleton, "clear_project_state", fail_unbind)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(close_project(state))

    assert exc.value.status_code == 500
    assert state.current_project is not None
    assert state.current_project["db_project_id"] == 7


def test_anchor_publish_is_blocked_after_project_epoch_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _project_state(tmp_path)
    original_write_text = Path.write_text

    def write_then_switch(path: Path, *args, **kwargs):
        result = original_write_text(path, *args, **kwargs)
        if path.name.endswith(".tmp"):
            state.invalidate_project_context()
        return result

    monkeypatch.setattr(Path, "write_text", write_then_switch)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(set_anchors([AnchorEntry(time=2.0, label="cut")], state))

    assert exc.value.status_code == 409
    assert not (tmp_path / "anchors.json").exists()
    assert not list(tmp_path.glob(".anchors.json.*.tmp"))
