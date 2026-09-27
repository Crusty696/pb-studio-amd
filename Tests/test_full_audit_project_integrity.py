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
