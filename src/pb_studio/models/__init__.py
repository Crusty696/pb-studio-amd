"""
PB Studio AMD - Data Models

Dataclasses for audio, video, and timeline processing.
"""

from src.pb_studio.models.audio import (
    AudioMetadata,
    BeatInfo,
    AudioAnalysisResult,
    StemResult,
    AudioEmbeddingResult,
)
from src.pb_studio.models.video import (
    VideoMetadata,
    SceneInfo,
    MotionData,
    VideoAnalysisResult,
)
from src.pb_studio.models.timeline import (
    TransitionType,
    CutPoint,
    CutPlan,
    RenderSegment,
    RenderResult,
)

__all__ = [
    # Audio models
    "AudioMetadata",
    "BeatInfo",
    "AudioAnalysisResult",
    "StemResult",
    "AudioEmbeddingResult",
    # Video models
    "VideoMetadata",
    "SceneInfo",
    "MotionData",
    "VideoAnalysisResult",
    # Timeline models
    "TransitionType",
    "CutPoint",
    "CutPlan",
    "RenderSegment",
    "RenderResult",
]
