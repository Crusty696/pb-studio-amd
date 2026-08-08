"""T328 render-contract regressions; execution is gated until T332."""

from __future__ import annotations

import importlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from backend.schemas.render_schemas import RenderProgress, RenderRequest
from pb_studio.rendering.render_service import RenderService


render_router = importlib.import_module("backend.routers.render_router")


FULL_LENGTH_SECONDS = 6335.027
FULL_LENGTH_FPS = 30.0
FULL_LENGTH_FRAMES = 190_051
SOURCE_END_SILENCE_SECONDS = 58.222062


def _probe_result(
    codec_name: str,
    *,
    duration: float = FULL_LENGTH_SECONDS,
    include_audio: bool = True,
) -> subprocess.CompletedProcess[str]:
    streams: list[dict[str, Any]] = [{
        "index": 0,
        "codec_type": "video",
        "codec_name": codec_name,
        "duration": f"{duration:.6f}",
        "width": 1920,
        "height": 1080,
    }]
    if include_audio:
        streams.append({
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "duration": f"{duration:.6f}",
            "sample_rate": "48000",
            "channels": 2,
        })
    payload = {
        "format": {"duration": f"{duration:.6f}"},
        "streams": streams,
    }
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )


@pytest.mark.parametrize("encoder", ["h264_amf", "hevc_amf", "av1_amf"])
def test_normalization_profiles_are_all_intra(encoder: str) -> None:
    args = RenderService._encoder_args(encoder)

    assert args[args.index("-g") + 1] == "1"

    normalization = inspect.getsource(RenderService._normalize_clips)
    precondition = normalization.index(
        "needs_norm = not self._is_frame_addressable"
    )
    transcode = normalization.index("self._transcode_clip")
    postcondition = normalization.index(
        "if not self._is_frame_addressable",
        transcode,
    )
    assert precondition < transcode < postcondition


@pytest.mark.parametrize(
    ("packet_flags", "returncode", "expected"),
    [
        ("K__\nK__\n", 0, True),
        ("K__\n___\n", 0, False),
        ("", 0, False),
        ("K__\n", 1, False),
    ],
)
def test_frame_addressability_requires_every_packet_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    packet_flags: str,
    returncode: int,
    expected: bool,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
    )
    commands: list[list[str]] = []

    def capture(
        command: list[str],
        **_kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout=packet_flags,
            stderr="probe failed" if returncode else "",
        )

    monkeypatch.setattr(service, "_run_capture_process", capture)

    assert service._is_frame_addressable(tmp_path / "clip.mp4") is expected
    assert "-show_packets" in commands[0]
    assert "packet=flags" in commands[0]


@pytest.mark.parametrize(
    ("encoder", "codec_name"),
    [("h264_amf", "h264"), ("hevc_amf", "hevc")],
)
def test_full_length_codec_validation_rejects_shortened_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoder: str,
    codec_name: str,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override=encoder,
    )
    requested_decodes: list[tuple[str, float]] = []

    monkeypatch.setattr(
        service,
        "_run_capture_process",
        lambda _command, **_kwargs: _probe_result(codec_name),
    )

    def shortened_decode(
        _artifact_path: Path,
        *,
        stream_selector: str,
        expected_duration: float,
        cancel_callback=None,
    ) -> dict[str, str]:
        del cancel_callback
        requested_decodes.append((stream_selector, expected_duration))
        return {
            "frame": str(FULL_LENGTH_FRAMES),
            "out_time_us": str(int((FULL_LENGTH_SECONDS - 1.0) * 1_000_000)),
            "progress": "end",
        }

    monkeypatch.setattr(service, "_decode_artifact_stream", shortened_decode)

    with pytest.raises(RuntimeError, match="Video-End-PTS"):
        service._validate_render_artifact(
            tmp_path / f"full-{codec_name}.mp4",
            expected_duration=FULL_LENGTH_SECONDS,
            target_fps=FULL_LENGTH_FPS,
            target_width=1920,
            target_height=1080,
            include_audio=True,
            expected_end_silence=SOURCE_END_SILENCE_SECONDS,
        )

    assert requested_decodes == [("0:v:0", FULL_LENGTH_SECONDS)]


