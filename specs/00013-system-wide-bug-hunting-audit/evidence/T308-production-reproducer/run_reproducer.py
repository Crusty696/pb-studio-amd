"""Run the preserved release render graph without touching the reference output."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import time
import traceback
from pathlib import Path

from pb_studio.rendering.render_service import RenderService


ROOT = Path(r"C:\Users\david\Documents\Pb_studio_AMD_version")
PROJECT_ROOT = Path(r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245")
JOB_ID = "0f81362b-084f-414a-bc41-d8fae85a749e"
RUN_DIR = PROJECT_ROOT / "diagnostics" / "T308-production-reproducer"
ARCHIVED_TEMP_DIR = (
    PROJECT_ROOT / "cache" / "qc-recovery-20260728" / ".temp_render"
)
EXPECTED_TIMELINE_HASH = (
    "dd548d82ec6650b4eb915f2904e910eb6d16dd5f2e229cc665ce534f83c994b2"
)
EXPECTED_SETTINGS_HASH = (
    "cbe3da460b924dd16868939030327f804e7439633e09fdb4cc45b96248e9772f"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    db_path = ROOT / "data" / "pb_studio.db"
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT settings_json FROM render_queue WHERE job_id = ?",
            (JOB_ID,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError(f"Render queue job missing: {JOB_ID}")

    settings_json = row[0]
    settings_hash = hashlib.sha256(settings_json.encode("utf-8")).hexdigest()
    if settings_hash != EXPECTED_SETTINGS_HASH:
        raise RuntimeError(f"Settings hash changed: {settings_hash}")

    resume = json.loads(settings_json)["_resume"]
    request = resume["request"]
    snapshot = resume["timeline_snapshot"]
    timeline_hash = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if timeline_hash != EXPECTED_TIMELINE_HASH or len(snapshot) != 4816:
        raise RuntimeError(
            f"Timeline freeze mismatch: count={len(snapshot)}, hash={timeline_hash}"
        )

    normalized_paths = sorted(ARCHIVED_TEMP_DIR.glob("norm_*.mp4"))
    if len(normalized_paths) != 6:
        raise RuntimeError(f"Expected six archived normalized clips, got {len(normalized_paths)}")

    source_order: list[str] = []
    for entry in snapshot:
        source = entry["metadata"]["file_path"]
        if source not in source_order:
            source_order.append(source)
    if len(source_order) != 6:
        raise RuntimeError(f"Expected six source clips, got {len(source_order)}")
    normalized_by_source = dict(zip(source_order, normalized_paths, strict=True))

    render_timeline = []
    for entry in snapshot:
        metadata = entry["metadata"]
        duration = float(entry["end_time"]) - float(entry["start_time"])
        in_point = float(metadata.get("clip_start", 0.0))
        render_timeline.append(
            {
                "file_path": str(normalized_by_source[metadata["file_path"]]),
                "in_point": in_point,
                "out_point": in_point + duration,
                "clip_name": metadata.get("clip_name", ""),
                "trigger_type": metadata.get("trigger_type", ""),
            }
        )

    manifest_path = RUN_DIR / "concat_list.txt"
    output_path = RUN_DIR / ".t308-production-reproducer-h264.partial.mp4"
    stdout_path = RUN_DIR / "ffmpeg.stdout.log"
    stderr_path = RUN_DIR / "ffmpeg.stderr.log"
    exit_path = RUN_DIR / "ffmpeg.exitcode.txt"
    completed_path = RUN_DIR / "completed.json"
    for runtime_path in (output_path, stdout_path, stderr_path, exit_path, completed_path):
        if runtime_path.exists():
            raise FileExistsError(f"Refusing to overwrite prior evidence: {runtime_path}")

    service = RenderService(output_dir=str(RUN_DIR), encoder_override="h264_amf")
    service._generate_concat_file(render_timeline, manifest_path)
    audio_path = request["audio_path"]
    audio_duration = service._get_audio_duration(audio_path)
    command, effective_duration = service._build_render_cmd(
        manifest_path,
        audio_path,
        output_path,
        bitrate=f"{float(request['bitrate_mbps']):.0f}M",
        preset="balanced",
        audio_offset=0.0,
        total_duration=audio_duration,
        encoder="h264_amf",
        audio_dur=audio_duration,
        include_audio=True,
    )

    context = {
        "job_id": JOB_ID,
        "settings_sha256": settings_hash,
        "timeline_count": len(snapshot),
        "timeline_canonical_sha256": timeline_hash,
        "manifest_sha256": sha256_file(manifest_path),
        "audio_path": audio_path,
        "audio_sha256": sha256_file(Path(audio_path)),
        "audio_duration": audio_duration,
        "effective_duration": effective_duration,
        "normalized_inputs": [
            {
                "source": source,
                "path": str(normalized_by_source[source]),
                "sha256": sha256_file(normalized_by_source[source]),
                "size": normalized_by_source[source].stat().st_size,
            }
            for source in source_order
        ],
        "command": command,
        "output_path": str(output_path),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (RUN_DIR / "started.json").write_text(
        json.dumps(context, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started = time.monotonic()
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            startupinfo=startupinfo,
        )
        (RUN_DIR / "ffmpeg.pid.txt").write_text(
            f"{process.pid}\n",
            encoding="ascii",
        )
        return_code = process.wait()

    exit_path.write_text(f"{return_code}\n", encoding="ascii")
    completed = {
        "return_code": return_code,
        "elapsed_seconds": time.monotonic() - started,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "output_exists": output_path.exists(),
        "output_size": output_path.stat().st_size if output_path.exists() else 0,
        "output_sha256": sha256_file(output_path) if output_path.exists() else None,
        "stderr_size": stderr_path.stat().st_size,
        "stderr_sha256": sha256_file(stderr_path),
    }
    completed_path.write_text(
        json.dumps(completed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return return_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        (RUN_DIR / "runner-error.log").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        raise
