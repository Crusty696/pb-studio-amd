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


def detect_video_audio_key(video_path: str | Path) -> Optional[str]:
    """Extrahiert Audio-Track aus Video, ruft KeyDetector. Returns Key-String oder None.

    Returns None wenn:
    - Video nicht existiert
    - Video keinen Audio-Track hat
    - ffmpeg fehlschlaegt
    - Audio < 1s nach Extract
    - KeyDetector "Unknown" zurueckgibt
    """
    try:
        from pb_studio.audio.key_detector import KeyDetector
        import librosa
    except Exception as e:
        logger.debug(f"Imports fuer audio_key_detector nicht verfuegbar: {e}")
        return None

    try:
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            return None
        video_path_str = str(video_path_obj.resolve())

        ffmpeg_path = "ffmpeg"
        try:
            from pb_studio.config import config as _config
            ffmpeg_path = str(getattr(_config, "ffmpeg_path", "ffmpeg"))
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
                logger.debug(
                    f"ffmpeg audio-extract fail (kein Audio?): "
                    f"{res.stderr.decode(errors='ignore')[:200]}"
                )
                return None

            if not tmp_wav.exists() or tmp_wav.stat().st_size < 1000:
                return None

            y, sr = librosa.load(str(tmp_wav), sr=22050, mono=True)
            if len(y) < sr:  # < 1s Audio
                return None

            detector = KeyDetector()
            key = detector.detect_key(y, sr)
            if key == "Unknown":
                return None
            return key
        finally:
            tmp_wav.unlink(missing_ok=True)

    except subprocess.TimeoutExpired:
        logger.debug(f"ffmpeg timeout fuer {video_path}")
        return None
    except Exception as e:
        logger.debug(f"detect_video_audio_key fehlgeschlagen (unkritisch): {e}")
        return None
