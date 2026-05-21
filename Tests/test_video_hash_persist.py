"""Regression-Test: video_hash wird persistiert + reloaded (L-VIDEO-3 / CD-3 / X4).

Vorher: persist_video_clip schrieb file_hash="" hardcoded, load_from_db ignorierte
video_hash. EmbeddingCache-Hit-Rate war 0% nach Restart, L-N3 CACHED-Badge zeigte
nie CACHED nach Reload.

Fix: persist_video_clip schreibt meta["video_hash"] + repo.add_media(file_hash=...).
load_from_db liest meta.video_hash (oder fallback row.file_hash) zurueck.
"""

import pytest


def test_persist_video_clip_meta_contains_video_hash(monkeypatch):
    """Unit: persist_video_clip baut meta-dict mit video_hash + ruft add_media
    mit file_hash=video_hash auf (statt hardcoded "")."""
    from backend.app_state import AppState

    state = AppState()
    captured = {}

    class FakeRepo:
        def add_media(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: FakeRepo(),
    )
    monkeypatch.setattr(state, "get_current_project_db_id", lambda: 1)

    clip = {"id": 5, "name": "x.mp4", "path": "/x.mp4",
            "duration_seconds": 1.0, "video_hash": "deadbeef"}
    state.persist_video_clip(clip)

    assert captured.get("file_hash") == "deadbeef", \
        "file_hash arg muss video_hash sein, nicht hardcoded ''"
    meta = captured.get("meta", {})
    assert meta.get("video_hash") == "deadbeef", \
        "meta['video_hash'] muss video_hash enthalten"


def test_load_from_db_restores_video_hash(monkeypatch, tmp_path):
    """Unit: load_from_db liest video_hash aus meta zurueck ins clip-dict.

    Simuliert DB-Row mit metadata_json + file_hash, prueft dass load_from_db
    den video_hash aus meta (oder fallback file_hash) restored.
    """
    import json
    from backend.app_state import AppState

    state = AppState()
    state.reset()

    # Fake video file path (Path.exists() check muss True liefern)
    fake_video = tmp_path / "test.mp4"
    fake_video.write_bytes(b"\x00\x00\x00\x20\x66\x74\x79\x70")

    HASH = "abc123def456"
    meta = {
        "clip_type": "video", "clip_id": 1, "name": "test.mp4",
        "width": 1920, "height": 1080, "fps": 30.0, "codec": "h264",
        "video_hash": HASH,
    }
    fake_row = {
        "id": 99,
        "file_path": str(fake_video),
        "file_hash": HASH,
        "duration_sec": 10.0,
        "metadata_json": json.dumps(meta),
        "ai_data_json": "{}",
    }

    class FakeRepo:
        def __init__(self): pass
        def get_by_project(self, project_id): return [fake_row]
        def delete_media(self, media_id): pass

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        lambda: FakeRepo(),
    )

    state.load_from_db(project_id=1)

    reloaded = state.get_video_clip(1)
    assert reloaded is not None, "load_from_db hat Video-Clip nicht restored"
    assert reloaded.get("video_hash") == HASH, (
        f"video_hash nicht persistiert/reloaded - bekam {reloaded.get('video_hash')}, "
        f"erwartet {HASH}. L-VIDEO-3 regression!"
    )
