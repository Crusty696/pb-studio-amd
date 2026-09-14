"""Die generierte Timeline darf beim Projektwechsel und beim Schliessen nicht verloren gehen.

Belegter Defekt: `state.set_timeline(...)` aus der Pacing-Engine schreibt nur in den
RAM. Einziger Produktions-Schreiber von timeline.json war `_save_project_in_context`.
`close_project` und `_activate_project` riefen `state.reset()` bzw. leerten den State,
ohne vorher zu persistieren.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

from backend import _brain_singleton
from backend.app_state import AppState
from backend.routers.project_router import (
    _load_timeline_into_state,
    close_project,
    persist_timeline_for_context,
)

project_router = importlib.import_module("backend.routers.project_router")


def _make_video_file(tmp_path: Path) -> Path:
    video = tmp_path / "clip_one.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return video


def _timeline_entries() -> list[dict]:
    """Kanonisches Runtime-Format: clip_id ist ein String, Zeitfelder start_time/end_time."""
    return [
        {
            "clip_id": "clip_1",
            "start_time": 0.0,
            "end_time": 2.5,
            "metadata": {"trigger_type": "beat"},
        },
        {
            "clip_id": "clip_1",
            "start_time": 2.5,
            "end_time": 5.0,
            "metadata": {"trigger_type": "beat"},
        },
    ]


def _state_with_timeline(tmp_path: Path, video: Path) -> AppState:
    state = AppState()
    state.current_project = {
        "name": tmp_path.name,
        "path": str(tmp_path),
        "db_project_id": 7,
    }
    state.video_clips[1] = {"id": 1, "path": str(video), "name": video.name}
    state.set_timeline(_timeline_entries())
    return state


def _reader_state(video: Path) -> AppState:
    reader = AppState()
    reader.video_clips[1] = {"id": 1, "path": str(video), "name": video.name}
    return reader


def _neutralize_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_brain_singleton, "clear_project_state", lambda: None)
    monkeypatch.setattr(
        _brain_singleton, "current_project_state_identity", lambda: None
    )


def test_persist_timeline_writes_reader_compatible_payload(tmp_path: Path) -> None:
    """Round-Trip: der echte Leser muss die geschriebene Datei wieder verstehen."""
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)

    assert persist_timeline_for_context(state, tmp_path) is True

    timeline_path = tmp_path / "timeline.json"
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "Der Leser erwartet ein Dict, keine nackte Liste"
    assert "timeline" in payload and "audio_path" in payload

    reader = _reader_state(video)
    assert _load_timeline_into_state(tmp_path, reader) is True
    loaded = reader.get_timeline_snapshot()
    assert len(loaded) == 2
    assert [entry["start_time"] for entry in loaded] == [0.0, 2.5]
    assert [entry["end_time"] for entry in loaded] == [2.5, 5.0]
    assert loaded[0]["clip_id"] == "clip_1"
    assert not list(tmp_path.glob(".timeline.json.*.tmp"))


def test_persist_timeline_returns_false_without_timeline(tmp_path: Path) -> None:
    state = AppState()
    assert persist_timeline_for_context(state, tmp_path) is False
    assert not (tmp_path / "timeline.json").exists()


def test_close_project_persists_timeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)
    _neutralize_brain(monkeypatch)

    asyncio.run(close_project(state))

    assert state.get_timeline_snapshot() == []
    reader = _reader_state(video)
    assert _load_timeline_into_state(tmp_path, reader) is True
    assert len(reader.get_timeline_snapshot()) == 2


def test_activate_project_persists_previous_timeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_a = tmp_path / "project-a"
    project_a.mkdir()
    project_b = tmp_path / "project-b"
    project_b.mkdir()
    video = _make_video_file(project_a)
    state = _state_with_timeline(project_a, video)
    monkeypatch.setattr(
        project_router, "_bind_brain_to_project", lambda *_a, **_kw: None
    )

    asyncio.run(
        project_router._activate_project(
            state,
            project_b,
            {"name": "project-b", "path": str(project_b), "db_project_id": 9},
            None,
        )
    )

    assert state.get_timeline_snapshot() == []
    assert not (project_b / "timeline.json").exists()
    reader = _reader_state(video)
    assert _load_timeline_into_state(project_a, reader) is True
    assert len(reader.get_timeline_snapshot()) == 2


def test_activate_project_skips_persist_when_reopening_same_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen desselben Projekts darf Datei und RAM nicht auseinanderlaufen lassen.

    open_project laedt die ALTE timeline.json in einen candidate_state, BEVOR
    _activate_project laeuft. Wuerde dort der neue RAM-Stand geschrieben, setzte
    install_project_state danach den alten Dateistand in den RAM zurueck - Datei
    und UI zeigten dann Verschiedenes. Es gibt keinen Same-Path-Guard in
    open_project, dieser Fall ist also real erreichbar.
    """
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)

    # Der Dateistand ist AELTER als der RAM-Stand (ein Cut statt zwei).
    old_on_disk = _timeline_entries()[:1]
    (tmp_path / "timeline.json").write_text(
        json.dumps({"audio_path": None, "timeline": old_on_disk}, ensure_ascii=False),
        encoding="utf-8",
    )
    candidate = _reader_state(video)
    assert _load_timeline_into_state(tmp_path, candidate) is True

    monkeypatch.setattr(
        project_router, "_bind_brain_to_project", lambda *_a, **_kw: None
    )

    asyncio.run(
        project_router._activate_project(
            state,
            tmp_path,
            {"name": tmp_path.name, "path": str(tmp_path), "db_project_id": 7},
            candidate,
        )
    )

    payload = json.loads((tmp_path / "timeline.json").read_text(encoding="utf-8"))
    assert len(payload["timeline"]) == 1, "Reopen darf die Datei nicht ueberschreiben"
    assert len(state.get_timeline_snapshot()) == 1
    assert len(state.get_timeline_snapshot()) == len(payload["timeline"])


