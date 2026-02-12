"""
Pacing Worker for PB Studio AMD

Generates cut plans from audio analysis using the AdvancedPacingEngine.
No GPU usage - pure CPU computation.
"""

import logging
from typing import Any, Optional

import numpy as np

from ..base_worker import BaseWorker
from ...models.audio import AudioAnalysisResult
from ...models.timeline import CutPoint, CutPlan, TransitionType
from ...pacing.advanced_pacing_engine import (
    AdvancedPacingEngine,
    PacingConfig,
    SyncMode,
    TransitionType as PacingTransitionType,
)

logger = logging.getLogger(__name__)


class PacingWorker(BaseWorker):
    """
    Worker that generates cut plans from audio analysis.

    Uses the AdvancedPacingEngine to create beat-synchronized
    cut points based on audio energy and rhythm.

    VRAM Budget: 0 MB (CPU only)

    Input:
        - audio_analysis: AudioAnalysisResult from audio analyzer
        - pacing_config: Dict with pacing settings

    Output:
        - CutPlan with all cut points

    Example:
        worker = PacingWorker(
            audio_analysis=analysis_result,
            pacing_config={
                "level": 3,
                "min_dur": 2.0,
                "max_dur": 8.0,
                "precision": 8
            }
        )
        worker.signals.result.connect(handle_cut_plan)
        thread_pool.start(worker)
    """

    VRAM_BUDGET_MB = 0  # No GPU usage

    def __init__(
        self,
        audio_analysis: AudioAnalysisResult,
        pacing_config: Optional[dict[str, Any]] = None,
        total_duration: Optional[float] = None,
    ):
        """
        Initialize the pacing worker.

        Args:
            audio_analysis: AudioAnalysisResult with beat times, energy curve, etc.
            pacing_config: Optional dict with pacing parameters:
                - level: Pacing level 1-5 (slow to fast), default 3
                - min_dur: Minimum clip duration in seconds, default 2.0
                - max_dur: Maximum clip duration in seconds, default 8.0
                - precision: Beat snapping strength 1-10, default 8
                - energy_react: Energy reactivity 0-10, default 5
                - chaos: Randomness/variation 0-10, default 2
                - sync_mode: "beat_sync", "energy_sync", "emotional", "hybrid"
            total_duration: Override total duration (uses analysis duration if None)
        """
        super().__init__("PacingWorker", vram_budget_mb=self.VRAM_BUDGET_MB)

        self.audio_analysis = audio_analysis
        self.pacing_config = pacing_config or {}
        self.total_duration = total_duration

    def _execute(self) -> CutPlan:
        """
        Generate cut plan from audio analysis.

        Returns:
            CutPlan with all computed cut points
        """
        self.emit_status("Initializing pacing engine...")
        self.emit_progress(0, "Preparing audio data")

        # Build PacingConfig from input parameters
        config = self._build_config()

        # Create pacing engine
        engine = AdvancedPacingEngine(config)

        self._check_cancelled()
        self.emit_progress(10, "Analyzing audio structure")

        # Prepare audio data for engine
        analysis_dict = self._prepare_analysis_dict()
        rms, times = self._prepare_energy_data()

        # Analyze audio structure
        engine.analyze_audio_structure(analysis_dict, rms, times)

        self._check_cancelled()
        self.emit_progress(30, "Planning cuts")

        # Determine total duration
        duration = self.total_duration
        if duration is None:
            if self.audio_analysis.beat_times:
                duration = max(self.audio_analysis.beat_times) + 2.0
            else:
                duration = 60.0  # Default fallback

        # Generate cut timeline
        cuts = engine.plan_cuts(duration)

        self._check_cancelled()
        self.emit_progress(80, "Building cut plan")

        # Convert engine CutPoints to timeline CutPoints
        timeline_cuts = self._convert_cuts(cuts)

        # Get statistics
        stats = engine.get_statistics()

        # Build CutPlan
        cut_plan = CutPlan(
            cuts=timeline_cuts,
            total_duration=duration,
            bpm=self.audio_analysis.bpm,
            sync_mode=config.sync_mode.value,
            statistics=stats,
        )

        self.emit_progress(100, f"Generated {len(timeline_cuts)} cuts")
        logger.info(
            f"PacingWorker completed: {len(timeline_cuts)} cuts, "
            f"avg duration: {cut_plan.avg_cut_duration:.2f}s, "
            f"beat alignment: {cut_plan.beat_aligned_ratio:.1%}"
        )

        return cut_plan

    def _build_config(self) -> PacingConfig:
        """Build PacingConfig from input parameters."""
        level = self.pacing_config.get("level", 3)
        min_dur = self.pacing_config.get("min_dur", 2.0)
        max_dur = self.pacing_config.get("max_dur", 8.0)
        precision = self.pacing_config.get("precision", 8)
        energy_react = self.pacing_config.get("energy_react", 5)
        chaos = self.pacing_config.get("chaos", 2)

        # Parse sync mode
        sync_mode_str = self.pacing_config.get("sync_mode", "hybrid")
        sync_mode_map = {
            "beat_sync": SyncMode.BEAT_SYNC,
            "energy_sync": SyncMode.ENERGY_SYNC,
            "emotional": SyncMode.EMOTIONAL_SYNC,
            "hybrid": SyncMode.HYBRID,
        }
        sync_mode = sync_mode_map.get(sync_mode_str, SyncMode.HYBRID)

        return PacingConfig(
            pacing=level,
            precision=precision,
            energy_react=energy_react,
            chaos=chaos,
            min_clip_length=min_dur,
            max_clip_length=max_dur,
            sync_mode=sync_mode,
            allow_transitions=True,
            prefer_downbeats=True,
        )

    def _prepare_analysis_dict(self) -> dict[str, Any]:
        """Convert AudioAnalysisResult to engine-compatible dict."""
        # Build beat_data list: [(time, beat_position), ...]
        beat_data = []
        beat_times = self.audio_analysis.beat_times
        downbeat_set = set(self.audio_analysis.downbeat_times)

        for i, time in enumerate(beat_times):
            # Beat position: 1 for downbeat, 2-4 for other beats
            is_downbeat = any(abs(time - dt) < 0.01 for dt in downbeat_set)
            position = 1 if is_downbeat else ((i % 4) + 1)
            beat_data.append((time, position))

        return {
            "bpm": self.audio_analysis.bpm,
            "beat_data": beat_data,
            "downbeats": self.audio_analysis.downbeat_times,
            "confidence": self.audio_analysis.confidence,
        }

    def _prepare_energy_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Prepare energy curve and time arrays."""
        energy = self.audio_analysis.energy_curve

        if not energy:
            # No energy data - create dummy
            return np.array([0.5]), np.array([0.0])

        rms = np.array(energy, dtype=np.float32)

        # Generate time values (assume regular sampling)
        if self.audio_analysis.beat_times:
            total_time = max(self.audio_analysis.beat_times) + 2.0
        else:
            total_time = 60.0

        times = np.linspace(0, total_time, len(rms))

        return rms, times

    def _convert_cuts(self, engine_cuts: list) -> list[CutPoint]:
        """Convert engine CutPoints to timeline CutPoints."""
        timeline_cuts = []

        # Map pacing transition types to timeline transition types
        transition_map = {
            PacingTransitionType.HARD_CUT: TransitionType.HARD_CUT,
            PacingTransitionType.FADE: TransitionType.FADE,
            PacingTransitionType.CROSSFADE: TransitionType.CROSSFADE,
            PacingTransitionType.ZOOM: TransitionType.ZOOM,
            PacingTransitionType.SLIDE: TransitionType.SLIDE,
        }

        for i, cut in enumerate(engine_cuts):
            timeline_cut = CutPoint(
                time=cut.time,
                duration=cut.duration,
                energy=cut.energy,
                beat_aligned=cut.beat_aligned,
                beat_strength=cut.beat_strength,
                transition=transition_map.get(cut.transition, TransitionType.HARD_CUT),
                confidence=cut.confidence,
                source_video_index=0,  # Will be assigned by clip selector
                metadata=cut.metadata,
            )
            timeline_cuts.append(timeline_cut)

        return timeline_cuts
