"""Das erneute Oeffnen des bereits offenen Projekts darf nichts verwerfen.

Audit 2026-08-29: open_project laedt die Datei-Timeline in einen candidate_state
und _activate_project ersetzt damit ueber install_project_state den kompletten
Laufzeitzustand - Timeline UND Analyse-Caches. Zeigt die Anfrage auf das bereits
offene Projekt, ist das kein Wechsel, sondern Datenverlust - gemessen:
RAM-Timeline 2 -> 0. Der Same-Path-Guard in _activate_project ueberspringt nur
das Persistieren, nicht den Austausch.
"""

import importlib
from pathlib import Path

import pytest

from backend.app_state import AppState

project_router = importlib.import_module("backend.routers.project_router")


def _timeline_entries():
    return [
        {"clip_id": "clip_1", "start_time": 0.0, "end_time": 2.0, "metadata": {}},
        {"clip_id": "clip_2", "start_time": 2.0, "end_time": 4.5, "metadata": {}},
    ]


class TestReopenIsANoOp:
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
        """Ohne diese Stubs schreibt der Test in die produktive Datenbank."""
        from pb_studio.data.repositories.project_repository import ProjectRepository

        records: dict[int, dict] = {}
        next_id = {"value": 500}

        def fake_find(project_path) -> int | None:
            normalized = str(Path(project_path).resolve())
            for project_id, record in records.items():
                if record["path"] == normalized:
                    return project_id
            return None

        def fake_find_or_create(project_path, project_name, meta=None) -> int:
            existing = fake_find(project_path)
            if existing is not None:
                return existing
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(project_path).resolve())}
            return project_id

        def fake_create_owned(_repo, _name, data, _owner_token) -> int:
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(data["path"]).resolve())}
            return project_id

        def fake_update(_repo, project_id, name=None, data=None):
            return None

        monkeypatch.setattr(
            project_router, "_find_or_create_project_db_record", fake_find_or_create
        )
        monkeypatch.setattr(project_router, "_find_project_db_record_id", fake_find)
        monkeypatch.setattr(ProjectRepository, "create_owned_project", fake_create_owned)
        monkeypatch.setattr(ProjectRepository, "update_project", fake_update)
        return records

    def test_reopen_keeps_the_unsaved_timeline_in_ram(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"

        # Ein Pacing-Lauf und eine Audioanalyse, die noch NICHT gespeichert sind.
        fresh_state.set_timeline(_timeline_entries())
        fresh_state.audio_analysis_cache[1] = {"bpm": 128.0}
        fresh_state.video_analysis_cache[1] = {"scenes": 7}

        response = client.post("/project/open", json={"path": str(project_path)})

        assert response.status_code == 200
        assert len(fresh_state.get_timeline_snapshot()) == 2, (
            "Reopen desselben Projekts hat den ungespeicherten RAM-Stand ersetzt"
        )
        # install_project_state ersetzt auch die Analyse-Caches. Eine verlorene
        # komplette Audioanalyse waere der zweite spuerbare Schaden.
        assert fresh_state.audio_analysis_cache == {1: {"bpm": 128.0}}, (
            "Reopen hat die ungespeicherte Audioanalyse verworfen"
        )
        assert fresh_state.video_analysis_cache == {1: {"scenes": 7}}, (
            "Reopen hat die ungespeicherte Videoanalyse verworfen"
        )
        assert response.json()["has_timeline"] is True
        assert response.json()["path"] == str(project_path)

    def test_reopen_does_not_load_the_project_from_disk(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """Der Guard muss VOR dem Laden greifen, nicht danach."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"
        fresh_state.set_timeline(_timeline_entries())

        def _must_not_run(*args, **kwargs):
            raise AssertionError(
                "open_project hat den Projektzustand geladen, obwohl das Projekt "
                "bereits offen ist - der Guard steht zu spaet"
            )

        monkeypatch.setattr(project_router, "_load_timeline_into_state", _must_not_run)

        assert client.post(
            "/project/open", json={"path": str(project_path)}
        ).status_code == 200

    def test_opening_a_different_project_still_loads_it(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """Der Guard darf nicht zu breit greifen."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        for name in ("Alpha", "Beta"):
            assert client.post(
                "/project/create", json={"name": name, "path": str(tmp_path)}
            ).status_code == 200

        # /project/create hat zuletzt Beta aktiviert - zurueck auf Alpha.
        assert client.post(
            "/project/open", json={"path": str(tmp_path / "Alpha")}
        ).status_code == 200

        seen = []
        real_loader = project_router._load_timeline_into_state

        def _record(project_path, target_state):
            seen.append(Path(project_path))
            return real_loader(project_path, target_state)

        monkeypatch.setattr(project_router, "_load_timeline_into_state", _record)

        response = client.post(
            "/project/open", json={"path": str(tmp_path / "Beta")}
        )

        assert response.status_code == 200
        assert seen == [tmp_path / "Beta"], (
            "Beim Oeffnen eines ANDEREN Projekts muss der Ladepfad weiterhin laufen"
        )

    def test_first_open_without_any_active_project_takes_the_normal_path(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """current_project is None darf den Guard nicht ausloesen."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"

        # Zustand wie beim frischen Backend-Start: nichts geoeffnet.
        fresh_state.current_project = None

        seen = []
        real_loader = project_router._load_timeline_into_state
        monkeypatch.setattr(
            project_router,
            "_load_timeline_into_state",
            lambda p, t: (seen.append(Path(p)), real_loader(p, t))[1],
        )

        assert client.post(
            "/project/open", json={"path": str(project_path)}
        ).status_code == 200
        assert seen == [project_path], (
            "Ohne aktives Projekt muss der normale Ladepfad laufen"
        )

    def test_active_project_without_path_takes_the_normal_path(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """Ein current_project ohne 'path' darf den Guard nicht ausloesen."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"

        fresh_state.current_project = {"name": "Alpha", "db_project_id": 500}

        seen = []
        real_loader = project_router._load_timeline_into_state
        monkeypatch.setattr(
            project_router,
            "_load_timeline_into_state",
            lambda p, t: (seen.append(Path(p)), real_loader(p, t))[1],
        )

        assert client.post(
            "/project/open", json={"path": str(project_path)}
        ).status_code == 200
        assert seen == [project_path], (
            "Ohne 'path' im current_project muss der normale Ladepfad laufen"
        )
