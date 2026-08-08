"""
Key Detector — Krumhansl-Kessler Algorithmus für Tonarten-Erkennung.

Nutzt librosa Chroma-CQT Features und korreliert mit Dur/Moll-Profilen.
CPU-only. NumPy <2.0 kompatibel (v1.26.4 getestet).

Rückgabe: z.B. "C major", "A minor", "F# minor"
"""

import logging
from typing import Optional

import numpy as np
import librosa

logger = logging.getLogger(__name__)

# Krumhansl-Kessler Tonigkeit-Profile (1990)
_MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88
], dtype=np.float64)

_MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17
], dtype=np.float64)

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]


class KeyDetector:
    """Erkennt die musikalische Tonart via Krumhansl-Kessler Korrelation."""

    def __init__(self, sr: int = 22050, hop_length: int = 512):
        self.sr = sr
        self.hop_length = hop_length

    def detect_key(self, y: np.ndarray, sr: int) -> str:
        """
        Erkennt Tonart aus numpy Audio-Array.

        Args:
            y:  Audio-Signal (float32/float64, mono oder stereo)
            sr: Sample-Rate

        Returns:
            Tonart-String, z.B. "C major", "A minor"
        """
        try:
            # Mono konvertieren wenn nötig
            if y.ndim > 1:
                y = np.mean(y, axis=0)

            # Chroma-CQT Features (robuster als STFT-Chroma für Tonart)
            chroma = librosa.feature.chroma_cqt(
                y=y, sr=sr, hop_length=self.hop_length
            )

            # Mitteln über Zeit → 12-dimensionaler Chroma-Vektor
            chroma_mean = np.mean(chroma, axis=1)

            best_key = "C major"
            best_corr = -np.inf

            for i in range(12):
                # Dur-Profil auf Grundton i rotieren
                major_rotated = np.roll(_MAJOR_PROFILE, i)
                corr_major = float(np.corrcoef(chroma_mean, major_rotated)[0, 1])
                if np.isnan(corr_major):
                    continue

                # Moll-Profil auf Grundton i rotieren
                minor_rotated = np.roll(_MINOR_PROFILE, i)
                corr_minor = float(np.corrcoef(chroma_mean, minor_rotated)[0, 1])
                if np.isnan(corr_minor):
                    continue

                if corr_major > best_corr:
                    best_corr = corr_major
                    best_key = f"{_NOTE_NAMES[i]} major"

                if corr_minor > best_corr:
                    best_corr = corr_minor
                    best_key = f"{_NOTE_NAMES[i]} minor"

            if best_corr == -np.inf:
                logger.warning("Key detection fehlgeschlagen (NaN correlation) — Audio möglicherweise leer oder Ton-Sinus")
                return "Unknown"

            logger.debug(f"Tonart erkannt: {best_key} (Korrelation: {best_corr:.3f})")
            return best_key

        except Exception as e:
            logger.warning(f"Key-Detection fehlgeschlagen: {e}")
            return "Unknown"

    def detect_key_from_chroma(self, chroma_mean: np.ndarray | list[float]) -> str:
        """Erkennt Tonart aus einem aggregierten 12-Bin-Chroma-Vektor."""
        chroma_vector = np.asarray(chroma_mean, dtype=np.float64).reshape(-1)
        if chroma_vector.size != 12 or not np.any(np.isfinite(chroma_vector)):
            return "Unknown"

        best_key = "C major"
        best_corr = -np.inf
        for i in range(12):
            major_corr = float(
                np.corrcoef(chroma_vector, np.roll(_MAJOR_PROFILE, i))[0, 1]
            )
            if not np.isnan(major_corr) and major_corr > best_corr:
                best_corr = major_corr
                best_key = f"{_NOTE_NAMES[i]} major"

            minor_corr = float(
                np.corrcoef(chroma_vector, np.roll(_MINOR_PROFILE, i))[0, 1]
            )
            if not np.isnan(minor_corr) and minor_corr > best_corr:
                best_corr = minor_corr
                best_key = f"{_NOTE_NAMES[i]} minor"

        return best_key if best_corr > -np.inf else "Unknown"

    def detect_key_from_file(
        self,
        audio_path: str,
        duration: Optional[float] = None,
    ) -> str:
        """
        Erkennt Tonart direkt aus Audio-Datei.

        Args:
            audio_path: Pfad zur Audio-Datei
            duration:   Optional — nur erste N Sekunden (Performance bei langen Files)

        Returns:
            Tonart-String, z.B. "C major", "A minor"
        """
        try:
            y, sr = librosa.load(
                audio_path, sr=self.sr, mono=True, duration=duration
            )
            return self.detect_key(y, sr)
        except Exception as e:
            logger.warning(f"Key-Detection (File) fehlgeschlagen — {audio_path}: {e}")
            return "Unknown"
