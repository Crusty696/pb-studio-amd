"""Audio-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AudioImportRequest(BaseModel):
    """Request: Audio-Datei importieren."""
    path: str = Field(..., description="Absoluter Pfad zur Audiodatei")


class AudioClipInfo(BaseModel):
    """Response: Importierter Audio-Clip."""
    id: int
    name: str
    path: str
    duration_seconds: float
    sample_rate: int = 44100
    channels: int = 2
    format: str = "mp3"


class AudioAnalyzeRequest(BaseModel):
    """Request: Audio analysieren."""
    clip_id: int
    detect_beats: bool = True
    detect_structure: bool = True
    spectral_analysis: bool = True
    # CLEANUP-001: waveform-Feld entfernt — Waveform nur via GET /audio/waveform/{id}


class BeatData(BaseModel):
    """Ein einzelner Beat."""
    time: float = Field(..., description="Beat-Zeitpunkt in Sekunden")
    strength: float = Field(1.0, ge=0.0, le=1.0, description="Beat-Stärke")
    beat_type: str = "beat"  # beat, downbeat, bar


class AudioAnalysisResult(BaseModel):
    """Response: Audio-Analyse Ergebnis."""
    clip_id: int
    duration_seconds: float
    bpm: float = 0.0
    beat_count: int = 0
    beats: list[BeatData] = []
    key: Optional[str] = None
    energy_curve: list[float] = []
    structure_segments: list["StructureSegment"] = []
    spectral_data: Optional["SpectralData"] = None


class WaveformRequest(BaseModel):
    """Request: Waveform-Daten."""
    bands: int = Field(3, ge=1, le=8, description="Anzahl Frequenzbänder")


class WaveformData(BaseModel):
    """Response: Waveform-Daten."""
    clip_id: int
    sample_rate: int
    bands: list[list[float]] = []  # Pro Band eine Liste von Amplitude-Werten
    duration_seconds: float = 0.0


class StemModel(str, Enum):
    """Verfügbare Stem-Separation Modelle (AMD UVR-MDX-NET)."""
    INST_HQ_3 = "UVR-MDX-NET-Inst_HQ_3.onnx"
    INST_HQ_4 = "UVR-MDX-NET-Inst_HQ_4.onnx"
    VOCALFT = "UVR-MDX-NET-Voc_FT.onnx"


class StemSeparateRequest(BaseModel):
    """Request: Stem-Separation."""
    clip_id: int
    model: StemModel = StemModel.INST_HQ_3


class StemResult(BaseModel):
    """Response: Stem-Separation Ergebnis."""
    clip_id: int
    vocals_path: Optional[str] = None
    instrumental_path: Optional[str] = None
    drums_path: Optional[str] = None
    bass_path: Optional[str] = None
    other_path: Optional[str] = None
    model_used: str = ""


class StructureSegment(BaseModel):
    """Ein Struktur-Segment (Verse, Chorus, Drop, etc.)."""
    start_time: float
    end_time: float
    label: str
    confidence: float = 0.0


class SpectralData(BaseModel):
    """Response: Spektral-Analyse Daten."""
    clip_id: int
    bands: dict[str, list[float]] = {}  # Band-Name → Amplitude-Werte
    frequency_ranges: dict[str, tuple[float, float]] = {}


# Forward-References auflösen (StructureSegment/SpectralData nach AudioAnalysisResult definiert)
AudioAnalysisResult.model_rebuild()