def test_complete_decode_requires_progress_end_without_time_truncation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
    )
    captured: dict[str, Any] = {}

    def incomplete_capture(
        command: list[str],
        *,
        timeout: float,
        cancel_callback=None,
    ) -> subprocess.CompletedProcess[str]:
        del cancel_callback
        captured["command"] = command
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=(
                f"frame={FULL_LENGTH_FRAMES}\n"
                f"out_time_us={int(FULL_LENGTH_SECONDS * 1_000_000)}\n"
                "progress=continue\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(service, "_run_capture_process", incomplete_capture)

    with pytest.raises(RuntimeError, match="ohne progress=end"):
        service._decode_artifact_stream(
            tmp_path / "incomplete.mp4",
            stream_selector="0:v:0",
            expected_duration=FULL_LENGTH_SECONDS,
        )

    assert "-xerror" in captured["command"]
    assert "-t" not in captured["command"]
    assert captured["timeout"] >= FULL_LENGTH_SECONDS


@pytest.mark.parametrize(
    ("true_peak_dbtp", "end_silence", "failure"),
    [
        (-0.50, SOURCE_END_SILENCE_SECONDS, "True-Peak"),
        (-1.10, 0.0, "Endstille"),
    ],
)
def test_full_length_audio_validation_fails_closed_on_audio_contract_violation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    true_peak_dbtp: float,
    end_silence: float,
    failure: str,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
    )
    monkeypatch.setattr(
        service,
        "_run_capture_process",
        lambda _command, **_kwargs: _probe_result("h264"),
    )

    def complete_protocol_record(
        _artifact_path: Path,
        *,
        stream_selector: str,
        expected_duration: float,
        cancel_callback=None,
    ) -> dict[str, str]:
        del stream_selector, cancel_callback
        assert expected_duration == FULL_LENGTH_SECONDS
        return {
            "frame": str(FULL_LENGTH_FRAMES),
            "out_time_us": str(int(FULL_LENGTH_SECONDS * 1_000_000)),
            "progress": "end",
        }

    monkeypatch.setattr(
        service,
        "_decode_artifact_stream",
        complete_protocol_record,
    )
    monkeypatch.setattr(
        service,
        "_measure_true_peak_dbtp",
        lambda *_args, **_kwargs: true_peak_dbtp,
    )
    monkeypatch.setattr(
        service,
        "_measure_trailing_silence_seconds",
        lambda *_args, **_kwargs: end_silence,
    )

    with pytest.raises(RuntimeError, match=failure):
        service._validate_render_artifact(
            tmp_path / "audio-contract.mp4",
            expected_duration=FULL_LENGTH_SECONDS,
            target_fps=FULL_LENGTH_FPS,
            target_width=1920,
            target_height=1080,
            include_audio=True,
            expected_end_silence=SOURCE_END_SILENCE_SECONDS,
        )


def test_artifact_end_silence_threshold_compensates_pre_encode_gain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
    )
    monkeypatch.setattr(
        service,
        "_run_capture_process",
        lambda _command, **_kwargs: _probe_result("h264"),
    )
    monkeypatch.setattr(
        service,
        "_decode_artifact_stream",
        lambda *_args, **_kwargs: {
            "frame": str(FULL_LENGTH_FRAMES),
            "out_time_us": str(int(FULL_LENGTH_SECONDS * 1_000_000)),
            "progress": "end",
        },
    )
    monkeypatch.setattr(
        service,
        "_measure_true_peak_dbtp",
        lambda *_args, **_kwargs: -1.10,
    )
    measured_thresholds: list[float | None] = []

    def record_end_silence_threshold(
        *_args,
        noise_threshold_db=None,
        **_kwargs,
    ) -> float:
        measured_thresholds.append(noise_threshold_db)
        return SOURCE_END_SILENCE_SECONDS

    monkeypatch.setattr(
        service,
        "_measure_trailing_silence_seconds",
        record_end_silence_threshold,
    )

    service._validate_render_artifact(
        tmp_path / "gain-compensated-silence.mp4",
        expected_duration=FULL_LENGTH_SECONDS,
        target_fps=FULL_LENGTH_FPS,
        target_width=1920,
        target_height=1080,
        include_audio=True,
        expected_end_silence=SOURCE_END_SILENCE_SECONDS,
    )

    assert measured_thresholds == [-62.0]


