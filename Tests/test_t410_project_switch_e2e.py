"""T410: project A jobs cannot publish or persist into project B."""

from __future__ import annotations

import asyncio
import copy
import importlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from backend.app_state import AppState
from backend.schemas.audio_schemas import AudioAnalyzeRequest
from backend.schemas.brain_schemas import BrainFeedbackRequest
from backend.schemas.pacing_schemas import (
    PacingConfigSchema,
    TimelineEntrySchema,
    TimelineUpdateRequest,
)
from backend.schemas.video_schemas import VideoAnalyzeRequest
from pb_studio.brain.brain_service import BrainService, StaleBrainProjectLeaseError
from pb_studio.storage.migration_runner import migrate


audio_router = importlib.import_module("backend.routers.audio_router")
brain_router = importlib.import_module("backend.routers.brain_router")
pacing_router = importlib.import_module("backend.routers.pacing_router")
project_router = importlib.import_module("backend.routers.project_router")
video_router = importlib.import_module("backend.routers.video_router")


_WAIT_SECONDS = 3.0


class _WorkerBarrier:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def run(self, result: Any) -> Any:
        self.entered.set()
        try:
            if not self.release.wait(_WAIT_SECONDS):
                raise TimeoutError("T410 worker release was not signalled")
            return result
        finally:
            self.finished.set()


class _BarrierConnection:
    """Delegates to the real SQLite connection after one bounded read barrier."""

    def __init__(self, connection: sqlite3.Connection, barrier: _WorkerBarrier) -> None:
        self._connection = connection
        self._barrier = barrier

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        self._barrier.run(None)
        return self._connection.execute(sql, params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not path.name.endswith((".db", ".db-wal", ".db-shm"))
    }


def _sqlite_snapshot(path: Path) -> dict[str, tuple[tuple[Any, ...], ...]]:
    with sqlite3.connect(path) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            name: tuple(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
            for name in table_names
        }


def _runtime_snapshot(state: AppState) -> dict[str, Any]:
    return copy.deepcopy(
        {
            "project": state.current_project,
            "audio": state.get_audio_clips_snapshot(),
            "audio_analysis": state.audio_analysis_cache,
            "video": state.get_video_clips_snapshot(),
            "video_analysis": state.get_video_analysis_snapshot(),
            "timeline": state.get_timeline_snapshot(),
            "audio_path": state.current_audio_path,
        }
    )


