"""Beat & Tempo Detection — BPM, rhythm patterns, drop detection."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Any
import numpy as np

try:
    import pydub
except ImportError:
    pydub = None


@dataclass
class DetectedBeat:
    """A single detected beat with confidence and context."""
    timestamp_ms: int = 0
    bpm_local: float = 120.0      # BPM at this beat
    confidence: float = 0.5       # 0.0 - 1.0 detection confidence
    energy_level: Optional[float] = None   # 0.0 (quiet) to 1.0 (loud)
    is_on_beat: bool = True      # Whether this beat aligns with expected grid

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "bpm_local": round(self.bpm_local, 1),
            "confidence": round(self.confidence, 3),
            "energy_level": round(self.energy_level, 3) if self.energy_level is not None else None,
        }


@dataclass
class BeatPattern:
    """Summary of a detected beat pattern (e.g., a section with consistent BPM)."""
    start_ms: int = 0
    end_ms: int = 0
    bpm_avg: float = 120.0
    bpm_std: float = 5.0
    total_beats: int = 0
    dominant_time_signature: str = "4/4"
    tempo_change_from_prev: Optional[float] = None  # BPM difference from previous section

    def to_dict(self) -> dict:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "bpm_avg": round(self.bpm_avg, 1),
            "bpm_std": round(self.bpm_std, 1),
            "total_beats": self.total_beats,
            "dominant_time_signature": self.dominant_time_signature,
            "tempo_change_from_prev": round(self.tempo_change_from_prev, 1) if self.tempo_change_from_prev else None,
        }


@dataclass
class BeatAnalysisResult:
    """Complete beat/tempo analysis result."""
    samples_analyzed: int = 0       # Number of audio frames analyzed
    duration_ms: int = 0           # Duration in milliseconds
    bpm_global: float = 120.0      # Overall average BPM
    bpm_min: float = 60.0
    bpm_max: float = 240.0
    tempo_changes: list[dict] = field(default_factory=list)   # {time_ms, from_bpm, to_bpm}
    patterns: list[BeatPattern] = field(default_factory=list)
    drops: list[dict] = field(default_factory=list)            # {time_ms, energy_spike_db, confidence}
    beat_grid_confidence: float = 0.5
    dominant_genre_hints: list[str] = field(default_factory=lambda: [])

    def to_dict(self) -> dict:
        return {
            "samples_analyzed": self.samples_analyzed,
            "duration_ms": self.duration_ms,
            "bpm_global": round(self.bpm_global, 1),
            "bpm_min": round(self.bpm_min, 1),
            "bpm_max": round(self.bpm_max, 1),
            "tempo_changes_count": len(self.tempo_changes),
            "patterns_count": len(self.patterns),
            "drops_count": len(self.drops),
            "beat_grid_confidence": round(self.beat_grid_confidence, 3),
        }


class BeatDetector:
    """
    Detects beat patterns, tempo (BPM), and rhythm characteristics from audio.

    Note: This is a simplified model-based detector. For production-grade analysis,
    pair with librosa / pydub for actual FFT/autocorrelation processing.

    Usage:
        detector = BeatDetector()
        result = detector.analyze(audio_path)
    """

    # Genre BPM ranges (heuristic hints)
    GENRE_BPM_RANGES = {
        "ambient": (60, 100),
        "house": (120, 135),
        "techno": (125, 145),
        "drum_and_bass": (165, 180),
        "trance": (128, 140),
        "rock": (80, 150),
        "pop": (95, 135),
        "rap": (70, 150),
        "jazz": (60, 180),
    }

    def __init__(self):
        self.result: Optional[BeatAnalysisResult] = None

    def analyze(self, audio_path: str | bytes) -> BeatAnalysisResult:
        """
        Analyze audio for beat/tempo patterns.

        Args:
            audio_path: Path to WAV/MP3/AAC file or raw audio data.

        Returns:
            BeatAnalysisResult with BPM, tempo changes, and drop locations.
        """
        if hasattr(audio_path, "__fspath__"):
            audio_path = str(audio_path)

        if pydub is not None:
            try:
                if isinstance(audio_path, (str, bytes)):
                    audio = pydub.AudioSegment.from_file(audio_path) if isinstance(audio_path, str) else pydub.AudioSegment(
                        bytes(audio_path), frame_rate=44100, channels=2, sample_width=2
                    )
                    return self._analyze_audio(audio)
                elif hasattr(audio_path, "get_array_of_samples"):
                    return self._analyze_audio(audio_path)
            except Exception:
                pass

        if isinstance(audio_path, str):
            try:
                import soundfile as sf
                data, sr = sf.read(audio_path)
                if len(data.shape) > 1:
                    data = data.mean(axis=1)
                return self._analyze_audio_data(data, sr)
            except Exception:
                pass

            try:
                import wave
                with wave.open(audio_path, "rb") as wf:
                    sr = wf.getframerate()
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    frames = wf.readframes(wf.getnframes())
                    if sampwidth == 2:
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64) / 32768.0
                    elif sampwidth == 1:
                        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
                    elif sampwidth == 4:
                        data = np.frombuffer(frames, dtype=np.int32).astype(np.float64) / 2147483648.0
                    else:
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64) / 32768.0
                    if n_channels > 1:
                        data = data.reshape((-1, n_channels)).mean(axis=1)
                    return self._analyze_audio_data(data, sr)
            except Exception:
                pass

        raise ImportError("pydub, soundfile or standard wave reader required to load audio file path.")

    def analyze_from_data(self, samples: list[int | float] | np.ndarray, sample_rate: int = 44100) -> BeatAnalysisResult:
        """Analyze raw PCM amplitude samples for beat detection."""
        if not len(samples):
            return BeatAnalysisResult()

        arr = np.array(samples, dtype=np.float64)
        if np.max(np.abs(arr)) > 1.5:
            arr = arr / 32768.0

        self.result = self._analyze_audio_data(arr, sample_rate)
        return self.result

    def analyze_from_wav(self, audio_segment: Any) -> BeatAnalysisResult:
        """Analyze a pydub AudioSegment directly."""
        return self._analyze_audio(audio_segment)

    def _analyze_audio(self, audio: Any) -> BeatAnalysisResult:
        """Analyze a pydub AudioSegment."""
        sample_rate = getattr(audio, "frame_rate", 44100)
        samples_raw = audio.get_array_of_samples()
        arr = np.array(samples_raw, dtype=np.float64)
        channels = getattr(audio, "channels", 1)
        if channels > 1:
            arr = arr.reshape((-1, channels)).mean(axis=1)

        max_val = np.max(np.abs(arr)) if len(arr) > 0 else 1.0
        if max_val > 1.0:
            arr = arr / max_val

        return self._analyze_audio_data(arr, sample_rate)

    def _analyze_audio_data(self, arr: np.ndarray, sample_rate: int = 44100) -> BeatAnalysisResult:
        """Core mathematical analysis pipeline on normalized float array."""
        samples_analyzed = len(arr)
        duration_ms = int(samples_analyzed * 1000 / max(1, sample_rate))

        frame_ms = 20  # 50 fps energy envelope
        hop_samples = max(1, int(sample_rate * frame_ms / 1000))

        rms_frames = []
        for i in range(0, samples_analyzed, hop_samples):
            chunk = arr[i:i + hop_samples]
            if len(chunk) > 0:
                rms_val = float(np.sqrt(np.mean(chunk**2)))
                rms_frames.append(rms_val)
            else:
                rms_frames.append(0.0)

        rms_arr = np.array(rms_frames, dtype=np.float64)
        mean_rms = np.mean(rms_arr) if len(rms_arr) > 0 else 0.0
        std_rms = np.std(rms_arr) if len(rms_arr) > 0 else 1.0
        norm_rms = (rms_arr - mean_rms) / (std_rms + 1e-6)

        bpm_scores: dict[float, float] = {}
        min_bpm = 60.0
        max_bpm = 200.0

        for bpm in np.arange(min_bpm, max_bpm + 1, 1.0):
            period_frames = int(round((60000.0 / bpm) / frame_ms))
            if period_frames < 2 or period_frames >= len(norm_rms) // 2:
                continue

            v1 = norm_rms[:-period_frames]
            v2 = norm_rms[period_frames:]
            if len(v1) > 10:
                corr = float(np.mean(v1 * v2))
                bpm_scores[bpm] = corr

        best_bpm = max(bpm_scores, key=lambda k: bpm_scores[k]) if bpm_scores else 120.0
        best_score = bpm_scores.get(best_bpm, 0.5)

        drops = self._detect_energy_drops(rms_frames, frame_ms)

        chunk_frames = int(8000 / frame_ms)
        tempo_changes: list[dict] = []
        prev_bpm = best_bpm

        if len(norm_rms) > chunk_frames * 2:
            for i in range(0, len(norm_rms) - chunk_frames, chunk_frames):
                chunk_norm = norm_rms[i:i + chunk_frames]
                chunk_bpm = self._quick_tempo_est(chunk_norm, frame_ms)
                time_ms = int(i * frame_ms)
                if abs(chunk_bpm - prev_bpm) > 4.0:
                    tempo_changes.append({
                        "time_ms": time_ms,
                        "from_bpm": round(prev_bpm, 1),
                        "to_bpm": round(chunk_bpm, 1),
                    })
                    prev_bpm = chunk_bpm

        patterns = []
        if tempo_changes:
            starts = [0] + [tc["time_ms"] for tc in tempo_changes]
            for j in range(len(starts) - 1):
                ps = starts[j]
                pe = starts[j + 1]
                b_avg = tempo_changes[j]["from_bpm"]
                patterns.append(BeatPattern(
                    start_ms=ps,
                    end_ms=pe,
                    bpm_avg=b_avg,
                    total_beats=int((pe - ps) / 1000.0 * b_avg / 60.0),
                ))
            last_start = starts[-1]
            patterns.append(BeatPattern(
                start_ms=last_start,
                end_ms=duration_ms,
                bpm_avg=prev_bpm,
                total_beats=int((duration_ms - last_start) / 1000.0 * prev_bpm / 60.0),
            ))
        else:
            patterns.append(BeatPattern(
                start_ms=0,
                end_ms=duration_ms,
                bpm_avg=best_bpm,
                total_beats=int(duration_ms / 1000.0 * best_bpm / 60.0),
            ))

        genre_hints = self._suggest_genres(best_bpm)

        self.result = BeatAnalysisResult(
            samples_analyzed=samples_analyzed,
            duration_ms=duration_ms,
            bpm_global=round(float(best_bpm), 1),
            bpm_min=round(float(min(bpm_scores.keys())), 1) if bpm_scores else 60.0,
            bpm_max=round(float(max(bpm_scores.keys())), 1) if bpm_scores else 240.0,
            tempo_changes=tempo_changes,
            patterns=patterns,
            drops=drops,
            beat_grid_confidence=round(max(0.1, min(1.0, (best_score + 1.0) / 2.0)), 3),
            dominant_genre_hints=genre_hints,
        )
        return self.result

    def _quick_tempo_est(self, norm_rms: np.ndarray, frame_ms: int = 20) -> float:
        """Quick BPM estimate on a segment."""
        if len(norm_rms) < 50:
            return 120.0
        scores: dict[float, float] = {}
        for bpm in range(70, 180, 2):
            lag = int(round((60000.0 / bpm) / frame_ms))
            if lag < len(norm_rms) // 2 and lag > 1:
                scores[float(bpm)] = float(np.mean(norm_rms[:-lag] * norm_rms[lag:]))
        return max(scores, key=lambda k: scores[k]) if scores else 120.0

    def _detect_energy_drops(self, rms_frames: list[float], frame_ms: int = 20) -> list[dict]:
        """Detect energy spikes/drops for cut suggestions."""
        n = len(rms_frames)
        if n < 10:
            return []

        arr = np.array(rms_frames, dtype=np.float64)
        median_val = float(np.median(arr))
        std_val = float(np.std(arr))
        threshold = median_val + 1.5 * std_val

        drops: list[dict] = []
        min_distance_frames = int(1000 / frame_ms)  # At least 1.0s between drops

        last_drop_frame = -min_distance_frames
        for i in range(1, n - 1):
            if arr[i] > threshold and arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
                if (i - last_drop_frame) >= min_distance_frames:
                    spike_db = float(20.0 * np.log10(max(arr[i], 1e-5) / max(median_val, 1e-5)))
                    conf = float(min(1.0, (arr[i] - threshold) / (std_val + 1e-5)))
                    drops.append({
                        "time_ms": int(i * frame_ms),
                        "energy_spike_db": round(spike_db, 2),
                        "confidence": round(max(0.2, conf), 3),
                    })
                    last_drop_frame = i

        return drops

    def _suggest_genres(self, bpm: float) -> list[str]:
        """Heuristic genre suggestions based on BPM."""
        hints = []
        if 60 <= bpm < 85:
            hints.extend(["ambient", "lo-fi", "chillout"])
        elif 85 <= bpm < 115:
            hints.extend(["hip-hop", "downtempo", "indie"])
        elif 115 <= bpm < 128:
            hints.extend(["deep house", "tech house", "melodic techno"])
        elif 128 <= bpm < 140:
            hints.extend(["progressive house", "trance", "techno"])
        elif 140 <= bpm < 155:
            hints.extend(["psytrance", "hard techno", "acid"])
        elif 155 <= bpm < 185:
            hints.extend(["drum and bass", "breakbeat", "hardcore"])
        else:
            hints.append("experimental")
        return list(dict.fromkeys(hints))[:3]

    def get_beat_grid(self, bpm: float = 120.0, duration_ms: int = 60000) -> list[int]:
        """Get millisecond timestamps for a beat grid at given BPM."""
        period_ms = max(1, int(round(60000.0 / bpm))) if bpm > 0 else 500
        return [t for t in range(0, duration_ms, period_ms)][:24]
