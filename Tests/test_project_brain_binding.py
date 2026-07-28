"""Atomic project-to-Brain state binding regressions."""
from __future__ import annotations

import json
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend._brain_singleton as brain_singleton
from backend.app_state import AppState, get_app_state
from backend.main import app
from fastapi.testclient import TestClient
from pb_studio.brain.brain_service import BrainService


def test_singleton_path_changes_only_after_successful_bind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    old_path = tmp_path / "old.db"
    new_path = tmp_path / "new.db"
    service = MagicMock()
    service.bind_project_state.side_effect = RuntimeError("bind failed")
    monkeypatch.setattr(
        brain_singleton.BrainService,
        "get",
        classmethod(lambda cls: service),
    )
    monkeypatch.setattr(brain_singleton, "_PROJECT_STATE_PATH", old_path)

    with pytest.raises(RuntimeError, match="bind failed"):
        brain_singleton.set_project_state(new_path)

    assert brain_singleton.current_project_state_path() == old_path


def test_failed_connection_initialization_preserves_old_connection(
    tmp_path: Path,
):
    service = BrainService.__new__(BrainService)
    old_connection = MagicMock()
    service.state_conn = old_connection

    with (
        patch("pb_studio.brain.brain_service.migrate"),
        patch(
            "pb_studio.brain.brain_service.sqlite3.connect",
            side_effect=RuntimeError("open failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="open failed"):
            service.bind_project_state(tmp_path / "new.db")

    assert service.state_conn is old_connection
    old_connection.close.assert_not_called()


def test_successful_connection_swap_closes_old_connection_after_init(
    tmp_path: Path,
):
    service = BrainService.__new__(BrainService)
    old_connection = MagicMock()
    new_connection = MagicMock()
    service.state_conn = old_connection

    with (
        patch("pb_studio.brain.brain_service.migrate"),
        patch(
            "pb_studio.brain.brain_service.sqlite3.connect",
            return_value=new_connection,
        ),
        patch("pb_studio.brain.brain_service.init_connection") as initialize,
    ):
        service.bind_project_state(tmp_path / "new.db")

    initialize.assert_called_once_with(new_connection)
    assert service.state_conn is new_connection
    old_connection.close.assert_called_once_with()


def test_open_bind_failure_preserves_previous_runtime_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend.config import config

    project_router = importlib.import_module("backend.routers.project_router")
    monkeypatch.setattr(config, "project_dir", tmp_path)
    monkeypatch.setattr(
        project_router,
        "_find_or_create_project_db_record",
        lambda *args, **kwargs: 200,
    )
    project_dir = tmp_path / "NewProject"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps({"name": "NewProject"}),
        encoding="utf-8",
    )

    state = AppState()
    old_project = {"name": "OldProject", "path": str(tmp_path / "OldProject")}
    state.current_project = dict(old_project)
    state.audio_clips[7] = {"id": 7, "path": "old.wav"}
    app.dependency_overrides[get_app_state] = lambda: state
    monkeypatch.setattr(
        brain_singleton,
        "set_project_state",
        MagicMock(side_effect=RuntimeError("state.db unavailable")),
    )

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/project/open",
                json={"path": str(project_dir)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert state.current_project == old_project
    assert state.audio_clips == {7: {"id": 7, "path": "old.wav"}}


def test_open_catalog_load_failure_preserves_previous_runtime_and_brain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend.config import config

    project_router = importlib.import_module("backend.routers.project_router")
    monkeypatch.setattr(config, "project_dir", tmp_path)
    monkeypatch.setattr(
        project_router,
        "_find_or_create_project_db_record",
        lambda *args, **kwargs: 202,
    )
    project_dir = tmp_path / "BrokenProject"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps({"name": "BrokenProject"}),
        encoding="utf-8",
    )

    state = AppState()
    old_project = {"name": "OldProject", "path": str(tmp_path / "OldProject")}
    state.current_project = dict(old_project)
    state.audio_clips[7] = {"id": 7, "path": "old.wav"}
    state.audio_analysis_cache[7] = {"bpm": 128.0}
    app.dependency_overrides[get_app_state] = lambda: state
    bind_brain = MagicMock()
    monkeypatch.setattr(brain_singleton, "set_project_state", bind_brain)
    monkeypatch.setattr(AppState, "load_from_db", lambda self, project_id=None: False)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/project/open",
                json={"path": str(project_dir)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert state.current_project == old_project
    assert state.audio_clips == {7: {"id": 7, "path": "old.wav"}}
    assert state.audio_analysis_cache == {7: {"bpm": 128.0}}
    bind_brain.assert_not_called()


def test_create_bind_failure_preserves_previous_runtime_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend.config import config

    project_router = importlib.import_module("backend.routers.project_router")
    monkeypatch.setattr(config, "project_dir", tmp_path)
    monkeypatch.setattr(
        project_router,
        "_find_or_create_project_db_record",
        lambda *args, **kwargs: 201,
    )

    state = AppState()
    old_project = {"name": "OldProject", "path": str(tmp_path / "OldProject")}
    state.current_project = dict(old_project)
    state.video_clips[9] = {"id": 9, "path": "old.mp4"}
    app.dependency_overrides[get_app_state] = lambda: state
    monkeypatch.setattr(
        brain_singleton,
        "set_project_state",
        MagicMock(side_effect=RuntimeError("state.db unavailable")),
    )

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/project/create",
                json={"name": "NewProject", "path": str(tmp_path)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert state.current_project == old_project
    assert state.video_clips == {9: {"id": 9, "path": "old.mp4"}}
