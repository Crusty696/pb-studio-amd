"""
Proxy Service (AMD Version)
============================

Erstellt optimierte Proxy-Videos für schnellere Analyse und Preview.
Nutzt AMD AMF Hardware-Encoder statt NVENC.

Features:
- Einheitliche Auflösung (1080p oder kleiner)
- Einheitliche FPS (30fps)
- Schneller Codec via AMD AMF oder Software-Fallback
- Caching (Proxy nur einmal erstellen)
"""

import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Callable, Tuple

logger = logging.getLogger(__name__)


class ProxyService:
    """Service für Proxy-Video-Erstellung mit AMD AMF Hardware-Encoding."""

    PROXY_WIDTH = 1920
    PROXY_HEIGHT = 1080
    PROXY_FPS = 30
    PROXY_CRF = 23

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir
        self._encoder = self._detect_encoder()

    def _detect_encoder(self) -> str:
        """Erkennt den besten AMD-Encoder für Proxies."""
        for enc in ["h264_amf", "h264_mf", "libx264"]:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", enc, "-f", "null", "-"
            ]
            try:
                result = subprocess.run(
                    cmd, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=10
                )
                if result.returncode == 0:
                    logger.info(f"Proxy-Encoder: {enc}")
                    return enc
            except Exception:
                continue
        return "libx264"

    def set_cache_dir(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_proxy_path(self, original_path: str) -> Path:
        if not self.cache_dir:
            raise RuntimeError("Cache-Verzeichnis nicht gesetzt!")
        p = Path(original_path)
        mtime = p.stat().st_mtime if p.exists() else 0
        hash_input = f"{p.absolute()}|{mtime}"
        hash_short = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return self.cache_dir / f"{p.stem}_proxy_{hash_short}.mp4"

    def needs_proxy(self, video_path: str) -> Tuple[bool, Dict]:
        info = self._get_video_info(video_path)
        if not info:
            return True, {}
        w = info.get("width", 0)
        h = info.get("height", 0)
        fps = info.get("fps", 0)
        needs = w > self.PROXY_WIDTH or h > self.PROXY_HEIGHT or abs(fps - self.PROXY_FPS) > 1.0
        return needs, info

    def _get_video_info(self, video_path: str) -> Optional[Dict]:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json", video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            fmt = data.get("format", {})
            rate_str = stream.get("r_frame_rate", "30/1")
            try:
                num, den = map(int, rate_str.split("/"))
                fps = num / den if den else 30.0
            except (ValueError, ZeroDivisionError):
                fps = 30.0
            duration = float(stream.get("duration") or fmt.get("duration") or 0)
            return {
                "width": int(stream.get("width", 0)),
                "height": int(stream.get("height", 0)),
                "fps": fps,
                "duration": duration,
            }
        except Exception as e:
            logger.warning(f"Video-Info Fehler für {video_path}: {e}")
            return None

    def create_proxy(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Optional[str]:
        """Erstellt einen Proxy für ein Video."""
        if not self.cache_dir:
            raise RuntimeError("Cache-Verzeichnis nicht gesetzt!")

        proxy_path = self.get_proxy_path(video_path)
        if proxy_path.exists() and proxy_path.stat().st_size > 0:
            logger.info(f"Proxy existiert bereits: {proxy_path.name}")
            return str(proxy_path)

        info = self._get_video_info(video_path)
        duration = info.get("duration", 60) if info else 60

        vf = f"scale='min({self.PROXY_WIDTH},iw)':-2,fps={self.PROXY_FPS}"

        if self._encoder == "h264_amf":
            enc_args = ["-c:v", "h264_amf", "-quality", "speed", "-b:v", "8M"]
        elif self._encoder == "h264_mf":
            enc_args = ["-c:v", "h264_mf", "-q:v", "70"]
        else:
            enc_args = ["-c:v", "libx264", "-preset", "fast", "-crf", str(self.PROXY_CRF)]

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf,
            *enc_args,
            "-an",
            "-progress", "pipe:1",
            "-stats_period", "0.5",
            str(proxy_path)
        ]

        logger.info(f"Erstelle Proxy: {Path(video_path).name} -> {proxy_path.name}")

        # Windows: Konsole verstecken
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = None
        try:
            process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, startupinfo=startupinfo
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line.startswith("out_time_us="):
                    try:
                        time_us = int(line.split("=")[1])
                        time_sec = time_us / 1_000_000.0
                        pct = min(100.0, (time_sec / duration) * 100)
                        if progress_callback:
                            progress_callback(pct, f"Proxy: {time_sec:.1f}s / {duration:.1f}s")
                    except (ValueError, IndexError):
                        pass

            _, stderr = process.communicate(timeout=3600)

            if process.returncode != 0:
                logger.error(f"Proxy-Erstellung fehlgeschlagen: {stderr}")
                proxy_path.unlink(missing_ok=True)
                return None

            if not proxy_path.exists() or proxy_path.stat().st_size == 0:
                logger.error("Proxy-Datei ist leer oder fehlt")
                return None

            logger.info(f"Proxy erstellt: {proxy_path.name} ({proxy_path.stat().st_size // 1024}KB)")
            return str(proxy_path)

        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
                process.communicate()
            logger.error("Proxy-Erstellung Timeout")
            proxy_path.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"Proxy-Erstellung Fehler: {e}")
            proxy_path.unlink(missing_ok=True)
            return None
        finally:
            if process is not None:
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

    def create_proxies_batch(
        self,
        video_paths: list,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Optional[str]]:
        """Erstellt Proxies für mehrere Videos."""
        results = {}
        total = len(video_paths)

        for i, video_path in enumerate(video_paths):
            video_name = Path(video_path).name
            base_pct = (i / total) * 100

            if progress_callback:
                progress_callback(base_pct, f"Prüfe: {video_name}")

            needs, info = self.needs_proxy(video_path)
            if not needs:
                logger.info(f"Kein Proxy nötig für {video_name}")
                results[video_path] = video_path
                continue

            proxy_path = self.get_proxy_path(video_path)
            if proxy_path.exists() and proxy_path.stat().st_size > 0:
                logger.info(f"Proxy cached: {video_name}")
                results[video_path] = str(proxy_path)
                continue

            def sub_progress(pct, status):
                if progress_callback:
                    overall = base_pct + (pct / total)
                    progress_callback(overall, f"[{i + 1}/{total}] {status}")

            results[video_path] = self.create_proxy(video_path, sub_progress)

        return results

    def get_disk_usage(self) -> Tuple[int, int]:
        if not self.cache_dir or not self.cache_dir.exists():
            return 0, 0
        count = 0
        size = 0
        for f in self.cache_dir.glob("*_proxy_*.mp4"):
            count += 1
            size += f.stat().st_size
        return count, size

    def clear_cache(self) -> int:
        if not self.cache_dir or not self.cache_dir.exists():
            return 0
        count = 0
        for f in self.cache_dir.glob("*_proxy_*.mp4"):
            try:
                f.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Konnte Proxy nicht löschen: {f} - {e}")
        logger.info(f"Proxy-Cache geleert: {count} Dateien")
        return count
