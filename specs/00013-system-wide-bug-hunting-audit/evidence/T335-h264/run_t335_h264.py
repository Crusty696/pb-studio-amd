from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from pb_studio.pacing.pacing_models import CutListEntry
from pb_studio.rendering.render_service import RenderService
from pb_studio.services.pacing_service import PacingService


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_DIR = Path(
    os.environ.get(
        "PBSTUDIO_T335_EVIDENCE_DIR",
        str(Path(__file__).resolve().parent),
    )
)
PROJECT_DIR = Path(
    r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245"
)
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_NAME = os.environ.get(
    "PBSTUDIO_FULL_EXPORT_OUTPUT_NAME",
    "release_qc_longmix_h264_t335.mp4",
)
OUTPUT_PATH = OUTPUT_DIR / OUTPUT_NAME
DB_PATH = ROOT / "data" / "pb_studio.db"
JOB_ID = "0f81362b-084f-414a-bc41-d8fae85a749e"
RENDER_JOB_ID = os.environ.get(
    "PBSTUDIO_T335_RENDER_JOB_ID",
    "t335-h264-full-length",
)
ENCODER = os.environ.get("PBSTUDIO_FULL_EXPORT_ENCODER", "h264_amf")
USE_ROUTER_FINALIZER = os.environ.get(
    "PBSTUDIO_USE_ROUTER_FINALIZER",
    "0",
) == "1"
FULL_LENGTH_SECONDS = 6335.027
EXPECTED_SETTINGS_SHA256 = (
    "cbe3da460b924dd16868939030327f804e7439633e09fdb4cc45b96248e9772f"
)
EXPECTED_TIMELINE_SHA256 = (
    "dd548d82ec6650b4eb915f2904e910eb6d16dd5f2e229cc665ce534f83c994b2"
)


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


