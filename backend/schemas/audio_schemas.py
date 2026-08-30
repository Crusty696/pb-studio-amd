"""Audio-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from enum import Enum


class AudioImportRequest(BaseModel):
    """Request: Audio-Datei importieren."""
    path: str = Field(..., description="Absoluter Pfad zur Audiodatei")


class AudioClipInfo(BaseModel):
    """Response: Importierter Audio-Clip inkl. vorhandenem Analyse-Status."""
    id: int
    name: str
    path: str
    duration_seconds: float
    sample_rate: int = 44100
    channels: int = 2
    format: str = "mp3"
    bpm: float = 0.0
    key: Optional[str] = None
    beat_count: int = 0
    is_analyzed: bool = False
    audio_hash: Optional[str] = None
    has_audio_embedding: bool = False
    analysis_status: str = "unavailable"
    stage_status: dict[str, str] = Field(default_factory=dict)
    stage_errors: dict[str, str] = Field(default_factory=dict)
    # L-N4: Stem-Separation Outputs — gesetzt nach POST /audio/stems/separate.
    # Dict {vocals|instrumental|drums|bass|other -> file-path}. UI rendert
    # STEMS-Badge wenn nicht None und nicht-leer.
    stems_paths: Optional[Dict[str, str]] = None


class SubtrackSegment(BaseModel):
    """Ein erkannter Sub-Track innerhalb eines DJ-Mixes."""
    start_time: float
    end_time: float
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    sub_bpm: Optional[float] = None
    sub_key: Optional[str] = None


class AudioAnalyzeRequest(BaseModel):
    """Request: Audio analysieren."""
    clip_id: int
    detect_beats: bool = True
    detect_structure: bool = True
    spectral_analysis: bool = True
    detect_key: bool = True
    force: bool = False
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
    subtrack_segments: list[SubtrackSegment] = []
    tempo_curve: list[float] = []
    # Audit-Fix 2026-07-10: Onset/Drum-Trigger-Kandidaten fuer den Pacing-Cache-Pfad
    # (ersetzt den toten core.session_manager-Import in advanced_pacing_engine.py).
    onset_times: list[float] = []
    kick_times: list[float] = []
    snare_times: list[float] = []
    hihat_times: list[float] = []
    analysis_status: str = "completed"
    stage_status: dict[str, str] = Field(default_factory=dict)
    stage_errors: dict[str, str] = Field(default_factory=dict)
    chunk_evidence: dict[str, Any] = Field(default_factory=dict)
    downbeats: list[float] = Field(default_factory=list)
    downbeat_provenance: dict[str, Any] = Field(default_factory=dict)
    # C-3: Ehrlichkeitsmechanik fuer das Beat-Raster, analog zu
    # downbeat_provenance. Haelt fest, WIE die BPM zustande kam
    # (`method`, `window_median_bpm`), wie gleichmaessig die Beat-Abstaende
    # sind (`interval_regularity`, `regular`) und ob die unabhaengige
    # Gegenprobe gegen die Kick-Onsets bestanden wurde (`kick_alignment`,
    # `kick_cross_check`). `status`: plausible | suspect | unavailable.
    beat_grid_provenance: dict[str, Any] = Field(default_factory=dict)


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
    """Verfügbare Stem-Separation Modelle (AMD UVR-MDX-NET & Demucs)."""
    INST_HQ_3 = "UVR-MDX-NET-Inst_HQ_3.onnx"
    INST_HQ_4 = "UVR-MDX-NET-Inst_HQ_4.onnx"
    VOCALFT = "UVR-MDX-NET-Voc_FT.onnx"
    HTDEMUCS = "htdemucs.yaml"  # 4-Spur Demucs (Drums, Bass, Vocals, Other)



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
    energy_score: float = 0.0


class SpectralData(BaseModel):
    """Response: Spektral-Analyse Daten."""
    clip_id: int
    times: list[float] = []
    bands: dict[str, list[float]] = {}  # Band-Name → Amplitude-Werte
    centroids: list[float] = []
    frequency_ranges: dict[str, list[float]] = {}
    # L-AUDIO-4: SpectralAnalyzer-Aggregate + Drop/Buildup/Breakdown-Events
    # mit-persistieren (waren zuvor im Mapping verworfen).
    band_means: dict[str, float] = {}
    band_variances: dict[str, float] = {}
    events: list[dict] = []


# Forward-References auflösen (StructureSegment/SpectralData nach AudioAnalysisResult definiert)
AudioAnalysisResult.model_rebuild()
