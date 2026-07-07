"""Extract a downsampled mono peak array from a video/audio file via ffmpeg.

Used by the timeline:
  - audio-lane bigger waveform (when source is the music file)
  - per-clip mini waveform (when source is the video's audio track)
"""
from __future__ import annotations
from pathlib import Path
import logging
import subprocess

import numpy as np

logger = logging.getLogger(__name__)


def extract_peaks(media_path: str, n_buckets: int = 256) -> list[float]:
    """Return a list of `n_buckets` peak magnitudes normalized to [0,1].

    Pipes ffmpeg PCM16 mono into numpy, then aggregates per bucket via max(abs(.)).
    Empty list if the file is missing or unreadable.
    Array of zeros if the file exists but has no audio track.
    """
    if n_buckets <= 0:
        return []
    p = Path(media_path)
    if not p.exists():
        return []

    from pb_studio.video.encoder_utils import _get_ffmpeg_path
    cmd = [
        _get_ffmpeg_path(), "-v", "error",
        "-i", str(p),
        "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg peaks-extract timeout for %s", p.name)
        return [0.0] * n_buckets
    if proc.returncode != 0:
        # No audio stream or other ffmpeg error -> return zeros so the UI can still draw a flat line.
        return [0.0] * n_buckets

    raw = proc.stdout
    if not raw:
        return [0.0] * n_buckets

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return [0.0] * n_buckets

    bucket_size = max(1, samples.size // n_buckets)
    peaks = np.empty(n_buckets, dtype=np.float32)
    for i in range(n_buckets):
        chunk = samples[i * bucket_size : (i + 1) * bucket_size]
        peaks[i] = float(np.max(np.abs(chunk))) if chunk.size else 0.0
    return peaks.tolist()
