"""Sub-Track-Detection für DJ-Mixes (Plan Phase 1 #4).

Block-4-Pipeline (4 Signale, gewichtete Fusion):
  S1: Foote-Novelty (SSM + Foote-Kernel) via librosa.segment + scipy
  S2: Stem-Aktivität (RMS-Sprünge in instrumental/vocal/drums) — opt. Stem-Output
  S3: Tempo-Drift (sliding-window librosa.beat)
  S4: Spectral-Flux (librosa.onset)

Fusion: 0.35 / 0.30 / 0.20 / 0.15
Peak-Picking: min_distance=60s, adaptive Threshold.

Fallback: 0 Boundaries -> 1 Sub-Track (start..end).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SubtrackBoundary:
    time: float
    confidence: float
    components: dict[str, float]  # raw S1..S4 contributions


@dataclass
class SubtrackResult:
    boundaries: list[SubtrackBoundary]
    segments: list[tuple[float, float, float]]  # (start, end, mean_confidence)
    tempo_curve: list[float]


# Fusion weights from Plan #04
W_FOOTE = 0.35
W_STEM = 0.30
W_TEMPO = 0.20
W_SPECTRAL = 0.15

DEFAULT_SR = 22050
HOP_LENGTH = 512
MIN_DISTANCE_SEC = 60.0


class SubtrackDetector:
    """Heuristische Sub-Track-Erkennung. CPU-only (librosa+scipy)."""

    def __init__(
        self,
        sr: int = DEFAULT_SR,
        hop_length: int = HOP_LENGTH,
        min_distance_sec: float = MIN_DISTANCE_SEC,
    ) -> None:
        self.sr = sr
        self.hop_length = hop_length
        self.min_distance_sec = min_distance_sec

    def detect(
        self,
        audio_path: str | Path,
        stem_paths: Optional[dict[str, str]] = None,
    ) -> SubtrackResult:
        """Detektiert Sub-Track-Boundaries.

        Args:
            audio_path: Pfad zur Mix-Audio-Datei
            stem_paths: optionaler dict mit stem-Output-Pfaden:
                {"vocals": ..., "drums": ..., "bass": ..., "other": ...}
                Wenn vorhanden -> S2 wird mit echten Stem-Aktivitäten berechnet.

        Returns:
            SubtrackResult mit Boundaries, Segments und tempo_curve.
        """
        import librosa

        y, sr = librosa.load(str(audio_path), sr=self.sr, mono=True)
        if y.size == 0:
            return SubtrackResult([], [(0.0, 0.0, 0.0)], [])

        duration = float(len(y)) / sr

        s1, t_axis = self._foote_novelty(y, sr)
        s2 = self._stem_activity(y, sr, stem_paths, t_axis)
        s3, tempo_curve = self._tempo_drift(y, sr, t_axis)
        s4 = self._spectral_flux(y, sr, t_axis)

        s1n = _normalize(s1)
        s2n = _normalize(s2)
        s3n = _normalize(s3)
        s4n = _normalize(s4)

        fused = (
            W_FOOTE * s1n
            + W_STEM * s2n
            + W_TEMPO * s3n
            + W_SPECTRAL * s4n
        )

        peaks = self._pick_peaks(fused, t_axis, duration)

        boundaries: list[SubtrackBoundary] = []
        for idx in peaks:
            t = float(t_axis[idx])
            boundaries.append(
                SubtrackBoundary(
                    time=t,
                    confidence=float(fused[idx]),
                    components={
                        "foote": float(s1n[idx]),
                        "stem": float(s2n[idx]),
                        "tempo": float(s3n[idx]),
                        "spectral": float(s4n[idx]),
                    },
                )
            )

        segments = self._boundaries_to_segments(boundaries, duration)
        return SubtrackResult(
            boundaries=boundaries,
            segments=segments,
            tempo_curve=[float(x) for x in tempo_curve],
        )

    def _foote_novelty(
        self, y: np.ndarray, sr: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """SSM + Foote-Kernel novelty curve.

        Aggregates chroma to ~1 frame/sec for 2h-mix to keep SSM ~7200x7200
        (200 MB) instead of 309k x 309k (75 GB).
        """
        import librosa

        # Compute chroma in chunks to prevent memory spikes on long files
        chunk_size_sec = 300  # 5 minutes
        chunk_samples = chunk_size_sec * sr
        chroma_list = []
        
        starts = list(range(0, y.size, chunk_samples))
        for i, start in enumerate(starts):
            # If this is the last chunk and it's too small (< 2048), process it with the previous one
            if i == len(starts) - 1 and len(y) - start < 2048 and i > 0:
                continue
                
            # Determine end index
            if i == len(starts) - 2 and len(y) - starts[i+1] < 2048:
                end = len(y)
            else:
                end = min(start + chunk_samples, y.size)
                
            y_chunk = y[start:end]
            if len(y_chunk) < 2048:
                if len(y_chunk) == 0:
                    continue
                # If we couldn't merge (e.g. only one chunk), pad it
                pad_len = 2048 - len(y_chunk)
                y_chunk = np.pad(y_chunk, (0, pad_len), mode="constant")
                chroma_chunk = librosa.feature.chroma_cqt(y=y_chunk, sr=sr, hop_length=self.hop_length)
                # Keep only original length frames
                expected_frames = max(1, int(round(len(y) / self.hop_length)))
                chroma_chunk = chroma_chunk[:, :expected_frames]
            else:
                chroma_chunk = librosa.feature.chroma_cqt(
                    y=y_chunk, sr=sr, hop_length=self.hop_length
                )
            chroma_list.append(chroma_chunk)
            
        if chroma_list:
            chroma = np.concatenate(chroma_list, axis=1)
        else:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)

        # Aggregate chroma into ~1-sec bins so SSM stays bounded.
        frames_per_sec = sr / self.hop_length
        bin_frames = max(1, int(round(frames_per_sec)))  # 1 second
        n_chroma = chroma.shape[1]
        n_bins = max(1, n_chroma // bin_frames)
        if bin_frames > 1 and n_bins >= 2:
            trim = n_bins * bin_frames
            agg = chroma[:, :trim].reshape(chroma.shape[0], n_bins, bin_frames).mean(axis=2)
        else:
            agg = chroma
        ssm = self._cosine_ssm(agg.T)

        kernel_size = min(64, max(8, ssm.shape[0] // 4))
        kernel = self._foote_kernel(kernel_size)
        nov = np.zeros(ssm.shape[0], dtype=np.float32)
        half = kernel_size // 2
        padded = np.pad(ssm, ((half, half), (half, half)), mode="edge")
        for i in range(ssm.shape[0]):
            block = padded[i : i + kernel_size, i : i + kernel_size]
            nov[i] = float(np.sum(block * kernel))

        nov = np.maximum(nov, 0.0)
        bin_hop = bin_frames * self.hop_length if bin_frames > 1 else self.hop_length
        t_axis = librosa.frames_to_time(
            np.arange(nov.size), sr=sr, hop_length=bin_hop
        )
        return nov, t_axis

    def _stem_activity(
        self,
        y: np.ndarray,
        sr: int,
        stem_paths: Optional[dict[str, str]],
        t_axis: np.ndarray,
    ) -> np.ndarray:
        """RMS-Aktivitäts-Sprünge. Wenn keine stems verfügbar -> Mix-RMS-Sprünge."""
        import librosa

        if stem_paths:
            stem_rms_list = []
            chunk_size_sec = 300  # 5-Minuten-Chunks zur Begrenzung des RAM-Verbrauchs (T018)
            for name in ("vocals", "drums", "bass", "other"):
                p = stem_paths.get(name)
                if p and Path(p).is_file():
                    try:
                        total_dur = float(librosa.get_duration(path=str(p)))
                        rms_chunks = []
                        # Chunkweise laden und RMS berechnen
                        for offset in range(0, int(total_dur), chunk_size_sec):
                            dur = min(chunk_size_sec, total_dur - offset)
                            s_chunk, _ = librosa.load(
                                str(p),
                                sr=sr,
                                mono=True,
                                offset=offset,
                                duration=dur,
                            )
                            if s_chunk.size > 0:
                                rms_chunk = librosa.feature.rms(
                                    y=s_chunk, hop_length=self.hop_length
                                )[0]
                                rms_chunks.append(rms_chunk)
                        
                        if rms_chunks:
                            rms = np.concatenate(rms_chunks)
                            stem_rms_list.append(rms)
                    except Exception as e:
                        logger.warning(f"Fehler bei chunked RMS-Berechnung fuer {name}: {e}")

            if stem_rms_list:
                # Da die concatenate-Teile eventuell minimal unterschiedliche Längen haben,
                # bringen wir alle RMS-Arrays auf die gleiche Länge (die des kürzesten).
                min_len = min(rms.size for rms in stem_rms_list)
                truncated_list = [rms[:min_len] for rms in stem_rms_list]
                stacked = np.stack(truncated_list, axis=0)
            else:
                stacked = librosa.feature.rms(y=y, hop_length=self.hop_length)
        else:
            stacked = librosa.feature.rms(y=y, hop_length=self.hop_length)

        # per-stem absolute first difference, summed
        diffs = np.abs(np.diff(stacked, axis=-1))
        stem_signal = np.sum(diffs, axis=0)
        # Interpolation auf t_axis, um Stauchung/Abschneiden zu verhindern
        if stem_signal.size and t_axis.size:
            times = np.arange(stem_signal.size) * (self.hop_length / sr)
            out = np.interp(t_axis, times, stem_signal).astype(np.float32)
        else:
            out = np.zeros(t_axis.size, dtype=np.float32)
        return out


    def _tempo_drift(
        self, y: np.ndarray, sr: int, t_axis: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Sliding-window tempo. Drift-Magnitude = absolute Diff zwischen Fenstern."""
        import librosa

        win_sec = 8.0
        hop_sec = 1.0
        win_samples = int(win_sec * sr)
        hop_samples = int(hop_sec * sr)
        if y.size < win_samples * 2:
            return np.zeros(t_axis.size, dtype=np.float32), np.array([])

        tempos = []
        centers = []
        for start in range(0, y.size - win_samples, hop_samples):
            seg = y[start : start + win_samples]
            try:
                t, _ = librosa.beat.beat_track(y=seg, sr=sr)
                t_arr = np.asarray(t).reshape(-1)
                tempos.append(float(t_arr.item()) if t_arr.size == 1 else float(t_arr[0]))
            except Exception:
                tempos.append(0.0)
            centers.append((start + win_samples / 2) / sr)
        tempo_arr = np.asarray(tempos, dtype=np.float32)
        center_arr = np.asarray(centers, dtype=np.float32)

        drift = np.zeros_like(tempo_arr)
        if tempo_arr.size > 1:
            drift[1:] = np.abs(np.diff(tempo_arr))

        # interpolate drift onto t_axis
        if center_arr.size == 0:
            interp = np.zeros(t_axis.size, dtype=np.float32)
        else:
            interp = np.interp(t_axis, center_arr, drift).astype(np.float32)
        return interp, tempo_arr

    def _spectral_flux(
        self, y: np.ndarray, sr: int, t_axis: np.ndarray
    ) -> np.ndarray:
        """Onset-Strength-Envelope -> als Spectral-Flux-Surrogat."""
        import librosa

        flux = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )
        # Interpolation auf t_axis, um Stauchung/Abschneiden zu verhindern
        if flux.size and t_axis.size:
            times = np.arange(flux.size) * (self.hop_length / sr)
            out = np.interp(t_axis, times, flux).astype(np.float32)
        else:
            out = np.zeros(t_axis.size, dtype=np.float32)
        return out

    def _pick_peaks(
        self,
        fused: np.ndarray,
        t_axis: np.ndarray,
        duration: float,
    ) -> list[int]:
        """Adaptive Threshold + min-distance Peak-Picking."""
        from scipy.signal import find_peaks

        if fused.size == 0:
            return []
        median = float(np.median(fused))
        std = float(np.std(fused))
        height = median + std

        if t_axis.size > 1:
            sec_per_frame = float(t_axis[1] - t_axis[0])
            if sec_per_frame <= 0:
                sec_per_frame = duration / max(t_axis.size, 1)
        else:
            sec_per_frame = duration / max(fused.size, 1)
        distance_frames = max(1, int(self.min_distance_sec / max(sec_per_frame, 1e-6)))

        peaks, _ = find_peaks(fused, height=height, distance=distance_frames)
        return [int(p) for p in peaks]

    def _boundaries_to_segments(
        self, boundaries: list[SubtrackBoundary], duration: float
    ) -> list[tuple[float, float, float]]:
        if not boundaries:
            return [(0.0, duration, 0.0)]
        times = [b.time for b in boundaries]
        confs = [b.confidence for b in boundaries]
        segs: list[tuple[float, float, float]] = []
        prev = 0.0
        for i, t in enumerate(times):
            segs.append((prev, t, confs[i]))
            prev = t
        segs.append((prev, duration, confs[-1] if confs else 0.0))
        return segs

    @staticmethod
    def _cosine_ssm(features: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(features, axis=1, keepdims=True) + 1e-9
        normed = features / norms
        ssm = normed @ normed.T
        return ssm.astype(np.float32)

    @staticmethod
    def _foote_kernel(size: int) -> np.ndarray:
        half = size // 2
        k = np.zeros((size, size), dtype=np.float32)
        # checkerboard kernel: +1 on diagonal blocks, -1 on anti-diagonal blocks
        k[:half, :half] = 1.0
        k[half:, half:] = 1.0
        k[:half, half:] = -1.0
        k[half:, :half] = -1.0
        # gaussian taper
        x = np.arange(size) - (size - 1) / 2.0
        g = np.exp(-(x ** 2) / (2 * (size / 4.0) ** 2))
        k *= np.outer(g, g)
        return k


def _normalize(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    mx = float(np.max(x))
    if mx <= 0:
        return np.zeros_like(x, dtype=np.float32)
    return (x / mx).astype(np.float32)