@pytest.mark.parametrize("encoder", ["h264_amf", "hevc_amf"])
def test_full_length_render_command_preserves_audio_duration_and_headroom(
    tmp_path: Path,
    encoder: str,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override=encoder,
    )

    command, effective_duration = service._build_render_cmd(
        tmp_path / "concat.txt",
        str(tmp_path / "source.wav"),
        tmp_path / "staging.mp4",
        "15M",
        "quality",
        0.0,
        FULL_LENGTH_SECONDS,
        encoder,
        audio_dur=FULL_LENGTH_SECONDS,
        include_audio=True,
    )

    audio_filter = command[command.index("-filter:a") + 1]
    assert audio_filter == "volume=-2.0dB"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-t") + 1] == "6335.027"
    assert effective_duration == FULL_LENGTH_SECONDS
    assert RenderService._AAC_TRUE_PEAK_LIMIT_DBTP == -1.0
    assert "atrim" not in audio_filter


def test_validator_failure_preserves_existing_target_and_removes_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
        job_id="publication-fault",
    )
    final_output = tmp_path / "existing.mp4"
    final_output.write_bytes(b"previous-validated-output")

    monkeypatch.setattr(service, "_normalize_clips", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        service,
        "_generate_concat_file",
        lambda *_args, **_kwargs: None,
    )

    def write_invalid_staging(
        _list_path: Path,
        _audio_path: str | None,
        staging_path: Path,
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        staging_path.write_bytes(b"invalid-staging")
        return {"progress_end": True}

    monkeypatch.setattr(service, "_run_ffmpeg_render", write_invalid_staging)
    monkeypatch.setattr(
        service,
        "_validate_render_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("full decode failed")
        ),
    )

    with pytest.raises(RuntimeError, match="full decode failed"):
        service.render_timeline(
            [],
            "",
            final_output.name,
            include_audio=False,
        )

    assert final_output.read_bytes() == b"previous-validated-output"
    assert list(tmp_path.glob(".*.partial.mp4")) == []

    publication = inspect.getsource(RenderService.render_timeline)
    assert publication.index("_validate_render_artifact") < publication.index(
        "os.replace(staging_output, final_output)"
    )


def test_job_and_resume_run_evidence_is_isolated_and_non_overwriting(
    tmp_path: Path,
) -> None:
    records: list[tuple[Path, dict[str, Any]]] = []

    for job_id, run_id in (
        ("queue/job-A", "run-a"),
        ("queue/job-A", "run-b"),
        ("queue-job-B", "run-a"),
    ):
        service = RenderService(output_dir=str(tmp_path), job_id=job_id)
        service.run_id = run_id
        path = service._persist_render_evidence(
            status="failed",
            exit_code=1,
            progress_end=False,
            machine_progress={
                "frame": "42",
                "fps": "12.5",
                "out_time_us": "1500000",
                "total_size": "4096",
                "speed": "0.5x",
            },
            progress_log="frame=42\nprogress=continue\n",
            stderr_log="Invalid data found at 0x1234\n",
            total_duration=FULL_LENGTH_SECONDS,
            total_frames=FULL_LENGTH_FRAMES,
        )
        records.append((path, json.loads(path.read_text(encoding="utf-8"))))

    paths = [path for path, _record in records]
    assert len(set(paths)) == 3
    assert paths[0].parent != paths[1].parent
    assert paths[0].parent != paths[2].parent
    assert records[0][1]["job_id"] == "queue_job-A"
    assert records[0][1]["run_id"] == "run-a"
    assert records[1][1]["run_id"] == "run-b"

    for _path, record in records:
        assert record["status"] == "failed"
        assert record["exit_code"] == 1
        assert record["progress_end"] is False
        assert record["end_pts_seconds"] == 1.5
        assert record["expected_duration_seconds"] == FULL_LENGTH_SECONDS
        assert len(record["failure_fingerprint"]) == 64
        assert len(record["progress_log_sha256"]) == 64
        assert len(record["stderr_log_sha256"]) == 64
        assert "command" not in record
        assert "environment" not in record

    duplicate = RenderService(output_dir=str(tmp_path), job_id="queue/job-A")
    duplicate.run_id = "run-a"
    with pytest.raises(FileExistsError):
        duplicate._persist_render_evidence(
            status="failed",
            exit_code=1,
            progress_end=False,
            machine_progress={},
            progress_log="",
            stderr_log="",
            total_duration=FULL_LENGTH_SECONDS,
            total_frames=FULL_LENGTH_FRAMES,
        )


