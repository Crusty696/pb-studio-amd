"""Real async GPU wrapper, fake model: serialize and drain before unlocking."""

from __future__ import annotations

import asyncio
import importlib
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace

import pytest


WAIT_SECONDS = 5.0


@pytest.fixture
def lifecycle(monkeypatch):
    dependencies = importlib.import_module("backend.dependencies")
    router = importlib.import_module("backend.routers.audio_router")
    tracker_module = importlib.import_module("pb_studio.audio.beat_this_tracker")
    budget_module = importlib.import_module("pb_studio.core.vram_budget_manager")
    lock = asyncio.Lock()
    cleanup_tasks = set()
    monkeypatch.setattr(dependencies, "gpu_lock", lock)
    monkeypatch.setattr(dependencies, "_gpu_cleanup_tasks", cleanup_tasks)
    # Use the actual shared wrapper, including its cancellation cleanup task.
    monkeypatch.setattr(router, "with_gpu_task", dependencies.with_gpu_task)
    events = []
    trackers = []
    behavior = SimpleNamespace(
        run=None, constructor_error=None, reserve=True, commit=True,
        register_error=None, session_ref=None,
    )

    class Manager:
        total_committed_mb = 0

        def register_model(self, model_id, name, size):
            assert lock.locked()
            events.append(("register", model_id))
            if behavior.register_error is not None:
                raise behavior.register_error

        def reserve(self, model_id):
            assert lock.locked()
            events.append(("reserve", model_id))
            return behavior.reserve

        def commit(self, model_id):
            assert lock.locked()
            events.append(("commit", model_id))
            return behavior.commit

        def release(self, model_id):
            assert lock.locked()
            assert trackers[-1].closed, "Release must follow physical session close"
            if behavior.session_ref is not None:
                assert behavior.session_ref() is None, "Unwound traceback retains physical session"
            events.append(("release", model_id))

        def cancel_reservation(self, model_id):
            assert lock.locked()
            events.append(("cancel_reservation", model_id))

        def unregister_model(self, model_id):
            assert lock.locked()
            events.append(("unregister", model_id))

        def record_task_observation(self, **kwargs):
            assert lock.locked()
            events.append(("observation", kwargs["success"]))

    class Tracker:
        def __init__(self):
            assert lock.locked()
            if behavior.constructor_error is not None:
                raise behavior.constructor_error
            self.number = len(trackers)
            self.closed = False
            self.manifest = {"revision": "fixture-revision"}
            trackers.append(self)
            events.append(("open", self.number))

        def track_file(self, path, guard, progress):
            assert lock.locked()
            events.append(("infer", self.number))
            if behavior.run is not None:
                behavior.run(self, guard)
            guard()
            progress(100.0)
            return [0.0, 0.5], [0.0]

        def close(self):
            assert lock.locked(), "Session must close before global GPU unlock"
            self.closed = True
            self._session = None
            events.append(("close", self.number))

    manager = Manager()
    monkeypatch.setattr(tracker_module, "BeatThisTracker", Tracker)
    monkeypatch.setattr(budget_module, "get_vram_manager", lambda: manager)
    return SimpleNamespace(
        router=router, lock=lock, cleanup=cleanup_tasks, events=events,
        trackers=trackers, behavior=behavior, tracker_module=tracker_module,
    )


async def _wait_thread_event(event):
    assert await asyncio.to_thread(event.wait, WAIT_SECONDS), "Worker did not reach gate"


async def _drain(lifecycle):
    pending = tuple(lifecycle.cleanup)
    if pending:
        await asyncio.wait_for(asyncio.gather(*pending), WAIT_SECONDS)


def _run(lifecycle):
    return lifecycle.router._track_neural_downbeats(
        "fixture.wav", 1.0, lambda: None, lambda *args: None,
    )


