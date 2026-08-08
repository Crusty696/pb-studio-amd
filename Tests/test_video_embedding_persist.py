"""Test: embedding_dim + embedding_samples werden persistiert (L-M8).

Audit L-M8: embedding_dim + embedding_samples kamen im Video-Analyse
Response zurueck, wurden aber nirgends in app_state.video_analysis_cache
persistiert. Reload zeigte 0.
"""

import pytest


def _state_with_video(tmp_path, clip_id: int):
    from backend.app_state import AppState

    video_path = tmp_path / f"test-{clip_id}.mp4"
    video_path.write_bytes(b"video")
    state = AppState(current_project={
        "name": "EmbeddingTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    clip = {
        "id": clip_id,
        "name": f"test-{clip_id}",
        "path": str(video_path),
        "duration_seconds": 10.0,
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(clip_id, clip)
    return state


def test_app_state_persists_embedding_meta(tmp_path):
    """update_video_analysis nimmt embedding_dim+samples als kwargs entgegen
    und persistiert sie in den In-Memory Cache + setzt has_embedding=True."""
    state = _state_with_video(tmp_path, 1)
    state.update_video_analysis(clip_id=1, embedding_dim=1152, embedding_samples=10)
    analysis = state.get_video_analysis(1)
    assert analysis is not None
    assert analysis.get("embedding_dim") == 1152
    assert analysis.get("embedding_samples") == 10
    assert analysis.get("has_embedding") is True


def test_app_state_no_embedding_sets_zero(tmp_path):
    """embedding_dim=0 -> has_embedding=False."""
    state = _state_with_video(tmp_path, 2)
    state.update_video_analysis(clip_id=2, embedding_dim=0, embedding_samples=0)
    analysis = state.get_video_analysis(2)
    assert analysis is not None
    assert analysis.get("embedding_dim") == 0
    assert analysis.get("embedding_samples") == 0
    assert analysis.get("has_embedding") is False


def test_video_clip_info_schema_has_embedding_fields():
    """VideoClipInfo Schema enthaelt embedding_dim/embedding_samples/has_embedding."""
    from backend.schemas.video_schemas import VideoClipInfo
    info = VideoClipInfo(id=1, name="test", path="/tmp/test.mp4", duration_seconds=10.0)
    assert hasattr(info, "embedding_dim")
    assert hasattr(info, "embedding_samples")
    assert hasattr(info, "has_embedding")
    assert info.has_embedding is False  # default


def test_video_analysis_result_has_embedding_samples():
    """VideoAnalysisResult enthaelt embedding_samples Feld (embedding_dim existiert bereits)."""
    from backend.schemas.video_schemas import VideoAnalysisResult
    result = VideoAnalysisResult(clip_id=1)
    assert hasattr(result, "embedding_dim")
    assert hasattr(result, "embedding_samples")
    assert result.embedding_dim == 0
    assert result.embedding_samples == 0


def test_update_video_analysis_partial_signature(tmp_path):
    """update_video_analysis akzeptiert ALLE Parameter optional (M8: angeglichen an update_audio_analysis).

    Vorher waren scene_count/avg_motion/has_embedding/is_analyzed positional-required.
    Nach M8 sind alle optional damit partielle Updates (nur embedding-meta) moeglich sind.
    """
    state = _state_with_video(tmp_path, 3)
    # Aufruf nur mit clip_id darf nicht crashen
    state.update_video_analysis(clip_id=3)
    # Aufruf nur mit embedding-Feldern darf nicht crashen
    state.update_video_analysis(clip_id=3, embedding_dim=512, embedding_samples=4)
    analysis = state.get_video_analysis(3)
    assert analysis is not None
    assert analysis.get("embedding_dim") == 512
    assert analysis.get("embedding_samples") == 4
    assert analysis.get("has_embedding") is True
