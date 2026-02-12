"""
Audio Analyze Worker for PB Studio AMD

Performs beat detection and audio analysis using BeatNet.
VRAM Budget: 0 MB (CPU-only operation)
"""

import logging
from typing import Any, List, Optional

from ..base_worker import BaseWorker
from ...audio.analyzer import AudioAnalyzer
from ...models.audio import AudioAnalysisResult

logger = logging.getLogger(__name__)


class AudioAnalyzeWorker(BaseWorker):
    """
    Worker for audio analysis including BPM and beat detection.

    Uses the existing AudioAnalyzer (BeatNet) for offline analysis.
    All processing happens on CPU, no GPU required.

    VRAM Budget: 0 MB (CPU-only, BeatNet DBN inference)
    """

    def __init__(self, wav_path: str):
        """
        Initialize the audio analyze worker.

        Args:
            wav_path: Path to the WAV file to analyze
        """
        super().__init__("AudioAnalyzeWorker", vram_budget_mb=0)
        self.wav_path = wav_path
        self._analyzer: Optional[AudioAnalyzer] = None

    def _execute(self) -> AudioAnalysisResult:
        """
        Execute the audio analysis operation.

        Returns:
            AudioAnalysisResult with BPM, beats, and energy curve
        """
        self.emit_progress(0, "Initializing BeatNet analyzer...")
        self._check_cancelled()

        # Initialize analyzer (lazy loading)
        self._analyzer = AudioAnalyzer()

        if not self._analyzer.model_loaded:
            raise RuntimeError("BeatNet model failed to load. Check dependencies.")

        self.emit_progress(20, "Running beat detection...")
        self._check_cancelled()

        # Run analysis
        result = self._analyzer.analyze_file(self.wav_path)

        self.emit_progress(80, "Processing results...")
        self._check_cancelled()

        # Check for errors
        if "error" in result:
            raise RuntimeError(f"Analysis failed: {result['error']}")

        # Handle no-audio case
        if "warning" in result and result.get("bpm", 0) == 0:
            logger.warning(f"No audio analysis possible: {result['warning']}")
            return AudioAnalysisResult(
                bpm=0.0,
                beat_times=[],
                downbeat_times=[],
                energy_curve=[],
                confidence=0.0
            )

        # Extract beat data
        bpm = float(result.get("bpm", 0))
        beat_data = result.get("beat_data", [])
        beat_count = result.get("count", 0)

        # Process beat_data into beat_times and downbeat_times
        beat_times: List[float] = []
        downbeat_times: List[float] = []

        for beat in beat_data:
            if len(beat) >= 2:
                time = float(beat[0])
                beat_type = int(beat[1]) if len(beat) > 1 else 0
                beat_times.append(time)
                # BeatNet: beat_type 1 = downbeat
                if beat_type == 1:
                    downbeat_times.append(time)

        # Calculate confidence based on beat consistency
        confidence = self._calculate_confidence(bpm, beat_times)

        # Generate placeholder energy curve (normalized 0-1)
        # Full energy analysis would require additional processing
        energy_curve = self._generate_energy_placeholder(len(beat_times))

        logger.info(f"Analysis complete: BPM={bpm:.1f}, Beats={beat_count}, Confidence={confidence:.2f}")
        self.emit_progress(100, "Analysis complete")

        return AudioAnalysisResult(
            bpm=bpm,
            beat_times=beat_times,
            downbeat_times=downbeat_times,
            energy_curve=energy_curve,
            confidence=confidence
        )

    def _calculate_confidence(self, bpm: float, beat_times: List[float]) -> float:
        """
        Calculate confidence score based on beat regularity.

        Args:
            bpm: Detected BPM
            beat_times: List of beat timestamps

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if bpm <= 0 or len(beat_times) < 4:
            return 0.0

        # Calculate expected interval from BPM
        expected_interval = 60.0 / bpm

        # Calculate actual intervals
        intervals = []
        for i in range(1, len(beat_times)):
            interval = beat_times[i] - beat_times[i - 1]
            intervals.append(interval)

        if not intervals:
            return 0.0

        # Calculate deviation from expected
        import statistics
        mean_interval = statistics.mean(intervals)
        deviation = abs(mean_interval - expected_interval) / expected_interval

        # Calculate variance
        if len(intervals) > 1:
            variance = statistics.variance(intervals)
            variance_score = max(0, 1.0 - (variance / (expected_interval ** 2)))
        else:
            variance_score = 0.5

        # Combine scores
        deviation_score = max(0, 1.0 - deviation * 2)
        confidence = (deviation_score * 0.6 + variance_score * 0.4)

        return min(1.0, max(0.0, confidence))

    def _generate_energy_placeholder(self, beat_count: int) -> List[float]:
        """
        Generate placeholder energy curve.

        In a full implementation, this would analyze the audio waveform.
        For now, we return a simple placeholder based on beat count.

        Args:
            beat_count: Number of detected beats

        Returns:
            List of normalized energy values (0-1)
        """
        if beat_count == 0:
            return []

        # Generate smooth placeholder curve
        import math
        energy = []
        for i in range(min(beat_count, 1000)):
            # Simulate energy variation with sine wave
            value = 0.5 + 0.3 * math.sin(i * 0.1) + 0.2 * math.sin(i * 0.3)
            energy.append(max(0.0, min(1.0, value)))

        return energy
