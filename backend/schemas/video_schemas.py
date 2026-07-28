"""Video-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Literal, Optional


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
    # L-N3: SHA256 media_hash fuer Embedding-Cache-Reuse. None wenn Hashing
    # fehlgeschlagen oder Clip aus aelterer DB ohne Hash geladen wurde.
    # UI nutzt das Feld fuer einen "CACHED"-Badge auf der VideoClip-Card.
    video_hash: Optional[str] = None
    has_video_embedding: bool = False
    # L-M4: Motion-Felder fuer UI-Detail-Panel (None falls noch nicht analysiert).
    # Quelle: app_state.video_analysis_cache[clip_id]['motion'].
    avg_motion: Optional[float] = None
    peak_motion: Optional[float] = None
    motion_category: Optional[str] = None
    # L-M8: SigLIP-Embedding-Metadaten (0 wenn kein Embedding generiert wurde).
    # Quelle: app_state.video_analysis_cache[clip_id]['embedding_*'].
    embedding_dim: Optional[int] = None
    embedding_samples: Optional[int] = None
    has_embedding: bool = False
    tag_source: Optional[str] = None


class VideoAnalyzeRequest(BaseModel):
    """Request: Video analysieren."""
    # BUG-063 FIX: ge=0 validation
    clip_id: int = Field(..., ge=0)
    detect_scenes: bool = True
    generate_embeddings: bool = True
    analyze_motion: bool = True
    generate_captions: bool = False
    analyze_colors: bool = True


class VideoAnalysisResult(BaseModel):
    """Response: Video-Analyse Ergebnis.

    L-VIDEO-4 (HIGH): 6 ehemals leere Felder entfernt — kein Producer im
    _run_video_analysis-Pfad, kein direkter Konsument in Pacing/Brain
    (Brain hat eigene CandidateFeatures-Datenklasse). Entfernt: mood_tags,
    style_tags, object_tags, brightness_curve, saturation_curve, color_temp_curve.

    Audit-Fix 2026-07-10 (Sweep-Finding HIGH-10): mood_tags + die neuen
    avg_brightness/avg_saturation/avg_color_temp-Felder wieder aufgenommen —
    die "kein Konsument"-Begruendung von L-VIDEO-4 traf nur auf dieses
    API-Response-Schema zu, NICHT auf den internen video_analysis_cache-Dict,
    den bridge_dimensions.py/post_processor.py/clip_selector.py direkt lesen
    (unabhaengig von diesem Pydantic-Schema). Jetzt gibt es einen echten
    Producer (compute_color_features in moondream_wrapper.py), die Felder
    sind wieder sinnvoll.
    """
    clip_id: int
    scene_count: int = 0
    avg_motion: float = 0.0
    dominant_colors: list[str] = []
    tags: list[str] = []
    embedding_dim: int = 0  # SigLIP; 0 = kein Embedding vorhanden
    embedding_samples: int = 0  # L-M8: Anzahl der gemittelten Frames
    has_embedding: bool = False
    scenes: list["SceneInfo"] = []
    motion: Optional["MotionData"] = None
    # L-K4: Tonart des Audio-Tracks (vom Video extrahiert via ffmpeg + Krumhansl-Kessler).
    # None wenn Video keinen Audio-Track hat oder Detection fehlschlaegt.
    # Wird im Pacing fuer use_key_matching (Camelot-Wheel Compatibility) genutzt.
    audio_key: Optional[str] = None
    tag_source: Optional[str] = None
    mood_tags: list[str] = []
    avg_brightness: float = 0.5
    avg_saturation: float = 0.5
    avg_color_temp: float = 0.0
    status: Literal["completed", "partial"] = "completed"
    stage_status: dict[str, str] = Field(default_factory=dict)
    stage_errors: dict[str, str] = Field(default_factory=dict)


class SceneInfo(BaseModel):
    """Ein erkannter Scene-Cut."""
    start_time: float
    end_time: float
    scene_type: str = "cut"  # cut, fade, dissolve
    confidence: Optional[float] = None


class MotionData(BaseModel):
    """Response: Motion-Analyse Daten."""
    clip_id: int
    avg_motion: float = 0.0
    # L-VIDEO-2 (M-4 CRITICAL): peak_motion (Max aus motion_curve) — wurde
    # von MotionData(**motion) silent gedropped weil das Feld im Schema fehlte.
    # Bricht /video/motion/{id} REST + UI MOTION-Card PEAK-Anzeige.
    peak_motion: float = 0.0
    motion_curve: list[float] = []
    # peak_frames: dict-Liste von MotionAnalyzer ({"frame_index": int, "confidence": float})
    peak_frames: list[dict] = []
    motion_category: str = "medium"  # low, medium, high, extreme


class ThumbstripResponse(BaseModel):
    """Response: N base64-encoded JPEG thumbnails fuer Timeline-Clip-Visualization."""
    clip_id: int
    count: int
    frames: list[str]  # Each entry: "data:image/jpeg;base64,..."


class ClipwaveResponse(BaseModel):
    """Response: downsampled mono peaks (0..1) fuer Timeline-Clip-Waveform."""
    clip_id: int
    count: int
    peaks: list[float]


# Forward-References auflösen (SceneInfo/MotionData nach VideoAnalysisResult definiert)
VideoAnalysisResult.model_rebuild()
