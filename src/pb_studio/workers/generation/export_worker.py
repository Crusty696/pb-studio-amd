"""
Export Worker for PB Studio AMD

Orchestrates the complete video export pipeline:
Pacing -> Render -> Concat -> Final Output

This is the main entry point for video generation.
"""

import logging
import os
import shutil
import tempfile
import time
from typing import Any, Optional

from PyQt6.QtCore import QThreadPool

from ..base_worker import BaseWorker
from ...models.audio import AudioAnalysisResult
from ...models.timeline import CutPlan, RenderSegment, RenderResult
from .pacing_worker import PacingWorker
from .render_worker import RenderWorker
from .concat_worker import ConcatWorker

logger = logging.getLogger(__name__)


class ExportWorker(BaseWorker):
    """
    Master worker that orchestrates the complete export pipeline.

    Coordinates PacingWorker -> RenderWorker -> ConcatWorker
    to produce the final video output.

    VRAM Budget: 500 MB (shared with child workers)

    Input:
        config dict containing:
        - audio_analysis: AudioAnalysisResult
        - source_videos: List of video paths
        - output_path: Final output path
        - master_audio: Optional audio track path
        - pacing_config: Pacing settings
        - codec: Video codec
        - quality: Encoding quality

    Output:
        RenderResult with complete export information

    Example:
        worker = ExportWorker(config={
            "audio_analysis": analysis,
            "source_videos": ["video1.mp4"],
            "output_path": "output.mp4",
            "pacing_config": {"level": 3},
        })
        worker.signals.result.connect(handle_result)
        thread_pool.start(worker)
    """

    VRAM_BUDGET_MB = 500  # Shared with child workers

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the export worker.

        Args:
            config: Configuration dict with the following keys:
                Required:
                - audio_analysis: AudioAnalysisResult object
                - source_videos: List of source video paths
                - output_path: Path for final output video

                Optional:
                - master_audio: Path to master audio track
                - pacing_config: Dict with pacing settings
                - codec: Video codec (default: "h264")
                - quality: Encoding quality (default: "quality")
                - output_fps: Output frame rate (default: 30.0)
                - output_resolution: Tuple (width, height)
                - cleanup_temp: Delete temp files (default: True)
        """
        super().__init__("ExportWorker", vram_budget_mb=self.VRAM_BUDGET_MB)

        # Validate required config
        required = ["audio_analysis", "source_videos", "output_path"]
        for key in required:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

        self.config = config

        # Extract config values
        self.audio_analysis: AudioAnalysisResult = config["audio_analysis"]
        self.source_videos: list[str] = config["source_videos"]
        self.output_path: str = config["output_path"]
        self.master_audio: Optional[str] = config.get("master_audio")
        self.pacing_config: dict = config.get("pacing_config", {})
        self.codec: str = config.get("codec", "h264")
        self.quality: str = config.get("quality", "quality")
        self.output_fps: float = config.get("output_fps", 30.0)
        self.output_resolution: Optional[tuple[int, int]] = config.get(
            "output_resolution"
        )
        self.cleanup_temp: bool = config.get("cleanup_temp", True)

        # State tracking
        self._temp_dir: Optional[str] = None
        self._cut_plan: Optional[CutPlan] = None
        self._segments: list[RenderSegment] = []

    def _execute(self) -> RenderResult:
        """
        Execute the complete export pipeline.

        Returns:
            RenderResult with all export information
        """
        start_time = time.time()

        self.emit_status("Starting export pipeline...")
        self.emit_progress(0, "Initializing")

        # Create temp directory
        self._temp_dir = tempfile.mkdtemp(prefix="pb_studio_export_")
        logger.info(f"Using temp directory: {self._temp_dir}")

        try:
            # Phase 1: Generate cut plan (0-20%)
            self._check_cancelled()
            self._cut_plan = self._run_pacing_phase()

            # Phase 2: Render segments (20-80%)
            self._check_cancelled()
            self._segments = self._run_render_phase()

            # Phase 3: Concatenate (80-100%)
            self._check_cancelled()
            final_path = self._run_concat_phase()

            # Build result
            render_time = time.time() - start_time

            result = RenderResult(
                segments=self._segments,
                final_output_path=final_path,
                total_duration=self._cut_plan.total_duration,
                render_time_seconds=render_time,
                encoder_used=self._get_encoder_name(),
                is_hardware_accelerated=self._is_hardware_accelerated(),
            )

            self.emit_progress(100, f"Export complete ({render_time:.1f}s)")
            logger.info(
                f"ExportWorker completed: {final_path} "
                f"({result.completed_segments} segments, {render_time:.1f}s)"
            )

            return result

        finally:
            # Cleanup temp directory
            if self.cleanup_temp and self._temp_dir:
                self._cleanup_temp_dir()

    def _run_pacing_phase(self) -> CutPlan:
        """
        Run the pacing phase to generate cut plan.

        Returns:
            CutPlan with all cut points
        """
        self.emit_status("Phase 1/3: Generating cut plan...")
        self.emit_progress(5, "Analyzing audio structure")

        # Create and run pacing worker synchronously
        pacing_worker = PacingWorker(
            audio_analysis=self.audio_analysis,
            pacing_config=self.pacing_config,
        )

        # Run worker's execute directly (we're already in a thread)
        cut_plan = pacing_worker._execute()

        self.emit_progress(20, f"Cut plan: {len(cut_plan)} cuts")
        logger.info(f"Pacing phase complete: {len(cut_plan)} cuts")

        return cut_plan

    def _run_render_phase(self) -> list[RenderSegment]:
        """
        Run the render phase to create video segments.

        Returns:
            List of RenderSegment objects
        """
        self.emit_status("Phase 2/3: Rendering segments...")
        self.emit_progress(25, "Preparing renderer")

        # Assign source videos to cuts (round-robin if multiple)
        self._assign_source_videos()

        # Create and run render worker
        render_worker = RenderWorker(
            cut_plan=self._cut_plan,
            source_videos=self.source_videos,
            temp_dir=self._temp_dir,
            codec=self.codec,
            quality=self.quality,
            output_fps=self.output_fps,
            output_resolution=self.output_resolution,
        )

        # Forward progress from render worker
        def on_render_progress(data):
            # Map 0-100 render progress to 25-75 overall progress
            render_pct = data.get("percent", 0)
            overall_pct = 25 + int(render_pct * 0.5)
            self.emit_progress(overall_pct, data.get("message", ""))

        render_worker.signals.progress.connect(on_render_progress)

        # Run render phase
        segments = render_worker._execute()

        self.emit_progress(75, f"Rendered {len(segments)} segments")
        logger.info(
            f"Render phase complete: "
            f"{sum(1 for s in segments if s.is_completed)} of {len(segments)} OK"
        )

        return segments

    def _run_concat_phase(self) -> str:
        """
        Run the concatenation phase to create final video.

        Returns:
            Path to final output video
        """
        self.emit_status("Phase 3/3: Concatenating...")
        self.emit_progress(80, "Preparing final video")

        # Create and run concat worker
        concat_worker = ConcatWorker(
            segments=self._segments,
            output_path=self.output_path,
            master_audio=self.master_audio,
            codec=self.codec,
            quality=self.quality,
        )

        # Forward progress
        def on_concat_progress(data):
            # Map 0-100 concat progress to 80-100 overall
            concat_pct = data.get("percent", 0)
            overall_pct = 80 + int(concat_pct * 0.2)
            self.emit_progress(overall_pct, data.get("message", ""))

        concat_worker.signals.progress.connect(on_concat_progress)

        # Run concat phase
        final_path = concat_worker._execute()

        logger.info(f"Concat phase complete: {final_path}")

        return final_path

    def _assign_source_videos(self) -> None:
        """
        Assign source videos to cut points.

        Uses round-robin assignment if multiple videos available.
        """
        if not self._cut_plan or not self.source_videos:
            return

        num_videos = len(self.source_videos)

        for i, cut in enumerate(self._cut_plan.cuts):
            self._check_cancelled()
            # Round-robin assignment
            cut.source_video_index = i % num_videos

    def _cleanup_temp_dir(self) -> None:
        """Clean up temporary directory and files."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug(f"Cleaned up temp dir: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")

    def _get_encoder_name(self) -> str:
        """Get the encoder name used for this export."""
        from ...video.encoder_utils import get_encoder_config

        config = get_encoder_config(codec=self.codec, quality=self.quality)
        return config.encoder

    def _is_hardware_accelerated(self) -> bool:
        """Check if hardware acceleration was used."""
        from ...video.encoder_utils import check_amf_available

        return check_amf_available()

    def get_cut_plan(self) -> Optional[CutPlan]:
        """Get the generated cut plan (available after pacing phase)."""
        return self._cut_plan

    def get_segments(self) -> list[RenderSegment]:
        """Get rendered segments (available after render phase)."""
        return self._segments
