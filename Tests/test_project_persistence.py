import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app_state import AppState, get_app_state
from backend.main import app


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

        def fake_find_or_create(project_path: Path, project_name: str, meta: dict | None = None) -> int:
            key = str(project_path.resolve())
            if key not in records:
                records[key] = next_id["value"]
                next_id["value"] += 1
            return records[key]

        project_router_module = importlib.import_module("backend.routers.project_router")
        monkeypatch.setattr(project_router_module, "_find_or_create_project_db_record", fake_find_or_create)
        return records

    def test_create_save_open_roundtrip_persists_timeline_metadata(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)

        create_response = client.post("/project/create", json={"name": "Roundtrip", "path": str(tmp_path)})
        assert create_response.status_code == 200

        audio_file = tmp_path / "roundtrip.mp3"
        audio_file.write_bytes(b"ID3")
        fresh_state.audio_clips[1] = {"id": 1, "path": str(audio_file), "name": "roundtrip"}
        fresh_state.current_audio_path = str(audio_file)
        fresh_state.set_timeline([
            {
                "clip_id": "1",
                "clip_name": "roundtrip",
                "file_path": str(audio_file),
                "start_time": 0.0,
                "end_time": 1.5,
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 1.0,
            }
        ])

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
        assert fresh_state.current_timeline[0]["metadata"]["file_path"] == str(audio_file)

    def test_roundtrip_timeline_endpoint_restores_flat_fields_after_reopen(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        client.post("/project/create", json={"name": "Roundtrip", "path": str(tmp_path)})

        audio_file = tmp_path / "roundtrip.mp3"
        audio_file.write_bytes(b"ID3")
        fresh_state.current_audio_path = str(audio_file)
        fresh_state.set_timeline([
            {
                "clip_id": "1",
                "clip_name": "roundtrip",
                "file_path": str(audio_file),
                "start_time": 0.0,
                "end_time": 1.5,
                "clip_start": 0.25,
                "trigger_type": "beat",
                "trigger_strength": 1.0,
            }
        ])

        assert client.post("/project/save").status_code == 200
        assert client.post("/project/close").status_code == 200
        assert client.post("/project/open", json={"path": str(tmp_path / "Roundtrip")}).status_code == 200

        timeline_response = client.get("/pacing/timeline")
        assert timeline_response.status_code == 200
        entry = timeline_response.json()["entries"][0]
        assert entry["clip_name"] == "roundtrip"
        assert entry["file_path"] == str(audio_file)
        assert entry["clip_start"] == 0.25
        assert entry["trigger_type"] == "beat"

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

    def test_open_uses_project_specific_db_id_for_restore(self, client, tmp_path, fresh_state, monkeypatch):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        project_dir = tmp_path / "ProjectB"
        project_dir.mkdir()
        (project_dir / "project.json").write_text(json.dumps({"name": "ProjectB"}), encoding="utf-8")

        captured = []

        def fake_load_from_db(project_id=None):
            captured.append(project_id)

        fresh_state.load_from_db = fake_load_from_db

        response = client.post("/project/open", json={"path": str(project_dir)})

        assert response.status_code == 200
        assert captured == [100]
        assert fresh_state.current_project["db_project_id"] == 100

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
