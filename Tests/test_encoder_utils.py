"""Test coverage for video/encoder_utils.py (P3.1 Test-Coverage-Gap-Filler).

Spec: PLAN_OPEN_TASKS_2026-05-15.md P3.1 — encoder_utils.py hat 10 defs ohne Tests.
Hier: Enums + EncoderConfig + Cache-Reset + build_args + get_encoder_info-Dict-Shape.
Mock-FFmpeg fuer check_amf_available, kein echter Subprocess.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pb_studio.video import encoder_utils
from pb_studio.video.encoder_utils import (
    Codec,
    Quality,
    RateControl,
    EncoderConfig,
    build_ffmpeg_encode_args,
    reset_availability_cache,
    get_encoder_info,
    get_preview_encoder,
    get_export_encoder,
)


# ---------- Enums ----------

def test_codec_enum_has_three_codecs():
    assert Codec.H264.value == "h264"
    assert Codec.HEVC.value == "hevc"
    assert Codec.AV1.value == "av1"
    assert len(list(Codec)) == 3


def test_quality_enum_values():
    assert Quality.SPEED.value == "speed"
    assert Quality.BALANCED.value == "balanced"
    assert Quality.QUALITY.value == "quality"


def test_rate_control_enum_values():
    assert RateControl.CQP.value == "cqp"
    assert RateControl.CBR.value == "cbr"
    assert RateControl.VBR_PEAK.value == "vbr_peak"
    assert RateControl.VBR_LATENCY.value == "vbr_latency"


# ---------- EncoderConfig dataclass ----------

def test_encoder_config_construction():
    cfg = EncoderConfig(
        encoder="h264_amf",
        params=["-quality", "speed"],
        is_hardware=True,
        description="Test AMF",
    )
    assert cfg.encoder == "h264_amf"
    assert cfg.params == ["-quality", "speed"]
    assert cfg.is_hardware is True
    assert cfg.description == "Test AMF"


# ---------- build_ffmpeg_encode_args ----------

def test_build_args_prefixes_with_codec_flag():
    cfg = EncoderConfig(
        encoder="h264_amf",
        params=["-quality", "balanced", "-b:v", "10000000"],
        is_hardware=True,
        description="AMF",
    )
    args = build_ffmpeg_encode_args(cfg)
    assert args[0] == "-c:v"
    assert args[1] == "h264_amf"
    assert args[2:] == ["-quality", "balanced", "-b:v", "10000000"]


def test_build_args_with_empty_params():
    cfg = EncoderConfig(encoder="h264_amf", params=[], is_hardware=True, description="AMF")
    args = build_ffmpeg_encode_args(cfg)
    assert args == ["-c:v", "h264_amf"]


# ---------- reset_availability_cache ----------

def test_reset_cache_sets_globals_to_none():
    # Force a value in the cache
    encoder_utils._amf_available = True
    encoder_utils._av1_amf_available = False
    reset_availability_cache()
    assert encoder_utils._amf_available is None
    assert encoder_utils._av1_amf_available is None


# ---------- get_encoder_info ----------

def test_get_encoder_info_returns_dict_with_required_keys(monkeypatch):
    """get_encoder_info should always return the same dict-shape regardless of FFmpeg state."""
    # Mock FFmpeg/AMF availability to avoid subprocess
    monkeypatch.setattr(encoder_utils, "check_ffmpeg_available", lambda: True)
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: True)
    monkeypatch.setattr(encoder_utils, "check_av1_amf_available", lambda: False)

    info = get_encoder_info()
    assert "ffmpeg_available" in info
    assert "amf_available" in info
    assert "av1_amf_available" in info
    assert "encoders" in info
    assert info["encoders"]["h264"] == "h264_amf"
    assert info["encoders"]["hevc"] == "hevc_amf"
    assert info["encoders"]["av1"] is None


def test_get_encoder_info_no_amf_reports_no_encoder(monkeypatch):
    monkeypatch.setattr(encoder_utils, "check_ffmpeg_available", lambda: True)
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: False)
    monkeypatch.setattr(encoder_utils, "check_av1_amf_available", lambda: False)

    info = get_encoder_info()
    assert info["encoders"]["h264"] is None
    assert info["encoders"]["hevc"] is None
    assert info["encoders"]["av1"] is None


# ---------- get_preview_encoder ----------

def test_preview_encoder_uses_amf_when_available(monkeypatch):
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: True)
    cfg = get_preview_encoder()
    assert cfg.encoder == "h264_amf"
    assert cfg.is_hardware is True
    assert "speed" in cfg.params  # speed-preset for preview
    assert "vbr_latency" in cfg.params


def test_preview_encoder_fails_when_amf_unavailable(monkeypatch):
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: False)
    with pytest.raises(RuntimeError, match="AMF"):
        get_preview_encoder()


# ---------- get_export_encoder (delegates to get_encoder_config) ----------

def test_export_encoder_default_codec_h264(monkeypatch):
    """Export should target h264 by default with quality+vbr_peak."""
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: True)
    cfg = get_export_encoder()
    # Either h264_amf (AMF) or libx264 (fallback) — both are valid h264 encoders
    assert cfg.encoder == "h264_amf"
    assert cfg.is_hardware is True


def test_encoder_config_fails_when_amf_unavailable(monkeypatch):
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: False)
    with pytest.raises(RuntimeError, match="AMF"):
        encoder_utils.get_encoder_config("h264")


def test_av1_config_fails_when_av1_amf_unavailable(monkeypatch):
    monkeypatch.setattr(encoder_utils, "check_amf_available", lambda: True)
    monkeypatch.setattr(encoder_utils, "check_av1_amf_available", lambda: False)
    with pytest.raises(RuntimeError, match="AV1 AMF"):
        encoder_utils.get_encoder_config("av1")


def test_render_encoder_schema_is_amf_only():
    from backend.schemas.render_schemas import RenderEncoder

    assert {encoder.value for encoder in RenderEncoder} == {
        "h264_amf",
        "hevc_amf",
        "av1_amf",
    }
