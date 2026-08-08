"""Extract mono peak array from a video file (or audio file) via ffmpeg pipe."""
from pathlib import Path
import subprocess

import pytest

from pb_studio.video.clip_audio_peaks import extract_peaks


pytestmark = pytest.mark.integration


@pytest.fixture
def sample_video_with_audio(tmp_path: Path) -> Path:
    """3s video with a 440 Hz tone audio track."""
    out = tmp_path / "tone.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_extract_peaks_returns_requested_buckets(sample_video_with_audio: Path):
    peaks = extract_peaks(str(sample_video_with_audio), n_buckets=200)
    assert len(peaks) == 200
    # 440Hz tone -> non-zero peaks
    assert max(peaks) > 0.1
    # Peaks normalized to [0,1]
    assert max(peaks) <= 1.0
    assert min(peaks) >= 0.0


def test_extract_peaks_no_audio_returns_zeros(tmp_path: Path):
    """Video without an audio track -> array of zeros, not exception."""
    out = tmp_path / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)],
        check=True, capture_output=True,
    )
    peaks = extract_peaks(str(out), n_buckets=64)
    assert len(peaks) == 64
    assert all(p == 0.0 for p in peaks)


def test_extract_peaks_missing_file_returns_empty(tmp_path: Path):
    peaks = extract_peaks(str(tmp_path / "missing.mp4"), n_buckets=64)
    assert peaks == []
