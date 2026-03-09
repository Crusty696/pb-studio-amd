"""
Render Service (AMD Version)
=============================

Timeline-Rendering mit Mixed-Footage-Normalisierung.
Nutzt AMD AMF Hardware-Encoder statt NVENC.

Features:
- Auflösung/Codec Konsistenz-Check
- Normalisierung abweichender Clips (Scale/Padding, FPS)
- FFmpeg AMF für Transcoding und Concat Protocol
- Master-Audio Muxing
- Echtzeit-Progress
"""

import json
import os
import re
import subprocess
import threading
import time
import queue
from pathlib import Path
from typing import List, Dict, Optional, Callable


class RenderCancelledError(RuntimeError):
    """Raised when a render operation is cancelled cooperatively."""
    pass
import logging

logger = logging.getLogger(__name__)


def _get_clip_path_str(clip: dict) -> Optional[str]:
    """Extrahiert den Clip-Pfad als String (Top-Level und metadata)."""
    for key in ("clip_path", "file_path", "path", "video_path"):
        val = clip.get(key)
        if val and Path(val).exists():
            return str(val)
    # Auch in metadata suchen (Pacing-Engine speichert Pfade dort)
    meta = clip.get("metadata", {})
    if meta:
        for key in ("file_path", "clip_path", "path", "video_path"):
            val = meta.get(key)
            if val and Path(val).exists():
                return str(val)
    return None


