from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


def test_gpu_timeout_includes_time_waiting_for_gpu_lock(monkeypatch) -> None:
    from backend import dependencies

    async def scenario() -> None:
        lock = asyncio.Lock()
        monkeypatch.setattr(dependencies, "gpu_lock", lock)
        await lock.acquire()
        started = time.monotonic()
        task = asyncio.create_task(
            dependencies.with_gpu_task(
                lambda: pytest.fail("worker must not start after deadline"),
                manage_vram=False,
                timeout_seconds=0.04,
            )
        )
        await asyncio.sleep(0.08)
        assert task.done(), "GPU lock wait escaped the worker deadline"
        with pytest.raises(TimeoutError):
            await task
        assert time.monotonic() - started < 0.25
        assert lock.locked()
        lock.release()

    asyncio.run(scenario())


def test_sse_sequence_does_not_rewind_after_backend_restart_simulation() -> None:
    from backend import dependencies

    dependencies.reset_event_journal()
    first_id = dependencies._next_event_sequence()
    dependencies.reset_event_journal()
    # A client's Last-Event-ID may outlive the process-local journal. A zero/gap
    # sequence on the same process identity would suppress new progress in WPF.
    assert dependencies._next_event_sequence() > first_id


def test_preview_response_contract_reports_artifact_duration_and_audio(tmp_path) -> None:
    from backend.schemas.pacing_schemas import PreviewResponse

    response = PreviewResponse(
        preview_path=str((tmp_path / "preview.mp4").resolve()),
        duration=2.4,
        resolution="640x360",
        audio_included=True,
    )
    assert response.audio_included is True
    assert response.duration == pytest.approx(2.4)
    assert Path(response.preview_path).is_absolute()


def test_preview_renderer_includes_master_audio_and_probes_artifact_duration(
    tmp_path, monkeypatch
) -> None:
    import json
    from types import SimpleNamespace

    from pb_studio.rendering import preview_renderer
    from pb_studio.rendering.preview_renderer import PreviewGenerator, TimelineEntry

    calls: list[list[str]] = []
    audio = tmp_path / "music.wav"
    source = tmp_path / "clip.mp4"
    audio.write_bytes(b"audio")
    source.write_bytes(b"video")

    def fake_run(command, **_kwargs):
        calls.append(command)
        if "-show_entries" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"format": {"duration": "1.75"}}),
                stderr="",
            )
        Path(command[-1]).write_bytes(b"media")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preview_renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(preview_renderer, "_preview_encoder_args", lambda: ["-c:v", "h264_amf"])
    monkeypatch.setattr(preview_renderer, "get_amf_device_args", lambda: [])

    generator = PreviewGenerator(output_dir=tmp_path)
    result = generator.generate_preview(
        [TimelineEntry(str(source), 0.0, 5.0, 0.0, 5.0)],
        start_time_sec=4.0,
        duration=2.0,
        audio_path=audio,
    )

    assert result == (tmp_path / "preview.mp4").resolve()
    assert generator.audio_included is True
    assert generator.last_duration_sec == pytest.approx(1.75)
    mux = next(command for command in calls if "-map" in command)
    assert mux[mux.index("-ss") + 1] == "4.000000"
    assert str(audio.resolve()) in mux
    assert mux[mux.index("-map") + 1] == "0:v:0"
    assert mux[mux.index("-map") + 3] == "1:a:0"
