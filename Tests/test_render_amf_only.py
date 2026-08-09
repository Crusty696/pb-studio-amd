"""Regression coverage for the AMF-only render contract."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from pb_studio.ai.tool_registry import _render_encoder_values
from pb_studio.rendering import render_service
from pb_studio.rendering.render_service import RenderService
from pb_studio.video import engine
from scripts import ensure_verification_media


AMF_ENCODERS = {"h264_amf", "hevc_amf", "av1_amf"}


@pytest.mark.parametrize("encoder", ["libx264", "libx265", "libsvtav1", "h264_mf"])
def test_render_service_rejects_non_amf_override(tmp_path: Path, encoder: str):
    with pytest.raises(ValueError, match="AMF"):
        RenderService(output_dir=str(tmp_path), encoder_override=encoder)


@pytest.mark.parametrize("encoder", sorted(AMF_ENCODERS))
def test_render_service_encoder_args_are_amf_only(encoder: str):
    args = RenderService._encoder_args(encoder)
    assert args[:2] == ["-c:v", encoder]


def test_render_service_encoder_args_reject_unknown():
    with pytest.raises(ValueError, match="AMF"):
        RenderService._encoder_args("libx264")


def test_chat_tool_encoder_schema_is_amf_only():
    assert set(_render_encoder_values()) == AMF_ENCODERS


def test_render_service_initialization_does_not_probe_encoder(tmp_path: Path, monkeypatch):
    def fail_if_called(_self):
        raise AssertionError("encoder probe must be lazy")

    monkeypatch.setattr(RenderService, "_detect_best_encoder", fail_if_called)
    RenderService(output_dir=str(tmp_path))


def test_encoder_probe_uses_amf_supported_frame_size(tmp_path: Path, monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "pb_studio.rendering.render_service.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(
        render_service,
        "get_amf_device_args",
        lambda: ["-init_hw_device", "d3d11va=pb_amf:7"],
    )
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")

    assert service._detect_best_encoder() == "hevc_amf"
    assert any("color=c=black:s=320x240:d=0.5" in command for command in commands)
    assert all(command.index("-init_hw_device") < command.index("-i") for command in commands)
    assert all("d3d11va=pb_amf:1" not in command for command in commands)


def test_clip_transcode_places_dynamic_amf_device_before_input(
    tmp_path: Path,
    monkeypatch,
):
    commands: list[list[str]] = []
    output_path = tmp_path / "normalized.mp4"

    class FakePipe:
        def readlines(self):
            return []

        def close(self):
            return None

    class FakeProcess:
        returncode = 0
        stdout = None
        stderr = FakePipe()

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            return None, ""

        def kill(self):
            self.returncode = -1

        def wait(self, timeout=None):
            return self.returncode

    def fake_popen(command, **_kwargs):
        commands.append(command)
        output_path.write_bytes(b"normalized")
        return FakeProcess()

    monkeypatch.setattr(render_service, "get_amf_device_args", lambda: [
        "-init_hw_device",
        "d3d11va=pb_amf:7",
    ])
    monkeypatch.setattr(render_service.subprocess, "Popen", fake_popen)
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")

    service._transcode_clip("source.mp4", output_path, 1920, 1080, 30.0)

    command = commands[0]
    assert command.index("-init_hw_device") < command.index("-i")
    assert "d3d11va=pb_amf:7" in command
    assert "d3d11va=pb_amf:1" not in command


def test_video_generator_amf_commands_use_dynamic_device_before_inputs(
    tmp_path: Path,
    monkeypatch,
):
    commands: list[list[str]] = []
    segment_path = tmp_path / "segment.mp4"
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"source")
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")

    def fake_run(command, **_kwargs):
        commands.append(command)
        if command[-1] == str(segment_path):
            segment_path.write_bytes(b"segment")
        return SimpleNamespace(returncode=0, stderr=b"")

    encoder = SimpleNamespace(
        encoder="h264_amf",
        params=["-quality", "speed"],
        description="AMD AMF",
    )
    monkeypatch.setattr(engine, "get_preview_encoder", lambda: encoder)
    monkeypatch.setattr(engine, "get_export_encoder", lambda **_kwargs: encoder)
    monkeypatch.setattr(engine, "get_amf_device_args", lambda: [
        "-init_hw_device",
        "d3d11va=pb_amf:7",
    ])
    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    generator = engine.VideoGenerator.__new__(engine.VideoGenerator)

    generator._ffmpeg_extract(source_path, 0.0, 1.0, segment_path)
    generator._concat_segments([segment_path], audio_path, tmp_path / "final.mp4")

    assert len(commands) == 2
    assert all(command.index("-init_hw_device") < command.index("-i") for command in commands)
    assert all("d3d11va=pb_amf:7" in command for command in commands)
    assert all("d3d11va=pb_amf:1" not in command for command in commands)


def test_verification_media_amf_command_uses_dynamic_device_before_input(
    tmp_path: Path,
    monkeypatch,
):
    commands: list[list[str]] = []
    monkeypatch.setattr(
        ensure_verification_media,
        "get_amf_device_args",
        lambda: ["-init_hw_device", "d3d11va=pb_amf:7"],
    )
    monkeypatch.setattr(
        ensure_verification_media,
        "run_ffmpeg",
        lambda command: commands.append(command),
    )

    ensure_verification_media.generate_color_bars_video(tmp_path / "bars.mp4")

    command = commands[0]
    assert command.index("-init_hw_device") < command.index("-i")
    assert "d3d11va=pb_amf:7" in command
    assert "d3d11va=pb_amf:1" not in command
