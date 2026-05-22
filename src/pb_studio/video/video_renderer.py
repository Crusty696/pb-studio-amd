"""VideoRenderer - Rendert die finale Cut-Liste zu einem Video.

AMD-Version: Nutzt AMF Hardware-Encoding (h264_amf, hevc_amf) statt NVENC.
Verwendet encoder_utils für AMD-kompatible FFmpeg-Parameter.
Parallelisiert das Rendering über einen ProcessPoolExecutor und nutzt MD5-Caching.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List

logger = logging.getLogger(__name__)


def _render_single_segment(
    ffmpeg_path: str,
    file_path: str,
    clip_start: float,
    duration: float,
    seg_path: str,
    vf_filters: str,
    encode_params: List[str]
) -> tuple[bool, str]:
    """Rendert ein einzelnes Segment parallel auf Modulebene.
    
    Verhindert Pickling-Probleme unter Windows, da es auf Modulebene definiert ist.
    Unterstützt intelligentes Caching vor dem Render-Aufruf.
    """
    p = Path(seg_path)
    # Caching-Prüfung: Falls Datei existiert und nicht leer ist, überspringen
    if p.exists() and p.stat().st_size > 1000:
        return True, "cached"

    cmd = [
        ffmpeg_path, "-y",
        "-ss", f"{clip_start:.6f}", "-t", f"{duration:.6f}",
        "-i", str(file_path),
        "-vf", vf_filters,
    ] + encode_params + ["-an", str(seg_path)]

    try:
        # Führe subprocess ohne shell=True aus (IRON RULE)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode == 0 and p.exists():
            return True, "rendered"
        else:
            err = res.stderr[-300:] if res.stderr else "Unknown error"
            return False, f"FFmpeg failed: {err}"
    except subprocess.TimeoutExpired:
        return False, "Timeout (5 min)"
    except Exception as e:
        return False, f"Exception: {str(e)}"


class VideoRenderer:
    """Rendert eine Cut-Liste zu einem fertigen Video (AMD AMF).

    Workflow:
    1. Clips parallel trimmen + skalieren (FFmpeg + ProcessPoolExecutor + Cache)
    2. Concat-Liste erstellen
    3. Audio zusammenführen
    4. Finales Encoding mit AMF (verlustfrei via concat demuxer copy)
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
            from .encoder_utils import _get_ffmpeg_path, _get_ffprobe_path
            self._ffmpeg = _get_ffmpeg_path()
            self._ffprobe = _get_ffprobe_path()
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
        """Führt einen synchronen FFmpeg-Befehl aus."""
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
        """Rendert Cut-Liste zu Video über paralleles Processing und Caching.

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
            logger.info(f"Starte paralleles Rendering: {len(cut_list)} Cuts -> {output_path}")

            # 1. Tasks vorbereiten
            tasks = []
            segments = []
            vf_filters = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p"
            encode_params = self._get_encode_params()

            for i, cut in enumerate(cut_list):
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

                # Eindeutiger Hash-Name für intelligentes Caching
                key = f"{file_path}_{clip_start:.6f}_{duration:.6f}_{self.codec}_{self.quality}"
                h = hashlib.md5(key.encode("utf-8")).hexdigest()
                seg_path = self.temp_dir / f"seg_{h}.mp4"

                segments.append(seg_path)
                tasks.append((self._ffmpeg, str(file_path), clip_start, duration, str(seg_path), vf_filters, encode_params))

            # 2. Parallel mit ProcessPoolExecutor rendern (4 Workers standardmäßig)
            num_workers = min(4, len(tasks)) if len(tasks) > 0 else 1
            logger.info(f"Rendere {len(tasks)} Segmente parallel mit {num_workers} Workers ...")

            ok_count = 0
            cached_count = 0
            fail_count = 0

            if len(tasks) > 0:
                with ProcessPoolExecutor(max_workers=num_workers) as executor:
                    futures = {
                        executor.submit(_render_single_segment, *task): i 
                        for i, task in enumerate(tasks)
                    }

                    for fut in as_completed(futures):
                        if self._cancelled:
                            logger.warning("Rendering wurde abgebrochen. Storniere ausstehende Tasks...")
                            executor.shutdown(wait=False, cancel_futures=True)
                            return None

                        idx = futures[fut]
                        success, status = fut.result()

                        if success:
                            if status == "cached":
                                cached_count += 1
                            else:
                                ok_count += 1
                        else:
                            fail_count += 1
                            logger.error(f"Segment-Render-Fehler bei Schnitt {idx}: {status}")

                        current += 1
                        if progress_callback:
                            progress_callback(current / total_steps)

            logger.info(f"Rendering beendet. Erfolgreich: {ok_count}, Aus Cache: {cached_count}, Fehler: {fail_count}")

            if fail_count > 0:
                logger.error(f"{fail_count} Segmente konnten nicht gerendert werden. Abbruch.")
                return None

            # 3. Concat (byteweise Zusammenführung, extrem schnell)
            concat_path = self.temp_dir / "concat_video.mp4"
            if not self._concat_segments(segments, concat_path):
                # Bereinige nur den fehlerhaften Concat-Output
                self._cleanup([concat_path])
                return None
            current += 1
            if progress_callback:
                progress_callback(current / total_steps)

            # 4. Audio + finales Muxing
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            if not self._merge_audio(concat_path, audio_path, out):
                self._cleanup([concat_path])
                return None

            if progress_callback:
                progress_callback(1.0)

            # WICHTIG: Gerenderte Segmente werden NICHT gelöscht, um den Cache für künftige Iterationen zu erhalten!
            # Nur der temporäre concat_video.mp4 Stream wird bereinigt.
            self._cleanup([concat_path])
            logger.info(f"Rendering erfolgreich abgeschlossen: {output_path}")
            return str(out)

        except Exception as e:
            logger.error(f"Rendering fehlgeschlagen: {e}", exc_info=True)
            return None

    def _prepare_segment(self, cut, index: int) -> Path | None:
        """Kompatibilitäts-Methode. Führt synchrones Rendern für ein einzelnes Segment aus."""
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

        # Eindeutiger Hash-Name
        key = f"{file_path}_{clip_start:.6f}_{duration:.6f}_{self.codec}_{self.quality}"
        h = hashlib.md5(key.encode("utf-8")).hexdigest()
        seg_path = self.temp_dir / f"seg_{h}.mp4"

        vf_filters = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p"
        encode_params = self._get_encode_params()

        success, status = _render_single_segment(
            self._ffmpeg, str(file_path), clip_start, duration, str(seg_path), vf_filters, encode_params
        )
        if success:
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
            if (c.get('start_time', 0) if isinstance(c, dict) else getattr(c, 'start_time', 0)) < end_time
        ]
        if not preview_cuts:
            return None
        # Thread-safe: eigene Instanz statt self.quality zu mutieren
        preview_renderer = VideoRenderer(
            codec=self.codec, quality="fast", temp_dir=self.temp_dir / "preview"
        )
        return preview_renderer.render_video(preview_cuts, audio_path, output_path, progress_callback)