def _prepare_projects(tmp_path: Path, database_path: Path) -> tuple[AppState, AppState, Path, dict]:
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()

    audio_a = project_a / "audio-a.wav"
    video_a = project_a / "video-a.mp4"
    audio_b = project_b / "audio-b.wav"
    video_b = project_b / "video-b.mp4"
    for path, payload in (
        (audio_a, b"A-audio"),
        (video_a, b"A-video"),
        (audio_b, b"B-audio-canary"),
        (video_b, b"B-video-canary"),
    ):
        path.write_bytes(payload)

    (project_b / "project.json").write_text('{"canary":"project-b"}', encoding="utf-8")
    (project_b / "timeline.json").write_text('{"canary":"timeline-b"}', encoding="utf-8")
    migrations = Path(__file__).resolve().parents[1] / "src" / "pb_studio" / "storage" / "migrations" / "state"
    state_a_path = project_a / "state.db"
    state_b_path = project_b / "state.db"
    migrate(state_a_path, migrations)
    migrate(state_b_path, migrations)
    with sqlite3.connect(state_a_path) as connection:
        connection.execute(
            "INSERT INTO timelines(id, name, audio_clip_id, created_at, is_current) "
            "VALUES (1, 'A timeline', 1, '2026-08-01T00:00:00Z', 1)"
        )
        connection.execute(
            "INSERT INTO timeline_cuts("
            "id, timeline_id, position_idx, clip_id, start_time, end_time, "
            "brain_scores_json, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                1,
                0,
                "clip_1",
                0.0,
                1.0,
                json.dumps({"beat_weight": 0.8}),
                json.dumps(
                    {
                        "bridge_values": {"beat_weight": 0.8},
                        "context_keys": [
                            "global",
                            "segment",
                            "mood",
                            "motion",
                            "audio",
                            "clip",
                        ],
                    }
                ),
            ),
        )
        connection.commit()
    with sqlite3.connect(state_b_path) as connection:
        connection.execute("CREATE TABLE t410_brain_canary (value TEXT NOT NULL)")
        connection.execute("INSERT INTO t410_brain_canary VALUES ('B-brain-canary')")
        connection.commit()

    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE t410_canary (project_id INTEGER, value TEXT)")
        connection.execute("INSERT INTO t410_canary VALUES (?, ?)", (202, "B-database-canary"))
        connection.commit()

    state = AppState(
        current_project={"db_project_id": 101, "path": str(project_a), "name": "A"},
        audio_clips={
            1: {
                "id": 1,
                "name": "audio-a.wav",
                "path": str(audio_a),
                "duration_seconds": 30.0,
            }
        },
        audio_analysis_cache={
            1: {
                "bpm": 120.0,
                "beat_count": 2,
                "beats": [0.0, 0.5],
                "energy_curve": [0.5, 0.6],
                "downbeats": [0.0],
                "onset_times": [0.0],
                "kick_times": [0.0],
                "snare_times": [0.5],
                "hihat_times": [0.25],
                "downbeat_provenance": {"source": "test"},
                "_stage_status": {"beats": "completed"},
            }
        },
        video_clips={
            1: {
                "id": 1,
                "name": "video-a.mp4",
                "path": str(video_a),
                "duration_seconds": 30.0,
            }
        },
        video_analysis_cache={1: {"status": "completed", "avg_motion": 0.2}},
        current_timeline=[{"clip_id": "clip_1", "start_time": 0.0, "end_time": 2.0}],
        current_audio_path=str(audio_a),
    )
    candidate_b = AppState(
        audio_clips={
            1: {
                "id": 1,
                "name": "audio-b.wav",
                "path": str(audio_b),
                "duration_seconds": 44.0,
                "canary": "B-audio",
            }
        },
        audio_analysis_cache={1: {"bpm": 99.0, "canary": "B-analysis"}},
        video_clips={
            1: {
                "id": 1,
                "name": "video-b.mp4",
                "path": str(video_b),
                "duration_seconds": 44.0,
                "canary": "B-video",
            }
        },
        video_analysis_cache={1: {"status": "completed", "canary": "B-video-analysis"}},
        current_timeline=[
            {
                "clip_id": "clip_1",
                "start_time": 10.0,
                "end_time": 12.0,
                "metadata": {"canary": "B-timeline"},
            }
        ],
        current_audio_path=str(audio_b),
    )
    project_data_b = {"db_project_id": 202, "path": str(project_b), "name": "B"}
    return state, candidate_b, project_b, project_data_b


def _start_operation(
    operation: str,
    state: AppState,
    barrier: _WorkerBarrier,
    monkeypatch: pytest.MonkeyPatch,
) -> asyncio.Task[Any]:
    if operation == "audio":
        monkeypatch.setattr(
            audio_router,
            "_run_audio_analysis",
            lambda *_args, **_kwargs: barrier.run(
                {"clip_id": 1, "duration_seconds": 30.0, "bpm": 222.0, "beat_count": 1}
            ),
        )
        return asyncio.create_task(audio_router.analyze_audio(AudioAnalyzeRequest(clip_id=1), state))

    if operation == "video":
        monkeypatch.setattr(
            video_router,
            "_run_scene_detection",
            lambda *_args, **_kwargs: barrier.run(
                {"scene_count": 1, "scenes": [], "stage_status": {}, "stage_errors": {}}
            ),
        )
        return asyncio.create_task(video_router.analyze_video(VideoAnalyzeRequest(clip_id=1), state))

    if operation == "pacing":
        monkeypatch.setattr(
            pacing_router,
            "_run_pacing_generation",
            lambda *_args, **_kwargs: barrier.run(
                [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0, "metadata": {}}]
            ),
        )
        request = PacingConfigSchema(audio_clip_id=1, video_clip_ids=[1])
        return asyncio.create_task(pacing_router.generate_cut_list(request, state))

    if operation == "timeline":
        from pb_studio.rendering.render_service import RenderService

        monkeypatch.setattr(
            RenderService,
            "_get_audio_duration",
            lambda _self, _path: barrier.run(30.0),
        )
        video_path = state.get_video_clip(1)["path"]
        request = TimelineUpdateRequest(
            entries=[
                TimelineEntrySchema(
                    clip_id="clip_1",
                    clip_name="video-a.mp4",
                    file_path=video_path,
                    start_time=0.0,
                    end_time=1.0,
                )
            ]
        )
        return asyncio.create_task(pacing_router.update_timeline(request, state))

    if operation == "brain":
        return asyncio.create_task(
            brain_router.feedback(BrainFeedbackRequest(cut_id=1, rating="perfect"), state)
        )

    raise AssertionError(f"unknown T410 operation: {operation}")


