"""
Advanced Pacing Engine - Musical Intelligence for Video Editing

This engine creates rhythm-synchronized video timelines using:
- Beat detection and tempo analysis
- Energy curve mapping
- Musical structure recognition (intro/verse/chorus/bridge)
- Dynamic cut timing with sub-frame precision

The engine generates Edit Decision Lists (EDL) compatible with the
VideoGenerator pipeline.

AMD-Anpassung v2:
- NV-kompatible API ergänzt: generate_cut_list(), generate_cut_list_with_stems(),
  analyze_song_structure(), trigger_settings Property
- Bestehende EDL-Architektur (plan_cuts, CutPoint) bleibt vollständig erhalten
- Portiert von NVIDIA-Version: Multi-Trigger, Song-Struktur, Stem-Support
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# =============================================================================
# NV-Kompatibilitäts-Konstanten (von NVIDIA-Version portiert)
# =============================================================================

# Intensitäts-Multiplikatoren für Song-Segmente
STRUCTURE_INTENSITY_MULTIPLIERS = {
    "intro": 0.6,
    "verse": 0.8,
    "chorus": 1.2,
    "bridge": 0.7,
    "drop": 1.5,
    "buildup": 1.0,
    "breakdown": 0.5,
    "outro": 0.6
}

# Energie-Phasen-Multiplikatoren für DJ-Mixes (> 10 Minuten)
ENERGY_PHASE_MULTIPLIERS = {
    "low_energy": 0.5,
    "rising": 0.9,
    "high_energy": 1.5,
    "falling": 0.7,
    "plateau": 0.8
}


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

    def __init__(
        self,
        config: Optional[PacingConfig] = None,
        trigger_settings: Optional[dict] = None,
    ):
        """
        Initialize the pacing engine.

        Args:
            config: PacingConfig instance. If None, uses default settings.
            trigger_settings: Optional dict oder TriggerSettings-Objekt.
                              Wird von PacingService als Dict übergeben.
        """
        self.config = config or PacingConfig()
        self.audio_analysis: Optional[Dict] = None
        self.energy_curve: Optional[np.ndarray] = None
        self.timeline: List[CutPoint] = []

        # NV-kompatibel: trigger_settings als Dict oder TriggerSettings-Objekt
        if trigger_settings is not None:
            if isinstance(trigger_settings, dict):
                from .pacing_models import TriggerSettings as _TS
                ts = _TS()
                for k, v in trigger_settings.items():
                    if hasattr(ts, k):
                        setattr(ts, k, v)
                self._trigger_settings = ts
            else:
                self._trigger_settings = trigger_settings
        else:
            self._trigger_settings = None

        # Lazy-init ClipSelector (für generate_cut_list_with_clips)
        self._clip_selector = None

    @property
    def clip_selector(self):
        """Gibt den ClipSelector zurück (lazy-init)."""
        if self._clip_selector is None:
            from .clip_selector import ClipSelector
            self._clip_selector = ClipSelector()
        return self._clip_selector

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
                # Find nearest beat (nur innerhalb total_duration)
                valid_snap_beats = [b for b in beats if b <= total_duration]
                if not valid_snap_beats:
                    valid_snap_beats = beats
                nearest_beat = min(valid_snap_beats, key=lambda x: abs(x - proposed_end))
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

            # Move to next beat (sicher ohne ValueError)
            try:
                beat_idx = beats.index(end_time)
            except ValueError:
                beat_idx += 1

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

        if beat_data and all(len(b) >= 2 for b in beat_data[:10]):
            # BeatNet provides beat position (1, 2, 3, 4)
            downbeats = [b[0] for b in beat_data if len(b) >= 2 and b[1] == 1]
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

    # =========================================================================
    # NV-KOMPATIBLE API (von NVIDIA-Version portiert, AMD-angepasst)
    # =========================================================================

    @property
    def trigger_settings(self) -> "TriggerSettings":
        """
        NV-kompatibles trigger_settings Property.
        Gibt das interne TriggerSettings-Objekt zurück.
        Wird lazy initialisiert wenn noch nicht vorhanden.
        """
        if not hasattr(self, "_trigger_settings") or self._trigger_settings is None:
            from .pacing_models import TriggerSettings
            self._trigger_settings = TriggerSettings()
        return self._trigger_settings

    @trigger_settings.setter
    def trigger_settings(self, value: "TriggerSettings") -> None:
        self._trigger_settings = value

    def analyze_song_structure(self, audio_path: str) -> List["SongSection"]:
        """
        Analysiert die Song-Struktur (Intro, Verse, Chorus, Drop, etc.).

        NV-kompatible Methode: Delegiert an AudioAnalyzer wenn verfügbar,
        sonst energie-basierter Fallback (DJ-Mix-aware).

        Args:
            audio_path: Pfad zur Audio-Datei

        Returns:
            Liste von SongSection-Objekten
        """
        from .pacing_models import SongSection

        try:
            import librosa
            from ..audio.structure_analyzer import StructureAnalyzer
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            analyzer = StructureAnalyzer()
            structure_result = analyzer.analyze_song_structure(y, sr)

            sections = []
            segments = structure_result.get("segments", [])

            if not segments:
                logger.warning("Keine Segmente erkannt, nutze Fallback")
                return self._fallback_song_structure(audio_path)

            for seg in segments:
                label = seg.get("label", "verse")
                energy_level = STRUCTURE_INTENSITY_MULTIPLIERS.get(label, 0.8)
                sections.append(SongSection(
                    name=label,
                    start_time=seg.get("start_time", 0.0),
                    end_time=seg.get("end_time", 0.0),
                    energy_level=energy_level
                ))

            self._song_sections_nv = sections
            logger.info(
                f"Song-Struktur analysiert: {len(sections)} Sektionen "
                f"(Labels: {[s.name for s in sections]})"
            )
            return sections

        except Exception as e:
            logger.error(f"Song-Struktur-Analyse fehlgeschlagen: {e}")
            return self._fallback_song_structure(audio_path)

    def _fallback_song_structure(self, audio_path: str) -> List["SongSection"]:
        """
        Fallback-Struktur-Analyse basierend auf Dauer.
        DJ-Mix-aware: > 10 Minuten → Energie-Phasen statt Song-Labels.
        """
        from .pacing_models import SongSection

        try:
            import librosa
            duration = librosa.get_duration(path=audio_path)
        except Exception:
            duration = 180.0

        is_dj_mix = duration > 600  # > 10 Minuten

        if is_dj_mix:
            segment_length = 60.0
            phase_cycle = ["low_energy", "rising", "high_energy", "falling", "plateau"]
        else:
            segment_length = 30.0
            phase_cycle = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]

        num_segments = max(1, int(duration / segment_length))
        sections = []

        for i in range(num_segments):
            start = i * segment_length
            end = min((i + 1) * segment_length, duration)
            name = phase_cycle[i % len(phase_cycle)]

            if is_dj_mix:
                energy_level = ENERGY_PHASE_MULTIPLIERS.get(name, 0.8)
            else:
                energy_level = STRUCTURE_INTENSITY_MULTIPLIERS.get(name, 0.8)

            sections.append(SongSection(
                name=name,
                start_time=start,
                end_time=end,
                energy_level=energy_level
            ))

        self._song_sections_nv = sections
        return sections

    def generate_cut_list(
        self,
        audio_track: Any,
        expected_bpm: Optional[float] = None,
        min_cut_interval: float = 0.5,
        energy_sensitivity: float = 0.5,
        song_sections: Optional[List[Any]] = None,
    ) -> List["PacingCut"]:
        """
        NV-kompatible Methode: Generiert eine Schnittliste aus Audio-Triggern.

        Unterstützt AudioTrack-Objekte (mit .file_path) und Pfad-Strings.
        Bei verfügbaren Stems wird automatisch generate_cut_list_with_stems() genutzt.

        Args:
            audio_track: AudioTrack-Objekt oder Pfad-String
            expected_bpm: Erwartetes BPM (optional, wird automatisch erkannt)
            min_cut_interval: Minimaler Abstand zwischen Schnitten
            energy_sensitivity: 0.0 (nur Beats) bis 1.0 (alles/hektisch)
            song_sections: Optionale Liste von SongSection-Objekten für
                           strukturbewusstes Pacing (aus analyze_song_structure()).
                           Wenn gesetzt, skaliert _apply_structure_weights() die
                           Trigger-Stärken anhand der Sektions-Energie-Multiplikatoren.

        Returns:
            Liste von PacingCut-Objekten
        """
        from .pacing_models import PacingCut, TriggerSettings
        import json

        # TriggerSettings initialisieren falls noch nicht vorhanden
        if not hasattr(self, "_trigger_settings") or self._trigger_settings is None:
            self._trigger_settings = TriggerSettings()

        ts = self._trigger_settings

        # Originale Settings sichern (Sensitivity-Anpassung hat Seiteneffekte)
        original_dict = ts.to_dict()

        try:
            # --- Sensitivity-Anpassung ---
            if energy_sensitivity < 0.4:
                factor = energy_sensitivity / 0.4
                ts.kick_weight = 1.0
                ts.beat_weight = 1.0
                ts.snare_weight *= factor
                ts.onset_weight = 0.0
                ts.hihat_weight = 0.0
                logger.info(f"Low Sensitivity ({energy_sensitivity:.2f}): Fokus auf Beats/Kick")
            elif energy_sensitivity > 0.6:
                boost = 1.0 + (energy_sensitivity - 0.6) * 2.0
                ts.onset_weight = min(ts.onset_weight * boost, 1.5)
                ts.hihat_weight = min(ts.hihat_weight * boost, 1.0)
                logger.info(f"High Sensitivity ({energy_sensitivity:.2f}): Boost Onsets/HiHat (x{boost:.2f})")

            # --- Audio-Pfad extrahieren ---
            if hasattr(audio_track, "file_path"):
                audio_path = audio_track.file_path
                stems_json = getattr(audio_track, "stems_paths", None)
            else:
                audio_path = str(audio_track)
                stems_json = None

            # --- Smart Stems: Wenn verfügbar, bevorzugt nutzen ---
            if stems_json:
                try:
                    stems_dict = json.loads(stems_json)
                    if stems_dict and "drums" in stems_dict and ts.kick_weight > 0:
                        logger.info(f"Smart Stems aktiviert: {stems_dict.get('drums', '')}")
                        return self.generate_cut_list_with_stems(
                            audio_path=audio_path,
                            stems=stems_dict,
                            expected_bpm=expected_bpm,
                            min_cut_interval=min_cut_interval,
                        )
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Stems-JSON ungültig: {e}")

            # --- Standard-Generierung ---
            return self._generate_cut_list_from_audio(
                audio_path=audio_path,
                expected_bpm=expected_bpm,
                min_cut_interval=min_cut_interval,
                song_sections=song_sections,
            )

        finally:
            # Settings wiederherstellen
            for k, v in original_dict.items():
                setattr(ts, k, v)

    def _generate_cut_list_from_audio(
        self,
        audio_path: str,
        expected_bpm: Optional[float] = None,
        min_cut_interval: float = 0.5,
        song_sections: Optional[List[Any]] = None,
    ) -> List["PacingCut"]:
        """
        Interne Methode: Generiert Cuts aus Audio-Analyse.
        Nutzt SessionManager-Cache wenn verfügbar (RAM-Optimierung für DJ-Mixes).

        Args:
            song_sections: Wenn gesetzt, werden Trigger-Stärken strukturbewusst
                           skaliert (Chorus/Drop → stärker, Intro/Outro → schwächer).
        """
        from .pacing_models import PacingCut
        import librosa

        logger.info(f"Generiere Cut-Liste für: {audio_path}")

        # --- Cache-Check: SessionManager ---
        cached_audio_data = None
        onset_times = None
        energy_curve = None
        duration = 0.0

        try:
            from ..core.session_manager import get_session_manager
            mgr = get_session_manager()
            cached_audio_data = (
                mgr.get_audio_data() if hasattr(mgr, "get_audio_data") else
                getattr(mgr, "_audio_data", None)
            )
            if cached_audio_data:
                onset_times = cached_audio_data.get("onset_times", [])
                energy_curve = cached_audio_data.get("energy_curve", [])
                duration = cached_audio_data.get("duration", 0.0)
                logger.info(f"SessionManager-Cache: {len(onset_times)} Onsets, {duration:.0f}s")
        except Exception:
            pass

        # --- Beats holen (pre-cached > SessionManager-Cache > BeatDetector) ---
        beats: List[float] = []
        downbeats: List[float] = []

        # 1. Pre-cached Beats von PacingService (aus /audio/analyze Cache)
        if hasattr(self, "_pre_cached_beats") and self._pre_cached_beats:
            beats = self._pre_cached_beats
            logger.info(f"Pre-cached Beats: {len(beats)}")
        elif cached_audio_data and cached_audio_data.get("beat_times"):
            beats = cached_audio_data["beat_times"]
            downbeats = cached_audio_data.get("downbeat_times", [])
            logger.info(f"Cache-Beats: {len(beats)}")
        else:
            try:
                from ..audio.beat_detector import get_beat_detector
                import concurrent.futures
                beat_detector = get_beat_detector(version="auto")
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(beat_detector.scan, audio_path)
                    beats, downbeats = future.result(timeout=60)
            except Exception as e:
                logger.warning(f"BeatDetector Fehler: {e} — Librosa-Fallback")
                try:
                    y_q, sr_q = librosa.load(audio_path, sr=22050)
                    _, beat_frames = librosa.beat.beat_track(y=y_q, sr=sr_q)
                    beats = librosa.frames_to_time(beat_frames, sr=sr_q).tolist()
                    del y_q
                except Exception as e2:
                    logger.error(f"Librosa-Fallback gescheitert: {e2}")

        # --- Audio laden (nur wenn Cache unvollständig UND keine pre-cached Beats) ---
        y = None
        sr = 22050

        has_pre_cached = hasattr(self, "_pre_cached_beats") and self._pre_cached_beats

        # R17/HIGH-03: Prefer injected duration (from audio analysis) over beat estimation.
        # Beat estimation under-counts for tracks with silent outros.
        if has_pre_cached and duration <= 0:
            pre_dur = getattr(self, "_pre_cached_duration", 0.0)
            if pre_dur > 0:
                duration = pre_dur
                logger.info(f"Dauer aus gecachter Audio-Analyse: {duration:.1f}s")
            elif beats:
                duration = beats[-1] + 1.0
                logger.info(f"Dauer aus pre-cached Beats geschätzt: {duration:.1f}s")

        if not has_pre_cached and not (onset_times and energy_curve and duration > 0):
            if not hasattr(self, "_cached_audio_path"):
                self._cached_audio_path = None
                self._cached_y = None
                self._cached_sr = 22050

            if self._cached_audio_path != audio_path or self._cached_y is None:
                if self._cached_y is not None:
                    del self._cached_y
                    self._cached_y = None
                    import gc; gc.collect()
                logger.info(f"Lade Audio: {audio_path}")
                self._cached_y, self._cached_sr = librosa.load(audio_path, sr=22050)
                self._cached_audio_path = audio_path

            y = self._cached_y
            sr = self._cached_sr
            duration = librosa.get_duration(y=y, sr=sr) if duration <= 0 else duration

        # --- BPM schätzen ---
        if expected_bpm is None:
            if cached_audio_data and cached_audio_data.get("bpm"):
                bpm = float(cached_audio_data["bpm"])
            # G2/HIGH: Read injected _pre_cached_bpm from audio analysis
            elif hasattr(self, "_pre_cached_bpm") and self._pre_cached_bpm:
                bpm = float(self._pre_cached_bpm)
                logger.info(f"BPM aus gecachter Audio-Analyse: {bpm:.1f}")
            elif len(beats) >= 2:
                intervals = np.diff(beats)
                median_interval = float(np.median(intervals))
                bpm = 60.0 / median_interval if median_interval > 0 else 120.0
            else:
                bpm = 120.0
        else:
            bpm = expected_bpm

        logger.info(f"BPM: {bpm:.1f}, Dauer: {duration:.1f}s")

        # --- Triggers sammeln ---
        triggers: List[PacingCut] = []
        ts = self.trigger_settings
        downbeat_set = set(downbeats)

        if ts.beat_weight > 0:
            for t in beats:
                is_downbeat = t in downbeat_set
                strength = ts.beat_weight * (1.0 if is_downbeat else 0.7)
                triggers.append(PacingCut(
                    time=float(t),
                    trigger_type="downbeat" if is_downbeat else "beat",
                    strength=strength,
                ))

        if onset_times and energy_curve:
            triggers.extend(
                self._build_triggers_from_cache(onset_times, energy_curve, bpm)
            )
        elif y is not None:
            triggers.extend(self._extract_other_triggers(y, sr, bpm))

        # --- Struktur-Gewichtung anwenden (WARN-03 FIX) ---
        # Muss VOR sort/enforce_minimum_interval laufen, damit stärkere Chorus-Trigger
        # den min-interval-Filter überleben und schwache Intro/Outro-Trigger herausfallen.
        if song_sections:
            triggers = self._apply_structure_weights(triggers, song_sections)

        triggers.sort(key=lambda x: x.time)
        filtered = self._enforce_minimum_interval(triggers, min_cut_interval)

        # Song-Ende als finalen Trigger
        if filtered and filtered[-1].time < duration:
            filtered.append(PacingCut(time=duration, trigger_type="end", strength=1.0))

        # Clip-Längen erzwingen
        filtered = self._enforce_clip_lengths(
            cuts=filtered,
            min_length=ts.min_clip_length,
            max_length=ts.max_clip_length,
            audio_duration=duration,
            variation=ts.clip_length_variation,
        )

        logger.info(f"Cut-Liste: {len(filtered)} Schnitte")
        return filtered

    def _apply_structure_weights(
        self,
        triggers: List["PacingCut"],
        song_sections: List[Any],
    ) -> List["PacingCut"]:
        """
        Skaliert Trigger-Stärken anhand der Song-Sektions-Energie.

        Für jeden Trigger wird die zugehörige SongSection anhand der Zeit gesucht.
        Die Trigger-Stärke wird mit section.energy_level multipliziert:
            - Chorus / Drop  (energy_level ~1.2–1.5) → stärker → überleben min-interval
            - Intro / Outro  (energy_level ~0.5–0.6) → schwächer → fallen raus
            - Verse           (energy_level ~0.8)     → leicht gedämpft

        Args:
            triggers: Ungefilterte, unsortierte PacingCut-Liste
            song_sections: Liste von SongSection-Objekten (name, start_time,
                           end_time, energy_level)

        Returns:
            Gleiche Liste mit angepassten strength-Werten (clamp 0.0–1.0)
        """
        if not song_sections or not triggers:
            return triggers

        # Sektionen nach start_time sortieren (Invariante für Bereichs-Suche)
        sorted_sections = sorted(song_sections, key=lambda s: s.start_time)
        modified = 0

        for cut in triggers:
            # Passende Sektion suchen (Zeitpunkt liegt im Intervall [start, end))
            section = None
            for sec in sorted_sections:
                if sec.start_time <= cut.time < sec.end_time:
                    section = sec
                    break

            if section is not None:
                original_strength = cut.strength
                # R16/CRIT-01: Clamp to 1.0 — consistent with PacingCut.__post_init__.
                # energy_level is already in [0.0, 1.0], so the product can never
                # exceed 1.0. The old 1.5 cap was unreachable and contradicted the
                # model invariant.
                cut.strength = min(cut.strength * section.energy_level, 1.0)
                if abs(cut.strength - original_strength) > 0.01:
                    modified += 1

        logger.info(
            "_apply_structure_weights: %d/%d Trigger angepasst "
            "(Sektionen: %s)",
            modified,
            len(triggers),
            {s.name: round(s.energy_level, 2) for s in sorted_sections},
        )
        return triggers

    def generate_cut_list_with_stems(
        self,
        audio_path: str,
        stems: Dict[str, str],
        expected_bpm: Optional[float] = None,
        min_cut_interval: float = 0.5,
    ) -> List["PacingCut"]:
        """
        NV-kompatible Methode: Generiert Cut-Liste unter Verwendung von Demucs-Stems.

        Args:
            audio_path: Pfad zur Original-Audio-Datei
            stems: {"drums": "/path/drums.wav", "bass": "/path/bass.wav", ...}
            expected_bpm: Erwartetes BPM
            min_cut_interval: Minimaler Abstand zwischen Cuts

        Returns:
            Liste von PacingCut-Objekten
        """
        from .pacing_models import PacingCut

        logger.info(f"Generiere Cut-Liste mit Stems: {list(stems.keys())}")

        # Basis-Cuts aus Original-Audio (größerer min_interval für Basis)
        base_cuts = self._generate_cut_list_from_audio(
            audio_path=audio_path,
            expected_bpm=expected_bpm,
            min_cut_interval=min_cut_interval * 2,
        )

        # Stem-Trigger extrahieren
        stem_triggers: List[PacingCut] = []

        if "drums" in stems:
            drum_triggers = self._extract_drum_triggers_from_stem(stems["drums"])
            stem_triggers.extend(drum_triggers)

        if "bass" in stems:
            bass_triggers = self._extract_bass_triggers_from_stem(stems["bass"])
            for t in bass_triggers:
                t.strength *= 0.7
            stem_triggers.extend(bass_triggers)

        all_triggers = base_cuts + stem_triggers
        all_triggers.sort(key=lambda x: x.time)

        filtered = self._enforce_minimum_interval(all_triggers, min_cut_interval)

        ts = self.trigger_settings
        duration = filtered[-1].time if filtered else 0.0
        filtered = self._enforce_clip_lengths(
            cuts=filtered,
            min_length=ts.min_clip_length,
            max_length=ts.max_clip_length,
            audio_duration=duration,
            variation=ts.clip_length_variation,
        )

        logger.info(
            f"Cut-Liste mit Stems: {len(filtered)} Cuts "
            f"(Basis: {len(base_cuts)}, Stems: {len(stem_triggers)})"
        )
        return filtered

    def generate_cut_list_with_structure(
        self,
        audio_path: str,
        expected_bpm: Optional[float] = None,
        min_cut_interval: float = 0.5,
    ) -> List["PacingCut"]:
        """
        Generiert Cut-Liste MIT Song-Struktur-Bewusstsein.

        WARN-03 FIX: song_sections werden jetzt an generate_cut_list() übergeben
        und via _apply_structure_weights() angewendet. Trigger in Chorus/Drop-
        Sektionen bekommen höhere Stärke → überleben min-interval-Filter öfter
        → mehr Cuts in energiereichen Teilen. Intro/Bridge/Outro → weniger Cuts.

        NV-Kompatibilität: Wird von PacingService aufgerufen wenn
        use_motion_matching=True UND use_structure_awareness=True.

        Returns:
            Liste von PacingCut-Objekten mit strukturbewussten Stärken
        """
        song_sections = self.analyze_song_structure(audio_path)
        logger.info(
            "generate_cut_list_with_structure: %d Sektionen erkannt "
            "(Labels: %s) — übergebe an generate_cut_list",
            len(song_sections),
            [s.name for s in song_sections],
        )
        return self.generate_cut_list(
            audio_track=audio_path,
            expected_bpm=expected_bpm,
            min_cut_interval=min_cut_interval,
            song_sections=song_sections,
        )

    def generate_cut_list_with_clips(
        self,
        audio_path: str,
        available_clips: List[Dict],
        expected_bpm: Optional[float] = None,
        min_cut_interval: float = 0.5,
    ) -> List[tuple]:
        """
        Generiert Cut-Liste und weist jedem Cut einen Clip zu.

        NV-Kompatibilität: Wird von PacingService aufgerufen wenn
        use_motion_matching=True UND use_structure_awareness=False.

        Returns:
            Liste von (PacingCut, clip_dict) Tupeln.
            clip_dict enthält mindestens 'id' und 'file_path'.
        """
        # WARN-02 FIX: Guard gegen leere Clip-Liste (verhindert ZeroDivisionError
        # im Round-Robin-Fallback wenn clip_idx % len(available_clips) aufgerufen wird)
        if not available_clips:
            logger.warning("generate_cut_list_with_clips: available_clips ist leer — gibt [] zurück")
            return []

        # Cuts generieren (kein clip_cache befüllen — BUG-02 FIX:
        # Fake-Embeddings mit np.random.random() verletzt "No Dummies"-Regel und
        # macht FAISS-Semantik-Suche wirkungslos. ClipSelector nutzt stattdessen
        # seinen internen motion/round-robin-Modus auf available_clips direkt.)
        cs = self.clip_selector

        pacing_cuts = self.generate_cut_list(
            audio_track=audio_path,
            expected_bpm=expected_bpm,
            min_cut_interval=min_cut_interval,
        )

        # Jeden Cut mit einem Clip pairen
        result = []
        clip_idx = 0
        for cut in pacing_cuts:
            # BUG-01 FIX: 'energy' war falscher Keyword — korrekt ist 'trigger_strength'
            selected = cs.select_clip(
                available_clips=available_clips,
                trigger_strength=cut.strength,
                trigger_type=cut.trigger_type,
            )
            if selected and selected.clip_path:
                clip_dict = {
                    "id": selected.clip_id or f"clip_{clip_idx}",
                    "file_path": selected.clip_path,
                }
            else:
                # Fallback: Round-Robin (available_clips ist hier garantiert nicht leer)
                clip = available_clips[clip_idx % len(available_clips)]
                clip_dict = {
                    "id": clip.get("id", f"clip_{clip_idx}"),
                    "file_path": clip.get("file_path", ""),
                }
            result.append((cut, clip_dict))
            clip_idx += 1

        logger.info(
            f"generate_cut_list_with_clips: {len(result)} (Cut, Clip)-Paare"
        )
        return result

    def enable_motion_matching(self, enabled: bool = True) -> None:
        """NV-Kompatibilität: Aktiviert/Deaktiviert Motion-Matching."""
        self._use_motion_matching = enabled
        logger.info(f"Motion-Matching: {'aktiviert' if enabled else 'deaktiviert'}")

    # =========================================================================
    # INTERNE HELPER (NV-portiert)
    # =========================================================================

    def _extract_drum_triggers_from_stem(self, stem_path: str) -> List["PacingCut"]:
        """Extrahiert Kick/Snare/HiHat aus Drums-Stem (Librosa-basiert)."""
        from .pacing_models import PacingCut
        import librosa

        triggers: List[PacingCut] = []
        ts = self.trigger_settings
        hop_length = 512

        try:
            y, sr = librosa.load(stem_path, sr=22050)

            if ts.kick_weight > 0:
                env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length,
                                                   aggregate=np.median, fmax=150)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr,
                                                    hop_length=hop_length, backtrack=True)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="kick",
                                              strength=ts.kick_weight * 0.95))

            if ts.snare_weight > 0:
                env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length,
                                                   fmin=200, fmax=400)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr,
                                                    hop_length=hop_length, backtrack=True)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="snare",
                                              strength=ts.snare_weight * 0.9))

            if ts.hihat_weight > 0:
                env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length, fmin=5000)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop_length)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="hihat",
                                              strength=ts.hihat_weight * 0.5))

            logger.info(f"Drum-Stem: {len(triggers)} Trigger")
        except Exception as e:
            logger.error(f"Drum-Stem-Analyse fehlgeschlagen: {e}")

        return sorted(triggers, key=lambda t: t.time)

    def _extract_bass_triggers_from_stem(self, stem_path: str) -> List["PacingCut"]:
        """Extrahiert Bass-Drops aus Bass-Stem."""
        from .pacing_models import PacingCut
        import librosa

        triggers: List[PacingCut] = []
        hop_length = 512

        try:
            y, sr = librosa.load(stem_path, sr=22050)
            frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length, units="frames")
            times = librosa.frames_to_time(frames, sr=sr, hop_length=hop_length)
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            rms_norm = rms / (np.max(rms) + 1e-10)

            for frame, t in zip(frames, times):
                strength = float(rms_norm[min(frame, len(rms_norm) - 1)])
                triggers.append(PacingCut(time=float(t), trigger_type="bass",
                                          strength=strength * 0.7))

            logger.info(f"Bass-Stem: {len(triggers)} Trigger")
        except Exception as e:
            logger.error(f"Bass-Stem-Analyse fehlgeschlagen: {e}")

        return triggers

    def _build_triggers_from_cache(
        self,
        onset_times: List[float],
        energy_curve: List[float],
        bpm: float,
    ) -> List["PacingCut"]:
        """
        Baut Trigger aus gecachten Audio-Analyse-Daten (ohne Audio neu zu laden).
        RAM-Optimierung für DJ-Mixes (z.B. 105 Minuten = 6335s).
        """
        from .pacing_models import PacingCut

        triggers: List[PacingCut] = []
        ts = self.trigger_settings

        # 1. Onsets
        if ts.onset_weight > 0 and onset_times:
            for t in onset_times:
                triggers.append(PacingCut(
                    time=float(t),
                    trigger_type="onset",
                    strength=min(ts.onset_weight * 0.5, 1.0),
                ))

        # 2. Energie-Spitzen
        if ts.energy_weight > 0 and energy_curve:
            try:
                energy_array = np.array(energy_curve)
                energy_norm = energy_array / (np.max(energy_array) + 1e-10)
                peaks = np.where(energy_norm > ts.energy_threshold)[0]

                duration_estimate = 180.0
                try:
                    from ..core.session_manager import get_session_manager
                    mgr = get_session_manager()
                    ad = mgr.get_audio_data() if hasattr(mgr, "get_audio_data") else None
                    if ad and "duration" in ad:
                        duration_estimate = ad["duration"]
                except Exception:
                    duration_estimate = max(180.0, len(energy_curve) / 10.0)

                time_per_sample = duration_estimate / len(energy_curve)
                peak_groups = np.split(peaks, np.where(np.diff(peaks) > 5)[0] + 1) if len(peaks) > 0 else []

                for group in peak_groups:
                    if len(group) > 0:
                        best_idx = group[np.argmax(energy_norm[group])]
                        t = best_idx * time_per_sample
                        triggers.append(PacingCut(
                            time=float(t),
                            trigger_type="energy",
                            strength=float(energy_norm[best_idx]) * ts.energy_weight,
                        ))
            except Exception as e:
                logger.warning(f"Energy-Trigger aus Cache fehlgeschlagen: {e}")

        return triggers

    def _extract_other_triggers(
        self,
        y: np.ndarray,
        sr: int,
        bpm: float,
    ) -> List["PacingCut"]:
        """Extrahiert Onsets, Drums und Energy-Spitzen aus Audio-Array."""
        from .pacing_models import PacingCut
        import librosa

        triggers: List[PacingCut] = []
        ts = self.trigger_settings
        hop_length = 512

        if ts.onset_weight > 0:
            frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames")
            for t in librosa.frames_to_time(frames, sr=sr):
                triggers.append(PacingCut(time=float(t), trigger_type="onset",
                                          strength=ts.onset_weight * 0.5))

        try:
            if ts.kick_weight > 0:
                env = librosa.onset.onset_strength(y=librosa.effects.preemphasis(y), sr=sr,
                                                   hop_length=hop_length, aggregate=np.median,
                                                   fmax=150, n_mels=64)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop_length)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="kick",
                                              strength=ts.kick_weight * 0.9))

            if ts.snare_weight > 0:
                env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length,
                                                   fmin=200, fmax=400, n_mels=64)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop_length)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="snare",
                                              strength=ts.snare_weight * 0.85))

            if ts.hihat_weight > 0:
                env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length,
                                                   fmin=5000, n_mels=64)
                frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop_length)
                for t in librosa.frames_to_time(frames, sr=sr, hop_length=hop_length):
                    triggers.append(PacingCut(time=float(t), trigger_type="hihat",
                                              strength=ts.hihat_weight * 0.4))
        except Exception as e:
            logger.warning(f"Drum-Detection fehlgeschlagen: {e}")

        if ts.energy_weight > 0:
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            rms_norm = rms / (np.max(rms) + 1e-10)
            peaks = np.where(rms_norm > ts.energy_threshold)[0]
            if len(peaks) > 0:
                groups = np.split(peaks, np.where(np.diff(peaks) > 5)[0] + 1)
                for group in groups:
                    if len(group) > 0:
                        best = group[np.argmax(rms_norm[group])]
                        t = librosa.frames_to_time(best, sr=sr, hop_length=hop_length)
                        triggers.append(PacingCut(time=float(t), trigger_type="energy",
                                                  strength=float(rms_norm[best]) * ts.energy_weight))

        return triggers

    def _enforce_minimum_interval(
        self,
        triggers: List["PacingCut"],
        min_interval: float,
    ) -> List["PacingCut"]:
        """Entfernt Trigger die zu dicht beieinander liegen (behält stärkere)."""
        if not triggers:
            return []

        filtered = [triggers[0]]
        last_time = triggers[0].time

        for trigger in triggers[1:]:
            if trigger.time - last_time >= min_interval:
                filtered.append(trigger)
                last_time = trigger.time
            elif trigger.strength > filtered[-1].strength:
                filtered[-1] = trigger
                last_time = trigger.time  # CRITICAL FIX: last_time aktualisieren

        return filtered

    def _enforce_clip_lengths(
        self,
        cuts: List["PacingCut"],
        min_length: float,
        max_length: float,
        audio_duration: float,
        variation: float = 0.0,
    ) -> List["PacingCut"]:
        """
        Stellt sicher, dass Clip-Längen innerhalb der Grenzen liegen.
        Fügt Auto-Split-Cuts ein wenn ein Clip zu lang wäre.
        """
        from .pacing_models import PacingCut
        import random

        if not cuts:
            return cuts

        # Min-Länge: Nutze enforce_minimum_interval
        filtered = self._enforce_minimum_interval(cuts, min_length)

        result: List[PacingCut] = []
        for i, cut in enumerate(filtered):
            result.append(cut)

            next_time = filtered[i + 1].time if i < len(filtered) - 1 else audio_duration
            clip_duration = next_time - cut.time

            current_max = max_length
            if variation > 0:
                var_factor = random.uniform(-variation * 0.5, variation * 0.5)
                current_max = max_length * (1.0 + var_factor)

            if clip_duration > current_max:
                num_splits = max(1, int(clip_duration / current_max))
                split_duration = clip_duration / (num_splits + 1)

                for j in range(num_splits):
                    jitter = split_duration * random.uniform(-variation * 0.2, variation * 0.2) if variation > 0 else 0.0
                    split_time = cut.time + (split_duration * (j + 1)) + jitter
                    prev_time = result[-1].time

                    if (split_time > prev_time + min_length) and (split_time < audio_duration - 0.1):
                        result.append(PacingCut(
                            time=split_time,
                            trigger_type="auto_split",
                            strength=0.5,
                            segment_type=cut.segment_type,
                        ))

        return sorted(result, key=lambda c: c.time)

    def get_trigger_statistics(self, cuts: List["PacingCut"]) -> Dict[str, Any]:
        """Gibt Statistiken über die generierten Cuts zurück."""
        if not cuts:
            return {
                "total_cuts": 0,
                "trigger_types": {},
                "avg_interval": 0.0,
                "min_interval": 0.0,
                "max_interval": 0.0,
                "avg_strength": 0.0,
            }

        trigger_counts: Dict[str, int] = {}
        for cut in cuts:
            trigger_counts[cut.trigger_type] = trigger_counts.get(cut.trigger_type, 0) + 1

        intervals = [cuts[i + 1].time - cuts[i].time for i in range(len(cuts) - 1)]

        return {
            "total_cuts": len(cuts),
            "trigger_types": trigger_counts,
            "avg_interval": float(np.mean(intervals)) if intervals else 0.0,
            "min_interval": float(np.min(intervals)) if intervals else 0.0,
            "max_interval": float(np.max(intervals)) if intervals else 0.0,
            "avg_strength": float(np.mean([c.strength for c in cuts])),
        }
