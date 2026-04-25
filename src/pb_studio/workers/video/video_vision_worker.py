"""
Video Vision Analysis Worker for PB Studio AMD.

Generates captions for video scenes using Moondream vision-language model.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image

from ..base_worker import BaseWorker
from ...models.video import SceneInfo

logger = logging.getLogger(__name__)


class VideoVisionWorker(BaseWorker):
    """
    Worker for generating captions and visual analysis of video scenes.

    Uses MoondreamAnalyzer (ONNX DirectML) or MoondreamPyTorch (CPU fallback)
    to analyze key frames from each scene.

    VRAM Budget: 2500 MB (Moondream model on GPU)

    For each scene, generates:
    - Scene caption/description
    - Optional: mood, objects, action analysis

    Example:
        scenes = [SceneInfo(...), ...]
        worker = VideoVisionWorker("/path/to/video.mp4", scenes)
        worker.signals.result.connect(on_captions_ready)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(
        self,
        file_path: str,
        scenes: list[SceneInfo],
        detailed_analysis: bool = False,
        custom_prompt: Optional[str] = None
    ):
        """
        Initialize the vision analysis worker.

        Args:
            file_path: Path to the video file
            scenes: List of SceneInfo objects to analyze
            detailed_analysis: If True, run multiple prompts per scene
                             (description, mood, objects, action)
            custom_prompt: Optional custom prompt to use instead of default
        """
        super().__init__("VideoVisionWorker", vram_budget_mb=2500)

        self.file_path = file_path
        self.scenes = scenes
        self.detailed_analysis = detailed_analysis
        self.custom_prompt = custom_prompt

        self._analyzer = None

    def _execute(self) -> dict[str, Any]:
        """
        Execute vision analysis for all scenes.

        Returns:
            Dictionary containing:
            - captions: Dict mapping scene_index to caption data
            - file_path: Original file path
            - model_type: 'ONNX' or 'PyTorch'
        """
        # C1/HIGH: Reserve VRAM before starting
        from ...core.system_monitor import get_system_monitor
        from ...core.vram_arbiter import VRAMArbiter
        
        monitor = get_system_monitor()
        arbiter = VRAMArbiter(monitor)
        
        # Model needs approx 2.5GB
        model_id = f"Moondream_{Path(self.file_path).stem}"
        vram_reserved = arbiter.reserve(2500, model_id=model_id)

        self.emit_status(f"Analyzing video content: {Path(self.file_path).name}")
        self.emit_progress(5, "Initializing vision model...")

        # Validate file exists
        video_path = Path(self.file_path)
        if not video_path.exists():
            if vram_reserved: arbiter.release(model_id=model_id)
            raise FileNotFoundError(f"Video file not found: {self.file_path}")

        if not self.scenes:
            if vram_reserved: arbiter.release(model_id=model_id)
            logger.warning("No scenes provided for vision analysis")
            return {
                "captions": {},
                "file_path": self.file_path,
                "model_type": "None",
            }

        self._check_cancelled()

        # Initialize vision model (try ONNX first, then PyTorch)
        model_type = self._init_vision_model()
        
        if vram_reserved:
            arbiter.commit(model_id)

        self.emit_progress(15, f"Using Moondream ({model_type})...")

        cap = None
        try:
            # Open video capture
            cap = cv2.VideoCapture(self.file_path)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open video: {self.file_path}")

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            captions = {}

            # Process each scene
            total_scenes = len(self.scenes)
            for i, scene in enumerate(self.scenes):
                self._check_cancelled()

                progress = 15 + int((i / total_scenes) * 80)
                self.emit_progress(
                    progress,
                    f"Analyzing scene {i + 1}/{total_scenes}..."
                )

                # Extract key frame from scene midpoint
                frame = self._extract_key_frame(cap, scene, fps)
                if frame is None:
                    logger.warning(f"Could not extract frame for scene {scene.scene_index}")
                    captions[scene.scene_index] = {"description": "[Frame extraction failed]"}
                    continue

                # Generate caption(s) for the frame
                scene_captions = self._analyze_frame(frame)
                captions[scene.scene_index] = scene_captions

            self.emit_progress(100, "Vision analysis complete")

            return {
                "captions": captions,
                "file_path": self.file_path,
                "model_type": model_type,
            }

        finally:
            if cap is not None:
                cap.release()
            self._unload_model()

    def _init_vision_model(self) -> str:
        """
        Initialize the vision model, with fallback options.

        Returns:
            Model type string ('ONNX' or 'PyTorch')
        """
        # Try MoondreamAnalyzer first; it may internally use ONNX, hybrid mode, or PyTorch fallback.
        try:
            from ...video.moondream import MoondreamAnalyzer

            self._analyzer = MoondreamAnalyzer(lazy_load=False)
            if self._analyzer.is_ready:
                provider = getattr(self._analyzer, "active_provider", "Unknown")
                if "PyTorch" in provider:
                    logger.info("Using Moondream PyTorch fallback via analyzer")
                    return "PyTorch"
                if getattr(self._analyzer, "_hybrid_mode", False):
                    logger.info("Using Moondream hybrid model")
                    return "Hybrid"
                logger.info("Using Moondream ONNX model")
                return "ONNX"

        except Exception as e:
            logger.warning(f"Moondream analyzer initialization failed: {e}")

        # Fallback to PyTorch
        try:
            from ...ai.moondream_pytorch import MoondreamPyTorch

            self._analyzer = MoondreamPyTorch()
            if self._analyzer.load():
                logger.info("Using Moondream PyTorch model (CPU)")
                return "PyTorch"

        except Exception as e:
            logger.error(f"PyTorch Moondream initialization failed: {e}")

        raise RuntimeError("No vision model available (neither ONNX nor PyTorch)")

    def _unload_model(self):
        """Unload the vision model to free resources."""
        if self._analyzer is not None:
            try:
                self._analyzer.unload()
            except Exception as e:
                logger.warning(f"Error unloading model: {e}")

    def _extract_key_frame(
        self,
        cap: cv2.VideoCapture,
        scene: SceneInfo,
        fps: float
    ) -> Optional[np.ndarray]:
        """
        Extract a representative key frame from a scene.

        Uses the midpoint of the scene.

        Args:
            cap: OpenCV VideoCapture object
            scene: SceneInfo defining the scene
            fps: Video frames per second

        Returns:
            BGR numpy array or None on error
        """
        # Use scene midpoint as key frame
        midpoint_sec = scene.midpoint
        frame_number = int(midpoint_sec * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        if not ret:
            # Try start of scene as fallback
            start_frame = int(scene.start * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            ret, frame = cap.read()

        return frame if ret else None

    def _analyze_frame(self, frame: np.ndarray) -> dict[str, str]:
        """
        Analyze a video frame with the vision model.

        Args:
            frame: BGR numpy array from OpenCV

        Returns:
            Dictionary with caption data
        """
        # Convert BGR to PIL Image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        result = {}

        # Determine which method to use based on analyzer type
        if hasattr(self._analyzer, 'generate_caption'):
            # ONNX MoondreamAnalyzer
            result = self._analyze_with_onnx(pil_image)
        elif hasattr(self._analyzer, 'caption'):
            # PyTorch MoondreamPyTorch
            result = self._analyze_with_pytorch(pil_image)
        else:
            result = {"description": "[Unknown analyzer type]"}

        return result

    def _analyze_with_onnx(self, image: Image.Image) -> dict[str, str]:
        """
        Analyze image using ONNX MoondreamAnalyzer.

        Args:
            image: PIL Image

        Returns:
            Dictionary with analysis results
        """
        result = {}

        # Use custom prompt if provided
        if self.custom_prompt:
            result["description"] = self._analyzer.generate_caption(
                image,
                prompt=self.custom_prompt,
                max_tokens=200
            )
            return result

        # Default description
        result["description"] = self._analyzer.generate_caption(
            image,
            prompt="Describe this video frame in one sentence.",
            max_tokens=100
        )

        # Detailed analysis if requested
        if self.detailed_analysis:
            result["mood"] = self._analyzer.generate_caption(
                image,
                prompt="What is the mood or atmosphere of this scene? Answer in 2-3 words.",
                max_tokens=20
            )
            result["objects"] = self._analyzer.generate_caption(
                image,
                prompt="List the main objects visible in this frame.",
                max_tokens=50
            )
            result["action"] = self._analyzer.generate_caption(
                image,
                prompt="What action or activity is happening in this frame?",
                max_tokens=50
            )

        return result

    def _analyze_with_pytorch(self, image: Image.Image) -> dict[str, str]:
        """
        Analyze image using PyTorch MoondreamPyTorch.

        Args:
            image: PIL Image

        Returns:
            Dictionary with analysis results
        """
        result = {}

        # Use custom prompt if provided
        if self.custom_prompt:
            result["description"] = self._analyzer.answer_question(
                image,
                question=self.custom_prompt
            )
            return result

        # Default caption
        result["description"] = self._analyzer.caption(image)

        # Detailed analysis if requested
        if self.detailed_analysis:
            result["mood"] = self._analyzer.answer_question(
                image,
                question="What is the mood or atmosphere of this scene? Answer in 2-3 words."
            )
            result["objects"] = self._analyzer.answer_question(
                image,
                question="List the main objects visible in this frame."
            )
            result["action"] = self._analyzer.answer_question(
                image,
                question="What action or activity is happening in this frame?"
            )

        return result
