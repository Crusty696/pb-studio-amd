from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager, contextmanager


class _FakeState:
    def __init__(self, clip: dict, analysis: dict) -> None:
        self.clip = clip
        self.analysis = analysis
        self.persisted: dict = {}
        self.persisted_history: list[dict] = []

    @asynccontextmanager
    async def project_operation(self):
        yield object()

    @contextmanager
    def project_commit(self, _context):
        yield

    def get_audio_clip(self, clip_id: int):
        return self.clip if clip_id == self.clip["id"] else None

    def get_audio_analysis(self, clip_id: int):
        return self.analysis if clip_id == self.clip["id"] else None

    def update_audio_analysis(self, **kwargs) -> None:
        self.persisted = kwargs
        self.persisted_history.append(dict(kwargs))


def _completed_cache() -> dict:
    return {
        "clip_id": 7,
        "duration_seconds": 30.0,
        "bpm": 128.0,
        "beat_count": 2,
        "beats": [
            {"time": 0.5, "strength": 0.8, "beat_type": "beat"},
            {"time": 1.0, "strength": 0.9, "beat_type": "beat"},
        ],
        "energy_curve": [0.2, 0.8],
        "downbeats": [],
        "downbeat_provenance": {"status": "unavailable"},
        "onset_times": [0.5],
        "kick_times": [0.5],
        "snare_times": [1.0],
        "hihat_times": [],
        "structure_segments": [],
        "spectral_data": {
            "clip_id": 7,
            "times": [0.0, 1.0],
            "bands": {"low": [0.2, 0.4]},
        },
        "key": "C major",
        "_analysis_status": "partial",
        "_stage_status": {
            "beats": "completed",
            "structure": "failed",
            "spectral": "completed",
            "key": "completed",
        },
        "_stage_errors": {"structure": "interrupted"},
    }


def test_retry_runs_only_missing_stage_and_preserves_completed_data(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")

    audio = tmp_path / "resume.wav"
    audio.write_bytes(b"audio")
    state = _FakeState(
        {
            "id": 7,
            "name": "resume",
            "path": str(audio),
            "duration_seconds": 30.0,
            "audio_hash": None,
            "is_analyzed": False,
        },
        _completed_cache(),
    )
    calls = []

    def run_analysis(
        _path,
        clip_id,
        request,
        _stems,
        _loop,
        on_stage_checkpoint=None,
        neural_downbeat_runner=None,
    ):
        calls.append(request)
        return {
            "clip_id": clip_id,
            "duration_seconds": 30.0,
            "bpm": 0.0,
            "beat_count": 0,
            "beats": [],
            "energy_curve": [],
            "downbeats": [],
            "downbeat_provenance": {},
            "onset_times": [],
            "kick_times": [],
            "snare_times": [],
            "hihat_times": [],
            "structure_segments": [
                {
                    "start_time": 0.0,
                    "end_time": 30.0,
                    "label": "verse",
                    "confidence": 0.8,
                    "energy_score": 0.6,
                }
            ],
            "spectral_data": None,
            "key": None,
            "_analysis_status": "completed",
            "_stage_status": {
                "beats": "skipped",
                "structure": "completed",
                "spectral": "skipped",
                "key": "skipped",
            },
            "_stage_errors": {},
        }

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)
    monkeypatch.setattr(audio_router, "publish_event", no_event)
    monkeypatch.setattr(audio_router, "publish_log", no_event)
    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        no_event,
    )

    response = asyncio.run(
        audio_router.analyze_audio(AudioAnalyzeRequest(clip_id=7), state)
    )

    assert len(calls) == 1
    assert calls[0].detect_beats is False
    assert calls[0].detect_structure is True
    assert calls[0].spectral_analysis is False
    assert calls[0].detect_key is False
    assert response.bpm == 128.0
    assert response.beat_count == 2
    assert response.energy_curve == [0.2, 0.8]
    assert response.key == "C major"
    assert response.spectral_data is not None
    assert response.onset_times == [0.5]
    assert response.structure_segments[0].label == "verse"
    assert response.stage_status == {
        "beats": "completed",
        "structure": "completed",
        "spectral": "completed",
        "key": "completed",
    }
    assert state.persisted["bpm"] == 128.0
    assert state.persisted["beats_json"] != "[]"


