"""Streaming-Audio-Analyzer fuer lange Mixe (>60min).

Standard librosa.load + BeatNet laden volle Datei in RAM. Fuer 90min-Mix:
~480MB RAM + langes Inference. Streaming-Approach chunkt Datei in 30s-Windows
mit 5s Overlap, beats werden pro Window detected + dedupliziert.

Kernprinzip: Nur der aktuelle Chunk + Overlap existiert im RAM.
Ergebnisse werden inkrementell aggregiert (rolling stats).

RAM-Ziel: <100MB fuer einen 60min Mix bei 22050 Hz mono float32.
  - 30s Chunk = 30 * 22050 * 4 Byte = ~2.6 MB
  - STFT-Buffer (n_fft=2048, hop=512) = ~0.5 MB
  - Overhead (numpy temps, librosa internals) = ~10 MB
  - Aggregations-Arrays (beats, energy-downsampled) = ~5 MB
  - Total peak: ~20 MB (vs. 480 MB non-streaming)
"""
from __future__ import annotations

import gc
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ergebnis-Datenklasse
# ---------------------------------------------------------------------------
@dataclass
class StreamingAnalysisResult:
    """Ergebnis der Streaming-Analyse.

    Felder sind API-kompatibel mit der bisherigen Version.
    """
    duration_seconds: float
    bpm: float = 0.0
    beats: list[float] = field(default_factory=list)
    energy_curve: list[float] = field(default_factory=list)
    window_count: int = 0


# ---------------------------------------------------------------------------
# Interne Hilfsklassen fuer inkrementelle Aggregation
# ---------------------------------------------------------------------------
class _RunningBPMEstimator:
    """Sammelt BPM-Schaetzungen pro Chunk und liefert Median."""

    __slots__ = ('_estimates',)

    def __init__(self) -> None:
        self._estimates: list[float] = []

    def add(self, bpm: float) -> None:
        if 30.0 < bpm < 300.0:  # plausible range fuer Musik
            self._estimates.append(bpm)

    @property
    def median_bpm(self) -> float:
        if not self._estimates:
            return 0.0
        return float(np.median(self._estimates))


class _BeatAccumulator:
    """Sammelt Beats aller Chunks und dedupliziert an Window-Boundaries."""

    __slots__ = ('_beats', '_dedup_threshold')

    def __init__(self, dedup_threshold: float = 0.05) -> None:
        self._beats: list[float] = []
        self._dedup_threshold = dedup_threshold

    def add_chunk_beats(self, beat_times_abs: list[float]) -> None:
        """Fuegt absolute Beat-Zeiten hinzu (bereits offset-korrigiert)."""
        self._beats.extend(beat_times_abs)

    def get_deduplicated(self) -> list[float]:
        """Sortiert und dedupliziert Beats (merge bei <threshold Abstand)."""
        if not self._beats:
            return []
        self._beats.sort()
        deduped: list[float] = [self._beats[0]]
        for b in self._beats[1:]:
            if (b - deduped[-1]) > self._dedup_threshold:
                deduped.append(b)
        return deduped


class _EnergyAggregator:
    """Streaming-Energy-Kurve mit Overlap-Handling und Downsampling.

    Speichert RMS-Werte pro Chunk, schneidet Overlap-Region ab,
    und normalisiert am Ende global.
    """

    __slots__ = ('_frames', '_global_max')

    def __init__(self) -> None:
        self._frames: list[float] = []
        self._global_max: float = 0.0

    def add_chunk_rms(
        self,
        rms: np.ndarray,
        is_first_chunk: bool,
        overlap_frames: int,
    ) -> None:
        """RMS-Werte eines Chunks hinzufuegen.

        Bei nicht-erstem Chunk werden die ersten overlap_frames uebersprungen
        um Doppel-Counting zu vermeiden.
        """
        if not is_first_chunk and overlap_frames > 0:
            rms = rms[overlap_frames:]
        if len(rms) == 0:
            return

        chunk_max = float(np.max(rms))
        if chunk_max > self._global_max:
            self._global_max = chunk_max

        # Downsample: ~10 Werte pro Sekunde statt ~43
        # (hop_length=512, sr=22050 → 43.07 frames/sec, Faktor 4 → ~10/sec)
        downsample_factor = 4
        if len(rms) > downsample_factor:
            n_out = len(rms) // downsample_factor
            rms_ds = rms[: n_out * downsample_factor].reshape(n_out, downsample_factor)
            self._frames.extend(rms_ds.mean(axis=1).tolist())
        else:
            self._frames.extend(rms.tolist())

    def get_normalized(self) -> list[float]:
        """Global normalisierte Energy-Kurve [0..1]."""
        if not self._frames or self._global_max <= 0:
            return self._frames
        inv = 1.0 / self._global_max
        return [v * inv for v in self._frames]


