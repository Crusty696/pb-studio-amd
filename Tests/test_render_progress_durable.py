"""Durable render-progress evidence contract."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pb_studio.rendering.render_service import RenderService


def test_ffmpeg_progress_is_persisted_before_child_process_exits(tmp_path: Path):
    release_child = tmp_path / "release-child"
    script = "\n".join(
        [
            "import pathlib, time",
            "print('frame=30', flush=True)",
            "print('fps=30.0', flush=True)",
            "print('out_time_us=1000000', flush=True)",
            "print('total_size=1024', flush=True)",
            "print('speed=1.0x', flush=True)",
            "print('progress=continue', flush=True)",
            f"release = pathlib.Path({str(release_child)!r})",
            "while not release.exists(): time.sleep(0.01)",
            "print('frame=60', flush=True)",
            "print('fps=30.0', flush=True)",
            "print('out_time_us=2000000', flush=True)",
            "print('total_size=2048', flush=True)",
            "print('speed=1.0x', flush=True)",
            "print('progress=end', flush=True)",
        ]
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    renderer = RenderService(
        output_dir=str(tmp_path / "exports"),
        encoder_override="h264_amf",
        job_id="durable-progress-test",
    )
    renderer.run_id = "run-1"
    progress_path = (
        renderer.output_dir
        / ".render_evidence"
        / renderer.job_token
        / renderer.run_id
        / "ffmpeg.progress.log"
    )
    persisted_while_running: list[bool] = []

    def observe_progress(_message: str, _percent: float, _telemetry: dict) -> None:
        text = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
        if "progress=continue" in text and "progress=end" not in text:
            persisted_while_running.append(process.poll() is None)
            release_child.touch()

    try:
        result = renderer._parse_ffmpeg_progress(
            process,
            total_duration=2.0,
            target_fps=30.0,
            progress_callback=observe_progress,
            render_start_time=time.monotonic(),
        )
    finally:
        release_child.touch(exist_ok=True)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)

    evidence_result = Path(result["evidence_path"])
    progress_log = evidence_result.with_name("ffmpeg.progress.log")
    record = json.loads(evidence_result.read_text(encoding="utf-8"))
    assert persisted_while_running == [True]
    assert "progress=continue" in progress_log.read_text(encoding="utf-8")
    assert "progress=end" in progress_log.read_text(encoding="utf-8")
    assert record["progress_end"] is True
    assert record["frame"] == 60


def test_last_persisted_progress_survives_ffmpeg_failure(tmp_path: Path):
    script = "\n".join(
        [
            "import time",
            "print('frame=30', flush=True)",
            "print('fps=30.0', flush=True)",
            "print('out_time_us=1000000', flush=True)",
            "print('total_size=1024', flush=True)",
            "print('speed=1.0x', flush=True)",
            "print('progress=continue', flush=True)",
            "time.sleep(30)",
        ]
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    renderer = RenderService(
        output_dir=str(tmp_path / "exports"),
        encoder_override="h264_amf",
        job_id="durable-progress-failure-test",
    )
    renderer.run_id = "run-failed"
    evidence_dir = (
        renderer.output_dir
        / ".render_evidence"
        / renderer.job_token
        / renderer.run_id
    )
    persisted_at_interrupt: list[bool] = []

    def interrupt_after_persist(
        _message: str, _percent: float, _telemetry: dict
    ) -> None:
        path = evidence_dir / "ffmpeg.progress.log"
        persisted_at_interrupt.append(
            path.exists() and "progress=continue" in path.read_text(encoding="utf-8")
        )
        process.terminate()

    try:
        with pytest.raises(RuntimeError, match="FFmpeg Error"):
            renderer._parse_ffmpeg_progress(
                process,
                total_duration=2.0,
                target_fps=30.0,
                progress_callback=interrupt_after_persist,
                render_start_time=time.monotonic(),
            )
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)

    progress_log = evidence_dir / "ffmpeg.progress.log"
    record_path = evidence_dir / "result.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert persisted_at_interrupt == [True]
    assert "progress=continue" in progress_log.read_text(encoding="utf-8")
    assert record["status"] == "failed"
    assert record["progress_end"] is False


def test_final_render_evidence_is_never_overwritten_within_a_run(tmp_path: Path):
    renderer = RenderService(
        output_dir=str(tmp_path / "exports"),
        encoder_override="h264_amf",
        job_id="evidence-no-overwrite",
    )
    renderer.run_id = "run-immutable"
    first_path = renderer._persist_render_evidence(
        status="completed",
        exit_code=0,
        progress_end=True,
        machine_progress={"frame": "60", "out_time_us": "2000000"},
        progress_log="frame=60\nprogress=end\n",
        stderr_log="first-final-record\n",
        total_duration=2.0,
        total_frames=60,
    )
    progress_path = first_path.with_name("ffmpeg.progress.log")
    stderr_path = first_path.with_name("ffmpeg.stderr.log")
    original = {
        path: path.read_bytes()
        for path in (first_path, progress_path, stderr_path)
    }

    with pytest.raises(FileExistsError):
        renderer._persist_render_evidence(
            status="failed",
            exit_code=1,
            progress_end=False,
            machine_progress={"frame": "1", "out_time_us": "1"},
            progress_log="frame=1\nprogress=continue\n",
            stderr_log="replacement-must-not-win\n",
            total_duration=2.0,
            total_frames=60,
        )

    assert {path: path.read_bytes() for path in original} == original
