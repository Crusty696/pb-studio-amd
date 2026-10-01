"""Sub-Track-Detection für DJ-Mixes (Plan Phase 1 #4).

Block-4-Pipeline (4 Signale, gewichtete Fusion):
  S1: Foote-Novelty (SSM + Foote-Kernel) via librosa.segment + scipy
  S2: Stem-Aktivität (RMS-Sprünge in instrumental/vocal/drums) — opt. Stem-Output
  S3: Tempo-Drift (sliding-window librosa.beat)
  S4: Spectral-Flux (librosa.onset)

Fusion: 0.35 / 0.30 / 0.20 / 0.15
Peak-Picking: min_distance=60s, adaptive Threshold.

Das gilt nur noch fuer Dateien bis 10 min. Lange Mixe (der eigentliche
Anwendungsfall) laufen seit T003 (2026-10-01) ueber eine optimale Zerlegung
der Chroma-Aehnlichkeit plus genaue Tempostufe - Begruendung und Messwerte in
`_long_mix_boundaries`.

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

# Langer-Mix-Pfad (T003) - Herleitung in `_long_mix_boundaries`.
NOVELTY_BIN_SEC = 4.0
# Zerlegung (2026-10-01): Preis je Grenze aus dem Plateau 14-24 an fuenf
# Referenzmixen gewaehlt, an zwei weiteren unberuehrt geprueft; Abschnitte
# 2-15 min (kuerzer spielt kaum ein DJ einen Titel, laenger dauert kaum ein
# Titel). Ein laengerer Einzeltitel wird zwangsweise geteilt.
PARTITION_PENALTY = 18.0
PARTITION_MIN_SEC = 120.0
PARTITION_MAX_SEC = 900.0
TEMPO_MERGE_SEC = 45.0
LONG_MIX_MIN_DISTANCE_SEC = 90.0
TRACK_PEAK_PROMINENCE = 0.45
TEMPO_WINDOW_SEC = 20.0
TEMPO_HOP_SEC = 10.0
TEMPO_MIN_WINDOW_SEC = 8.0
TEMPO_MEDIAN_SEC = 30.0
TEMPO_STEP_SIDE_SEC = 20.0
TEMPO_STEP_MIN_BPM = 0.3
TEMPO_STEP_RANGE_BPM = 0.5


class SubtrackDetector:
    """Heuristische Sub-Track-Erkennung. CPU-only (librosa+scipy)."""

    LONG_MIX_THRESHOLD_SEC = 600.0
    LONG_MIX_CHUNK_SEC = 120.0
    MAX_SSM_FRAMES = 2048

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

        try:
            duration = float(librosa.get_duration(path=str(audio_path)))
        except Exception as exc:
            raise RuntimeError(
                f"Audio-Dauer fuer Subtrack-Erkennung nicht ermittelbar: {audio_path}"
            ) from exc

        if duration > self.LONG_MIX_THRESHOLD_SEC:
            return self._detect_long_mix(audio_path, duration, stem_paths)

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

    def _detect_long_mix(
        self,
        audio_path: str | Path,
        duration: float,
        stem_paths: Optional[dict[str, str]],
    ) -> SubtrackResult:
        """Bounded long-mix path: chunked decode and capped SSM resolution."""
        chroma, activity, flux, tempo = self._bounded_chunk_features(
            audio_path,
            duration,
            stem_paths,
        )
        if chroma.shape[1] == 0:
            return SubtrackResult([], [(0.0, duration, 0.0)], [])
        boundaries = self._long_mix_boundaries(chroma, activity, flux, tempo, duration)
        return SubtrackResult(
            boundaries=boundaries,
            segments=self._boundaries_to_segments(boundaries, duration),
            tempo_curve=[float(value) for value in tempo],
        )

    def _long_mix_boundaries(
        self,
        chroma: np.ndarray,
        activity: np.ndarray,
        flux: np.ndarray,
        tempo: np.ndarray,
        duration: float,
    ) -> list[SubtrackBoundary]:
        """Titelwechsel aus Sekunden-Features eines langen Mixes.

        T003 (2026-09-30): die alte gewichtete Summe aus Foote(0,35)/RMS-
        Spruengen(0,30)/beat_track-Tempo(0,20)/Flux(0,15) fand an einem
        59-min-Referenzmix 23 statt 9 Grenzen (F1 0,375): RMS und Flux
        markieren Breaks und Drops innerhalb eines Titels, `beat_track` liefert
        je Block nur Attraktorwerte, der kurze Foote-Kern sieht Abschnitte.

        T003 (2026-10-01), aktueller Weg - zwei unabhaengige Hinweise:
          (a) **Optimale Zerlegung der Chroma-Aehnlichkeit**
              (`_optimal_partition`): der Mix wird so in Abschnitte von
              2-15 min zerlegt, dass die Frames innerhalb eines Abschnitts
              einander moeglichst aehnlich sind, mit einem festen Preis je
              Grenze. Ein Titel wiederholt seine Harmonien ueber die ganze
              Laenge, ein Break aendert daran wenig.
          (b) **Tempostufe** aus dem genauen Beatgrid-Schaetzer, nur fuer
              Mixe, deren Titel nicht auf ein Tempo gezogen sind; sie ergaenzt
              Grenzen, die (a) nicht innerhalb von `TEMPO_MERGE_SEC` hat.

        Der Vorgaenger (Wiederholungs-Neuheit, Foote-Kern +-128 s, Spitzen
        per Prominenz relativ zur groessten Spitze) erreichte an
        beatgematchten Referenzmixen F1 0,44-0,70: eine einzelne starke
        Spitze drueckte die uebrigen unter die Schwelle, und der lokale Kern
        verortete Grenzen bis zu 40 s daneben. Messung und Grenzen:
        specs/00035-full-audit-remediation/evidence/t003-boundaries-20261001.md.
        """
        chroma, activity, flux, tempo = self._group_features(
            chroma, activity, flux, tempo, duration
        )
        chroma, activity, flux, tempo = self._cap_feature_resolution(
            chroma,
            activity,
            flux,
            tempo,
        )
        n_frames = chroma.shape[1]
        frame_sec = duration / float(n_frames)
        # Bin-Mitten statt Bin-Anfaenge: bei 4-s-Bins sonst 2 s systematisch zu frueh.
        t_axis = (np.arange(n_frames, dtype=np.float64) + 0.5) * frame_sec

        similarity = self._frame_similarity(chroma)
        cuts = self._optimal_partition(similarity, frame_sec)
        contrast = self._cut_contrast(similarity, cuts)
        s_tempo = self._tempo_step_novelty(tempo, frame_sec)
        activity_n = _normalize(activity)
        flux_n = _normalize(flux)

        # (Zeit, Frame, Konfidenz, Kontrast der Zerlegung)
        found: list[tuple[float, int, float, float]] = [
            (cut * frame_sec, min(cut, n_frames - 1), value, value)
            for cut, value in zip(cuts, contrast)
        ]
        for peak in self._pick_track_peaks(s_tempo, frame_sec):
            t = float(t_axis[peak])
            if all(abs(t - item[0]) > TEMPO_MERGE_SEC for item in found):
                found.append((t, int(peak), float(s_tempo[peak]), 0.0))
        found.sort()
        return [
            SubtrackBoundary(
                time=float(time),
                confidence=float(np.clip(confidence, 0.0, 1.0)),
                components={
                    "foote": float(np.clip(split, 0.0, 1.0)),
                    "stem": float(activity_n[index]),
                    "tempo": float(s_tempo[index]),
                    "spectral": float(flux_n[index]),
                },
            )
            for time, index, confidence, split in found
        ]

    @staticmethod
    def _frame_similarity(chroma: np.ndarray) -> np.ndarray:
        """Kosinus-Aehnlichkeit der je Tonklasse standardisierten Chroma-Frames."""
        x = np.asarray(chroma, dtype=np.float64)
        x = (x - x.mean(axis=1, keepdims=True)) / (x.std(axis=1, keepdims=True) + 1e-9)
        x = x.T
        x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
        return x @ x.T

    @staticmethod
    def _optimal_partition(similarity: np.ndarray, frame_sec: float) -> list[int]:
        """Grenzen (Frame-Indizes) der besten Zerlegung in homogene Abschnitte.

        Bewertung eines Abschnitts [i, j): Summe seiner Aehnlichkeiten geteilt
        durch seine Laenge (Kernel-k-means). Ein Abschnitt, der zwei Titel
        ueberspannt, verliert die Kreuzterme; eine Teilung innerhalb eines
        Titels gewinnt nichts. Jede Grenze kostet `PARTITION_PENALTY`
        (in 4-s-Frame-Einheiten, damit die Wahl nicht von der Aufloesung
        abhaengt). Dynamische Programmierung ueber alle Zerlegungen mit
        Abschnitten von `PARTITION_MIN_SEC` bis `PARTITION_MAX_SEC` -
        O(n * max_len), bei 2048 Frames unter einer Sekunde.

        Gemessen an sieben Referenzmixen mit exakten Grenzen (Plateau
        Preis 14-24, gewaehlt 18); Einzelwerte im Beleg.
        """
        m = similarity.shape[0]
        lo = max(1, int(PARTITION_MIN_SEC / frame_sec))
        hi = max(lo, int(PARTITION_MAX_SEC / frame_sec))
        if m < 2 * lo:
            return []
        scale = frame_sec / NOVELTY_BIN_SEC
        prefix = np.zeros((m + 1, m + 1), dtype=np.float64)
        prefix[1:, 1:] = similarity.cumsum(axis=0).cumsum(axis=1)
        best = np.full(m + 1, -np.inf)
        best[0] = 0.0
        back = np.zeros(m + 1, dtype=np.int64)
        for j in range(lo, m + 1):
            starts = np.arange(max(0, j - hi), j - lo + 1)
            block = prefix[j, j] - prefix[starts, j] - prefix[j, starts] + prefix[starts, starts]
            value = best[starts] + scale * block / (j - starts) - PARTITION_PENALTY
            k = int(np.argmax(value))
            best[j], back[j] = value[k], starts[k]
        if not np.isfinite(best[m]):
            return []
        cuts: list[int] = []
        j = m
        while j > 0:
            j = int(back[j])
            if j > 0:
                cuts.append(j)
        return sorted(cuts)

    @staticmethod
    def _cut_contrast(similarity: np.ndarray, cuts: list[int]) -> list[float]:
        """Je Grenze: mittlere Aehnlichkeit innerhalb der Nachbarn minus zwischen ihnen."""
        edges = [0, *cuts, similarity.shape[0]]
        out: list[float] = []
        for k in range(1, len(edges) - 1):
            a = slice(edges[k - 1], edges[k])
            b = slice(edges[k], edges[k + 1])
            within = 0.5 * (float(similarity[a, a].mean()) + float(similarity[b, b].mean()))
            out.append(within - float(similarity[a, b].mean()))
        return out

    def _bounded_chunk_features(
        self,
        audio_path: str | Path,
        duration: float,
        stem_paths: Optional[dict[str, str]],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract approximately one feature frame/second without full decode."""
        import librosa

        chroma_parts: list[np.ndarray] = []
        activity_parts: list[np.ndarray] = []
        flux_parts: list[np.ndarray] = []
        tempo_parts: list[np.ndarray] = []
        offset = 0.0
        while offset < duration:
            chunk_duration = min(self.LONG_MIX_CHUNK_SEC, duration - offset)
            y, sr = librosa.load(
                str(audio_path),
                sr=self.sr,
                mono=True,
                offset=offset,
                duration=chunk_duration,
            )
            if y.size == 0:
                offset += chunk_duration
                continue

            chroma = librosa.feature.chroma_cqt(
                y=y,
                sr=sr,
                hop_length=self.hop_length,
            )
            rms_sources = [
                librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
            ]
            if stem_paths:
                rms_sources = []
                for name in ("vocals", "drums", "bass", "other"):
                    stem_path = stem_paths.get(name)
                    if not stem_path or not Path(stem_path).is_file():
                        continue
                    stem, _ = librosa.load(
                        str(stem_path),
                        sr=sr,
                        mono=True,
                        offset=offset,
                        duration=chunk_duration,
                    )
                    if stem.size:
                        rms_sources.append(
                            librosa.feature.rms(
                                y=stem,
                                hop_length=self.hop_length,
                            )[0]
                        )
                if not rms_sources:
                    rms_sources = [
                        librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
                    ]

            min_rms = min(value.size for value in rms_sources)
            rms = np.mean(
                np.stack([value[:min_rms] for value in rms_sources]),
                axis=0,
            )
            activity = np.abs(np.diff(rms, prepend=rms[:1]))
            onset = librosa.onset.onset_strength(
                y=y,
                sr=sr,
                hop_length=self.hop_length,
            )
            frames_per_bin = max(1, int(round(sr / self.hop_length)))
            chroma_binned = self._mean_bin_2d(chroma, frames_per_bin)
            n_bins = chroma_binned.shape[1]
            activity_parts.append(
                self._mean_bin_1d(activity, frames_per_bin, n_bins)
            )
            flux_parts.append(self._mean_bin_1d(onset, frames_per_bin, n_bins))
            chroma_parts.append(chroma_binned)
            tempo_parts.append(
                self._window_tempo_bins(y, sr, n_bins, frames_per_bin * self.hop_length / sr)
            )
            offset += chunk_duration

        if not chroma_parts:
            empty = np.array([], dtype=np.float32)
            return np.empty((12, 0), dtype=np.float32), empty, empty, empty
        return (
            np.concatenate(chroma_parts, axis=1).astype(np.float32),
            np.concatenate(activity_parts).astype(np.float32),
            np.concatenate(flux_parts).astype(np.float32),
            np.concatenate(tempo_parts).astype(np.float32),
        )

    @staticmethod
    def _window_tempo_bins(
        y: np.ndarray, sr: int, n_bins: int, bin_sec: float
    ) -> np.ndarray:
        """Genaues Tempo je Fenster, auf die Sekunden-Bins verteilt; 0 = unbekannt.

        Ersetzt `librosa.beat.beat_track` je 120-s-Block (nur Attraktorwerte,
        siehe `_detect_long_mix`). Fenster ohne sitzendes Raster (Kontrast unter
        `GRID_CONTRAST_MIN`, typisch Breakdowns ohne Kick) bleiben unbekannt,
        statt ein zufaelliges Tempo als Stufe einzutragen.
        """
        from pb_studio.audio.beat_grid import GRID_CONTRAST_MIN, estimate_beat_grid

        out = np.zeros(n_bins, dtype=np.float32)
        win = int(TEMPO_WINDOW_SEC * sr)
        hop = int(TEMPO_HOP_SEC * sr)
        if n_bins == 0 or y.size < int(TEMPO_MIN_WINDOW_SEC * sr) or hop <= 0:
            return out
        starts = range(0, y.size - win + 1, hop) if y.size >= win else [0]
        centers: list[float] = []
        tempos: list[float] = []
        for start in starts:
            segment = y[start:start + win]
            try:
                grid = estimate_beat_grid(segment, sr)
            except Exception as exc:  # pragma: no cover - defensive, logged
                logger.debug("Fenster-Tempo fehlgeschlagen: %s", exc)
                continue
            if grid.bpm > 0.0 and grid.contrast >= GRID_CONTRAST_MIN:
                centers.append((start + segment.size / 2.0) / sr)
                tempos.append(float(grid.bpm))
        if not tempos:
            return out
        bin_centers = (np.arange(n_bins) + 0.5) * bin_sec
        center_arr = np.asarray(centers)
        nearest = np.abs(bin_centers[:, None] - center_arr[None, :]).argmin(axis=1)
        return np.asarray(tempos, dtype=np.float32)[nearest]

    def _group_features(
        self,
        chroma: np.ndarray,
        activity: np.ndarray,
        flux: np.ndarray,
        tempo: np.ndarray,
        duration: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Sekunden-Bins zu ~`NOVELTY_BIN_SEC` zusammenfassen (Tempo: Median der bekannten)."""
        n = chroma.shape[1]
        size = int(round(NOVELTY_BIN_SEC / max(duration / max(n, 1), 1e-6)))
        if size <= 1 or n < 2 * size:
            return chroma, activity, flux, tempo
        groups = n // size
        cut = groups * size

        def _mean(values: np.ndarray) -> np.ndarray:
            return values[..., :cut].reshape(*values.shape[:-1], groups, size).mean(axis=-1)

        tempo_groups = tempo[:cut].reshape(groups, size)
        grouped_tempo = np.asarray(
            [float(np.median(row[row > 0])) if np.any(row > 0) else 0.0 for row in tempo_groups],
            dtype=np.float32,
        )
        return (
            _mean(chroma).astype(np.float32),
            _mean(activity).astype(np.float32),
            _mean(flux).astype(np.float32),
            grouped_tempo,
        )

    @staticmethod
    def _tempo_step_novelty(tempo: np.ndarray, frame_sec: float) -> np.ndarray:
        """Tempostufe zwischen den Medianen links/rechts, auf [0, 1] abgebildet."""
        from scipy.ndimage import median_filter

        n = tempo.size
        out = np.zeros(n, dtype=np.float32)
        known = tempo > 0
        if n < 3 or np.count_nonzero(known) < 2:
            return out
        index = np.arange(n)
        filled = np.interp(index, index[known], tempo[known])
        size = max(1, int(round(TEMPO_MEDIAN_SEC / frame_sec)) // 2 * 2 + 1)
        smooth = median_filter(filled, size=size, mode="nearest")
        side = max(1, int(round(TEMPO_STEP_SIDE_SEC / frame_sec)))
        for i in range(1, n):
            left = smooth[max(0, i - side):i]
            right = smooth[i:i + side]
            step = abs(float(np.median(right)) - float(np.median(left)))
            out[i] = (step - TEMPO_STEP_MIN_BPM) / TEMPO_STEP_RANGE_BPM
        return np.clip(out, 0.0, 1.0).astype(np.float32)

    def _pick_track_peaks(self, fused: np.ndarray, frame_sec: float) -> list[int]:
        from scipy.signal import find_peaks

        if fused.size == 0:
            return []
        distance_sec = max(self.min_distance_sec, LONG_MIX_MIN_DISTANCE_SEC)
        distance = max(1, int(distance_sec / max(frame_sec, 1e-6)))
        peaks, _ = find_peaks(fused, distance=distance, prominence=TRACK_PEAK_PROMINENCE)
        # Der Mindestabstand gilt auch zu Mix-Anfang und -Ende: ein "Titel" von
        # 81 s vor der ersten Grenze ist dieselbe Unterschreitung wie zwischen
        # zwei Grenzen. (Am dritten Referenzmix lag dort der einzige Fehlalarm;
        # der Foote-Kern sieht am Rand nur die eine Seite.)
        edge = distance
        return [int(p) for p in peaks if edge <= p < fused.size - edge]

    @staticmethod
    def _mean_bin_2d(values: np.ndarray, size: int) -> np.ndarray:
        n_bins = max(1, int(np.ceil(values.shape[1] / size)))
        return np.stack(
            [
                np.mean(values[:, index * size : (index + 1) * size], axis=1)
                for index in range(n_bins)
            ],
            axis=1,
        )

    @staticmethod
    def _mean_bin_1d(values: np.ndarray, size: int, n_bins: int) -> np.ndarray:
        return np.asarray(
            [
                float(np.mean(values[index * size : (index + 1) * size]))
                if values[index * size : (index + 1) * size].size
                else 0.0
                for index in range(n_bins)
            ],
            dtype=np.float32,
        )

    def _cap_feature_resolution(
        self,
        chroma: np.ndarray,
        activity: np.ndarray,
        flux: np.ndarray,
        tempo: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if chroma.shape[1] <= self.MAX_SSM_FRAMES:
            return chroma, activity, flux, tempo
        edges = np.linspace(
            0,
            chroma.shape[1],
            self.MAX_SSM_FRAMES + 1,
            dtype=int,
        )
        return (
            np.stack(
                [
                    np.mean(chroma[:, edges[i] : edges[i + 1]], axis=1)
                    for i in range(self.MAX_SSM_FRAMES)
                ],
                axis=1,
            ).astype(np.float32),
            np.asarray(
                [
                    np.mean(activity[edges[i] : edges[i + 1]])
                    for i in range(self.MAX_SSM_FRAMES)
                ],
                dtype=np.float32,
            ),
            np.asarray(
                [
                    np.mean(flux[edges[i] : edges[i + 1]])
                    for i in range(self.MAX_SSM_FRAMES)
                ],
                dtype=np.float32,
            ),
            np.asarray(
                [
                    np.mean(tempo[edges[i] : edges[i + 1]])
                    for i in range(self.MAX_SSM_FRAMES)
                ],
                dtype=np.float32,
            ),
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
        """Sliding-window tempo. Drift-Magnitude = absolute Diff zwischen Fenstern.

        AP4.6 (Audit 2026-06-10): hop_sec wird dynamisch je nach Dateidauer angepasst,
        um den massiven Rechenaufwand (tausende beat_track-Aufrufe) bei langen
        DJ-Mixen (>30 min) zu verhindern.
        """
        import librosa

        win_sec = 8.0
        total_duration = y.size / sr
        if total_duration > 1800.0:    # > 30 Min: 10s Hops
            hop_sec = 10.0
        elif total_duration > 600.0:   # > 10 Min: 5s Hops
            hop_sec = 5.0
        else:
            hop_sec = 2.0              # < 10 Min: 2s Hops (2x schneller als 1s)

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