def test_public_progress_contract_exposes_terminal_machine_evidence() -> None:
    progress = RenderProgress(
        task_id="task-1",
        status="completed",
        percent=100.0,
        progress_end=True,
        run_id="run-1",
        queue_job_id="queue-1",
        evidence_path=r"C:\project\.render_evidence\queue-1\run-1\result.json",
        validation_path=(
            r"C:\project\.render_evidence\queue-1\run-1\validation.json"
        ),
        validation_status="validated",
    ).model_dump()

    assert progress["status"] == "completed"
    assert progress["progress_end"] is True
    assert progress["run_id"] == "run-1"
    assert progress["evidence_path"].endswith("result.json")
    assert progress["validation_path"].endswith("validation.json")
    assert progress["validation_status"] == "validated"

    router_source = inspect.getsource(render_router._run_render_task)
    for field in (
        '"run_id"',
        '"evidence_path"',
        '"validation_path"',
        '"progress_end"',
        '"validation_status"',
    ):
        assert field in router_source


def test_resume_payload_and_owned_process_shutdown_contract(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "source.wav"
    audio_path.touch()
    request = RenderRequest(
        output_path=str(tmp_path / "output.mp4"),
        audio_path=str(audio_path),
    )
    timeline = [{
        "start_time": 0.0,
        "end_time": FULL_LENGTH_SECONDS,
        "metadata": {"file_path": str(tmp_path / "clip.mp4")},
    }]

    settings = render_router._request_settings_dict(
        request,
        timeline_snapshot=timeline,
        project_root=tmp_path,
        project_db_id=1,
    )
    resume = settings["_resume"]
    assert resume["version"] == render_router._RENDER_RESUME_PAYLOAD_VERSION
    assert resume["request"]["output_path"] == str(tmp_path / "output.mp4")
    assert resume["timeline_snapshot"] == timeline
    assert Path(resume["project_root"]) == tmp_path.resolve()
    assert resume["project_db_id"] == 1

    render_source = inspect.getsource(RenderService.render_timeline)
    assert "self.run_id = uuid.uuid4().hex" in render_source
    assert "self.temp_root / self.job_token / self.run_id" in render_source

    capture_source = inspect.getsource(RenderService._run_capture_process)
    assert "self._register_process(process)" in capture_source
    assert "cancel_callback and cancel_callback()" in capture_source
    assert "process.kill()" in capture_source
    assert "self._unregister_process(process)" in capture_source

    shutdown_source = inspect.getsource(render_router._shutdown_active_renders)
    assert "state.set_cancel_flag(task_id, True)" in shutdown_source
    assert "RenderService.terminate_active_processes" in shutdown_source
    assert "await asyncio.gather(*pending, return_exceptions=True)" in shutdown_source

    resume_source = inspect.getsource(render_router._resume_render_queue_on_startup)
    assert "restore_running_as_interrupted()" in resume_source
    assert "_track_render_runtime_task(task_id, task)" in resume_source
    assert "output_path.is_relative_to(project_root)" in resume_source
