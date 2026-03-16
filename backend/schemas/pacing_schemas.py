"""Pacing-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class TriggerSettingsSchema(BaseModel):
    """Trigger-Einstellungen für Pacing.

    Feldnamen muessen mit TriggerSettings-Dataclass uebereinstimmen
    (src/pb_studio/pacing/pacing_models.py), sonst werden sie von
    advanced_pacing_engine.py:150 per hasattr() stillschweigend ignoriert.
    """
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


class PacingConfigSchema(BaseModel):
    """Request: Pacing-Konfiguration."""
    audio_clip_id: int
    video_clip_ids: list[int] = []
    expected_bpm: float = 120.0
    trigger_settings: Optional[TriggerSettingsSchema] = None
    use_motion_matching: bool = False
    use_structure_awareness: bool = False
    duration_limit: Optional[float] = None
    min_cut_interval: float = 0.5


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


class PreviewRequest(BaseModel):
    """Request: Timeline-Preview generieren."""
    start_sec: float = 0.0
    duration: float = 10.0


class PreviewResponse(BaseModel):
    """Response: Preview-Datei."""
    preview_path: str
    duration: float
    resolution: str = "640x360"
