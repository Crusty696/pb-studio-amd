"""
AMD AMF Encoder Utilities for PB Studio.

Provides hardware-accelerated video encoding using AMD's Advanced Media Framework.
AMF unavailability is a hard error; software encoders are prohibited.

Supported encoders:
- h264_amf: H.264/AVC hardware encoding (best compatibility)
- hevc_amf: H.265/HEVC hardware encoding (better compression)
- av1_amf: AV1 hardware encoding (RDNA3+ only, best quality)
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from pb_studio.core.directml_adapter import get_directml_adapter
from pb_studio.runtime_contract import ffmpeg_path, ffprobe_path

logger = logging.getLogger(__name__)


class Codec(Enum):
    """Supported video codecs."""
    H264 = "h264"
    HEVC = "hevc"
    AV1 = "av1"


class Quality(Enum):
    """Encoding quality presets."""
    SPEED = "speed"       # Fastest, lower quality
    BALANCED = "balanced" # Good balance
    QUALITY = "quality"   # Best quality, slower


class RateControl(Enum):
    """Rate control modes."""
    CQP = "cqp"              # Constant QP
    CBR = "cbr"              # Constant Bitrate
    VBR_PEAK = "vbr_peak"    # Variable Bitrate (recommended)
    VBR_LATENCY = "vbr_latency"  # VBR Low Latency


@dataclass
class EncoderConfig:
    """Configuration for video encoder."""
    encoder: str                  # FFmpeg encoder name
    params: list                  # Encoder-specific parameters
    is_hardware: bool             # True if hardware accelerated
    description: str              # Human-readable description


# Cache for encoder availability check
_amf_available: Optional[bool] = None
_av1_amf_available: Optional[bool] = None
# Audit-Fix 2026-07-10 (Sweep-Finding EXPORT-8): invalidate_encoder_cache() war
# definiert aber nie aufgerufen — Treiber-Update/GPU-Handoff waehrend der
# (langlaufenden) Backend-Session blieb bis zum Neustart unsichtbar. TTL statt
# neuem UI/Endpoint: einfachster Fix ohne neue Oberflaeche.
_ENCODER_CACHE_TTL_SECONDS = 600.0
_amf_checked_at: Optional[float] = None
_av1_amf_checked_at: Optional[float] = None


def _get_ffmpeg_path() -> str:
    """Return the verified project-local FFmpeg runtime."""
    return str(ffmpeg_path())


def _get_ffprobe_path() -> str:
    """Return the verified FFprobe paired with canonical FFmpeg."""
    return str(ffprobe_path())


def get_amf_device_args() -> list[str]:
    """Return global FFmpeg args for the selected DirectML DXGI adapter."""
    device_id = get_directml_adapter().device_id
    if isinstance(device_id, bool) or not isinstance(device_id, int) or device_id < 0:
        raise RuntimeError("DirectML adapter has an invalid device ID for AMF")
    return ["-init_hw_device", f"d3d11va=pb_amf:{device_id}"]


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is installed and accessible."""
    try:
        return Path(_get_ffmpeg_path()).is_file()
    except RuntimeError:
        return False


def invalidate_encoder_cache():
    """Invalidiert den globalen AMF-Cache (erzwingt Neu-Erkennung)."""
    global _amf_available
    _amf_available = None
    logger.info("AMF encoder status cache invalidated")

def check_amf_available() -> bool:
    """
    Check if AMD AMF encoders are available AND functional.

    Prueft nicht nur ob h264_amf in FFmpeg gelistet ist,
    sondern testet auch die tatsaechliche Encoding-Faehigkeit
    (faengt Error 30 / CreateComponent-Fehler ab).

    Returns:
        True if h264_amf encoder works, False otherwise.
    """
    global _amf_available, _amf_checked_at

    import time as _time
    if _amf_available is not None and _amf_checked_at is not None:
        if (_time.monotonic() - _amf_checked_at) < _ENCODER_CACHE_TTL_SECONDS:
            return _amf_available
        logger.debug("AMF-Cache TTL abgelaufen — Neu-Erkennung")

    if not check_ffmpeg_available():
        logger.warning("FFmpeg not found in PATH")
        _amf_available = False
        _amf_checked_at = _time.monotonic()
        return False

    try:
        ffmpeg = _get_ffmpeg_path()
        # Schritt 1: Pruefen ob Encoder gelistet ist
        result = subprocess.run(
            [ffmpeg, "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "h264_amf" not in result.stdout:
            logger.info("AMD AMF encoder not found in FFmpeg, using software fallback")
            _amf_available = False
            _amf_checked_at = _time.monotonic()
            return False

        # Schritt 2: Tatsaechliches Encoding testen (faengt Error 30 ab)
        import tempfile
        test_out = str(Path(tempfile.gettempdir()) / "pb_amf_test.mp4")
        try:
            probe = subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                 *get_amf_device_args(),
                 "-f", "lavfi", "-i", "color=black:s=320x240:d=0.5",
                 "-c:v", "h264_amf", "-quality", "speed", test_out],
                capture_output=True, text=True, timeout=15
            )
            if probe.returncode == 0 and Path(test_out).exists():
                _amf_available = True
                logger.info("AMD AMF encoder verfuegbar und funktional")
            else:
                _amf_available = False
                logger.warning(
                    f"AMF Encoder gelistet aber nicht funktional: {probe.stderr[:200]}"
                )
        finally:
            if Path(test_out).exists():
                os.remove(test_out)

        _amf_checked_at = _time.monotonic()
        return _amf_available

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to check AMF availability: {e}")
        _amf_available = False
        _amf_checked_at = _time.monotonic()
        return False