def _load_frozen_job() -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        row = connection.execute(
            "SELECT settings_json FROM render_queue WHERE job_id = ?",
            (JOB_ID,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError(f"Frozen render job missing: {JOB_ID}")
    settings_json = str(row[0])
    settings = json.loads(settings_json)
    timeline = settings["_resume"]["timeline_snapshot"]
    return settings_json, settings, timeline


def _canonical_timeline_hash(timeline: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        timeline,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _finalize_timeline(
    frozen_timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if USE_ROUTER_FINALIZER:
        from backend.routers.render_router import (
            _finalize_timeline_for_render,
        )

        finalized_timeline = _finalize_timeline_for_render(
            frozen_timeline,
            FULL_LENGTH_SECONDS,
        )
        finalized = [
            CutListEntry(
                clip_id=str(item["clip_id"]),
                start_time=float(item["start_time"]),
                end_time=float(item["end_time"]),
                metadata=deepcopy(item.get("metadata") or {}),
            )
            for item in finalized_timeline
        ]
    else:
        entries = [
            CutListEntry(
                clip_id=str(item["clip_id"]),
                start_time=float(item["start_time"]),
                end_time=float(item["end_time"]),
                metadata=deepcopy(item.get("metadata") or {}),
            )
            for item in frozen_timeline
        ]
        finalized = PacingService()._finalize_cut_list(
            entries,
            FULL_LENGTH_SECONDS,
        )
    if not finalized:
        raise RuntimeError("Finalized timeline is empty")
    if abs(finalized[0].start_time) > 1e-9:
        raise RuntimeError("Finalized timeline does not start at zero")
    if abs(finalized[-1].end_time - FULL_LENGTH_SECONDS) > 1e-9:
        raise RuntimeError("Finalized timeline does not end at 6335.027")
    for previous, current in zip(finalized, finalized[1:]):
        if abs(previous.end_time - current.start_time) > 1e-6:
            raise RuntimeError(
                "Finalized timeline is not contiguous: "
                f"{previous.end_time} -> {current.start_time}"
            )
    return [
        {
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": entry.metadata,
        }
        for entry in finalized
    ]


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "runner.pid.txt").write_text(
        f"{os.getpid()}\n",
        encoding="ascii",
    )
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Fresh T335 target already exists: {OUTPUT_PATH}")

    settings_json, settings, frozen_timeline = _load_frozen_job()
    settings_hash = hashlib.sha256(settings_json.encode("utf-8")).hexdigest()
    frozen_hash = _canonical_timeline_hash(frozen_timeline)
    if settings_hash != EXPECTED_SETTINGS_SHA256:
        raise RuntimeError(f"Frozen settings hash drift: {settings_hash}")
    if frozen_hash != EXPECTED_TIMELINE_SHA256:
        raise RuntimeError(f"Frozen timeline hash drift: {frozen_hash}")

    request = settings["_resume"]["request"]
    audio_path = Path(request["audio_path"])
    finalized_timeline = _finalize_timeline(frozen_timeline)
    source_paths = sorted(
        {
            Path(item["metadata"]["file_path"])
            for item in finalized_timeline
        },
        key=lambda path: str(path).casefold(),
    )
    for path in [audio_path, *source_paths]:
        if not path.is_file():
            raise FileNotFoundError(path)

    amf_probe = RenderService.probe_encoder(ENCODER)
    if not amf_probe:
        raise RuntimeError(f"{ENCODER} functional probe failed")

    started = {
        "started_at": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "job_id": RENDER_JOB_ID,
        "frozen_queue_job_id": JOB_ID,
        "settings_sha256": settings_hash,
        "frozen_timeline_sha256": frozen_hash,
        "frozen_timeline_count": len(frozen_timeline),
        "frozen_first_start": frozen_timeline[0]["start_time"],
        "finalized_timeline_sha256": _canonical_timeline_hash(
            finalized_timeline
        ),
        "finalized_timeline_count": len(finalized_timeline),
        "finalized_first_start": finalized_timeline[0]["start_time"],
        "finalized_last_end": finalized_timeline[-1]["end_time"],
        "audio_path": str(audio_path),
        "audio_sha256": _sha256(audio_path),
        "audio_duration": FULL_LENGTH_SECONDS,
        "source_files": [
            {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in source_paths
        ],
        "encoder": ENCODER,
        "router_finalizer": USE_ROUTER_FINALIZER,
        "amf_probe": amf_probe,
        "resolution": "640x360",
        "fps": 30.0,
        "bitrate": "4M",
        "output_path": str(OUTPUT_PATH),
    }
    _write_json(EVIDENCE_DIR / "started.json", started)

    progress_path = EVIDENCE_DIR / "progress.jsonl"
    progress_handle = progress_path.open("a", encoding="utf-8", buffering=1)

    def progress(
        message: str,
        percent: float,
        telemetry: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "recorded_at": datetime.now().astimezone().isoformat(),
            "message": message,
            "percent": float(percent),
            **(telemetry or {}),
        }
        progress_handle.write(
            json.dumps(record, sort_keys=True) + "\n"
        )
        print(json.dumps(record, sort_keys=True), flush=True)

    service = RenderService(
        output_dir=str(OUTPUT_DIR),
        encoder_override=ENCODER,
        job_id=RENDER_JOB_ID,
    )
    start = time.monotonic()
    try:
        result = service.render_timeline(
            timeline=finalized_timeline,
            audio_path=str(audio_path),
            output_filename=OUTPUT_NAME,
            target_width=640,
            target_height=360,
            target_fps=30.0,
            bitrate="4M",
            preset="balanced",
            progress_callback=progress,
            include_audio=True,
        )
        elapsed = time.monotonic() - start
        validation_path = (
            OUTPUT_DIR
            / ".render_evidence"
            / service.job_token
            / service.run_id
            / "validation.json"
        )
        render_result_path = validation_path.with_name("result.json")
        completed = {
            "completed_at": datetime.now().astimezone().isoformat(),
            "elapsed_seconds": elapsed,
            "result": result,
            "output_path": str(OUTPUT_PATH),
            "output_size": OUTPUT_PATH.stat().st_size,
            "output_sha256": _sha256(OUTPUT_PATH),
            "run_id": service.run_id,
            "validation_path": str(validation_path),
            "render_result_path": str(render_result_path),
            "validation": json.loads(
                validation_path.read_text(encoding="utf-8")
            ),
            "render_result": json.loads(
                render_result_path.read_text(encoding="utf-8")
            ),
        }
        _write_json(EVIDENCE_DIR / "completed.json", completed)
    except Exception as exc:
        _write_json(
            EVIDENCE_DIR / "failed.json",
            {
                "failed_at": datetime.now().astimezone().isoformat(),
                "elapsed_seconds": time.monotonic() - start,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "run_id": service.run_id,
            },
        )
        raise
    finally:
        progress_handle.close()


if __name__ == "__main__":
    main()
