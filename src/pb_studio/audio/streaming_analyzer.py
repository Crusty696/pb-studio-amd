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
    onset_times: list[float] = field(default_factory=list)
    kick_times: list[float] = field(default_factory=list)
    snare_times: list[float] = field(default_factory=list)
    hihat_times: list[float] = field(default_factory=list)
    chroma_mean: list[float] = field(default_factory=list)
    spectral_times: list[float] = field(default_factory=list)
    spectral_bands: dict[str, list[float]] = field(default_factory=dict)
    spectral_centroids: list[float] = field(default_factory=list)
    stage_errors: dict[str, list[str]] = field(default_factory=dict)
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

    def __init__(self, dedup_threshold: float = 0.15) -> None:
        self._beats: list[float] = []
        self._dedup_threshold = dedup_threshold

    def add_chunk_beats(self, beat_times_abs: list[float]) -> None:
        """Fuegt absolute Beat-Zeiten hinzu (bereits offset-korrigiert)."""
        self._beats.extend(beat_times_abs)

    def get_deduplicated(self) -> list[float]:
        """Sortiert und dedupliziert Beats (merge bei <threshold Abstand, indem nahegelegene gemittelt werden)."""
        if not self._beats:
            return []
        self._beats.sort()
        # Hinweis (Review 2026-07-09): Chained Grouping — Vergleich gegen das
        # LETZTE Element der Gruppe. Ketten mit je <=threshold Abstand
        # kollabieren zu EINEM Beat; erst ab effektiv >400 BPM relevant, fuer
        # Overlap-Jitter-Dedup gewollt. Bei Problemen: gegen current_group[0]
        # vergleichen.
        deduped: list[float] = []
        current_group: list[float] = [self._beats[0]]
        for b in self._beats[1:]:
            if (b - current_group[-1]) <= self._dedup_threshold:
                current_group.append(b)
            else:
                deduped.append(sum(current_group) / len(current_group))
                current_group = [b]
        if current_group:
            deduped.append(sum(current_group) / len(current_group))
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

    def add_gap(
        self,
        duration_seconds: float,
        is_first_chunk: bool,
        overlap_frames: int,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Reserviert die Zeit eines fehlgeschlagenen Chunks als Stille."""
        rms_frames = 1 + int(duration_seconds * sample_rate) // hop_length
        if not is_first_chunk and overlap_frames > 0:
            rms_frames = max(0, rms_frames - overlap_frames)
        downsample_factor = 4
        output_frames = (
            rms_frames // downsample_factor
            if rms_frames > downsample_factor
            else rms_frames
        )
        self._frames.extend([0.0] * output_frames)

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
    BEAT_DEDUP_THRESHOLD_SEC = 0.15  # 150ms Deduplizierung

    # STFT-Parameter
    # Full-duration spectral summaries include the 12–20 kHz "air" band.
    SR = 44100
    N_FFT = 2048
    HOP_LENGTH = 512
    MAX_REPRESENTATIVE_POINTS = 7200

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
        energy_only: bool = False,
    ) -> StreamingAnalysisResult:
        """Volle chunked Analyse. on_progress(0..100).

        Fuer Files <= 1.5x window_sec wird Single-Shot verwendet.
        Fuer laengere Files echtes Chunk-Streaming.

        AP4.1 (Audit 2026-06-10): energy_only=True ueberspringt die teure
        Beat-Detection (librosa.beat.beat_track pro Chunk) und liefert nur
        die RMS-Energy-Curve. Wird genutzt, um die Energy vom Original-Mix
        zu berechnen, waehrend Beats vom Drums-Stem kommen (beats=[], bpm=0).
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
            return self._analyze_single_shot(path, duration, on_progress, energy_only=energy_only)

        return self._analyze_streaming(path, duration, on_progress, energy_only=energy_only)

    # ------------------------------------------------------------------
    # Single-Shot (kurze Files)
    # ------------------------------------------------------------------
    def _analyze_single_shot(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
        energy_only: bool = False,
    ) -> StreamingAnalysisResult:
        """Fuer kleine Files: standard librosa load + librosa beat_track."""
        import librosa

        if on_progress:
            on_progress(10.0)
        y, sr = librosa.load(str(path), sr=self.SR, mono=True)
        if on_progress:
            on_progress(40.0)

        if energy_only:
            tempo, beats = 0.0, []
            trigger_times = ([], [], [], [])
        else:
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            trigger_times = self._detect_triggers(y)

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
            onset_times=trigger_times[0],
            kick_times=trigger_times[1],
            snare_times=trigger_times[2],
            hihat_times=trigger_times[3],
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
        energy_only: bool = False,
    ) -> StreamingAnalysisResult:
        """Prepare an O(1)-seek source and always remove its temp transcode."""
        import soundfile as sf

        temp_wav_path: Optional[str] = None
        try:
            try:
                native_sr = sf.info(str(path)).samplerate
            except Exception:
                native_sr = None
            if native_sr is None:
                temp_wav_path = self._transcode_to_wav(path)
                if temp_wav_path is None:
                    raise RuntimeError(
                        "Streaming-Transcode fehlgeschlagen; "
                        "langsames Offset-Decoding ist deaktiviert"
                    )
                path = Path(temp_wav_path)
                native_sr = sf.info(str(path)).samplerate
            return self._analyze_streaming_prepared(
                path,
                duration,
                on_progress,
                energy_only,
                native_sr,
            )
        finally:
            if temp_wav_path is not None:
                try:
                    Path(temp_wav_path).unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning(
                        "Streaming-Tempdatei konnte nicht entfernt werden: %s",
                        exc,
                    )

    def _analyze_streaming_prepared(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
        energy_only: bool,
        native_sr: int,
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
        onset_acc = _BeatAccumulator(self.BEAT_DEDUP_THRESHOLD_SEC)
        kick_acc = _BeatAccumulator(self.BEAT_DEDUP_THRESHOLD_SEC)
        snare_acc = _BeatAccumulator(self.BEAT_DEDUP_THRESHOLD_SEC)
        hihat_acc = _BeatAccumulator(self.BEAT_DEDUP_THRESHOLD_SEC)
        energy_agg = _EnergyAggregator()
        chroma_sum = np.zeros(12, dtype=np.float64)
        chroma_weight = 0
        spectral_times: list[float] = []
        spectral_bands: dict[str, list[float]] = {}
        spectral_centroids: list[float] = []
        stage_errors: dict[str, list[str]] = {}

        overlap_frames = int(self.overlap_sec * self.SR / self.HOP_LENGTH)

        for i in range(n_windows):
            # Berechne start_sample absolut und drift-frei
            start_sample = int(i * step * native_sr)
            chunk_start = start_sample / native_sr
            chunk_dur = min(self.window_sec, duration - chunk_start)
            if chunk_dur < 2.0:
                continue

            try:
                chunk = self._load_chunk(path, chunk_start, chunk_dur)
            except Exception as e:
                logger.warning(f"Chunk {i} load fehlgeschlagen: {e}")
                stage_errors.setdefault("load", []).append(f"chunk {i}: {e}")
                energy_agg.add_gap(
                    chunk_dur,
                    is_first_chunk=(i == 0),
                    overlap_frames=overlap_frames,
                    sample_rate=self.SR,
                    hop_length=self.HOP_LENGTH,
                )
                if on_progress:
                    on_progress((i + 1) * 100.0 / n_windows)
                continue

            # --- Beat-Detection pro Chunk (bei energy_only uebersprungen) ---
            if not energy_only:
                beats_ok = self._process_beats(
                    chunk, chunk_start, bpm_est, beat_acc
                )
                if not beats_ok:
                    stage_errors.setdefault("beats", []).append(
                        f"chunk {i}: beat detection failed"
                    )
                triggers_ok = self._process_triggers(
                    chunk,
                    chunk_start,
                    onset_acc,
                    kick_acc,
                    snare_acc,
                    hihat_acc,
                )
                if not triggers_ok:
                    stage_errors.setdefault("beats", []).append(
                        f"chunk {i}: trigger detection failed"
                    )

            try:
                representative = self._extract_representative_features(
                    chunk,
                    chunk_start,
                    skip_seconds=0.0 if i == 0 else self.overlap_sec,
                )
                feature_weight = int(representative["chroma_weight"])
                chroma_sum += (
                    np.asarray(representative["chroma_mean"], dtype=np.float64)
                    * feature_weight
                )
                chroma_weight += feature_weight
                spectral_times.extend(representative["times"])
                spectral_centroids.extend(representative["centroids"])
                for band_name, values in representative["bands"].items():
                    spectral_bands.setdefault(band_name, []).extend(values)
            except Exception as e:
                logger.warning(
                    f"Full-duration Features bei {chunk_start:.1f}s fehlgeschlagen: {e}"
                )
                stage_errors.setdefault("features", []).append(
                    f"chunk {i}: {e}"
                )

            # --- RMS-Energy pro Chunk ---
            energy_ok = self._process_energy(
                chunk, is_first=(i == 0),
                overlap_frames=overlap_frames,
                energy_agg=energy_agg,
            )
            if not energy_ok:
                stage_errors.setdefault("energy", []).append(
                    f"chunk {i}: RMS calculation failed"
                )
                energy_agg.add_gap(
                    chunk_dur,
                    is_first_chunk=(i == 0),
                    overlap_frames=overlap_frames,
                    sample_rate=self.SR,
                    hop_length=self.HOP_LENGTH,
                )

            # Chunk-Buffer freigeben
            del chunk
            gc.collect()

            if on_progress:
                on_progress((i + 1) * 100.0 / n_windows)

        (
            spectral_times,
            spectral_bands,
            spectral_centroids,
        ) = self._cap_representative_points(
            spectral_times,
            spectral_bands,
            spectral_centroids,
        )
        return StreamingAnalysisResult(
            duration_seconds=duration,
            bpm=bpm_est.median_bpm,
            beats=beat_acc.get_deduplicated(),
            energy_curve=energy_agg.get_normalized(),
            onset_times=onset_acc.get_deduplicated(),
            kick_times=kick_acc.get_deduplicated(),
            snare_times=snare_acc.get_deduplicated(),
            hihat_times=hihat_acc.get_deduplicated(),
            chroma_mean=(
                (chroma_sum / chroma_weight).tolist()
                if chroma_weight > 0
                else []
            ),
            spectral_times=spectral_times,
            spectral_bands=spectral_bands,
            spectral_centroids=spectral_centroids,
            stage_errors=stage_errors,
            window_count=n_windows,
        )

    def _extract_representative_features(
        self,
        chunk: np.ndarray,
        chunk_start: float,
        skip_seconds: float,
    ) -> dict:
        """One-second spectral/chroma summaries for full-duration consumers."""
        import librosa

        from .spectral_analyzer import FREQUENCY_BANDS

        stft = np.abs(
            librosa.stft(
                chunk,
                n_fft=self.N_FFT,
                hop_length=self.HOP_LENGTH,
            )
        )
        frequencies = librosa.fft_frequencies(sr=self.SR, n_fft=self.N_FFT)
        centroids = librosa.feature.spectral_centroid(
            S=stft,
            sr=self.SR,
        )[0]
        chroma = librosa.feature.chroma_stft(
            S=stft,
            sr=self.SR,
            n_fft=self.N_FFT,
        )
        local_times = librosa.frames_to_time(
            np.arange(stft.shape[1]),
            sr=self.SR,
            hop_length=self.HOP_LENGTH,
        )
        frames_per_second = max(1, int(round(self.SR / self.HOP_LENGTH)))
        start_frame = int(skip_seconds * self.SR / self.HOP_LENGTH)
        indices = range(start_frame, stft.shape[1], frames_per_second)
        times: list[float] = []
        centroid_points: list[float] = []
        band_points = {name: [] for name in FREQUENCY_BANDS}
        for start in indices:
            end = min(start + frames_per_second, stft.shape[1])
            if end <= start:
                continue
            times.append(float(chunk_start + np.mean(local_times[start:end])))
            centroid_points.append(float(np.mean(centroids[start:end])))
            for band_name, (low, high) in FREQUENCY_BANDS.items():
                mask = (frequencies >= low) & (frequencies < high)
                value = float(np.mean(np.sum(stft[mask, start:end], axis=0)))
                band_points[band_name].append(value)
        return {
            "times": times,
            "bands": band_points,
            "centroids": centroid_points,
            "chroma_mean": np.mean(chroma, axis=1).tolist(),
            "chroma_weight": chroma.shape[1],
        }

    def _cap_representative_points(
        self,
        times: list[float],
        bands: dict[str, list[float]],
        centroids: list[float],
    ) -> tuple[list[float], dict[str, list[float]], list[float]]:
        if len(times) <= self.MAX_REPRESENTATIVE_POINTS:
            return times, bands, centroids
        edges = np.linspace(
            0,
            len(times),
            self.MAX_REPRESENTATIVE_POINTS + 1,
            dtype=int,
        )

        def reduce(values: list[float]) -> list[float]:
            return [
                float(np.mean(values[edges[i] : edges[i + 1]]))
                for i in range(self.MAX_REPRESENTATIVE_POINTS)
            ]

        return (
            reduce(times),
            {name: reduce(values) for name, values in bands.items()},
            reduce(centroids),
        )

    def _transcode_to_wav(self, path: Path) -> Optional[str]:
        """BUGFIX H5 helper: transcode any audio file to a temp mono WAV at
        self.SR via ffmpeg, once, so streaming chunk-loads can use fast
        soundfile block-I/O instead of O(n^2) librosa offset re-seeks.

        Returns the temp WAV path, or None on failure (caller keeps original).
        """
        import subprocess
        import tempfile
        import uuid
        try:
            try:
                from pb_studio.video.encoder_utils import _get_ffmpeg_path
                ffmpeg = _get_ffmpeg_path()
            except Exception:
                ffmpeg = "ffmpeg"
            temp_wav = str(Path(tempfile.gettempdir()) / f"pb_studio_stream_{uuid.uuid4().hex}.wav")
            cmd = [
                ffmpeg, "-y", "-i", str(path),
                "-vn", "-acodec", "pcm_s16le", "-ar", str(self.SR), "-ac", "1",
                temp_wav,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0 and Path(temp_wav).exists() and Path(temp_wav).stat().st_size > 0:
                logger.info("Streaming: transcoded to temp WAV for fast block-I/O: %s", temp_wav)
                return temp_wav
            logger.warning("Streaming transcode failed (rc=%s); using slow per-chunk fallback.", result.returncode)
            return None
        except Exception as e:
            logger.warning("Streaming transcode error (%s); using slow per-chunk fallback.", e)
            return None

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

        # AP-07 Fix: Begrenze start_sample auf info.frames - 1, um ValueError bei seek
        # ueber das Dateiende (aufgrund von Rundungen bei Dateiende-Metadaten) zu verhindern.
        start_sample = min(int(offset * native_sr), info.frames - 1)
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
    ) -> bool:
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
            return True

        except Exception as e:
            logger.warning(f"Beat-Detection bei {chunk_start:.1f}s fehlgeschlagen: {e}")
            return False

    def _detect_triggers(
        self,
        chunk: np.ndarray,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        """Detect onset and drum candidates relative to one in-memory chunk."""
        import librosa

        hop = self.HOP_LENGTH
        onset_times = librosa.frames_to_time(
            librosa.onset.onset_detect(y=chunk, sr=self.SR, units="frames"),
            sr=self.SR,
        ).tolist()

        def _band_times(*, signal: np.ndarray, fmin=None, fmax=None) -> list[float]:
            kwargs = {
                "y": signal,
                "sr": self.SR,
                "hop_length": hop,
                "n_mels": 64,
            }
            if fmin is not None:
                kwargs["fmin"] = fmin
            if fmax is not None:
                kwargs["fmax"] = fmax
            envelope = librosa.onset.onset_strength(**kwargs)
            frames = librosa.onset.onset_detect(
                onset_envelope=envelope,
                sr=self.SR,
                hop_length=hop,
            )
            return librosa.frames_to_time(
                frames,
                sr=self.SR,
                hop_length=hop,
            ).tolist()

        kick_times = _band_times(
            signal=librosa.effects.preemphasis(chunk),
            fmax=150,
        )
        snare_times = _band_times(signal=chunk, fmin=200, fmax=400)
        hihat_times = _band_times(signal=chunk, fmin=5000)
        return onset_times, kick_times, snare_times, hihat_times

    def _process_triggers(
        self,
        chunk: np.ndarray,
        chunk_start: float,
        onset_acc: _BeatAccumulator,
        kick_acc: _BeatAccumulator,
        snare_acc: _BeatAccumulator,
        hihat_acc: _BeatAccumulator,
    ) -> bool:
        """Collect absolute trigger times and deduplicate overlap at result time."""
        try:
            relative_groups = self._detect_triggers(chunk)
            for relative, accumulator in zip(
                relative_groups,
                (onset_acc, kick_acc, snare_acc, hihat_acc),
            ):
                accumulator.add_chunk_beats(
                    [float(value) + chunk_start for value in relative]
                )
            return True
        except Exception as e:
            logger.warning(
                f"Trigger-Detection bei {chunk_start:.1f}s fehlgeschlagen: {e}"
            )
            return False

    # ------------------------------------------------------------------
    # Energy-Processing pro Chunk
    # ------------------------------------------------------------------
    def _process_energy(
        self,
        chunk: np.ndarray,
        is_first: bool,
        overlap_frames: int,
        energy_agg: _EnergyAggregator,
    ) -> bool:
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
            return True
        except Exception as e:
            logger.warning(f"Energy-Berechnung fehlgeschlagen: {e}")
            return False

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
