"""Video processing module for PB Studio AMD.

This module provides:
- Video generation and rendering (FFmpeg + AMF)
- Scene detection (PySceneDetect)
- Optical flow / motion analysis (RAFT + DirectML)
- Vision-language analysis (Moondream)
"""

from .engine import VideoGenerator
from .scene_detect import SceneDetector
from .raft import MotionAnalyzer, FarnebackFlowAnalyzer, create_motion_analyzer
from .moondream import MoondreamAnalyzer
from .encoder_utils import get_encoder_config, build_ffmpeg_encode_args

__all__ = [
    'VideoGenerator',
    'SceneDetector',
    'MotionAnalyzer',
    'FarnebackFlowAnalyzer',
    'create_motion_analyzer',
    'MoondreamAnalyzer',
    'get_encoder_config',
    'build_ffmpeg_encode_args'
]
