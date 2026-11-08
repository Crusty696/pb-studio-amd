"""Cached ffprobe duration lookup shared by pacing and export."""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_clip_duration(clip_path: str, cache: dict[str, float], log: logging.Logger = logger) -> float:
    """Ermittelt Clip-Dauer via ffprobe (kein ffmpeg-python). Cached per Pfad."""
    key = str(clip_path)
    if key in cache:
        return cache[key]
    from pb_studio.video.encoder_utils import _get_ffprobe_path
    cmd = [
        _get_ffprobe_path(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", str(clip_path)
    ]
    try:
        res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
        dur = float(json.loads(res)["format"]["duration"])
        cache[key] = dur
        return dur
    except Exception as e:
        log.error(f"Clip-Dauer nicht ermittelbar: {clip_path}: {e}")
        raise ValueError(f"Konnte Dauer nicht lesen: {Path(clip_path).name}") from e