@pytest.mark.parametrize("operation", ["audio", "video", "pacing", "timeline", "brain"])
def test_project_switch_cancels_a_job_without_mutating_b(
    operation: str,
    tmp_path: Path,
    isolated_test_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        state, candidate_b, project_b, project_data_b = _prepare_projects(
            tmp_path, isolated_test_database
        )
        expected_b = _runtime_snapshot(candidate_b)
        expected_b["project"] = project_data_b
        database_before = _sqlite_snapshot(isolated_test_database)
        brain_database_before = _sqlite_snapshot(project_b / "state.db")
        files_before = _file_snapshot(project_b)
        barrier = _WorkerBarrier()
        brain_service: BrainService | None = None
        captured_brain_leases: list[Any] = []

        if operation == "brain":
            brain_service = BrainService(brain_dir=tmp_path / "brain-runtime")
            brain_service.bind_project_state(
                tmp_path / "project-a" / "state.db",
                project_epoch=state.project_epoch,
                project_id=101,
            )
            monkeypatch.setattr(
                BrainService,
                "get",
                classmethod(lambda cls, **_kwargs: brain_service),
            )
            monkeypatch.setattr(brain_router, "get_brain_service", lambda: brain_service)
            acquire_real_lease = brain_router._acquire_project_state_lease

            def acquire_barrier_lease(service: BrainService, context: Any) -> Any:
                lease = acquire_real_lease(service, context)
                lease._slot.connection = _BarrierConnection(lease._slot.connection, barrier)
                captured_brain_leases.append(lease)
                return lease

            monkeypatch.setattr(
                brain_router,
                "_acquire_project_state_lease",
                acquire_barrier_lease,
            )
        else:
            monkeypatch.setattr(
                project_router,
                "_bind_brain_to_project",
                lambda *_args, **_kwargs: None,
            )
        task = _start_operation(operation, state, barrier, monkeypatch)
        try:
            entered = await asyncio.wait_for(
                asyncio.to_thread(barrier.entered.wait, _WAIT_SECONDS),
                timeout=_WAIT_SECONDS + 0.5,
            )
            assert entered, f"{operation} did not reach its worker boundary"

            await asyncio.wait_for(
                project_router._activate_project(state, project_b, project_data_b, candidate_b),
                timeout=_WAIT_SECONDS,
            )
            assert task.cancelled(), f"{operation} task was not cancelled by project switch"

            barrier.release.set()
            finished = await asyncio.wait_for(
                asyncio.to_thread(barrier.finished.wait, _WAIT_SECONDS),
                timeout=_WAIT_SECONDS + 0.5,
            )
            assert finished, f"{operation} worker did not finish after bounded release"
            with pytest.raises(asyncio.CancelledError):
                await task

            assert _runtime_snapshot(state) == expected_b
            assert _sqlite_snapshot(isolated_test_database) == database_before
            assert _sqlite_snapshot(project_b / "state.db") == brain_database_before
            assert _file_snapshot(project_b) == files_before
            if operation == "brain":
                assert brain_service is not None
                assert captured_brain_leases
                identity = brain_service.project_state_identity
                assert identity is not None
                assert identity.state_db_path == (project_b / "state.db").resolve()
                assert identity.project_id == 202
                assert identity.epoch == state.project_epoch
                with pytest.raises(StaleBrainProjectLeaseError):
                    captured_brain_leases[0].run_write(
                        lambda connection: connection.execute(
                            "INSERT INTO feedback_events("
                            "cut_id, rating, alpha_delta, beta_delta, "
                            "context_keys_json, timestamp) "
                            "VALUES (1, 'perfect', 1, 0, '[]', 'stale')"
                        )
                    )
        finally:
            barrier.release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if brain_service is not None:
                brain_service.close()

    asyncio.run(scenario())
