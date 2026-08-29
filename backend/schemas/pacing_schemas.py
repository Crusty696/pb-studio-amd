"""Pacing-bezogene Schemas."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any


# Product scope permits 4-hour DJ mixes; UI editing permits 0.1-second clips.
# 4 * 60 * 60 / 0.1 = 144,000 entries, so this cap preserves the documented
# maximum timeline while making one manual update request finite.
TIMELINE_UPDATE_MAX_ENTRIES = 144_000


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
    # S-H2 (Audit V2): defense-in-depth bounds — Pacing-Engine bricht bei BPM<=0
    # mit DivisionByZero. 250 BPM ist musikalisch oberes Maximum (Speedcore).
    expected_bpm: float = Field(120.0, gt=0.0, le=400.0)
    trigger_settings: Optional[TriggerSettingsSchema] = None
    use_motion_matching: bool = False
    use_semantic_matching: bool = False
    use_structure_awareness: bool = False
    # Audit E1: Tonart-Matching (Camelot-Wheel) — bevorzugt Cuts mit harmonisch
    # kompatiblen Tonarten (relative_minor + perfect_fifth). Backwards-compat:
    # default False → bestehende Calls bleiben unveraendert.
    use_key_matching: bool = False
    # L-K5: Stem-basiertes Pacing — wenn True und audio_clip stems_paths hat
    # (drums/bass via Demucs), wird AdvancedPacingEngine.generate_cut_list_with_stems
    # aufgerufen. Default False -> bestehende Calls bleiben unveraendert.
    use_stem_pacing: bool = False
    # S-H2 (Audit V2): duration_limit cap muss positiv sein, sonst Render-Pfad NoOp.
    duration_limit: Optional[float] = Field(None, gt=0.0)
    canvas_path: Optional[str] = Field(None, max_length=32767)
    min_cut_interval: float = Field(0.5, ge=0.0)
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


class ModeDegradationSchema(BaseModel):
    """Ein angeforderter Pacing-Modus, der mangels Datengrundlage nicht wirkte.

    FR-362: ein Modus darf nicht still auf Defaultwerte zurückfallen und dabei
    als aktiv gemeldet werden. Wenn kein einziger Clip bewertbar ist, wirkt der
    Modus als uniformer Faktor — also gar nicht. Das gehört sichtbar gemacht.
    """
    mode: str
    reason: str
    scored_clips: int = 0
    total_clips: int = 0


class CutListResponse(BaseModel):
    """Response: Generierte Cut-Liste."""
    cuts: list[CutListEntrySchema] = []
    total_duration: float = 0.0
    cut_count: int = 0
    average_cut_duration: float = 0.0
    # Leer = jeder angeforderte Modus hatte eine echte Datengrundlage.
    degradations: list[ModeDegradationSchema] = []


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
    # Plan Phase 5: brain confidence + DB cut id (when use_brain=true)
    brain_confidence: float = 0.0
    cut_id: Optional[int] = None
    feature_confidence: float = 0.0
    semantic_status: str = "unavailable"
    semantic_reason: Optional[str] = None
    trigger_provenance: dict[str, Any] = Field(default_factory=dict)
    brain_axis_status: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Response: Aktuelle Timeline."""
    entries: list[TimelineEntrySchema] = []
    total_duration: float = 0.0
    audio_path: Optional[str] = None


class TimelineUpdateRequest(BaseModel):
    """Request: Timeline manuell aktualisieren."""
    entries: list[TimelineEntrySchema] = Field(max_length=TIMELINE_UPDATE_MAX_ENTRIES)


class PreviewResponse(BaseModel):
    """Response: Preview-Datei."""
    preview_path: str
    duration: float
    resolution: str = "640x360"
