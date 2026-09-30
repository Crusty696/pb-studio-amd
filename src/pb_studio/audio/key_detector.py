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

# Vorsprung fuer Moll beim Korrelationsvergleich (T003, 2026-09-30).
#
# Gemessen gegen rekordbox-Tonarten der Bibliothek des Projektinhabers
# (Psy-/Progressive-Trance, Melodic House/Techno): 91 % der Titel stehen dort
# in Moll. Ohne Vorsprung war der haeufigste Fehler die Dur/Moll-Verwechslung
# bei gleichem Grundton - 9 von 15 Fehlern auf der 40-Titel-Stichprobe. Die
# Krumhansl-Kessler-Profile stammen aus Hoerversuchen mit westlicher
# Kunstmusik; in Moll-lastiger elektronischer Tanzmusik liegen Dur und Moll
# desselben Grundtons oft nur wenige Hundertstel auseinander.
# Der Wert ist an einem getrennten 120-Titel-Tuning-Satz gewaehlt und am
# unveraenderten 40-Titel-Pruefsatz gemessen (scripts/dev/t003_*):
#
#     Vorsprung   Tuning Moll   Tuning Dur   Pruefsatz (40, alle Moll)
#       0,0         72/106         7/14           25/40
#       0,075       80/106         7/14           32/40
#       0,1         83/106         5/14           33/40
#       0,15        84/106         1/14           35/40
#
# 0,075 ist der groesste Wert, der im Tuning-Satz noch kein Dur-Stueck kostet.
# ACHTUNG, genrespezifisch wie `beat_grid.TEMPO_RANGE`: fuer Material mit
# vielen Dur-Stuecken muss er auf 0.0 gesetzt und neu gemessen werden.
MINOR_PRIOR = 0.075


class KeyDetector:
    """Erkennt die musikalische Tonart via Krumhansl-Kessler Korrelation."""

    def __init__(self, sr: int = 22050, hop_length: int = 512,
                 minor_prior: float = MINOR_PRIOR):
        self.sr = sr
        self.hop_length = hop_length
        self.minor_prior = float(minor_prior)

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

            best_key, best_corr = self._best_key(chroma_mean)

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

        best_key, best_corr = self._best_key(chroma_vector)
        return best_key if best_corr > -np.inf else "Unknown"

    def _best_key(self, chroma_vector: np.ndarray) -> tuple[str, float]:
        """Beste Tonart per Profilkorrelation; Moll erhaelt `minor_prior` Vorsprung.

        Eine gemeinsame Implementierung fuer Datei- und Chroma-Pfad, damit beide
        Pfade dieselbe Tonart liefern (vorher zwei Kopien derselben Schleife).
        """
        with np.errstate(invalid="ignore", divide="ignore"):
            best_key = "C major"
            best_corr = -np.inf
            for i in range(12):
                corr_major = float(np.corrcoef(chroma_vector, np.roll(_MAJOR_PROFILE, i))[0, 1])
                corr_minor = float(np.corrcoef(chroma_vector, np.roll(_MINOR_PROFILE, i))[0, 1])
                if np.isnan(corr_major) or np.isnan(corr_minor):
                    continue
                corr_minor += self.minor_prior
                if corr_major > best_corr:
                    best_corr = corr_major
                    best_key = f"{_NOTE_NAMES[i]} major"
                if corr_minor > best_corr:
                    best_corr = corr_minor
                    best_key = f"{_NOTE_NAMES[i]} minor"
        return best_key, best_corr

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
