"""Video processing module for PB Studio AMD.

This module provides:
- Video generation and rendering (FFmpeg + AMF)
- Scene detection (PySceneDetect)
- Optical flow / motion analysis (RAFT + DirectML)
- Vision-language analysis (Moondream)
- Frame extraction and thumbnails (OpenCV)
- Auto-tagging (keyword-based)
- Video rendering pipeline (AMF hardware encoding)
"""

try:
    from .engine import VideoGenerator
except ImportError:
    pass

try:
    from .scene_detect import SceneDetector
except ImportError:
    pass  # scenedetect nicht verfügbar (z.B. Linux CI ohne Windows-.venv)

try:
    from .raft import MotionAnalyzer, create_motion_analyzer
except ImportError:
    pass

try:
    from .moondream import MoondreamAnalyzer
except ImportError:
    pass

try:
    from .encoder_utils import get_encoder_config, build_ffmpeg_encode_args
except ImportError:
    pass

# --- Neue Module (portiert von NVIDIA, angepasst für AMD) ---

try:
    from .frame_extractor import FrameGrabber
except ImportError:
    FrameGrabber = None

try:
    from .thumbnail_generator import generate_clip_thumbnail, batch_generate_thumbnails
except ImportError:
    generate_clip_thumbnail = None
    batch_generate_thumbnails = None

try:
    from .auto_tagger import extract_tags, aggregate_clip_tags, TAG_KEYWORDS
except ImportError:
    extract_tags = None
    aggregate_clip_tags = None
    TAG_KEYWORDS = {}

__all__ = [
    # Bestehende Module
    'VideoGenerator',
    'SceneDetector',
    'MotionAnalyzer',
    'create_motion_analyzer',
    'MoondreamAnalyzer',
    'get_encoder_config',
    'build_ffmpeg_encode_args',
    # Neue Module
    'FrameGrabber',
    'generate_clip_thumbnail',
    'batch_generate_thumbnails',
    'extract_tags',
    'aggregate_clip_tags',
    'TAG_KEYWORDS',
]