class RenderService:
    """Timeline-Rendering Service mit AMD AMF Hardware-Encoding."""

    _working_encoder: Optional[str] = None
    _encoder_lock: threading.Lock = threading.Lock()

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.temp_dir = self.output_dir / ".temp_render"
        self.temp_dir.mkdir(exist_ok=True)

        with RenderService._encoder_lock:
            if RenderService._working_encoder is None:
                RenderService._working_encoder = self._detect_best_encoder()
                logger.info(f"Encoder erkannt und gecacht: {RenderService._working_encoder}")

    def _detect_best_encoder(self) -> str:
        """Testet verfügbare AMD-Encoder und gibt den besten zurück."""
        encoders = [
            ("hevc_amf", "AMD GPU H.265 (beste Kompression)"),
            ("h264_amf", "AMD GPU H.264"),
            ("h264_mf", "Windows Media Foundation"),
            ("libx265", "CPU H.265 (langsam)"),
            ("libx264", "CPU H.264 (langsam)"),
        ]

        for enc_name, desc in encoders:
            test_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", enc_name,
                "-f", "null", "-"
            ]
            try:
                result = subprocess.run(
                    test_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15
                )
                if result.returncode == 0:
                    logger.info(f"Encoder-Test OK: {enc_name} ({desc})")
                    return enc_name
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        logger.warning("Kein GPU-Encoder verfügbar, verwende libx264")
        return "libx264"

    def render_timeline(
        self,
        timeline: List[Dict],
        audio_path: str,
        output_filename: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: float = 30.0,
        bitrate: str = "15M",
        preset: str = "balanced",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        audio_offset: float = 0.0,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Hauptfunktion für Timeline-Rendering."""
        final_output = self.output_dir / output_filename
        audio_dur = self._get_audio_duration(audio_path)
        total_duration = audio_dur if audio_dur and audio_dur > 0 else self._calculate_timeline_duration(timeline)

        try:
            if progress_callback:
                progress_callback("Prüfe Quellmaterial...", 10)

            normalized_clips = self._normalize_clips(
                timeline, target_width, target_height, target_fps, progress_callback, cancel_callback
            )

            if progress_callback:
                progress_callback("Erstelle Schnittliste...", 55)
            concat_list_path = self.temp_dir / "concat_list.txt"
            self._generate_concat_file(normalized_clips, concat_list_path)

            if progress_callback:
                progress_callback("Starte Rendering...", 58)

            self._run_ffmpeg_render(
                concat_list_path, audio_path, final_output,
                bitrate, preset, audio_offset, total_duration, progress_callback, cancel_callback
            )

            if progress_callback:
                progress_callback("Fertig!", 100)
            logger.info(f"Rendering erfolgreich: {final_output}")
            return str(final_output)

        except Exception as e:
            logger.error(f"Render Error: {e}", exc_info=True)
            raise
        finally:
            self._cleanup_temp(normalized_clips if "normalized_clips" in locals() else [])

    def _calculate_timeline_duration(self, timeline: List[Dict]) -> float:
        total = 0.0
        for clip in timeline:
            in_pt = clip.get("in_point") or clip.get("in", 0.0)
            out_pt = clip.get("out_point") or clip.get("out", in_pt + 2.0)
            total += out_pt - in_pt
        return max(total, 1.0)

    def _normalize_clips(
        self, timeline: List[Dict], w: int, h: int, fps: float,
        cb: Optional[Callable], cancel_callback: Optional[Callable[[], bool]] = None
    ) -> List[Dict]:
        """Prüft Clips und transkodiert bei Bedarf in einheitliches Format."""
        normalized = []
        total = len(timeline)

        for i, clip in enumerate(timeline):
            if cancel_callback and cancel_callback():
                raise RenderCancelledError("Rendering cancelled during clip normalization")
            path = _get_clip_path_str(clip)
            if not path:
                logger.warning(f"Clip {i} hat keinen Pfad-Eintrag!")
                continue

            needs_norm = self._check_needs_normalization(path, w, h, fps)
            if needs_norm:
                if cb:
                    pct = 10 + int(40 * (i / total))
                    cb(f"Normalisiere Clip {i + 1}/{total}...", pct)

                temp_name = f"norm_{i}_{int(time.time())}.mp4"
                temp_path = self.temp_dir / temp_name
                self._transcode_clip(path, temp_path, w, h, fps, cancel_callback)

                new_clip = clip.copy()
                new_clip["clip_path"] = str(temp_path)
                new_clip["file_path"] = str(temp_path)
                new_clip["is_temp"] = True
                normalized.append(new_clip)
            else:
                normalized.append(clip)

        return normalized

    def _check_needs_normalization(self, path: str, tw: int, th: int, tfps: float) -> bool:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json", path
        ]
        try:
            res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            data = json.loads(res)
            stream = data["streams"][0]
            width = int(stream["width"])
            height = int(stream["height"])
            rate_str = stream.get("r_frame_rate", "30/1")
            num, den = map(int, rate_str.split("/"))
            fps = float(num) / float(den) if den != 0 else 0.0
            if abs(fps - tfps) >= 0.1 or width != tw or height != th:
                logger.info(f"Mismatch: {Path(path).name}: {width}x{height}@{fps:.2f}fps")
                return True
            return False
        except Exception as e:
            logger.warning(f"FFprobe check failed: {e}")
            return True

    def _transcode_clip(
        self,
        input_path: str,
        output_path: Path,
        w: int,
        h: int,
        fps: float,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ):
        # BUG-026 Fix: fps als float formatiert (z.B. 23.976 → "23.976")
        vf_filter = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps:.3f}"
        encoder = RenderService._working_encoder or "libx264"

        if encoder == "hevc_amf":
            enc_args = ["-c:v", "hevc_amf", "-quality", "balanced", "-b:v", "12M"]
        elif encoder == "h264_amf":
            enc_args = ["-c:v", "h264_amf", "-quality", "balanced", "-b:v", "12M"]
        elif encoder == "h264_mf":
            enc_args = ["-c:v", "h264_mf", "-b:v", "10M"]
        elif encoder == "libx265":
            enc_args = ["-c:v", "libx265", "-preset", "fast", "-crf", "24", "-tag:v", "hvc1"]
        else:
            enc_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf_filter,
            *enc_args,
            "-an", str(output_path)
        ]

        process = None
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                bufsize=1,
            )
            stderr_lines: list[str] = []
            while process.poll() is None:
                if cancel_callback and cancel_callback():
                    process.kill()
                    process.wait(timeout=5)
                    raise RenderCancelledError("Rendering cancelled during clip normalization")
                if process.stderr is not None:
                    line = process.stderr.readline()
                    if line:
                        stderr_lines.append(line)
                        continue
                time.sleep(0.1)

            if process.stderr is not None:
                stderr_lines.extend(process.stderr.readlines())
            stderr_text = "".join(stderr_lines)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, stderr=stderr_text)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"Encoder {encoder} hat leere Datei erstellt")
        except RenderCancelledError:
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Transcode fehlgeschlagen mit {encoder}: {e}")
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise RuntimeError(f"Transcode fehlgeschlagen: {input_path}")

    def _generate_concat_file(self, timeline: List[Dict], list_path: Path):
        with open(list_path, "w", encoding="utf-8") as f:
            for clip in timeline:
                in_pt = clip.get("in_point") if clip.get("in_point") is not None else clip.get("in", 0.0)
                out_pt = clip.get("out_point") if clip.get("out_point") is not None else clip.get("out", in_pt + 2.0)
                p = _get_clip_path_str(clip)
                if not p:
                    continue
                p_str = str(Path(p).absolute()).replace("\\", "/")
                p_str = p_str.replace("'", "'\\''")
                f.write(f"file '{p_str}'\n")
                f.write(f"inpoint {in_pt:.3f}\n")
                f.write(f"outpoint {out_pt:.3f}\n")

    def _run_ffmpeg_render(
        self, list_path: Path, audio_path: str, output_path: Path,
        bitrate: str, preset: str, audio_offset: float,
        total_duration: float,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ):
        """Finaler Render mit Echtzeit-Progress."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-segment_time_metadata", "1",
            "-i", str(list_path)
        ]

        if audio_offset > 0:
            cmd.extend(["-ss", f"{audio_offset:.3f}", "-i", audio_path])
        else:
            cmd.extend(["-i", audio_path])

        cmd.extend(["-map", "0:v", "-map", "1:a"])

        encoder = RenderService._working_encoder or "libx264"
        if encoder == "hevc_amf":
            cmd.extend(["-c:v", "hevc_amf", "-quality", preset, "-b:v", bitrate])
        elif encoder == "h264_amf":
            cmd.extend(["-c:v", "h264_amf", "-quality", preset, "-b:v", bitrate])
        elif encoder == "h264_mf":
            cmd.extend(["-c:v", "h264_mf", "-b:v", "10M"])
        elif encoder == "libx265":
            cmd.extend(["-c:v", "libx265", "-preset", "fast", "-crf", "22", "-tag:v", "hvc1"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])

        logger.info(f"Final Render Encoder: {encoder}")

        cmd.extend([
            "-c:a", "aac", "-b:a", "320k",
            "-movflags", "+faststart",
            "-stats_period", "0.5",
        ])

        audio_dur = self._get_audio_duration(audio_path)
        # Render-Dauer: kürzere von Audio und Timeline (nicht gesamte Audio bei kurzer Timeline)
        render_dur = total_duration
        if audio_dur and audio_dur > 0:
            render_dur = min(audio_dur, total_duration) if total_duration > 0 else audio_dur
        if render_dur and render_dur > 0:
            cmd.extend(["-t", f"{render_dur:.3f}"])
            total_duration = render_dur

        cmd.append(str(output_path))

        # Windows: Konsole verstecken
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, startupinfo=startupinfo, bufsize=1
        )

        try:
            self._parse_ffmpeg_progress(process, total_duration, progress_callback, cancel_callback)
        finally:
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

    def _parse_ffmpeg_progress(
        self, process: subprocess.Popen, total_duration: float,
        progress_callback: Optional[Callable],
        cancel_callback: Optional[Callable[[], bool]] = None,
    ):
        """Liest FFmpeg stderr und verfolgt Fortschritt."""
        stderr_queue: queue.Queue = queue.Queue()
        stderr_lines: list = []

        def enqueue_stderr(pipe, q, lines_list):
            try:
                for line in iter(pipe.readline, ""):
                    q.put(line)
                    lines_list.append(line)
            except Exception:
                pass

        stderr_thread = threading.Thread(
            target=enqueue_stderr,
            args=(process.stderr, stderr_queue, stderr_lines)
        )
        stderr_thread.daemon = True
        stderr_thread.start()

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")
        last_progress = 60

        while process.poll() is None:
            if cancel_callback and cancel_callback():
                process.kill()
                process.wait(timeout=5)
                raise RenderCancelledError("Rendering cancelled during ffmpeg encode")
            try:
                line = stderr_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            match = time_pattern.search(line.strip())
            if match:
                try:
                    h, m, s = match.groups()
                    time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    if total_duration > 0:
                        render_pct = min(time_sec / total_duration, 1.0)
                        overall_pct = 60 + int(38 * render_pct)
                        if overall_pct > last_progress and progress_callback:
                            last_progress = overall_pct
                            progress_callback(
                                f"Rendering: {self._format_time(time_sec)} / {self._format_time(total_duration)}",
                                overall_pct
                            )
                except (ValueError, IndexError):
                    pass

        try:
            process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise RuntimeError("FFmpeg Finalisierung Timeout")

        stderr = "".join(stderr_lines)
        if process.returncode != 0:
            logger.error(f"FFmpeg stderr: {stderr}")
            raise RuntimeError(f"FFmpeg Error (Code {process.returncode}): {stderr[:500]}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", audio_path
        ]
        try:
            res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            return float(json.loads(res)["format"]["duration"])
        except Exception:
            return None

    def _cleanup_temp(self, normalized_clips: List[Dict]):
        for clip in normalized_clips:
            if clip.get("is_temp", False):
                try:
                    os.remove(clip["clip_path"])
                except Exception:
                    pass
        try:
            (self.temp_dir / "concat_list.txt").unlink(missing_ok=True)
        except Exception:
            pass
