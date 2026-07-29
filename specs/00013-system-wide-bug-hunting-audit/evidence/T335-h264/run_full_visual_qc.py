from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\Users\david\Documents\Pb_studio_AMD_version")
TARGET = Path(
    os.environ.get(
        "PBSTUDIO_FULL_QC_TARGET",
        (
            r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245"
            r"\output\release_qc_longmix_h264_t335.mp4"
        ),
    )
)
EVIDENCE_DIR = Path(
    os.environ.get(
        "PBSTUDIO_FULL_QC_EVIDENCE_DIR",
        str(Path(__file__).resolve().parent / "full-visual-qc"),
    )
)
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
EXPECTED_SHA256 = os.environ.get(
    "PBSTUDIO_FULL_QC_EXPECTED_SHA256",
    "4bf4c2c83dd6db9a047d1e1541b237cbbfe955f7303b445dfb6fe9b3d33cc366",
)
FULL_LENGTH_SECONDS = 6335.027
EXPECTED_FRAMES = 190051
SEGMENT_SECONDS = 60.0


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


def _parse_framemd5(path: Path) -> list[dict[str, Any]]:
    time_base = None
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = re.match(r"#tb 0:\s*(\d+)/(\d+)", line)
        if match:
            time_base = int(match.group(1)) / int(match.group(2))
            continue
        if not line or line.startswith("#"):
            continue
        fields = [part.strip() for part in line.split(",")]
        if len(fields) != 6 or time_base is None:
            raise RuntimeError(f"Invalid framemd5 record: {line}")
        records.append(
            {
                "pts": int(fields[2]),
                "seconds": int(fields[2]) * time_base,
                "duration": int(fields[3]),
                "size": int(fields[4]),
                "md5": fields[5],
            }
        )
    if time_base is None or not records:
        raise RuntimeError(f"No framemd5 records in {path}")
    return records


def _run_framemd5(
    output_path: Path,
    *,
    start: float,
    duration: float,
    fps: float,
) -> list[dict[str, Any]]:
    command = [
        str(FFMPEG),
        "-y",
        "-v",
        "error",
        "-ss",
        f"{start:.6f}",
        "-i",
        str(TARGET),
        "-t",
        f"{duration:.6f}",
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        f"fps={fps:g}",
        "-f",
        "framemd5",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"framemd5 failed for {output_path.name}: {result.stderr[-2000:]}"
        )
    return _parse_framemd5(output_path)


def _parse_black_intervals(log_text: str) -> list[dict[str, float]]:
    return [
        {
            "start": float(start),
            "end": float(end),
            "duration": float(duration),
        }
        for start, end, duration in re.findall(
            r"black_start:([0-9.]+)\s+black_end:([0-9.]+)"
            r"\s+black_duration:([0-9.]+)",
            log_text,
        )
    ]


