from __future__ import annotations

import asyncio
import importlib
import threading
from pathlib import Path

import pytest


PROJECT_UUID = "75efc170-823d-4874-962e-5e472becaf8f"
OTHER_UUID = "0e736c32-948c-4323-b9ba-0f9d50fa193f"


def _state(tmp_path: Path):
    from backend.app_state import AppState

    return AppState(current_project={
        "db_project_id": 23,
        "project_uuid": PROJECT_UUID,
        "path": str(tmp_path),
    })


def test_nested_operation_preserves_exact_immutable_identity(tmp_path: Path):
    from backend.app_state import AppState

    state = _state(tmp_path)

    async def run() -> None:
        async with state.project_operation() as outer:
            async with state.project_operation() as inner:
                assert inner == outer
                assert inner.project_uuid == state.current_project["project_uuid"]

    asyncio.run(run())


def test_operation_rejects_uuid_swap_without_epoch_change(tmp_path: Path):
    from backend.app_state import AppState, ProjectContextChangedError

    state = _state(tmp_path)

    async def run() -> None:
        async with state.project_operation() as context:
            state.current_project["project_uuid"] = OTHER_UUID
            with pytest.raises(ProjectContextChangedError):
                state.require_project_context_current(context)

    asyncio.run(run())


def test_stale_context_blocks_delete_db_and_ram_mutations(
    monkeypatch,
    tmp_path: Path,
):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)
    state.audio_clips[7] = {"id": 7, "path": str(tmp_path / "track.wav")}
    state.audio_analysis_cache[7] = {"bpm": 128.0}
    context = state.capture_project_context()
    state.current_project["project_uuid"] = OTHER_UUID
    writes: list[int] = []

    class FakeRepo:
        def find_by_project_and_path(self, project_id, file_path):
            assert project_id == 23
            return {"id": 70}

        def delete_media(self, media_id):
            writes.append(media_id)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )

    with pytest.raises(ProjectContextChangedError):
        state.delete_audio_clip(7, context=context)

    assert writes == []
    assert 7 in state.audio_clips
    assert 7 in state.audio_analysis_cache


def test_stale_context_blocks_analysis_update_db_and_ram_mutations(
    monkeypatch,
    tmp_path: Path,
):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)
    state.audio_clips[7] = {"id": 7, "path": str(tmp_path / "track.wav")}
    context = state.capture_project_context()
    state.current_project["project_uuid"] = OTHER_UUID
    writes: list[dict] = []

    class FakeRepo:
        def find_by_project_and_path(self, project_id, file_path):
            assert project_id == 23
            return {"id": 70, "ai_data_json": "{}"}

        def update_status(self, media_id, status, ai_data):
            writes.append(ai_data)

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )

    with pytest.raises(ProjectContextChangedError):
        state.update_audio_analysis(
            clip_id=7,
            bpm=128.0,
            context=context,
        )

    assert writes == []
    assert state.audio_analysis_cache == {}
    assert "bpm" not in state.audio_clips[7]


def test_stale_context_blocks_recovery_and_load_publication(
    monkeypatch,
    tmp_path: Path,
):
    from backend.app_state import ProjectContextChangedError

    state = _state(tmp_path)
    state.audio_clips[9] = {"id": 9, "name": "old"}
    context = state.capture_project_context()
    state.current_project["project_uuid"] = OTHER_UUID
    recoveries: list[int] = []

    class FakeRepo:
        db = None

        def recover_analysis_receipts(self, project_id):
            recoveries.append(project_id)
            return 0

        def get_by_project(self, project_id):
            raise AssertionError("stale load must stop before query")

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository",
        FakeRepo,
    )

    with pytest.raises(ProjectContextChangedError):
        state.load_from_db(project_id=23, context=context)

    assert recoveries == []
    assert state.audio_clips == {9: {"id": 9, "name": "old"}}


def test_resume_task_identity_rejects_uuid_mismatch_without_mutation(tmp_path: Path):
    from backend.app_state import ProjectContextChangedError
    from backend.routers.render_router import _require_render_task_identity

    context = _state(tmp_path).capture_project_context()
    task_data = {
        "project_uuid": OTHER_UUID,
        "project_db_id": context.project_id,
        "project_root": str(context.project_root),
    }

    with pytest.raises(ProjectContextChangedError):
        _require_render_task_identity(task_data, context)


