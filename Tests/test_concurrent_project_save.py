"""Haertung: die Stage-Dateinamen im Save-Pfad muessen eindeutig und versteckt sein.

Kein Rennen-Nachweis. ``_save_project_in_context`` ist synchron und laeuft
einprozessig im Event-Loop-Thread, kann also heute gar nicht verschraenken.
Diese Tests messen nur das beobachtbare Verhalten der Namensvergabe, damit ein
spaeteres ``await``, ein Threadpool oder mehrere uvicorn-Worker nicht auf einen
festen Dateinamen treffen. Vorbild ist ``set_anchors`` in derselben Datei.
"""

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app_state import AppState, get_app_state
from backend.main import app
from pb_studio.data.repositories.project_repository import ProjectRepository


@pytest.fixture
def fresh_state():
    state = AppState()
    app.dependency_overrides[get_app_state] = lambda: state
    yield state
    app.dependency_overrides.clear()


@pytest.fixture
def client(fresh_state):
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_project_db_lookup(monkeypatch):
    """Haelt die Projekt-DB aus dem Test heraus (Muster aus test_project_persistence)."""
    records: dict[int, dict] = {}
    next_id = {"value": 900}

    def fake_find(project_path: Path) -> int | None:
        normalized = str(project_path.resolve())
        for project_id, record in records.items():
            if record["path"] == normalized:
                return project_id
        return None

    def fake_find_or_create(project_path: Path, project_name: str, meta: dict | None = None) -> int:
        existing = fake_find(project_path)
        if existing is not None:
            return existing
        project_id = next_id["value"]
        next_id["value"] += 1
        records[project_id] = {"path": str(project_path.resolve()), "owner_token": None}
        return project_id

    def fake_create_owned(_repo, _name: str, data: dict, owner_token: str) -> int:
        project_id = next_id["value"]
        next_id["value"] += 1
        records[project_id] = {
            "path": str(Path(data["path"]).resolve()),
            "owner_token": owner_token,
        }
        return project_id

    def fake_update(_repo, project_id: int, name=None, data=None):
        if project_id not in records:
            raise LookupError(f"Projekt {project_id} existiert nicht mehr")
        if data and data.get("path"):
            records[project_id]["path"] = str(Path(data["path"]).resolve())

    module = importlib.import_module("backend.routers.project_router")
    monkeypatch.setattr(module, "_find_or_create_project_db_record", fake_find_or_create)
    monkeypatch.setattr(module, "_find_project_db_record_id", fake_find)
    monkeypatch.setattr(ProjectRepository, "create_owned_project", fake_create_owned)
    monkeypatch.setattr(ProjectRepository, "update_project", fake_update)
    return records


@pytest.fixture
def recorded_writes(monkeypatch):
    """Zeichnet jeden Path.write_text/write_bytes-Zielpfad auf."""
    seen: list[Path] = []
    real_text = Path.write_text
    real_bytes = Path.write_bytes

    def spy_text(self, *args, **kwargs):
        seen.append(Path(self))
        return real_text(self, *args, **kwargs)

    def spy_bytes(self, *args, **kwargs):
        seen.append(Path(self))
        return real_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy_text)
    monkeypatch.setattr(Path, "write_bytes", spy_bytes)
    return seen


def _prepare_project(client, fresh_state, tmp_path, monkeypatch, name: str) -> Path:
    from backend.config import config

    monkeypatch.setattr(config, "project_dir", tmp_path)
    assert client.post("/project/create", json={"name": name, "path": str(tmp_path)}).status_code == 200

    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"video")
    fresh_state.video_clips[1] = {
        "id": 1,
        "path": str(video_file),
        "name": "clip",
        "duration_seconds": 1.5,
    }
    fresh_state.set_timeline([
        {
            "clip_id": "clip_1",
            "clip_name": "clip",
            "file_path": str(video_file),
            "start_time": 0.0,
            "end_time": 1.5,
        }
    ])
    return tmp_path / name


