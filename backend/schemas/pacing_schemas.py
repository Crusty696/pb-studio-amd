"""Pacing-bezogene Schemas."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any


class PreviewRequest(BaseModel):
    """Request: Timeline-Preview generieren."""
    # BUG-062 FIX: ge=0.0 validation
    start_sec: float = Field(0.0, ge=0.0)
    duration: float = Field(10.0, gt=0.0)


class TriggerSettingsSchema(BaseModel):
    """Trigger-Einstellungen für Pacing."""
    beat_weight: float = Field(1.0, ge=0.0, le=2.0)
    onset_weight: float = Field(0.5, ge=0.0, le=2.0)
    kick_weight: float = Field(1.2, ge=0.0, le=2.0)
    snare_weight: float = Field(1.0, ge=0.0, le=2.0)
    hihat_weight: float = Field(0.3, ge=0.0, le=2.0)
    energy_weight: float = Field(0.8, ge=0.0, le=2.0)
    energy_threshold: float = Field(0.6, ge=0.0, le=1.0)
    min_clip_length: float = Field(1.0, ge=0.1)
    max_clip_length: float = Field(8.0, ge=0.5)
    onset_sensitivity: float = Field(0.5, ge=0.0, le=1.0)
    clip_length_variation: float = Field(0.0, ge=0.0, le=1.0)
    min_cut_interval: float = Field(0.5, ge=0.0)
    max_cut_interval: float = Field(10.0, gt=0.0)
    beat_trigger_mode: str = Field("all", pattern="^(all|downbeat_only|strong_only)$")

    @field_validator("max_clip_length")
    @classmethod
    def max_must_be_ge_min(cls, v: float, info: Any) -> float:
        # BUG-064 FIX: Validation logic
        if "min_clip_length" in info.data and v < info.data["min_clip_length"]:
            raise ValueError(f"max_clip_length ({v}) muss >= min_clip_length ({info.data['min_clip_length']}) sein")
        return v

class PacingConfigSchema(BaseModel):
    """Request: Pacing-Konfiguration."""
    audio_clip_id: int
    video_clip_ids: list[int] = []
    expected_bpm: float = 120.0
    trigger_settings: Optional[TriggerSettingsSchema] = None
    use_motion_matching: bool = False
    use_semantic_matching: bool = False
    use_structure_awareness: bool = False
    duration_limit: Optional[float] = None
    min_cut_interval: float = 0.5
    # Plan Phase 4: brain integration toggles
    use_brain: bool = False
    brain_min_confidence: float = Field(0.0, ge=0.0, le=1.0)


class CutListEntrySchema(BaseModel):
    """Ein Eintrag in der Cut-Liste."""
    clip_id: str
    start_time: float
    end_time: float
    metadata: dict[str, Any] = {}

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class CutListResponse(BaseModel):
    """Response: Generierte Cut-Liste."""
    cuts: list[CutListEntrySchema] = []
    total_duration: float = 0.0
    cut_count: int = 0
    average_cut_duration: float = 0.0


class TimelineEntrySchema(BaseModel):
    """Ein Timeline-Eintrag für die Vorschau."""
    clip_id: str
    clip_name: str
    file_path: str
    start_time: float
    end_time: float
    clip_start: float = 0.0
    trigger_type: str = ""
    trigger_strength: float = 0.0
    segment_type: Optional[str] = None


class TimelineResponse(BaseModel):
    """Response: Aktuelle Timeline."""
    entries: list[TimelineEntrySchema] = []
    total_duration: float = 0.0
    audio_path: Optional[str] = None


class TimelineUpdateRequest(BaseModel):
    """Request: Timeline manuell aktualisieren."""
    entries: list[TimelineEntrySchema]


class PreviewResponse(BaseModel):
    """Response: Preview-Datei."""
    preview_path: str
    duration: float
    resolution: str = "640x360"
