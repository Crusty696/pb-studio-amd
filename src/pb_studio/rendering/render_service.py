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
import hashlib
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
    _FRAME_ADDRESSABILITY_PROBE_TIMEOUT_SECONDS = 300.0
    _ARTIFACT_PROBE_TIMEOUT_SECONDS = 60.0
    _ARTIFACT_DECODE_TIMEOUT_FLOOR_SECONDS = 300.0
    _ARTIFACT_FRAME_TOLERANCE = 1
    _ARTIFACT_MIN_DURATION_TOLERANCE_SECONDS = 0.05
    _AAC_PRE_ENCODE_GAIN_DB = -2.0
    _AAC_TRUE_PEAK_LIMIT_DBTP = -1.0
    _END_SILENCE_THRESHOLD_DB = -60
    _END_SILENCE_MIN_SECONDS = 1.0
    _END_SILENCE_TOLERANCE_SECONDS = 0.05
    _encoder_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        output_dir: str = "exports",
        encoder_override: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        if encoder_override is not None and encoder_override not in self._AMF_ENCODERS:
            raise ValueError(
                f"Encoder {encoder_override!r} is prohibited; "
                "only AMD AMF hardware encoders are allowed"
            )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        raw_job_token = job_id or uuid.uuid4().hex
        self.job_token = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_job_token).strip("._-")
        if not self.job_token:
            self.job_token = uuid.uuid4().hex
        self.job_token = self.job_token[:64]
        self.temp_root = self.output_dir / ".temp_render"
        self.run_id = ""
        self.temp_dir = self.temp_root / self.job_token
        self._encoder_override = encoder_override

    @classmethod
    def _register_process(cls, process: subprocess.Popen) -> None:
        with cls._active_processes_lock:
            cls._active_processes.add(process)

    @classmethod
    def _unregister_process(cls, process: subprocess.Popen) -> None:
        with cls._active_processes_lock:
            cls._active_processes.discard(process)

    def _run_capture_process(
        self,
        cmd: list[str],
        *,
        timeout: float,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Fuehrt einen job-eigenen Prozess abbrechbar und registriert aus."""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
        )
        self._register_process(process)
        deadline = time.monotonic() + max(timeout, 0.0)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    stdout, stderr = process.communicate()
                    raise subprocess.TimeoutExpired(
                        cmd,
                        timeout,
                        output=stdout,
                        stderr=stderr,
                    )
                try:
                    stdout, stderr = process.communicate(timeout=min(remaining, 0.25))
                    break
                except subprocess.TimeoutExpired:
                    if cancel_callback and cancel_callback():
                        process.kill()
                        process.communicate()
                        raise RenderCancelledError(
                            f"Rendering cancelled during process: {Path(cmd[0]).name}"
                        )
            return subprocess.CompletedProcess(
                cmd,
                process.returncode,
                stdout,
                stderr,
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            self._unregister_process(process)
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()

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
        self._validate_timeline_clips(timeline)
        # R19/LOW-019-3: Cache audio_dur here — _run_ffmpeg_render reuses it
        # to avoid a second ffprobe subprocess on the same audio file.
        audio_dur = (
            self._get_audio_duration(audio_path, cancel_callback)
            if include_audio
            else None
        )
        total_duration = audio_dur if audio_dur and audio_dur > 0 else self._calculate_timeline_duration(timeline)
        expected_end_silence = (
            self._measure_trailing_silence_seconds(
                Path(audio_path),
                expected_duration=total_duration,
                input_offset=audio_offset,
                cancel_callback=cancel_callback,
            )
            if include_audio
            else None
        )
        total_frames = max(int(round(max(total_duration, 0.0) * max(target_fps, 0.0))), 0)
        render_start = time.monotonic()

        self.run_id = uuid.uuid4().hex
        self.temp_dir = self.temp_root / self.job_token / self.run_id
        self.temp_dir.mkdir(exist_ok=False, parents=True)
        final_output = self.output_dir / output_filename
        staging_output = final_output.with_name(
            f".{final_output.stem}.{self.job_token}.{self.run_id}.partial{final_output.suffix}"
        )

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
            try:
                artifact_metrics = self._validate_render_artifact(
                    staging_output,
                    expected_duration=total_duration,
                    target_fps=target_fps,
                    target_width=target_width,
                    target_height=target_height,
                    include_audio=include_audio,
                    expected_end_silence=expected_end_silence,
                    cancel_callback=cancel_callback,
                )
            except Exception as exc:
                self._persist_validation_evidence(error=exc)
                raise
            self._persist_validation_evidence(metrics=artifact_metrics)
            logger.info("Render-Artefakt validiert: %s", artifact_metrics)
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
            validation_path = (
                self.output_dir
                / ".render_evidence"
                / self.job_token
                / self.run_id
                / "validation.json"
            )
            if self.run_id and not validation_path.is_file():
                self._persist_validation_evidence(error=e)
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

            needs_norm = self._check_needs_normalization(
                path,
                w,
                h,
                fps,
                target_codec,
                cancel_callback,
            )
            if not needs_norm:
                needs_norm = not self._is_frame_addressable(path, cancel_callback)
            if needs_norm:
                if cb:
                    pct = 10 + int(40 * (i / total))
                    cb(f"Normalisiere Clip {i + 1}/{total}...", pct)

                temp_name = f"norm_{i}.mp4"
                temp_path = self.temp_dir / temp_name
                self._transcode_clip(path, temp_path, w, h, fps, cancel_callback)
                if not self._is_frame_addressable(temp_path, cancel_callback):
                    temp_path.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Normalisierter Clip ist nicht frame-adressierbar: {Path(path).name}"
                    )

                new_clip = clip.copy()
                new_clip["clip_path"] = str(temp_path)
                new_clip["file_path"] = str(temp_path)
                new_clip["is_temp"] = True
                normalized_cache[path] = new_clip
                normalized.append(new_clip)
            else:
                normalized.append(clip)

        return normalized

    def _check_needs_normalization(
        self,
        path: str,
        tw: int,
        th: int,
        tfps: float,
        target_codec: str,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> bool:
        cmd = [
            _get_ffprobe_path(), "-v", "error",
            "-show_streams",
            "-of", "json", path
        ]
        try:
            result = self._run_capture_process(
                cmd,
                timeout=30.0,
                cancel_callback=cancel_callback,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:])
            data = json.loads(result.stdout)
            
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
        except RenderCancelledError:
            raise
        except Exception as e:
            logger.warning(f"FFprobe check failed: {e}")
            return True

    def _is_frame_addressable(
        self,
        path: str | Path,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """True, wenn jedes Videopaket an einer unabhängig dekodierbaren Stelle beginnt."""
        cmd = [
            _get_ffprobe_path(),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_packets",
            "-show_entries", "packet=flags",
            "-of", "csv=p=0",
            str(path),
        ]
        try:
            result = self._run_capture_process(
                cmd,
                timeout=self._FRAME_ADDRESSABILITY_PROBE_TIMEOUT_SECONDS,
                cancel_callback=cancel_callback,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:])
            output = result.stdout
        except RenderCancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Frame-Adressierbarkeitspruefung fehlgeschlagen fuer %s: %s",
                Path(path).name,
                exc,
            )
            return False

        packet_flags = [line.strip() for line in output.splitlines() if line.strip()]
        is_addressable = bool(packet_flags) and all("K" in flags for flags in packet_flags)
        if not is_addressable:
            keyframes = sum("K" in flags for flags in packet_flags)
            logger.info(
                "Long-GOP erkannt: %s (%d/%d keyframe-adressierbare Pakete)",
                Path(path).name,
                keyframes,
                len(packet_flags),
            )
        return is_addressable

    # B4-Fix (2026-05-19): Per-Encoder ffmpeg-arg-Builder, damit
    # `_transcode_clip` mit jedem Encoder retry-fallback aufrufbar ist.
    @staticmethod
    def _encoder_args(encoder: str) -> list[str]:
        if encoder == "hevc_amf":
            return [
                "-c:v", "hevc_amf", "-rc", "cbr", "-quality", "balanced",
                "-b:v", "12M", "-g", "1",
            ]
        if encoder == "h264_amf":
            return [
                "-c:v", "h264_amf", "-rc", "cbr", "-quality", "balanced",
                "-b:v", "12M", "-g", "1",
            ]
        if encoder == "av1_amf":
            return [
                "-c:v", "av1_amf", "-quality", "balanced",
                "-b:v", "12M", "-g", "1",
            ]
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
            cmd.extend([
                "-filter:a", f"volume={self._AAC_PRE_ENCODE_GAIN_DB:.1f}dB",
                "-c:a", "aac",
                "-b:a", "320k",
            ])
        else:
            cmd.append("-an")
        cmd.extend([
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-stats_period", "0.5",
            "-nostats",
        ])

        render_dur = total_duration
        if audio_dur and audio_dur > 0:
            render_dur = min(audio_dur, total_duration) if total_duration > 0 else audio_dur
        if render_dur and render_dur > 0:
            cmd.extend(["-t", f"{render_dur:.3f}"])
            total_duration = render_dur

        cmd.append(str(output_path))
        return cmd, total_duration

    def _validate_render_artifact(
        self,
        artifact_path: Path,
        *,
        expected_duration: float,
        target_fps: float,
        target_width: int,
        target_height: int,
        include_audio: bool,
        expected_end_silence: Optional[float] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> dict[str, Any]:
        """Validiert Streams und dekodiert das vollstaendige Staging-Artefakt."""
        probe_cmd = [
            _get_ffprobe_path(),
            "-v", "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,duration,width,height,sample_rate,channels",
            "-of", "json",
            str(artifact_path),
        ]
        try:
            probe = self._run_capture_process(
                probe_cmd,
                timeout=self._ARTIFACT_PROBE_TIMEOUT_SECONDS,
                cancel_callback=cancel_callback,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Artefakt-Streamprobe hat das Zeitlimit ueberschritten") from exc
        if probe.returncode != 0:
            raise RuntimeError(
                f"Artefakt-Streamprobe fehlgeschlagen: {probe.stderr[-2000:]}"
            )
        try:
            probe_data = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Artefakt-Streamprobe lieferte ungueltiges JSON") from exc

        streams = probe_data.get("streams", [])
        video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        if len(video_streams) != 1:
            raise RuntimeError(
                f"Artefakt braucht genau einen Video-Stream, gefunden: {len(video_streams)}"
            )
        if len(audio_streams) != (1 if include_audio else 0):
            raise RuntimeError(
                "Artefakt-Audiovertrag verletzt: "
                f"include_audio={include_audio}, streams={len(audio_streams)}"
            )

        video_stream = video_streams[0]
        expected_video_codec = {
            "h264_amf": "h264",
            "hevc_amf": "hevc",
            "av1_amf": "av1",
        }[self._active_encoder()]
        if video_stream.get("codec_name") != expected_video_codec:
            raise RuntimeError(
                "Artefakt-Video-Codec verletzt: "
                f"erwartet={expected_video_codec}, ist={video_stream.get('codec_name')}"
            )
        if (
            int(video_stream.get("width", 0) or 0) != target_width
            or int(video_stream.get("height", 0) or 0) != target_height
        ):
            raise RuntimeError(
                "Artefakt-Aufloesung verletzt: "
                f"erwartet={target_width}x{target_height}, "
                f"ist={video_stream.get('width')}x{video_stream.get('height')}"
            )
        if include_audio:
            audio_stream = audio_streams[0]
            if audio_stream.get("codec_name") != "aac":
                raise RuntimeError(
                    f"Artefakt-Audio-Codec verletzt: {audio_stream.get('codec_name')}"
                )
            if (
                int(audio_stream.get("sample_rate", 0) or 0) <= 0
                or int(audio_stream.get("channels", 0) or 0) <= 0
            ):
                raise RuntimeError(
                    "Artefakt-Audio-Stream hat ungueltige Rate oder Kanalzahl"
                )

        duration_tolerance = max(
            self._ARTIFACT_MIN_DURATION_TOLERANCE_SECONDS,
            1.0 / max(target_fps, 1.0),
        )
        format_duration = self._required_duration(
            probe_data.get("format", {}).get("duration"),
            "Container",
        )
        if abs(format_duration - expected_duration) > duration_tolerance:
            raise RuntimeError(
                "Artefakt-Containerdauer verletzt: "
                f"erwartet={expected_duration:.6f}, ist={format_duration:.6f}"
            )

        video_decode = self._decode_artifact_stream(
            artifact_path,
            stream_selector="0:v:0",
            expected_duration=expected_duration,
            cancel_callback=cancel_callback,
        )
        expected_frames = int(round(expected_duration * target_fps))
        decoded_frames = int(video_decode.get("frame", "0") or 0)
        if abs(decoded_frames - expected_frames) > self._ARTIFACT_FRAME_TOLERANCE:
            raise RuntimeError(
                "Artefakt-Framezahl verletzt: "
                f"erwartet={expected_frames}, ist={decoded_frames}"
            )
        video_end = self._progress_end_seconds(video_decode, "Video")
        if abs(video_end - expected_duration) > duration_tolerance:
            raise RuntimeError(
                "Artefakt-Video-End-PTS verletzt: "
                f"erwartet={expected_duration:.6f}, ist={video_end:.6f}"
            )

        audio_end: Optional[float] = None
        true_peak_dbtp: Optional[float] = None
        end_silence: Optional[float] = None
        if include_audio:
            audio_decode = self._decode_artifact_stream(
                artifact_path,
                stream_selector="0:a:0",
                expected_duration=expected_duration,
                cancel_callback=cancel_callback,
            )
            audio_end = self._progress_end_seconds(audio_decode, "Audio")
            if abs(audio_end - expected_duration) > duration_tolerance:
                raise RuntimeError(
                    "Artefakt-Audio-End-PTS verletzt: "
                    f"erwartet={expected_duration:.6f}, ist={audio_end:.6f}"
                )
            true_peak_dbtp = self._measure_true_peak_dbtp(
                artifact_path,
                expected_duration=expected_duration,
                cancel_callback=cancel_callback,
            )
            if true_peak_dbtp > self._AAC_TRUE_PEAK_LIMIT_DBTP:
                raise RuntimeError(
                    "Artefakt-Audio-True-Peak verletzt: "
                    f"Limit={self._AAC_TRUE_PEAK_LIMIT_DBTP:.2f} dBTP, "
                    f"ist={true_peak_dbtp:.2f} dBTP"
                )
            end_silence = self._measure_trailing_silence_seconds(
                artifact_path,
                expected_duration=expected_duration,
                noise_threshold_db=(
                    self._END_SILENCE_THRESHOLD_DB
                    + self._AAC_PRE_ENCODE_GAIN_DB
                ),
                cancel_callback=cancel_callback,
            )
            if (
                expected_end_silence is not None
                and abs(end_silence - expected_end_silence)
                > self._END_SILENCE_TOLERANCE_SECONDS
            ):
                raise RuntimeError(
                    "Artefakt-Audio-Endstille verletzt: "
                    f"erwartet={expected_end_silence:.6f}s, "
                    f"ist={end_silence:.6f}s"
                )

        return {
            "container_duration": format_duration,
            "video_end_pts": video_end,
            "audio_end_pts": audio_end,
            "decoded_frames": decoded_frames,
            "expected_frames": expected_frames,
            "true_peak_dbtp": true_peak_dbtp,
            "end_silence_seconds": end_silence,
            "expected_end_silence_seconds": expected_end_silence,
        }

    def _measure_true_peak_dbtp(
        self,
        artifact_path: Path,
        *,
        expected_duration: float,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> float:
        cmd = [
            _get_ffmpeg_path(),
            "-hide_banner",
            "-nostats",
            "-i", str(artifact_path),
            "-map", "0:a:0",
            "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
            "-f", "null",
            os.devnull,
        ]
        try:
            result = self._run_capture_process(
                cmd,
                timeout=max(
                    self._ARTIFACT_DECODE_TIMEOUT_FLOOR_SECONDS,
                    expected_duration,
                ),
                cancel_callback=cancel_callback,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Artefakt-True-Peak-Messung hat das Zeitlimit ueberschritten"
            ) from exc
        if result.returncode != 0:
            raise RuntimeError(
                f"Artefakt-True-Peak-Messung fehlgeschlagen: {result.stderr[-2000:]}"
            )
        matches = re.findall(r'"input_tp"\s*:\s*"([^"]+)"', result.stderr)
        if not matches:
            raise RuntimeError("Artefakt-True-Peak-Messung lieferte keinen input_tp")
        try:
            return float(matches[-1])
        except ValueError as exc:
            raise RuntimeError(
                f"Artefakt-True-Peak ist ungueltig: {matches[-1]!r}"
            ) from exc

    def _measure_trailing_silence_seconds(
        self,
        audio_path: Path,
        *,
        expected_duration: float,
        input_offset: float = 0.0,
        noise_threshold_db: Optional[float] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> float:
        threshold_db = (
            self._END_SILENCE_THRESHOLD_DB
            if noise_threshold_db is None
            else noise_threshold_db
        )
        cmd = [_get_ffmpeg_path(), "-hide_banner", "-nostats"]
        if input_offset > 0:
            cmd.extend(["-ss", f"{input_offset:.6f}"])
        cmd.extend([
            "-i", str(audio_path),
            "-map", "0:a:0",
            "-t", f"{expected_duration:.6f}",
            "-af",
            (
                f"silencedetect=noise={threshold_db:g}dB:"
                f"d={self._END_SILENCE_MIN_SECONDS}"
            ),
            "-f", "null",
            os.devnull,
        ])
        try:
            result = self._run_capture_process(
                cmd,
                timeout=max(
                    self._ARTIFACT_DECODE_TIMEOUT_FLOOR_SECONDS,
                    expected_duration,
                ),
                cancel_callback=cancel_callback,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Audio-Endstille-Messung hat das Zeitlimit ueberschritten"
            ) from exc
        if result.returncode != 0:
            raise RuntimeError(
                f"Audio-Endstille-Messung fehlgeschlagen: {result.stderr[-2000:]}"
            )
        matches = re.findall(
            r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            result.stderr,
        )
        if not matches:
            return 0.0
        try:
            silence_end, silence_duration = map(float, matches[-1])
        except ValueError as exc:
            raise RuntimeError("Audio-Endstille-Messung ist ungueltig") from exc
        if (
            abs(silence_end - expected_duration)
            > self._END_SILENCE_TOLERANCE_SECONDS
        ):
            return 0.0
        return silence_duration

    @staticmethod
    def _required_duration(value: Any, label: str) -> float:
        try:
            duration = float(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label}-Dauer fehlt oder ist ungueltig") from exc
        if duration <= 0:
            raise RuntimeError(f"{label}-Dauer ist nicht positiv: {duration}")
        return duration

    def _decode_artifact_stream(
        self,
        artifact_path: Path,
        *,
        stream_selector: str,
        expected_duration: float,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> dict[str, str]:
        cmd = [
            _get_ffmpeg_path(),
            "-v", "error",
            "-xerror",
            "-i", str(artifact_path),
            "-map", stream_selector,
        ]
        if ":v:" in stream_selector:
            cmd.append("-an")
        else:
            cmd.append("-vn")
        cmd.extend([
            "-progress", "pipe:1",
            "-nostats",
            "-f", "null",
            os.devnull,
        ])
        timeout = max(
            self._ARTIFACT_DECODE_TIMEOUT_FLOOR_SECONDS,
            expected_duration,
        )
        try:
            decode = self._run_capture_process(
                cmd,
                timeout=timeout,
                cancel_callback=cancel_callback,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Vollstaendiger Decode hat das Zeitlimit ueberschritten: {stream_selector}"
            ) from exc
        if decode.returncode != 0:
            raise RuntimeError(
                f"Vollstaendiger Decode fehlgeschlagen ({stream_selector}): "
                f"{decode.stderr[-2000:]}"
            )
        progress: dict[str, str] = {}
        for line in decode.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                progress[key] = value
        if progress.get("progress") != "end":
            raise RuntimeError(
                f"Vollstaendiger Decode ohne progress=end: {stream_selector}"
            )
        return progress

    @staticmethod
    def _progress_end_seconds(progress: dict[str, str], label: str) -> float:
        raw_value = progress.get("out_time_us")
        try:
            end_seconds = int(raw_value or "") / 1_000_000.0
        except ValueError as exc:
            raise RuntimeError(f"{label}-End-PTS fehlt im Decode-Fortschritt") from exc
        if end_seconds <= 0:
            raise RuntimeError(f"{label}-End-PTS ist nicht positiv: {end_seconds}")
        return end_seconds

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
            audio_dur = self._get_audio_duration(audio_path, cancel_callback)

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
        """Liest FFmpegs `-progress`-Protokoll und persistiert Rohbelege."""
        progress_queue: queue.Queue[str] = queue.Queue()
        progress_lines: list[str] = []
        stderr_lines: list[str] = []

        def read_pipe(
            pipe: Any,
            lines: list[str],
            target_queue: Optional[queue.Queue[str]] = None,
        ) -> None:
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    lines.append(line)
                    if target_queue is not None:
                        target_queue.put(line)
            except Exception:
                logger.debug("FFmpeg pipe reader ended unexpectedly", exc_info=True)

        stdout_thread = threading.Thread(
            target=read_pipe,
            args=(process.stdout, progress_lines, progress_queue),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_pipe,
            args=(process.stderr, stderr_lines),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        total_frames = max(int(round(max(total_duration, 0.0) * max(target_fps, 0.0))), 0)
        last_progress = 60
        last_publish_at = 0.0
        last_frame = 0
        last_fps = 0.0
        last_elapsed = 0.0
        last_machine_progress: dict[str, str] = {}
        progress_block: dict[str, str] = {}
        progress_end = False
        cancelled = False

        while True:
            running = process.poll() is None
            if running and cancel_callback and cancel_callback():
                process.kill()
                process.wait(timeout=5)
                cancelled = True
                break
            try:
                line = progress_queue.get(timeout=0.1 if running else 0.01)
            except queue.Empty:
                if not running and not stdout_thread.is_alive():
                    break
                if cancel_callback and cancel_callback():
                    process.kill()
                    process.wait(timeout=5)
                    cancelled = True
                    break
                continue

            key, separator, value = line.strip().partition("=")
            if not separator:
                continue
            progress_block[key] = value
            if key != "progress":
                continue

            last_machine_progress = dict(progress_block)
            progress_end = value == "end"
            progress_block.clear()
            try:
                time_sec = int(last_machine_progress.get("out_time_us", "0")) / 1_000_000.0
                parsed_frame = int(last_machine_progress.get("frame", "0") or 0)
                parsed_fps = float(last_machine_progress.get("fps", "0") or 0.0)
            except ValueError:
                continue

            current_frame = parsed_frame if parsed_frame > 0 else int(
                round(time_sec * max(target_fps, 0.0))
            )
            if total_frames > 0:
                current_frame = min(current_frame, total_frames)
            last_frame = max(current_frame, last_frame)
            elapsed_seconds = max(
                (
                    time.monotonic() - render_start_time
                    if render_start_time is not None
                    else time_sec
                ),
                0.0,
            )
            last_elapsed = elapsed_seconds
            effective_fps = parsed_fps
            if effective_fps <= 0.0 and elapsed_seconds > 0 and last_frame > 0:
                effective_fps = last_frame / elapsed_seconds
            last_fps = effective_fps
            remaining_frames = max(total_frames - last_frame, 0) if total_frames > 0 else 0
            eta_seconds = remaining_frames / effective_fps if effective_fps > 0.0 else 0.0

            if total_duration > 0:
                render_pct = min(time_sec / total_duration, 1.0)
                overall_pct = 60 + int(38 * render_pct)
                now = time.monotonic()
                should_publish = (
                    overall_pct > last_progress
                    or now - last_publish_at >= 1.0
                    or progress_end
                )
                if should_publish:
                    last_progress = max(last_progress, overall_pct)
                    last_publish_at = now
                    self._emit_progress(
                        progress_callback,
                        f"Rendering: {self._format_time(time_sec)} / {self._format_time(total_duration)}",
                        overall_pct,
                        current_frame=last_frame,
                        total_frames=total_frames,
                        fps=effective_fps,
                        elapsed_seconds=elapsed_seconds,
                        eta_seconds=max(eta_seconds, 0.0),
                    )

        finalization_timeout = False
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            finalization_timeout = True
        finally:
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

        stderr = "".join(stderr_lines)
        status = "cancelled" if cancelled else "completed"
        if not cancelled and (
            finalization_timeout
            or process.returncode != 0
            or not progress_end
        ):
            status = "failed"
        evidence = self._persist_render_evidence(
            status=status,
            exit_code=process.returncode,
            progress_end=progress_end,
            machine_progress=last_machine_progress,
            progress_log="".join(progress_lines),
            stderr_log=stderr,
            total_duration=total_duration,
            total_frames=total_frames,
        )
        if cancelled:
            raise RenderCancelledError("Rendering cancelled during ffmpeg encode")
        if finalization_timeout:
            raise RuntimeError(
                f"FFmpeg Finalisierung Timeout; evidence={evidence}"
            )
        if process.returncode != 0:
            logger.error("FFmpeg failure evidence: %s", evidence)
            return self._handle_ffmpeg_error(process.returncode, stderr)
        if not progress_end:
            raise RuntimeError(
                f"FFmpeg exit 0 ohne progress=end; evidence={evidence}"
            )
        
        return {
            "fps": last_fps,
            "current_frame": last_frame,
            "total_frames": total_frames,
            "elapsed_seconds": last_elapsed,
            "out_time_us": int(last_machine_progress.get("out_time_us", "0") or 0),
            "progress_end": True,
            "evidence_path": str(evidence),
        }

    def _persist_render_evidence(
        self,
        *,
        status: str,
        exit_code: Optional[int],
        progress_end: bool,
        machine_progress: dict[str, str],
        progress_log: str,
        stderr_log: str,
        total_duration: float,
        total_frames: int,
    ) -> Path:
        evidence_dir = (
            self.output_dir
            / ".render_evidence"
            / self.job_token
            / self.run_id
        )
        evidence_dir.mkdir(parents=True, exist_ok=False)
        progress_path = evidence_dir / "ffmpeg.progress.log"
        stderr_path = evidence_dir / "ffmpeg.stderr.log"
        self._atomic_write_text(progress_path, progress_log)
        self._atomic_write_text(stderr_path, stderr_log)

        normalized_tail = re.sub(
            r"0x[0-9a-fA-F]+",
            "0xADDR",
            stderr_log[-4000:],
        )
        failure_fingerprint: Optional[str] = None
        if status != "completed":
            fingerprint_source = (
                f"{status}|{exit_code}|{progress_end}|{normalized_tail}"
            ).encode("utf-8", errors="replace")
            failure_fingerprint = hashlib.sha256(fingerprint_source).hexdigest()
        out_time_us = int(machine_progress.get("out_time_us", "0") or 0)
        record = {
            "schema_version": 1,
            "job_id": self.job_token,
            "run_id": self.run_id,
            "status": status,
            "exit_code": exit_code,
            "progress_end": progress_end,
            "frame": int(machine_progress.get("frame", "0") or 0),
            "fps": float(machine_progress.get("fps", "0") or 0.0),
            "out_time_us": out_time_us,
            "end_pts_seconds": out_time_us / 1_000_000.0,
            "total_size": int(machine_progress.get("total_size", "0") or 0),
            "speed": machine_progress.get("speed"),
            "expected_duration_seconds": total_duration,
            "expected_frames": total_frames,
            "failure_fingerprint": failure_fingerprint,
            "progress_log_sha256": hashlib.sha256(
                progress_log.encode("utf-8", errors="replace")
            ).hexdigest(),
            "stderr_log_sha256": hashlib.sha256(
                stderr_log.encode("utf-8", errors="replace")
            ).hexdigest(),
            "recorded_at_epoch": time.time(),
        }
        record_path = evidence_dir / "result.json"
        self._atomic_write_text(
            record_path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
        return record_path

    def _persist_validation_evidence(
        self,
        *,
        metrics: Optional[dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> Path:
        evidence_dir = (
            self.output_dir
            / ".render_evidence"
            / self.job_token
            / self.run_id
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        error_text = f"{type(error).__name__}: {error}" if error is not None else None
        fingerprint = (
            hashlib.sha256(error_text.encode("utf-8", errors="replace")).hexdigest()
            if error_text is not None
            else None
        )
        if error is None:
            validation_status = "passed"
        elif isinstance(error, RenderCancelledError):
            validation_status = "cancelled"
        else:
            validation_status = "failed"
        record = {
            "schema_version": 1,
            "job_id": self.job_token,
            "run_id": self.run_id,
            "status": validation_status,
            "metrics": metrics,
            "error": error_text,
            "failure_fingerprint": fingerprint,
            "recorded_at_epoch": time.time(),
        }
        path = evidence_dir / "validation.json"
        self._atomic_write_text(
            path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
        return path

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary_path.write_text(content, encoding="utf-8")
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

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

    def _get_audio_duration(
        self,
        audio_path: str,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> Optional[float]:
        cmd = [
            _get_ffprobe_path(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", audio_path
        ]
        try:
            result = self._run_capture_process(
                cmd,
                timeout=30.0,
                cancel_callback=cancel_callback,
            )
            if result.returncode != 0:
                return None
            return float(json.loads(result.stdout)["format"]["duration"])
        except RenderCancelledError:
            raise
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
        for directory in (self.temp_dir, self.temp_dir.parent, self.temp_root):
            try:
                directory.rmdir()
            except OSError:
                break
