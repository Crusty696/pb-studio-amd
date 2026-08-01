from __future__ import annotations

import asyncio
import hashlib
import importlib
import multiprocessing
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from backend.app_state import AppState
from backend.schemas.render_schemas import RenderRequest
from pb_studio.rendering.render_queue import (
    RenderQueue,
    STATE_COMPLETED,
    STATE_INTERRUPTED,
    STATE_RUNNING,
)


render_router = importlib.import_module("backend.routers.render_router")


class _StandaloneRenderDb:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(
            str(path),
            timeout=30.0,
            check_same_thread=False,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout = 30000")
        self.connection.execute("PRAGMA journal_mode = WAL")

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def get_connection(self) -> sqlite3.Connection:
        return self.connection

    def close(self) -> None:
        self.connection.close()


def _enqueue_in_process(
    db_path: str,
    output_path: str,
    barrier: Any,
    results: Any,
) -> None:
    database = _StandaloneRenderDb(Path(db_path))
    try:
        queue = RenderQueue(database)
        barrier.wait(timeout=15.0)
        job = queue.enqueue(
            "cross-process-media",
            output_path,
            {"encoder": "h264_amf", "fps": 30.0},
        )
        results.put(("ok", job.job_id))
    except Exception as exc:
        results.put(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        database.close()


def test_cross_process_enqueue_returns_one_active_attempt(tmp_path: Path) -> None:
    db_path = tmp_path / "render-cross-process.db"
    output_path = str(tmp_path / "same-output.mp4")
    parent_database = _StandaloneRenderDb(db_path)
    parent_queue = RenderQueue(parent_database)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    results = context.Queue()
    processes = [
        context.Process(
            target=_enqueue_in_process,
            args=(str(db_path), output_path, barrier, results),
        )
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        barrier.wait(timeout=15.0)
        responses = [results.get(timeout=20.0) for _ in processes]
        for process in processes:
            process.join(timeout=20.0)
            assert process.exitcode == 0

        assert all(status == "ok" for status, _ in responses), responses
        assert len({job_id for _, job_id in responses}) == 1
        assert len(parent_queue.list_jobs()) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        parent_database.close()


def test_content_identity_hashes_missing_catalog_hashes_and_detects_changes(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "mix.wav"
    video = tmp_path / "clip.mp4"
    audio.write_bytes(b"audio-v1")
    video.write_bytes(b"video-v1")
    request = RenderRequest(
        output_path=str(tmp_path / "render.mp4"),
        audio_path=str(audio),
    )
    timeline = [{
        "clip_id": "clip_1",
        "start_time": 0.0,
        "end_time": 1.0,
        "metadata": {"file_path": str(video)},
    }]
    state = AppState(
        audio_clips={1: {"path": str(audio)}},
        video_clips={1: {"path": str(video)}},
    )

    first_digest, first_snapshot = render_router._build_render_identity(
        request,
        timeline,
        state,
        project_root=tmp_path,
        project_db_id=7,
    )
    assert first_snapshot["media_content_hashes"]["audio"]["content_hash"] == (
        hashlib.sha256(b"audio-v1").hexdigest()
    )
    assert first_snapshot["media_content_hashes"]["video"][0]["content_hash"] == (
        hashlib.sha256(b"video-v1").hexdigest()
    )

    audio.write_bytes(b"audio-v2")
    video.write_bytes(b"video-v2")
    second_digest, _ = render_router._build_render_identity(
        request,
        timeline,
        state,
        project_root=tmp_path,
        project_db_id=7,
    )
    assert second_digest != first_digest


def test_resume_runs_interrupted_attempt_to_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    queue = render_router._get_render_queue()
    audio = tmp_path / "mix.wav"
    video = tmp_path / "clip.mp4"
    output = tmp_path / "resume.mp4"
    audio.write_bytes(b"audio")
    video.write_bytes(b"video")
    timeline = [{
        "clip_id": "clip_1",
        "start_time": 0.0,
        "end_time": 1.0,
        "metadata": {"file_path": str(video)},
    }]
    request = RenderRequest(output_path=str(output), audio_path=str(audio))
    media_state = AppState(
        current_project={"path": str(tmp_path), "db_project_id": 1},
        audio_clips={1: {"path": str(audio), "audio_hash": "audio-hash"}},
        video_clips={1: {"path": str(video), "video_hash": "video-hash"}},
    )
    media_digest, identity_snapshot = render_router._build_render_identity(
        request,
        timeline,
        media_state,
        project_root=tmp_path,
        project_db_id=1,
    )
    job = queue.enqueue(
        media_digest,
        str(output),
        render_router._request_settings_dict(
            request,
            timeline_snapshot=timeline,
            project_root=tmp_path,
            project_db_id=1,
            identity_snapshot=identity_snapshot,
        ),
    )
    queue.update_status(job.job_id, STATE_RUNNING)
    transitions: list[str] = []
    original_update = queue.update_status

    def recording_update(job_id: str, status: str, **kwargs: Any):
        transitions.append(status)
        return original_update(job_id, status, **kwargs)

    async def no_op(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(queue, "update_status", recording_update)
    monkeypatch.setattr(
        render_router,
        "_load_resume_media_state",
        lambda *_args: (media_state, tmp_path),
    )
    monkeypatch.setattr(render_router, "_acquire_gpu_lock_or_cancel", no_op)
    monkeypatch.setattr(render_router.gpu_lock, "release", lambda: None)
    monkeypatch.setattr(render_router, "publish_event", no_op)
    monkeypatch.setattr(render_router, "publish_log", no_op)
    monkeypatch.setattr(
        render_router,
        "_execute_render",
        lambda *_args, **_kwargs: {
            "progress_end": True,
            "run_id": "t412-resume",
            "evidence_path": None,
            "validation_path": None,
            "validation_status": "passed",
        },
    )

    async def run_resume() -> list[str]:
        render_router._render_runtime_tasks.clear()
        resumed = await render_router._resume_render_queue_on_startup(
            AppState(),
            queue=queue,
        )
        await asyncio.gather(*list(render_router._render_runtime_tasks.values()))
        return resumed

    resumed = asyncio.run(run_resume())
    restored = queue.get(job.job_id)
    assert resumed == [job.job_id]
    assert restored is not None
    assert restored.status == STATE_COMPLETED
    assert transitions == [STATE_INTERRUPTED, STATE_RUNNING, STATE_COMPLETED]
