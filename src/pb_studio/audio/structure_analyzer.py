"""Structure-Analyzer - Erkennung von Song-Abschnitten.

Segment-Boundary-Detection, Feature-Extraktion, Clustering und Label-Zuweisung.

AMD-Version: Rein CPU-basiert mit librosa + sklearn.
"""

from typing import Any, Callable, Dict, List

import librosa
import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter1d
from sklearn.cluster import AgglomerativeClustering

import logging

logger = logging.getLogger(__name__)

FloatArray = NDArray[np.floating]

SEGMENT_LABELS = {
    "intro": "Intro", "verse": "Verse", "chorus": "Chorus",
    "bridge": "Bridge", "drop": "Drop", "buildup": "Buildup",
    "breakdown": "Breakdown", "outro": "Outro",
}


class StructureAnalyzer:
    """Analyse der Song-Struktur (Segmente, Labels).

    Verwendet Novelty-Detection, Feature-Extraktion, Clustering
    und Energie-basiertes Labeling für Verse, Chorus, Bridge, etc.
    """

    def __init__(self, sr_default: int = 22050, progress_callback=None):
        self.sr_default = sr_default
        self._progress_callback = progress_callback

    def _report_progress(self, phase: str, progress: float) -> None:
        if self._progress_callback:
            self._progress_callback(phase, progress)

    # ------------------------------------------------------------------
    # Boundary detection
    # ------------------------------------------------------------------

    def _detect_boundaries(self, y: FloatArray, sr: int) -> FloatArray:
        """Erkennt Segment-Grenzen mittels Checkerboard-Kernel Novelty."""
        hop_length = 512
        duration = librosa.get_duration(y=y, sr=sr)

        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop_length, n_mfcc=13)

        features = np.vstack([
            librosa.util.normalize(chroma, axis=1),
            librosa.util.normalize(mfcc, axis=1)
        ])
        del chroma, mfcc

        max_frames = 5000
        if features.shape[1] > max_frames:
            original_num_frames = features.shape[1]
            indices = np.linspace(0, original_num_frames - 1, max_frames, dtype=int)
            features = features[:, indices]
            # Jedes Downsampled-Frame repräsentiert original_num_frames/max_frames Originals.
            # effective_hop muss entsprechend skaliert werden, damit
            # librosa.frames_to_time() die richtigen Zeiten liefert.
            effective_hop = hop_length * (original_num_frames / max_frames)
        else:
            effective_hop = hop_length

        try:
            rec = librosa.segment.recurrence_matrix(
                features, mode='affinity', metric='cosine', sparse=True
            )
            rec_dense = rec.toarray()

            kernel_size = min(64, features.shape[1] // 10)
            if kernel_size < 4:
                kernel_size = 4

            novelty = self._checkerboard_novelty(rec_dense, kernel_size)
            novelty_smooth = uniform_filter1d(novelty, size=5)

            if np.max(novelty_smooth) > 0:
                novelty_smooth = novelty_smooth / np.max(novelty_smooth)

            peaks = librosa.util.peak_pick(
                novelty_smooth, pre_max=7, post_max=7,
                pre_avg=7, post_avg=7, delta=0.1, wait=10
            )

            times = librosa.frames_to_time(peaks, sr=sr, hop_length=int(effective_hop))
            boundaries = np.concatenate([[0.0], times, [duration]])
            boundaries = np.unique(boundaries)
            boundaries.sort()

            # Zu kurze Segmente entfernen (< 8s)
            min_seg = 8.0
            filtered = [boundaries[0]]
            for b in boundaries[1:]:
                if b - filtered[-1] >= min_seg:
                    filtered.append(b)
                elif b == boundaries[-1]:
                    if len(filtered) > 1:
                        filtered[-1] = b
                    else:
                        filtered.append(b)

            logger.info(f"Segment-Grenzen: {len(filtered) - 1} Segmente")
            return np.array(filtered)

        except Exception as e:
            logger.warning(f"Boundary Detection fehlgeschlagen: {e}, nutze Fallback")
            num_segments = max(1, int(duration / 30))
            return np.linspace(0, duration, num_segments + 1)

    def _checkerboard_novelty(self, rec_matrix: FloatArray, kernel_size: int = 64) -> FloatArray:
        n = rec_matrix.shape[0]
        half_k = kernel_size // 2

        # Original loop bound is for i in range(half_k, n - half_k)
        # So we extract windows of size 2 * half_k
        window_size = 2 * half_k

        kernel = np.ones((kernel_size, kernel_size))
        kernel[:half_k, :half_k] = -1
        kernel[half_k:, half_k:] = -1
        novelty = np.zeros(n)

        if n < window_size:
            return novelty

        stride_bytes = rec_matrix.strides[0]

        # Number of sliding windows must exactly match the number of loop iterations
        # The loop iterations are from half_k to n - half_k, so length is n - 2*half_k
        num_windows = n - window_size

        # Ensure we don't try to stride negative shapes if n == window_size
        if num_windows <= 0:
            return novelty

        windows = np.lib.stride_tricks.as_strided(
            rec_matrix,
            shape=(num_windows, window_size, window_size),
            strides=(stride_bytes + rec_matrix.strides[1], stride_bytes, rec_matrix.strides[1])
        )

        # The window kernel must match the extracted window_size exactly
        sub_kernel = kernel[:window_size, :window_size]

        novelty[half_k : n - half_k] = np.abs(
            np.tensordot(windows, sub_kernel, axes=([1, 2], [0, 1]))
        )

        return novelty

    # ------------------------------------------------------------------
    # Segment feature extraction
    # ------------------------------------------------------------------

    def _extract_segment_features(self, y: FloatArray, sr: int, boundaries: FloatArray) -> FloatArray:
        features = []
        for i in range(len(boundaries) - 1):
            start_sample = int(boundaries[i] * sr)
            end_sample = int(boundaries[i + 1] * sr)
            segment = y[start_sample:end_sample]
            if len(segment) < 2048:
                segment = np.pad(segment, (0, 2048 - len(segment)), mode='constant')

            chroma = librosa.feature.chroma_cqt(y=segment, sr=sr)
            mfcc = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=13)
            rms = librosa.feature.rms(y=segment)
            sc = librosa.feature.spectral_contrast(y=segment, sr=sr)
            cent = librosa.feature.spectral_centroid(y=segment, sr=sr)

            fv = np.concatenate([
                np.mean(chroma, axis=1), np.std(chroma, axis=1),
                np.mean(mfcc, axis=1), np.std(mfcc, axis=1),
                [np.mean(rms), np.std(rms)],
                np.mean(sc, axis=1),
                [np.mean(cent), np.std(cent)]
            ])
            features.append(fv)
        return np.array(features)

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def _cluster_segments(self, features: FloatArray) -> FloatArray:
        if len(features) < 2:
            return np.array([0] * len(features))
        n_clusters = min(max(3, len(features) // 2), 8)
        n_clusters = min(n_clusters, len(features))
        try:
            clustering = AgglomerativeClustering(
                n_clusters=n_clusters, metric='euclidean', linkage='ward'
            )
            return clustering.fit_predict(features)
        except Exception as e:
            logger.warning(f"Clustering fehlgeschlagen: {e}")
            return np.arange(len(features))

    # ------------------------------------------------------------------
    # Label assignment
    # ------------------------------------------------------------------

    def _assign_labels(
        self, y: FloatArray, sr: int, boundaries: FloatArray, cluster_labels: FloatArray
    ) -> List[str]:
        labels = []
        duration = len(y) / sr
        is_dj_mix = duration > 600

        transitions = []
        if is_dj_mix:
            from .dj_mix_analyzer import DJMixAnalyzer
            mix_analyzer = DJMixAnalyzer(sr_default=sr)
            transitions = mix_analyzer.detect_mix_transitions(y, sr)

            hop_length = 1024
            full_rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            rms_times = librosa.frames_to_time(np.arange(len(full_rms)), sr=sr, hop_length=hop_length)
            smoothed_rms = uniform_filter1d(full_rms, size=max(3, len(full_rms) // 200))
            global_rms = np.mean(smoothed_rms)
            max_rms = np.max(smoothed_rms)
        else:
            global_rms = np.mean(librosa.feature.rms(y=y))

        cluster_label_map: Dict[int, str] = {}

        for i, (cluster, start, end) in enumerate(
            zip(cluster_labels, boundaries[:-1], boundaries[1:])
        ):
            segment = y[int(start * sr):int(end * sr)]
            if len(segment) < 512:
                segment = np.pad(segment, (0, 512 - len(segment)), mode='constant')
            segment_rms = np.mean(librosa.feature.rms(y=segment))
            relative_pos = start / duration
            segment_duration = end - start

            if is_dj_mix:
                is_transition = any(
                    abs(start - t['time']) <= 15 or abs(end - t['time']) <= 15
                    for t in transitions
                )
                if is_transition:
                    label = "transition"
                else:
                    start_idx = np.searchsorted(rms_times, start)
                    end_idx = np.searchsorted(rms_times, end)
                    if end_idx > start_idx and end_idx < len(smoothed_rms):
                        seg_rms = smoothed_rms[start_idx:end_idx]
                        if len(seg_rms) > 2:
                            trend = np.polyfit(range(len(seg_rms)), seg_rms, 1)[0]
                            avg = np.mean(seg_rms)
                            var = np.var(seg_rms)
                            if var > max_rms * 0.1:
                                label = "transition"
                            elif avg > global_rms * 1.5:
                                label = "peak"
                            elif avg > global_rms * 1.2:
                                label = "high_energy"
                            elif trend > global_rms * 0.02:
                                label = "rising"
                            elif trend < -global_rms * 0.02:
                                label = "falling"
                            elif avg < global_rms * 0.7:
                                label = "low_energy"
                            else:
                                label = "plateau"
                        else:
                            label = "high_energy" if segment_rms > global_rms * 1.3 else "plateau"
                    else:
                        label = "high_energy" if segment_rms > global_rms * 1.3 else "plateau"
            else:
                if relative_pos < 0.08:
                    label = "intro"
                elif relative_pos > 0.92:
                    label = "outro"
                elif segment_rms > global_rms * 1.3:
                    label = "drop" if segment_duration < 15 else "chorus"
                elif segment_rms < global_rms * 0.6:
                    label = "breakdown" if segment_duration < 20 else "bridge"
                elif segment_rms > global_rms * 1.1:
                    if i < len(boundaries) - 2:
                        ns = y[int(boundaries[i + 1] * sr):int(boundaries[i + 2] * sr)]
                        if len(ns) > 512:
                            nr = np.mean(librosa.feature.rms(y=ns))
                            label = "buildup" if nr > segment_rms * 1.2 else "verse"
                        else:
                            label = "verse"
                    else:
                        label = "verse"
                else:
                    label = "verse"

            if not is_dj_mix:
                ci = int(cluster)
                if ci in cluster_label_map:
                    if label not in ("intro", "outro"):
                        label = cluster_label_map[ci]
                else:
                    if label not in ("intro", "outro"):
                        cluster_label_map[ci] = label

            labels.append(label)
        return labels

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze_song_structure(
        self, y: FloatArray, sr: int, num_segments: int = 10,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> dict:
        """Analysiert Song-Struktur (Segmente und Labels).

        Args:
            y: Audio-Daten (Numpy-Array)
            sr: Samplerate
            num_segments: Ziel-Anzahl Segmente (Hinweis)
            progress_callback: Optionaler Callback (phase, progress)

        Returns:
            Dict mit total_segments und segments Liste
        """
        cb = progress_callback or self._progress_callback
        if cb:
            cb("structure_start", 0.0)

        try:
            duration = librosa.get_duration(y=y, sr=sr)

            boundaries = self._detect_boundaries(y, sr)
            segment_features = self._extract_segment_features(y, sr, boundaries)

            if len(segment_features) > 1:
                cluster_labels = self._cluster_segments(segment_features)
            else:
                cluster_labels = np.array([0])

            named_labels = self._assign_labels(y, sr, boundaries, cluster_labels)

            segments = []
            for i in range(len(boundaries) - 1):
                segments.append({
                    "segment_id": i + 1,
                    "start_time": float(boundaries[i]),
                    "end_time": float(boundaries[i + 1]),
                    "duration": float(boundaries[i + 1] - boundaries[i]),
                    "label": named_labels[i],
                    "cluster": int(cluster_labels[i]) if i < len(cluster_labels) else 0,
                    "confidence": 0.7
                })

            result = {"total_segments": len(segments), "segments": segments}

            label_counts = {}
            for seg in segments:
                lbl = seg["label"]
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
            logger.info(f"Song-Struktur: {result['total_segments']} Segmente, Labels: {label_counts}")

            if cb:
                cb("structure_done", 1.0)
            return result

        except Exception as e:
            logger.error(f"Struktur-Analyse fehlgeschlagen: {e}", exc_info=True)
            return {
                "total_segments": 1,
                "segments": [{
                    "segment_id": 1, "start_time": 0.0,
                    "end_time": float(librosa.get_duration(y=y, sr=sr)),
                    "duration": float(librosa.get_duration(y=y, sr=sr)),
                    "label": "verse", "cluster": 0, "confidence": 0.3
                }]
            }
