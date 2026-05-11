"""Test: thumbnail_available wird auf True gesetzt nach Thumbnail-Request (L-N7).

Audit L-N7: thumbnail_available war unklar ob persistiert. Nach
erfolgreichem /video/thumbnails/{id} soll der Flag im in-memory state
auf True gesetzt sein, damit list_clips den korrekten Wert ausgibt.

Hinweis: app_state.video_clips speichert dicts (nicht Objects). Die neue
Methode update_video_clip mutiert daher den dict-Eintrag.
"""

import pytest


def test_app_state_update_video_clip_sets_flag():
    """update_video_clip setzt thumbnail_available im in-memory state."""
    from backend.app_state import AppState
    state = AppState()
    state.set_video_clip(1, {
        "id": 1, "name": "test", "path": "/tmp/test.mp4",
        "duration_seconds": 10.0, "thumbnail_available": False,
    })
    state.update_video_clip(clip_id=1, thumbnail_available=True)
    clip = state.get_video_clip(1)
    assert clip is not None
    assert clip.get("thumbnail_available") is True


def test_app_state_update_video_clip_unknown_id_no_crash():
    """update_video_clip mit unbekannter clip_id wirft keinen Fehler."""
    from backend.app_state import AppState
    state = AppState()
    # Should not crash for unknown clip id
    state.update_video_clip(clip_id=999, thumbnail_available=True)
    # state bleibt leer
    assert state.get_video_clip(999) is None


def test_app_state_update_video_clip_multiple_fields():
    """update_video_clip kann mehrere Felder auf einmal setzen."""
    from backend.app_state import AppState
    state = AppState()
    state.set_video_clip(7, {
        "id": 7, "name": "multi", "path": "/tmp/multi.mp4",
        "duration_seconds": 5.0, "thumbnail_available": False, "tags": [],
    })
    state.update_video_clip(clip_id=7, thumbnail_available=True, tags=["sunset"])
    clip = state.get_video_clip(7)
    assert clip is not None
    assert clip.get("thumbnail_available") is True
    assert clip.get("tags") == ["sunset"]


def test_video_clip_info_has_thumbnail_available():
    """VideoClipInfo Schema enthaelt thumbnail_available, default False."""
    from backend.schemas.video_schemas import VideoClipInfo
    info = VideoClipInfo(id=1, name="test", path="/tmp/test.mp4", duration_seconds=10.0)
    assert hasattr(info, "thumbnail_available")
    assert info.thumbnail_available is False  # default
