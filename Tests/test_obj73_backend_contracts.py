"""Regression contracts for OBJ-73 backend release-gate repairs."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend import dependencies as deps
from backend.schemas.pacing_schemas import PreviewRequest
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import PacingCut
from pb_studio.services.pacing_service import PacingService
from pb_studio.video import raft

pacing_router = importlib.import_module("backend.routers.pacing_router")


def test_sse_event_is_journaled_without_connected_clients():
    async def scenario() -> None:
        deps._event_queues.clear()
        deps._event_queue_filters.clear()
        deps.reset_event_journal()

        await deps.publish_event("render_progress", {"job_id": "job-73"})
        await deps.publish_event("render_completed", {"job_id": "job-73"})

        replay = deps.get_journaled_events_since(1)
        assert len(replay) == 1
        assert replay[0][1]["event"] == "render_completed"
        assert replay[0][1]["data"] == {"job_id": "job-73"}

    try:
        asyncio.run(scenario())
    finally:
        deps.reset_event_journal()


def _configure_raft_init(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    reserve_result: bool,
    commit_result: bool,
):
    from pb_studio.core import vram_budget_manager

    model_path = tmp_path / "raft_small.onnx"
    model_path.write_bytes(b"test-model")
    analyzer = raft.MotionAnalyzer(models_dir=str(tmp_path), lazy_load=True)

    session = MagicMock()
    session.get_inputs.return_value = [MagicMock(shape=[1, 3, 256, 448])]
    session.get_outputs.return_value = []
    session.get_providers.return_value = ["DmlExecutionProvider"]

    manager = MagicMock()
    manager.get_model.return_value = SimpleNamespace(unload_callback=None)
    manager.reserve.return_value = reserve_result
    manager.commit.return_value = commit_result

    inference_session = MagicMock(return_value=session)
    monkeypatch.setattr(analyzer, "_create_session_options", MagicMock())
    monkeypatch.setattr(
        analyzer,
        "_get_providers",
        lambda: [("DmlExecutionProvider", {})],
    )
    monkeypatch.setattr(raft.ort, "InferenceSession", inference_session)
    monkeypatch.setattr(raft, "enforce_directml_session", lambda value: value)
    monkeypatch.setattr(vram_budget_manager, "get_vram_manager", lambda: manager)
    return analyzer, manager, inference_session


def test_raft_reservation_failure_prevents_session_creation(tmp_path, monkeypatch):
    analyzer, manager, inference_session = _configure_raft_init(
        tmp_path,
        monkeypatch,
        reserve_result=False,
        commit_result=True,
    )

    assert analyzer._init_model() is False
    inference_session.assert_not_called()
    manager.commit.assert_not_called()
    manager.cancel_reservation.assert_not_called()
    assert analyzer.session is None


def test_raft_commit_failure_cancels_reservation_and_discards_session(
    tmp_path,
    monkeypatch,
):
    analyzer, manager, inference_session = _configure_raft_init(
        tmp_path,
        monkeypatch,
        reserve_result=True,
        commit_result=False,
    )

    assert analyzer._init_model() is False
    inference_session.assert_called_once()
    manager.cancel_reservation.assert_called_once_with("raft_small")
    manager.release.assert_not_called()
    assert analyzer.session is None
    assert analyzer.is_ready is False


def test_raft_session_failure_cancels_prior_reservation(tmp_path, monkeypatch):
    analyzer, manager, inference_session = _configure_raft_init(
        tmp_path,
        monkeypatch,
        reserve_result=True,
        commit_result=True,
    )
    inference_session.side_effect = RuntimeError("invalid model")

    assert analyzer._init_model() is False
    manager.cancel_reservation.assert_called_once_with("raft_small")
    manager.commit.assert_not_called()
    assert analyzer.session is None


class _PreviewState:
    current_timeline = [{"clip_id": "clip_1"}]

    def get_timeline_snapshot(self):
        return list(self.current_timeline)

    def get_video_clips_snapshot(self):
        return {}


class _TrackingAsyncLock:
    def __init__(self):
        self.active = False

    async def __aenter__(self):
        assert self.active is False
        self.active = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.active = False


def test_preview_generation_runs_under_shared_gpu_lock(monkeypatch):
    lock = _TrackingAsyncLock()
    monkeypatch.setattr(pacing_router, "gpu_lock", lock)
    monkeypatch.setattr(
        pacing_router,
        "validate_timeline_media_paths",
        lambda timeline, _clips: timeline,
    )

    async def fake_to_thread(_func, *_args):
        assert lock.active is True
        return "preview.mp4"

    monkeypatch.setattr(pacing_router.asyncio, "to_thread", fake_to_thread)

    response = asyncio.run(
        pacing_router.generate_preview(PreviewRequest(), _PreviewState())
    )

    assert response.preview_path == "preview.mp4"
    assert lock.active is False


def test_preview_empty_result_is_http_500(monkeypatch):
    monkeypatch.setattr(pacing_router, "gpu_lock", _TrackingAsyncLock())
    monkeypatch.setattr(
        pacing_router,
        "validate_timeline_media_paths",
        lambda timeline, _clips: timeline,
    )

    async def fake_to_thread(_func, *_args):
        return ""

    monkeypatch.setattr(pacing_router.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            pacing_router.generate_preview(PreviewRequest(), _PreviewState())
        )

    assert error.value.status_code == 500
    assert "keine Ausgabedatei" in error.value.detail


def test_stem_engine_applies_structure_to_base_and_stem_triggers(monkeypatch):
    engine = AdvancedPacingEngine()
    captured: dict[str, object] = {}

    def fake_base_generation(**kwargs):
        captured["base_sections"] = kwargs["song_sections"]
        return [PacingCut(time=0.5, trigger_type="beat", strength=0.8)]

    def fake_projection(*, base_cuts, stem_triggers, min_cut_interval):
        captured["stem_strength"] = stem_triggers[0].strength
        return []

    monkeypatch.setattr(engine, "_generate_cut_list_from_audio", fake_base_generation)
    monkeypatch.setattr(
        engine,
        "_extract_drum_triggers_from_stem",
        lambda _path: [PacingCut(time=0.5, trigger_type="kick", strength=0.8)],
    )
    monkeypatch.setattr(engine, "_project_stem_triggers_onto_base", fake_projection)
    monkeypatch.setattr(engine, "_enforce_minimum_interval", lambda cuts, _gap: cuts)
    monkeypatch.setattr(engine, "_enforce_clip_lengths", lambda **kwargs: kwargs["cuts"])

    import librosa

    monkeypatch.setattr(librosa, "get_duration", lambda **_kwargs: 2.0)
    engine.generate_cut_list_with_stems(
        audio_path="song.wav",
        stems={"drums": "drums.wav"},
        song_sections=[
            {"label": "intro", "start_time": 0.0, "end_time": 2.0}
        ],
    )

    normalized = captured["base_sections"]
    assert normalized[0].name == "intro"
    assert captured["stem_strength"] == pytest.approx(0.48)


def test_stem_service_forwards_cached_structure_without_reanalysis(
    tmp_path,
    monkeypatch,
):
    from pb_studio.data import vector_store

    captured: dict[str, object] = {}
    cached_segments = [
        {"label": "drop", "start_time": 0.0, "end_time": 4.0}
    ]

    def fake_stem_generation(self, **kwargs):
        captured["song_sections"] = kwargs["song_sections"]
        return []

    monkeypatch.setattr(
        AdvancedPacingEngine,
        "generate_cut_list_with_stems",
        fake_stem_generation,
    )
    monkeypatch.setattr(
        AdvancedPacingEngine,
        "generate_cut_list",
        lambda self, **_kwargs: [],
    )
    monkeypatch.setattr(vector_store, "VectorStore", lambda **_kwargs: MagicMock())

    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    service = PacingService()
    result = service.generate_cut_list_with_stems(
        audio_path=str(tmp_path / "song.wav"),
        stems={"drums": str(tmp_path / "drums.wav")},
        clips=[
            {
                "id": 1,
                "name": "clip",
                "file_path": str(video_path),
                "duration": 4.0,
            }
        ],
        pacing_config={
            "trigger_settings": {},
            "expected_bpm": 120.0,
            "use_semantic_matching": False,
            "use_structure_awareness": True,
            "min_cut_interval": 0.5,
        },
        total_duration=4.0,
        cached_analysis={"structure_segments": cached_segments},
    )

    assert len(result) == 1
    assert result[0].clip_id == "clip_1"
    assert result[0].start_time == pytest.approx(0.0)
    assert result[0].end_time == pytest.approx(4.0)
    assert result[0].metadata["trigger_type"] == "time_grid_fallback"
    assert captured["song_sections"] is cached_segments
    assert service._last_skipped_structure_reanalyze is True
