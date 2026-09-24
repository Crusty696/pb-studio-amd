"""Regressions for spec 00030 Pacing functional completion."""

from __future__ import annotations

import asyncio
import importlib
import json
import random
import types
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.schemas.pacing_schemas import (
    PacingConfigSchema,
    PreviewRequest,
    TimelineEntrySchema,
    TriggerSettingsSchema,
)

pacing_router = importlib.import_module("backend.routers.pacing_router")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: PacingConfigSchema(audio_clip_id=1, duration_limit=float("inf")), "duration_limit"),
        (lambda: PreviewRequest(start_sec=float("inf")), "start_sec"),
        (lambda: PreviewRequest(duration=float("inf")), "duration"),
        (lambda: TriggerSettingsSchema(min_clip_length=float("inf")), "min_clip_length"),
        (lambda: TriggerSettingsSchema(max_clip_length=float("inf")), "max_clip_length"),
        (lambda: TriggerSettingsSchema(min_cut_interval=float("inf")), "min_cut_interval"),
        (lambda: TriggerSettingsSchema(max_cut_interval=float("inf")), "max_cut_interval"),
        (
            lambda: TimelineEntrySchema(
                clip_id="clip_1",
                clip_name="clip",
                file_path=r"C:\media\clip.mp4",
                start_time=float("nan"),
                end_time=1.0,
            ),
            "start_time",
        ),
    ],
)
def test_pacing_schemas_reject_non_finite_time_values(factory, field: str) -> None:
    with pytest.raises(ValidationError) as error:
        factory()

    assert field in str(error.value)


class _PreviewState:
    def __init__(self, timeline_end: float = 3.0) -> None:
        self.current_timeline = [{
            "clip_id": "clip_1",
            "start_time": 0.0,
            "end_time": timeline_end,
            "metadata": {"file_path": r"C:\media\clip.mp4", "clip_start": 0.0},
        }]
        self.project_operation_entered = False
        self.context_checks = 0

    @asynccontextmanager
    async def project_operation(self):
        self.project_operation_entered = True
        yield object()

    def require_project_context_current(self, _context) -> None:
        self.context_checks += 1

    def get_timeline_snapshot(self):
        return list(self.current_timeline)

    def get_video_clips_snapshot(self):
        return {}


class _TrackingAsyncLock:
    def __init__(self) -> None:
        self.active = False

    async def __aenter__(self):
        assert self.active is False
        self.active = True
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        self.active = False


def _prepare_preview(monkeypatch: pytest.MonkeyPatch, lock: _TrackingAsyncLock) -> None:
    monkeypatch.setattr(pacing_router, "gpu_lock", lock)
    monkeypatch.setattr(
        pacing_router,
        "validate_timeline_media_paths",
        lambda timeline, _clips: timeline,
    )


def test_preview_uses_project_context_and_reports_actual_interval(monkeypatch) -> None:
    state = _PreviewState(timeline_end=3.0)
    lock = _TrackingAsyncLock()
    _prepare_preview(monkeypatch, lock)
    captured: dict[str, float] = {}

    async def fake_to_thread(_func, _timeline, start: float, duration: float):
        captured["start"] = start
        captured["duration"] = duration
        return "preview.mp4"

    monkeypatch.setattr(pacing_router.asyncio, "to_thread", fake_to_thread)

    response = asyncio.run(
        pacing_router.generate_preview(
            PreviewRequest(start_sec=2.0, duration=10.0),
            state,
        )
    )

    assert state.project_operation_entered is True
    assert state.context_checks >= 1
    assert captured == {"start": 2.0, "duration": 1.0}
    assert response.duration == pytest.approx(1.0)


def test_preview_rejects_start_outside_timeline_before_render(monkeypatch) -> None:
    state = _PreviewState(timeline_end=3.0)
    lock = _TrackingAsyncLock()
    _prepare_preview(monkeypatch, lock)

    async def forbidden_to_thread(*_args):
        raise AssertionError("render must not start")

    monkeypatch.setattr(pacing_router.asyncio, "to_thread", forbidden_to_thread)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            pacing_router.generate_preview(
                PreviewRequest(start_sec=3.0, duration=1.0),
                state,
            )
        )

    assert error.value.status_code == 400
    assert "außerhalb" in str(error.value.detail)


