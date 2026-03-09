"""Anchor Features - 20-dimensionaler Audio-Feature-Vektor.

Extrahiert einen kompakten Feature-Vektor pro Audio-Segment für
das Anchor-basierte Pacing-System:
- 8 Band-Mittelwerte (SpectralAnalyzer)
- 8 Band-Varianzen (SpectralAnalyzer)
- 3 Energie-Features (RMS mean, max, dynamic range)
- 1 Beat-Dichte (Beats pro Sekunde)

AMD-Version: Rein CPU-basiert mit librosa.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import librosa

logger = logging.getLogger(__name__)


class AnchorFeatureExtractor:
    """Extrahiert 20-dimensionale Feature-Vektoren aus Audio-Segmenten."""

    FEATURE_DIM = 20  # 8 means + 8 vars + 3 energy + 1 beat_density

    def __init__(self, sr: int = 22050):
        self.sr = sr
        self._spectral_analyzer = None

    def _get_spectral_analyzer(self):
        """Lazy-Load des SpectralAnalyzers."""
        if self._spectral_analyzer is None:
            from .spectral_analyzer import SpectralAnalyzer
            self._spectral_analyzer = SpectralAnalyzer(sr=self.sr)
        return self._spectral_analyzer

    def extract_features(
        self,
        audio_path: str | Path,
        start_time: float = 0.0,
        end_time: float | None = None,
        beat_times: List[float] | None = None,
    ) -> np.ndarray:
        """Extrahiert 20-dim Feature-Vektor aus einem Audio-Segment.

        Args:
            audio_path: Pfad zur Audio-Datei
            start_time: Startzeit in Sekunden
            end_time: Endzeit in Sekunden (None = bis Ende)
            beat_times: Bereits erkannte Beat-Zeiten (optional)

        Returns:
            numpy Array mit 20 Features
        """
        audio_path = str(audio_path)

        try:
            # Audio-Segment laden
            offset = start_time
            duration = (end_time - start_time) if end_time else None
            y, sr = librosa.load(audio_path, sr=self.sr, offset=offset, duration=duration)

            if len(y) < 2048:
                logger.warning(f"Audio-Segment zu kurz: {len(y)} Samples")
                return np.zeros(self.FEATURE_DIM)

            segment_duration = len(y) / sr

            # 1. Spektral-Features (8 means + 8 variances = 16 Features)
            spectral = self._get_spectral_analyzer()
            spectral_result = spectral.analyze(audio_path, duration=duration, offset=offset)

            band_means = spectral.get_band_means(spectral_result)
            band_vars = spectral.get_band_variances(spectral_result)

            # 2. Energie-Features (3 Features)
            rms = librosa.feature.rms(y=y)[0]
            rms_mean = float(np.mean(rms))
            rms_max = float(np.max(rms))
            dynamic_range = float(rms_max - np.min(rms))

            # 3. Beat-Dichte (1 Feature)
            if beat_times is not None:
                # Beats im Segment zählen
                segment_beats = [
                    t for t in beat_times
                    if start_time <= t < (end_time or float('inf'))
                ]
                beat_density = len(segment_beats) / max(segment_duration, 0.1)
            else:
                # Beat-Dichte aus Onset-Strength schätzen
                onset_env = librosa.onset.onset_strength(y=y, sr=sr)
                onset_count = len(librosa.onset.onset_detect(
                    y=y, sr=sr, onset_envelope=onset_env, units='time'
                ))
                beat_density = onset_count / max(segment_duration, 0.1)

            # Feature-Vektor zusammenbauen
            features = np.array(
                band_means + band_vars + [rms_mean, rms_max, dynamic_range, beat_density],
                dtype=np.float32
            )

            # Normalisierung (L2)
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm

            return features

        except Exception as e:
            logger.error(f"Feature-Extraktion fehlgeschlagen: {e}")
            return np.zeros(self.FEATURE_DIM, dtype=np.float32)

    def extract_features_batch(
        self,
        audio_path: str | Path,
        segments: List[Tuple[float, float]],
        beat_times: List[float] | None = None,
    ) -> np.ndarray:
        """Extrahiert Features für mehrere Segmente.

        Args:
            audio_path: Pfad zur Audio-Datei
            segments: Liste von (start_time, end_time) Tupeln
            beat_times: Bereits erkannte Beat-Zeiten

        Returns:
            numpy Matrix (n_segments x 20)
        """
        features_list = []
        for start, end in segments:
            feat = self.extract_features(audio_path, start, end, beat_times)
            features_list.append(feat)

        if not features_list:
            return np.zeros((0, self.FEATURE_DIM), dtype=np.float32)

        return np.stack(features_list)

    def compute_similarity(self, features_a: np.ndarray, features_b: np.ndarray) -> float:
        """Berechnet Cosine-Similarity zwischen zwei Feature-Vektoren."""
        norm_a = np.linalg.norm(features_a)
        norm_b = np.linalg.norm(features_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(features_a, features_b) / (norm_a * norm_b))
