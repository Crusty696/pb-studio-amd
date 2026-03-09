"""VideoRenderer - Rendert die finale Cut-Liste zu einem Video.

AMD-Version: Nutzt AMF Hardware-Encoding (h264_amf, hevc_amf) statt NVENC.
Verwendet encoder_utils für AMD-kompatible FFmpeg-Parameter.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List

logger = logging.getLogger(__name__)


class VideoRenderer:
    """Rendert eine Cut-Liste zu einem fertigen Video (AMD AMF).

    Workflow:
    1. Clips trimmen (FFmpeg)
    2. Concat-Liste erstellen
    3. Audio zusammenführen
    4. Finales Encoding mit AMF
    """

    def __init__(
        self, codec: str = "h264_amf", quality: str = "medium",
        temp_dir: str | Path | None = None,
    ):
        self.codec = codec
        self.quality = quality
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "pb_studio_render"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._cancelled = False

        # FFmpeg-Pfad aus encoder_utils
        try:
            from .encoder_utils import get_encoder_config
            config = get_encoder_config()
            self._ffmpeg = config.get("ffmpeg_path", "ffmpeg")
            self._ffprobe = config.get("ffprobe_path", "ffprobe")
        except Exception:
            self._ffmpeg = "ffmpeg"
            self._ffprobe = "ffprobe"

    def _get_encode_params(self) -> List[str]:
        """Gibt AMD AMF Encoding-Parameter zurück."""
        if self.codec == "h264_amf":
            params = ["-c:v", "h264_amf"]
            if self.quality == "fast":
                params += ["-quality", "speed", "-rc", "vbr_peak", "-b:v", "8M"]
            elif self.quality == "high":
                params += ["-quality", "quality", "-rc", "vbr_peak", "-b:v", "20M"]
            else:  # medium
                params += ["-quality", "balanced", "-rc", "vbr_peak", "-b:v", "12M"]
        elif self.codec == "hevc_amf":
            params = ["-c:v", "hevc_amf"]
            if self.quality == "fast":
                params += ["-quality", "speed", "-rc", "vbr_peak", "-b:v", "6M"]
            elif self.quality == "high":
                params += ["-quality", "quality", "-rc", "vbr_peak", "-b:v", "15M"]
            else:
                params += ["-quality", "balanced", "-rc", "vbr_peak", "-b:v", "10M"]
        else:
            # Software-Fallback
            params = ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
        return params

    def _run_ffmpeg(self, cmd: List[str]) -> bool:
        """Führt FFmpeg-Befehl aus. Kein shell=True (IRON RULE)."""
        try:
            logger.debug(f"FFmpeg: {' '.join(cmd[:8])}...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=7200
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg Fehler: {result.stderr[-500:]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg Timeout (2h)")
            return False
        except Exception as e:
            logger.error(f"FFmpeg Ausführung fehlgeschlagen: {e}")
            return False

    def render_video(
        self, cut_list: list, audio_path: str, output_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> str | None:
        """Rendert Cut-Liste zu Video.

        Args:
            cut_list: Liste mit Dicts/Objekten (file_path, clip_start, duration)
            audio_path: Pfad zur Audio-Datei
            output_path: Ausgabepfad

        Returns:
            Pfad zum Video oder None
        """
        if not cut_list:
            logger.error("Leere Cut-Liste")
            return None

        self._cancelled = False
        total_steps = len(cut_list) + 2
        current = 0

        try:
            logger.info(f"Starte Rendering: {len(cut_list)} Cuts -> {output_path}")

            # 1. Clips trimmen
            segments = []
            for i, cut in enumerate(cut_list):
                if self._cancelled:
                    self._cleanup(segments)
                    return None

                seg = self._prepare_segment(cut, i)
                if seg:
                    segments.append(seg)

                current += 1
                if progress_callback:
                    progress_callback(current / total_steps)

            if not segments:
                logger.error("Keine Segmente erstellt")
                return None

            # 2. Concat
            concat_path = self.temp_dir / "concat_video.mp4"
            if not self._concat_segments(segments, concat_path):
                self._cleanup(segments)
                return None
            current += 1
            if progress_callback:
                progress_callback(current / total_steps)

            # 3. Audio + finales Encoding
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            if not self._merge_audio(concat_path, audio_path, out):
                self._cleanup(segments + [concat_path])
                return None

            if progress_callback:
                progress_callback(1.0)

            self._cleanup(segments + [concat_path])
            logger.info(f"Rendering fertig: {output_path}")
            return str(out)

        except Exception as e:
            logger.error(f"Rendering fehlgeschlagen: {e}", exc_info=True)
            return None

    def _prepare_segment(self, cut, index: int) -> Path | None:
        """Trimmt einen Clip zu einem Segment."""
        # Cut kann Dict oder Objekt sein
        if isinstance(cut, dict):
            file_path = cut.get("file_path", "")
            clip_start = cut.get("clip_start", cut.get("start_time", 0))
            duration = cut.get("duration", 5.0)
        else:
            file_path = getattr(cut, "file_path", "") or ""
            if hasattr(cut, "get_file_path"):
                file_path = cut.get_file_path() or file_path
            clip_start = getattr(cut, "clip_start", 0)
            if hasattr(cut, "get_clip_start"):
                clip_start = cut.get_clip_start()
            duration = getattr(cut, "duration", 5.0)

        if not file_path or not Path(file_path).exists():
            logger.error(f"Clip nicht gefunden: {file_path}")
            return None

        seg_path = self.temp_dir / f"segment_{index:04d}.mp4"

        cmd = [
            self._ffmpeg, "-y",
            "-ss", str(clip_start), "-t", str(duration),
            "-i", str(file_path),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
        ] + self._get_encode_params() + ["-an", str(seg_path)]

        if self._run_ffmpeg(cmd) and seg_path.exists():
            return seg_path
        return None

    def _concat_segments(self, segments: list[Path], output: Path) -> bool:
        concat_list = self.temp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for seg in segments:
                escaped = str(seg).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(output)
        ]
        ok = self._run_ffmpeg(cmd)
        concat_list.unlink(missing_ok=True)
        return ok

    def _merge_audio(self, video: Path, audio_path: str, output: Path) -> bool:
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output)
        ]
        return self._run_ffmpeg(cmd)

    def _cleanup(self, files: list[Path]) -> None:
        for fp in files:
            try:
                if isinstance(fp, Path) and fp.exists():
                    fp.unlink()
            except Exception:
                pass

    def cancel(self) -> None:
        self._cancelled = True

    def generate_preview(
        self, cut_list: list, audio_path: str, output_path: str,
        start_time: float = 0.0, duration: float = 30.0,
        progress_callback: Callable[[float], None] | None = None,
    ) -> str | None:
        end_time = start_time + duration
        preview_cuts = [
            c for c in cut_list
            if (getattr(c, 'start_time', c.get('start_time', 0)) if isinstance(c, dict) else getattr(c, 'start_time', 0)) < end_time
        ]
        if not preview_cuts:
            return None
        orig_q = self.quality
        self.quality = "fast"
        result = self.render_video(preview_cuts, audio_path, output_path, progress_callback)
        self.quality = orig_q
        return result