def test_persist_timeline_skips_missing_project_directory(tmp_path: Path) -> None:
    """Ein extern geloeschter Projektordner darf nicht wiederauferstehen."""
    project_root = tmp_path / "geloescht"
    state = AppState()
    state.set_timeline(_timeline_entries())

    assert persist_timeline_for_context(state, project_root) is False
    assert not project_root.exists()


def test_persist_timeline_keeps_existing_file_when_timeline_empty(
    tmp_path: Path,
) -> None:
    """Leerer RAM-Stand loescht keine vorhandenen Nutzdaten (bewusste Asymmetrie zu /project/save)."""
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(
        json.dumps({"audio_path": None, "timeline": _timeline_entries()}),
        encoding="utf-8",
    )
    state = AppState()
    state.set_timeline([])

    assert persist_timeline_for_context(state, tmp_path) is False
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert len(payload["timeline"]) == 2


def test_close_project_succeeds_when_timeline_persist_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Schreibfehler darf das Schliessen nicht verhindern."""
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)
    _neutralize_brain(monkeypatch)

    def boom(*_args, **_kwargs) -> bool:
        raise OSError("Datentraeger voll")

    monkeypatch.setattr(project_router, "persist_timeline_for_context", boom)

    response = asyncio.run(close_project(state))

    assert response.success is True
    assert state.current_project is None
    assert state.get_timeline_snapshot() == []


class TestHasTimelineAfterUnsavedClose:
    """I-1: nach Close ohne /project/save meldete /project/open has_timeline=false,
    obwohl die Timeline geladen wurde. project.json bleibt in diesem Pfad bewusst
    unangetastet; die Wahrheit ist deshalb die tatsaechlich gelesene Datei."""

    @pytest.fixture
    def fresh_state(self):
        from backend.app_state import get_app_state
        from backend.main import app

        state = AppState()
        app.dependency_overrides[get_app_state] = lambda: state
        yield state
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self, fresh_state):
        from fastapi.testclient import TestClient
        from backend.main import app

        return TestClient(app)

    @pytest.fixture(autouse=True)
    def stub_project_db_lookup(self, monkeypatch):
        from pb_studio.data.repositories.project_repository import ProjectRepository

        records: dict[int, dict] = {}
        next_id = {"value": 500}

        def fake_find(project_path: Path) -> int | None:
            normalized = str(Path(project_path).resolve())
            for project_id, record in records.items():
                if record["path"] == normalized:
                    return project_id
            return None

        def fake_find_or_create(project_path: Path, project_name: str, meta=None) -> int:
            existing = fake_find(project_path)
            if existing is not None:
                return existing
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(project_path).resolve())}
            return project_id

        def fake_create_owned(_repo, _name: str, data: dict, _owner_token: str) -> int:
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(data["path"]).resolve())}
            return project_id

        def fake_update(_repo, project_id: int, name=None, data=None):
            return None

        monkeypatch.setattr(
            project_router, "_find_or_create_project_db_record", fake_find_or_create
        )
        monkeypatch.setattr(project_router, "_find_project_db_record_id", fake_find)
        monkeypatch.setattr(ProjectRepository, "create_owned_project", fake_create_owned)
        monkeypatch.setattr(ProjectRepository, "update_project", fake_update)
        return records

    def test_open_reports_timeline_that_was_saved_by_close(
        self,
        client,
        fresh_state,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        project_path = tmp_path / "Unsaved"
        assert client.post(
            "/project/create", json={"name": "Unsaved", "path": str(tmp_path)}
        ).status_code == 200

        video_file = project_path / "video" / "cut.mp4"
        video_file.write_bytes(b"video")
        fresh_state.video_clips[1] = {"id": 1, "path": str(video_file), "name": "cut"}
        fresh_state.set_timeline(_timeline_entries())

        def restore_catalog(self, project_id=None):  # noqa: ANN001
            self.video_clips[1] = {"id": 1, "path": str(video_file), "name": "cut"}
            return True

        monkeypatch.setattr(AppState, "load_from_db", restore_catalog)

        # Bewusst KEIN /project/save: der Nutzer schliesst direkt nach dem Pacing-Lauf.
        assert client.post("/project/close").status_code == 200
        meta = json.loads((project_path / "project.json").read_text(encoding="utf-8"))
        assert meta["has_timeline"] is False, "project.json bleibt in diesem Pfad stale"

        response = client.post("/project/open", json={"path": str(project_path)})
        assert response.status_code == 200
        assert len(fresh_state.get_timeline_snapshot()) == 2
        assert response.json()["has_timeline"] is True
