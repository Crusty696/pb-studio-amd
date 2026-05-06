"""
Pacing Models
=============

Datenklassen für das Pacing-System.
Portiert von NVIDIA-Version, angepasst für AMD DirectML.

Änderungen v2 (AMD Alignment):
- CutListEntry.clip_id: int -> str (NV-Kompatibilität)
- SelectedClip.clip_id: int -> str (NV-Kompatibilität)
- SelectedClip.get_motion_at_time(): Signatur auf (t, duration) normalisiert
- TriggerSettings: Fehlende Felder ergänzt (energy_threshold, min/max_cut_interval, etc.)
- TimelineEntry: Fehlende Felder ergänzt (clip_id, cut_reason, metadata)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class PacingCut:
    """Ein einzelner Schnittpunkt in der Audio-Analyse."""
    time: float
    trigger_type: str = "beat"      # beat, onset, energy, kick, snare, hihat, downbeat
    strength: float = 0.5           # 0.0 (weich) bis 1.0 (hart)
    segment_type: Optional[str] = None  # normal, drop, buildup, breakdown, intro, verse, etc.

    def __post_init__(self):
        # Stärke auf gültigen Bereich begrenzen
        self.strength = max(0.0, min(1.0, self.strength))


@dataclass
class CutListEntry:
    """Ein Eintrag in der finalen Cut-Liste."""
    clip_id: str          # NV-kompatibel: str (nicht int)
    start_time: float
    end_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectedClip:
    """Ein ausgewählter Video-Clip mit Score und Motion-Profil."""
    clip_id: str          # NV-kompatibel: str (nicht int)
    clip_path: str
    score: float
    motion_score: float = 0.5
    motion_profile: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None  # Plan Phase 4: brain_scores etc.

    def get_motion_at_time(self, t: float, duration: float = 0.0) -> float:
        """
        Gibt den Motion-Score an einem bestimmten Zeitpunkt zurück.

        Args:
            t: Zeitpunkt in Sekunden (oder ms bei altem NV-Code)
            duration: Clip-Gesamtdauer (0.0 = t wird direkt als normalisierter Index interpretiert)
        """
        if not self.motion_profile:
            return self.motion_score

        if duration > 0:
            # Normaler Modus: t ist Sekunden, duration ist Gesamtdauer
            idx = int((t / duration) * (len(self.motion_profile) - 1))
        else:
            # Legacy-Modus (NV-Kompatibilität): t ist direkt der normalisierte Index (ms)
            idx = int(t / 1000.0 * (len(self.motion_profile) - 1)) if t > 1.0 else int(t * (len(self.motion_profile) - 1))

        idx = max(0, min(idx, len(self.motion_profile) - 1))
        return self.motion_profile[idx]


@dataclass
class TriggerSettings:
    """Gewichtung der verschiedenen Audio-Trigger."""
    # --- Trigger-Gewichte ---
    beat_weight: float = 1.0
    onset_weight: float = 0.5
    kick_weight: float = 1.2          # NV-Default: 1.2 (AMD hatte 0.8)
    snare_weight: float = 1.0         # NV-Default: 1.0 (AMD hatte 0.6)
    hihat_weight: float = 0.3
    energy_weight: float = 0.8        # NV-Default: 0.8 (AMD hatte 0.7)

    # --- Clip-Längen ---
    min_clip_length: float = 1.0
    max_clip_length: float = 8.0      # NEU: NV hatte dieses Feld
    clip_length_variation: float = 0.0  # NEU: 0.0 = kein Jitter, 0.3 = ±30% Variation

    # --- Cut-Intervalle ---
    min_cut_interval: float = 0.5     # NEU: Minimaler Abstand zwischen Schnitten
    max_cut_interval: float = 10.0    # NEU: Maximaler Abstand (wird durch _enforce_clip_lengths genutzt)

    # --- Energy-Threshold ---
    energy_threshold: float = 0.6     # NEU: Ab diesem Wert gilt ein Peak als Energie-Trigger

    # --- Beat-Modus ---
    beat_trigger_mode: str = "all"    # NEU: "all", "downbeat_only", "strong_only"

    # --- Onset-Sensitivität ---
    onset_sensitivity: float = 0.5    # NEU: 0.0=wenig sensitiv, 1.0=sehr sensitiv

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerSettings":
        return cls(
            beat_weight=float(data.get("beat_weight", 1.0)),
            onset_weight=float(data.get("onset_weight", 0.5)),
            kick_weight=float(data.get("kick_weight", 1.2)),
            snare_weight=float(data.get("snare_weight", 1.0)),
            hihat_weight=float(data.get("hihat_weight", 0.3)),
            energy_weight=float(data.get("energy_weight", 0.8)),
            min_clip_length=float(data.get("min_clip_length", 1.0)),
            max_clip_length=float(data.get("max_clip_length", 8.0)),
            clip_length_variation=float(data.get("clip_length_variation", 0.0)),
            min_cut_interval=float(data.get("min_cut_interval", 0.5)),
            max_cut_interval=float(data.get("max_cut_interval", 10.0)),
            energy_threshold=float(data.get("energy_threshold", 0.6)),
            beat_trigger_mode=str(data.get("beat_trigger_mode", "all")),
            onset_sensitivity=float(data.get("onset_sensitivity", 0.5)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beat_weight": self.beat_weight,
            "onset_weight": self.onset_weight,
            "kick_weight": self.kick_weight,
            "snare_weight": self.snare_weight,
            "hihat_weight": self.hihat_weight,
            "energy_weight": self.energy_weight,
            "min_clip_length": self.min_clip_length,
            "max_clip_length": self.max_clip_length,
            "clip_length_variation": self.clip_length_variation,
            "min_cut_interval": self.min_cut_interval,
            "max_cut_interval": self.max_cut_interval,
            "energy_threshold": self.energy_threshold,
            "beat_trigger_mode": self.beat_trigger_mode,
            "onset_sensitivity": self.onset_sensitivity,
        }


@dataclass
class SongSection:
    """Ein Abschnitt im Song (Intro, Verse, Drop, etc.)."""
    name: str
    start_time: float
    end_time: float
    energy_level: float = 0.5   # 0.0 (ruhig) bis 1.0 (energetisch)

    @property
    def duration(self) -> float:
        """Dauer des Abschnitts in Sekunden."""
        return self.end_time - self.start_time


@dataclass
class TimelineEntry:
    """Ein Eintrag in der generierten Video-Timeline."""
    video_path: str
    start_time_in_song: float
    duration: float
    video_in_point: float = 0.0
    video_out_point: float = 0.0
    # NV-kompatible Felder:
    clip_id: str = ""               # NEU: Clip-ID für Rückverfolgung
    cut_reason: str = ""            # NEU: Warum dieser Clip gewählt wurde
    metadata: Dict[str, Any] = field(default_factory=dict)  # NEU: Zusatzdaten
