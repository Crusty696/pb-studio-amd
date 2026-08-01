import copy
import importlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

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


class TestProjectLifecyclePersistence:
    @pytest.fixture(autouse=True)
    def stub_project_db_lookup(self, monkeypatch):
        records = {}
        next_id = {"value": 100}

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
            records[project_id] = {
                "path": str(project_path.resolve()),
                "owner_token": None,
            }
            return project_id

        def fake_create_owned(_repo, _name: str, data: dict, owner_token: str) -> int:
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {
                "path": str(Path(data["path"]).resolve()),
                "owner_token": owner_token,
            }
            return project_id

        def fake_delete_owned(_repo, project_id: int, owner_token: str) -> bool:
            record = records.get(project_id)
            if record is None:
                return False
            if record["owner_token"] != owner_token:
                raise RuntimeError("ownership mismatch")
            del records[project_id]
            return True

        def fake_update(_repo, project_id: int, name=None, data=None):
            if project_id not in records:
                raise LookupError(f"Projekt {project_id} existiert nicht mehr")
            if data and data.get("path"):
                records[project_id]["path"] = str(Path(data["path"]).resolve())

        project_router_module = importlib.import_module("backend.routers.project_router")
        monkeypatch.setattr(project_router_module, "_find_or_create_project_db_record", fake_find_or_create)
        monkeypatch.setattr(project_router_module, "_find_project_db_record_id", fake_find)
        monkeypatch.setattr(ProjectRepository, "create_owned_project", fake_create_owned)
        monkeypatch.setattr(ProjectRepository, "delete_owned_project", fake_delete_owned)
        monkeypatch.setattr(ProjectRepository, "update_project", fake_update)
        return records

    def test_create_save_open_roundtrip_persists_timeline_metadata(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)

        create_response = client.post("/project/create", json={"name": "Roundtrip", "path": str(tmp_path)})
        assert create_response.status_code == 200

        audio_file = tmp_path / "roundtrip.mp3"
        video_file = tmp_path / "roundtrip.mp4"
        audio_file.write_bytes(b"ID3")
        video_file.write_bytes(b"video")
        fresh_state.audio_clips[1] = {"id": 1, "path": str(audio_file), "name": "roundtrip"}
        fresh_state.video_clips[1] = {
            "id": 1,
            "path": str(video_file),
            "name": "roundtrip-video",
            "duration_seconds": 1.5,
        }
        fresh_state.current_audio_path = str(audio_file)
        fresh_state.set_timeline([
            {
                "clip_id": "clip_1",
                "clip_name": "roundtrip",
                "file_path": str(video_file),
                "start_time": 0.0,
                "end_time": 1.5,
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 1.0,
            }
        ])
        def restore_catalog(self, project_id=None):
            self.audio_clips[1] = {
                "id": 1,
                "path": str(audio_file),
                "name": "roundtrip",
            }
            self.video_clips[1] = {
                "id": 1,
                "path": str(video_file),
                "name": "roundtrip-video",
                "duration_seconds": 1.5,
            }
            return True

        monkeypatch.setattr(AppState, "load_from_db", restore_catalog)

        save_response = client.post("/project/save")
        assert save_response.status_code == 200

        close_response = client.post("/project/close")
        assert close_response.status_code == 200

        open_response = client.post("/project/open", json={"path": str(tmp_path / "Roundtrip")})
        assert open_response.status_code == 200
        body = open_response.json()
        assert body["audio_count"] == 1
        assert body["has_timeline"] is True
        assert fresh_state.current_audio_path == str(audio_file)
        assert len(fresh_state.current_timeline) == 1
        assert fresh_state.current_timeline[0]["metadata"]["file_path"] == str(video_file)

    def test_roundtrip_timeline_endpoint_restores_flat_fields_after_reopen(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        client.post("/project/create", json={"name": "Roundtrip", "path": str(tmp_path)})

        audio_file = tmp_path / "roundtrip.mp3"
        video_file = tmp_path / "roundtrip.mp4"
        audio_file.write_bytes(b"ID3")
        video_file.write_bytes(b"video")
        fresh_state.audio_clips[1] = {
            "id": 1,
            "path": str(audio_file),
            "name": "roundtrip",
        }
        fresh_state.video_clips[1] = {
            "id": 1,
            "path": str(video_file),
            "name": "roundtrip-video",
            "duration_seconds": 1.5,
        }
        fresh_state.current_audio_path = str(audio_file)
        fresh_state.set_timeline([
            {
                "clip_id": "clip_1",
                "clip_name": "roundtrip",
                "file_path": str(video_file),
                "start_time": 0.0,
                "end_time": 1.5,
                "clip_start": 0.25,
                "trigger_type": "beat",
                "trigger_strength": 1.0,
            }
        ])
        def restore_catalog(self, project_id=None):
            self.audio_clips[1] = {
                "id": 1,
                "path": str(audio_file),
                "name": "roundtrip",
            }
            self.video_clips[1] = {
                "id": 1,
                "path": str(video_file),
                "name": "roundtrip-video",
                "duration_seconds": 1.5,
            }
            return True

        monkeypatch.setattr(AppState, "load_from_db", restore_catalog)

        assert client.post("/project/save").status_code == 200
        assert client.post("/project/close").status_code == 200
        assert client.post("/project/open", json={"path": str(tmp_path / "Roundtrip")}).status_code == 200

        timeline_response = client.get("/pacing/timeline")
        assert timeline_response.status_code == 200
        entry = timeline_response.json()["entries"][0]
        assert entry["clip_name"] == "roundtrip"
        assert entry["file_path"] == str(video_file)
        assert entry["clip_start"] == 0.25
        assert entry["trigger_type"] == "beat"

    def test_save_returns_error_when_project_db_sync_fails(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post("/project/create", json={"name": "SyncFailure", "path": str(tmp_path)}).status_code == 200
        project_path = tmp_path / "SyncFailure"
        meta_before = (project_path / "project.json").read_bytes()
        monkeypatch.setattr(fresh_state, "sync_project_db_record", MagicMock(return_value=False))

        response = client.post("/project/save")

        assert response.status_code == 500
        assert response.json()["detail"] == "Projektdateien/DB konnten nicht konsistent gespeichert werden"
        assert (project_path / "project.json").read_bytes() == meta_before
        assert not (project_path / "timeline.json").exists()

    def test_create_project_resets_stale_in_memory_state(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        fresh_state.audio_clips[1] = {"id": 1, "path": str(tmp_path / "old.mp3")}
        fresh_state.video_clips[2] = {"id": 2, "path": str(tmp_path / "old.mp4")}
        fresh_state.current_timeline = [{"clip_id": "2", "start_time": 0.0, "end_time": 1.0}]
        fresh_state.current_audio_path = str(tmp_path / "old.mp3")
        fresh_state.render_tasks["task-1"] = {"status": "running"}
        fresh_state.cancel_flags["task-1"] = False

        response = client.post("/project/create", json={"name": "FreshProject", "path": str(tmp_path)})

        assert response.status_code == 200
        assert fresh_state.audio_clips == {}
        assert fresh_state.video_clips == {}
        assert fresh_state.current_timeline == []
        assert fresh_state.current_audio_path is None
        assert fresh_state.render_tasks == {}
        # MEDIUM-015: reset() marks remaining cancel_flags as True (not clears) so
        # in-flight render threads see the cancellation signal after project reset.
        assert fresh_state.cancel_flags == {"task-1": True}

        project = response.json()
        assert project["audio_count"] == 0
        assert project["video_count"] == 0
        assert project["has_timeline"] is False

    def test_create_existing_project_returns_conflict_without_mutation(
        self,
        client,
        tmp_path,
        fresh_state,
        monkeypatch,
    ):
        from backend.config import config

        project_router = importlib.import_module("backend.routers.project_router")
        monkeypatch.setattr(config, "project_dir", tmp_path)
        create_owned = MagicMock(return_value=300)
        brain_bind = MagicMock()
        monkeypatch.setattr(ProjectRepository, "create_owned_project", create_owned)
        monkeypatch.setattr(project_router, "_bind_brain_to_project", brain_bind)

        project_dir = tmp_path / "ExistingProject"
        nested_dir = project_dir / "custom"
        nested_dir.mkdir(parents=True)
        (project_dir / "project.json").write_text('{"name":"Original"}', encoding="utf-8")
        (nested_dir / "sentinel.bin").write_bytes(b"keep-me")

        fresh_state.current_project = {
            "name": "OldProject",
            "path": str(tmp_path / "OldProject"),
            "db_project_id": 99,
        }
        fresh_state.audio_clips[7] = {"id": 7, "path": "old.wav"}
        fresh_state.video_clips[8] = {"id": 8, "path": "old.mp4"}
        fresh_state.current_timeline = [{"clip_id": "8", "start_time": 0.0, "end_time": 1.0}]
        state_before = copy.deepcopy(
            {
                "current_project": fresh_state.current_project,
                "audio_clips": fresh_state.audio_clips,
                "video_clips": fresh_state.video_clips,
                "timeline": fresh_state.current_timeline,
            }
        )
        entries_before = {
            (path.relative_to(project_dir), path.is_dir())
            for path in project_dir.rglob("*")
        }
        file_contents_before = {
            path.relative_to(project_dir): path.read_bytes()
            for path in project_dir.rglob("*")
            if path.is_file()
        }

        response = client.post(
            "/project/create",
            json={"name": "ExistingProject", "path": str(tmp_path)},
        )

        assert response.status_code == 409
        assert entries_before == {
            (path.relative_to(project_dir), path.is_dir())
            for path in project_dir.rglob("*")
        }
        assert file_contents_before == {
            path.relative_to(project_dir): path.read_bytes()
            for path in project_dir.rglob("*")
            if path.is_file()
        }
        assert fresh_state.current_project == state_before["current_project"]
        assert fresh_state.audio_clips == state_before["audio_clips"]
        assert fresh_state.video_clips == state_before["video_clips"]
        assert fresh_state.current_timeline == state_before["timeline"]
        create_owned.assert_not_called()
        brain_bind.assert_not_called()

    def test_concurrent_create_allows_exactly_one_success(
        self,
        client,
        tmp_path,
        monkeypatch,
    ):
        from backend.config import config

        project_router = importlib.import_module("backend.routers.project_router")
        monkeypatch.setattr(config, "project_dir", tmp_path)
        next_id = iter((301, 302))
        created: dict[int, str] = {}

        def create_owned(_name, _data, owner_token):
            project_id = next(next_id)
            created[project_id] = owner_token
            return project_id

        def delete_owned(project_id, owner_token):
            assert created[project_id] == owner_token
            del created[project_id]
            return True

        create_owned_mock = MagicMock(side_effect=create_owned)
        delete_owned_mock = MagicMock(side_effect=delete_owned)
        brain_bind = MagicMock()
        monkeypatch.setattr(ProjectRepository, "create_owned_project", create_owned_mock)
        monkeypatch.setattr(ProjectRepository, "delete_owned_project", delete_owned_mock)
        monkeypatch.setattr(project_router, "_bind_brain_to_project", brain_bind)
        start = threading.Barrier(2)

        def create():
            start.wait()
            return client.post(
                "/project/create",
                json={"name": "ConcurrentProject", "path": str(tmp_path)},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: create(), range(2)))

        statuses = sorted(response.status_code for response in responses)
        assert statuses == [200, 409], [response.json() for response in responses]
        assert (tmp_path / "ConcurrentProject" / "project.json").exists()
        assert create_owned_mock.call_count in {1, 2}
        assert delete_owned_mock.call_count == create_owned_mock.call_count - 1
        assert len(created) == 1
        brain_bind.assert_called_once()

    def test_open_uses_project_specific_db_id_for_restore(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        project_dir = tmp_path / "ProjectB"
        project_dir.mkdir()
        (project_dir / "project.json").write_text(json.dumps({"name": "ProjectB"}), encoding="utf-8")

        captured = []

        restored_audio = tmp_path / "restored.wav"
        restored_audio.write_bytes(b"RIFF")

        def fake_load_from_db(self, project_id=None):
            captured.append(project_id)
            self.audio_clips[8] = {"id": 8, "path": str(restored_audio)}
            return True

        monkeypatch.setattr(AppState, "load_from_db", fake_load_from_db)

        response = client.post("/project/open", json={"path": str(project_dir)})

        assert response.status_code == 200
        assert captured == [-1]
        assert fresh_state.current_project["db_project_id"] == 100
        assert fresh_state.audio_clips == {
            8: {"id": 8, "path": str(restored_audio)}
        }

    def test_load_from_db_replaces_old_in_memory_catalog_instead_of_merging(self, monkeypatch, tmp_path):
        existing_audio = tmp_path / "real.wav"
        existing_audio.write_bytes(b"RIFF")

        rows = [
            {
                "id": 11,
                "file_path": str(existing_audio),
                "duration_sec": 34.0,
                "metadata_json": json.dumps({
                    "clip_type": "audio",
                    "clip_id": 8,
                    "name": "real",
                    "sample_rate": 48000,
                    "channels": 1,
                    "format": "wav",
                }),
            },
        ]

        class FakeRepo:
            def get_by_project(self, project_id):
                assert project_id == 1
                return rows

            def delete_media(self, media_id):
                raise AssertionError("delete_media should not be called in this test")

        monkeypatch.setattr("pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo)

        state = AppState()
        state.audio_clips[999] = {"id": 999, "path": str(tmp_path / "stale.wav")}
        state.video_clips[777] = {"id": 777, "path": str(tmp_path / "stale.mp4")}
        state._audio_next_id = 1000
        state._video_next_id = 778

        state.load_from_db()

        assert list(state.audio_clips) == [8]
        assert state.audio_clips[8]["path"] == str(existing_audio)
        assert state.video_clips == {}
        assert state._audio_next_id == 9
        assert state._video_next_id == 1
