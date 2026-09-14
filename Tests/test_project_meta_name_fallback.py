"""Ein project.json mit "name": null darf ein Projekt nicht unoeffenbar machen.

Review 2026-08-29 zu 00f2c23: alle drei Namensausdruecke in open_project nutzen
``meta.get("name", <fallback>)``. Der Default greift nur bei FEHLENDEM Schluessel
- ``{"name": None}.get("name", "X")`` liefert None. ProjectInfo verlangt einen
``str``; ein extern editiertes oder von Hand kopiertes project.json mit
``"name": null`` beendet den Endpunkt daher mit einer ValidationError, also
HTTP 500. Betroffen sind der Guard-Pfad, der Normalpfad und der Name des
DB-Records.
"""

import importlib
import json
from pathlib import Path

import pytest

from backend.app_state import AppState

project_router = importlib.import_module("backend.routers.project_router")


def _write_null_name(project_path: Path) -> None:
    meta_path = project_path / "project.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["name"] = None
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


class TestNullNameInProjectMeta:
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
        next_id = {"value": 700}

        def fake_find(project_path) -> int | None:
            normalized = str(Path(project_path).resolve())
            for project_id, record in records.items():
                if record["path"] == normalized:
                    return project_id
            return None

        def fake_find_or_create(project_path, project_name, meta=None) -> int:
            assert isinstance(project_name, str) and project_name, (
                "Der DB-Record wuerde ohne Namen angelegt"
            )
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

    def test_normal_path_falls_back_to_the_folder_name(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        for name in ("Alpha", "Beta"):
            assert client.post(
                "/project/create", json={"name": name, "path": str(tmp_path)}
            ).status_code == 200
        # Beta ist aktiv, Alpha laeuft also durch den Normalpfad.
        _write_null_name(tmp_path / "Alpha")

        response = client.post(
            "/project/open", json={"path": str(tmp_path / "Alpha")}
        )

        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Alpha"

    def test_guard_path_falls_back_to_the_active_project_name(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"
        _write_null_name(project_path)

        response = client.post("/project/open", json={"path": str(project_path)})

        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Alpha"
