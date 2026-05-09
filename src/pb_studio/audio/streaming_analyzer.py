"""Streaming-Audio-Analyzer fuer lange Mixe (>60min).

Standard librosa.load + BeatNet laden volle Datei in RAM. Fuer 90min-Mix:
~480MB RAM + langes Inference. Streaming-Approach chunkt Datei in 5min-Windows
mit 30s Overlap, beats werden pro Window detected + dedupliziert.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StreamingAnalysisResult:
    duration_seconds: float
    bpm: float = 0.0
    beats: list[float] = field(default_factory=list)
    energy_curve: list[float] = field(default_factory=list)
    window_count: int = 0


class StreamingAudioAnalyzer:
    """Chunked Audio-Analyse fuer lange Mixe."""

    DEFAULT_WINDOW_SEC = 300.0  # 5min
    DEFAULT_OVERLAP_SEC = 30.0
    BEAT_DEDUP_THRESHOLD_SEC = 0.5

    def __init__(
        self,
        window_sec: float = DEFAULT_WINDOW_SEC,
        overlap_sec: float = DEFAULT_OVERLAP_SEC,
    ):
        self.window_sec = window_sec
        self.overlap_sec = overlap_sec
        self._beat_detector = None

    def analyze(
        self,
        audio_path: str | Path,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> StreamingAnalysisResult:
        """Volle chunked Analyse. on_progress(0..100)."""
        import librosa

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio not found: {path}")

        duration = librosa.get_duration(path=str(path))
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}")

        # For files <= 1.5x window, fallback to single-shot
        if duration <= self.window_sec * 1.5:
            return self._analyze_single_shot(path, duration, on_progress)

        return self._analyze_streaming(path, duration, on_progress)

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
        y, sr = librosa.load(str(path), sr=22050, mono=True)
        if on_progress:
            on_progress(40.0)

        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        if on_progress:
            on_progress(70.0)
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
        energy = (rms / rms_max).tolist() if rms_max > 0 else []

        if on_progress:
            on_progress(100.0)
        return StreamingAnalysisResult(
            duration_seconds=duration,
            bpm=float(tempo) if hasattr(tempo, '__float__') else float(tempo[0]),
            beats=beats,
            energy_curve=energy,
            window_count=1,
        )

    def _analyze_streaming(
        self,
        path: Path,
        duration: float,
        on_progress: Optional[Callable[[float], None]],
    ) -> StreamingAnalysisResult:
        """Chunked Analyse fuer grosse Files."""
        import librosa

        # Berechne windows
        step = self.window_sec - self.overlap_sec
        n_windows = int(np.ceil((duration - self.overlap_sec) / step))
        n_windows = max(1, n_windows)

        all_beats: list[float] = []
        all_energy: list[float] = []
        bpm_estimates: list[float] = []

        for i in range(n_windows):
            start = i * step
            window_dur = min(self.window_sec, duration - start)
            if window_dur < 5.0:  # zu kurzes Window skip
                continue

            try:
                y, sr = librosa.load(
                    str(path), sr=22050, mono=True, offset=start, duration=window_dur
                )
            except Exception as e:
                logger.warning(f"Window {i} load failed: {e}")
                continue

            # Beats pro Window
            try:
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                window_beats = librosa.frames_to_time(beat_frames, sr=sr)
                # Offset addieren
                window_beats_abs = (window_beats + start).tolist()
                all_beats.extend(window_beats_abs)
                bpm_estimates.append(
                    float(tempo) if hasattr(tempo, '__float__') else float(tempo[0])
                )
            except Exception as e:
                logger.warning(f"Window {i} beat-track failed: {e}")

            # Energy pro Window
            try:
                rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
                rms_norm = (rms / max(np.max(rms), 1e-9)).tolist()
                # Skip overlap-region in middle/end windows um Doppel-Counting zu vermeiden
                if i > 0:
                    overlap_frames = int(self.overlap_sec * sr / 512)
                    rms_norm = rms_norm[overlap_frames:]
                all_energy.extend(rms_norm)
            except Exception as e:
                logger.warning(f"Window {i} energy failed: {e}")

            if on_progress:
                on_progress((i + 1) * 100.0 / n_windows)

        # Beat-dedup an Window-Boundaries
        all_beats.sort()
        deduped_beats: list[float] = []
        for b in all_beats:
            if not deduped_beats or (b - deduped_beats[-1]) > self.BEAT_DEDUP_THRESHOLD_SEC:
                deduped_beats.append(b)

        # Median-BPM ueber alle Windows
        bpm = float(np.median(bpm_estimates)) if bpm_estimates else 0.0

        return StreamingAnalysisResult(
            duration_seconds=duration,
            bpm=bpm,
            beats=deduped_beats,
            energy_curve=all_energy,
            window_count=n_windows,
        )