def test_two_neural_tasks_serialize_and_close_before_unlock(lifecycle):
    started = threading.Event()
    release = threading.Event()

    def run(tracker, guard):
        if tracker.number == 0:
            started.set()
            assert release.wait(WAIT_SECONDS)

    lifecycle.behavior.run = run

    async def scenario():
        first = asyncio.create_task(_run(lifecycle))
        second = None
        try:
            await _wait_thread_event(started)
            second = asyncio.create_task(_run(lifecycle))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert len(lifecycle.trackers) == 1
            assert lifecycle.lock.locked()
        finally:
            release.set()
            await asyncio.wait_for(
                asyncio.gather(*[task for task in (first, second) if task]),
                WAIT_SECONDS,
            )
        assert lifecycle.events.index(("close", 0)) < lifecycle.events.index(("open", 1))
        assert all(tracker.closed for tracker in lifecycle.trackers)
        assert not lifecycle.lock.locked()
        assert not lifecycle.cleanup

    asyncio.run(scenario())


def test_running_cancellation_retains_lock_until_guard_exits_and_session_closes(lifecycle):
    started = threading.Event()
    release = threading.Event()
    reached_guard = threading.Event()

    def run(tracker, guard):
        started.set()
        assert release.wait(WAIT_SECONDS)
        reached_guard.set()
        guard()

    lifecycle.behavior.run = run

    async def scenario():
        task = asyncio.create_task(_run(lifecycle))
        try:
            await _wait_thread_event(started)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert lifecycle.lock.locked()
            assert lifecycle.cleanup
            assert not lifecycle.trackers[0].closed
            assert not reached_guard.is_set()
        finally:
            release.set()
            await _drain(lifecycle)
            if not task.done():
                await asyncio.wait_for(task, WAIT_SECONDS)
        assert reached_guard.is_set()
        assert lifecycle.trackers[0].closed
        assert not lifecycle.lock.locked()
        assert ("observation", False) in lifecycle.events

    asyncio.run(scenario())


def test_cancellation_while_waiting_never_constructs_or_runs_tracker(lifecycle):
    async def scenario():
        await lifecycle.lock.acquire()
        task = asyncio.create_task(_run(lifecycle))
        try:
            await asyncio.sleep(0)
            assert not task.done()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert lifecycle.lock.locked(), "Waiting task must not release another owner's lock"
            assert lifecycle.trackers == []
            assert lifecycle.events == []
            assert not lifecycle.cleanup
        finally:
            lifecycle.lock.release()

    asyncio.run(scenario())


def test_asset_error_releases_lock_without_registering_a_session(lifecycle):
    error = lifecycle.tracker_module.BeatThisUnavailable("fixture hash mismatch")
    lifecycle.behavior.constructor_error = error

    async def scenario():
        with pytest.raises(type(error), match="hash mismatch"):
            await _run(lifecycle)
        assert not lifecycle.lock.locked()
        assert lifecycle.trackers == []
        assert not any(name == "register" for name, value in lifecycle.events)
        assert ("observation", False) in lifecycle.events
        assert not lifecycle.cleanup

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["reserve", "commit"])
def test_vram_failure_closes_session_and_cleans_budget_before_unlock(lifecycle, failure):
    setattr(lifecycle.behavior, failure, False)

    async def scenario():
        with pytest.raises(RuntimeError, match="VRAM"):
            await _run(lifecycle)
        assert lifecycle.trackers[0].closed
        assert not lifecycle.lock.locked()
        names = [name for name, value in lifecycle.events]
        assert "infer" not in names
        assert names.index("close") < names.index("release")
        assert names.index("release") < names.index("cancel_reservation")
        assert names.index("cancel_reservation") < names.index("unregister")
        assert not lifecycle.cleanup

    asyncio.run(scenario())


def test_exception_traceback_cannot_retain_session_after_budget_release(lifecycle):
    retained_errors = []

    class Session:
        pass

    def run(tracker, guard):
        session = Session()
        tracker._session = session
        lifecycle.behavior.session_ref = weakref.ref(session)
        error = RuntimeError("fixture ORT failure with local session")
        retained_errors.append(error)
        raise error

    lifecycle.behavior.run = run

    async def scenario():
        with pytest.raises(RuntimeError, match="ORT failure") as raised:
            await _run(lifecycle)
        assert raised.value is retained_errors[0]
        assert retained_errors[0].__traceback__ is not None
        assert lifecycle.behavior.session_ref() is None
        assert lifecycle.trackers[0].closed
        assert not lifecycle.lock.locked()
        assert any(name == "release" for name, _ in lifecycle.events)

    asyncio.run(scenario())


