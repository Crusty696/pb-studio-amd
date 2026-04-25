"""
Video Motion Analysis Worker for PB Studio AMD.

Analyzes motion in video scenes using RAFT optical flow.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from ..base_worker import BaseWorker
from ...models.video import SceneInfo, MotionData
from ...video.raft import MotionAnalyzer, FarnebackFlowAnalyzer, create_motion_analyzer

logger = logging.getLogger(__name__)


class VideoMotionWorker(BaseWorker):
    """
    Worker for analyzing motion in video scenes using optical flow.

    Uses the existing MotionAnalyzer (RAFT via ONNX DirectML) or
    falls back to FarnebackFlowAnalyzer (CPU OpenCV) if RAFT unavailable.

    VRAM Budget: 1500 MB (RAFT model on GPU)

    For each scene, computes:
    - Average motion intensity
    - Maximum motion intensity
    - Motion curve over time

    Example:
        scenes = [SceneInfo(...), ...]
        worker = VideoMotionWorker("/path/to/video.mp4", scenes)
        worker.signals.result.connect(on_motion_analyzed)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        file_path: str,
        scenes: list[SceneInfo],
        sample_rate: int = 5,
        prefer_gpu: bool = True
    ):
        """
        Initialize the motion analysis worker.

        Args:
            file_path: Path to the video file
            scenes: List of SceneInfo objects to analyze
            sample_rate: Analyze every N-th frame (higher = faster but less accurate)
            prefer_gpu: If True, try RAFT on GPU; if False, use CPU Farneback
        """
        super().__init__("VideoMotionWorker", vram_budget_mb=1500)

        self.file_path = file_path
        self.scenes = scenes
        self.sample_rate = max(1, sample_rate)
        self.prefer_gpu = prefer_gpu

        self._analyzer: Optional[MotionAnalyzer | FarnebackFlowAnalyzer] = None

    def _execute(self) -> dict[str, Any]:
        """
        Execute motion analysis for all scenes.

        Returns:
            Dictionary containing:
            - motion_data: List[MotionData] for each scene
            - file_path: Original file path
            - analyzer_type: 'RAFT' or 'Farneback'
        """
        # C1/HIGH: Reserve VRAM before starting
        from ...core.system_monitor import get_system_monitor
        from ...core.vram_arbiter import VRAMArbiter
        
        monitor = get_system_monitor()
        arbiter = VRAMArbiter(monitor)
        
        # Model needs approx 1.5GB
        model_id = f"RAFT_{Path(self.file_path).stem}"
        vram_reserved = arbiter.reserve(1500, model_id=model_id)

        self.emit_status(f"Analyzing motion: {Path(self.file_path).name}")
        self.emit_progress(5, "Initializing motion analyzer...")

        # Validate file exists
        video_path = Path(self.file_path)
        if not video_path.exists():
            if vram_reserved: arbiter.release(model_id=model_id)
            raise FileNotFoundError(f"Video file not found: {self.file_path}")

        if not self.scenes:
            if vram_reserved: arbiter.release(model_id=model_id)
            logger.warning("No scenes provided for motion analysis")
            return {
                "motion_data": [],
                "file_path": self.file_path,
                "analyzer_type": "None",
            }

        self._check_cancelled()

        # Initialize motion analyzer
        self._analyzer = create_motion_analyzer(prefer_gpu=self.prefer_gpu)
        analyzer_type = "RAFT" if isinstance(self._analyzer, MotionAnalyzer) else "Farneback"
        
        if vram_reserved and analyzer_type == "RAFT":
            arbiter.commit(model_id)
        elif vram_reserved:
            # Not using GPU RAFT, release reservation
            arbiter.release(model_id=model_id)

        self.emit_progress(10, f"Using {analyzer_type} optical flow...")

        # Open video capture
        cap = cv2.VideoCapture(self.file_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {self.file_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            motion_data_list = []

            # Process each scene
            total_scenes = len(self.scenes)
            for i, scene in enumerate(self.scenes):
                self._check_cancelled()

                progress = 10 + int((i / total_scenes) * 85)
                self.emit_progress(
                    progress,
                    f"Analyzing scene {i + 1}/{total_scenes}..."
                )

                motion_data = self._analyze_scene(cap, scene, fps)
                motion_data_list.append(motion_data)

            self.emit_progress(100, "Motion analysis complete")

            return {
                "motion_data": motion_data_list,
                "file_path": self.file_path,
                "analyzer_type": analyzer_type,
            }

        finally:
            cap.release()
            # Unload RAFT model to free VRAM
            if isinstance(self._analyzer, MotionAnalyzer):
                self._analyzer.unload()
                if vram_reserved: arbiter.release(model_id=model_id)

    def _analyze_scene(
        self,
        cap: cv2.VideoCapture,
        scene: SceneInfo,
        fps: float
    ) -> MotionData:
        """
        Analyze motion within a single scene.

        Args:
            cap: OpenCV VideoCapture object
            scene: SceneInfo defining the scene boundaries
            fps: Video frames per second

        Returns:
            MotionData with computed motion metrics
        """
        start_frame = int(scene.start * fps)
        end_frame = int(scene.end * fps)

        # Ensure we have at least 2 frames to compare
        if end_frame - start_frame < 2:
            return MotionData(
                scene_index=scene.scene_index,
                avg_motion=0.0,
                max_motion=0.0,
                motion_curve=[0.0],
                timestamps=[scene.start],
            )

        # Seek to start of scene
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        motion_values = []
        timestamps = []
        prev_frame = None

        frame_idx = start_frame
        while frame_idx < end_frame:
            self._check_cancelled()

            ret, frame = cap.read()
            if not ret:
                break

            # Only process every N-th frame
            if (frame_idx - start_frame) % self.sample_rate == 0:
                if prev_frame is not None:
                    # Calculate motion between frames
                    magnitude = self._analyzer.get_motion_magnitude(prev_frame, frame)
                    motion_values.append(magnitude)
                    timestamps.append(frame_idx / fps)

                prev_frame = frame.copy()

            frame_idx += 1

        # Compute aggregate metrics
        if motion_values:
            avg_motion = float(np.mean(motion_values))
            max_motion = float(np.max(motion_values))
            # Normalize motion values to 0-1 range
            motion_curve = self._normalize_motion(motion_values)
        else:
            avg_motion = 0.0
            max_motion = 0.0
            motion_curve = [0.0]
            timestamps = [scene.start]

        return MotionData(
            scene_index=scene.scene_index,
            avg_motion=avg_motion,
            max_motion=max_motion,
            motion_curve=motion_curve,
            timestamps=timestamps,
        )

    def _normalize_motion(self, values: list[float]) -> list[float]:
        """
        Normalize motion values to 0-1 range.

        Uses a sensible maximum threshold to avoid outliers dominating.

        Args:
            values: Raw motion magnitude values

        Returns:
            Normalized values in 0-1 range
        """
        if not values:
            return [0.0]

        # Use 95th percentile as max to avoid outliers
        max_val = float(np.percentile(values, 95))
        if max_val <= 0:
            max_val = 1.0

        # Normalize and clamp to 0-1
        normalized = [min(1.0, v / max_val) for v in values]
        return normalized
