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

import inspect
import json
import os
import re
import subprocess
import threading
import time
import queue
import uuid
from pathlib import Path
from typing import Any, List, Dict, Optional, Callable


class RenderCancelledError(RuntimeError):
    """Raised when a render operation is cancelled cooperatively."""
    pass
import logging

# AP2.1 (Audit 2026-06-10): bare "ffmpeg"/"ffprobe" schlugen fehl, wenn FFmpeg
# nur als Bundle in tools/ffmpeg/bin liegt (PATH-unabhängige Auflösung via
# ConfigManager -> PATH -> tools/, wie encoder_utils sie bereits nutzt).
from pb_studio.video.encoder_utils import _get_ffmpeg_path, _get_ffprobe_path

logger = logging.getLogger(__name__)


def _get_clip_path_str(clip: dict) -> Optional[str]:
    """Extrahiert den Clip-Pfad als String (Top-Level und metadata)."""
    for key in ("clip_path", "file_path", "path", "video_path"):
        val = clip.get(key)
        if val:
            if Path(val).is_file():
                return str(val)
    # Auch in metadata suchen (Pacing-Engine speichert Pfade dort)
    meta = clip.get("metadata", {})
    if meta:
        for key in ("file_path", "clip_path", "path", "video_path"):
            val = meta.get(key)
            if val:
                if Path(val).is_file():
                    return str(val)
    return None


