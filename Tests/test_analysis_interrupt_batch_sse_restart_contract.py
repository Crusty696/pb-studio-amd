"""Router lifecycle contract for interrupted audio-analysis resume.

The analyzer boundary is replaced deliberately; real-media execution belongs to
the OBJ-74 live-QC task.  The existing test module is only an on-disk sentinel
for the router's pre-flight path check and is never opened as media.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


ROUTER_PATH_SENTINEL = Path(__file__).resolve()


class _State:
    def __init__(self, analysis: dict | None = None) -> None:
        self.clip = {
            "id": 74,
            "name": "interrupt-resume-contract",
            "path": str(ROUTER_PATH_SENTINEL),
            "duration_seconds": 30.0,
            "audio_hash": None,
            "is_analyzed": False,
        }
        self.analysis = dict(analysis or {})
        self.persisted_history: list[dict] = []

    @asynccontextmanager
    async def project_operation(self):
        yield object()

    @contextmanager
    def project_commit(self, _context):
        yield

    def is_project_context_current(self, _context) -> bool:
        return True

    def get_audio_clip(self, clip_id: int):
        return self.clip if clip_id == self.clip["id"] else None

    def get_audio_analysis(self, clip_id: int):
        return dict(self.analysis) if clip_id == self.clip["id"] else None

    def update_audio_analysis(self, **kwargs) -> None:
        self.persisted_history.append(dict(kwargs))
        beats_json = kwargs.get("beats_json")
        self.analysis = {
            "clip_id": kwargs["clip_id"],
            "duration_seconds": self.clip["duration_seconds"],
            "bpm": kwargs.get("bpm"),
            "key": kwargs.get("key"),
            "beat_count": kwargs.get("beat_count"),
            "beats": json.loads(beats_json) if beats_json is not None else None,
            "energy_curve": kwargs.get("energy_curve"),
            "structure_segments": kwargs.get("structure_segments"),
            "spectral_data": kwargs.get("spectral_data"),
            "onset_times": kwargs.get("onset_times"),
            "kick_times": kwargs.get("kick_times"),
            "snare_times": kwargs.get("snare_times"),
            "hihat_times": kwargs.get("hihat_times"),
            "downbeats": kwargs.get("downbeats"),
            "downbeat_provenance": kwargs.get("downbeat_provenance"),
            "_analysis_status": kwargs.get("analysis_status"),
            "_stage_status": dict(kwargs.get("stage_status") or {}),
            "_stage_errors": dict(kwargs.get("stage_errors") or {}),
        }


def _beat_checkpoint(clip_id: int) -> dict:
    return {
        "clip_id": clip_id,
        "duration_seconds": 30.0,
        "bpm": 128.0,
        "beat_count": 1,
        "beats": [{"time": 0.5, "strength": 0.8, "beat_type": "beat"}],
        "energy_curve": [0.8],
        "downbeats": [],
        "downbeat_provenance": {"status": "unavailable"},
        "onset_times": [0.5],
        "kick_times": [0.5],
        "snare_times": [],
        "hihat_times": [],
        "_stage_status": {"beats": "completed"},
        "_stage_errors": {},
    }


def test_interrupt_sse_restart_runs_only_missing_stage(monkeypatch) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")
    first_state = _State()
    checkpoint_done = threading.Event()
    release_worker = threading.Event()
    worker_done = threading.Event()
    events: list[tuple[str, dict]] = []

    def interrupted_run(
        _path,
        clip_id,
        _request,
        _stems,
        _loop,
        on_stage_checkpoint=None,
        neural_downbeat_runner=None,
    ):
        try:
            on_stage_checkpoint("beats", _beat_checkpoint(clip_id))
            checkpoint_done.set()
            release_worker.wait(timeout=3.0)
            on_stage_checkpoint(
                "structure",
                {
                    "clip_id": clip_id,
                    "duration_seconds": 30.0,
                    "structure_segments": [],
                    "_stage_status": {"structure": "completed"},
                    "_stage_errors": {},
                },
            )
        finally:
            worker_done.set()

    async def capture_event(name, payload):
        events.append((name, dict(payload)))

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_router, "_run_audio_analysis", interrupted_run)
    monkeypatch.setattr(audio_router, "publish_event", capture_event)
    monkeypatch.setattr(audio_router, "publish_log", no_event)
    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        no_event,
    )

    request = AudioAnalyzeRequest(
        clip_id=74,
        detect_beats=True,
        detect_structure=True,
        spectral_analysis=False,
        detect_key=False,
    )

    async def interrupt_once() -> None:
        task = asyncio.create_task(audio_router.analyze_audio(request, first_state))
        assert await asyncio.to_thread(checkpoint_done.wait, 2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        release_worker.set()
        assert await asyncio.to_thread(worker_done.wait, 2.0)

    asyncio.run(interrupt_once())

    interrupted = first_state.analysis
    assert interrupted["_stage_status"] == {
        "beats": "completed",
        "structure": "interrupted",
    }
    assert interrupted["bpm"] == 128.0
    assert events[-1][0] == "analysis_progress"
    assert events[-1][1]["status"] == "interrupted"

    restarted_state = _State(interrupted)
    planned_requests = []

    def resumed_run(
        _path,
        clip_id,
        planned,
        _stems,
        _loop,
        on_stage_checkpoint=None,
        neural_downbeat_runner=None,
    ):
        planned_requests.append(planned)
        fresh = {
            "clip_id": clip_id,
            "duration_seconds": 30.0,
            "structure_segments": [
                {
                    "start_time": 0.0,
                    "end_time": 30.0,
                    "label": "verse",
                    "confidence": 0.8,
                    "energy_score": 0.6,
                }
            ],
            "_stage_status": {"structure": "completed"},
            "_stage_errors": {},
        }
        on_stage_checkpoint("structure", fresh)
        return fresh

    monkeypatch.setattr(audio_router, "_run_audio_analysis", resumed_run)
    result = asyncio.run(audio_router.analyze_audio(request, restarted_state))

    assert len(planned_requests) == 1
    assert planned_requests[0].detect_beats is False
    assert planned_requests[0].detect_structure is True
    assert result.bpm == 128.0
    assert result.beat_count == 1
    assert result.structure_segments[0].label == "verse"
    assert result.analysis_status == "completed"
    assert result.stage_status == {
        "beats": "completed",
        "structure": "completed",
    }
    assert events[-1][1]["status"] == "completed"
