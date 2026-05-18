"""FrameGrabber.extract_thumbnail_strip — N evenly-spaced thumbnails als Bytes."""
from pathlib import Path
import pytest

from pb_studio.video.frame_extractor import FrameGrabber


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """Erzeugt ein 3s farbiges Testvideo via ffmpeg (lavfi color source)."""
    import subprocess
    out = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_strip_returns_n_frames(sample_video: Path):
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(sample_video), n=5, size=(160, 90))
    assert len(frames) == 5
    for img in frames:
        assert img.size == (160, 90)


def test_strip_handles_n_larger_than_video_frames(sample_video: Path):
    """Bei n > verfuegbaren Sample-Punkten -> n Frames trotzdem, ggf. duplicated."""
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(sample_video), n=30, size=(80, 45))
    assert len(frames) == 30


def test_strip_no_video_returns_empty(tmp_path: Path):
    grabber = FrameGrabber()
    frames = grabber.extract_thumbnail_strip(str(tmp_path / "missing.mp4"), n=5)
    assert frames == []