def check_av1_amf_available() -> bool:
    """
    Check if AV1 AMF encoder is available (RDNA3+ only).

    Returns:
        True if av1_amf encoder is available, False otherwise.
    """
    global _av1_amf_available, _av1_amf_checked_at

    import time as _time
    if _av1_amf_available is not None and _av1_amf_checked_at is not None:
        if (_time.monotonic() - _av1_amf_checked_at) < _ENCODER_CACHE_TTL_SECONDS:
            return _av1_amf_available

    if not check_ffmpeg_available():
        _av1_amf_available = False
        _av1_amf_checked_at = _time.monotonic()
        return False

    try:
        ffmpeg = _get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg, "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        _av1_amf_available = "av1_amf" in result.stdout

        if _av1_amf_available:
            logger.info("AMD AV1 AMF encoder available (RDNA3+)")

        _av1_amf_checked_at = _time.monotonic()
        return _av1_amf_available

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to check AV1 AMF availability: {e}")
        _av1_amf_available = False
        _av1_amf_checked_at = _time.monotonic()
        return False


def get_encoder_config(
    codec: str = "h264",
    quality: str = "balanced",
    rate_control: str = "vbr_peak",
    bitrate: Optional[int] = None,
) -> EncoderConfig:
    """
    Get FFmpeg encoder configuration for the specified codec.

    Selects an AMD AMF hardware encoder or fails explicitly.

    Args:
        codec: 'h264', 'hevc', or 'av1'
        quality: 'speed', 'balanced', or 'quality'
        rate_control: 'cqp', 'cbr', 'vbr_peak', or 'vbr_latency'
        bitrate: Target bitrate in bits/s (e.g., 8000000 for 8 Mbps)
    Returns:
        EncoderConfig with encoder name and optimal parameters
    """
    if codec not in {"h264", "hevc", "av1"}:
        raise ValueError(f"Unsupported AMF codec: {codec!r}")
    if not check_amf_available():
        raise RuntimeError(
            "AMD AMF encoder unavailable or non-functional; "
            "software encoding is disabled by project policy"
        )
    if codec == "av1" and not check_av1_amf_available():
        raise RuntimeError("AV1 AMF encoder unavailable on this AMD GPU/FFmpeg build")

    # Default bitrates for 1080p
    default_bitrates = {
        "h264": 8_000_000,   # 8 Mbps
        "hevc": 6_000_000,   # 6 Mbps
        "av1": 5_000_000,    # 5 Mbps
    }

    target_bitrate = bitrate or default_bitrates.get(codec, 8_000_000)
    max_bitrate = int(target_bitrate * 1.5)
    buf_size = int(target_bitrate * 2)

    if codec == "h264":
        return EncoderConfig(
            encoder="h264_amf",
            params=[
                "-quality", quality,
                "-rc", rate_control,
                "-b:v", str(target_bitrate),
                "-maxrate", str(max_bitrate),
                "-bufsize", str(buf_size),
                "-g", "120",
            ],
            is_hardware=True,
            description="AMD AMF H.264 Hardware Encoder",
        )
    if codec == "hevc":
        return EncoderConfig(
            encoder="hevc_amf",
            params=[
                "-quality", quality,
                "-rc", rate_control,
                "-b:v", str(target_bitrate),
                "-maxrate", str(max_bitrate),
            ],
            is_hardware=True,
            description="AMD AMF HEVC Hardware Encoder",
        )
    return EncoderConfig(
        encoder="av1_amf",
        params=[
            "-quality", quality,
            "-b:v", str(target_bitrate),
        ],
        is_hardware=True,
        description="AMD AMF AV1 Hardware Encoder (RDNA3+)",
    )


def get_preview_encoder() -> EncoderConfig:
    """
    Get fast encoder configuration for preview rendering.

    Uses hardware acceleration with speed preset for fastest encoding.

    Returns:
        EncoderConfig optimized for preview (fast, lower quality)
    """
    return get_encoder_config(
        codec="h264",
        quality="speed",
        rate_control="vbr_latency",
        bitrate=4_000_000,
    )


def get_export_encoder(
    codec: str = "h264",
    quality: str = "quality"
) -> EncoderConfig:
    """
    Get high-quality encoder configuration for final export.

    Uses hardware acceleration with quality preset.

    Args:
        codec: 'h264', 'hevc', or 'av1'
        quality: Usually 'quality' for exports

    Returns:
        EncoderConfig optimized for export (high quality)
    """
    return get_encoder_config(
        codec=codec,
        quality=quality,
        rate_control="vbr_peak"
    )


def build_ffmpeg_encode_args(config: EncoderConfig) -> list:
    """
    Build FFmpeg command line arguments from encoder config.

    Args:
        config: EncoderConfig object

    Returns:
        List of FFmpeg arguments (e.g., ["-c:v", "h264_amf", ...])
    """
    args = ["-c:v", config.encoder]
    args.extend(config.params)
    return args


def reset_availability_cache():
    """Reset cached encoder availability (for testing)."""
    global _amf_available, _av1_amf_available, _amf_checked_at, _av1_amf_checked_at
    _amf_available = None
    _av1_amf_available = None
    _amf_checked_at = None
    _av1_amf_checked_at = None


def get_encoder_info() -> dict:
    """
    Get information about available encoders.

    Returns:
        Dict with encoder availability status
    """
    amf_available = check_amf_available()
    av1_amf_available = check_av1_amf_available() if amf_available else False
    return {
        "ffmpeg_available": check_ffmpeg_available(),
        "amf_available": amf_available,
        "av1_amf_available": av1_amf_available,
        "encoders": {
            "h264": "h264_amf" if amf_available else None,
            "hevc": "hevc_amf" if amf_available else None,
            "av1": "av1_amf" if av1_amf_available else None,
        }
    }