class RenderService:
    """Timeline-Rendering Service mit AMD AMF Hardware-Encoding."""

    _AMF_ENCODERS = frozenset({"h264_amf", "hevc_amf", "av1_amf"})
    _active_processes: set[subprocess.Popen] = set()
    _active_processes_lock: threading.Lock = threading.Lock()
    _working_encoder: Optional[str] = None
    _working_encoder_checked_at: Optional[float] = None
    # Audit-Fix 2026-07-10 (Sweep-Finding EXPORT-8): war ein reiner Prozess-
    # Lifetime-Cache ohne jede Invalidierung — Treiber-Update/GPU-Handoff
    # waehrend der Backend-Session blieb bis zum Neustart unsichtbar.
    _ENCODER_CACHE_TTL_SECONDS = 600.0
    _encoder_lock: threading.Lock = threading.Lock()

    def __init__(self, output_dir: str = "exports", encoder_override: Optional[str] = None):
        if encoder_override is not None and encoder_override not in self._AMF_ENCODERS:
            raise ValueError(
                f"Encoder {encoder_override!r} is prohibited; "
                "only AMD AMF hardware encoders are allowed"
            )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.temp_dir = self.output_dir / ".temp_render"
        self.temp_dir.mkdir(exist_ok=True)
        self._encoder_override = encoder_override

    @classmethod
    def _register_process(cls, process: subprocess.Popen) -> None:
        with cls._active_processes_lock:
            cls._active_processes.add(process)

    @classmethod
    def _unregister_process(cls, process: subprocess.Popen) -> None:
        with cls._active_processes_lock:
            cls._active_processes.discard(process)

    @classmethod
    def terminate_active_processes(cls, grace_seconds: float = 1.0) -> int:
        """Stoppt aktive Render-FFmpeg-Prozesse und wartet auf deren Ende."""
        with cls._active_processes_lock:
            processes = list(cls._active_processes)

        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    logger.debug("FFmpeg terminate fehlgeschlagen", exc_info=True)

        deadline = time.monotonic() + max(grace_seconds, 0.0)
        for process in processes:
            try:
                process.wait(timeout=max(deadline - time.monotonic(), 0.0))
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except Exception:
                    logger.debug("FFmpeg kill fehlgeschlagen", exc_info=True)
                try:
                    process.wait(timeout=1.0)
                except Exception:
                    logger.warning("FFmpeg-Prozess konnte nicht beendet werden")
            except Exception:
                logger.warning("FFmpeg-Prozess konnte nicht abgewartet werden")

        return len(processes)

    def _detect_best_encoder(self) -> str:
        """Testet verfügbare AMD-Encoder und gibt den besten zurück."""
        encoders = [
            ("hevc_amf", "AMD GPU H.265 (beste Kompression)"),
            ("av1_amf", "AMD GPU AV1 (modernste Kompression)"),
            ("h264_amf", "AMD GPU H.264"),
        ]

        for enc_name, desc in encoders:
            if self.probe_encoder(enc_name):
                logger.info(f"Encoder-Test OK: {enc_name} ({desc})")
                return enc_name

        raise RuntimeError(
            "No functional AMD AMF encoder available; software encoding is disabled"
        )

    @classmethod
    def probe_encoder(cls, encoder: str) -> bool:
        """Führt einen echten Test-Encode für einen AMF-Encoder aus."""
        if encoder not in cls._AMF_ENCODERS:
            raise ValueError(f"Encoder {encoder!r} is not an allowed AMD AMF encoder")
        test_cmd = [
            _get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.5",
            "-frames:v", "1", "-pix_fmt", "yuv420p",
            "-c:v", encoder,
            "-f", "null", "-",
        ]
        try:
            result = subprocess.run(
                test_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False

    def _active_encoder(self) -> str:
        if self._encoder_override is not None:
            return self._encoder_override
        with RenderService._encoder_lock:
            cache_stale = (
                RenderService._working_encoder is None
                or RenderService._working_encoder_checked_at is None
                or (time.monotonic() - RenderService._working_encoder_checked_at)
                >= RenderService._ENCODER_CACHE_TTL_SECONDS
            )
            if cache_stale:
                RenderService._working_encoder = self._detect_best_encoder()
                RenderService._working_encoder_checked_at = time.monotonic()
                logger.info(f"Encoder erkannt und gecacht: {RenderService._working_encoder}")
            encoder = RenderService._working_encoder
        if encoder not in self._AMF_ENCODERS:
            raise RuntimeError("No valid AMD AMF encoder is active")
        return encoder

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
        progress_callback: Optional[Callable[..., None]] = None,
        audio_offset: float = 0.0,
        cancel_callback: Optional[Callable[[], bool]] = None,
        include_audio: bool = True,
    ) -> str:
        """Hauptfunktion für Timeline-Rendering."""
        final_output = self.output_dir / output_filename
        staging_output = final_output.with_name(
            f".{final_output.stem}.{uuid.uuid4().hex}.partial{final_output.suffix}"
        )
        self._validate_timeline_clips(timeline)
        # R19/LOW-019-3: Cache audio_dur here — _run_ffmpeg_render reuses it
        # to avoid a second ffprobe subprocess on the same audio file.
        audio_dur = self._get_audio_duration(audio_path) if include_audio else None
        total_duration = audio_dur if audio_dur and audio_dur > 0 else self._calculate_timeline_duration(timeline)
        total_frames = max(int(round(max(total_duration, 0.0) * max(target_fps, 0.0))), 0)
        render_start = time.monotonic()

        # R19/LOW-019-1: Pre-init so finally can always call _cleanup_temp safely,
        # even if an exception occurs before _normalize_clips assigns the variable.
        normalized_clips: List[Dict] = []
        try:
            self._emit_progress(
                progress_callback,
                "Prüfe Quellmaterial...",
                10,
                total_frames=total_frames,
                current_frame=0,
                fps=0.0,
                elapsed_seconds=0.0,
                eta_seconds=0.0,
            )

            normalized_clips = self._normalize_clips(
                timeline, target_width, target_height, target_fps, progress_callback, cancel_callback
            )

            self._emit_progress(
                progress_callback,
                "Erstelle Schnittliste...",
                55,
                total_frames=total_frames,
                current_frame=0,
                fps=0.0,
                elapsed_seconds=max(time.monotonic() - render_start, 0.0),
                eta_seconds=0.0,
            )
            concat_list_path = self.temp_dir / "concat_list.txt"
            self._generate_concat_file(normalized_clips, concat_list_path)

            self._emit_progress(
                progress_callback,
                "Starte Rendering...",
                58,
                total_frames=total_frames,
                current_frame=0,
                fps=0.0,
                elapsed_seconds=max(time.monotonic() - render_start, 0.0),
                eta_seconds=0.0,
            )

            last_telemetry = self._run_ffmpeg_render(
                concat_list_path, audio_path if include_audio else None, staging_output,
                bitrate, preset, audio_offset, total_duration, target_fps, progress_callback, cancel_callback, render_start,
                audio_dur=audio_dur,
                include_audio=include_audio,
            )
            if not staging_output.exists() or staging_output.stat().st_size == 0:
                raise RuntimeError("FFmpeg hat keine vollständige Render-Ausgabe erzeugt")
            os.replace(staging_output, final_output)

            elapsed = max(time.monotonic() - render_start, 0.0)
            final_fps = last_telemetry.get("fps", 0.0) if last_telemetry else 0.0
            if final_fps <= 0 and elapsed > 0:
                final_fps = total_frames / elapsed

            self._emit_progress(
                progress_callback,
                "Fertig!",
                100,
                total_frames=total_frames,
                current_frame=total_frames,
                fps=final_fps,
                elapsed_seconds=elapsed,
                eta_seconds=0.0,
            )
            logger.info(f"Rendering erfolgreich: {final_output}")
            return str(final_output)

        except Exception as e:
            logger.error(f"Render Error: {e}", exc_info=True)
            raise
        finally:
            staging_output.unlink(missing_ok=True)
            self._cleanup_temp(normalized_clips)

    def _calculate_timeline_duration(self, timeline: List[Dict]) -> float:
        total = 0.0
        for clip in timeline:
            in_pt = clip.get("in_point") or clip.get("in", 0.0)
            out_pt = clip.get("out_point") or clip.get("out", in_pt + 2.0)
            total += out_pt - in_pt
        return max(total, 1.0)

    @staticmethod
    def _validate_timeline_clips(timeline: List[Dict]) -> None:
        """Bricht vor Encoder-/Transcode-Arbeit ab, wenn ein Clip fehlt."""
        missing = [index for index, clip in enumerate(timeline) if not _get_clip_path_str(clip)]
        if missing:
            indexes = ", ".join(str(index) for index in missing)
            raise FileNotFoundError(f"Timeline-Clip(s) fehlen oder sind nicht lesbar: {indexes}")

    def _normalize_clips(
        self, timeline: List[Dict], w: int, h: int, fps: float,
        cb: Optional[Callable], cancel_callback: Optional[Callable[[], bool]] = None
    ) -> List[Dict]:
        """Prüft Clips und transkodiert bei Bedarf in einheitliches Format."""
        normalized = []
        normalized_cache = {}  # Cache für bereits transkodierte Clips: input_path -> new_clip
        total = len(timeline)

        # Ermittle Ziel-Codec basierend auf dem aktiven Encoder
        primary_enc = self._active_encoder()
        if "hevc" in primary_enc:
            target_codec = "hevc"
        elif "av1" in primary_enc:
            target_codec = "av1"
        else:
            target_codec = "h264"

        for i, clip in enumerate(timeline):
            if cancel_callback and cancel_callback():
                raise RenderCancelledError("Rendering cancelled during clip normalization")
            path = _get_clip_path_str(clip)
            if not path:
                raise FileNotFoundError(
                    f"Timeline-Clip {i} fehlt oder ist nicht mehr lesbar"
                )

            # Cache-Lookup: Wenn derselbe Clip bereits normalisiert wurde, Pfad wiederverwenden
            if path in normalized_cache:
                cached_clip = normalized_cache[path]
                new_clip = clip.copy()
                new_clip["clip_path"] = cached_clip["clip_path"]
                new_clip["file_path"] = cached_clip["file_path"]
                new_clip["is_temp"] = cached_clip["is_temp"]
                normalized.append(new_clip)
                continue

            needs_norm = self._check_needs_normalization(path, w, h, fps, target_codec)
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
                normalized_cache[path] = new_clip
                normalized.append(new_clip)
            else:
                normalized.append(clip)

        return normalized

    def _check_needs_normalization(self, path: str, tw: int, th: int, tfps: float, target_codec: str) -> bool:
        cmd = [
            _get_ffprobe_path(), "-v", "error",
            "-show_streams",
            "-of", "json", path
        ]
        try:
            res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            data = json.loads(res)
            
            # Suche Video-Stream und zaehle Audio-Streams
            video_stream = None
            audio_streams_count = 0
            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video" and video_stream is None:
                    video_stream = stream
                elif codec_type == "audio":
                    audio_streams_count += 1
            
            if not video_stream:
                logger.warning(f"Kein Video-Stream in {Path(path).name} gefunden!")
                return True
                
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            codec_name = video_stream.get("codec_name", "")
            pix_fmt = video_stream.get("pix_fmt", "")
            
            rate_str = video_stream.get("r_frame_rate", "30/1")
            num, den = map(int, rate_str.split("/"))
            fps = float(num) / float(den) if den != 0 else 0.0
            
            # Normalisierung erforderlich, wenn Auflösung/FPS nicht übereinstimmen,
            # der Codec nicht mit dem Render-Codec übereinstimmt, Audio-Streams vorhanden sind
            # oder das Pixel-Format nicht dem Standard yuv420p entspricht.
            if width != tw or height != th or abs(fps - tfps) >= 0.1:
                logger.info(f"Mismatch Resolution/FPS: {Path(path).name}: {width}x{height}@{fps:.2f}fps, erwartet {tw}x{th}@{tfps:.2f}fps")
                return True
                
            if codec_name != target_codec:
                logger.info(f"Mismatch Codec: {Path(path).name} hat {codec_name}, erwartet {target_codec}")
                return True
                
            if audio_streams_count > 0:
                logger.info(f"Mismatch Audio: {Path(path).name} enthält {audio_streams_count} Audio-Stream(s), normalisiere zum Entfernen")
                return True
                
            if pix_fmt != "yuv420p" and pix_fmt != "yuv420p10le":
                logger.info(f"Mismatch PixFmt: {Path(path).name} hat {pix_fmt}, normalisiere zu yuv420p")
                return True

            # AP2.2 (Audit 2026-06-10): SAR-Mismatch fuehrt im Concat-Demuxer zu
            # Stream-Parameter-Wechseln (anamorphe Clips). "0:1"/"N/A" = unbekannt -> ok.
            sar = video_stream.get("sample_aspect_ratio", "1:1")
            if sar not in ("1:1", "0:1", "N/A", ""):
                logger.info(f"Mismatch SAR: {Path(path).name} hat {sar}, normalisiere zu 1:1")
                return True

            return False
        except Exception as e:
            logger.warning(f"FFprobe check failed: {e}")
            return True

    # B4-Fix (2026-05-19): Per-Encoder ffmpeg-arg-Builder, damit
    # `_transcode_clip` mit jedem Encoder retry-fallback aufrufbar ist.
    @staticmethod
    def _encoder_args(encoder: str) -> list[str]:
        if encoder == "hevc_amf":
            return ["-c:v", "hevc_amf", "-rc", "cbr", "-quality", "balanced", "-b:v", "12M"]
        if encoder == "h264_amf":
            return ["-c:v", "h264_amf", "-rc", "cbr", "-quality", "balanced", "-b:v", "12M"]
        if encoder == "av1_amf":
            return ["-c:v", "av1_amf", "-quality", "balanced", "-b:v", "12M"]
        raise ValueError(f"Encoder {encoder!r} is not an allowed AMD AMF encoder")

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
        primary = self._active_encoder()

        chain = [primary]

        last_error: Optional[Exception] = None
        for attempt_idx, encoder in enumerate(chain):
            enc_args = self._encoder_args(encoder)
            cmd = [
                _get_ffmpeg_path(), "-y", "-i", input_path,
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
                self._register_process(process)
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
                return
            except RenderCancelledError:
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as e:
                last_error = e
                logger.warning(
                    f"Transcode fehlgeschlagen mit {encoder} "
                    f"(attempt {attempt_idx + 1}/{len(chain)}): {e}"
                )
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                # naechster Encoder in Chain
                continue
            finally:
                if process is not None and process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception:
                        pass
                if process is not None:
                    for pipe in (process.stdout, process.stderr):
                        if pipe is not None:
                            try:
                                pipe.close()
                            except Exception:
                                pass
                if process is not None:
                    self._unregister_process(process)

        # Alle Encoder fehlgeschlagen — gibt es kein last_error, war chain leer
        logger.error(
            f"Alle {len(chain)} Encoder fehlgeschlagen fuer {Path(input_path).name}: "
            f"chain={chain}, last={last_error}"
        )
        raise RuntimeError(f"Transcode fehlgeschlagen: {input_path}")

    def _generate_concat_file(self, timeline: List[Dict], list_path: Path):
        with open(list_path, "w", encoding="utf-8") as f:
            for clip in timeline:
                in_pt = clip.get("in_point") if clip.get("in_point") is not None else clip.get("in", 0.0)
                out_pt = clip.get("out_point") if clip.get("out_point") is not None else clip.get("out", in_pt + 2.0)
                p = _get_clip_path_str(clip)
                if not p:
                    raise FileNotFoundError(
                        "Timeline-Clip ist vor Erstellung der Concat-Liste verschwunden"
                    )
                p_str = str(Path(p).absolute()).replace("\\", "/")
                # FFmpeg concat protocol: single quotes required (double quotes treated as literal chars)
                p_escaped = p_str.replace("'", "'\\''")
                f.write(f"file '{p_escaped}'\n")
                f.write(f"inpoint {in_pt:.3f}\n")
                f.write(f"outpoint {out_pt:.3f}\n")

    def _build_render_cmd(
        self, list_path: Path, audio_path: Optional[str], output_path: Path,
        bitrate: str, preset: str, audio_offset: float,
        total_duration: float, encoder: str,
        audio_dur: Optional[float] = None,
        include_audio: bool = True,
    ) -> tuple[list[str], float]:
        """Baut FFmpeg-Kommando fuer einen bestimmten Encoder. Gibt (cmd, effective_duration) zurueck."""
        cmd = [
            _get_ffmpeg_path(), "-y",
            "-f", "concat", "-safe", "0",
            "-segment_time_metadata", "1",
            "-i", str(list_path)
        ]

        if include_audio:
            if not audio_path:
                raise ValueError("Audio-Pfad fehlt trotz include_audio=True")
            if audio_offset > 0:
                cmd.extend(["-ss", f"{audio_offset:.3f}", "-i", audio_path])
            else:
                cmd.extend(["-i", audio_path])
            cmd.extend(["-map", "0:v", "-map", "1:a"])
        else:
            cmd.extend(["-map", "0:v"])
        cmd.extend(["-vf", "select=concatdec_select,setpts=N/FR/TB"])

        if encoder == "hevc_amf":
            cmd.extend(["-c:v", "hevc_amf", "-rc", "cbr", "-quality", preset, "-b:v", bitrate])
        elif encoder == "h264_amf":
            cmd.extend(["-c:v", "h264_amf", "-rc", "cbr", "-quality", preset, "-b:v", bitrate])
        elif encoder == "av1_amf":
            cmd.extend(["-c:v", "av1_amf", "-quality", preset, "-b:v", bitrate])
        else:
            raise ValueError(f"Encoder {encoder!r} is not an allowed AMD AMF encoder")

        if include_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "320k"])
        else:
            cmd.append("-an")
        cmd.extend(["-movflags", "+faststart", "-stats_period", "0.5"])

        render_dur = total_duration
        if audio_dur and audio_dur > 0:
            render_dur = min(audio_dur, total_duration) if total_duration > 0 else audio_dur
        if render_dur and render_dur > 0:
            cmd.extend(["-t", f"{render_dur:.3f}"])
            total_duration = render_dur

        cmd.append(str(output_path))
        return cmd, total_duration

    def _run_ffmpeg_render(
        self, list_path: Path, audio_path: Optional[str], output_path: Path,
        bitrate: str, preset: str, audio_offset: float,
        total_duration: float,
        target_fps: float,
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
        render_start_time: Optional[float] = None,
        audio_dur: Optional[float] = None,
        include_audio: bool = True,
    ) -> dict[str, Any]:
        """Finaler Render mit Echtzeit-Progress über AMD AMF."""
        # BUG-070 FIX: Guard gegen Path(None)
        if include_audio and audio_path and not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio-Datei nicht gefunden: {audio_path!r}")

        if include_audio and audio_dur is None:
            audio_dur = self._get_audio_duration(audio_path)

        primary = self._active_encoder()

        chain = [primary]

        last_error: Optional[Exception] = None
        for attempt_idx, encoder in enumerate(chain):
            logger.info(f"Final Render Encoder: {encoder} (attempt {attempt_idx + 1}/{len(chain)})")

            cmd, effective_duration = self._build_render_cmd(
                list_path, audio_path, output_path,
                bitrate, preset, audio_offset, total_duration, encoder,
                audio_dur=audio_dur,
                include_audio=include_audio,
            )

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, startupinfo=startupinfo, bufsize=1
            )
            self._register_process(process)

            try:
                result = self._parse_ffmpeg_progress(
                    process,
                    effective_duration,
                    target_fps,
                    progress_callback,
                    cancel_callback,
                    render_start_time=render_start_time,
                )
                return result
            except RenderCancelledError:
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                last_error = e
                logger.warning(
                    f"Final-Render fehlgeschlagen mit {encoder} "
                    f"(attempt {attempt_idx + 1}/{len(chain)}): {e}"
                )
                try:
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                # naechster Encoder in Chain
                continue
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
                self._unregister_process(process)

        # Alle Encoder fehlgeschlagen
        raise RuntimeError(
            f"Final-Render fehlgeschlagen mit allen Encodern {chain}: {last_error}"
        )

    def _parse_ffmpeg_progress(
        self,
        process: subprocess.Popen,
        total_duration: float,
        target_fps: float,
        progress_callback: Optional[Callable[..., None]],
        cancel_callback: Optional[Callable[[], bool]] = None,
        render_start_time: Optional[float] = None,
    ) -> dict[str, Any]:
        """Liest FFmpeg stderr und verfolgt Fortschritt."""
        stderr_queue: queue.Queue = queue.Queue()
        stderr_lines: list = []

        def enqueue_stderr(pipe, q, lines_list):
            # T4.2 (2026-05-23): Blockweises readline() statt pipe.read(1)
            # um CPU-Last drastisch zu reduzieren.
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
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
        frame_pattern = re.compile(r"frame=\s*(\d+)")
        fps_pattern = re.compile(r"fps=\s*([0-9]+(?:\.[0-9]+)?)")
        total_frames = max(int(round(max(total_duration, 0.0) * max(target_fps, 0.0))), 0)
        last_progress = 60
        last_publish_at = 0.0
        last_frame = 0
        last_fps = 0.0
        last_elapsed = 0.0

        while True:
            # Check if process is still running
            running = process.poll() is None
            
            try:
                # Use shorter timeout when not running to drain quickly
                line = stderr_queue.get(timeout=0.1 if running else 0.005)
            except queue.Empty:
                if not running:
                    break
                if cancel_callback and cancel_callback():
                    process.kill()
                    process.wait(timeout=5)
                    raise RenderCancelledError("Rendering cancelled during ffmpeg encode")
                continue

            stripped = line.strip()
            match = time_pattern.search(stripped)
            if match:
                try:
                    h, m, s = match.groups()
                    time_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    frame_match = frame_pattern.search(stripped)
                    parsed_frame = int(frame_match.group(1)) if frame_match else 0
                    fps_match = fps_pattern.search(stripped)
                    parsed_fps = float(fps_match.group(1)) if fps_match else 0.0
                    current_frame = parsed_frame if parsed_frame > 0 else int(round(time_sec * max(target_fps, 0.0)))
                    if total_frames > 0:
                        current_frame = min(current_frame, total_frames)
                    current_frame = max(current_frame, last_frame)
                    last_frame = current_frame

                    elapsed_seconds = max(
                        (time.monotonic() - render_start_time) if render_start_time is not None else time_sec,
                        0.0,
                    )
                    last_elapsed = elapsed_seconds
                    
                    effective_fps = parsed_fps
                    if effective_fps <= 0.0 and elapsed_seconds > 0 and current_frame > 0:
                        effective_fps = current_frame / elapsed_seconds
                    last_fps = effective_fps

                    remaining_frames = max(total_frames - current_frame, 0) if total_frames > 0 else 0
                    eta_seconds = (remaining_frames / effective_fps) if effective_fps > 0.0 else 0.0

                    if total_duration > 0:
                        render_pct = min(time_sec / total_duration, 1.0)
                        overall_pct = 60 + int(38 * render_pct)
                        now = time.monotonic()
                        should_publish = (
                            overall_pct > last_progress
                            or now - last_publish_at >= 1.0
                            or current_frame >= total_frames > 0
                        )
                        if should_publish:
                            last_progress = max(last_progress, overall_pct)
                            last_publish_at = now
                            self._emit_progress(
                                progress_callback,
                                f"Rendering: {self._format_time(time_sec)} / {self._format_time(total_duration)}",
                                overall_pct,
                                current_frame=current_frame,
                                total_frames=total_frames,
                                fps=effective_fps,
                                elapsed_seconds=elapsed_seconds,
                                eta_seconds=max(eta_seconds, 0.0),
                            )
                except (ValueError, IndexError):
                    pass

        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError("FFmpeg Finalisierung Timeout")
        finally:
            stderr_thread.join(timeout=5)

        stderr = "".join(stderr_lines)
        if process.returncode != 0:
            logger.error(f"FFmpeg stderr: {stderr}")
            return self._handle_ffmpeg_error(process.returncode, stderr)
        
        return {
            "fps": last_fps,
            "current_frame": last_frame,
            "total_frames": total_frames,
            "elapsed_seconds": last_elapsed,
        }

    def _handle_ffmpeg_error(self, returncode: int, stderr: str) -> dict[str, Any]:
        """Extrahiert Fehlermeldungen aus FFmpeg stderr."""
        # Wichtige Fehlermeldungen suchen
        error_msg = "Unbekannter FFmpeg-Fehler"
        if "AMF_ERROR_ALLOC_FAILED" in stderr:
            error_msg = "AMD AMF: VRAM-Speichermangel"
        elif "AMF_ERROR_INVALID_ARG" in stderr:
            error_msg = "AMD AMF: Ungültige Parameter (Codec-Mismatch?)"
        elif "No such file or directory" in stderr:
            error_msg = "Datei nicht gefunden"
        elif "Permission denied" in stderr:
            error_msg = "Zugriff verweigert"
        
        err_tail = stderr.strip()[-1000:] if len(stderr) > 1000 else stderr.strip()
        full_msg = f"FFmpeg Error (Code {returncode}): {error_msg}\n\nStderr Tail:\n{err_tail}"
        raise RuntimeError(full_msg)

    @staticmethod
    def _format_time(seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    @staticmethod
    def _emit_progress(
        progress_callback: Optional[Callable[..., None]],
        message: str,
        percent: float,
        **telemetry: Any,
    ) -> None:
        if progress_callback is None:
            return
        try:
            signature = inspect.signature(progress_callback)
            supports_varargs = any(
                param.kind == inspect.Parameter.VAR_POSITIONAL
                for param in signature.parameters.values()
            )
            if supports_varargs or len(signature.parameters) >= 3:
                progress_callback(message, percent, telemetry)
            else:
                progress_callback(message, percent)
        except (TypeError, ValueError):
            progress_callback(message, percent)

    def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        cmd = [
            _get_ffprobe_path(), "-v", "error",
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
                Path(clip["clip_path"]).unlink(missing_ok=True)
        try:
            (self.temp_dir / "concat_list.txt").unlink(missing_ok=True)
        except Exception:
            pass
