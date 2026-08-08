from pathlib import Path
import subprocess

import pytest

from pb_studio.rendering.render_service import RenderCancelledError, RenderService


def _service_without_media_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RenderService:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    monkeypatch.setattr(
        service,
        "_get_audio_duration",
        lambda _path, _cancel_callback=None: 1.0,
    )
    monkeypatch.setattr(
        service,
        "_measure_trailing_silence_seconds",
        lambda *args, **kwargs: 0.0,
    )
    monkeypatch.setattr(
        service,
        "_validate_render_artifact",
        lambda *args, **kwargs: {"duration_seconds": 1.0},
    )
    monkeypatch.setattr(service, "_normalize_clips", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "_generate_concat_file", lambda *args, **kwargs: None)
    return service


@pytest.mark.parametrize("error", [RuntimeError("ffmpeg failed"), RenderCancelledError("cancelled")])
def test_failed_or_cancelled_render_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    service = _service_without_media_work(tmp_path, monkeypatch)
    final_output = tmp_path / "existing.mp4"
    final_output.write_bytes(b"previous-success")

    def fail_render(_list_path, _audio_path, staging_path, *args, **kwargs):
        staging_path.write_bytes(b"incomplete")
        raise error

    monkeypatch.setattr(service, "_run_ffmpeg_render", fail_render)

    with pytest.raises(type(error)):
        service.render_timeline([], "audio.wav", final_output.name)

    assert final_output.read_bytes() == b"previous-success"
    assert list(tmp_path.glob(".*.partial.mp4")) == []


def test_successful_render_atomically_replaces_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service_without_media_work(tmp_path, monkeypatch)
    final_output = tmp_path / "existing.mp4"
    final_output.write_bytes(b"previous-success")
    staging_paths: list[Path] = []

    def complete_render(_list_path, _audio_path, staging_path, *args, **kwargs):
        staging_paths.append(staging_path)
        staging_path.write_bytes(b"complete-render")
        return {"fps": 30.0}

    monkeypatch.setattr(service, "_run_ffmpeg_render", complete_render)

    result = service.render_timeline([], "audio.wav", final_output.name)

    assert result == str(final_output)
    assert final_output.read_bytes() == b"complete-render"
    assert len(staging_paths) == 1
    assert staging_paths[0] != final_output
    assert staging_paths[0].parent == final_output.parent
    assert staging_paths[0].suffix == final_output.suffix
    assert not staging_paths[0].exists()


def test_each_render_uses_a_unique_staging_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service_without_media_work(tmp_path, monkeypatch)
    staging_paths: list[Path] = []

    def complete_render(_list_path, _audio_path, staging_path, *args, **kwargs):
        staging_paths.append(staging_path)
        staging_path.write_bytes(b"complete-render")
        return {"fps": 30.0}

    monkeypatch.setattr(service, "_run_ffmpeg_render", complete_render)

    service.render_timeline([], "audio.wav", "same.mp4")
    service.render_timeline([], "audio.wav", "same.mp4")

    assert staging_paths[0] != staging_paths[1]


def test_shutdown_terminates_kills_and_waits_active_ffmpeg() -> None:
    class StubbornProcess:
        terminated = False
        killed = False
        waited = False

        def poll(self):
            return 0 if self.killed else None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.waited = True
            if not self.killed:
                raise subprocess.TimeoutExpired("ffmpeg", timeout)
            return 0

    process = StubbornProcess()
    RenderService._register_process(process)
    try:
        count = RenderService.terminate_active_processes(grace_seconds=0.0)
    finally:
        RenderService._unregister_process(process)

    assert count == 1
    assert process.terminated
    assert process.killed
    assert process.waited
