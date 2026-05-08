"""Spectral Analyzer - 8-Band Frequenzanalyse für Audio.

Analysiert Audio in 8 Frequenzbändern für die Pacing-Engine:
- Sub-Bass, Bass, Low-Mid, Mid, Upper-Mid, Presence, Brilliance, Air
- Erkennung von Drops, Buildups, Breakdowns
- Energie-Verteilung pro Band über Zeit

AMD-Version: Rein CPU-basiert mit librosa (kein GPU nötig).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from numpy.typing import NDArray
import librosa

logger = logging.getLogger(__name__)

# Type alias
FloatArray = NDArray[np.floating]

# 8-Band Frequenz-Definition (Hz)
FREQUENCY_BANDS = {
    "sub_bass":   (20, 60),
    "bass":       (60, 250),
    "low_mid":    (250, 500),
    "mid":        (500, 2000),
    "upper_mid":  (2000, 4000),
    "presence":   (4000, 6000),
    "brilliance": (6000, 12000),
    "air":        (12000, 20000),
}

BAND_NAMES = list(FREQUENCY_BANDS.keys())


class SpectralAnalyzer:
    """8-Band Spektral-Analyse für Audio-Dateien.

    Berechnet Energie pro Frequenzband über Zeit und erkennt
    musikalische Events (Drops, Buildups, Breakdowns).
    """

    def __init__(self, sr: int = 22050, hop_length: int = 512, n_fft: int = 2048):
        self.sr = sr
        self.hop_length = hop_length
        self.n_fft = n_fft

    def analyze_from_array(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Führt vollständige 8-Band Spektral-Analyse auf bereits geladenem Audio durch.

        Vermeidet einen erneuten Disk-Zugriff wenn Audio bereits im Speicher liegt.

        Args:
            y:  Audio-Signal (float32/float64, mono)
            sr: Sample-Rate des Signals

        Returns:
            Gleiche Struktur wie analyze() — band_energies, band_means, events, …
        """
        try:
            # STFT berechnen
            S = np.abs(librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length))
            freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)
            times = librosa.frames_to_time(
                np.arange(S.shape[1]), sr=sr, hop_length=self.hop_length
            )

            # Spectral Centroid berechnen
            centroids = librosa.feature.spectral_centroid(S=S, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length)[0]

            band_energies: Dict[str, Any] = {}
            band_means: Dict[str, float] = {}
            band_variances: Dict[str, float] = {}

            for band_name, (low_freq, high_freq) in FREQUENCY_BANDS.items():
                freq_mask = (freqs >= low_freq) & (freqs < high_freq)
                if not np.any(freq_mask):
                    band_energies[band_name] = np.zeros(len(times))
                    band_means[band_name] = 0.0
                    band_variances[band_name] = 0.0
                    continue
                band_energy = np.sum(S[freq_mask, :], axis=0)
                band_energies[band_name] = band_energy
                band_means[band_name] = float(np.mean(band_energy))
                band_variances[band_name] = float(np.var(band_energy))

            events = self._detect_events(band_energies, times)

            return {
                "times": times.tolist(),
                "band_energies": {k: v.tolist() for k, v in band_energies.items()},
                "centroids": centroids.tolist(),
                "band_means": band_means,
                "band_variances": band_variances,
                "events": events,
                "duration": float(len(y) / sr),
                "num_frames": len(times),
            }
        except Exception as e:
            logger.error(f"Spektral-Analyse (Array) fehlgeschlagen: {e}")
            return self._empty_result()

    def analyze(self, audio_path: str | Path, duration: float | None = None, offset: float = 0.0) -> Dict[str, Any]:
        """Führt vollständige 8-Band Spektral-Analyse durch.

        Args:
            audio_path: Pfad zur Audio-Datei
            duration: Maximale Dauer zum Laden (None = komplett)
            offset: Start-Offset in Sekunden (Default 0.0)

        Returns:
            Dict mit band_energies, band_means, band_variances, events
        """
        audio_path = str(audio_path)

        try:
            y, sr = librosa.load(audio_path, sr=self.sr, offset=offset, duration=duration)
        except Exception as e:
            logger.error(f"Audio laden fehlgeschlagen: {e}")
            return self._empty_result()

        # STFT berechnen
        S = np.abs(librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)
        times = librosa.frames_to_time(
            np.arange(S.shape[1]), sr=sr, hop_length=self.hop_length
        )

        # Energie pro Band berechnen
        band_energies = {}
        band_means = {}
        band_variances = {}

        for band_name, (low_freq, high_freq) in FREQUENCY_BANDS.items():
            # Frequenz-Indizes für dieses Band
            freq_mask = (freqs >= low_freq) & (freqs < high_freq)
            if not np.any(freq_mask):
                band_energies[band_name] = np.zeros(len(times))
                band_means[band_name] = 0.0
                band_variances[band_name] = 0.0
                continue

            # Energie = Summe der Magnitude im Band pro Frame
            band_energy = np.sum(S[freq_mask, :], axis=0)
            band_energies[band_name] = band_energy
            band_means[band_name] = float(np.mean(band_energy))
            band_variances[band_name] = float(np.var(band_energy))

        # Events erkennen
        events = self._detect_events(band_energies, times)

        return {
            "times": times.tolist(),
            "band_energies": {k: v.tolist() for k, v in band_energies.items()},
            "band_means": band_means,
            "band_variances": band_variances,
            "events": events,
            "duration": float(len(y) / sr),
            "num_frames": len(times),
        }

    def get_band_energy_at_time(
        self, analysis_result: Dict, time_seconds: float
    ) -> Dict[str, float]:
        """Gibt die Band-Energien zu einem bestimmten Zeitpunkt zurück."""
        times = analysis_result.get("times", [])
        if not times:
            return {band: 0.0 for band in BAND_NAMES}

        # Nächsten Frame-Index finden
        idx = int(np.searchsorted(times, time_seconds))
        idx = min(idx, len(times) - 1)

        result = {}
        for band_name in BAND_NAMES:
            energies = analysis_result["band_energies"].get(band_name, [])
            if idx < len(energies):
                result[band_name] = float(energies[idx])
            else:
                result[band_name] = 0.0
        return result

    def get_band_means(self, analysis_result: Dict) -> List[float]:
        """Gibt die 8 Band-Mittelwerte als Liste zurück (für Feature-Vektoren)."""
        return [analysis_result["band_means"].get(b, 0.0) for b in BAND_NAMES]

    def get_band_variances(self, analysis_result: Dict) -> List[float]:
        """Gibt die 8 Band-Varianzen als Liste zurück (für Feature-Vektoren)."""
        return [analysis_result["band_variances"].get(b, 0.0) for b in BAND_NAMES]

    def _detect_events(
        self, band_energies: Dict[str, FloatArray], times: FloatArray
    ) -> List[Dict[str, Any]]:
        """Erkennt musikalische Events aus Spektral-Daten.

        Events: drop, buildup, breakdown
        """
        events = []
        if len(times) < 10:
            return events

        # Gesamt-Energie über alle Bänder
        total_energy = np.zeros(len(times))
        for band_energy in band_energies.values():
            if len(band_energy) == len(times):
                total_energy += band_energy

        # Normalisieren
        max_energy = np.max(total_energy) + 1e-10
        normalized = total_energy / max_energy

        # Glättung (1-Sekunden-Fenster)
        window = max(1, int(self.sr / self.hop_length))
        from scipy.ndimage import uniform_filter1d
        smoothed = uniform_filter1d(normalized, size=window)

        # Gradient berechnen
        gradient = np.gradient(smoothed)

        # Drop: Plötzlicher starker Anstieg nach niedrigem Level
        for i in range(window, len(smoothed) - window):
            prev_avg = np.mean(smoothed[i - window:i])
            curr_val = smoothed[i]

            # Drop: Energie springt um >50% hoch
            if curr_val > prev_avg * 1.5 and prev_avg < 0.4:
                events.append({
                    "type": "drop",
                    "time": float(times[i]),
                    "intensity": float(curr_val - prev_avg),
                    "confidence": min(1.0, (curr_val - prev_avg) / 0.5),
                })

            # Breakdown: Energie fällt stark ab
            elif curr_val < prev_avg * 0.4 and prev_avg > 0.5:
                events.append({
                    "type": "breakdown",
                    "time": float(times[i]),
                    "intensity": float(prev_avg - curr_val),
                    "confidence": min(1.0, (prev_avg - curr_val) / 0.5),
                })

        # Buildup: Kontinuierlich steigende Energie über >4 Sekunden
        buildup_window = int(4 * self.sr / self.hop_length)
        for i in range(buildup_window, len(gradient) - buildup_window, buildup_window):
            segment_gradient = gradient[i:i + buildup_window]
            if np.mean(segment_gradient) > 0.001 and np.min(segment_gradient) > -0.002:
                events.append({
                    "type": "buildup",
                    "time": float(times[i]),
                    "duration": float(times[min(i + buildup_window, len(times) - 1)] - times[i]),
                    "intensity": float(np.mean(segment_gradient)),
                    "confidence": min(1.0, np.mean(segment_gradient) / 0.005),
                })

        # Duplikate entfernen (Events innerhalb 2s zusammenfassen)
        if events:
            events.sort(key=lambda e: e["time"])
            filtered = [events[0]]
            for event in events[1:]:
                if event["time"] - filtered[-1]["time"] > 2.0 or event["type"] != filtered[-1]["type"]:
                    filtered.append(event)
            events = filtered

        logger.info(f"Spektral-Events: {len(events)} erkannt")
        return events

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "times": [],
            "band_energies": {b: [] for b in BAND_NAMES},
            "band_means": {b: 0.0 for b in BAND_NAMES},
            "band_variances": {b: 0.0 for b in BAND_NAMES},
            "events": [],
            "duration": 0.0,
            "num_frames": 0,
        }
