from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app_state import AppState
from backend.schemas.render_schemas import RenderEncoder, RenderQuality, RenderRequest
from pb_studio.rendering.preview_renderer import PreviewGenerator, TimelineEntry
from pb_studio.rendering.render_service import RenderService

render_router = importlib.import_module("backend.routers.render_router")


def _request(
    tmp_path: Path,
    *,
    quality: RenderQuality = RenderQuality.HIGH,
    encoder: RenderEncoder | None = None,
    include_audio: bool = True,
) -> RenderRequest:
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"audio")
    return RenderRequest(
        output_path=str(tmp_path / "output.mp4"),
        audio_path=str(audio),
        quality=quality,
        encoder=encoder,
        include_audio=include_audio,
    )


def test_include_audio_false_builds_video_only_command(tmp_path: Path) -> None:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    cmd, _ = service._build_render_cmd(
        tmp_path / "concat.txt",
        str(tmp_path / "mix.wav"),
        tmp_path / "out.mp4",
        "12M",
        "quality",
        0.0,
        5.0,
        "h264_amf",
        include_audio=False,
    )

    assert "-an" in cmd
    assert "1:a" not in cmd
    assert str(tmp_path / "mix.wav") not in cmd
    assert "-c:a" not in cmd


def test_quality_and_include_audio_reach_render_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    captured: dict[str, object] = {}

    monkeypatch.setattr(RenderService, "_get_audio_duration", lambda self, path: 1.0)

    def fake_render(self, **kwargs):
        captured.update(kwargs)
        return str(tmp_path / "output.mp4")

    monkeypatch.setattr(RenderService, "render_timeline", fake_render)
    state = AppState()
    loop = asyncio.new_event_loop()
    try:
        render_router._execute_render(
            "task-1",
            _request(
                tmp_path,
                quality=RenderQuality.PREVIEW,
                include_audio=False,
            ),
            state,
            [{
                "start_time": 0.0,
                "end_time": 1.0,
                "metadata": {"file_path": str(clip)},
            }],
            loop,
        )
    finally:
        loop.close()

    assert captured["preset"] == "speed"
    assert captured["include_audio"] is False


def test_missing_clip_fails_before_probe_or_media_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")

    def unexpected(*args, **kwargs):
        raise AssertionError("media work must not start before clip preflight")

    monkeypatch.setattr(service, "_get_audio_duration", unexpected)
    monkeypatch.setattr(service, "_active_encoder", unexpected)

    with pytest.raises(FileNotFoundError, match="Timeline-Clip"):
        service.render_timeline(
            [{"file_path": str(tmp_path / "missing.mp4")}],
            str(tmp_path / "mix.wav"),
            "out.mp4",
        )


def test_preview_renderer_uses_reported_640x360_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"preview")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(
        "pb_studio.rendering.preview_renderer.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(
        "pb_studio.rendering.preview_renderer._preview_encoder_args",
        lambda: ["-c:v", "h264_amf"],
    )
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    generator = PreviewGenerator(output_dir=tmp_path)

    result = generator.generate_preview(
        [TimelineEntry(str(source), 0.0, 1.0, 0.0, 1.0)],
        duration=1.0,
    )

    assert result == tmp_path / "preview.mp4"
    filters = [
        command[command.index("-vf") + 1]
        for command in commands
        if "-vf" in command
    ]
    assert filters
    assert all("scale=640:360" in value for value in filters)


def test_cancel_before_gpu_lock_acquire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class State:
        @staticmethod
        def get_cancel_flag(_task_id):
            return True

    lock = asyncio.Lock()
    monkeypatch.setattr(render_router, "gpu_lock", lock)

    async def run() -> None:
        with pytest.raises(render_router._RenderCancelled):
            await render_router._acquire_gpu_lock_or_cancel(
                "task-1", State(), poll_seconds=0.01
            )
        assert not lock.locked()

    asyncio.run(run())


def test_cancel_during_gpu_lock_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class State:
        cancelled = False

        def get_cancel_flag(self, _task_id):
            return self.cancelled

    state = State()

    async def run() -> None:
        lock = asyncio.Lock()
        await lock.acquire()
        monkeypatch.setattr(render_router, "gpu_lock", lock)
        waiter = asyncio.create_task(
            render_router._acquire_gpu_lock_or_cancel(
                "task-1", state, poll_seconds=0.01
            )
        )
        await asyncio.sleep(0.03)
        state.cancelled = True
        with pytest.raises(render_router._RenderCancelled):
            await asyncio.wait_for(waiter, timeout=0.2)
        assert lock.locked()
        lock.release()

    asyncio.run(run())


def test_encoder_override_probe_is_functional_and_av1_fails_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    probed: list[str] = []

    def unavailable(encoder: str) -> bool:
        probed.append(encoder)
        return False

    monkeypatch.setattr(RenderService, "probe_encoder", unavailable)

    async def run() -> None:
        with pytest.raises(HTTPException) as exc:
            await render_router._preflight_render_request(
                _request(tmp_path, encoder=RenderEncoder.AV1_AMF),
                [{"metadata": {"file_path": str(clip)}}],
            )
        assert exc.value.status_code == 503
        assert "AV1 AMF" in exc.value.detail

    asyncio.run(run())
    assert probed == ["av1_amf"]


def test_render_queue_dedupe_returns_existing_runtime_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    request = _request(tmp_path)
    state = AppState()
    state.set_timeline([{
        "start_time": 0.0,
        "end_time": 1.0,
        "metadata": {"file_path": str(clip)},
    }])
    state.set_render_task("existing", {
        "task_id": "existing",
        "status": "pending",
        "percent": 0.0,
        "current_frame": 0,
        "total_frames": 30,
        "fps": 0.0,
        "elapsed_seconds": 0.0,
        "eta_seconds": 0.0,
        "output_path": request.output_path,
        "error": None,
        "queue_job_id": "queue-existing",
    })

    class Queue:
        @staticmethod
        def enqueue(*args, **kwargs):
            assert kwargs["job_id"] != "queue-existing"
            return SimpleNamespace(job_id="queue-existing", status="queued")

    monkeypatch.setattr(render_router, "_get_render_queue", lambda: Queue())
    monkeypatch.setattr(
        render_router,
        "resolve_active_project_root",
        lambda state, fallback: tmp_path,
    )

    result = asyncio.run(render_router.start_render(request, state))

    assert result.task_id == "existing"
    assert len(state.render_tasks) == 1
