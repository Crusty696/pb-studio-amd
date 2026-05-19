"""Regression-Test fuer D-C1 (Audit 2026-05-19):
Vor Fix wrote update_audio_analysis nur in audio_analysis_cache, NICHT in
audio_clips → User sah inkonsistente Werte je nach Endpoint.

Fix: cache_update wird in audio_analysis_cache UND audio_clips parallel
geschrieben (analog video_analysis_cache + video_clips).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.app_state import AppState


@pytest.fixture
def state():
    AppState._instance = None  # reset singleton
    s = AppState()
    s.audio_clips.clear()
    s.audio_analysis_cache.clear()
    s.video_clips.clear()
    s.video_analysis_cache.clear()
    yield s


def test_update_audio_analysis_writes_to_audio_clips(state, tmp_path):
    """update_audio_analysis muss audio_clips[id] UND audio_analysis_cache[id] aktualisieren."""
    clip_id = 1
    state.audio_clips[clip_id] = {
        "id": clip_id,
        "path": "test.wav",
        "duration_seconds": 60.0,
        "bpm": 0.0,
        "key": "",
    }

    with patch("pb_studio.data.repositories.media_repository.MediaRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.get_by_id.return_value = {
            "id": 100,
            "metadata_json": "{}",
            "ai_data_json": "{}",
        }
        mock_repo.find_media.return_value = [{"id": 100, "metadata_json": "{}", "ai_data_json": "{}"}]
        mock_repo.update_status.return_value = None

        state.update_audio_analysis(
            clip_id=clip_id,
            bpm=128.5,
            key="C major",
            is_analyzed=True,
        )

    # audio_analysis_cache muss aktualisiert sein
    assert state.audio_analysis_cache[clip_id]["bpm"] == 128.5
    assert state.audio_analysis_cache[clip_id]["key"] == "C major"

    # D-C1 Fix: audio_clips muss ebenfalls aktualisiert sein
    assert state.audio_clips[clip_id]["bpm"] == 128.5, \
        "D-C1 Regression: audio_clips wurde nicht synchronisiert (bpm)"
    assert state.audio_clips[clip_id]["key"] == "C major", \
        "D-C1 Regression: audio_clips wurde nicht synchronisiert (key)"
    assert state.audio_clips[clip_id]["is_analyzed"] is True, \
        "D-C1 Regression: audio_clips.is_analyzed nicht synchronisiert"


def test_update_video_analysis_writes_to_video_clips(state):
    """update_video_analysis muss video_clips[id] UND video_analysis_cache[id] aktualisieren."""
    clip_id = 42
    state.video_clips[clip_id] = {
        "id": clip_id,
        "path": "test.mp4",
        "duration_seconds": 30.0,
        "scene_count": 0,
        "avg_motion": 0.0,
    }

    with patch("pb_studio.data.repositories.media_repository.MediaRepository") as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.get_by_id.return_value = {
            "id": 200,
            "metadata_json": "{}",
            "ai_data_json": "{}",
        }
        mock_repo.find_media.return_value = [{"id": 200, "metadata_json": "{}", "ai_data_json": "{}"}]
        mock_repo.update_status.return_value = None

        state.update_video_analysis(
            clip_id=clip_id,
            scene_count=12,
            avg_motion=0.5,
            is_analyzed=True,
        )

    # video_analysis_cache muss aktualisiert sein
    assert state.video_analysis_cache[clip_id].get("scene_count") == 12

    # D-C1 Fix: video_clips muss ebenfalls aktualisiert sein
    assert state.video_clips[clip_id].get("scene_count") == 12, \
        "D-C1 Regression: video_clips wurde nicht synchronisiert (scene_count)"
    assert state.video_clips[clip_id].get("avg_motion") == 0.5, \
        "D-C1 Regression: video_clips wurde nicht synchronisiert (avg_motion)"
