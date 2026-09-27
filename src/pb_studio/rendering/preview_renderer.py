"""
PreviewGenerator - Schnelle Vorschau ab beliebigem Zeitpunkt (AMD Version).

Erzeugt 90-Sekunden-Previews mit Smart Slicing.
Kein ffmpeg-python — nutzt subprocess direkt.
Kein NVENC — AP2.4 (Audit 2026-06-10): nutzt get_preview_encoder()
mit h264_amf; fehlendes AMF ist ein expliziter Fehler.
"""

import logging
import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pb_studio.video.encoder_utils import (
    _get_ffmpeg_path,
    _get_ffprobe_path,
    get_amf_device_args,
    get_preview_encoder,
)

logger = logging.getLogger(__name__)


def _preview_encoder_args() -> list[str]:
    """Encoder-Args für Preview-Segmente (AMF-first, IRON RULE 4)."""
    enc = get_preview_encoder()
    return ["-c:v", enc.encoder, *enc.params]


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

    OUTPUT_WIDTH = 640
    OUTPUT_HEIGHT = 360
    OUTPUT_FPS = 30
    DEFAULT_DURATION = 90.0

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path("data/temp")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_duration_sec = 0.0
        self.audio_included = False

    def generate_preview(
        self,
        timeline: list[TimelineEntry],
        start_time_sec: float = 0.0,
        duration: float = DEFAULT_DURATION,
        audio_path: str | Path | None = None,
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
        success = self._render_clips(
            filtered_clips, start_time_sec, duration, output_path,
            audio_path=Path(audio_path) if audio_path else None,
        )
        if not success:
            return None
        measured_duration = self._probe_duration(output_path)
        if measured_duration is None or measured_duration <= 0:
            logger.error("Preview-Artefakt hat keine gueltige ffprobe-Dauer")
            return None
        self.last_duration_sec = measured_duration
        self.audio_included = audio_path is not None
        return output_path.resolve()

    @staticmethod
    def _probe_duration(path: Path) -> float | None:
        cmd = [
            _get_ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path.resolve()),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15,
            )
            if result.returncode != 0:
                return None
            duration = float(json.loads(result.stdout).get("format", {}).get("duration"))
            return duration if math.isfinite(duration) and duration > 0 else None
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
            logger.exception("Preview-Dauer konnte nicht gemessen werden: %s", path)
            return None

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
        *,
        audio_path: Path | None = None,
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
                    _get_ffmpeg_path(), "-y",
                    *get_amf_device_args(),
                    "-ss", str(actual_start),
                    "-t", str(clip_duration),
                    "-i", clip.video_path,
                    "-vf", vf,
                    *_preview_encoder_args(),
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
                else:
                    logger.error(
                        f"ffmpeg segment {i} rendering fehlgeschlagen (code {result.returncode}):\n"
                        f"Stderr: {result.stderr}\n"
                        f"Cmd: {' '.join(cmd)}"
                    )
                    return False

            if not segment_files:
                logger.error("Keine gültigen Segmente gerendert")
                return False

            logger.info(f"Preview: {len(segment_files)} Segmente gerendert, concat...")

            # BUG-FIX: Windows-Doppelpunkt-Bug im concat-Protokoll beheben.
            # Da absolute Pfade auf Windows einen Doppelpunkt enthalten (z. B. 'C:\...'),
            # scheitert ffmpeg mit 'Protocol c not on whitelist'.
            # Lösung: Wir wechseln das Arbeitsverzeichnis des ffmpeg Concat-Prozesses auf
            # temp_dir und übergeben nur die relativen Dateinamen der Segmente an concat_input.
            # Der Ausgabepfad muss unbedingt absolut übergeben werden!
            concat_input = "|".join(s.name for s in segment_files)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                _get_ffmpeg_path(), "-y",
                *get_amf_device_args(),
                "-i", f"concat:{concat_input}",
            ]
            if audio_path is not None:
                if not audio_path.is_file():
                    raise FileNotFoundError(f"Preview-Musikdatei fehlt: {audio_path}")
                cmd.extend(["-ss", f"{preview_start:.6f}", "-i", str(audio_path.resolve())])
                cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
            cmd.extend([*_preview_encoder_args(), "-pix_fmt", "yuv420p"])
            if audio_path is not None:
                cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
            else:
                cmd.append("-an")
            cmd.extend(["-t", f"{preview_duration:.6f}", str(output_path.resolve())])
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
                cwd=str(temp_dir)
            )

            if result.returncode != 0:
                logger.error(
                    f"ffmpeg preview concat fehlgeschlagen (code {result.returncode}):\n"
                    f"Stderr: {result.stderr}\n"
                    f"Cmd: {' '.join(cmd)}"
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
