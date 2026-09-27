"""Regressions for same-path media refresh and truthful project counters."""

from backend.app_state import AppState


def test_same_path_audio_import_refreshes_hash_and_probe_metadata(tmp_path, monkeypatch):
    from pb_studio.data.repositories.media_repository import MediaRepository

    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}
    repo = MediaRepository()
    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: repo,
    )
    path = str(tmp_path / "mix.wav")
    first = state.register_audio_clip({
        "name": "mix", "path": path, "duration_seconds": 10.0,
        "sample_rate": 44100, "channels": 2, "format": "wav",
        "audio_hash": "old-hash",
    })
    state.set_audio_analysis(first["id"], {"bpm": 128.0, "_analysis_status": "completed"})

    refreshed = state.register_audio_clip({
        "name": "mix", "path": path, "duration_seconds": 12.0,
        "sample_rate": 48000, "channels": 1, "format": "wav",
        "audio_hash": "new-hash",
    })

    assert refreshed["id"] == first["id"]
    assert refreshed["audio_hash"] == "new-hash"
    assert refreshed["duration_seconds"] == 12.0
    assert refreshed["is_analyzed"] is False
    assert state.get_audio_analysis(first["id"]) is None
    row = repo.find_by_project_and_path(1, path)
    assert row["file_hash"] == "new-hash"
    assert row["duration_sec"] == 12.0
    assert row["ai_data_json"] is None


def test_same_path_video_import_refreshes_hash_and_probe_metadata(tmp_path, monkeypatch):
    from pb_studio.data.repositories.media_repository import MediaRepository

    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}
    repo = MediaRepository()
    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: repo,
    )
    path = str(tmp_path / "clip.mp4")
    first = state.register_video_clip({
        "name": "clip", "path": path, "duration_seconds": 10.0,
        "width": 1920, "height": 1080, "fps": 30.0, "codec": "h264",
        "video_hash": "old-hash",
    })
    state.set_video_analysis(first["id"], {"tags": ["old"], "status": "completed"})

    refreshed = state.register_video_clip({
        "name": "clip", "path": path, "duration_seconds": 12.0,
        "width": 1280, "height": 720, "fps": 25.0, "codec": "hevc",
        "video_hash": "new-hash",
    })

    assert refreshed["id"] == first["id"]
    assert refreshed["video_hash"] == "new-hash"
    assert refreshed["duration_seconds"] == 12.0
    assert refreshed["tags"] == []
    assert state.get_video_analysis(first["id"]) is None
    row = repo.find_by_project_and_path(1, path)
    assert row["file_hash"] == "new-hash"
    assert row["duration_sec"] == 12.0
    assert row["ai_data_json"] is None


class _PersistedMediaFixture:
    def __init__(self, *, clip_type: str, path: str, clip_id: int):
        import json

        hash_key = "audio_hash" if clip_type == "audio" else "video_hash"
        self.row = {
            "id": 71,
            "file_path": path,
            "file_hash": "old-hash",
            "duration_sec": 10.0,
            "metadata_json": json.dumps({
                "clip_type": clip_type,
                "clip_id": clip_id,
                "name": "old-name",
                hash_key: "old-hash",
            }),
            "ai_data_json": json.dumps({"analysis_status": "completed"}),
            "status": "completed",
        }

    def find_by_project_and_path(self, project_id, file_path):
        return dict(self.row) if file_path == self.row["file_path"] else None

    def add_media(self, project_id, file_path, file_hash, duration, meta=None):
        import json

        if file_hash != self.row["file_hash"]:
            self.row["ai_data_json"] = None
            self.row["status"] = "pending"
        self.row.update({
            "file_hash": file_hash,
            "duration_sec": duration,
            "metadata_json": json.dumps(meta or {}),
        })
        return self.row["id"]

    def invalidate_analysis(self, media_id):
        assert media_id == self.row["id"]
        self.row["ai_data_json"] = None
        self.row["status"] = "pending"


def test_reloaded_audio_same_path_compares_fresh_hash_before_reuse(
    tmp_path, monkeypatch,
):
    path = str(tmp_path / "mix.wav")
    repo = _PersistedMediaFixture(clip_type="audio", path=path, clip_id=7)
    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: repo,
    )
    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}

    refreshed = state.register_audio_clip({
        "id": None, "name": "mix", "path": path, "duration_seconds": 12.0,
        "sample_rate": 48000, "channels": 1, "format": "wav",
        "audio_hash": "new-hash", "is_analyzed": False,
        "has_audio_embedding": False,
    })

    assert refreshed["id"] == 7
    assert refreshed["audio_hash"] == "new-hash"
    assert refreshed["duration_seconds"] == 12.0
    assert refreshed["is_analyzed"] is False
    assert repo.row["file_hash"] == "new-hash"
    assert repo.row["ai_data_json"] is None
    assert repo.row["status"] == "pending"


def test_reloaded_video_same_path_compares_fresh_hash_before_reuse(
    tmp_path, monkeypatch,
):
    path = str(tmp_path / "clip.mp4")
    repo = _PersistedMediaFixture(clip_type="video", path=path, clip_id=8)
    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: repo,
    )
    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}

    refreshed = state.register_video_clip({
        "id": None, "name": "clip", "path": path, "duration_seconds": 12.0,
        "width": 1280, "height": 720, "fps": 25.0, "codec": "hevc",
        "video_hash": "new-hash", "has_video_embedding": False,
    })

    assert refreshed["id"] == 8
    assert refreshed["video_hash"] == "new-hash"
    assert refreshed["duration_seconds"] == 12.0
    assert "stage_status" not in refreshed
    assert refreshed["is_analyzed"] is False
    assert refreshed["tags"] == []
    assert repo.row["file_hash"] == "new-hash"
    assert repo.row["ai_data_json"] is None
    assert repo.row["status"] == "pending"


def test_reloaded_audio_with_unknown_hash_does_not_trust_legacy_ai_data(
    tmp_path, monkeypatch,
):
    import json

    path = str(tmp_path / "legacy.wav")
    repo = _PersistedMediaFixture(clip_type="audio", path=path, clip_id=9)
    repo.row["file_hash"] = ""
    metadata = json.loads(repo.row["metadata_json"])
    metadata["audio_hash"] = None
    repo.row["metadata_json"] = json.dumps(metadata)
    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: repo,
    )
    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}

    refreshed = state.register_audio_clip({
        "id": None, "name": "legacy", "path": path, "duration_seconds": 12.0,
        "sample_rate": 44100, "channels": 2, "format": "wav",
        "audio_hash": None, "is_analyzed": False,
        "has_audio_embedding": False,
    })

    assert refreshed["is_analyzed"] is False
    assert repo.row["file_hash"] == ""
    assert repo.row["ai_data_json"] is None
    assert repo.row["status"] == "pending"
