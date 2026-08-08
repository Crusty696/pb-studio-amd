"""Focused regressions for lossless, stage-aware video-analysis resume."""

from __future__ import annotations

import asyncio
import importlib
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.schemas.video_schemas import VideoAnalyzeRequest


def _existing_analysis() -> dict:
    return {
        "clip_id": 7,
        "scene_count": 1,
        "scenes": [
            {
                "start_time": 0.0,
                "end_time": 4.0,
                "scene_type": "cut",
                "confidence": None,
            }
        ],
        "avg_motion": 4.5,
        "motion": {
            "clip_id": 7,
            "avg_motion": 4.5,
            "peak_motion": 8.0,
            "motion_curve": [2.0, 8.0],
            "peak_frames": [],
            "motion_category": "low",
        },
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False,
        "dominant_colors": ["#112233"],
        "tags": ["concert", "stage"],
        "tag_source": "lmstudio:test-model",
        "audio_key": "8A",
        "mood_tags": ["dark"],
        "avg_brightness": 0.2,
        "avg_saturation": 0.4,
        "avg_color_temp": -0.3,
        "status": "partial",
        "analysis_status": "partial",
        "stage_status": {
            "scenes": "completed",
            "motion": "completed",
            "embedding": "failed",
            "colors": "completed",
            "captions": "completed",
            "audio_key": "completed",
        },
        "stage_errors": {"embedding": "previous SigLIP failure"},
    }


class _State:
    def __init__(self, path, analysis=None):
        self.clip = {
            "id": 7,
            "name": "resume",
            "path": str(path),
            "duration_seconds": 4.0,
            "video_hash": "hash-7",
        }
        self.analysis = deepcopy(analysis)

    def get_video_clip(self, clip_id):
        return self.clip if clip_id == 7 else None

    def get_video_analysis(self, clip_id):
        return deepcopy(self.analysis) if clip_id == 7 else None

    @contextmanager
    def project_commit(self, _context):
        yield


async def _noop(*_args, **_kwargs):
    return None


def test_partial_retry_runs_only_failed_embedding_and_preserves_completed_data(
    monkeypatch,
    tmp_path,
):
    video_router = importlib.import_module("backend.routers.video_router")

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    state = _State(media, _existing_analysis())
    calls = {"scenes": 0, "gpu": 0, "colors": 0, "persisted": None}

    def scene_stage(*_args, **_kwargs):
        calls["scenes"] += 1
        return {
            "scene_count": 0,
            "scenes": [],
            "stage_status": {"scenes": "skipped"},
            "stage_errors": {},
        }

    async def gpu_stage(_func, *_args, **_kwargs):
        calls["gpu"] += 1
        return {
            "avg_motion": 0.0,
            "motion": None,
            "embedding_dim": 1152,
            "embedding_samples": 3,
            "has_embedding": True,
            "stage_status": {"motion": "skipped", "embedding": "completed"},
            "stage_errors": {},
        }

    async def color_stage(*_args, **_kwargs):
        calls["colors"] += 1
        return {
            "dominant_colors": [],
            "tags": [],
            "tag_source": "skipped",
            "stage_status": {"colors": "skipped", "captions": "skipped"},
            "stage_errors": {},
        }

    def persist(_state, _context, _clip, result):
        calls["persisted"] = deepcopy(result)

    monkeypatch.setattr(video_router, "_run_scene_detection", scene_stage)
    monkeypatch.setattr(video_router, "with_gpu_task", gpu_stage)
    monkeypatch.setattr(video_router, "_run_color_and_caption_analysis", color_stage)
    monkeypatch.setattr(video_router, "_persist_video_analysis_outcome", persist)
    monkeypatch.setattr(video_router, "_commit_pending_video_embedding", lambda _result: None)
    monkeypatch.setattr(video_router, "_dedupe_old_video_embeddings", lambda _result: None)
    monkeypatch.setattr(video_router, "publish_event", _noop)
    monkeypatch.setattr(video_router, "publish_log", _noop)
    monkeypatch.setattr(
        "pb_studio.video.audio_key_detector.detect_video_audio_key",
        lambda _path: "8A",
    )

    result = asyncio.run(
        video_router._analyze_video_in_project(
            VideoAnalyzeRequest(
                clip_id=7,
                detect_scenes=False,
                generate_embeddings=True,
                analyze_motion=False,
                generate_captions=False,
                analyze_colors=False,
            ),
            state,
            SimpleNamespace(project_id=1),
        )
    )

    assert calls == {
        "scenes": 0,
        "gpu": 1,
        "colors": 0,
        "persisted": calls["persisted"],
    }
    assert [scene.model_dump() for scene in result.scenes] == _existing_analysis()["scenes"]
    assert result.motion.model_dump() == _existing_analysis()["motion"]
    assert result.dominant_colors == ["#112233"]
    assert result.tags == ["concert", "stage"]
    assert result.embedding_dim == 1152
    assert result.embedding_samples == 3
    assert result.has_embedding is True
    assert result.stage_status["scenes"] == "completed"
    assert result.stage_status["motion"] == "completed"
    assert result.stage_status["colors"] == "completed"
    assert result.stage_status["captions"] == "completed"
    assert result.stage_status["embedding"] == "completed"
    assert "embedding" not in result.stage_errors
    assert calls["persisted"]["scenes"] == _existing_analysis()["scenes"]