def test_registration_failure_still_closes_tracker(lifecycle):
    lifecycle.behavior.register_error = RuntimeError("fixture registration failure")

    async def scenario():
        with pytest.raises(RuntimeError, match="registration failure"):
            await _run(lifecycle)
        assert lifecycle.trackers[0].closed
        assert not lifecycle.lock.locked()
        names = [name for name, _ in lifecycle.events]
        assert "close" in names
        assert "infer" not in names
        assert "reserve" not in names
        assert not lifecycle.cleanup

    asyncio.run(scenario())


def test_api_neural_bridge_progresses_with_single_default_executor_worker(
    lifecycle, monkeypatch, tmp_path
):
    """Actual API dispatch must not block its own default-pool inference worker."""
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio = tmp_path / "executor-fixture.wav"
    audio.write_bytes(b"fixture")

    class State:
        def require_project_context_current(self, context):
            pass

        @asynccontextmanager
        async def project_operation(self):
            yield object()

        @contextmanager
        def project_commit(self, context):
            yield

        def get_audio_clip(self, clip_id):
            return {
                "id": clip_id, "name": "executor-fixture", "path": str(audio),
                "duration_seconds": 1.0, "audio_hash": None, "is_analyzed": False,
            }

        def get_audio_analysis(self, clip_id):
            return {}

        def update_audio_analysis(self, **kwargs):
            pass

    def analysis(path, clip_id, request, stems, progress,
                 on_stage_checkpoint=None, neural_downbeat_runner=None):
        assert neural_downbeat_runner is not None
        beats, downbeats, revision = neural_downbeat_runner(path, 1.0)
        assert revision == "fixture-revision"
        return {
            "clip_id": clip_id, "duration_seconds": 1.0, "bpm": 120.0,
            "beat_count": len(beats),
            "beats": [
                {"time": time, "strength": 0.5, "beat_type": "downbeat" if time in downbeats else "beat"}
                for time in beats
            ],
            "downbeats": downbeats,
            "downbeat_provenance": {"status": "measured", "model_revision": revision},
            "energy_curve": [0.5], "onset_times": beats, "kick_times": beats,
            "snare_times": [], "hihat_times": [], "structure_segments": [],
            "spectral_data": None, "key": None,
            "_analysis_status": "completed",
            "_stage_status": {"beats": "completed", "structure": "skipped", "spectral": "skipped", "key": "skipped"},
            "_stage_errors": {},
        }

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr(lifecycle.router, "_run_audio_analysis", analysis)
    monkeypatch.setattr(lifecycle.router, "publish_event", noop)
    monkeypatch.setattr(lifecycle.router, "publish_log", noop)
    monkeypatch.setattr(lifecycle.router, "_store_audio_embedding_in_brain_cache", noop)

    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        requests = [
            AudioAnalyzeRequest(
                clip_id=index, detect_beats=True, detect_structure=False,
                spectral_analysis=False, detect_key=False,
            )
            for index in range(1, 4)
        ]
        responses = await asyncio.wait_for(
            asyncio.gather(*[
                lifecycle.router.analyze_audio(request, State()) for request in requests
            ]), WAIT_SECONDS,
        )
        assert [response.bpm for response in responses] == [120.0] * 3
        assert len(lifecycle.trackers) == 3
        assert all(tracker.closed for tracker in lifecycle.trackers)
        assert not lifecycle.lock.locked()

    with ThreadPoolExecutor(max_workers=2) as audio_pool:
        monkeypatch.setattr(lifecycle.router, "_audio_analysis_pool", audio_pool)
        asyncio.run(scenario())
