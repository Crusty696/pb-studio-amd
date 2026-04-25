"""
Render Worker for PB Studio AMD

Renders individual video segments using FFmpeg with AMD AMF hardware acceleration.
"""

import logging
import random
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from ..base_worker import BaseWorker
from ...models.timeline import CutPlan, CutPoint, RenderSegment
from ...video.encoder_utils import (
    get_encoder_config,
    build_ffmpeg_encode_args,
    _get_ffmpeg_path,
    _get_ffprobe_path,
)

logger = logging.getLogger(__name__)


class RenderWorker(BaseWorker):
    """
    Worker that renders individual video segments.

    Uses FFmpeg with AMD AMF hardware acceleration to extract
    and encode video segments based on the cut plan.

    VRAM Budget: 500 MB (AMF encoder)

    Input:
        - cut_plan: CutPlan with cut points
        - source_videos: List of source video paths
        - temp_dir: Directory for temporary segment files

    Output:
        - List[RenderSegment] with rendered segment info

    Example:
        worker = RenderWorker(
            cut_plan=cut_plan,
            source_videos=["video1.mp4", "video2.mp4"],
            temp_dir="/tmp/render"
        )
        worker.signals.result.connect(handle_segments)
        thread_pool.start(worker)
    """

    VRAM_BUDGET_MB = 500  # AMF encoder VRAM usage

    def __init__(
        self,
        cut_plan: CutPlan,
        source_videos: list[str],
        temp_dir: str,
        codec: str = "h264",
        quality: str = "balanced",
        output_fps: float = 30.0,
        output_resolution: Optional[tuple[int, int]] = None,
    ):
        """
        Initialize the render worker.

        Args:
            cut_plan: CutPlan with all cut points to render
            source_videos: List of source video file paths
            temp_dir: Directory to store temporary segment files
            codec: Video codec ("h264", "hevc", or "av1")
            quality: Encoding quality ("speed", "balanced", "quality")
            output_fps: Output frame rate
            output_resolution: Optional (width, height) for output
        """
        super().__init__("RenderWorker", vram_budget_mb=self.VRAM_BUDGET_MB)

        self.cut_plan = cut_plan
        self.source_videos = source_videos
        self.temp_dir = temp_dir
        self.codec = codec
        self.quality = quality
        self.output_fps = output_fps
        self.output_resolution = output_resolution

        # Cache fuer Video-Dauern (vermeidet wiederholte FFprobe-Aufrufe)
        self._duration_cache: dict[str, float] = {}

        # Validate inputs
        if not source_videos:
            raise ValueError("At least one source video is required")

    def _execute(self) -> list[RenderSegment]:
        """
        Render all segments from the cut plan.

        Returns:
            List of RenderSegment objects with render results
        """
        self.emit_status("Initializing renderer...")
        self.emit_progress(0, "Preparing render environment")

        # Ensure temp directory exists
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)

        # Get encoder configuration
        encoder_config = get_encoder_config(
            codec=self.codec,
            quality=self.quality,
        )

        logger.info(f"Using encoder: {encoder_config.description}")
        self.emit_status(f"Encoder: {encoder_config.description}")

        segments: list[RenderSegment] = []
        total_cuts = len(self.cut_plan.cuts)

        if total_cuts == 0:
            self.emit_progress(100, "No segments to render")
            return segments

        for i, cut in enumerate(self.cut_plan.cuts):
            self._check_cancelled()

            progress = int((i / total_cuts) * 100)
            self.emit_progress(progress, f"Rendering segment {i + 1}/{total_cuts}")

            # Get source video for this cut (mit Validierung)
            source_idx = cut.source_video_index
            if source_idx < 0 or source_idx >= len(self.source_videos):
                logger.warning(
                    f"Invalid source_video_index {source_idx}, "
                    f"clamping to valid range [0, {len(self.source_videos)-1}]"
                )
                source_idx = max(0, min(source_idx, len(self.source_videos) - 1))
            source_video = self.source_videos[source_idx]

            # Generate output path
            output_path = str(Path(self.temp_dir) / f"segment_{i:04d}.mp4")

            # Render segment
            segment = self._render_segment(
                segment_index=i,
                cut=cut,
                source_video=source_video,
                output_path=output_path,
                encoder_config=encoder_config,
            )

            segments.append(segment)

            if segment.is_failed:
                logger.error(f"Segment {i} failed: {segment.error_message}")

        # Calculate success stats
        completed = sum(1 for s in segments if s.is_completed)
        failed = sum(1 for s in segments if s.is_failed)

        self.emit_progress(100, f"Rendered {completed}/{total_cuts} segments")
        logger.info(f"RenderWorker completed: {completed} OK, {failed} failed")

        return segments

    def _render_segment(
        self,
        segment_index: int,
        cut: CutPoint,
        source_video: str,
        output_path: str,
        encoder_config: Any,
    ) -> RenderSegment:
        """
        Render a single video segment.

        Args:
            segment_index: Index of segment
            cut: CutPoint with timing info
            source_video: Path to source video
            output_path: Path for output segment
            encoder_config: EncoderConfig for FFmpeg

        Returns:
            RenderSegment with render status
        """
        # Quell-Video-Dauer ermitteln und Seek-Position berechnen
        clip_dur = self._get_video_duration(source_video)
        if clip_dur <= 0:
            clip_dur = cut.duration + 1.0  # Fallback

        # Segment-Dauer an Clip-Laenge anpassen
        seg_dur = min(cut.duration, clip_dur - 0.05)
        if seg_dur < 0.3:
            seg_dur = min(1.0, clip_dur)

        # Seek-Position INNERHALB des Quell-Clips (nicht Timeline-Position!)
        max_seek = max(0, clip_dur - seg_dur - 0.05)
        
        # BUG-095 FIX: Deterministic randomness using segment_index as seed
        # Provides variety but ensures same output for same input
        rnd = random.Random(segment_index + 42)
        seek_pos = rnd.uniform(0, max_seek) if max_seek > 0 else 0

        segment = RenderSegment(
            segment_index=segment_index,
            source_video=source_video,
            start_time=seek_pos,
            duration=seg_dur,
            output_path=output_path,
            transition=cut.transition,
            render_status="rendering",
        )

        try:
            # Build FFmpeg command
            cmd = self._build_ffmpeg_command(
                source_video=source_video,
                start_time=seek_pos,
                duration=seg_dur,
                output_path=output_path,
                encoder_config=encoder_config,
            )

            logger.debug(f"FFmpeg command: {' '.join(cmd)}")

            # Execute FFmpeg
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per segment
            )
            render_time = time.time() - start_time

            if result.returncode == 0:
                segment.render_status = "completed"
                logger.debug(
                    f"Segment {segment_index} rendered in {render_time:.1f}s"
                )
            else:
                segment.render_status = "failed"
                segment.error_message = result.stderr[:500]
                logger.error(
                    f"FFmpeg failed for segment {segment_index}: "
                    f"{result.stderr[:200]}"
                )

        except subprocess.TimeoutExpired:
            segment.render_status = "failed"
            segment.error_message = "Render timeout (300s exceeded)"
            logger.error(f"Segment {segment_index} timed out")

        except Exception as e:
            segment.render_status = "failed"
            segment.error_message = str(e)
            logger.error(f"Segment {segment_index} error: {e}")

        return segment

    def _build_ffmpeg_command(
        self,
        source_video: str,
        start_time: float,
        duration: float,
        output_path: str,
        encoder_config: Any,
    ) -> list[str]:
        """
        Build FFmpeg command for segment extraction.

        Args:
            source_video: Input video path
            start_time: Start time in seconds
            duration: Duration in seconds
            output_path: Output file path
            encoder_config: EncoderConfig object

        Returns:
            List of command arguments
        """
        cmd = [_get_ffmpeg_path(), "-y"]  # Overwrite output

        # Input seeking (fast seek before input)
        cmd.extend(["-ss", f"{start_time:.3f}"])

        # Input file
        cmd.extend(["-i", source_video])

        # Duration
        cmd.extend(["-t", f"{duration:.3f}"])

        # Video filters (if resolution specified)
        if self.output_resolution:
            width, height = self.output_resolution
            cmd.extend([
                "-vf",
                f"scale={width}:{height}:flags=lanczos,fps={self.output_fps}"
            ])
        else:
            cmd.extend(["-vf", f"fps={self.output_fps}"])

        # Encoder settings
        encode_args = build_ffmpeg_encode_args(encoder_config)
        cmd.extend(encode_args)

        # Kein Audio in Segmenten (Audio kommt spaeter im Concat-Schritt)
        cmd.append("-an")

        # Output format settings
        cmd.extend(["-movflags", "+faststart"])

        # Output path
        cmd.append(output_path)

        return cmd

    def _get_video_duration(self, video_path: str) -> float:
        """Ermittelt die Dauer eines Videos (mit Cache)."""
        if video_path in self._duration_cache:
            return self._duration_cache[video_path]
        try:
            result = subprocess.run(
                [_get_ffprobe_path(), "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", video_path],
                capture_output=True, text=True, timeout=10
            )
            dur = float(result.stdout.strip())
            self._duration_cache[video_path] = dur
            return dur
        except Exception:
            return 0.0
