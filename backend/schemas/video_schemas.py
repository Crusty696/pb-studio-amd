"""Video-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class VideoImportRequest(BaseModel):
    """Request: Video-Dateien importieren."""
    paths: list[str] = Field(..., min_length=1, description="Liste absoluter Pfade")


class VideoClipInfo(BaseModel):
    """Response: Importierter Video-Clip."""
    id: int
    name: str
    path: str
    duration_seconds: float
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    codec: str = ""
    thumbnail_available: bool = False
    tags: list[str] = []
    is_analyzed: bool = False
    video_hash: Optional[str] = None
    has_video_embedding: bool = False


class VideoAnalyzeRequest(BaseModel):
    """Request: Video analysieren."""
    # BUG-063 FIX: ge=0 validation
    clip_id: int = Field(..., ge=0)
    detect_scenes: bool = True
    generate_embeddings: bool = True
    analyze_motion: bool = True
    generate_captions: bool = False


class VideoAnalysisResult(BaseModel):
    """Response: Video-Analyse Ergebnis."""
    clip_id: int
    scene_count: int = 0
    avg_motion: float = 0.0
    dominant_colors: list[str] = []
    tags: list[str] = []
    mood_tags: list[str] = []
    style_tags: list[str] = []
    object_tags: list[str] = []
    embedding_dim: int = 0  # SigLIP; 0 = kein Embedding vorhanden
    has_embedding: bool = False
    scenes: list["SceneInfo"] = []
    motion: Optional["MotionData"] = None
    brightness_curve: list[float] = []
    saturation_curve: list[float] = []
    color_temp_curve: list[float] = []
    # L-K4: Tonart des Audio-Tracks (vom Video extrahiert via ffmpeg + Krumhansl-Kessler).
    # None wenn Video keinen Audio-Track hat oder Detection fehlschlaegt.
    # Wird im Pacing fuer use_key_matching (Camelot-Wheel Compatibility) genutzt.
    audio_key: Optional[str] = None


class SceneInfo(BaseModel):
    """Ein erkannter Scene-Cut."""
    start_time: float
    end_time: float
    scene_type: str = "cut"  # cut, fade, dissolve
    confidence: float = 0.0


class MotionData(BaseModel):
    """Response: Motion-Analyse Daten."""
    clip_id: int
    avg_motion: float = 0.0
    motion_curve: list[float] = []
    # peak_frames: dict-Liste von MotionAnalyzer ({"frame_index": int, "confidence": float})
    peak_frames: list[dict] = []
    motion_category: str = "medium"  # low, medium, high, extreme


# Forward-References auflösen (SceneInfo/MotionData nach VideoAnalysisResult definiert)
VideoAnalysisResult.model_rebuild()
