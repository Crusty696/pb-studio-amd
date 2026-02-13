"""
AMD AMF Encoder Utilities for PB Studio.

Provides hardware-accelerated video encoding using AMD's Advanced Media Framework.
Falls back to software encoders if AMF is not available.

Supported encoders:
- h264_amf: H.264/AVC hardware encoding (best compatibility)
- hevc_amf: H.265/HEVC hardware encoding (better compression)
- av1_amf: AV1 hardware encoding (RDNA3+ only, best quality)
"""

import logging
import subprocess
import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is installed and accessible."""
    return shutil.which("ffmpeg") is not None


def check_amf_available() -> bool:
    """
    Check if AMD AMF encoders are available AND functional.

    Prueft nicht nur ob h264_amf in FFmpeg gelistet ist,
    sondern testet auch die tatsaechliche Encoding-Faehigkeit
    (faengt Error 30 / CreateComponent-Fehler ab).

    Returns:
        True if h264_amf encoder works, False otherwise.
    """
    global _amf_available

    if _amf_available is not None:
        return _amf_available

    if not check_ffmpeg_available():
        logger.warning("FFmpeg not found in PATH")
        _amf_available = False
        return False

    try:
        # Schritt 1: Pruefen ob Encoder gelistet ist
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "h264_amf" not in result.stdout:
            logger.info("AMD AMF encoder not found in FFmpeg, using software fallback")
            _amf_available = False
            return False

        # Schritt 2: Tatsaechliches Encoding testen (faengt Error 30 ab)
        import tempfile, os
        test_out = os.path.join(tempfile.gettempdir(), "pb_amf_test.mp4")
        try:
            probe = subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=black:s=320x240:d=0.5",
                 "-c:v", "h264_amf", "-quality", "speed", test_out],
                capture_output=True, text=True, timeout=15
            )
            if probe.returncode == 0 and os.path.exists(test_out):
                _amf_available = True
                logger.info("AMD AMF encoder verfuegbar und funktional")
            else:
                _amf_available = False
                logger.warning(
                    f"AMF Encoder gelistet aber nicht funktional: {probe.stderr[:200]}"
                )
        finally:
            if os.path.exists(test_out):
                os.remove(test_out)

        return _amf_available

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to check AMF availability: {e}")
        _amf_available = False
        return False


def check_av1_amf_available() -> bool:
    """
    Check if AV1 AMF encoder is available (RDNA3+ only).

    Returns:
        True if av1_amf encoder is available, False otherwise.
    """
    global _av1_amf_available

    if _av1_amf_available is not None:
        return _av1_amf_available

    if not check_ffmpeg_available():
        _av1_amf_available = False
        return False

    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        _av1_amf_available = "av1_amf" in result.stdout

        if _av1_amf_available:
            logger.info("AMD AV1 AMF encoder available (RDNA3+)")

        return _av1_amf_available

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to check AV1 AMF availability: {e}")
        _av1_amf_available = False
        return False


def get_encoder_config(
    codec: str = "h264",
    quality: str = "balanced",
    rate_control: str = "vbr_peak",
    bitrate: Optional[int] = None,
    force_software: bool = False
) -> EncoderConfig:
    """
    Get FFmpeg encoder configuration for the specified codec.

    Automatically selects AMD AMF hardware encoder if available,
    otherwise falls back to software encoder.

    Args:
        codec: 'h264', 'hevc', or 'av1'
        quality: 'speed', 'balanced', or 'quality'
        rate_control: 'cqp', 'cbr', 'vbr_peak', or 'vbr_latency'
        bitrate: Target bitrate in bits/s (e.g., 8000000 for 8 Mbps)
        force_software: Force software encoder even if hardware is available

    Returns:
        EncoderConfig with encoder name and optimal parameters
    """
    use_amf = check_amf_available() and not force_software

    # Default bitrates for 1080p
    default_bitrates = {
        "h264": 8_000_000,   # 8 Mbps
        "hevc": 6_000_000,   # 6 Mbps
        "av1": 5_000_000,    # 5 Mbps
    }

    target_bitrate = bitrate or default_bitrates.get(codec, 8_000_000)
    max_bitrate = int(target_bitrate * 1.5)
    buf_size = int(target_bitrate * 2)

    # H.264 Encoder
    if codec == "h264":
        if use_amf:
            return EncoderConfig(
                encoder="h264_amf",
                params=[
                    "-quality", quality,
                    "-rc", rate_control,
                    "-b:v", str(target_bitrate),
                    "-maxrate", str(max_bitrate),
                    "-bufsize", str(buf_size),
                    "-g", "120",  # GOP size
                ],
                is_hardware=True,
                description="AMD AMF H.264 Hardware Encoder"
            )
        else:
            # Software fallback: libx264
            preset_map = {
                "speed": "ultrafast",
                "balanced": "medium",
                "quality": "slow"
            }
            return EncoderConfig(
                encoder="libx264",
                params=[
                    "-preset", preset_map.get(quality, "medium"),
                    "-crf", "23",
                    "-b:v", str(target_bitrate),
                    "-maxrate", str(max_bitrate),
                    "-bufsize", str(buf_size),
                ],
                is_hardware=False,
                description="libx264 Software Encoder"
            )

    # H.265/HEVC Encoder
    elif codec == "hevc":
        if use_amf:
            return EncoderConfig(
                encoder="hevc_amf",
                params=[
                    "-quality", quality,
                    "-rc", rate_control,
                    "-b:v", str(target_bitrate),
                    "-maxrate", str(max_bitrate),
                ],
                is_hardware=True,
                description="AMD AMF HEVC Hardware Encoder"
            )
        else:
            # Software fallback: libx265
            preset_map = {
                "speed": "ultrafast",
                "balanced": "medium",
                "quality": "slow"
            }
            return EncoderConfig(
                encoder="libx265",
                params=[
                    "-preset", preset_map.get(quality, "medium"),
                    "-crf", "28",
                    "-b:v", str(target_bitrate),
                ],
                is_hardware=False,
                description="libx265 Software Encoder"
            )

    # AV1 Encoder
    elif codec == "av1":
        # AV1 AMF requires RDNA3+
        if use_amf and check_av1_amf_available():
            return EncoderConfig(
                encoder="av1_amf",
                params=[
                    "-quality", quality,
                    "-b:v", str(target_bitrate),
                ],
                is_hardware=True,
                description="AMD AMF AV1 Hardware Encoder (RDNA3+)"
            )
        else:
            # Software fallback: SVT-AV1
            preset_map = {
                "speed": "10",
                "balanced": "6",
                "quality": "4"
            }
            return EncoderConfig(
                encoder="libsvtav1",
                params=[
                    "-preset", preset_map.get(quality, "6"),
                    "-crf", "30",
                    "-b:v", str(target_bitrate),
                ],
                is_hardware=False,
                description="SVT-AV1 Software Encoder"
            )

    # Unknown codec - default to H.264
    logger.warning(f"Unknown codec '{codec}', defaulting to H.264")
    return get_encoder_config("h264", quality, rate_control, bitrate, force_software)


def get_preview_encoder() -> EncoderConfig:
    """
    Get fast encoder configuration for preview rendering.

    Uses hardware acceleration with speed preset for fastest encoding.

    Returns:
        EncoderConfig optimized for preview (fast, lower quality)
    """
    if check_amf_available():
        return EncoderConfig(
            encoder="h264_amf",
            params=[
                "-quality", "speed",
                "-rc", "vbr_latency",
                "-b:v", "4000000",  # 4 Mbps for preview
            ],
            is_hardware=True,
            description="AMD AMF H.264 (Preview)"
        )
    else:
        return EncoderConfig(
            encoder="libx264",
            params=[
                "-preset", "ultrafast",
                "-crf", "28",
            ],
            is_hardware=False,
            description="libx264 (Preview)"
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
    global _amf_available, _av1_amf_available
    _amf_available = None
    _av1_amf_available = None


def get_encoder_info() -> dict:
    """
    Get information about available encoders.

    Returns:
        Dict with encoder availability status
    """
    return {
        "ffmpeg_available": check_ffmpeg_available(),
        "amf_available": check_amf_available(),
        "av1_amf_available": check_av1_amf_available(),
        "encoders": {
            "h264": "h264_amf" if check_amf_available() else "libx264",
            "hevc": "hevc_amf" if check_amf_available() else "libx265",
            "av1": "av1_amf" if check_av1_amf_available() else "libsvtav1",
        }
    }