def test_force_recomputes_only_explicitly_requested_stage(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")

    audio = tmp_path / "force.wav"
    audio.write_bytes(b"audio")
    cached = _completed_cache()
    cached["_stage_status"]["structure"] = "completed"
    cached["structure_segments"] = [
        {"start_time": 0.0, "end_time": 30.0, "label": "verse"}
    ]
    state = _FakeState(
        {
            "id": 7,
            "name": "force",
            "path": str(audio),
            "duration_seconds": 30.0,
            "audio_hash": None,
            "is_analyzed": True,
        },
        cached,
    )
    calls = []

    def run_analysis(
        _path,
        clip_id,
        request,
        _stems,
        _loop,
        on_stage_checkpoint=None,
        neural_downbeat_runner=None,
    ):
        calls.append(request)
        return {
            "clip_id": clip_id,
            "duration_seconds": 30.0,
            "bpm": 132.0,
            "beat_count": 1,
            "beats": [{"time": 1.0, "strength": 1.0, "beat_type": "beat"}],
            "energy_curve": [0.9],
            "downbeats": [],
            "downbeat_provenance": {"status": "unavailable"},
            "onset_times": [1.0],
            "kick_times": [1.0],
            "snare_times": [],
            "hihat_times": [],
            "structure_segments": [],
            "spectral_data": None,
            "key": None,
            "_analysis_status": "completed",
            "_stage_status": {
                "beats": "completed",
                "structure": "skipped",
                "spectral": "skipped",
                "key": "skipped",
            },
            "_stage_errors": {},
        }

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)
    monkeypatch.setattr(audio_router, "publish_event", no_event)
    monkeypatch.setattr(audio_router, "publish_log", no_event)
    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        no_event,
    )

    request = AudioAnalyzeRequest(
        clip_id=7,
        detect_beats=True,
        detect_structure=False,
        spectral_analysis=False,
        detect_key=False,
        force=True,
    )
    response = asyncio.run(audio_router.analyze_audio(request, state))

    assert len(calls) == 1
    assert calls[0].detect_beats is True
    assert calls[0].detect_structure is False
    assert calls[0].spectral_analysis is False
    assert calls[0].detect_key is False
    assert response.bpm == 132.0
    assert response.structure_segments[0].label == "verse"
    assert response.spectral_data is not None
    assert response.key == "C major"


def test_cancel_preserves_checkpoint_and_blocks_late_worker_commit(
    monkeypatch,
    tmp_path,
) -> None:
    import threading

    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "cancel.wav"
    audio.write_bytes(b"audio")
    state = _FakeState(
        {
            "id": 7,
            "name": "cancel",
            "path": str(audio),
            "duration_seconds": 30.0,
            "audio_hash": None,
            "is_analyzed": False,
        },
        {},
    )
    checkpoint_done = threading.Event()
    release_worker = threading.Event()
    worker_done = threading.Event()

    def run_analysis(
        _path,
        clip_id,
        _request,
        _stems,
        _loop,
        on_stage_checkpoint=None,
        neural_downbeat_runner=None,
    ):
        try:
            on_stage_checkpoint(
                "beats",
                {
                    "clip_id": clip_id,
                    "duration_seconds": 30.0,
                    "bpm": 128.0,
                    "beat_count": 1,
                    "beats": [
                        {"time": 0.5, "strength": 0.8, "beat_type": "beat"}
                    ],
                    "energy_curve": [0.8],
                    "downbeats": [],
                    "downbeat_provenance": {"status": "unavailable"},
                    "onset_times": [0.5],
                    "kick_times": [0.5],
                    "snare_times": [],
                    "hihat_times": [],
                    "_stage_status": {"beats": "completed"},
                    "_stage_errors": {},
                },
            )
            checkpoint_done.set()
            release_worker.wait(timeout=3.0)
            on_stage_checkpoint(
                "structure",
                {
                    "clip_id": clip_id,
                    "duration_seconds": 30.0,
                    "structure_segments": [
                        {"start_time": 0.0, "end_time": 30.0, "label": "late"}
                    ],
                    "_stage_status": {"structure": "completed"},
                    "_stage_errors": {},
                },
            )
            raise AssertionError("late checkpoint must stop cancelled worker")
        finally:
            worker_done.set()

    async def no_event(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)
    monkeypatch.setattr(audio_router, "publish_event", no_event)
    monkeypatch.setattr(audio_router, "publish_log", no_event)

    async def scenario() -> None:
        request = AudioAnalyzeRequest(
            clip_id=7,
            detect_beats=True,
            detect_structure=True,
            spectral_analysis=False,
            detect_key=False,
        )
        task = asyncio.create_task(audio_router.analyze_audio(request, state))
        assert await asyncio.to_thread(checkpoint_done.wait, 2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        release_worker.set()
        assert await asyncio.to_thread(worker_done.wait, 2.0)

    asyncio.run(scenario())

    assert len(state.persisted_history) == 2
    assert state.persisted_history[0]["stage_status"] == {"beats": "completed"}
    assert state.persisted_history[-1]["stage_status"] == {
        "beats": "completed",
        "structure": "interrupted",
    }
    assert state.persisted_history[-1]["bpm"] == 128.0
    assert state.persisted_history[-1]["structure_segments"] is None
