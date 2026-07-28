"""Render-bezogene Schemas."""

from pydantic import BaseModel, Field, field_validator
from pathlib import Path as _Path
from typing import Optional
from enum import Enum


class RenderQuality(str, Enum):
    """Render-Qualitätsstufen."""
    PREVIEW = "preview"    # 720p, schnell
    STANDARD = "standard"  # 1080p, balanced
    HIGH = "high"          # 1080p, hohe Bitrate
    ULTRA = "ultra"        # 4K, maximale Qualität


class RenderEncoder(str, Enum):
    """Verfügbare Video-Encoder."""
    HEVC_AMF = "hevc_amf"    # AMD Hardware H.265
    H264_AMF = "h264_amf"    # AMD Hardware H.264
    AV1_AMF = "av1_amf"      # AMD Hardware AV1


class RenderRequest(BaseModel):
    """Request: Rendering starten."""
    output_path: str = Field(..., description="Ziel-Dateipfad")
    audio_path: str = Field(..., description="Audio-Quell-Pfad")
    quality: RenderQuality = RenderQuality.HIGH
    encoder: Optional[RenderEncoder] = None  # None = Auto-Detect
    resolution_width: int = Field(default=1920, ge=2, le=7680)
    resolution_height: int = Field(default=1080, ge=2, le=4320)
    fps: float = Field(default=30.0, gt=0.0, le=120.0)
    bitrate_mbps: float = Field(default=12.0, gt=0.0, le=500.0)
    include_audio: bool = True

    @field_validator("output_path")
    @classmethod
    def output_dir_must_exist(cls, v: str) -> str:
        # BUG-065 FIX: Check if parent directory exists
        if v:
            p = _Path(v).resolve()
            if not p.parent.exists():
                raise ValueError(f"Zielverzeichnis existiert nicht: {p.parent!r}")
        return v

    @field_validator("audio_path")
    @classmethod
    def audio_path_must_exist(cls, v: str) -> str:
        if v and not _Path(v).exists():
            raise ValueError(f"audio_path existiert nicht: {v!r}")
        return v


class RenderProgress(BaseModel):
    """Response: Render-Fortschritt."""
    task_id: str
    status: str = "running"  # pending, running, completed, failed, cancelled
    percent: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    fps: float = 0.0
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0
    output_path: Optional[str] = None
    error: Optional[str] = None


class RenderResult(BaseModel):
    """Response: Render-Ergebnis."""
    task_id: str
    success: bool
    output_path: Optional[str] = None
    duration_seconds: float = 0.0
    file_size_mb: float = 0.0
    encoder_used: str = ""
    error: Optional[str] = None
