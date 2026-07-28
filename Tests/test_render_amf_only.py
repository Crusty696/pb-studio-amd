"""Regression coverage for the AMF-only render contract."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from pb_studio.ai.tool_registry import _render_encoder_values
from pb_studio.rendering.render_service import RenderService


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
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")

    assert service._detect_best_encoder() == "hevc_amf"
    assert any("color=c=black:s=320x240:d=0.5" in command for command in commands)