def test_resume_catalog_uuid_mismatch_fails_before_state_load(
    monkeypatch,
    tmp_path: Path,
):
    render_router = importlib.import_module("backend.routers.render_router")

    project_root = tmp_path / "project"
    project_root.mkdir()

    class FakeProjectRepository:
        def get_by_id(self, project_id):
            assert project_id == 23
            return {
                "id": 23,
                "project_uuid": PROJECT_UUID,
                "data": {
                    "path": str(project_root),
                    "project_uuid": PROJECT_UUID,
                },
            }

    monkeypatch.setattr(render_router.config, "project_dir", str(tmp_path))
    monkeypatch.setattr(
        "pb_studio.data.repositories.project_repository.ProjectRepository",
        FakeProjectRepository,
    )

    with pytest.raises(ValueError, match="project_uuid"):
        render_router._load_resume_media_state(
            str(project_root),
            23,
            OTHER_UUID,
        )


@pytest.mark.parametrize("project_id", [1.1, 1.9, "1.0", True, 0, -1])
def test_resume_rejects_noncanonical_project_ids(
    monkeypatch,
    tmp_path: Path,
    project_id,
):
    render_router = importlib.import_module("backend.routers.render_router")
    project_root = tmp_path / "project"
    project_root.mkdir()

    class FakeProjectRepository:
        def get_by_id(self, _project_id):
            raise AssertionError("invalid project ID must fail before catalog lookup")

    monkeypatch.setattr(render_router.config, "project_dir", str(tmp_path))
    monkeypatch.setattr(
        "pb_studio.data.repositories.project_repository.ProjectRepository",
        FakeProjectRepository,
    )
    with pytest.raises(ValueError, match="Projekt-ID"):
        render_router._load_resume_media_state(
            str(project_root),
            project_id,
            PROJECT_UUID,
        )


def test_stubborn_render_after_drain_timeout_cannot_mutate_new_project_or_emit_sse(
    monkeypatch,
    tmp_path: Path,
):
    render_router = importlib.import_module("backend.routers.render_router")
    from backend.schemas.render_schemas import RenderRequest

    state = _state(tmp_path)
    context = state.capture_project_context()
    task_id = "owner-collision"
    state.render_tasks[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "percent": 0.0,
        "project_uuid": context.project_uuid,
        "project_db_id": context.project_id,
        "project_root": str(context.project_root),
    }
    state.cancel_flags[task_id] = False

    worker_started = threading.Event()
    release_worker = threading.Event()
    stale_progress_attempted = threading.Event()
    events: list[dict] = []

    def stubborn_execute(
        worker_task_id,
        _request,
        worker_state,
        _timeline,
        _event_loop,
        worker_context,
    ):
        worker_started.set()
        assert release_worker.wait(timeout=5.0)
        stale_progress_attempted.set()
        render_router._update_render_task_for_owner(
            worker_state,
            worker_task_id,
            worker_context,
            {"percent": 75.0},
        )
        return {"progress_end": True}

    async def capture_event(_event_type, payload):
        events.append(dict(payload))

    async def run() -> None:
        monkeypatch.setattr(render_router, "gpu_lock", asyncio.Lock())
        monkeypatch.setattr(render_router, "_execute_render", stubborn_execute)
        monkeypatch.setattr(render_router, "publish_event", capture_event)
        monkeypatch.setattr(render_router, "_queue_update_or_raise", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(render_router, "_safe_queue_update", lambda *_args, **_kwargs: None)
        render_task = asyncio.create_task(
            render_router._run_render_task_bound(
                task_id,
                RenderRequest(output_path=str(tmp_path / "out.mp4"), include_audio=False),
                state,
                [],
                context,
                None,
            )
        )
        assert await asyncio.to_thread(worker_started.wait, 2.0)

        done_count, pending_count = await state.cancel_and_drain_project_tasks(
            timeout_seconds=0.0
        )
        assert done_count == 0
        assert pending_count == 1

        other_root = tmp_path / "other"
        other_root.mkdir()
        state.invalidate_project_context()
        state.current_project = {
            "db_project_id": 24,
            "project_uuid": OTHER_UUID,
            "path": str(other_root),
        }
        new_task = {
            "task_id": task_id,
            "status": "queued",
            "percent": 0.0,
            "project_uuid": OTHER_UUID,
            "project_db_id": 24,
            "project_root": str(other_root.resolve()),
        }
        state.render_tasks[task_id] = dict(new_task)
        state.cancel_flags[task_id] = False
        release_worker.set()
        await asyncio.gather(render_task, return_exceptions=True)

        assert stale_progress_attempted.is_set()
        assert state.render_tasks[task_id] == new_task
        assert state.cancel_flags[task_id] is False
        assert events == []

    try:
        asyncio.run(run())
    finally:
        release_worker.set()
