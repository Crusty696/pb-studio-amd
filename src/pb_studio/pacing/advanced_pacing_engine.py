"""
Advanced Pacing Engine - Musical Intelligence for Video Editing

This engine creates rhythm-synchronized video timelines using:
- Beat detection and tempo analysis
- Energy curve mapping
- Musical structure recognition (intro/verse/chorus/bridge)
- Dynamic cut timing with sub-frame precision

The engine generates Edit Decision Lists (EDL) compatible with the
VideoGenerator pipeline.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SyncMode(Enum):
    """Synchronization strategies for video cuts."""
    BEAT_SYNC = "beat_sync"          # Cut exactly on beats
    ENERGY_SYNC = "energy_sync"      # Cut based on energy peaks
    EMOTIONAL_SYNC = "emotional"     # Cut based on musical phrases
    HYBRID = "hybrid"                # Combine all strategies


class TransitionType(Enum):
    """Video transition types."""
    HARD_CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    ZOOM = "zoom"
    SLIDE = "slide"


@dataclass
class PacingConfig:
    """
    Configuration for the pacing engine.

    Compatible with VideoGenerator config format for seamless integration.
    """
    pacing: int = 3                   # 1-5 (slow to fast)
    precision: int = 8                # 1-10 (beat snapping strength)
    energy_react: int = 5             # 0-10 (audio reactivity)
    chaos: int = 2                    # 0-10 (randomness/variation)
    min_clip_length: float = 2.0      # Minimum clip duration (seconds)
    max_clip_length: float = 8.0      # Maximum clip duration (seconds)
    sync_mode: SyncMode = SyncMode.HYBRID
    allow_transitions: bool = True
    prefer_downbeats: bool = True     # Favor strong beats (1st beat of measure)
    energy_smoothing: float = 0.3     # Smoothing factor for energy curve

    def to_legacy_dict(self) -> Dict:
        """Convert to VideoGenerator-compatible config format."""
        return {
            "pacing": self.pacing,
            "precision": self.precision,
            "energy_react": self.energy_react,
            "chaos": self.chaos,
            "min_dur": self.min_clip_length,
            "max_dur": self.max_clip_length
        }


@dataclass
class CutPoint:
    """Represents a single cut decision in the timeline."""
    time: float                       # Cut timestamp (seconds)
    duration: float                   # Clip duration (seconds)
    energy: float                     # Local energy level (0.0 to 1.0)
    beat_aligned: bool = False        # Was this cut aligned to a beat?
    beat_strength: float = 0.0        # Strength of nearest beat (0.0 to 1.0)
    transition: TransitionType = TransitionType.HARD_CUT
    confidence: float = 1.0           # Algorithm confidence (0.0 to 1.0)
    metadata: Dict = field(default_factory=dict)

    @property
    def end_time(self) -> float:
        """Calculate end timestamp."""
        return self.time + self.duration


class AdvancedPacingEngine:
    """
    Main pacing engine for intelligent video timeline generation.

    This engine analyzes audio structure and generates optimal cut points
    that synchronize with musical elements (beats, energy, phrases).
    """

    def __init__(self, config: Optional[PacingConfig] = None):
        """
        Initialize the pacing engine.

        Args:
            config: PacingConfig instance. If None, uses default settings.
        """
        self.config = config or PacingConfig()
        self.audio_analysis: Optional[Dict] = None
        self.energy_curve: Optional[np.ndarray] = None
        self.timeline: List[CutPoint] = []

    def analyze_audio_structure(self, analysis: Dict, rms: np.ndarray, times: np.ndarray):
        """
        Process audio analysis data and prepare for timeline generation.

        Args:
            analysis: Dict from AudioAnalyzer with beat_data, bpm, etc.
            rms: RMS energy array from librosa
            times: Corresponding time values for RMS array
        """
        self.audio_analysis = analysis

        # Smooth energy curve
        if self.config.energy_smoothing > 0:
            self.energy_curve = self._smooth_energy(rms, self.config.energy_smoothing)
        else:
            self.energy_curve = rms

        # Normalize energy
        if len(self.energy_curve) > 0:
            min_val = np.min(self.energy_curve)
            max_val = np.max(self.energy_curve)

            if max_val > min_val:
                self.energy_curve = (self.energy_curve - min_val) / (max_val - min_val)
            else:
                self.energy_curve = np.zeros_like(self.energy_curve)

        # Store time mapping
        self.energy_times = times

        logger.info(f"Audio structure analyzed. BPM: {analysis.get('bpm', 0)}, "
                   f"Beats: {len(analysis.get('beat_data', []))}")

    def plan_cuts(self, total_duration: float) -> List[CutPoint]:
        """
        Generate the complete cut timeline.

        Args:
            total_duration: Total audio duration in seconds

        Returns:
            List of CutPoint objects defining the edit sequence
        """
        if self.audio_analysis is None:
            raise ValueError("Audio structure not analyzed. Call analyze_audio_structure() first.")

        self.timeline = []

        # Extract beat information
        beats = [b[0] for b in self.audio_analysis.get("beat_data", [])]
        downbeats = self._identify_downbeats(beats)
        bpm = self.audio_analysis.get("bpm", 120)

        # Generate cuts based on sync mode
        if self.config.sync_mode == SyncMode.BEAT_SYNC:
            self.timeline = self._plan_beat_sync(beats, downbeats, total_duration)
        elif self.config.sync_mode == SyncMode.ENERGY_SYNC:
            self.timeline = self._plan_energy_sync(total_duration)
        elif self.config.sync_mode == SyncMode.EMOTIONAL_SYNC:
            self.timeline = self._plan_emotional_sync(beats, total_duration)
        else:  # HYBRID
            self.timeline = self._plan_hybrid_sync(beats, downbeats, total_duration)

        logger.info(f"Generated {len(self.timeline)} cuts. "
                   f"Total duration: {total_duration:.2f}s")

        return self.timeline

    def _plan_hybrid_sync(
        self,
        beats: List[float],
        downbeats: List[float],
        total_duration: float
    ) -> List[CutPoint]:
        """
        Hybrid synchronization combining beat alignment and energy curves.

        This is the most sophisticated mode, balancing musical structure
        with dynamic energy changes.
        """
        cuts = []
        current_time = 0.0

        # Pacing configuration
        pacing_bias = 1.0 - ((self.config.pacing - 1) / 4.0)  # 1=slow, 5=fast
        precision_factor = self.config.precision / 10.0
        energy_factor = self.config.energy_react / 10.0
        chaos_factor = self.config.chaos / 10.0

        while current_time < total_duration:
            # 1. Calculate target duration based on energy
            local_energy = self._get_energy_at_time(current_time)

            # High energy -> shorter clips (faster pacing)
            # Low energy -> longer clips (slower pacing)
            speed_factor = pacing_bias - (local_energy * energy_factor * 0.5)
            speed_factor = max(0.0, min(1.0, speed_factor))

            target_dur = (self.config.min_clip_length +
                         (self.config.max_clip_length - self.config.min_clip_length) * speed_factor)

            # 2. Apply chaos (creative variation)
            if chaos_factor > 0:
                import random
                jitter = (random.random() - 0.5) * 2 * chaos_factor * \
                        (self.config.max_clip_length - self.config.min_clip_length)
                target_dur += jitter

            target_dur = max(self.config.min_clip_length,
                           min(self.config.max_clip_length, target_dur))

            # 3. Align to nearest beat (precision-based)
            proposed_end = current_time + target_dur
            beat_aligned = False
            beat_strength = 0.0

            if beats and precision_factor > 0:
                # Find nearest beat
                nearest_beat = min(beats, key=lambda x: abs(x - proposed_end))
                distance = abs(nearest_beat - proposed_end)

                # Calculate snap window (higher precision = tighter snap)
                snap_window = 2.0 * precision_factor

                if distance < snap_window:
                    # Check if it's a downbeat (stronger alignment)
                    if self.config.prefer_downbeats and nearest_beat in downbeats:
                        proposed_end = nearest_beat
                        beat_aligned = True
                        beat_strength = 1.0
                    elif precision_factor > 0.5:  # Only snap to regular beats with high precision
                        proposed_end = nearest_beat
                        beat_aligned = True
                        beat_strength = 0.7

            final_dur = proposed_end - current_time

            # Safety check: No zero-length clips
            if final_dur < 0.5:
                final_dur = 0.5
                proposed_end = current_time + final_dur

            # 4. Determine transition type
            transition = self._select_transition(local_energy, beat_aligned)

            # 5. Calculate confidence score
            confidence = self._calculate_confidence(
                beat_aligned, local_energy, final_dur
            )

            # 6. Create CutPoint
            cut = CutPoint(
                time=current_time,
                duration=final_dur,
                energy=local_energy,
                beat_aligned=beat_aligned,
                beat_strength=beat_strength,
                transition=transition,
                confidence=confidence,
                metadata={
                    "pacing_level": self.config.pacing,
                    "precision_applied": precision_factor,
                    "chaos_applied": chaos_factor
                }
            )

            cuts.append(cut)
            current_time = proposed_end

        return cuts

    def _plan_beat_sync(
        self,
        beats: List[float],
        downbeats: List[float],
        total_duration: float
    ) -> List[CutPoint]:
        """Pure beat synchronization - cuts only on beats."""
        if not beats:
            logger.warning("No beats detected. Falling back to time-based cuts.")
            return self._plan_time_based(total_duration)

        cuts = []
        beat_idx = 0

        while beat_idx < len(beats) - 1:
            start_time = beats[beat_idx]

            # Find next beat within clip length constraints
            target_end = start_time + self.config.min_clip_length

            # Find beat closest to target end
            valid_beats = [b for b in beats[beat_idx+1:]
                          if start_time + self.config.min_clip_length <= b <=
                             start_time + self.config.max_clip_length]

            if not valid_beats:
                # Use next beat regardless
                if beat_idx + 1 < len(beats):
                    end_time = beats[beat_idx + 1]
                else:
                    break
            else:
                end_time = valid_beats[0]

            duration = end_time - start_time
            local_energy = self._get_energy_at_time(start_time)
            is_downbeat = start_time in downbeats

            cut = CutPoint(
                time=start_time,
                duration=duration,
                energy=local_energy,
                beat_aligned=True,
                beat_strength=1.0 if is_downbeat else 0.7,
                transition=TransitionType.HARD_CUT,
                confidence=1.0
            )

            cuts.append(cut)

            # Move to next beat
            beat_idx = beats.index(end_time) if end_time in beats else beat_idx + 1

        return cuts

    def _plan_energy_sync(self, total_duration: float) -> List[CutPoint]:
        """Energy-based cuts - align with energy peaks and valleys."""
        if self.energy_curve is None or len(self.energy_curve) == 0:
            return self._plan_time_based(total_duration)

        # Detect energy peaks
        peaks = self._detect_energy_peaks()

        cuts = []
        current_time = 0.0

        for peak_time in peaks:
            if peak_time <= current_time:
                continue

            duration = peak_time - current_time

            # Clamp to clip length constraints
            if duration < self.config.min_clip_length:
                continue
            if duration > self.config.max_clip_length:
                duration = self.config.max_clip_length

            local_energy = self._get_energy_at_time(current_time)

            cut = CutPoint(
                time=current_time,
                duration=duration,
                energy=local_energy,
                beat_aligned=False,
                transition=self._select_transition(local_energy, False),
                confidence=0.8
            )

            cuts.append(cut)
            current_time += duration

        return cuts

    def _plan_emotional_sync(self, beats: List[float], total_duration: float) -> List[CutPoint]:
        """
        Emotional/musical phrase-based cuts.

        Attempts to identify musical sections (4-bar, 8-bar phrases)
        and cut on phrase boundaries.
        """
        if not beats:
            return self._plan_time_based(total_duration)

        bpm = self.audio_analysis.get("bpm", 120)
        bar_length = (60.0 / bpm) * 4  # 4 beats per bar

        cuts = []
        current_time = 0.0
        phrase_lengths = [4, 8, 16]  # Bars per phrase

        while current_time < total_duration:
            # Choose phrase length based on pacing
            if self.config.pacing >= 4:
                phrase_bars = phrase_lengths[0]  # 4 bars (fast)
            elif self.config.pacing >= 3:
                phrase_bars = phrase_lengths[1]  # 8 bars (medium)
            else:
                phrase_bars = phrase_lengths[2]  # 16 bars (slow)

            duration = phrase_bars * bar_length
            duration = max(self.config.min_clip_length,
                          min(self.config.max_clip_length, duration))

            local_energy = self._get_energy_at_time(current_time)

            cut = CutPoint(
                time=current_time,
                duration=duration,
                energy=local_energy,
                beat_aligned=False,
                transition=TransitionType.FADE,  # Smoother transitions for phrases
                confidence=0.7,
                metadata={"phrase_length": phrase_bars}
            )

            cuts.append(cut)
            current_time += duration

        return cuts

    def _plan_time_based(self, total_duration: float) -> List[CutPoint]:
        """Fallback: Simple time-based cuts."""
        cuts = []
        current_time = 0.0
        avg_duration = (self.config.min_clip_length + self.config.max_clip_length) / 2.0

        while current_time < total_duration:
            duration = min(avg_duration, total_duration - current_time)

            cut = CutPoint(
                time=current_time,
                duration=duration,
                energy=0.5,
                beat_aligned=False,
                confidence=0.3  # Low confidence
            )

            cuts.append(cut)
            current_time += duration

        return cuts

    def _get_energy_at_time(self, time: float) -> float:
        """Get interpolated energy value at specific timestamp."""
        if self.energy_curve is None or len(self.energy_curve) == 0:
            return 0.5  # Neutral energy

        # Find nearest time index
        if not hasattr(self, 'energy_times') or len(self.energy_times) == 0:
            return 0.5

        idx = np.searchsorted(self.energy_times, time)
        idx = min(idx, len(self.energy_curve) - 1)

        return float(self.energy_curve[idx])

    def _identify_downbeats(self, beats: List[float]) -> List[float]:
        """
        Identify downbeats (first beat of each measure).

        Assumes 4/4 time signature.
        """
        if not beats or len(beats) < 4:
            return beats

        # Use beat strength from analysis if available
        beat_data = self.audio_analysis.get("beat_data", [])

        if beat_data and len(beat_data[0]) >= 2:
            # BeatNet provides beat position (1, 2, 3, 4)
            downbeats = [b[0] for b in beat_data if b[1] == 1]
        else:
            # Fallback: Assume every 4th beat is a downbeat
            downbeats = [beats[i] for i in range(0, len(beats), 4)]

        return downbeats

    def _smooth_energy(self, energy: np.ndarray, smoothing: float) -> np.ndarray:
        """Apply moving average smoothing to energy curve."""
        if smoothing <= 0 or len(energy) < 3:
            return energy

        window_size = max(3, int(len(energy) * smoothing))

        # Ensure window size is odd
        if window_size % 2 == 0:
            window_size += 1

        # Simple moving average
        kernel = np.ones(window_size) / window_size
        smoothed = np.convolve(energy, kernel, mode='same')

        return smoothed

    def _detect_energy_peaks(self, threshold: float = 0.7) -> List[float]:
        """Detect energy peaks in the audio."""
        if self.energy_curve is None or not hasattr(self, 'energy_times'):
            return []

        peaks = []

        for i in range(1, len(self.energy_curve) - 1):
            # Local maximum detection
            if (self.energy_curve[i] > self.energy_curve[i-1] and
                self.energy_curve[i] > self.energy_curve[i+1] and
                self.energy_curve[i] >= threshold):
                peaks.append(float(self.energy_times[i]))

        return peaks

    def _select_transition(self, energy: float, beat_aligned: bool) -> TransitionType:
        """Select appropriate transition based on energy and beat alignment."""
        if not self.config.allow_transitions:
            return TransitionType.HARD_CUT

        # High energy + beat aligned = hard cut
        if energy > 0.7 and beat_aligned:
            return TransitionType.HARD_CUT

        # Low energy = fade
        if energy < 0.3:
            return TransitionType.FADE

        # Medium energy = crossfade
        if 0.3 <= energy <= 0.7:
            return TransitionType.CROSSFADE

        return TransitionType.HARD_CUT

    def _calculate_confidence(
        self,
        beat_aligned: bool,
        energy: float,
        duration: float
    ) -> float:
        """Calculate confidence score for a cut decision."""
        score = 0.5  # Base confidence

        # Boost for beat alignment
        if beat_aligned:
            score += 0.3

        # Boost for good duration range
        mid_duration = (self.config.min_clip_length + self.config.max_clip_length) / 2.0
        duration_quality = 1.0 - abs(duration - mid_duration) / mid_duration
        score += duration_quality * 0.2

        return min(1.0, max(0.0, score))

    def generate_edit_decision_list(self) -> List[Dict]:
        """
        Generate VideoGenerator-compatible edit decision list.

        Returns:
            List of dicts with {time, duration, energy} for each cut
        """
        if not self.timeline:
            raise ValueError("No timeline generated. Call plan_cuts() first.")

        edl = []

        for cut in self.timeline:
            edl.append({
                "time": cut.time,
                "duration": cut.duration,
                "energy": cut.energy,
                "beat_aligned": cut.beat_aligned,
                "transition": cut.transition.value,
                "confidence": cut.confidence
            })

        return edl

    def get_statistics(self) -> Dict:
        """Get statistics about the generated timeline."""
        if not self.timeline:
            return {}

        durations = [c.duration for c in self.timeline]
        energies = [c.energy for c in self.timeline]
        beat_aligned_count = sum(1 for c in self.timeline if c.beat_aligned)

        return {
            "total_cuts": len(self.timeline),
            "beat_aligned_cuts": beat_aligned_count,
            "beat_alignment_ratio": beat_aligned_count / len(self.timeline) if self.timeline else 0,
            "avg_cut_duration": np.mean(durations) if durations else 0,
            "min_cut_duration": np.min(durations) if durations else 0,
            "max_cut_duration": np.max(durations) if durations else 0,
            "avg_energy": np.mean(energies) if energies else 0,
            "avg_confidence": np.mean([c.confidence for c in self.timeline])
        }
