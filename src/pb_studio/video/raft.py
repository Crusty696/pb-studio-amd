"""
RAFT Optical Flow - ONNX Implementation with DirectML.

This module provides optical flow estimation using the RAFT (Recurrent All-Pairs
Field Transforms) model exported to ONNX format. Optimized for AMD GPUs via DirectML.

RAFT computes dense optical flow between two consecutive frames, useful for:
- Scene cut detection via motion analysis
- Motion-based video segmentation
- Action recognition preprocessing
- Video stabilization

Reference: https://arxiv.org/abs/2003.12039
"""

import logging
import numpy as np
import onnxruntime as ort
import cv2
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Union

logger = logging.getLogger(__name__)

# RAFT preprocessing constants
RAFT_DEFAULT_SIZE = (448, 256)  # Width x Height (divisible by 8)
RAFT_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
RAFT_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Flow visualization constants
FLOW_VIS_WHEEL_NCOLS = 55


class MotionAnalyzer:
    """
    RAFT-based optical flow analyzer for motion estimation.

    Uses ONNX Runtime with DirectML for AMD GPU acceleration.
    Falls back to CPU if DirectML is unavailable.

    Key Methods:
    - calculate_flow(): Compute flow between two frames
    - get_motion_magnitude(): Get scalar motion metric
    - detect_scene_change(): Check if frames are from different scenes
    - visualize_flow(): Create flow visualization image
    """

    def __init__(
        self,
        models_dir: Optional[str] = None,
        target_size: Tuple[int, int] = RAFT_DEFAULT_SIZE,
        lazy_load: bool = True
    ):
        """
        Initialize the RAFT motion analyzer.

        Args:
            models_dir: Directory containing ONNX model files.
                       If None, uses ConfigManager default.
            target_size: (width, height) for flow computation.
                        Must be divisible by 8.
            lazy_load: If True, defer model loading until first use.
                      Recommended since RAFT is memory-intensive.
        """
        # Import here to avoid circular imports
        from pb_studio.config_manager import ConfigManager

        self.config = ConfigManager()
        self._models_dir = models_dir or self.config.get("paths", {}).get("models_dir", "./models")

        # Validate and store target size
        w, h = target_size
        if w % 8 != 0 or h % 8 != 0:
            logger.warning(f"Target size {target_size} not divisible by 8, adjusting...")
            w = (w // 8) * 8
            h = (h // 8) * 8
        self.target_size = (max(w, 64), max(h, 64))

        # Session state
        self.session: Optional[ort.InferenceSession] = None
        self._active_provider = "Unknown"
        self._initialized = False

        # Model path - unterstuetze beide Dateinamen
        raft_small = Path(self._models_dir) / "raft_small.onnx"
        raft_standard = Path(self._models_dir) / "raft.onnx"
        self.model_path = raft_small if raft_small.exists() else raft_standard

        # Flow colorwheel for visualization (computed once)
        self._colorwheel = None

        if not lazy_load:
            self._init_model()

    def _create_session_options(self) -> ort.SessionOptions:
        """Create optimized session options for DirectML compatibility."""
        sess_options = ort.SessionOptions()

        # KRITISCH fuer DirectML: Memory Pattern MUSS deaktiviert sein
        sess_options.enable_mem_pattern = False

        # Graph-Optimierungen aktivieren
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Performance-Optimierungen
        sess_options.enable_cpu_mem_arena = True
        sess_options.intra_op_num_threads = 0  # Auto
        sess_options.inter_op_num_threads = 0  # Auto

        # Memory-Limits fuer grosse Modelle
        sess_options.add_session_config_entry("session.use_env_allocators", "1")

        return sess_options

    def _get_providers(self) -> List[str]:
        """Get available execution providers — DirectML only (AMD IRON RULE: no CPU fallback)."""
        available = ort.get_available_providers()

        providers = []

        if 'DmlExecutionProvider' in available:
            providers.append('DmlExecutionProvider')
            logger.info("DirectML provider available - using AMD GPU acceleration for RAFT")

        # IRON RULE: AMD DirectML ONLY — kein CPUExecutionProvider Fallback
        return providers

    def _init_model(self) -> bool:
        """
        Initialize the RAFT ONNX model session.

        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True

        if not self.model_path.exists():
            logger.warning(
                f"RAFT ONNX model not found at {self.model_path}. "
                "Motion analysis will be unavailable. "
                "Download the model or export from PyTorch."
            )
            return False

        try:
            sess_options = self._create_session_options()
            providers = self._get_providers()

            if not providers:
                logger.warning(
                    "RAFT: DmlExecutionProvider nicht verfügbar. "
                    "Motion-Analyse deaktiviert (IRON RULE: kein CPU-Fallback)."
                )
                return False

            logger.info(f"Loading RAFT model from {self.model_path}...")

            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=providers
            )

            self._active_provider = self.session.get_providers()[0]
            self._initialized = True

            logger.info(f"RAFT model loaded. Active Provider: {self._active_provider}")
            self._log_model_info()

            return True

        except Exception as e:
            logger.error(f"Failed to initialize RAFT model: {e}")
            self.session = None
            return False

    def _log_model_info(self):
        """Log model input/output information for debugging."""
        if self.session:
            logger.debug("RAFT Model Inputs:")
            for inp in self.session.get_inputs():
                logger.debug(f"  {inp.name}: {inp.shape} ({inp.type})")

            logger.debug("RAFT Model Outputs:")
            for out in self.session.get_outputs():
                logger.debug(f"  {out.name}: {out.shape} ({out.type})")

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess a frame for RAFT input.

        Steps:
        1. Convert BGR to RGB (if from OpenCV)
        2. Resize to target size
        3. Normalize with ImageNet mean/std
        4. Convert to NCHW format

        Args:
            frame: BGR numpy array (H, W, 3)

        Returns:
            Preprocessed tensor [1, 3, H, W]
        """
        # BGR -> RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = frame

        # Resize
        resized = cv2.resize(
            rgb_frame,
            self.target_size,
            interpolation=cv2.INTER_LINEAR
        )

        # Zu float32 konvertieren und auf [0, 1] normalisieren
        img_array = resized.astype(np.float32) / 255.0

        # ImageNet Normalisierung
        img_array = (img_array - RAFT_MEAN) / RAFT_STD

        # HWC -> NCHW
        img_array = np.transpose(img_array, (2, 0, 1))  # CHW
        img_array = np.expand_dims(img_array, axis=0)   # NCHW

        return img_array.astype(np.float32)

    def calculate_flow(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        num_iterations: int = 12
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate optical flow between two consecutive frames.

        Args:
            frame1: First frame (BGR, from OpenCV)
            frame2: Second frame (BGR, from OpenCV)
            num_iterations: RAFT refinement iterations (more = better quality)

        Returns:
            Tuple of (flow_u, flow_v):
            - flow_u: Horizontal flow component (H, W)
            - flow_v: Vertical flow component (H, W)

            Returns (zeros, zeros) on error.
        """
        if not self._initialized:
            if not self._init_model():
                h, w = frame1.shape[:2]
                return np.zeros((h, w)), np.zeros((h, w))

        try:
            # Preprocess both frames
            img1 = self.preprocess_frame(frame1)
            img2 = self.preprocess_frame(frame2)

            # Prepare inputs based on model's expected format
            input_names = [inp.name for inp in self.session.get_inputs()]

            # Robustes Input-Mapping: positional-first wenn genau 2 Inputs
            inputs = {}
            img_inputs = [n for n in input_names if "iter" not in n.lower()]
            iter_inputs = [n for n in input_names if "iter" in n.lower()]

            if len(img_inputs) == 2:
                # Direktes positionales Mapping — unabhaengig von Namenskonventionen
                inputs[img_inputs[0]] = img1
                inputs[img_inputs[1]] = img2
            elif len(img_inputs) >= 3:
                # Bei 3+ Bild-Inputs: heuristisches Matching fuer bekannte Namen
                for name in img_inputs:
                    name_lower = name.lower()
                    if any(k in name_lower for k in ["1", "first", "prev", "image1", "frame1"]):
                        inputs[name] = img1
                    elif any(k in name_lower for k in ["2", "second", "next", "image2", "frame2", "curr"]):
                        inputs[name] = img2
                # Fallback: positional wenn Heuristik nicht ausreicht
                if len(inputs) < 2 and len(img_inputs) >= 2:
                    inputs[img_inputs[0]] = img1
                    inputs[img_inputs[1]] = img2
            elif len(input_names) >= 2:
                # Alle Inputs sind Bild-Inputs (keine iter-Inputs)
                inputs[input_names[0]] = img1
                inputs[input_names[1]] = img2

            # Iterations-Input falls vorhanden
            for name in iter_inputs:
                inputs[name] = np.array([num_iterations], dtype=np.int64)

            # Run inference
            outputs = self.session.run(None, inputs)

            # RAFT Output ist typisch: flow [1, 2, H, W]
            # oder Liste von flows fuer verschiedene Iterationen
            if isinstance(outputs, list) and len(outputs) > 0:
                # Letzter Output ist finaler Flow bei iterativen Modellen
                flow = outputs[-1] if len(outputs) > 1 else outputs[0]
            elif outputs is not None:
                flow = outputs
            else:
                logger.warning("RAFT returned None output")
                h, w = frame1.shape[:2]
                return np.zeros((h, w)), np.zeros((h, w))

            # Output-Shape validieren
            if not isinstance(flow, np.ndarray):
                logger.warning(f"RAFT returned non-ndarray output: {type(flow)}")
                h, w = frame1.shape[:2]
                return np.zeros((h, w)), np.zeros((h, w))

            if flow.ndim not in (3, 4):
                logger.warning(f"RAFT output has unexpected ndim={flow.ndim}, shape={flow.shape}")
                h, w = frame1.shape[:2]
                return np.zeros((h, w)), np.zeros((h, w))

            # Extrahiere U (horizontal) und V (vertikal) Komponenten
            if flow.ndim == 4:  # [B, 2, H, W]
                if flow.shape[1] < 2:
                    logger.warning(f"RAFT output has <2 channels: {flow.shape}")
                    h, w = frame1.shape[:2]
                    return np.zeros((h, w)), np.zeros((h, w))
                flow_u = flow[0, 0, :, :]
                flow_v = flow[0, 1, :, :]
            elif flow.ndim == 3:  # [2, H, W]
                if flow.shape[0] < 2:
                    logger.warning(f"RAFT output has <2 channels: {flow.shape}")
                    h, w = frame1.shape[:2]
                    return np.zeros((h, w)), np.zeros((h, w))
                flow_u = flow[0, :, :]
                flow_v = flow[1, :, :]
            else:
                logger.warning(f"Unexpected flow shape: {flow.shape}")
                h, w = frame1.shape[:2]
                return np.zeros((h, w)), np.zeros((h, w))

            # Skaliere Flow auf Original-Bildgroesse
            orig_h, orig_w = frame1.shape[:2]
            if flow_u.shape != (orig_h, orig_w):
                if flow_u.shape[0] == 0 or flow_u.shape[1] == 0:
                    logger.warning(f"RAFT returned zero-size flow: {flow_u.shape}")
                    return np.zeros((orig_h, orig_w)), np.zeros((orig_h, orig_w))
                scale_x = orig_w / flow_u.shape[1]
                scale_y = orig_h / flow_u.shape[0]

                flow_u = cv2.resize(flow_u, (orig_w, orig_h)) * scale_x
                flow_v = cv2.resize(flow_v, (orig_w, orig_h)) * scale_y

            return flow_u.astype(np.float32), flow_v.astype(np.float32)

        except Exception as e:
            logger.error(f"Flow calculation failed: {e}")
            h, w = frame1.shape[:2]
            return np.zeros((h, w)), np.zeros((h, w))

    def get_motion_magnitude(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        percentile: float = 95.0
    ) -> float:
        """
        Calculate a scalar motion magnitude between two frames.

        Useful for scene change detection and motion-based segmentation.

        Args:
            frame1: First frame
            frame2: Second frame
            percentile: Use this percentile of magnitudes (95% ignores outliers)

        Returns:
            Motion magnitude score (higher = more motion)
        """
        flow_u, flow_v = self.calculate_flow(frame1, frame2)

        # Berechne Magnitude
        magnitude = np.sqrt(flow_u**2 + flow_v**2)
        magnitude = np.nan_to_num(magnitude, nan=0.0, posinf=1000.0, neginf=0.0)

        # Verwende Percentil statt Maximum (robuster gegen Ausreisser)
        if magnitude.size > 0:
            return float(np.percentile(magnitude, percentile))
        return 0.0

    def get_motion_statistics(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate comprehensive motion statistics.

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Dictionary with motion metrics:
            - mean_magnitude: Average motion
            - max_magnitude: Peak motion
            - std_magnitude: Motion variance
            - motion_coverage: Percentage of pixels with significant motion
            - dominant_direction: Primary motion direction in degrees
        """
        flow_u, flow_v = self.calculate_flow(frame1, frame2)
        magnitude = np.sqrt(flow_u**2 + flow_v**2)
        angle = np.arctan2(flow_v, flow_u) * 180 / np.pi  # In Grad

        # Motion threshold (mindestens 1 Pixel Bewegung)
        motion_mask = magnitude > 1.0

        stats = {
            "mean_magnitude": float(np.mean(magnitude)),
            "max_magnitude": float(np.max(magnitude)),
            "std_magnitude": float(np.std(magnitude)),
            "p95_magnitude": float(np.percentile(magnitude, 95)),
            "motion_coverage": float(np.sum(motion_mask) / magnitude.size * 100),
            "dominant_direction": float(np.median(angle[motion_mask])) if np.any(motion_mask) else 0.0
        }

        return stats

    def detect_scene_change(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        threshold: float = 50.0
    ) -> Tuple[bool, float]:
        """
        Detect if two frames are from different scenes based on motion analysis.

        Scene changes typically show:
        - Very high motion magnitude (abrupt change)
        - OR inconsistent flow patterns (different content)

        Args:
            frame1: First frame
            frame2: Second frame
            threshold: Motion threshold for scene change

        Returns:
            Tuple of (is_scene_change, confidence_score)
        """
        stats = self.get_motion_statistics(frame1, frame2)

        # Hohe Bewegung mit hoher Varianz = wahrscheinlich Szenenwechsel
        magnitude = stats["p95_magnitude"]
        variance = stats["std_magnitude"]

        # Szenenwechsel-Score
        # Kombiniert Magnitude und Varianz
        score = magnitude * (1 + variance / 10.0)

        is_change = score > threshold
        confidence = min(score / threshold, 2.0)  # 0-2 range

        return is_change, float(confidence)

    def _make_colorwheel(self) -> np.ndarray:
        """
        Create color wheel for flow visualization (Middlebury style).
        """
        if self._colorwheel is not None:
            return self._colorwheel

        # Color definitions
        RY, YG, GC, CB, BM, MR = 15, 6, 4, 11, 13, 6
        ncols = RY + YG + GC + CB + BM + MR

        colorwheel = np.zeros((ncols, 3), dtype=np.uint8)
        col = 0

        # RY
        colorwheel[0:RY, 0] = 255
        colorwheel[0:RY, 1] = np.floor(255 * np.arange(0, RY) / RY)
        col += RY

        # YG
        colorwheel[col:col+YG, 0] = 255 - np.floor(255 * np.arange(0, YG) / YG)
        colorwheel[col:col+YG, 1] = 255
        col += YG

        # GC
        colorwheel[col:col+GC, 1] = 255
        colorwheel[col:col+GC, 2] = np.floor(255 * np.arange(0, GC) / GC)
        col += GC

        # CB
        colorwheel[col:col+CB, 1] = 255 - np.floor(255 * np.arange(0, CB) / CB)
        colorwheel[col:col+CB, 2] = 255
        col += CB

        # BM
        colorwheel[col:col+BM, 2] = 255
        colorwheel[col:col+BM, 0] = np.floor(255 * np.arange(0, BM) / BM)
        col += BM

        # MR
        colorwheel[col:col+MR, 0] = 255
        colorwheel[col:col+MR, 2] = 255 - np.floor(255 * np.arange(0, MR) / MR)

        self._colorwheel = colorwheel
        return colorwheel

    def visualize_flow(
        self,
        flow_u: np.ndarray,
        flow_v: np.ndarray,
        clip_flow: Optional[float] = None
    ) -> np.ndarray:
        """
        Create a color visualization of optical flow.

        Uses the Middlebury color scheme:
        - Hue represents direction
        - Saturation represents magnitude

        Args:
            flow_u: Horizontal flow component
            flow_v: Vertical flow component
            clip_flow: Optional maximum flow magnitude for normalization

        Returns:
            BGR visualization image (H, W, 3)
        """
        colorwheel = self._make_colorwheel()
        ncols = colorwheel.shape[0]

        # Compute magnitude and angle
        magnitude = np.sqrt(flow_u**2 + flow_v**2)
        angle = np.arctan2(-flow_v, -flow_u) / np.pi  # -1 to 1

        # Normalize magnitude
        if clip_flow is not None:
            magnitude = np.clip(magnitude, 0, clip_flow)
            max_flow = clip_flow
        else:
            max_flow = np.max(magnitude) if np.max(magnitude) > 0 else 1.0

        normalized_mag = magnitude / max_flow

        # Map angle to colorwheel index
        fk = (angle + 1) / 2 * (ncols - 1)  # 0 to ncols-1
        k0 = np.floor(fk).astype(np.int32)
        k1 = k0 + 1
        k1[k1 == ncols] = 0
        f = fk - k0

        # Create visualization
        h, w = flow_u.shape
        vis = np.zeros((h, w, 3), dtype=np.uint8)

        for c in range(3):
            c0 = colorwheel[k0, c] / 255.0
            c1 = colorwheel[k1, c] / 255.0
            color = (1 - f) * c0 + f * c1

            # Reduce saturation for small magnitudes
            color = 1 - normalized_mag[..., np.newaxis] * (1 - color[..., np.newaxis])
            vis[:, :, c] = (color[:, :, 0] * 255).astype(np.uint8)

        # Convert RGB to BGR for OpenCV
        vis = cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)

        return vis

    def analyze_video_segment(
        self,
        frames: List[np.ndarray],
        stride: int = 1
    ) -> Dict[str, Any]:
        """
        Analyze motion patterns in a video segment.

        Args:
            frames: List of consecutive frames
            stride: Process every N-th frame pair

        Returns:
            Dictionary with segment analysis:
            - frame_motions: List of motion magnitudes
            - avg_motion: Average motion across segment
            - peak_motion: Maximum motion
            - scene_changes: List of detected scene change indices
        """
        if len(frames) < 2:
            return {
                "frame_motions": [],
                "avg_motion": 0.0,
                "peak_motion": 0.0,
                "scene_changes": []
            }

        motions = []
        scene_changes = []

        for i in range(0, len(frames) - 1, stride):
            frame1 = frames[i]
            frame2 = frames[min(i + stride, len(frames) - 1)]

            magnitude = self.get_motion_magnitude(frame1, frame2)
            motions.append(magnitude)

            is_change, confidence = self.detect_scene_change(frame1, frame2)
            if is_change:
                scene_changes.append({
                    "frame_index": i,
                    "confidence": confidence
                })

        return {
            "frame_motions": motions,
            "avg_motion": float(np.mean(motions)) if motions else 0.0,
            "peak_motion": float(np.max(motions)) if motions else 0.0,
            "scene_changes": scene_changes
        }

    @property
    def is_ready(self) -> bool:
        """Check if model is initialized and ready for inference."""
        return self._initialized and self.session is not None

    @property
    def active_provider(self) -> str:
        """Get the active execution provider name."""
        return self._active_provider

    def unload(self):
        """Release model resources."""
        self.session = None
        self._initialized = False

        # DirectML gibt VRAM erst bei GC frei
        import gc
        gc.collect()

        logger.info("RAFT model unloaded")


# CPU Fallback using OpenCV's Farneback method
class FarnebackFlowAnalyzer:
    """
    Fallback optical flow analyzer using OpenCV's Farneback method.

    Use this when RAFT model is not available or GPU resources are limited.
    Less accurate but works on CPU without additional dependencies.
    """

    def __init__(self):
        """Initialize the Farneback flow analyzer."""
        logger.info("Using Farneback optical flow (CPU fallback)")

    def calculate_flow(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate optical flow using Farneback algorithm.

        Args:
            frame1: First frame (BGR)
            frame2: Second frame (BGR)

        Returns:
            Tuple of (flow_u, flow_v)
        """
        # Zu Graustufen konvertieren
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

        # Farneback Optical Flow
        flow = cv2.calcOpticalFlowFarneback(
            gray1, gray2,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0
        )

        flow_u = flow[:, :, 0]
        flow_v = flow[:, :, 1]

        return flow_u, flow_v

    def get_motion_magnitude(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        percentile: float = 95.0
    ) -> float:
        """Calculate motion magnitude between frames."""
        flow_u, flow_v = self.calculate_flow(frame1, frame2)
        magnitude = np.sqrt(flow_u**2 + flow_v**2)
        return float(np.percentile(magnitude, percentile))


def create_motion_analyzer(prefer_gpu: bool = True) -> MotionAnalyzer:
    """
    Factory function to create a DirectML RAFT motion analyzer.

    IRON RULE: Kein CPU-Fallback (kein Farneback). Wenn RAFT/DirectML nicht
    verfuegbar ist, wird ein nicht-initialisierter MotionAnalyzer zurueckgegeben
    dessen analyze_video_segment() ein leeres Ergebnis liefert.

    Args:
        prefer_gpu: Reserviert fuer API-Kompatibilitaet — wird ignoriert.
                   Nur DirectML wird unterstuetzt.

    Returns:
        MotionAnalyzer (ggf. nicht initialisiert wenn DirectML fehlt)
    """
    import os
    allow_cpu = os.environ.get("ALLOW_CPU_FALLBACK", "0").strip().lower() in ("1", "true", "yes")
    if allow_cpu:
        # Nur per explizitem Env-Flag erlaubt (z.B. fuer Unit-Tests)
        logger.warning("ALLOW_CPU_FALLBACK=1 gesetzt — Farneback CPU-Fallback aktiviert")
        analyzer = MotionAnalyzer(lazy_load=False)
        if analyzer.is_ready:
            return analyzer
        return FarnebackFlowAnalyzer()  # type: ignore[return-value]

    analyzer = MotionAnalyzer(lazy_load=False)
    if not analyzer.is_ready:
        logger.warning(
            "RAFT DirectML nicht verfuegbar — Motion-Analyse deaktiviert. "
            "Kein CPU-Fallback (IRON RULE)."
        )
    return analyzer