# ---------------------------------------------------------------------------
# Hauptklasse
# ---------------------------------------------------------------------------
class StreamingAudioAnalyzer:
    """Chunked Audio-Analyse fuer lange Mixe.

    Verwendet soundfile fuer block-basiertes I/O (kein voller RAM-Load)
    und librosa fuer STFT/Beat-Detection pro Chunk.
    """

    DEFAULT_WINDOW_SEC = 30.0   # 30 Sekunden Chunks
    DEFAULT_OVERLAP_SEC = 5.0   # 5 Sekunden Overlap
    BEAT_DEDUP_THRESHOLD_SEC = 0.05  # 50ms Deduplizierung

    # STFT-Parameter
    SR = 22050
    N_FFT = 2048
    HOP_LENGTH = 512

    def __init__(
        self,
        window_sec: float = DEFAULT_WINDOW_SEC,
        overlap_sec: float = DEFAULT_OVERLAP_SEC,
    ):
        self.window_sec = window_sec
        self.overlap_sec = overlap_sec

    def analyze(
        self,
        audio_path: str | Path,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> StreamingAnalysisResult:
        """Volle chunked Analyse. on_progress(0..100).

        Fuer Files <= 1.5x window_sec wird Single-Shot verwendet.
        Fuer laengere Files echtes Chunk-Streaming.
        """
        import librosa

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio not found: {path}")

        duration = librosa.get_duration(path=str(path))
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}")

        # Fuer Files <= 1.5x window: Fallback zu single-shot
        if duration <= self.window_sec * 1.5:
            return self._analyze_single_shot(path, duration, on_progress)

        return self._analyze_streaming(path, duration, on_progress)

    # ------------------------------------------------------------------
    # Single-Shot (kurze Files)
    # ------------------------------------------------------------------
    def _analyze_single_shot(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
    ) -> StreamingAnalysisResult:
        """Fuer kleine Files: standard librosa load + librosa beat_track."""
        import librosa

        if on_progress:
            on_progress(10.0)
        y, sr = librosa.load(str(path), sr=self.SR, mono=True)
        if on_progress:
            on_progress(40.0)

        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        if on_progress:
            on_progress(70.0)
        rms = librosa.feature.rms(
            y=y, frame_length=self.N_FFT, hop_length=self.HOP_LENGTH
        )[0]
        rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
        energy = (rms / rms_max).tolist() if rms_max > 0 else []

        if on_progress:
            on_progress(100.0)

        # Sicher BPM als float extrahieren
        bpm_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

        return StreamingAnalysisResult(
            duration_seconds=duration,
            bpm=bpm_val,
            beats=beats,
            energy_curve=energy,
            window_count=1,
        )

    # ------------------------------------------------------------------
    # Streaming-Analyse (lange Files)
    # ------------------------------------------------------------------
    def _analyze_streaming(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
    ) -> StreamingAnalysisResult:
        """Echtes Chunk-Streaming mit soundfile block-I/O.

        Nur der aktuelle Chunk + Overlap lebt im RAM.
        """
        import librosa

        step = self.window_sec - self.overlap_sec
        if step <= 0:
            step = self.window_sec  # Safety: overlap darf nicht >= window sein
        n_windows = max(1, math.ceil((duration - self.overlap_sec) / step))

        # Aggregations-Objekte
        bpm_est = _RunningBPMEstimator()
        beat_acc = _BeatAccumulator(self.BEAT_DEDUP_THRESHOLD_SEC)
        energy_agg = _EnergyAggregator()

        overlap_frames = int(self.overlap_sec * self.SR / self.HOP_LENGTH)

        for i in range(n_windows):
            chunk_start = i * step
            chunk_dur = min(self.window_sec, duration - chunk_start)
            if chunk_dur < 2.0:
                continue

            try:
                chunk = self._load_chunk(path, chunk_start, chunk_dur)
            except Exception as e:
                logger.warning(f"Chunk {i} load fehlgeschlagen: {e}")
                continue

            # --- Beat-Detection pro Chunk ---
            self._process_beats(
                chunk, chunk_start, bpm_est, beat_acc
            )

            # --- RMS-Energy pro Chunk ---
            self._process_energy(
                chunk, is_first=(i == 0),
                overlap_frames=overlap_frames,
                energy_agg=energy_agg,
            )

            # Chunk-Buffer freigeben
            del chunk
            gc.collect()

            if on_progress:
                on_progress((i + 1) * 100.0 / n_windows)

        return StreamingAnalysisResult(
            duration_seconds=duration,
            bpm=bpm_est.median_bpm,
            beats=beat_acc.get_deduplicated(),
            energy_curve=energy_agg.get_normalized(),
            window_count=n_windows,
        )

    # ------------------------------------------------------------------
    # Chunk-Loading
    # ------------------------------------------------------------------
    def _load_chunk(
        self,
        path: Path,
        offset: float,
        duration: float,
    ) -> np.ndarray:
        """Laedt einen Audio-Chunk mit soundfile (block-I/O).

        Faellt auf librosa.load zurueck wenn soundfile fehlschlaegt
        (z.B. bei nicht-WAV Formaten wie MP3).
        """
        try:
            return self._load_chunk_soundfile(path, offset, duration)
        except Exception:
            # Fallback: librosa.load (dekodiert MP3/FLAC/OGG via audioread/ffmpeg)
            import librosa
            y, _sr = librosa.load(
                str(path), sr=self.SR, mono=True,
                offset=offset, duration=duration,
            )
            return y

    def _load_chunk_soundfile(
        self,
        path: Path,
        offset: float,
        duration: float,
    ) -> np.ndarray:
        """Echtes Block-I/O via soundfile — minimaler RAM."""
        import soundfile as sf

        info = sf.info(str(path))
        native_sr = info.samplerate

        start_sample = int(offset * native_sr)
        n_samples = int(duration * native_sr)

        with sf.SoundFile(str(path)) as f:
            f.seek(start_sample)
            chunk = f.read(n_samples, dtype='float32', always_2d=True)

        # Mono-Mixdown falls stereo/multi-channel
        if chunk.ndim == 2 and chunk.shape[1] > 1:
            chunk = chunk.mean(axis=1)
        else:
            chunk = chunk.ravel()

        # Resample auf Ziel-SR wenn noetig
        if native_sr != self.SR:
            import librosa
            chunk = librosa.resample(
                chunk, orig_sr=native_sr, target_sr=self.SR
            )

        return chunk

    # ------------------------------------------------------------------
    # Beat-Processing pro Chunk
    # ------------------------------------------------------------------
    def _process_beats(
        self,
        chunk: np.ndarray,
        chunk_start: float,
        bpm_est: _RunningBPMEstimator,
        beat_acc: _BeatAccumulator,
    ) -> None:
        """Beat-Detection auf einem Chunk mit librosa.beat.beat_track."""
        import librosa

        try:
            tempo, beat_frames = librosa.beat.beat_track(
                y=chunk, sr=self.SR,
                hop_length=self.HOP_LENGTH,
            )
            # Absolute Beat-Zeiten
            beat_times_rel = librosa.frames_to_time(
                beat_frames, sr=self.SR, hop_length=self.HOP_LENGTH
            )
            beat_times_abs = (beat_times_rel + chunk_start).tolist()
            beat_acc.add_chunk_beats(beat_times_abs)

            # BPM extrahieren
            bpm_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])
            bpm_est.add(bpm_val)

        except Exception as e:
            logger.warning(f"Beat-Detection bei {chunk_start:.1f}s fehlgeschlagen: {e}")

    # ------------------------------------------------------------------
    # Energy-Processing pro Chunk
    # ------------------------------------------------------------------
    def _process_energy(
        self,
        chunk: np.ndarray,
        is_first: bool,
        overlap_frames: int,
        energy_agg: _EnergyAggregator,
    ) -> None:
        """RMS-Energy auf einem Chunk berechnen."""
        import librosa

        try:
            rms = librosa.feature.rms(
                y=chunk,
                frame_length=self.N_FFT,
                hop_length=self.HOP_LENGTH,
            )[0]

            energy_agg.add_chunk_rms(
                rms,
                is_first_chunk=is_first,
                overlap_frames=overlap_frames,
            )
        except Exception as e:
            logger.warning(f"Energy-Berechnung fehlgeschlagen: {e}")

    # ------------------------------------------------------------------
    # STFT-Streaming (fuer erweiterte Spektral-Analyse)
    # ------------------------------------------------------------------
    def compute_stft_streaming(
        self,
        audio_path: str | Path,
        on_chunk: Optional[Callable[[np.ndarray, float], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Chunk-basierte STFT-Berechnung fuer externe Konsumenten.

        Ruft on_chunk(stft_magnitude, chunk_start_sec) pro Chunk auf.
        Der Konsument verarbeitet die STFT in-place ohne Akkumulation.

        Nuetzlich fuer SpectralAnalyzer-Integration bei langen Files.
        """
        import librosa

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio not found: {path}")

        duration = librosa.get_duration(path=str(path))
        step = self.window_sec - self.overlap_sec
        if step <= 0:
            step = self.window_sec
        n_windows = max(1, math.ceil((duration - self.overlap_sec) / step))

        for i in range(n_windows):
            chunk_start = i * step
            chunk_dur = min(self.window_sec, duration - chunk_start)
            if chunk_dur < 2.0:
                continue

            try:
                chunk = self._load_chunk(path, chunk_start, chunk_dur)

                # STFT berechnen
                S = np.abs(librosa.stft(
                    chunk,
                    n_fft=self.N_FFT,
                    hop_length=self.HOP_LENGTH,
                ))

                if on_chunk:
                    on_chunk(S, chunk_start)

                del S, chunk
                gc.collect()

            except Exception as e:
                logger.warning(f"STFT-Chunk {i} fehlgeschlagen: {e}")

            if on_progress:
                on_progress((i + 1) * 100.0 / n_windows)

    # ------------------------------------------------------------------
    # Utility: Memory-Estimation
    # ------------------------------------------------------------------
    @staticmethod
    def estimate_memory_mb(duration_sec: float, sr: int = 22050) -> dict:
        """Schaetzt RAM-Verbrauch: streaming vs. non-streaming.

        Returns:
            Dict mit 'non_streaming_mb' und 'streaming_peak_mb'.
        """
        # Non-streaming: volle Datei als float32 + STFT + Beat-Buffers
        full_samples = duration_sec * sr
        non_streaming = (
            full_samples * 4  # float32 audio
            + full_samples * 4  # STFT workspace (grob)
            + 50 * 1024 * 1024  # librosa overhead
        ) / (1024 * 1024)

        # Streaming: nur 30s chunk + overhead
        chunk_samples = 30 * sr
        streaming = (
            chunk_samples * 4  # float32 audio chunk
            + chunk_samples * 4  # STFT workspace
            + 15 * 1024 * 1024  # overhead + aggregation
        ) / (1024 * 1024)

        return {
            'non_streaming_mb': round(non_streaming, 1),
            'streaming_peak_mb': round(streaming, 1),
        }
