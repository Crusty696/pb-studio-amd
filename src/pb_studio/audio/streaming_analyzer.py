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
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from pb_studio.audio.band_params import (
    HIHAT_BAND,
    KICK_BAND,
    SNARE_BAND,
    band_stft_params,
)

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
    chunk_evidence: list[dict] = field(default_factory=list)
    resume_checkpoint: dict = field(default_factory=dict)
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

    @property
    def count(self) -> int:
        return len(self._estimates)

    def values_since(self, start: int) -> list[float]:
        return [float(value) for value in self._estimates[start:]]


class _BeatAccumulator:
    """Sammelt Beats aller Chunks und dedupliziert an Window-Boundaries."""

    __slots__ = ('_beats', '_dedup_threshold', '_window_floor')

    def __init__(self, dedup_threshold: float = 0.15) -> None:
        self._beats: list[float] = []
        self._dedup_threshold = dedup_threshold
        self._window_floor: Optional[float] = None

    def set_window_floor(self, min_time: Optional[float]) -> None:
        """Untergrenze fuer das gerade verarbeitete Fenster setzen.

        H-2 (Audit 2026-08-30): Fenster ueberlappen sich um overlap_sec. Ohne
        Untergrenze liefert jeder Chunk ab dem zweiten auch Ergebnisse fuer die
        Overlap-Region, die der Vorgaenger bereits vollstaendig abgedeckt hat —
        20 % der Timeline werden doppelt gezaehlt. Analog zu
        `_EnergyAggregator.add_chunk_rms` (ueberspringt overlap_frames) und
        `_extract_representative_features` (skip_seconds) verwirft der
        Akkumulator daher alle Zeitpunkte vor `min_time`. `None` = keine
        Untergrenze (erstes Fenster, das keinen Vorgaenger hat).

        Wichtig: verworfen werden nur die ERGEBNISSE. Der Detektor bekommt
        weiterhin den vollen Chunk inklusive Overlap als Kontext.
        """
        self._window_floor = None if min_time is None else float(min_time)

    def add_chunk_beats(self, beat_times_abs: list[float]) -> None:
        """Fuegt absolute Beat-Zeiten hinzu (bereits offset-korrigiert)."""
        floor = self._window_floor
        if floor is None:
            self._beats.extend(beat_times_abs)
            return
        self._beats.extend(
            value for value in beat_times_abs if float(value) >= floor
        )

    def get_deduplicated(self) -> list[float]:
        """Sortiert und dedupliziert Beats (merge bei <threshold Abstand, indem nahegelegene gemittelt werden)."""
        if not self._beats:
            return []
        # H-2 (2026-08-30): seit `set_window_floor` tilen sich die Fenster
        # ueberschneidungsfrei, die Dedup ist NICHT mehr die Overlap-Abwehr.
        # Sie bleibt fuer zwei Faelle: (a) Resume-Checkpoints, die noch von
        # einer Version vor dem Fix stammen und Overlap-Duplikate enthalten,
        # (b) den frame-genauen Nahtpunkt an der Fenstergrenze.
        self._beats.sort()
        # Vergleich gegen das ERSTE Element der Gruppe, nicht gegen das letzte.
        #
        # Bis 2026-08-30 wurde gegen `current_group[-1]` verglichen. Damit
        # kollabiert jede Kette, deren Nachbarabstaende einzeln unter der
        # Schwelle liegen, zu EINEM Wert - unabhaengig von ihrer Gesamtlaenge.
        # Der Kommentar von 2026-07-09 hielt das fuer "erst ab >400 BPM
        # relevant" und uebersah, dass dieselbe Klasse auch die Trigger-Listen
        # (Onset/Kick/Snare/HiHat) fuehrt. Gemessen mit 64 gleichmaessigen
        # Anschlaegen:
        #
        #     120 BPM  8tel  0.250s -> 64 bleiben 64
        #     120 BPM 16tel  0.125s -> 64 werden  1
        #     174 BPM 16tel  0.086s -> 64 werden  1
        #
        # Eine durchgehende 16tel-HiHat war im Streaming-Pfad also auf einen
        # einzigen Zeitpunkt reduziert. Gegen `current_group[0]` verglichen
        # umfasst eine Gruppe hoechstens ein Fenster von `threshold`, womit
        # Ketten erhalten bleiben und der Naht-Jitter weiterhin zusammenfaellt.
        deduped: list[float] = []
        current_group: list[float] = [self._beats[0]]
        for b in self._beats[1:]:
            if (b - current_group[0]) <= self._dedup_threshold:
                current_group.append(b)
            else:
                deduped.append(sum(current_group) / len(current_group))
                current_group = [b]
        if current_group:
            deduped.append(sum(current_group) / len(current_group))
        return deduped

    @property
    def count(self) -> int:
        return len(self._beats)

    def values_since(self, start: int) -> list[float]:
        return [float(value) for value in self._beats[start:]]


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

        # Downsample: ~21.5 Werte pro Sekunde statt ~86
        # (hop_length=512, sr=44100 → 86.13 frames/sec, Faktor 4 → ~21.5/sec)
        # L-5 (Audit 2026-08-30): stand vorher auf sr=22050 → 43.07/10; die
        # Klasse laeuft aber auf SR = 44100. Der stale Kommentar war die
        # dokumentarische Wurzel eines Faktor-2-Fehlers stromabwaerts.
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

    def add_checkpoint(self, frames: list[float], observed_max: float) -> None:
        self._frames.extend(float(value) for value in frames)
        self._global_max = max(self._global_max, float(observed_max))

    def values_since(self, start: int) -> list[float]:
        return [float(value) for value in self._frames[start:]]

    @property
    def global_max(self) -> float:
        return self._global_max

    @property
    def count(self) -> int:
        return len(self._frames)


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

    # Trigger (Onset/Kick/Snare/HiHat) brauchen eine deutlich kleinere Schwelle
    # als Beats. 150 ms sind bei Beats unkritisch - selbst 300 BPM haelt 200 ms
    # Abstand -, verschlucken aber jede 16tel-Figur: 128 BPM 16tel liegen
    # 117 ms auseinander, 174 BPM 16tel nur 86 ms. Seit H-2 (Window-Floor)
    # entstehen ohnehin keine Overlap-Duplikate mehr; zu deduplizieren bleibt
    # allein der Jitter an der Fensternaht, und der liegt in der
    # Groessenordnung einer Hop-Laenge (512/44100 = 11.6 ms).
    TRIGGER_DEDUP_THRESHOLD_SEC = 0.025

    # STFT-Parameter
    # Full-duration spectral summaries include the 12–20 kHz "air" band.
    SR = 44100
    N_FFT = 2048
    HOP_LENGTH = 512
    MAX_REPRESENTATIVE_POINTS = 7200
    CHECKPOINT_SCHEMA_VERSION = 2

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
        resume_checkpoint: Optional[dict] = None,
        on_chunk_checkpoint: Optional[Callable[[dict], None]] = None,
        checkpoint_guard: Optional[Callable[[], None]] = None,
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

        source_identity = self._source_identity(path)

        duration = librosa.get_duration(path=str(path))
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}")

        # Fuer Files <= 1.5x window: Fallback zu single-shot
        if duration <= self.window_sec * 1.5:
            return self._analyze_single_shot(path, duration, on_progress, energy_only=energy_only)

        return self._analyze_streaming(
            path,
            duration,
            on_progress,
            energy_only=energy_only,
            resume_checkpoint=resume_checkpoint,
            on_chunk_checkpoint=on_chunk_checkpoint,
            checkpoint_guard=checkpoint_guard,
            source_identity=source_identity,
        )

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
            chunk_evidence=[{
                "chunk_index": 0,
                "start_seconds": 0.0,
                "duration_seconds": duration,
                "status": "completed",
                "stages": {
                    "load": {"status": "completed"},
                    "beats": {
                        "status": "skipped" if energy_only else "completed",
                        "beat_count": len(beats),
                    },
                    "triggers": {
                        "status": "skipped" if energy_only else "completed",
                        "onset_count": len(trigger_times[0]),
                        "kick_count": len(trigger_times[1]),
                        "snare_count": len(trigger_times[2]),
                        "hihat_count": len(trigger_times[3]),
                    },
                    "features": {"status": "not_requested"},
                    "energy": {
                        "status": "completed",
                        "point_count": len(energy),
                    },
                },
            }],
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
        resume_checkpoint: Optional[dict] = None,
        on_chunk_checkpoint: Optional[Callable[[dict], None]] = None,
        checkpoint_guard: Optional[Callable[[], None]] = None,
        source_identity: Optional[dict] = None,
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
                resume_checkpoint=resume_checkpoint,
                on_chunk_checkpoint=on_chunk_checkpoint,
                checkpoint_guard=checkpoint_guard,
                source_identity=source_identity,
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

    @staticmethod
    def _source_identity(path: Path) -> dict[str, int | str]:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        return {
            "path": os.path.normcase(str(resolved)),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }

    def _checkpoint_config(self, energy_only: bool) -> dict[str, int | float | bool]:
        return {
            "sample_rate": self.SR,
            "window_seconds": float(self.window_sec),
            "overlap_seconds": float(self.overlap_sec),
            "n_fft": self.N_FFT,
            "hop_length": self.HOP_LENGTH,
            "energy_only": bool(energy_only),
        }

    @staticmethod
    def _is_finite_number(value) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )

    @classmethod
    def _is_numeric_list(cls, value, *, length: int | None = None) -> bool:
        return (
            isinstance(value, list)
            and (length is None or len(value) == length)
            and all(cls._is_finite_number(item) for item in value)
        )

    def _checkpoint_is_compatible(
        self,
        checkpoint: Optional[dict],
        *,
        source_identity: Optional[dict],
        duration: float,
        n_windows: int,
        energy_only: bool,
    ) -> bool:
        if not isinstance(checkpoint, dict) or source_identity is None:
            return False
        checkpoint_duration = checkpoint.get("duration_seconds")
        return (
            checkpoint.get("schema_version") == self.CHECKPOINT_SCHEMA_VERSION
            and checkpoint.get("source") == source_identity
            and checkpoint.get("config") == self._checkpoint_config(energy_only)
            and checkpoint.get("window_count") == n_windows
            and self._is_finite_number(checkpoint_duration)
            and abs(float(checkpoint_duration) - duration) <= 0.01
            and isinstance(checkpoint.get("chunks"), list)
        )

    def _checkpoint_row_is_valid(
        self,
        row: dict,
        *,
        chunk_index: int,
        chunk_start: float,
        chunk_duration: float,
        energy_only: bool,
    ) -> bool:
        if not isinstance(row, dict) or row.get("chunk_index") != chunk_index:
            return False
        if not (
            self._is_finite_number(row.get("start_seconds"))
            and self._is_finite_number(row.get("duration_seconds"))
            and abs(float(row["start_seconds"]) - chunk_start) <= 1e-6
            and abs(float(row["duration_seconds"]) - chunk_duration) <= 0.01
        ):
            return False

        if chunk_duration < 2.0:
            return (
                row.get("status") == "skipped"
                and row.get("error") == "terminal chunk shorter than 2.0 seconds"
            )
        if row.get("status") != "completed":
            return False

        stages = row.get("stages")
        payload = row.get("payload")
        if not isinstance(stages, dict) or not isinstance(payload, dict):
            return False
        if stages.get("load", {}).get("status") != "completed":
            return False
        expected_detection_status = "skipped" if energy_only else "completed"
        if (
            stages.get("beats", {}).get("status") != expected_detection_status
            or stages.get("triggers", {}).get("status") != expected_detection_status
            or stages.get("features", {}).get("status") != "completed"
            or stages.get("energy", {}).get("status") != "completed"
        ):
            return False

        timed_names = ("beats", "onsets", "kicks", "snares", "hihats")
        if not all(self._is_numeric_list(payload.get(name)) for name in timed_names):
            return False
        if energy_only and any(payload[name] for name in timed_names):
            return False
        time_margin = self.HOP_LENGTH / self.SR + self.BEAT_DEDUP_THRESHOLD_SEC
        lower = chunk_start - time_margin
        upper = chunk_start + chunk_duration + time_margin
        if any(
            not lower <= float(value) <= upper
            for name in timed_names
            for value in payload[name]
        ):
            return False
        if not self._is_numeric_list(payload.get("bpm_estimates")):
            return False

        energy_frames = payload.get("energy_frames")
        energy_max = payload.get("energy_max")
        if (
            not self._is_numeric_list(energy_frames)
            or not energy_frames
            or not self._is_finite_number(energy_max)
            or float(energy_max) < 0.0
            or float(energy_max)
            < max(float(value) for value in energy_frames)
            or len(energy_frames) != stages["energy"].get("point_count")
        ):
            return False

        features = payload.get("features")
        if not isinstance(features, dict):
            return False
        feature_times = features.get("times")
        centroids = features.get("centroids")
        bands = features.get("bands")
        chroma_mean = features.get("chroma_mean")
        chroma_weight = features.get("chroma_weight")
        from .spectral_analyzer import FREQUENCY_BANDS

        expected_band_names = set(FREQUENCY_BANDS) | {"low", "mid", "high"}
        if (
            not self._is_numeric_list(feature_times)
            or not feature_times
            or any(
                not lower <= float(value) <= upper
                for value in feature_times
            )
            or not self._is_numeric_list(centroids, length=len(feature_times))
            or not isinstance(bands, dict)
            or set(bands) != expected_band_names
            or not all(
                isinstance(name, str)
                and self._is_numeric_list(values, length=len(feature_times))
                for name, values in bands.items()
            )
            or not self._is_numeric_list(chroma_mean, length=12)
            or not isinstance(chroma_weight, int)
            or isinstance(chroma_weight, bool)
            or chroma_weight <= 0
            or len(feature_times)
            != stages["features"].get("representative_point_count")
        ):
            return False

        if energy_only:
            return True
        return (
            len(payload["beats"]) == stages["beats"].get("beat_count")
            and len(payload["onsets"]) == stages["triggers"].get("onset_count")
            and len(payload["kicks"]) == stages["triggers"].get("kick_count")
            and len(payload["snares"]) == stages["triggers"].get("snare_count")
            and len(payload["hihats"]) == stages["triggers"].get("hihat_count")
        )

    def _checkpoint_snapshot(
        self,
        *,
        source_identity: Optional[dict],
        duration: float,
        n_windows: int,
        energy_only: bool,
        chunks: list[dict],
    ) -> dict:
        if source_identity is None:
            return {}
        return {
            "schema_version": self.CHECKPOINT_SCHEMA_VERSION,
            "source": dict(source_identity),
            "config": self._checkpoint_config(energy_only),
            "duration_seconds": float(duration),
            "window_count": int(n_windows),
            "chunks": list(chunks),
        }

    @staticmethod
    def _public_chunk_evidence(row: dict, *, reused: bool = False) -> dict:
        evidence = {key: value for key, value in row.items() if key != "payload"}
        if reused:
            evidence["reused_from_checkpoint"] = True
        return evidence

    def _analyze_streaming_prepared(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
        energy_only: bool,
        native_sr: int,
        *,
        resume_checkpoint: Optional[dict] = None,
        on_chunk_checkpoint: Optional[Callable[[dict], None]] = None,
        checkpoint_guard: Optional[Callable[[], None]] = None,
        source_identity: Optional[dict] = None,
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
        # Trigger mit eigener, viel kleinerer Schwelle - siehe
        # TRIGGER_DEDUP_THRESHOLD_SEC: 150 ms verschlucken jede 16tel-Figur.
        onset_acc = _BeatAccumulator(self.TRIGGER_DEDUP_THRESHOLD_SEC)
        kick_acc = _BeatAccumulator(self.TRIGGER_DEDUP_THRESHOLD_SEC)
        snare_acc = _BeatAccumulator(self.TRIGGER_DEDUP_THRESHOLD_SEC)
        hihat_acc = _BeatAccumulator(self.TRIGGER_DEDUP_THRESHOLD_SEC)
        energy_agg = _EnergyAggregator()
        chroma_sum = np.zeros(12, dtype=np.float64)
        chroma_weight = 0
        spectral_times: list[float] = []
        spectral_bands: dict[str, list[float]] = {}
        spectral_centroids: list[float] = []
        stage_errors: dict[str, list[str]] = {}
        chunk_evidence: list[dict] = []
        checkpoint_records: list[dict] = []

        resume_rows: dict[int, dict] = {}
        if self._checkpoint_is_compatible(
            resume_checkpoint,
            source_identity=source_identity,
            duration=duration,
            n_windows=n_windows,
            energy_only=energy_only,
        ):
            for row in resume_checkpoint.get("chunks", []):
                index = row.get("chunk_index") if isinstance(row, dict) else None
                if isinstance(index, int) and not isinstance(index, bool):
                    resume_rows[index] = row

        def _guard_checkpoint() -> None:
            if checkpoint_guard is not None:
                checkpoint_guard()

        def _publish_chunk_checkpoint(record: dict) -> None:
            checkpoint_records.append(record)
            if on_chunk_checkpoint is None:
                return
            snapshot = self._checkpoint_snapshot(
                source_identity=source_identity,
                duration=duration,
                n_windows=n_windows,
                energy_only=energy_only,
                chunks=checkpoint_records,
            )
            if not snapshot:
                return
            _guard_checkpoint()
            on_chunk_checkpoint(snapshot)

        overlap_frames = int(self.overlap_sec * self.SR / self.HOP_LENGTH)

        for i in range(n_windows):
            _guard_checkpoint()
            # Berechne start_sample absolut und drift-frei
            start_sample = int(i * step * native_sr)
            chunk_start = start_sample / native_sr
            chunk_dur = min(self.window_sec, duration - chunk_start)

            # H-2: Fenster i deckt [chunk_start, chunk_start+window) ab, aber
            # die ersten overlap_sec hat Fenster i-1 bereits vollstaendig
            # geliefert. Beats/Trigger aus dieser Zone werden verworfen, damit
            # jede Zeitposition von genau einem Fenster stammt. Das erste
            # Fenster hat keinen Vorgaenger und behaelt alles.
            window_floor = None if i == 0 else chunk_start + self.overlap_sec
            for accumulator in (
                beat_acc,
                onset_acc,
                kick_acc,
                snare_acc,
                hihat_acc,
            ):
                accumulator.set_window_floor(window_floor)

            resume_row = resume_rows.get(i)
            if resume_row is not None and self._checkpoint_row_is_valid(
                resume_row,
                chunk_index=i,
                chunk_start=chunk_start,
                chunk_duration=chunk_dur,
                energy_only=energy_only,
            ):
                if chunk_dur >= 2.0:
                    payload = resume_row["payload"]
                    for value in payload["bpm_estimates"]:
                        bpm_est.add(float(value))
                    beat_acc.add_chunk_beats(payload["beats"])
                    onset_acc.add_chunk_beats(payload["onsets"])
                    kick_acc.add_chunk_beats(payload["kicks"])
                    snare_acc.add_chunk_beats(payload["snares"])
                    hihat_acc.add_chunk_beats(payload["hihats"])
                    energy_agg.add_checkpoint(
                        payload["energy_frames"],
                        float(payload["energy_max"]),
                    )
                    representative = payload["features"]
                    feature_weight = int(representative["chroma_weight"])
                    chroma_sum += (
                        np.asarray(
                            representative["chroma_mean"],
                            dtype=np.float64,
                        )
                        * feature_weight
                    )
                    chroma_weight += feature_weight
                    spectral_times.extend(representative["times"])
                    spectral_centroids.extend(representative["centroids"])
                    for band_name, values in representative["bands"].items():
                        spectral_bands.setdefault(band_name, []).extend(values)
                checkpoint_records.append(resume_row)
                chunk_evidence.append(
                    self._public_chunk_evidence(resume_row, reused=True)
                )
                if on_progress:
                    on_progress((i + 1) * 100.0 / n_windows)
                continue

            if chunk_dur < 2.0:
                record = {
                    "chunk_index": i,
                    "start_seconds": chunk_start,
                    "duration_seconds": max(chunk_dur, 0.0),
                    "status": "skipped",
                    "error": "terminal chunk shorter than 2.0 seconds",
                    "stages": {},
                }
                chunk_evidence.append(record)
                _publish_chunk_checkpoint(record)
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
                record = {
                    "chunk_index": i,
                    "start_seconds": chunk_start,
                    "duration_seconds": chunk_dur,
                    "status": "failed",
                    "stages": {
                        "load": {"status": "failed", "error": str(e)},
                        "beats": {"status": "blocked"},
                        "triggers": {"status": "blocked"},
                        "features": {"status": "blocked"},
                        "energy": {"status": "failed", "error": "load failed"},
                    },
                }
                chunk_evidence.append(record)
                _publish_chunk_checkpoint(record)
                continue

            stages: dict[str, dict] = {"load": {"status": "completed"}}
            bpm_count_before = bpm_est.count
            beat_count_before = beat_acc.count
            trigger_counts_before = (
                onset_acc.count,
                kick_acc.count,
                snare_acc.count,
                hihat_acc.count,
            )
            # --- Beat-Detection pro Chunk (bei energy_only uebersprungen) ---
            if not energy_only:
                beats_error = self._process_beats(
                    chunk, chunk_start, bpm_est, beat_acc
                )
                if beats_error is not None:
                    stage_errors.setdefault("beats", []).append(
                        f"chunk {i}: {beats_error}"
                    )
                    stages["beats"] = {
                        "status": "failed",
                        "error": beats_error,
                        "beat_count": 0,
                    }
                else:
                    stages["beats"] = {
                        "status": "completed",
                        "beat_count": beat_acc.count - beat_count_before,
                    }
                triggers_error = self._process_triggers(
                    chunk,
                    chunk_start,
                    onset_acc,
                    kick_acc,
                    snare_acc,
                    hihat_acc,
                )
                if triggers_error is not None:
                    stage_errors.setdefault("beats", []).append(
                        f"chunk {i}: {triggers_error}"
                    )
                    stages["triggers"] = {
                        "status": "failed",
                        "error": triggers_error,
                    }
                else:
                    stages["triggers"] = {
                        "status": "completed",
                        "onset_count": onset_acc.count - trigger_counts_before[0],
                        "kick_count": kick_acc.count - trigger_counts_before[1],
                        "snare_count": snare_acc.count - trigger_counts_before[2],
                        "hihat_count": hihat_acc.count - trigger_counts_before[3],
                    }
            else:
                stages["beats"] = {"status": "skipped"}
                stages["triggers"] = {"status": "skipped"}

            representative: dict = {}
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
                stages["features"] = {
                    "status": "completed",
                    "representative_point_count": len(representative["times"]),
                    "chroma_weight": feature_weight,
                }
            except Exception as e:
                logger.warning(
                    f"Full-duration Features bei {chunk_start:.1f}s fehlgeschlagen: {e}"
                )
                stage_errors.setdefault("features", []).append(
                    f"chunk {i}: {e}"
                )
                stages["features"] = {"status": "failed", "error": str(e)}

            # --- RMS-Energy pro Chunk ---
            energy_count_before = energy_agg.count
            energy_error = self._process_energy(
                chunk, is_first=(i == 0),
                overlap_frames=overlap_frames,
                energy_agg=energy_agg,
            )
            if energy_error is not None:
                stage_errors.setdefault("energy", []).append(
                    f"chunk {i}: {energy_error}"
                )
                energy_agg.add_gap(
                    chunk_dur,
                    is_first_chunk=(i == 0),
                    overlap_frames=overlap_frames,
                    sample_rate=self.SR,
                    hop_length=self.HOP_LENGTH,
                )
                stages["energy"] = {
                    "status": "failed",
                    "error": energy_error,
                    "point_count": energy_agg.count - energy_count_before,
                }
            else:
                stages["energy"] = {
                    "status": "completed",
                    "point_count": energy_agg.count - energy_count_before,
                }

            evidence = {
                "chunk_index": i,
                "start_seconds": chunk_start,
                "duration_seconds": chunk_dur,
                "status": (
                    "partial"
                    if any(
                        stage.get("status") == "failed"
                        for stage in stages.values()
                    )
                    else "completed"
                ),
                "stages": stages,
            }
            record = {
                **evidence,
                "payload": {
                    "bpm_estimates": bpm_est.values_since(bpm_count_before),
                    "beats": beat_acc.values_since(beat_count_before),
                    "onsets": onset_acc.values_since(trigger_counts_before[0]),
                    "kicks": kick_acc.values_since(trigger_counts_before[1]),
                    "snares": snare_acc.values_since(trigger_counts_before[2]),
                    "hihats": hihat_acc.values_since(trigger_counts_before[3]),
                    "energy_frames": energy_agg.values_since(energy_count_before),
                    "energy_max": float(energy_agg.global_max),
                    "features": representative,
                },
            }
            chunk_evidence.append(evidence)

            # Chunk-Buffer freigeben
            del chunk
            gc.collect()

            _publish_chunk_checkpoint(record)

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
            chunk_evidence=chunk_evidence,
            resume_checkpoint=self._checkpoint_snapshot(
                source_identity=source_identity,
                duration=duration,
                n_windows=n_windows,
                energy_only=energy_only,
                chunks=checkpoint_records,
            ),
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
        # Audit 2026-08-05 (CRIT-AUDIO-1/T2.4): auch der Streaming-Pfad muss die
        # Aggregate low/mid/high liefern — sonst haetten ausgerechnet lange
        # DJ-Mixe (>10 min) kein bass-/hoehengewichtetes Pacing.
        from .spectral_analyzer import add_aggregate_bands

        return {
            "times": times,
            "bands": add_aggregate_bands(band_points),
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
    ) -> Optional[str]:
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
            return None

        except Exception as e:
            logger.warning(f"Beat-Detection bei {chunk_start:.1f}s fehlgeschlagen: {e}")
            return str(e)

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

        # H-3 (Audit 2026-08-30): Bandgrenzen und Filterbank aus der
        # gemeinsamen Quelle `pb_studio.audio.band_params`. Vorher rechnete
        # diese Funktion eine eigene, dritte Fassung derselben Formel; das
        # Kick-Band bekam trotz Parametrierung fuer 20-150 Hz kein `fmin`
        # uebergeben, und dem Kick fehlte das `aggregate=np.median`, das
        # Router und Pacing-Engine beide setzen.
        def _band_times(
            *,
            signal: np.ndarray,
            band: tuple[float, float],
            aggregate=None,
        ) -> list[float]:
            fmin, fmax = band
            n_fft, n_mels = band_stft_params(self.SR, fmin, fmax)
            kwargs = {
                "y": signal,
                "sr": self.SR,
                "hop_length": hop,
                "n_fft": n_fft,
                "n_mels": n_mels,
                "fmin": fmin,
                "fmax": fmax,
            }
            if aggregate is not None:
                kwargs["aggregate"] = aggregate
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
            band=KICK_BAND,
            aggregate=np.median,
        )
        snare_times = _band_times(signal=chunk, band=SNARE_BAND)
        hihat_times = _band_times(signal=chunk, band=HIHAT_BAND)
        return onset_times, kick_times, snare_times, hihat_times

    def _process_triggers(
        self,
        chunk: np.ndarray,
        chunk_start: float,
        onset_acc: _BeatAccumulator,
        kick_acc: _BeatAccumulator,
        snare_acc: _BeatAccumulator,
        hihat_acc: _BeatAccumulator,
    ) -> Optional[str]:
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
            return None
        except Exception as e:
            logger.warning(
                f"Trigger-Detection bei {chunk_start:.1f}s fehlgeschlagen: {e}"
            )
            return str(e)

    # ------------------------------------------------------------------
    # Energy-Processing pro Chunk
    # ------------------------------------------------------------------
    def _process_energy(
        self,
        chunk: np.ndarray,
        is_first: bool,
        overlap_frames: int,
        energy_agg: _EnergyAggregator,
    ) -> Optional[str]:
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
            return None
        except Exception as e:
            logger.warning(f"Energy-Berechnung fehlgeschlagen: {e}")
            return str(e)

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
