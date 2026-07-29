from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.app_state import AppState
from backend.schemas.render_schemas import RenderEncoder, RenderRequest
from pb_studio.config_manager import ConfigManager
from pb_studio.data.database_core import DatabaseCore
from pb_studio.rendering.render_queue import (
    STATE_FAILED,
    STATE_INTERRUPTED,
    STATE_RUNNING,
    get_render_queue,
    reset_for_tests,
)
from pb_studio.rendering.render_service import (
    RenderCancelledError,
    RenderService,
)


ROOT = Path(r"C:\Users\david\Documents\Pb_studio_AMD_version")
PROJECT_DIR = Path(
    r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245"
)
LIVE_DB = ROOT / "data" / "pb_studio.db"
render_router = importlib.import_module("backend.routers.render_router")
EVIDENCE_DIR = Path(
    os.environ.get(
        "PBSTUDIO_T336_CONTROL_EVIDENCE_DIR",
        str(Path(__file__).resolve().parent / "control-gates"),
    )
)
DB_COPY = EVIDENCE_DIR / "pb_studio.control-gates.db"
FROZEN_JOB_ID = "0f81362b-084f-414a-bc41-d8fae85a749e"
EXISTING_TARGET = PROJECT_DIR / "output" / "release_qc_longmix_h264_t335.mp4"
RESUME_OUTPUT = PROJECT_DIR / "output" / "t336_resume_cancel_probe.mp4"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_frozen_settings() -> dict[str, Any]:
    uri = f"file:{LIVE_DB.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        row = connection.execute(
            "SELECT settings_json FROM render_queue WHERE job_id = ?",
            (FROZEN_JOB_ID,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError(f"Frozen job missing: {FROZEN_JOB_ID}")
    return json.loads(str(row[0]))


def _bind_database_copy() -> None:
    if DatabaseCore._instance is not None:
        DatabaseCore._instance.shutdown()
    DatabaseCore._instance = None
    reset_for_tests()
    config = ConfigManager()
    config._config = ConfigManager._deep_merge(
        config._config,
        {"paths": {"db_path": str(DB_COPY)}},
    )
    database = DatabaseCore()
    if database.db_path.resolve() != DB_COPY.resolve():
        raise RuntimeError(f"Database copy binding failed: {database.db_path}")


async def _resume_and_cancel(
    settings: dict[str, Any],
) -> dict[str, Any]:
    queue = get_render_queue()
    job = queue.enqueue(
        media_hash="t336-real-resume-cancel",
        output_path=str(RESUME_OUTPUT),
        settings=settings,
    )
    queue.update_status(job.job_id, STATE_RUNNING)
    restored = queue.restore_running_as_interrupted()
    if job.job_id not in restored:
        raise RuntimeError("Running job was not restored as interrupted")
    if queue.get(job.job_id).status != STATE_INTERRUPTED:
        raise RuntimeError("Restart state is not interrupted")

    state = AppState()
    await render_router.gpu_lock.acquire()
    try:
        resumed = await render_router._resume_render_queue_on_startup(
            state,
            queue=queue,
        )
        if resumed != [job.job_id]:
            raise RuntimeError(f"Unexpected resumed jobs: {resumed}")
        task_ids = [
            task_id
            for task_id, task in state.render_tasks.items()
            if task.get("queue_job_id") == job.job_id
        ]
        if len(task_ids) != 1:
            raise RuntimeError(f"Resume runtime task mismatch: {task_ids}")
        task_id = task_ids[0]
        cancel_result = await render_router.cancel_render(task_id, state)
        if cancel_result.get("cancelled") is not True:
            raise RuntimeError(f"Cancel was not accepted: {cancel_result}")
    finally:
        if render_router.gpu_lock.locked():
            render_router.gpu_lock.release()

    deadline = time.monotonic() + 10.0
    task_snapshot = state.get_render_task(task_id)
    while (
        task_snapshot
        and task_snapshot.get("status") != "cancelled"
        and time.monotonic() < deadline
    ):
        await asyncio.sleep(0.05)
        task_snapshot = state.get_render_task(task_id)
    if not task_snapshot or task_snapshot.get("status") != "cancelled":
        raise RuntimeError(f"Runtime cancel did not finish: {task_snapshot}")

    queue_snapshot = queue.get(job.job_id)
    if queue_snapshot is None or queue_snapshot.status != STATE_FAILED:
        raise RuntimeError(f"Queue cancel status mismatch: {queue_snapshot}")
    if RESUME_OUTPUT.exists():
        raise RuntimeError(f"Cancelled resume published output: {RESUME_OUTPUT}")

    return {
        "job_id": job.job_id,
        "restored_from_running": True,
        "restart_status": STATE_INTERRUPTED,
        "resumed_job_ids": resumed,
        "runtime_task_id": task_id,
        "cancel_response": cancel_result,
        "runtime_status": task_snapshot.get("status"),
        "runtime_progress_end": task_snapshot.get("progress_end"),
        "runtime_validation_status": task_snapshot.get("validation_status"),
        "queue_status": queue_snapshot.status,
        "queue_error": queue_snapshot.get("error"),
        "output_exists": RESUME_OUTPUT.exists(),
    }


async def _av1_preflight(
    frozen_settings: dict[str, Any],
) -> dict[str, Any]:
    timeline = frozen_settings["_resume"]["timeline_snapshot"]
    functional = await asyncio.to_thread(
        RenderService.probe_encoder,
        "av1_amf",
    )
    if functional:
        raise RuntimeError("AV1 unexpectedly functional; plan expects unavailable")
    request_data = dict(frozen_settings["_resume"]["request"])
    request_data["encoder"] = RenderEncoder.AV1_AMF.value
    request_data["output_path"] = str(
        PROJECT_DIR / "output" / "t336_av1_must_not_start.mp4"
    )
    request = RenderRequest.model_validate(request_data)
    try:
        await render_router._preflight_render_request(
            request,
            timeline,
        )
    except HTTPException as exc:
        if exc.status_code != 503 or "AV1 AMF" not in str(exc.detail):
            raise
        return {
            "probe_functional": functional,
            "status_code": exc.status_code,
            "detail": str(exc.detail),
            "output_exists": Path(request.output_path).exists(),
        }
    raise RuntimeError("AV1 preflight did not fail before task creation")


def _existing_target_cancel(
    frozen_settings: dict[str, Any],
) -> dict[str, Any]:
    if not EXISTING_TARGET.is_file():
        raise FileNotFoundError(EXISTING_TARGET)
    target_hash_before = _sha256(EXISTING_TARGET)
    first = frozen_settings["_resume"]["timeline_snapshot"][0]
    metadata = first["metadata"]
    source_path = Path(metadata["file_path"])
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    service = RenderService(
        output_dir=str(EXISTING_TARGET.parent),
        encoder_override="h264_amf",
        job_id="t336-existing-target-cancel",
    )
    try:
        service.render_timeline(
            timeline=[{
                "file_path": str(source_path),
                "in_point": float(metadata.get("clip_start", 0.0)),
                "out_point": float(metadata.get("clip_start", 0.0)) + 1.0,
            }],
            audio_path="",
            output_filename=EXISTING_TARGET.name,
            target_width=640,
            target_height=360,
            target_fps=30.0,
            cancel_callback=lambda: True,
            include_audio=False,
        )
    except RenderCancelledError:
        pass
    else:
        raise RuntimeError("Existing-target render was not cancelled")

    target_hash_after = _sha256(EXISTING_TARGET)
    if target_hash_after != target_hash_before:
        raise RuntimeError("Existing validated target changed during cancel")
    partials = [
        str(path)
        for path in EXISTING_TARGET.parent.glob(
            ".release_qc_longmix_h264_t335.t336-existing-target-cancel.*.partial.mp4"
        )
    ]
    if partials:
        raise RuntimeError(f"Cancelled staging files remain: {partials}")
    return {
        "target": str(EXISTING_TARGET),
        "sha256_before": target_hash_before,
        "sha256_after": target_hash_after,
        "preserved": True,
        "partial_files": partials,
    }


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=False)
    if RESUME_OUTPUT.exists():
        raise FileExistsError(RESUME_OUTPUT)
    frozen_settings = _load_frozen_settings()
    live_db_hash_before = _sha256(LIVE_DB)
    shutil.copy2(LIVE_DB, DB_COPY)
    if _sha256(DB_COPY) != live_db_hash_before:
        raise RuntimeError("Database copy hash mismatch")
    _bind_database_copy()

    resume_settings = json.loads(json.dumps(frozen_settings))
    resume_settings["encoder"] = "h264_amf"
    resume_settings["_resume"]["request"]["encoder"] = "h264_amf"
    resume_settings["_resume"]["request"]["output_path"] = str(RESUME_OUTPUT)

    resume_cancel = asyncio.run(_resume_and_cancel(resume_settings))
    av1 = asyncio.run(_av1_preflight(frozen_settings))
    existing_target = _existing_target_cancel(frozen_settings)
    live_db_hash_after = _sha256(LIVE_DB)
    if live_db_hash_after != live_db_hash_before:
        raise RuntimeError("Live database changed during copy-based gates")

    _write_json(
        EVIDENCE_DIR / "control-gates.json",
        {
            "status": "pass",
            "live_database": {
                "path": str(LIVE_DB),
                "sha256_before": live_db_hash_before,
                "sha256_after": live_db_hash_after,
                "unchanged": True,
            },
            "database_copy": {
                "path": str(DB_COPY),
                "sha256_initial": live_db_hash_before,
            },
            "restart_resume_cancel": resume_cancel,
            "av1_unavailable": av1,
            "existing_target": existing_target,
        },
    )


if __name__ == "__main__":
    main()
