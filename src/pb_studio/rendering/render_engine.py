"""
RenderEngine - AMD AMF GPU-Rendering für PB_studio.

Nutzt AMD AMF Hardware-Encoder (h264_amf, hevc_amf) via FFmpeg.
Kein NVENC, kein CUDA — reine AMD DirectML/AMF Pipeline.
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


def _get_clip_path(clip: dict) -> Optional[Path]:
    """Extrahiert den Clip-Pfad aus einem Timeline-Dict."""
    for key in ("clip_path", "file_path", "path", "video_path"):
        val = clip.get(key)
        if val:
            p = Path(val)
            if p.exists():
                return p
    return None


@dataclass
class RenderConfig:
    """Konfiguration für das Video-Rendering."""
    output_path: str = ""
    preset: str = "medium"
    crf: int = 23
    resolution: str = "1920x1080"
    fps: int = 30
    audio_bitrate: int = 192
    pixel_format: str = "yuv420p"
    audio_codec: str = "aac"
    sample_rate: int = 48000

    @property
    def width(self) -> int:
        return int(self.resolution.split("x")[0])

    @property
    def height(self) -> int:
        return int(self.resolution.split("x")[1])


class RenderEngine:
    """FFmpeg Render Engine mit AMD AMF Hardware-Encoding."""

    def __init__(self, config: Optional[RenderConfig] = None) -> None:
        self.config = config if config is not None else RenderConfig()
        self._active_processes: list[subprocess.Popen] = []
        import threading
        self._process_lock = threading.Lock()
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        self._is_cancelled = False
        self._encoder = self._detect_encoder()
        logger.info(f"RenderEngine: Encoder erkannt: {self._encoder}")

    def _detect_encoder(self) -> str:
        """Testet verfügbare AMD-Encoder und gibt den besten zurück.

        Reihenfolge: hevc_amf → h264_amf → h264_mf → libx264.
        Kein NVENC, kein CUDA — AMD-only (IRON RULE).
        """
        candidates = [
            "hevc_amf",
            "h264_amf",
            "h264_mf",
            "libx264",
        ]
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True,
                timeout=15,
            )
            available = result.stdout.decode("utf-8", errors="replace") + result.stderr.decode("utf-8", errors="replace")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("RenderEngine: FFmpeg nicht erreichbar — verwende libx264")
            return "libx264"

        for enc in candidates:
            if enc in available:
                logger.info(f"RenderEngine: Encoder ausgewählt: {enc}")
                return enc

        logger.warning("RenderEngine: Kein bevorzugter Encoder gefunden — verwende libx264")
        return "libx264"

    def render(self, timeline: dict[str, Any]) -> bool:
        """Rendert die Timeline mit AMD AMF GPU-Encoding."""
        self._is_cancelled = False
        concat_file = None
        try:
            clips = timeline.get("clips", [])
            valid_clips = self._filter_valid_clips(clips)
            if not valid_clips:
                logger.error("Keine gültigen Clips gefunden.")
                return False

            concat_file = self._create_concat_file(valid_clips)
            if not concat_file:
                return False

            cmd = self._build_ffmpeg_command(concat_file, timeline)
            return self._execute_ffmpeg_with_progress(cmd)
        except Exception as e:
            logger.error(f"Rendering fehlgeschlagen: {e}")
            return False
        finally:
            if concat_file is not None:
                try:
                    concat_file.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Konnte Concat-Datei nicht löschen: {e}")

    def _filter_valid_clips(self, clips: list[dict]) -> list[Path]:
        valid = []
        for clip in clips:
            path = _get_clip_path(clip)
            if path and path.resolve().exists():
                valid.append(path.resolve())
        return valid

    def _create_concat_file(self, valid_clips: list[Path]) -> Optional[Path]:
        try:
            temp_dir = Path(tempfile.gettempdir()) / "pb_studio_render"
            temp_dir.mkdir(parents=True, exist_ok=True)
            concat_file = temp_dir / "concat_list.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for path in valid_clips:
                    # BUG-069 FIX: FFmpeg concat protocol requires single quotes and specific escaping
                    safe_path = str(path.resolve()).replace("\\", "/")
                    p_escaped = safe_path.replace("'", "'\\''")
                    f.write(f"file '{p_escaped}'\n")
            return concat_file
        except Exception as e:
            logger.error(f"Concat-Datei konnte nicht erstellt werden: {e}")
            return None

    def _build_ffmpeg_command(
        self, concat_file: Path, timeline: dict[str, Any]
    ) -> list[str]:
        """Baut FFmpeg-Kommando mit AMD AMF Encoder."""
        audio_path = timeline.get("audio_path")
        audio_offset = timeline.get("audio_offset", 0.0)

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]

        if audio_path and Path(audio_path).exists():
            if audio_offset > 0:
                cmd.extend(["-ss", str(audio_offset)])
            cmd.extend(["-i", str(audio_path)])

        # R02 Fix: Dynamisch erkannter Encoder statt hardcodiertem hevc_amf
        encoder = self._encoder
        if encoder == "hevc_amf":
            cmd.extend(["-c:v", "hevc_amf", "-quality", "balanced", "-b:v", "12M"])
        elif encoder == "h264_amf":
            cmd.extend(["-c:v", "h264_amf", "-quality", "balanced", "-b:v", "12M"])
        elif encoder == "h264_mf":
            cmd.extend(["-c:v", "h264_mf", "-b:v", "10M"])
        elif encoder == "libx265":
            cmd.extend(["-c:v", "libx265", "-preset", "fast", "-crf", "24", "-tag:v", "hvc1"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])

        scale_filter = (
            f"scale={self.config.width}:{self.config.height}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={self.config.width}:{self.config.height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={self.config.fps}"
        )
        cmd.extend(["-vf", scale_filter, "-pix_fmt", "yuv420p"])

        if audio_path and Path(audio_path).exists():
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            try:
                import json
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json", str(audio_path)
                ]
                res = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT, timeout=30)
                audio_dur = float(json.loads(res)["format"]["duration"])
                cmd.extend(["-t", f"{audio_dur:.3f}"])
                logger.info(f"RenderEngine: Dauer via Audio = {audio_dur:.1f}s")
            except Exception as e:
                logger.warning(f"Audio-Dauer nicht ermittelbar: {e}")

        cmd.append(self.config.output_path)
        return cmd

    def _execute_ffmpeg_with_progress(self, cmd: list[str]) -> bool:
        """Führt FFmpeg aus und gibt Ergebnis zurück."""
        process = None
        try:
            output_path = Path(self.config.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"AMD AMF Rendering gestartet: {output_path.name}")

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1
            )
            with self._process_lock:
                self._active_processes.append(process)

            try:
                stdout, stderr = process.communicate(timeout=3600)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate()
                raise RuntimeError("FFmpeg Timeout nach 3600s")

            if process.returncode != 0:
                logger.error(f"FFmpeg AMF Fehler: {stderr}")
                try:
                    if output_path.exists():
                        output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return False

            return output_path.exists() and output_path.stat().st_size > 0

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"AMD AMF Rendering Ausführungsfehler: {e}")
            return False
        finally:
            if process is not None:
                with self._process_lock:
                    if process in self._active_processes:
                        self._active_processes.remove(process)
                if process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception:
                        pass
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None:
                        try:
                            pipe.close()
                        except Exception:
                            pass

    def kill_zombie_processes(self) -> int:
        """Beendet alle aktiven FFmpeg-Subprozesse."""
        killed = 0
        with self._process_lock:
            processes = list(self._active_processes)
        for p in processes:
            try:
                p.kill()
                killed += 1
            except Exception:
                pass
        return killed

    def __del__(self) -> None:
        self.kill_zombie_processes()