def _parse_freeze_intervals(log_text: str) -> list[dict[str, float]]:
    starts = [
        float(value)
        for value in re.findall(
            r"lavfi\.freezedetect\.freeze_start:\s*([0-9.]+)",
            log_text,
        )
    ]
    ends = [
        (float(end), float(duration))
        for duration, end in re.findall(
            r"lavfi\.freezedetect\.freeze_duration:\s*([0-9.]+).*?"
            r"lavfi\.freezedetect\.freeze_end:\s*([0-9.]+)",
            log_text,
            flags=re.DOTALL,
        )
    ]
    intervals = []
    for index, start in enumerate(starts):
        if index < len(ends):
            end, duration = ends[index]
        else:
            end = FULL_LENGTH_SECONDS
            duration = max(end - start, 0.0)
        intervals.append(
            {"start": start, "end": end, "duration": duration}
        )
    return intervals


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=False)
    (EVIDENCE_DIR / "runner.pid.txt").write_text(
        f"{os.getpid()}\n",
        encoding="ascii",
    )
    if not TARGET.is_file():
        raise FileNotFoundError(TARGET)
    target_sha256 = _sha256(TARGET)
    if target_sha256 != EXPECTED_SHA256:
        raise RuntimeError(f"Target hash drift: {target_sha256}")

    sample_path = EVIDENCE_DIR / "timeline-20s.framemd5"
    stderr_path = EVIDENCE_DIR / "full-scan.stderr.log"
    progress_path = EVIDENCE_DIR / "full-scan.progress.jsonl"
    command = [
        str(FFMPEG),
        "-y",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(TARGET),
        "-filter_complex",
        (
            "[0:v:0]split=2[scan][sample];"
            "[scan]blackdetect=d=0.5:pix_th=0.10,"
            "freezedetect=n=-50dB:d=2[scanout];"
            "[sample]fps=1/20[sampleout]"
        ),
        "-progress",
        "pipe:1",
        "-map",
        "[scanout]",
        "-an",
        "-f",
        "null",
        os.devnull,
        "-map",
        "[sampleout]",
        "-an",
        "-f",
        "framemd5",
        str(sample_path),
    ]
    _write_json(
        EVIDENCE_DIR / "started.json",
        {
            "started_at": datetime.now().astimezone().isoformat(),
            "pid": os.getpid(),
            "target": str(TARGET),
            "target_size": TARGET.stat().st_size,
            "target_sha256": target_sha256,
            "expected_duration": FULL_LENGTH_SECONDS,
            "expected_frames": EXPECTED_FRAMES,
            "command": command,
        },
    )

    progress_blocks: list[dict[str, str]] = []
    current_block: dict[str, str] = {}
    with (
        stderr_path.open("w", encoding="utf-8") as stderr_handle,
        progress_path.open("w", encoding="utf-8", buffering=1) as progress_handle,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_handle,
            text=True,
            errors="replace",
        )
        if process.stdout is None:
            raise RuntimeError("FFmpeg progress pipe missing")
        for raw_line in process.stdout:
            key, separator, value = raw_line.strip().partition("=")
            if not separator:
                continue
            current_block[key] = value
            if key == "progress":
                record = {
                    "recorded_at": datetime.now().astimezone().isoformat(),
                    **current_block,
                }
                progress_blocks.append(dict(current_block))
                progress_handle.write(json.dumps(record, sort_keys=True) + "\n")
                current_block.clear()
        returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(f"Full visual scan failed with exit code {returncode}")
    if not progress_blocks or progress_blocks[-1].get("progress") != "end":
        raise RuntimeError("Full visual scan ended without progress=end")

    final_progress = progress_blocks[-1]
    decoded_frames = int(final_progress.get("frame", "0") or 0)
    out_time_seconds = int(
        final_progress.get("out_time_us", "0") or 0
    ) / 1_000_000.0
    if abs(decoded_frames - EXPECTED_FRAMES) > 1:
        raise RuntimeError(
            f"Full visual scan frame mismatch: {decoded_frames}"
        )
    if abs(out_time_seconds - FULL_LENGTH_SECONDS) > 0.05:
        raise RuntimeError(
            f"Full visual scan duration mismatch: {out_time_seconds}"
        )

    timeline_samples = _parse_framemd5(sample_path)
    expected_segments = math.ceil(FULL_LENGTH_SECONDS / SEGMENT_SECONDS)
    segment_receipts: list[dict[str, Any]] = []
    for segment_index in range(expected_segments):
        segment_start = segment_index * SEGMENT_SECONDS
        segment_end = min(
            segment_start + SEGMENT_SECONDS,
            FULL_LENGTH_SECONDS,
        )
        samples = [
            item
            for item in timeline_samples
            if segment_start <= item["seconds"] < segment_end
        ]
        if not samples:
            raise RuntimeError(
                f"No decoded sample for segment {segment_index}"
            )
        segment_receipts.append(
            {
                "segment_index": segment_index,
                "start": segment_start,
                "end": segment_end,
                "sample_count": len(samples),
                "unique_hashes": len({item["md5"] for item in samples}),
                "first_hash": samples[0]["md5"],
                "last_hash": samples[-1]["md5"],
            }
        )

    transition_samples = _run_framemd5(
        EVIDENCE_DIR / "window-1962.framemd5",
        start=1961.0,
        duration=2.5,
        fps=10.0,
    )
    transition_unique = len({item["md5"] for item in transition_samples})
    if len(transition_samples) < 20 or transition_unique < 3:
        raise RuntimeError(
            "The 1962.1-second transition window lacks valid new frames"
        )

    terminal_start = 6275.0
    terminal_samples = _run_framemd5(
        EVIDENCE_DIR / "terminal-window.framemd5",
        start=terminal_start,
        duration=FULL_LENGTH_SECONDS - terminal_start,
        fps=1.0,
    )
    terminal_unique = len({item["md5"] for item in terminal_samples})
    if len(terminal_samples) < 59 or terminal_unique < 3:
        raise RuntimeError("Terminal window lacks valid changing frames")

    scan_log = stderr_path.read_text(encoding="utf-8", errors="replace")
    black_intervals = _parse_black_intervals(scan_log)
    freeze_intervals = _parse_freeze_intervals(scan_log)
    terminal_black = [
        item for item in black_intervals if item["end"] > terminal_start
    ]
    terminal_freeze = [
        item for item in freeze_intervals if item["end"] > terminal_start
    ]
    if terminal_black:
        raise RuntimeError(f"Terminal black interval: {terminal_black}")
    if terminal_freeze:
        raise RuntimeError(f"Terminal freeze interval: {terminal_freeze}")

    _write_json(
        EVIDENCE_DIR / "qc-result.json",
        {
            "status": "pass",
            "completed_at": datetime.now().astimezone().isoformat(),
            "target": str(TARGET),
            "target_size": TARGET.stat().st_size,
            "target_sha256": target_sha256,
            "full_decode": {
                "exit_code": returncode,
                "progress_end": True,
                "decoded_frames": decoded_frames,
                "expected_frames": EXPECTED_FRAMES,
                "out_time_seconds": out_time_seconds,
                "expected_duration": FULL_LENGTH_SECONDS,
            },
            "timeline_segments": {
                "segment_seconds": SEGMENT_SECONDS,
                "expected_segments": expected_segments,
                "covered_segments": len(segment_receipts),
                "receipts": segment_receipts,
            },
            "window_1962": {
                "start": 1961.0,
                "duration": 2.5,
                "sample_count": len(transition_samples),
                "unique_hashes": transition_unique,
            },
            "terminal_window": {
                "start": terminal_start,
                "end": FULL_LENGTH_SECONDS,
                "sample_count": len(terminal_samples),
                "unique_hashes": terminal_unique,
                "black_intervals": terminal_black,
                "freeze_intervals": terminal_freeze,
            },
            "full_scan_events": {
                "black_intervals": black_intervals,
                "freeze_intervals": freeze_intervals,
            },
        },
    )


if __name__ == "__main__":
    main()
