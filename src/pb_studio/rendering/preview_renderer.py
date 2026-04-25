"""
PreviewGenerator - Schnelle Vorschau ab beliebigem Zeitpunkt (AMD Version).

Erzeugt 90-Sekunden-Previews mit Smart Slicing.
Kein ffmpeg-python — nutzt subprocess direkt.
Kein NVENC — nutzt libx264 ultrafast für Speed.
"""

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TimelineEntry:
    """Ein Eintrag in der Timeline (Clip-Segment)."""
    video_path: str
    start_time: float
    end_time: float
    timeline_start: float
    timeline_end: float

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def timeline_duration(self) -> float:
        return self.timeline_end - self.timeline_start


class PreviewGenerator:
    """Generiert schnelle Vorschauen für die Timeline."""

    OUTPUT_WIDTH = 1920
    OUTPUT_HEIGHT = 1080
    OUTPUT_FPS = 30
    DEFAULT_DURATION = 90.0

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path("data/temp")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_preview(
        self,
        timeline: list[TimelineEntry],
        start_time_sec: float = 0.0,
        duration: float = DEFAULT_DURATION,
    ) -> Path | None:
        """Generiert eine Preview ab einem bestimmten Zeitpunkt."""
        if not timeline:
            logger.error("Timeline ist leer")
            return None

        end_time_sec = start_time_sec + duration
        filtered_clips = self._filter_clips_for_interval(
            timeline, start_time_sec, end_time_sec
        )
        if not filtered_clips:
            logger.warning(f"Keine Clips im Intervall [{start_time_sec}, {end_time_sec}]")
            return None

        logger.info(
            f"Preview: {len(filtered_clips)} Clips für "
            f"[{start_time_sec:.1f}s - {end_time_sec:.1f}s]"
        )

        output_path = self.output_dir / "preview.mp4"
        success = self._render_clips(filtered_clips, start_time_sec, duration, output_path)
        return output_path if success else None

    def _filter_clips_for_interval(
        self, timeline: list[TimelineEntry], start: float, end: float
    ) -> list[TimelineEntry]:
        filtered = [e for e in timeline if e.timeline_end > start and e.timeline_start < end]
        filtered.sort(key=lambda e: e.timeline_start)
        return filtered

    def _render_clips(
        self, clips: list[TimelineEntry],
        preview_start: float, preview_duration: float,
        output_path: Path,
    ) -> bool:
        """Rendert gefilterte Clips zu einer Preview via mpegts concat."""
        temp_dir = None
        segment_files = []

        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="pb_preview_"))

            for i, clip in enumerate(clips):
                clip_offset = max(0, preview_start - clip.timeline_start)
                actual_start = clip.start_time + clip_offset
                clip_end_in_preview = min(
                    clip.timeline_end - preview_start, preview_duration
                )
                clip_start_in_preview = max(0, clip.timeline_start - preview_start)
                clip_duration = clip_end_in_preview - clip_start_in_preview

                if clip_duration <= 0.05:
                    continue

                seg_path = temp_dir / f"seg_{i:04d}.ts"
                vf = (
                    f"scale={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}"
                    f":force_original_aspect_ratio=decrease,"
                    f"pad={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
                    f"fps={self.OUTPUT_FPS:.3f},setpts=PTS-STARTPTS"
                )
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(actual_start),
                    "-t", str(clip_duration),
                    "-i", clip.video_path,
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-pix_fmt", "yuv420p",
                    "-an", "-f", "mpegts",
                    str(seg_path)
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=60
                )
                if result.returncode == 0 and seg_path.exists():
                    segment_files.append(seg_path)

            if not segment_files:
                logger.error("Keine gültigen Segmente gerendert")
                return False

            logger.info(f"Preview: {len(segment_files)} Segmente gerendert, concat...")

            concat_input = "|".join(str(s) for s in segment_files)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                "ffmpeg", "-y",
                "-i", f"concat:{concat_input}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-an",
                str(output_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120
            )
            return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0

        except Exception as e:
            logger.error(f"Preview-Rendering fehlgeschlagen: {e}")
            return False
        finally:
            for f in segment_files:
                try:
                    f.unlink()
                except Exception:
                    pass
            if temp_dir is not None:
                try:
                    shutil.rmtree(str(temp_dir), ignore_errors=True)
                except Exception:
                    pass

    def cleanup(self) -> None:
        """Räumt temporäre Preview-Dateien auf."""
        try:
            for file in self.output_dir.glob("preview*.mp4"):
                file.unlink()
            for file in self.output_dir.glob("thumb_*.jpg"):
                file.unlink()
        except Exception as e:
            logger.warning(f"Cleanup-Fehler: {e}")
