"""
Video Scene Detection Worker for PB Studio AMD.

Detects scene boundaries in video files using PySceneDetect.
"""

import logging
from pathlib import Path
from typing import Any

from ..base_worker import BaseWorker
from ...models.video import SceneInfo
from ...video.scene_detect import SceneDetector

logger = logging.getLogger(__name__)


class VideoSceneWorker(BaseWorker):
    """
    Worker for detecting scene boundaries in video files.

    Uses the existing SceneDetector module which wraps PySceneDetect.
    Scenes are detected based on content changes (ContentDetector algorithm).

    VRAM Budget: 0 MB (CPU only, uses PySceneDetect)

    Example:
        worker = VideoSceneWorker("/path/to/video.mp4", threshold=8.0)
        worker.signals.result.connect(on_scenes_detected)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, file_path: str, threshold: float = 8.0):
        """
        Initialize the scene detection worker.

        Args:
            file_path: Path to the video file
            threshold: Scene detection threshold (lower = more sensitive)
                      Default 8.0 works well for most content.
                      Range: 1.0 (very sensitive) to 50.0 (only hard cuts)
        """
        super().__init__("VideoSceneWorker", vram_budget_mb=0)

        self.file_path = file_path
        self.threshold = threshold

    def _execute(self) -> dict[str, Any]:
        """
        Execute scene detection.

        Returns:
            Dictionary containing:
            - scenes: List[SceneInfo] with detected scenes
            - file_path: Original file path
            - threshold: Threshold used for detection
        """
        self.emit_status(f"Detecting scenes: {Path(self.file_path).name}")
        self.emit_progress(10, "Initializing scene detector...")

        # Validate file exists
        video_path = Path(self.file_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {self.file_path}")

        self._check_cancelled()
        self.emit_progress(20, f"Analyzing video (threshold={self.threshold})...")

        # Create detector and run detection
        detector = SceneDetector(threshold=self.threshold)
        raw_scenes = detector.detect_scenes(self.file_path)

        self._check_cancelled()
        self.emit_progress(80, "Processing scene data...")

        # Convert raw tuples to SceneInfo objects
        scenes = self._convert_to_scene_info(raw_scenes)

        self.emit_progress(100, f"Detected {len(scenes)} scenes")

        return {
            "scenes": scenes,
            "file_path": self.file_path,
            "threshold": self.threshold,
        }

    def _convert_to_scene_info(
        self,
        raw_scenes: list[tuple[float, float]]
    ) -> list[SceneInfo]:
        """
        Convert raw scene tuples to SceneInfo objects.

        Args:
            raw_scenes: List of (start_sec, end_sec) tuples from SceneDetector

        Returns:
            List of SceneInfo objects with computed properties
        """
        scenes = []

        for i, (start, end) in enumerate(raw_scenes):
            scene = SceneInfo(
                start=start,
                end=end,
                duration=end - start,
                thumbnail_path=None,  # Can be generated later
                scene_index=i,
            )
            scenes.append(scene)

        # If no scenes detected, create a single scene for entire video
        if not scenes:
            logger.info("No scene cuts detected - treating video as single scene")
            # We need video duration; try to get it
            duration = self._get_video_duration()
            if duration > 0:
                scenes.append(SceneInfo(
                    start=0.0,
                    end=duration,
                    duration=duration,
                    thumbnail_path=None,
                    scene_index=0,
                ))

        return scenes

    def _get_video_duration(self) -> float:
        """
        Get video duration using OpenCV as fallback.

        Returns:
            Video duration in seconds, or 0.0 on error
        """
        try:
            import cv2

            cap = cv2.VideoCapture(self.file_path)
            if not cap.isOpened():
                return 0.0

            try:
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                return frame_count / fps if fps > 0 else 0.0
            finally:
                cap.release()

        except Exception as e:
            logger.warning(f"Could not get video duration: {e}")
            return 0.0