def test_force_recomputes_requested_completed_stage(monkeypatch, tmp_path):
    video_router = importlib.import_module("backend.routers.video_router")

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"video")
    existing = _existing_analysis()
    existing["stage_status"]["embedding"] = "completed"
    existing["has_embedding"] = True
    existing["embedding_dim"] = 1152
    existing["embedding_samples"] = 3
    state = _State(media, existing)
    calls = {"scenes": 0}

    def scene_stage(*_args, **_kwargs):
        calls["scenes"] += 1
        return {
            "scene_count": 1,
            "scenes": [{"start_time": 0.0, "end_time": 9.0, "scene_type": "cut", "confidence": None}],
            "stage_status": {"scenes": "completed"},
            "stage_errors": {},
        }

    monkeypatch.setattr(video_router, "_run_scene_detection", scene_stage)
    monkeypatch.setattr(
        video_router,
        "with_gpu_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("GPU must not run")),
    )
    monkeypatch.setattr(
        video_router,
        "_run_color_and_caption_analysis",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("color/caption must not run")),
    )
    monkeypatch.setattr(video_router, "_persist_video_analysis_outcome", lambda *_args: None)
    monkeypatch.setattr(video_router, "_commit_pending_video_embedding", lambda _result: None)
    monkeypatch.setattr(video_router, "_dedupe_old_video_embeddings", lambda _result: None)
    monkeypatch.setattr(video_router, "publish_event", _noop)
    monkeypatch.setattr(video_router, "publish_log", _noop)
    monkeypatch.setattr(
        "pb_studio.video.audio_key_detector.detect_video_audio_key",
        lambda _path: "8A",
    )

    result = asyncio.run(
        video_router._analyze_video_in_project(
            VideoAnalyzeRequest(
                clip_id=7,
                detect_scenes=True,
                generate_embeddings=False,
                analyze_motion=False,
                generate_captions=False,
                analyze_colors=False,
                analyze_audio_key=False,
                force=True,
            ),
            state,
            SimpleNamespace(project_id=1),
        )
    )

    assert calls["scenes"] == 1
    assert result.scenes[0].end_time == 9.0
    assert result.motion.model_dump() == existing["motion"]
    assert result.has_embedding is True


def test_missing_file_does_not_persist_defaults(monkeypatch, tmp_path):
    video_router = importlib.import_module("backend.routers.video_router")

    state = _State(tmp_path / "missing.mp4", _existing_analysis())

    def must_not_persist(*_args, **_kwargs):
        raise AssertionError("missing input must not overwrite prior analysis")

    monkeypatch.setattr(video_router, "_persist_video_analysis_outcome", must_not_persist)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            video_router._analyze_video_in_project(
                VideoAnalyzeRequest(clip_id=7),
                state,
                SimpleNamespace(project_id=1),
            )
        )

    assert exc_info.value.status_code == 422
    assert state.analysis == _existing_analysis()
