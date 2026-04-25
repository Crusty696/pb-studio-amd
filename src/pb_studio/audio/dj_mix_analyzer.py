"""DJ-Mix-Analyzer - Erkennung von Übergängen und Energie-Phasen in DJ-Mixes.

AMD-Version: Rein CPU-basiert mit librosa + scipy.
"""

from typing import Any, Dict, List

import numpy as np
from numpy.typing import NDArray
import librosa
from scipy.ndimage import uniform_filter1d

import logging

logger = logging.getLogger(__name__)

# Type alias
FloatArray = NDArray[np.floating]

# Energy phases
ENERGY_PHASES = {
    "low_energy": "Ruhig",
    "rising": "Aufbau",
    "high_energy": "Intensiv",
    "falling": "Abbau",
    "plateau": "Plateau",
    "transition": "Track-Übergang",
    "peak": "Peak",
}

ENERGY_PHASE_INTENSITY = {
    "low_energy": 0.5,
    "rising": 0.8,
    "high_energy": 1.5,
    "falling": 0.7,
    "plateau": 1.0
}


class DJMixAnalyzer:
    """Analyse von DJ-Mixes (Übergänge, Energie-Phasen)."""

    def __init__(self, sr_default: int = 22050, progress_callback=None):
        self.sr_default = sr_default
        self._progress_callback = progress_callback

    def _report_progress(self, phase: str, progress: float) -> None:
        if self._progress_callback:
            self._progress_callback(phase, progress)

    def detect_mix_transitions(
        self, y: FloatArray, sr: int, min_transition_gap: float = 60.0
    ) -> List[Dict[str, Any]]:
        """Erkennt Track-Übergänge in DJ-Mixes.

        Verwendet: Spectral Flux, Chromagram-Wechsel, RMS-Energy-Drops, Onset-Pattern.

        Args:
            y: Audio-Daten
            sr: Samplerate
            min_transition_gap: Mindestabstand zwischen Übergängen (Sekunden)

        Returns:
            Liste von Dicts mit time, confidence, type, duration
        """
        try:
            duration = len(y) / sr

            # Downsampling für Performance
            if sr > 11025:
                y_ds = librosa.resample(y, orig_sr=sr, target_sr=11025)
                sr_a = 11025
            else:
                y_ds = y
                sr_a = sr

            hop_length = 512

            # 1. Spectral Flux
            mel_spec = librosa.feature.melspectrogram(y=y_ds, sr=sr_a, hop_length=hop_length, n_mels=128)
            mel_db = librosa.power_to_db(mel_spec, ref=np.max)
            spectral_flux = np.sum(np.maximum(0, np.diff(mel_db, axis=1)), axis=0)

            # 2. Chromagram-Analyse (10s Fenster)
            window_frames = int(10 * sr_a / hop_length)
            chroma_windows = []
            chroma_times = []

            for i in range(0, len(y_ds), window_frames * hop_length):
                window = y_ds[i:i + window_frames * hop_length]
                # BUG-058 FIX: Konsistente Mindestlaenge (1s) fuer alle Fenster-Analysen
                if len(window) >= sr_a:
                    chroma = librosa.feature.chroma_cqt(y=window, sr=sr_a)
                    chroma_windows.append(np.mean(chroma, axis=1))
                    chroma_times.append(i / sr_a)

            chroma_changes = []
            for i in range(1, len(chroma_windows)):
                cos_dist = 1 - np.dot(chroma_windows[i - 1], chroma_windows[i]) / (
                    np.linalg.norm(chroma_windows[i - 1]) * np.linalg.norm(chroma_windows[i]) + 1e-10
                )
                chroma_changes.append(cos_dist)

            # 3. RMS-Energy-Dips
            rms = librosa.feature.rms(y=y_ds, hop_length=hop_length)[0]
            rms_windows = []
            for i in range(0, len(rms), window_frames):
                w = rms[i:i + window_frames]
                # BUG-058 FIX: Nutze dieselbe Bedingung wie bei Chroma (Mapping-Integritaet)
                if len(w) >= window_frames:
                    rms_windows.append(np.mean(w))

            energy_changes = []
            for i in range(2, len(rms_windows) - 2):
                current = rms_windows[i]
                prev = np.mean(rms_windows[i - 2:i])
                next_val = np.mean(rms_windows[i + 1:i + 3])
                if current < prev * 0.6 and next_val > current * 1.4:
                    dip_strength = (prev - current) + (next_val - current)
                    energy_changes.append((chroma_times[min(i, len(chroma_times) - 1)], dip_strength))

            # 4. Onset-Pattern-Analyse
            onset_strength = librosa.onset.onset_strength(y=y_ds, sr=sr_a, aggregate=np.median)
            onset_pattern_changes = []
            for i in range(window_frames, len(onset_strength), window_frames):
                cp = onset_strength[i - window_frames:i]
                np_ = onset_strength[i:i + window_frames] if i + window_frames < len(onset_strength) else onset_strength[i:]
                if len(np_) > window_frames // 2 and len(cp) == len(np_):
                    corr = np.corrcoef(cp, np_)[0, 1]
                    if np.isnan(corr):
                        corr = 0
                    change = 1 - abs(corr)
                    t = librosa.frames_to_time(np.array([i]), sr=sr_a, hop_length=hop_length)
                    onset_pattern_changes.append((t[0], change))

            # 5. Kombinieren
            spectral_times = librosa.frames_to_time(np.arange(len(spectral_flux)), sr=sr_a, hop_length=hop_length)
            all_candidates = []

            if len(spectral_flux) > 0:
                s_thresh = np.mean(spectral_flux) + 2 * np.std(spectral_flux)
                for t in spectral_times[spectral_flux > s_thresh]:
                    idx = min(int(t * sr_a / hop_length), len(spectral_flux) - 1)
                    all_candidates.append((t, 'spectral', spectral_flux[idx]))

            c_thresh = np.mean(chroma_changes) + 1.5 * np.std(chroma_changes) if chroma_changes else 0
            for i, change in enumerate(chroma_changes):
                if change > c_thresh:
                    all_candidates.append((chroma_times[i + 1], 'harmonic', change))

            for t, strength in energy_changes:
                all_candidates.append((t, 'energy', strength))

            for t, strength in onset_pattern_changes:
                if strength > 0.3:
                    all_candidates.append((t, 'onset_pattern', strength))

            all_candidates.sort()

            # Clustering (±15s)
            clustered = []
            cluster = []
            for c in all_candidates:
                if not cluster or c[0] - cluster[0][0] <= 15:
                    cluster.append(c)
                else:
                    if len(cluster) >= 2:
                        ct = np.mean([x[0] for x in cluster])
                        types = [x[1] for x in cluster]
                        conf = min(1.0, len(set(types)) * 0.3 + len(cluster) * 0.1)
                        t_type = "combined" if len(set(types)) > 1 else types[0]
                        clustered.append({"time": float(ct), "confidence": float(conf), "type": t_type, "duration": 10.0})
                    cluster = [c]

            if len(cluster) >= 2:
                ct = np.mean([x[0] for x in cluster])
                types = [x[1] for x in cluster]
                conf = min(1.0, len(set(types)) * 0.3 + len(cluster) * 0.1)
                t_type = "combined" if len(set(types)) > 1 else types[0]
                clustered.append({"time": float(ct), "confidence": float(conf), "type": t_type, "duration": 10.0})

            # Mindestabstand
            final = []
            for tr in sorted(clustered, key=lambda x: x['time']):
                if not final or tr['time'] - final[-1]['time'] >= min_transition_gap:
                    final.append(tr)

            logger.info(f"Track-Übergänge: {len(final)} erkannt")
            return final

        except Exception as e:
            logger.error(f"Track-Übergangs-Erkennung fehlgeschlagen: {e}")
            return []

    def analyze_energy_phases(self, y: FloatArray, sr: int, window_seconds: float = 10.0) -> dict:
        """Analysiert Energie-Phasen für DJ-Mixes.

        Returns:
            Dict mit energy_curve, energy_times, energy_phases, total_phases
        """
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        rms_max = np.max(rms) + 1e-10
        rms_normalized = rms / rms_max

        window_frames = int(window_seconds * sr / hop_length)
        rms_smoothed = uniform_filter1d(rms_normalized, size=max(3, window_frames // 4))
        times = librosa.frames_to_time(np.arange(len(rms_smoothed)), sr=sr, hop_length=hop_length)

        phases = []
        current_phase_start = 0.0
        current_phase = self._classify_phase(rms_smoothed, 0, window_frames)

        for i in range(window_frames, len(rms_smoothed) - window_frames, window_frames):
            phase = self._classify_phase(rms_smoothed, i, window_frames)
            if phase != current_phase:
                phase_end = times[i] if i < len(times) else times[-1]
                phases.append({
                    "phase": current_phase,
                    "start_time": current_phase_start,
                    "end_time": phase_end,
                    "avg_energy": float(np.mean(rms_smoothed[max(0, i - window_frames):i]))
                })
                current_phase_start = phase_end
                current_phase = phase

        phases.append({
            "phase": current_phase,
            "start_time": current_phase_start,
            "end_time": float(times[-1]) if len(times) > 0 else 0.0,
            "avg_energy": float(np.mean(rms_smoothed[-window_frames:]))
        })

        return {
            "energy_curve": rms_smoothed.tolist(),
            "energy_times": times.tolist(),
            "energy_phases": phases,
            "total_phases": len(phases)
        }

    def _classify_phase(self, energy: np.ndarray, idx: int, window: int) -> str:
        start = max(0, idx - window)
        end = min(len(energy), idx + window)
        current = np.mean(energy[idx:min(idx + window // 2, len(energy))])
        past = np.mean(energy[start:idx]) if idx > start else current
        future = np.mean(energy[idx:end]) if end > idx else current
        trend = future - past

        if current < 0.35:
            return "low_energy"
        elif current > 0.7:
            return "high_energy"
        elif trend > 0.1:
            return "rising"
        elif trend < -0.1:
            return "falling"
        else:
            return "plateau"
