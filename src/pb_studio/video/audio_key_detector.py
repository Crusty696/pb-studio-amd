"""Extrahiert Audio-Track aus Video + detektiert Tonart via Krumhansl-Kessler (L-K4).

Verwendet ffmpeg um WAV-Slice (max 30s) zu extrahieren, dann KeyDetector.
Fehler (kein Audio-Track, ffmpeg-Fehler) -> None (kein Crash).

Verwendet wird das Ergebnis von _key_compatibility_score(audio_key, video_key)
in AdvancedPacingEngine.clip_selector — bevor diese Funktion existierte, hatte
UseKeyMatching keinen Effekt da Video-Clips kein audio_key Feld hatten.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def has_video_audio_stream(video_path: str | Path) -> bool:
    """Prueft via ffprobe, ob das Video mindestens eine Audio-Spur besitzt."""
    try:
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            return False

        ffprobe_path = "ffprobe"
        try:
            from pb_studio.config_manager import ConfigManager
            ffprobe_path = str(ConfigManager().get("paths.ffprobe_bin", "ffprobe"))
        except Exception:
            ffprobe_path = "ffprobe"

        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path_obj.resolve()),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return res.returncode == 0 and "audio" in res.stdout.strip().lower()
    except Exception as e:
        logger.debug(f"has_video_audio_stream Check fehlgeschlagen: {e}")
        return False


def detect_video_audio_key(video_path: str | Path) -> Optional[str]:
    """Extrahiert Audio-Track aus Video, ruft KeyDetector. Returns Key-String oder None.

    Returns None (Faehigkeit unavailable) wenn:
    - Video nicht existiert
    - Video nachweislich keine Tonspur hat (ffprobe liefert keinen Audio-Stream)
    - Audio < 1s nach Extract
    - KeyDetector "Unknown" zurueckgibt

    Raises RuntimeError (Fehler/failed) wenn:
    - Video eine Tonspur besitzt, aber ffmpeg-Extraktion fehlschlaegt oder timed out
    - Extrahierte WAV-Datei beschaedigt oder unlesbar ist
    """
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        return None

    # Echte Faehigkeitsgrenze pruefen: Besitzt das Video ueberhaupt eine Tonspur?
    if not has_video_audio_stream(video_path_obj):
        return None

    try:
        from pb_studio.audio.key_detector import KeyDetector
        import librosa
    except Exception as e:
        raise RuntimeError(f"Imports fuer audio_key_detector nicht verfuegbar: {e}") from e

    video_path_str = str(video_path_obj.resolve())

    ffmpeg_path = "ffmpeg"
    try:
        from pb_studio.config_manager import ConfigManager
        ffmpeg_path = str(ConfigManager().get("paths.ffmpeg_bin", "ffmpeg"))
    except Exception:
        try:
            from pb_studio.video.encoder_utils import _get_ffmpeg_path
            ffmpeg_path = _get_ffmpeg_path()
        except Exception:
            ffmpeg_path = "ffmpeg"

    # NamedTemporaryFile + delete=False, damit wir den Pfad an ffmpeg geben koennen
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = Path(tmp.name)

    try:
        cmd = [
            ffmpeg_path, "-y", "-i", video_path_str,
            "-ss", "0", "-t", "30",
            "-vn", "-ac", "1", "-ar", "22050",
            str(tmp_wav),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=30)
        if res.returncode != 0:
            stderr_snippet = res.stderr.decode(errors="ignore")[:300]
            raise RuntimeError(f"ffmpeg audio-extract fail fuer Video mit Tonspur: {stderr_snippet}")

        if not tmp_wav.exists() or tmp_wav.stat().st_size < 1000:
            raise RuntimeError(f"Extrahierte WAV-Datei ungueltig oder leer (<1KB)")

        y, sr = librosa.load(str(tmp_wav), sr=22050, mono=True)
        if len(y) < sr:  # < 1s Audio
            return None

        detector = KeyDetector()
        key = detector.detect_key(y, sr)
        if key == "Unknown":
            return None
        return key
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timeout (30s) fuer {video_path}") from exc
    finally:
        tmp_wav.unlink(missing_ok=True)