def _stage_names(seen: list[Path], scope: Path) -> list[str]:
    """Nur Schreibvorgaenge im Projektverzeichnis auswerten.

    Der Spy patcht ``Path.write_text``/``write_bytes`` prozessweit und sieht
    damit auch fremde Threads. Im Repo existieren Writer mit FESTEN
    ``.tmp``-Namen (z.B. ``brain/feedback_logger.py``); feuert einer davon
    waehrend des Tests, schluege die Namenspruefung fehl und zeigte
    faelschlich auf den Save-Pfad.
    """
    scope_resolved = scope.resolve()
    return [
        p.name for p in seen
        if p.name.endswith(".tmp") and p.parent.resolve() == scope_resolved
    ]


def test_stage_filenames_are_unique_and_hidden_per_save(
    client, fresh_state, tmp_path, monkeypatch, recorded_writes
):
    """Zwei Saves duerfen keinen Stage-Dateinamen teilen; alle sind versteckt."""
    project_path = _prepare_project(client, fresh_state, tmp_path, monkeypatch, "StageNames")

    recorded_writes.clear()
    assert client.post("/project/save").status_code == 200
    first = _stage_names(recorded_writes, project_path)

    recorded_writes.clear()
    assert client.post("/project/save").status_code == 200
    second = _stage_names(recorded_writes, project_path)

    assert first, "Save hat keine Stage-Datei geschrieben - Test misst nichts"
    assert second

    # Versteckt, wie bei set_anchors.
    for name in first + second:
        assert name.startswith("."), f"Stage-Datei nicht versteckt: {name}"

    # Innerhalb eines Saves eindeutig ...
    assert len(set(first)) == len(first)
    assert len(set(second)) == len(second)
    # ... und zwischen zwei Saves ueberschneidungsfrei.
    assert not (set(first) & set(second)), (
        f"Stage-Dateinamen wiederverwendet: {sorted(set(first) & set(second))}"
    )


def test_successful_save_leaves_no_tmp_files_behind(
    client, fresh_state, tmp_path, monkeypatch
):
    project_path = _prepare_project(client, fresh_state, tmp_path, monkeypatch, "NoLeftovers")

    assert client.post("/project/save").status_code == 200

    leftovers = [p.name for p in project_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], f"Stage-Dateien nicht aufgeraeumt: {leftovers}"
    assert json.loads((project_path / "project.json").read_text(encoding="utf-8"))["name"] == "NoLeftovers"


def test_rollback_intermediate_path_is_unique_and_hidden(tmp_path, recorded_writes):
    """``_restore_file_snapshot`` darf keinen festen Zwischenpfad benutzen."""
    module = importlib.import_module("backend.routers.project_router")

    target = tmp_path / "project.json"
    target.write_bytes(b"neu")

    recorded_writes.clear()
    module._restore_file_snapshot(target, b"alt-1")
    first = _stage_names(recorded_writes, tmp_path)

    recorded_writes.clear()
    module._restore_file_snapshot(target, b"alt-2")
    second = _stage_names(recorded_writes, tmp_path)

    assert len(first) == 1 and len(second) == 1
    assert first[0].startswith("."), f"Rollback-Zwischenpfad nicht versteckt: {first[0]}"
    assert second[0].startswith(".")
    assert first[0] != second[0], f"Rollback-Zwischenpfad wiederverwendet: {first[0]}"
    assert target.read_bytes() == b"alt-2"


def test_project_meta_stage_path_is_unique_and_hidden(tmp_path, recorded_writes):
    """``_write_project_meta`` muss dieselbe Stage-Konvention benutzen.

    ``with_suffix(".tmp")`` ERSETZT die Endung: aus ``project.json`` wurde
    ``project.tmp`` - fest benannt und sichtbar.
    """
    module = importlib.import_module("backend.routers.project_router")

    recorded_writes.clear()
    module._write_project_meta(tmp_path, {"name": "A"})
    first = _stage_names(recorded_writes, tmp_path)

    recorded_writes.clear()
    module._write_project_meta(tmp_path, {"name": "B"})
    second = _stage_names(recorded_writes, tmp_path)

    assert len(first) == 1 and len(second) == 1
    assert first[0].startswith("."), f"Meta-Stage nicht versteckt: {first[0]}"
    assert first[0].startswith(".project.json."), (
        f"Meta-Stage haengt die Endung nicht an: {first[0]}"
    )
    assert first[0] != second[0], f"Meta-Stage wiederverwendet: {first[0]}"
    assert json.loads((tmp_path / "project.json").read_text(encoding="utf-8"))["name"] == "B"
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []
