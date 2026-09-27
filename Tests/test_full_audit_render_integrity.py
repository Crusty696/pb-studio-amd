from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app_state import AppState, ProjectOperationContext
from backend.schemas.render_schemas import RenderRequest
from pb_studio.rendering import render_service
from pb_studio.rendering.render_service import RenderService

render_router = importlib.import_module("backend.routers.render_router")


def test_incident_frame_deficit_reproduces_through_router_and_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "discardable-source.mp4"
    source.write_bytes(b"test source")
    duration = 3299.456508
    decoded_end = 3299.456508
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        render_service,
        "RenderService",
        lambda **kwargs: _service_with_incident_identity(kwargs),
    )
    monkeypatch.setattr(
        RenderService,
        "_get_audio_duration",
        lambda self, path, *_args, **_kwargs: duration,
    )
    monkeypatch.setattr(
        RenderService,
        "_measure_trailing_silence_seconds",
        lambda *args, **kwargs: 0.0,
    )
    monkeypatch.setattr(RenderService, "_normalize_clips", lambda self, *args: [
        {"file_path": str(source), "in_point": 0.0, "out_point": duration}
    ])

    def fake_run_ffmpeg(self, *args, **kwargs):
        captured["run_ffmpeg_kwargs"] = kwargs
        service_args = args
        cmd, _ = self._build_render_cmd(
            Path("concat.txt"), str(tmp_path / "mix.wav"),
            Path(args[2]), "12M", "quality", 0.0,
            duration, "h264_amf", include_audio=True,
            target_rate=kwargs.get("target_rate"),
        )
        expected_frames = int(cmd[cmd.index("-frames:v") + 1]) if "-frames:v" in cmd else 98982
        captured["final_command"] = cmd
        captured["rendered_frames"] = expected_frames
        rendered_frames = expected_frames
        staging = Path(args[2])
        staging.write_bytes(b"completed FFmpeg artifact")
        evidence_dir = (
            self.output_dir / ".render_evidence" / self.job_token / self.run_id
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "result.json").write_text(
            json.dumps({
                "status": "completed",
                "frame": rendered_frames,
                "expected_frames": 98984,
                "exit_code": 0,
                "progress_end": True,
            }),
            encoding="utf-8",
        )
        return {
            "fps": 250.67,
            "current_frame": rendered_frames,
            "total_frames": 98984,
            "progress_end": True,
            "out_time_us": 3299439456,
        }

    monkeypatch.setattr(RenderService, "_run_ffmpeg_render", fake_run_ffmpeg)

    def fake_capture(self, cmd, *, timeout, cancel_callback=None):
        captured.setdefault("probe_commands", []).append(cmd)
        if "-show_entries" in cmd:
            stdout = json.dumps({
                "streams": [{
                    "codec_type": "video", "codec_name": "h264",
                    "width": 1920, "height": 1080,
                }, {
                    "codec_type": "audio", "codec_name": "aac",
                    "sample_rate": "44100", "channels": 2,
                }],
                "format": {"duration": str(decoded_end)},
            })
        else:
            frame_count = int(captured.get("rendered_frames", 98982))
            stdout = (
                f"frame={frame_count}\nout_time_us=3299456508\nprogress=end\n"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(RenderService, "_run_capture_process", fake_capture)
    monkeypatch.setattr(RenderService, "_measure_true_peak_dbtp", lambda *a, **k: -2.0)
    monkeypatch.setattr(
        render_router,
        "_finalize_timeline_for_render",
        lambda timeline, _duration: timeline,
    )

    state = AppState()
    state.set_render_task("incident", {"task_id": "incident", "queue_job_id": "q-incident"})
    state.set_cancel_flag("incident", False)
    (tmp_path / "mix.wav").write_bytes(b"test audio")
    request = RenderRequest(
        output_path=str(tmp_path / "incident-output.mp4"),
        audio_path=str(tmp_path / "mix.wav"),
        fps=30.0,
    )
    loop = asyncio.new_event_loop()

    async def run_task() -> None:
        monkeypatch.setattr(render_router, "_queue_update_or_raise", lambda *a, **k: None)
        monkeypatch.setattr(render_router, "_safe_queue_update", lambda *a, **k: None)
        monkeypatch.setattr(render_router, "publish_event", _noop_async)
        monkeypatch.setattr(render_router, "publish_log", _noop_async)
        await render_router._run_render_task(
            "incident", request, state,
            [{
                "clip_id": "clip_test",
                "start_time": 0.0,
                "end_time": duration,
                "metadata": {"file_path": str(source), "clip_start": 0.0},
            }],
            "q-incident",
        )

    try:
        loop.run_until_complete(run_task())
    finally:
        loop.close()

    task = state.get_render_task("incident")
    assert task["status"] == "completed"
    assert task["validation_status"] == "validated"
    assert Path(task["evidence_path"]).is_file()
    assert Path(task["validation_path"]).is_file()
    validation = json.loads(Path(task["validation_path"]).read_text(encoding="utf-8"))
    assert validation["status"] == "passed"
    assert validation["metrics"]["decoded_frames"] == 98984


def test_render_command_and_validator_share_rational_frame_rate(
    tmp_path: Path,
) -> None:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    cmd, _ = service._build_render_cmd(
        tmp_path / "concat.txt", str(tmp_path / "mix.wav"),
        tmp_path / "out.mp4", "12M", "quality", 0.0,
        3299.456508, "h264_amf", include_audio=True,
        target_rate=__import__("fractions").Fraction(30, 1),
    )
    assert cmd[cmd.index("-r") + 1] == "30/1"
    assert "settb=AVTB,setpts=N*1/30/TB" in cmd[cmd.index("-vf") + 1]
    assert cmd[cmd.index("-frames:v") + 1] == "98984"
    assert cmd[cmd.index("-t") + 1] == "3299.457"


@pytest.mark.parametrize("same_as", ["video", "audio"])
def test_start_render_rejects_input_output_identity_before_enqueue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    same_as: str,
) -> None:
    media = tmp_path / "source.mp4"
    audio = tmp_path / "mix.wav"
    media.write_bytes(b"video")
    audio.write_bytes(b"audio")
    output = media if same_as == "video" else audio
    request = RenderRequest(
        output_path=str(output), audio_path=str(audio),
    )
    state = AppState()
    state.current_project = {"name": "test", "path": str(tmp_path), "db_project_id": 1}
    state.set_audio_clip(1, {"id": 1, "path": str(audio)})
    state.set_video_clip(1, {"id": 1, "path": str(media)})
    state.set_timeline([{
        "clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0,
        "metadata": {"file_path": str(media), "clip_start": 0.0},
    }])
    enqueues: list[object] = []
    monkeypatch.setattr(render_router, "_get_render_queue", lambda: SimpleNamespace(
        cleanup_terminal=lambda **kwargs: None,
        enqueue=lambda *args, **kwargs: _queued_job(enqueues, kwargs),
        update_status=lambda *args, **kwargs: SimpleNamespace(job_id=args[0]),
    ))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(render_router._start_render_for_project(
            request, state,
            ProjectOperationContext(1, tmp_path.resolve(), state._project_epoch),
        ))
    assert exc.value.status_code == 400
    assert "same file" in exc.value.detail.lower() or "dieselbe datei" in exc.value.detail.lower()
    assert not enqueues


def _service_with_incident_identity(kwargs: dict[str, object]) -> RenderService:
    options = dict(kwargs)
    options["encoder_override"] = "h264_amf"
    options.setdefault("job_id", "incident-98982")
    return RenderService(**options)


def _queued_job(enqueues: list[object], kwargs: dict[str, object]) -> SimpleNamespace:
    enqueues.append(kwargs)
    return SimpleNamespace(job_id=kwargs["job_id"], status="queued")


async def _noop_async(*args, **kwargs) -> None:
    return None