def test_preview_cancellation_holds_gpu_lock_until_worker_finishes(monkeypatch) -> None:
    async def scenario() -> None:
        state = _PreviewState(timeline_end=3.0)
        lock = _TrackingAsyncLock()
        _prepare_preview(monkeypatch, lock)
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_to_thread(*_args):
            started.set()
            await release.wait()
            return "preview.mp4"

        monkeypatch.setattr(pacing_router.asyncio, "to_thread", fake_to_thread)

        task = asyncio.create_task(
            pacing_router.generate_preview(PreviewRequest(duration=1.0), state)
        )
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)

        assert lock.active is True
        assert task.done() is False

        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert lock.active is False

    asyncio.run(scenario())


def test_onset_sensitivity_changes_detection_threshold_monotonically() -> None:
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    insensitive = AdvancedPacingEngine(trigger_settings={"onset_sensitivity": 0.0})
    sensitive = AdvancedPacingEngine(trigger_settings={"onset_sensitivity": 1.0})

    assert sensitive._onset_detection_delta() < insensitive._onset_detection_delta()


def test_max_cut_interval_is_a_hard_bound_with_clip_length_variation() -> None:
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.pacing.pacing_models import PacingCut

    engine = AdvancedPacingEngine(trigger_settings={
        "min_clip_length": 1.0,
        "min_cut_interval": 1.0,
        "max_clip_length": 8.0,
        "max_cut_interval": 2.0,
        "clip_length_variation": 1.0,
    })
    effective_min, effective_max = engine._effective_cut_intervals(1.0)

    for seed in range(50):
        random.seed(seed)
        cuts = engine._enforce_clip_lengths(
            [PacingCut(time=0.0)],
            min_length=effective_min,
            max_length=effective_max,
            audio_duration=60.0,
            variation=1.0,
        )
        boundaries = [cut.time for cut in cuts] + [60.0]
        intervals = [right - left for left, right in zip(boundaries, boundaries[1:])]
        assert min(intervals) >= effective_min - 1e-6
        assert max(intervals) <= effective_max + 1e-6


@pytest.mark.parametrize(
    "entries",
    [
        [
            {"start_time": 0.0, "end_time": 1.0},
            {"start_time": 1.25, "end_time": 2.0},
        ],
        [{"start_time": -0.25, "end_time": 1.0}],
        [{"start_time": 0.25, "end_time": 1.0}],
    ],
)
def test_timeline_validation_rejects_gaps_and_invalid_origin(entries) -> None:
    from backend.schemas.common import validate_timeline

    _warnings, errors = validate_timeline(entries)

    assert errors


