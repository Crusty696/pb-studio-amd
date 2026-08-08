from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

from pb_studio.pacing.pacing_models import CutListEntry
from pb_studio.services.pacing_service import PacingService
from backend.routers.render_router import _finalize_timeline_for_render


REPO_DIR = Path(__file__).resolve().parents[4]
GLOBAL_DB = REPO_DIR / "data" / "pb_studio.db"
CURRENT_JOB_ID = "851b5ccf-7f73-4866-8bd9-6e3845d512fd"
FROZEN_JOB_ID = "0f81362b-084f-414a-bc41-d8fae85a749e"
FULL_LENGTH_SECONDS = 6335.027


def _load_job(job_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = sqlite3.connect(
        f"file:{GLOBAL_DB}?mode=ro",
        uri=True,
    )
    try:
        row = connection.execute(
            "SELECT settings_json FROM render_queue WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError(f"Render queue job is missing: {job_id}")
    settings = json.loads(row[0])
    resume = settings.get("_resume") or {}
    timeline = resume.get("timeline_snapshot")
    if not isinstance(timeline, list):
        raise RuntimeError(f"Timeline snapshot is missing: {job_id}")
    return settings, timeline


def _finalize_timeline(
    frozen_timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = [
        CutListEntry(
            clip_id=str(item["clip_id"]),
            start_time=float(item["start_time"]),
            end_time=float(item["end_time"]),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in frozen_timeline
    ]
    return [
        {
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": entry.metadata,
        }
        for entry in PacingService()._finalize_cut_list(
            entries,
            FULL_LENGTH_SECONDS,
        )
    ]


def _render_timeline(
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for entry in timeline:
        metadata = entry.get("metadata") or {}
        clip_start = float(metadata.get("clip_start", 0.0) or 0.0)
        duration = (
            float(entry.get("end_time", 0.0))
            - float(entry.get("start_time", 0.0))
        )
        result.append(
            {
                "file_path": (
                    metadata.get("file_path")
                    or entry.get("file_path")
                    or entry.get("path", "")
                ),
                "in_point": clip_start,
                "out_point": clip_start + duration,
            }
        )
    return result


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _metrics(timeline: list[dict[str, Any]]) -> dict[str, Any]:
    rendered = _render_timeline(timeline)
    durations = [
        float(entry["out_point"]) - float(entry["in_point"])
        for entry in rendered
    ]
    rounded_durations = [
        round(float(entry["out_point"]), 3)
        - round(float(entry["in_point"]), 3)
        for entry in rendered
    ]
    frame_windows = [
        math.ceil(round(float(entry["out_point"]), 3) * 30.0 - 1e-9)
        - math.ceil(round(float(entry["in_point"]), 3) * 30.0 - 1e-9)
        for entry in rendered
    ]
    gaps = []
    for index, (previous, current) in enumerate(
        zip(timeline, timeline[1:]),
        start=1,
    ):
        delta = (
            float(current["start_time"])
            - float(previous["end_time"])
        )
        if abs(delta) > 1e-9:
            gaps.append({"index": index, "delta": delta})
    return {
        "timeline_count": len(timeline),
        "timeline_sha256": _canonical_hash(timeline),
        "render_timeline_sha256": _canonical_hash(rendered),
        "first_start": float(timeline[0]["start_time"]),
        "last_end": float(timeline[-1]["end_time"]),
        "sum_timeline_duration": sum(durations),
        "sum_rounded_concat_duration": sum(rounded_durations),
        "rounded_duration_delta": (
            sum(rounded_durations) - sum(durations)
        ),
        "frame_window_sum": sum(frame_windows),
        "expected_frames": round(FULL_LENGTH_SECONDS * 30.0),
        "gap_count": len(gaps),
        "gap_sample": gaps[:20],
        "unique_source_count": len(
            {entry["file_path"].casefold() for entry in rendered}
        ),
    }


def main() -> None:
    current_settings, current_timeline = _load_job(CURRENT_JOB_ID)
    frozen_settings, frozen_timeline = _load_job(FROZEN_JOB_ID)
    finalized_timeline = _finalize_timeline(frozen_timeline)
    report = {
        "current_job_id": CURRENT_JOB_ID,
        "frozen_job_id": FROZEN_JOB_ID,
        "current_request": (
            current_settings.get("_resume", {}).get("request")
        ),
        "frozen_request": (
            frozen_settings.get("_resume", {}).get("request")
        ),
        "current": _metrics(current_timeline),
        "fixed_current": _metrics(
            _finalize_timeline_for_render(
                current_timeline,
                FULL_LENGTH_SECONDS,
            )
        ),
        "t335_finalized": _metrics(finalized_timeline),
        "timelines_equal": current_timeline == finalized_timeline,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
