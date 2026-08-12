from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_UUID = "75efc170-823d-4874-962e-5e472becaf8f"


def _state(tmp_path: Path):
    from backend.app_state import AppState

    return AppState(
        current_project={
            "db_project_id": 7,
            "project_uuid": PROJECT_UUID,
            "path": str(tmp_path),
        }
    )


@pytest.mark.parametrize(
    "project_data",
    [
        None,
        {},
        {"db_project_id": None},
        {"db_project_id": ""},
        {"db_project_id": 0},
        {"db_project_id": -1},
        {"db_project_id": True},
        {"db_project_id": "invalid"},
        {"db_project_id": 1.1},
        {"db_project_id": 1.9},
        {"db_project_id": "1.0"},
        {"db_project_id": "+1"},
        {"db_project_id": "01"},
    ],
)
def test_resolve_project_db_id_has_no_project_one_fallback(project_data):
    from backend.app_state import (
        ProjectContextUnavailableError,
        resolve_project_db_id,
    )

    with pytest.raises(ProjectContextUnavailableError):
        resolve_project_db_id(project_data)


def test_capture_binds_uuid_catalog_id_root_and_epoch(tmp_path: Path):
    state = _state(tmp_path)

    context = state.capture_project_context()

    assert context.project_uuid == PROJECT_UUID
    assert context.project_id == 7
    assert context.project_root == tmp_path.resolve()
    assert context.epoch == 0


@pytest.mark.parametrize("project_uuid", [None, "", "not-a-uuid"])
def test_capture_rejects_missing_or_invalid_project_uuid(
    tmp_path: Path,
    project_uuid,
):
    from backend.app_state import ProjectContextUnavailableError

    state = _state(tmp_path)
    state.current_project["project_uuid"] = project_uuid

    with pytest.raises(ProjectContextUnavailableError, match="project_uuid"):
        state.capture_project_context()


def test_uuid_change_invalidates_context_even_when_id_root_and_epoch_match(
    tmp_path: Path,
):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)
    context = state.capture_project_context()
    state.current_project["project_uuid"] = "0e736c32-948c-4323-b9ba-0f9d50fa193f"

    assert state.is_project_context_current(context) is False
    with pytest.raises(ProjectContextChangedError):
        with state.project_commit(context):
            pass


def test_explicit_project_id_must_match_captured_identity(tmp_path: Path):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)

    with pytest.raises(ProjectContextChangedError):
        state.resolve_operation_context(project_id=8)

    context = state.resolve_operation_context(project_id=7)
    assert context.project_uuid == PROJECT_UUID


@pytest.mark.parametrize("value", [1.1, 1.9, "1.0", "+7", "07", True, 0, -1])
def test_explicit_project_id_rejects_noncanonical_values(tmp_path: Path, value):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)
    with pytest.raises(ProjectContextChangedError):
        state.resolve_operation_context(project_id=value)
