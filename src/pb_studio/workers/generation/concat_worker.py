"""
Concat Worker for PB Studio AMD

Concatenates rendered video segments into the final output video.
Uses FFmpeg with AMD AMF hardware acceleration for re-encoding.
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from ..base_worker import BaseWorker
from ...models.timeline import RenderSegment, RenderResult
from ...video.encoder_utils import (
    get_encoder_config,
    build_ffmpeg_encode_args,
)

logger = logging.getLogger(__name__)


class ConcatWorker(BaseWorker):
    """
    Worker that concatenates video segments into final output.

    Uses FFmpeg concat demuxer for fast concatenation when possible,
    or re-encodes with AMD AMF when transitions are needed.

    VRAM Budget: 500 MB (AMF encoder)

    Input:
        - segments: List of RenderSegment objects
        - master_audio: Optional path to master audio track
        - output_path: Final output video path

    Output:
        - final_output_path (str)

    Example:
        worker = ConcatWorker(
            segments=render_segments,
            master_audio="master.wav",
            output_path="final_video.mp4"
        )
        worker.signals.result.connect(handle_final)
        thread_pool.start(worker)
    """

    VRAM_BUDGET_MB = 500  # AMF encoder VRAM usage

    def __init__(
        self,
        segments: list[RenderSegment],
        output_path: str,
        master_audio: Optional[str] = None,
        codec: str = "h264",
        quality: str = "quality",
        use_transitions: bool = True,
    ):
        """
        Initialize the concat worker.

        Args:
            segments: List of RenderSegment objects to concatenate
            output_path: Path for final output video
            master_audio: Optional path to master audio file
            codec: Video codec ("h264", "hevc", "av1")
            quality: Encoding quality ("speed", "balanced", "quality")
            use_transitions: Whether to apply transitions between segments
        """
        super().__init__("ConcatWorker", vram_budget_mb=self.VRAM_BUDGET_MB)

        self.segments = segments
        self.output_path = output_path
        self.master_audio = master_audio
        self.codec = codec
        self.quality = quality
        self.use_transitions = use_transitions

    def _execute(self) -> str:
        """
        Concatenate all segments into final video.

        Returns:
            Path to final output video
        """
        self.emit_status("Preparing concatenation...")
        self.emit_progress(0, "Validating segments")

        # Filter to completed segments only
        valid_segments = [s for s in self.segments if s.is_completed]

        if not valid_segments:
            raise ValueError("No valid segments to concatenate")

        logger.info(
            f"Concatenating {len(valid_segments)} segments "
            f"(of {len(self.segments)} total)"
        )

        self._check_cancelled()
        self.emit_progress(10, "Creating concat list")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        # Create concat list file
        concat_list_path = self._create_concat_list(valid_segments)

        self._check_cancelled()
        self.emit_progress(20, "Starting concatenation")

        try:
            start_time = time.time()

            if self.master_audio:
                # Concatenate video and mix with master audio
                self._concat_with_audio(concat_list_path)
            else:
                # Simple video concatenation
                self._concat_video_only(concat_list_path)

            render_time = time.time() - start_time

            self.emit_progress(100, f"Concatenation complete ({render_time:.1f}s)")
            logger.info(
                f"ConcatWorker completed: {self.output_path} "
                f"in {render_time:.1f}s"
            )

            return self.output_path

        finally:
            # Clean up concat list
            if os.path.exists(concat_list_path):
                os.remove(concat_list_path)

    def _create_concat_list(self, segments: list[RenderSegment]) -> str:
        """
        Create FFmpeg concat demuxer list file.

        Args:
            segments: List of segments to include

        Returns:
            Path to concat list file
        """
        list_path = os.path.join(
            os.path.dirname(self.output_path) or ".",
            "_concat_list.txt"
        )

        with open(list_path, "w", encoding="utf-8") as f:
            for segment in sorted(segments, key=lambda s: s.segment_index):
                # FFmpeg concat requires escaped paths
                escaped_path = segment.output_path.replace("\\", "/")
                escaped_path = escaped_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        return list_path

    def _concat_video_only(self, concat_list_path: str) -> None:
        """
        Concatenate video segments without audio replacement.

        Uses concat demuxer for fast stream copying when possible.

        Args:
            concat_list_path: Path to concat list file
        """
        # Try fast concat first (stream copy)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",  # Stream copy (fast)
            "-movflags", "+faststart",
            self.output_path,
        ]

        logger.debug(f"Concat command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        if result.returncode != 0:
            logger.warning(
                f"Fast concat failed, trying re-encode: {result.stderr[:200]}"
            )
            self._concat_with_reencode(concat_list_path)

    def _concat_with_audio(self, concat_list_path: str) -> None:
        """
        Concatenate video and replace audio with master track.

        Args:
            concat_list_path: Path to concat list file
        """
        encoder_config = get_encoder_config(
            codec=self.codec,
            quality=self.quality,
        )

        encode_args = build_ffmpeg_encode_args(encoder_config)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-i", self.master_audio,
            "-map", "0:v:0",  # Video from concat
            "-map", "1:a:0",  # Audio from master
        ]

        # Add encoder arguments
        cmd.extend(encode_args)

        # Audio encoding
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        # Shortest duration (in case audio is longer)
        cmd.extend(["-shortest"])

        # Output settings
        cmd.extend(["-movflags", "+faststart"])
        cmd.append(self.output_path)

        logger.debug(f"Concat with audio command: {' '.join(cmd)}")

        self.emit_progress(50, "Re-encoding with master audio...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Concatenation failed: {result.stderr[:500]}"
            )

    def _concat_with_reencode(self, concat_list_path: str) -> None:
        """
        Concatenate with re-encoding (fallback for incompatible streams).

        Args:
            concat_list_path: Path to concat list file
        """
        encoder_config = get_encoder_config(
            codec=self.codec,
            quality=self.quality,
        )

        encode_args = build_ffmpeg_encode_args(encoder_config)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
        ]

        # Add encoder arguments
        cmd.extend(encode_args)

        # Audio encoding
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        # Output settings
        cmd.extend(["-movflags", "+faststart"])
        cmd.append(self.output_path)

        logger.debug(f"Re-encode concat command: {' '.join(cmd)}")

        self.emit_progress(50, "Re-encoding segments...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Re-encode concatenation failed: {result.stderr[:500]}"
            )
