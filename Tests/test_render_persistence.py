"""
Tests für die persistente Render-Queue.

Stellt sicher, dass:
  - Jobs über einen Backend-Restart hinweg erhalten bleiben.
  - 'running' Jobs beim Restart automatisch zu 'interrupted' requeued werden.
  - 'completed' / 'failed' Jobs ihren Endstatus nach Restart behalten.
  - Doppeltes Enqueue desselben Hashes (auch concurrent) keine Duplikate erzeugt.

Die isolated_test_database-Fixture (conftest.py) gibt jedem Test eine frische
SQLite-Datei. Den "Backend-Restart" simulieren wir via DatabaseCore.shutdown()
+ neuer DatabaseCore-Instanz; die Tabelle render_queue lebt im DB-File und ist
nach dem Restart automatisch wieder lesbar.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from pb_studio.data.database_core import DatabaseCore
from pb_studio.rendering import render_queue as rq_module
from pb_studio.rendering.render_queue import (
    DEFAULT_MAX_TERMINAL_JOBS,
    DEFAULT_RETENTION_DAYS,
    RenderQueue,
    STATE_CANCELLED,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_INTERRUPTED,
    STATE_QUEUED,
    STATE_RUNNING,
    compute_job_hash,
    compute_settings_hash,
    get_render_queue,
    reset_for_tests,
    select_terminal_retention,
)
from backend.app_state import AppState
from backend.routers.render_router import _cleanup_old_render_tasks
from backend.schemas.render_schemas import RenderProgress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(width: int = 1920, height: int = 1080, bitrate: float = 12.0) -> dict[str, Any]:
    return {
        "resolution_width": width,
        "resolution_height": height,
        "fps": 30.0,
        "bitrate_mbps": bitrate,
        "encoder": "h264_amf",
        "include_audio": True,
    }


def _restart_backend() -> RenderQueue:
    """Simuliert einen Backend-Restart.

    Schließt alle DB-Connections, vergisst sowohl das DatabaseCore- als auch
    das RenderQueue-Singleton, und liefert eine frische Queue gegen dieselbe
    DB-Datei zurück.
    """
    if DatabaseCore._instance is not None:
        DatabaseCore._instance.shutdown()
    DatabaseCore._instance = None
    reset_for_tests()
    return get_render_queue()


@pytest.fixture
def queue() -> RenderQueue:
    """Frische Queue + sicherer Cleanup zwischen Tests."""
    reset_for_tests()
    q = get_render_queue()
    yield q
    reset_for_tests()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_queue_persists_over_restart(queue: RenderQueue, tmp_path: Path) -> None:
    """Jobs müssen einen simulierten Backend-Crash überleben."""
    output = tmp_path / "render1.mp4"
    job = queue.enqueue(
        media_hash="hash-A",
        output_path=str(output),
        settings=_settings(),
    )
    assert job.status == STATE_QUEUED
    job_id = job.job_id

    # Restart
    new_queue = _restart_backend()
    restored = new_queue.get(job_id)

    assert restored is not None, "Job wurde beim Restart vergessen"
    assert restored.job_id == job_id
    assert restored.status == STATE_QUEUED
    assert restored.output_path == str(output)
    assert restored["media_hash"] == "hash-A"


def test_running_jobs_are_requeued_on_startup(queue: RenderQueue, tmp_path: Path) -> None:
    """'running' Jobs werden beim Startup automatisch zu 'interrupted'."""
    job1 = queue.enqueue("hash-1", str(tmp_path / "a.mp4"), _settings())
    job2 = queue.enqueue("hash-2", str(tmp_path / "b.mp4"), _settings())
    job3 = queue.enqueue("hash-3", str(tmp_path / "c.mp4"), _settings())

    queue.update_status(job1.job_id, STATE_RUNNING)
    queue.update_status(job2.job_id, STATE_RUNNING)
    # job3 bleibt queued

    # Restart → restore_running_as_interrupted() erfolgt explizit
    new_queue = _restart_backend()
    requeued = new_queue.restore_running_as_interrupted()

    assert sorted(requeued) == sorted([job1.job_id, job2.job_id])

    # Status-Check
    assert new_queue.get(job1.job_id).status == STATE_INTERRUPTED
    assert new_queue.get(job2.job_id).status == STATE_INTERRUPTED
    assert new_queue.get(job3.job_id).status == STATE_QUEUED

    # interrupted gilt als laufbereit
    pending_ids = {j.job_id for j in new_queue.list_pending()}
    assert pending_ids == {job1.job_id, job2.job_id, job3.job_id}


def test_startup_reconstructs_and_schedules_render_payload(
    queue: RenderQueue,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import importlib

    from backend.app_state import AppState
    from backend.schemas.render_schemas import RenderRequest

    render_router = importlib.import_module("backend.routers.render_router")
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"audio")
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "resume.mp4"
    timeline = [{
        "clip_id": "clip_1",
        "start_time": 0.0,
        "end_time": 2.0,
        "metadata": {"file_path": str(video)},
    }]
    request = RenderRequest(output_path=str(output), audio_path=str(audio))
    settings = render_router._request_settings_dict(
        request,
        timeline_snapshot=timeline,
        project_root=tmp_path,
        project_db_id=1,
    )
    job = queue.enqueue("resume-hash", str(output), settings)
    queue.update_status(job.job_id, STATE_RUNNING)

    scheduled = []

    async def fake_run(
        task_id,
        restored_request,
        state,
        restored_timeline,
        queue_job_id,
    ):
        scheduled.append((
            task_id,
            restored_request,
            state,
            restored_timeline,
            queue_job_id,
        ))

    monkeypatch.setattr(render_router, "_run_render_task", fake_run)
    media_state = AppState(
        audio_clips={1: {"path": str(audio)}},
        video_clips={1: {"path": str(video)}},
    )
    monkeypatch.setattr(
        render_router,
        "_load_resume_media_state",
        lambda *_args: (media_state, tmp_path),
    )
    state = AppState()
    resumed = asyncio.run(
        render_router._resume_render_queue_on_startup(state, queue=queue)
    )

    assert resumed == [job.job_id]
    assert len(scheduled) == 1
    (
        task_id,
        restored_request,
        restored_state,
        restored_timeline,
        queue_job_id,
    ) = scheduled[0]
    assert restored_state is state
    assert restored_request.audio_path == str(audio)
    assert restored_request.output_path == str(output)
    assert restored_timeline == timeline
    assert queue_job_id == job.job_id
    task = state.get_render_task(task_id)
    assert task is not None
    assert task["queue_job_id"] == job.job_id


def test_startup_marks_legacy_job_without_resume_payload_failed(
    queue: RenderQueue,
    tmp_path: Path,
) -> None:
    from backend.app_state import AppState
    from backend.routers.render_router import _resume_render_queue_on_startup

    job = queue.enqueue("legacy-hash", str(tmp_path / "legacy.mp4"), _settings())
    queue.update_status(job.job_id, STATE_RUNNING)

    resumed = asyncio.run(
        _resume_render_queue_on_startup(AppState(), queue=queue)
    )

    assert resumed == []
    restored = queue.get(job.job_id)
    assert restored is not None
    assert restored.status == STATE_FAILED
    assert "Resume-Payload" in (restored["error"] or "")


def test_shutdown_cancellation_of_resumed_job_remains_interrupted(
    queue: RenderQueue,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import importlib

    from backend.app_state import AppState
    from backend.schemas.render_schemas import RenderRequest

    render_router = importlib.import_module("backend.routers.render_router")
    output = tmp_path / "resume-shutdown.mp4"
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"audio")
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    request = RenderRequest(
        output_path=str(output),
        audio_path=str(audio),
    )
    timeline = [{
        "clip_id": "clip_1",
        "start_time": 0.0,
        "end_time": 1.0,
        "metadata": {"file_path": str(video)},
    }]
    job = queue.enqueue(
        "resume-shutdown-hash",
        str(output),
        render_router._request_settings_dict(
            request,
            timeline_snapshot=timeline,
            project_root=tmp_path,
            project_db_id=1,
        ),
    )
    queue.update_status(job.job_id, STATE_RUNNING)

    async def stubborn_render(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(render_router, "_run_render_task", stubborn_render)
    media_state = AppState(
        audio_clips={1: {"path": str(audio)}},
        video_clips={1: {"path": str(video)}},
    )
    monkeypatch.setattr(
        render_router,
        "_load_resume_media_state",
        lambda *_args: (media_state, tmp_path),
    )

    async def run() -> None:
        render_router._reset_render_runtime_for_startup()
        state = AppState()
        resumed = await render_router._resume_render_queue_on_startup(
            state,
            queue=queue,
        )
        assert resumed == [job.job_id]
        await render_router._shutdown_active_renders(
            state,
            cooperative_timeout=0.0,
            forced_timeout=0.0,
        )
        await asyncio.sleep(0)
        render_router._reset_render_runtime_for_startup()

    asyncio.run(run())

    restored = queue.get(job.job_id)
    assert restored is not None
    assert restored.status == STATE_INTERRUPTED
    assert "shutdown" in (restored["error"] or "").lower()


def test_completed_jobs_remain_completed_after_restart(queue: RenderQueue, tmp_path: Path) -> None:
    """'completed' darf von restore_running_as_interrupted nicht angefasst werden."""
    job = queue.enqueue("hash-done", str(tmp_path / "done.mp4"), _settings())
    queue.update_status(job.job_id, STATE_RUNNING)
    queue.update_status(job.job_id, STATE_COMPLETED)

    after_restart = _restart_backend()
    after_restart.restore_running_as_interrupted()

    restored = after_restart.get(job.job_id)
    assert restored is not None
    assert restored.status == STATE_COMPLETED
    assert restored["progress_percent"] == 100.0
    assert restored["finished_at"] is not None


def test_failed_jobs_remain_failed(queue: RenderQueue, tmp_path: Path) -> None:
    """'failed' Jobs überleben Restart unverändert (kein Auto-Retry)."""
    job = queue.enqueue("hash-fail", str(tmp_path / "fail.mp4"), _settings())
    queue.update_status(job.job_id, STATE_RUNNING)
    queue.update_status(job.job_id, STATE_FAILED, error="encoder timeout")

    after_restart = _restart_backend()
    after_restart.restore_running_as_interrupted()

    restored = after_restart.get(job.job_id)
    assert restored is not None
    assert restored.status == STATE_FAILED
    assert restored["error"] == "encoder timeout"


@pytest.mark.parametrize(
    "terminal_status",
    [STATE_COMPLETED, STATE_FAILED, STATE_CANCELLED],
)
def test_terminal_attempt_is_immutable_and_retry_gets_new_job(
    queue: RenderQueue,
    tmp_path: Path,
    terminal_status: str,
) -> None:
    output = str(tmp_path / f"retry-{terminal_status}.mp4")
    first = queue.enqueue("retry-hash", output, _settings())
    queue.update_status(first.job_id, STATE_RUNNING)
    queue.update_status(first.job_id, terminal_status, error=terminal_status)
    terminal_snapshot = dict(queue.get(first.job_id))

    with pytest.raises(ValueError, match="Terminaler Render-Job"):
        queue.update_status(first.job_id, STATE_RUNNING)

    assert dict(queue.get(first.job_id)) == terminal_snapshot
    retry = queue.enqueue("retry-hash", output, _settings())
    assert retry.job_id != first.job_id
    assert retry.status == STATE_QUEUED


def test_idempotent_enqueue(queue: RenderQueue, tmp_path: Path) -> None:
    """Doppeltes Enqueue desselben (media_hash, output_path, settings) gibt
    denselben Job zurück — keine zweite Zeile in der Tabelle."""
    output = str(tmp_path / "idemp.mp4")
    settings = _settings()

    first = queue.enqueue("hash-X", output, settings)
    second = queue.enqueue("hash-X", output, settings)

    assert second.job_id == first.job_id
    assert len(queue.list_jobs()) == 1

    # Andere Settings → eigener Job
    third = queue.enqueue("hash-X", output, _settings(width=3840, height=2160))
    assert third.job_id != first.job_id
    assert len(queue.list_jobs()) == 2

    # Anderes media_hash → eigener Job
    fourth = queue.enqueue("hash-Y", output, settings)
    assert fourth.job_id != first.job_id
    assert len(queue.list_jobs()) == 3

    # Gleiche Inputs nach Terminalstatus → neuer Retry-Attempt mit eigener ID
    queue.update_status(first.job_id, STATE_RUNNING)
    queue.update_status(first.job_id, STATE_COMPLETED)
    fifth = queue.enqueue("hash-X", output, settings)
    assert fifth.job_id != first.job_id
    assert fifth.status == STATE_QUEUED
    assert len(queue.list_jobs()) == 4


def test_concurrent_enqueue_does_not_double(queue: RenderQueue, tmp_path: Path) -> None:
    """Mehrere Threads, die parallel denselben Hash enqueuen, dürfen
    NIEMALS zwei Zeilen erzeugen."""
    output = str(tmp_path / "concurrent.mp4")
    settings = _settings()

    barrier = threading.Barrier(8)
    results: list[str] = []
    results_lock = threading.Lock()
    errors: list[Exception] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=5.0)
            job = queue.enqueue("hash-RACE", output, settings)
            with results_lock:
                results.append(job.job_id)
        except Exception as exc:  # pragma: no cover - reported via assert
            with results_lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker) for _ in range(8)]
        for f in futures:
            f.result(timeout=10)

    assert not errors, f"Worker errors: {errors}"
    assert len(results) == 8
    assert len(set(results)) == 1, f"Race produzierte mehrere job_ids: {set(results)}"
    assert len(queue.list_jobs()) == 1, "Mehrfache Zeilen in render_queue trotz Idempotency"


# ---------------------------------------------------------------------------
# Sanity-Checks für die Hash-Helfer (klein, aber wichtig für Idempotency)
# ---------------------------------------------------------------------------

def test_hash_helpers_are_deterministic() -> None:
    """compute_settings_hash / compute_job_hash müssen rein deterministisch sein."""
    settings = {"a": 1, "b": [1, 2], "c": {"x": "y"}}
    settings_reordered = {"c": {"x": "y"}, "b": [1, 2], "a": 1}
    assert compute_settings_hash(settings) == compute_settings_hash(settings_reordered)

    h1 = compute_job_hash("media-1", "/tmp/out.mp4", "ssh1")
    h2 = compute_job_hash("media-1", "/tmp/out.mp4", "ssh1")
    assert h1 == h2

    # Pfadtrenner werden normalisiert (Windows ↔ POSIX)
    h_win = compute_job_hash("media-1", r"C:\proj\out.mp4", "ssh1")
    h_posix = compute_job_hash("media-1", "C:/proj/out.mp4", "ssh1")
    assert h_win == h_posix


# ---------------------------------------------------------------------------
# Spec 00024: Render-Retention und Fortschritts-Parität
# ---------------------------------------------------------------------------

def test_select_terminal_retention_rules() -> None:
    """Prüft Alters- und Mengen-Grenzwerte, Schutz aktiver Jobs und ungültiger Zeitstempel."""
    now = 1_700_000_000.0  # Fester Testzeitpunkt (> _MIN_VALID_UTC_EPOCH)
    day = 86_400.0

    records = [
        # Zu alt (>30 Tage):
        {"job_id": "old-1", "status": "completed", "finished_at": now - (35 * day)},
        {"job_id": "old-2", "status": "failed", "finished_at": now - (31 * day)},
        # Jünger als 30 Tage:
        {"job_id": "recent-1", "status": "completed", "finished_at": now - (5 * day)},
        {"job_id": "recent-2", "status": "cancelled", "finished_at": now - (2 * day)},
        {"job_id": "recent-3", "status": "completed", "finished_at": now - (1 * day)},
        # Nicht terminal (muss geschützt werden):
        {"job_id": "active-1", "status": "running", "finished_at": now - (40 * day)},
        {"job_id": "active-2", "status": "queued", "finished_at": now - (40 * day)},
        {"job_id": "active-3", "status": "interrupted", "finished_at": now - (40 * day)},
        # Explizit geschützt:
        {"job_id": "protected-1", "status": "completed", "finished_at": now - (40 * day)},
        # Ungültige/fehlende finished_at:
        {"job_id": "invalid-none", "status": "completed", "finished_at": None},
        {"job_id": "invalid-monotonic", "status": "failed", "finished_at": 12345.6},  # < 946684800.0
        {"job_id": "invalid-text", "status": "cancelled", "finished_at": "not-a-number"},
    ]

    # Test 1: retention_days=30, max_terminal_jobs=5
    # old-1 und old-2 fallen durch Altersgrenze raus. recent-1..3 bleiben (<= 5).
    deleted, invalid = select_terminal_retention(
        records,
        now_epoch=now,
        retention_days=30,
        max_terminal_jobs=5,
        protected_ids=frozenset({"protected-1"}),
    )
    assert set(deleted) == {"old-1", "old-2"}
    assert set(invalid) == {"invalid-none", "invalid-monotonic", "invalid-text"}

    # Test 2: max_terminal_jobs=1: Nach Altersprüfung bleiben recent-1, 2, 3 (3 Stück).
    # Bei max=1 müssen die 2 ältesten ("recent-1", "recent-2") zusätzlich gelöscht werden.
    deleted2, invalid2 = select_terminal_retention(
        records,
        now_epoch=now,
        retention_days=30,
        max_terminal_jobs=1,
        protected_ids=frozenset({"protected-1"}),
    )
    assert deleted2 == ["old-1", "old-2", "recent-1", "recent-2"]


def test_render_queue_cleanup_terminal(queue: RenderQueue, tmp_path: Path) -> None:
    """Queue.cleanup_terminal löscht ausschließlich gewählte terminale Metadaten aus SQLite."""
    now = 1_700_000_000.0
    day = 86_400.0

    # Job anlegen & manuell auf completed mit altem Zeitstempel setzen
    job1 = queue.enqueue("hash-1", str(tmp_path / "1.mp4"), _settings())
    queue.update_status(job1.job_id, STATE_RUNNING)
    queue.update_status(job1.job_id, STATE_COMPLETED)
    with queue._db.transaction(immediate=True) as conn:
        conn.execute(
            "UPDATE render_queue SET finished_at = ? WHERE job_id = ?",
            (now - (35 * day), job1.job_id),
        )

    # Neuerer Job
    job2 = queue.enqueue("hash-2", str(tmp_path / "2.mp4"), _settings())
    queue.update_status(job2.job_id, STATE_RUNNING)
    queue.update_status(job2.job_id, STATE_COMPLETED)
    with queue._db.transaction(immediate=True) as conn:
        conn.execute(
            "UPDATE render_queue SET finished_at = ? WHERE job_id = ?",
            (now - (2 * day), job2.job_id),
        )

    # Aktiver Job (darf nicht gelöscht werden)
    job3 = queue.enqueue("hash-3", str(tmp_path / "3.mp4"), _settings())

    res = queue.cleanup_terminal(
        retention_days=30,
        max_terminal_jobs=50,
        now_epoch=now,
    )
    assert res["deleted"] == [job1.job_id]
    assert queue.get(job1.job_id) is None
    assert queue.get(job2.job_id) is not None
    assert queue.get(job3.job_id) is not None


def test_cleanup_old_render_tasks_syncs_memory_and_queue(tmp_path: Path) -> None:
    """_cleanup_old_render_tasks bereinigt AppState.render_tasks und Queue synchron."""
    now = 1_700_000_000.0
    day = 86_400.0
    state = AppState()
    state.render_tasks = {
        "task-expired": {
            "status": "completed",
            "percent": 100.0,
            "progress_percent": 100.0,
            "finished_at": now - (40 * day),
        },
        "task-recent": {
            "status": "completed",
            "percent": 100.0,
            "progress_percent": 100.0,
            "finished_at": now - (1 * day),
        },
        "task-running": {
            "status": "running",
            "percent": 50.0,
            "progress_percent": 50.0,
        },
        "task-invalid-time": {
            "status": "failed",
            "percent": 20.0,
            "progress_percent": 20.0,
            "finished_at": 50.0,  # < _MIN_VALID_UTC_EPOCH
        },
    }
    state.cancel_flags["task-expired"] = False
    state.cancel_flags["task-running"] = False

    res = _cleanup_old_render_tasks(
        state,
        max_tasks=50,
        retention_days=30,
        now_epoch=now,
    )
    assert "task-expired" in res["deleted"]
    assert "task-expired" not in state.render_tasks
    assert "task-expired" not in state.cancel_flags  # > 1h alt -> gepoppt
    assert "task-recent" in state.render_tasks
    assert "task-running" in state.render_tasks
    assert "task-invalid-time" in state.render_tasks  # geschützt vor Löschung
    assert "task-invalid-time" in res["invalid_finished_at"]


def test_render_progress_schema_bidirectional_sync() -> None:
    """RenderProgress synchronisiert percent und progress_percent bidirektional."""
    p1 = RenderProgress(task_id="t1", percent=45.5)
    assert p1.progress_percent == 45.5
    assert p1.percent == 45.5

    p2 = RenderProgress(task_id="t2", progress_percent=88.2)
    assert p2.percent == 88.2
    assert p2.progress_percent == 88.2

    # Beide angegeben -> progress_percent gewinnt
    p3 = RenderProgress(task_id="t3", percent=10.0, progress_percent=20.0)
    assert p3.progress_percent == 20.0
    assert p3.percent == 20.0

