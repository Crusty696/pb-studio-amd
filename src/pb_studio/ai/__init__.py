"""
AI Module - AMD DirectML-optimized Models

This module contains AI model wrappers optimized for AMD GPUs via DirectML.
All models use ONNX Runtime with DirectML execution provider.

Available Components:
- CLAPAnalyzer: Zero-shot audio classification (CLAP model)
- SigLIPWrapper: Image embeddings and zero-shot classification
- VideoSpecialist: Video analysis and clip matching using SigLIP
- SmartDirector: AI-powered video generation orchestrator

Smart Director Architecture:
    Smart Director
    |-- Audio Analysis (CLAP) --> Mood Tags, Energy Curve
    |-- Video Analysis (SigLIP) --> Clip Embeddings, Content Tags
    |-- Pacing Engine --> Cut Points, Timeline
    +-- Matcher --> Audio-Video Semantic Matching
"""

try:
    from .clap_wrapper import CLAPAnalyzer
except ImportError:
    pass

try:
    from .siglip_wrapper import SigLIPWrapper
except ImportError:
    pass

try:
    from .video_specialist import VideoSpecialist, VideoClip
except ImportError:
    pass

try:
    from .smart_director import (
        SmartDirector,
        AudioAnalysis,
        ClipAnalysis,
        Timeline,
        TimelineClip,
        MoodCategory
    )
except ImportError:
    pass

__all__ = [
    # Model Wrappers
    'CLAPAnalyzer',
    'SigLIPWrapper',
    'VideoSpecialist',
    'VideoClip',

    # Smart Director
    'SmartDirector',
    'AudioAnalysis',
    'ClipAnalysis',
    'Timeline',
    'TimelineClip',
    'MoodCategory',
]