def test_pacing_progress_uses_request_unique_task_id(monkeypatch) -> None:
    config = PacingConfigSchema(
        audio_clip_id=7,
        request_id="pacing:request-123",
    )
    events: list[tuple[str, dict]] = []

    async def fake_publish(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    monkeypatch.setattr(pacing_router, "publish_event", fake_publish)

    async def scenario() -> None:
        pacing_router._emit_pacing_progress(
            asyncio.get_running_loop(),
            25.0,
            config.audio_clip_id,
            config.request_id,
        )
        await asyncio.sleep(0)

    asyncio.run(scenario())

    assert config.request_id == "pacing:request-123"
    assert events == [(
        "pacing_progress",
        {
            "task_id": "pacing:request-123",
            "clip_id": 7,
            "percent": 25.0,
            "message": "Pacing 25.0%",
        },
    )]


@pytest.mark.parametrize(
    ("duration_limit", "expected_duration"),
    [(None, 10.0), (4.0, 4.0), (60.0, 10.0)],
)
def test_duration_limit_caps_but_never_expands_audio(
    tmp_path,
    duration_limit: float | None,
    expected_duration: float,
) -> None:
    from pb_studio.pacing.pacing_models import CutListEntry
    from pb_studio.services.pacing_service import PacingService

    video = tmp_path / "video.mp4"
    video.touch()
    source_cut = CutListEntry(
        clip_id="clip_1",
        start_time=0.0,
        end_time=10.0,
        metadata={"file_path": str(video), "clip_start": 0.0},
    )

    cuts = PacingService().generate_cut_list(
        audio_path=str(tmp_path / "audio.wav"),
        clips=[{
            "id": 1,
            "name": "video",
            "file_path": str(video),
            "duration": 10.0,
        }],
        pacing_config={"trigger_settings": {}},
        total_duration=10.0,
        duration_limit=duration_limit,
        sequencer_cuts=[source_cut],
    )

    assert cuts[-1].end_time == pytest.approx(expected_duration)


def test_motion_toggle_changes_selection_and_normalizes_raft_scalars() -> None:
    from pb_studio.pacing.clip_selector import ClipSelector

    clips = [
        {"id": "fast", "file_path": "fast.mp4", "motion_score": 30.0},
        {"id": "calm", "file_path": "calm.mp4", "motion_score": 3.0},
    ]
    enabled = ClipSelector(blacklist_percentage=0.0)
    enabled.use_motion_matching = True
    disabled = ClipSelector(blacklist_percentage=0.0)
    disabled.use_motion_matching = False

    motion_pick = enabled.select_clip(clips, 0.1, "beat")
    neutral_pick = disabled.select_clip(clips, 0.1, "beat")

    assert motion_pick.clip_id == "calm"
    assert motion_pick.motion_score == pytest.approx(0.1)
    assert neutral_pick.clip_id == "fast"


def test_short_schema_valid_cuts_are_not_discarded(tmp_path, monkeypatch) -> None:
    from pb_studio.pacing.pacing_models import PacingCut
    from pb_studio.services.pacing_service import PacingService

    video = tmp_path / "short.mp4"
    video.touch()
    service = PacingService()
    monkeypatch.setattr(service, "_get_clip_duration", lambda _path: 10.0)
    cuts = service._process_pacing_cuts_to_cutlist(
        [
            (PacingCut(time=0.0), str(video), "clip_1"),
            (PacingCut(time=0.25), str(video), "clip_1"),
        ],
        target_duration=0.25,
    )

    assert len(cuts) == 1
    assert cuts[0].end_time - cuts[0].start_time == pytest.approx(0.25)


def test_canvas_supports_four_hour_timestamps_and_registered_non_mp4(tmp_path) -> None:
    from pb_studio.services.pacing_service import PacingService

    canvas = tmp_path / "story.canvas"
    canvas.write_text(
        json.dumps({"nodes": [
            {"type": "text", "text": "@120:00", "x": 0},
            {"type": "text", "text": "@121:00", "x": 100},
            {"type": "file", "file": "shots/scene.mov", "x": 50, "y": 100},
        ]}),
        encoding="utf-8",
    )
    anchors = PacingService().load_canvas_manual_anchors(
        str(canvas),
        [{
            "id": 9,
            "file_path": str(tmp_path / "scene.mov"),
            "duration": 5.0,
        }],
    )

    assert len(anchors) == 1
    assert anchors[0]["mix_start"] == pytest.approx(120.5 * 60.0)


def test_missing_stems_have_structured_degradation_reason() -> None:
    config = PacingConfigSchema(audio_clip_id=7, use_stem_pacing=True)

    stems, reason = pacing_router._resolve_stem_paths(
        config,
        {7: {"stems_paths": {}}},
    )

    assert stems == {}
    assert "keine analysierten Stems" in str(reason)


def test_brain_empty_result_preserves_time_dependent_fallback_context() -> None:
    from pb_studio.pacing.clip_selector import ClipSelector
    from pb_studio.pacing.pacing_models import SelectedClip

    class _Adapter:
        def candidate_features(self, **_kwargs):
            return object()

    class _Reranker:
        def rerank(self, *_args, **_kwargs):
            return []

    selector = ClipSelector(blacklist_percentage=0.0)
    selector.brain_reranker = _Reranker()
    selector.brain_context_keys = ["context"]
    selector.brain_feature_adapter = _Adapter()
    selector.get_audio_state_at_time = lambda _time: "drop"
    captured: dict[str, object] = {}

    def fake_fallback(
        self,
        candidates,
        trigger_strength,
        trigger_type,
        current_time=None,
        audio_state="normal",
    ):
        captured.update(current_time=current_time, audio_state=audio_state)
        return SelectedClip("1", "one.mp4", 1.0, 0.5)

    selector._fallback_select = types.MethodType(fake_fallback, selector)
    selector.select_clip(
        [{"id": "1", "file_path": "one.mp4"}],
        0.8,
        "drop",
        current_time=12.5,
    )

    assert captured == {"current_time": 12.5, "audio_state": "drop"}
