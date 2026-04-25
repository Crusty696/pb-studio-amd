"""
Timeline Models
===============

Datenklassen für Timeline-Clips.
Portiert von NVIDIA-Version.

Änderungen v2 (AMD Alignment):
- TimelineClip: clip_name, trigger_type, trigger_strength ergänzt (NV-Kompatibilität)
- to_dict(): neue Felder + file_path Alias für Rückwärtskompatibilität
"""

from dataclasses import dataclass


@dataclass
class TimelineClip:
    """Ein einzelner Clip in der Timeline."""
    video_path: str
    start_time_in_song: float
    duration: float
    video_in_point: float
    video_out_point: float
    score: float = 0.0
    caption: str = ""
    motion_score: float = 0.5
    # NV-kompatible Felder:
    clip_name: str = ""             # NEU: Dateiname/Clip-Name für Anzeige
    trigger_type: str = "beat"      # NEU: Welcher Trigger hat diesen Cut ausgelöst
    trigger_strength: float = 0.5   # NEU: Stärke des Triggers (0.0-1.0)

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "file_path": self.video_path,       # Rückwärtskompatibilität
            "start_time_in_song": self.start_time_in_song,
            "duration": self.duration,
            "video_in_point": self.video_in_point,
            "video_out_point": self.video_out_point,
            "score": self.score,
            "caption": self.caption,
            "motion_score": self.motion_score,
            "clip_name": self.clip_name,
            "trigger_type": self.trigger_type,
            "trigger_strength": self.trigger_strength,
        }
