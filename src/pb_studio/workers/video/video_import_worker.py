"""
Video Import Worker for PB Studio AMD.

Extracts video metadata via FFprobe without GPU usage.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

from ..base_worker import BaseWorker
from ...models.video import VideoMetadata
from ...video.encoder_utils import _get_ffprobe_path

logger = logging.getLogger(__name__)


class VideoImportWorker(BaseWorker):
    """
    Worker for importing video files and extracting metadata.

    Uses FFprobe to extract:
    - Duration, FPS, resolution
    - Codec information
    - Audio track presence
    - Bitrate

    VRAM Budget: 0 MB (CPU only, uses FFprobe)

    Example:
        worker = VideoImportWorker("/path/to/video.mp4", project_id="proj_123")
        worker.signals.result.connect(on_metadata_ready)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, file_path: str, project_id: str):
        """
        Initialize the video import worker.

        Args:
            file_path: Path to the video file
            project_id: Project ID for associating the import
        """
        super().__init__("VideoImportWorker", vram_budget_mb=0)

        self.file_path = file_path
        self.project_id = project_id

    def _execute(self) -> dict[str, Any]:
        """
        Execute video import and metadata extraction.

        Returns:
            Dictionary containing:
            - metadata: VideoMetadata object
            - file_path: Original file path
            - project_id: Associated project ID
        """
        self.emit_status(f"Importing video: {Path(self.file_path).name}")
        self.emit_progress(10, "Validating file...")

        # Validate file exists
        video_path = Path(self.file_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {self.file_path}")

        if not video_path.is_file():
            raise ValueError(f"Path is not a file: {self.file_path}")

        self._check_cancelled()
        self.emit_progress(30, "Extracting metadata via FFprobe...")

        # Extract metadata using FFprobe
        metadata = self._extract_metadata_ffprobe()

        self._check_cancelled()
        self.emit_progress(100, "Import complete")

        return {
            "metadata": metadata,
            "file_path": self.file_path,
            "project_id": self.project_id,
        }

    def _extract_metadata_ffprobe(self) -> VideoMetadata:
        """
        Extract video metadata using FFprobe.

        Returns:
            VideoMetadata with extracted information
        """
        ffprobe_cmd = [
            _get_ffprobe_path(),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(self.file_path)
        ]

        try:
            result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.warning(f"FFprobe error: {result.stderr}")
                return self._fallback_metadata()

            probe_data = json.loads(result.stdout)
            return self._parse_ffprobe_output(probe_data)

        except subprocess.TimeoutExpired:
            logger.warning("FFprobe timeout - using fallback metadata")
            return self._fallback_metadata()

        except FileNotFoundError:
            logger.warning("FFprobe not found - using fallback metadata")
            return self._fallback_metadata()

        except json.JSONDecodeError as e:
            logger.warning(f"FFprobe JSON parse error: {e}")
            return self._fallback_metadata()

    def _parse_ffprobe_output(self, probe_data: dict) -> VideoMetadata:
        """
        Parse FFprobe JSON output into VideoMetadata.

        Args:
            probe_data: Parsed JSON from FFprobe

        Returns:
            VideoMetadata object
        """
        # Find video stream
        video_stream = None
        has_audio = False

        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                has_audio = True

        if video_stream is None:
            logger.warning("No video stream found in file")
            return self._fallback_metadata()

        # Extract FPS (handle various formats)
        fps = self._parse_fps(video_stream)

        # Extract duration
        duration = self._parse_duration(video_stream, probe_data)

        # Extract bitrate
        bitrate = self._parse_bitrate(video_stream, probe_data)

        return VideoMetadata(
            duration=duration,
            fps=fps,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            codec=video_stream.get("codec_name", "unknown"),
            has_audio=has_audio,
            bitrate=bitrate,
        )

    def _parse_fps(self, video_stream: dict) -> float:
        """Parse FPS from various FFprobe formats."""
        # Try r_frame_rate first (most common)
        r_frame_rate = video_stream.get("r_frame_rate", "")
        if r_frame_rate and "/" in r_frame_rate:
            try:
                num, den = r_frame_rate.split("/")
                if int(den) != 0:
                    return float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass

        # Try avg_frame_rate
        avg_frame_rate = video_stream.get("avg_frame_rate", "")
        if avg_frame_rate and "/" in avg_frame_rate:
            try:
                num, den = avg_frame_rate.split("/")
                if int(den) != 0:
                    return float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass

        # Fallback
        return 30.0

    def _parse_duration(self, video_stream: dict, probe_data: dict) -> float:
        """Parse duration from stream or format data."""
        # Try stream duration first
        if "duration" in video_stream:
            try:
                return float(video_stream["duration"])
            except (ValueError, TypeError):
                pass

        # Try format duration
        format_info = probe_data.get("format", {})
        if "duration" in format_info:
            try:
                return float(format_info["duration"])
            except (ValueError, TypeError):
                pass

        # Fallback
        return 0.0

    def _parse_bitrate(self, video_stream: dict, probe_data: dict) -> Optional[int]:
        """Parse bitrate from stream or format data."""
        # Try stream bitrate
        if "bit_rate" in video_stream:
            try:
                return int(video_stream["bit_rate"])
            except (ValueError, TypeError):
                pass

        # Try format bitrate
        format_info = probe_data.get("format", {})
        if "bit_rate" in format_info:
            try:
                return int(format_info["bit_rate"])
            except (ValueError, TypeError):
                pass

        return None

    def _fallback_metadata(self) -> VideoMetadata:
        """
        Create fallback metadata when FFprobe fails.

        Uses OpenCV as backup to get basic info.
        """
        cap = None
        try:
            import cv2

            cap = cv2.VideoCapture(self.file_path)
            if not cap.isOpened():
                raise RuntimeError("Could not open video with OpenCV")

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0.0

            return VideoMetadata(
                duration=duration,
                fps=fps,
                width=width,
                height=height,
                codec="unknown",
                has_audio=False,  # Cannot determine with OpenCV
                bitrate=None,
            )

        except Exception as e:
            logger.error(f"Fallback metadata extraction failed: {e}")
            # Return minimal valid metadata
            return VideoMetadata(
                duration=0.0,
                fps=30.0,
                width=0,
                height=0,
                codec="unknown",
                has_audio=False,
                bitrate=None,
            )

        finally:
            if cap is not None:
                cap.release()
