"""6 Kontext-Slots + 5 Backoff-Keys (Plan Section 5).

Slots: section / subtrack_pos / energy_level / mood / motion_class / pace_class
Backoff levels (most-specific last):
  Level 0: ""
  Level 1: section
  Level 2: section|mood
  Level 3: section|mood|motion
  Level 4: section|mood|motion|energy
  Level 5: section|mood|motion|energy|pace|subpos
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class CutContext:
    """Quantised context for a single cut (used as backoff key prefix)."""
    section_type: str = "transition"      # intro|verse|build|drop|break|outro|transition
    subtrack_position: str = "middle"     # start|middle|end
    audio_energy_level: str = "medium"    # low|medium|high
    audio_mood: str = "neutral"           # dark|neutral|uplifting
    video_motion_class: str = "medium"    # low|medium|high|extreme
    video_pace_class: str = "medium"      # slow|medium|fast

    @property
    def context_keys(self) -> list[str]:
        return [
            "",
            f"section={self.section_type}",
            f"section={self.section_type}|mood={self.audio_mood}",
            f"section={self.section_type}|mood={self.audio_mood}|motion={self.video_motion_class}",
            f"section={self.section_type}|mood={self.audio_mood}|motion={self.video_motion_class}|energy={self.audio_energy_level}",
            f"section={self.section_type}|mood={self.audio_mood}|motion={self.video_motion_class}|energy={self.audio_energy_level}|pace={self.video_pace_class}|subpos={self.subtrack_position}",
        ]


_ENERGY_BUCKETS = ("low", "medium", "high")
_MOTION_BUCKETS = ("low", "medium", "high", "extreme")
_PACE_BUCKETS = ("slow", "medium", "fast")


class ContextResolver:
    """Builds CutContext from raw audio/video features at a cut time."""

    def resolve(
        self,
        *,
        section_type: str = "transition",
        cut_time_sec: float,
        subtrack_start_sec: float,
        subtrack_end_sec: float,
        audio_energy: float,
        audio_mood_tags: list[str],
        video_motion_score: float,
        video_pace_class_value: float,
        energy_curve_full: Optional[list[float] | np.ndarray] = None,
        motion_curve_full: Optional[list[float] | np.ndarray] = None,
    ) -> CutContext:
        sub_pos = self._subtrack_position(
            cut_time_sec, subtrack_start_sec, subtrack_end_sec
        )
        e_level = self._tertile(
            audio_energy, energy_curve_full, _ENERGY_BUCKETS
        )
        mood = self._mood_label(audio_mood_tags)
        motion = self._tertile(
            video_motion_score, motion_curve_full, _MOTION_BUCKETS
        )
        pace = self._pace_label(video_pace_class_value)

        return CutContext(
            section_type=section_type,
            subtrack_position=sub_pos,
            audio_energy_level=e_level,
            audio_mood=mood,
            video_motion_class=motion,
            video_pace_class=pace,
        )

    @staticmethod
    def _subtrack_position(
        cut_t: float, start: float, end: float
    ) -> str:
        if end <= start:
            return "middle"
        rel = (cut_t - start) / (end - start)
        if rel < 0.25:
            return "start"
        if rel >= 0.75:
            return "end"
        return "middle"

    @staticmethod
    def _tertile(
        value: float,
        curve: Optional[list[float] | np.ndarray],
        buckets: tuple[str, ...],
    ) -> str:
        # Use 33./66. percentile of curve when available; otherwise fixed thresholds.
        if curve is not None:
            arr = np.asarray(list(curve), dtype=np.float32)
            arr = arr[arr >= 0]
            if arr.size >= 3:
                p33 = float(np.percentile(arr, 33))
                p66 = float(np.percentile(arr, 66))
                cuts = [p33, p66]
            else:
                cuts = [0.33, 0.66]
        else:
            cuts = [0.33, 0.66]

        if len(buckets) == 4:  # motion has 4 buckets
            p25 = cuts[0] * 0.5
            for limit, label in zip(
                (p25, cuts[0], cuts[1]),
                buckets[:-1],
            ):
                if value < limit:
                    return label
            return buckets[-1]

        for limit, label in zip(cuts, buckets[:-1]):
            if value < limit:
                return label
        return buckets[-1]

    @staticmethod
    def _mood_label(tags: list[str]) -> str:
        if not tags:
            return "neutral"
        s = {t.lower() for t in tags}
        if s & {"dark", "cold", "moody", "tense"}:
            return "dark"
        if s & {"uplifting", "warm", "happy", "energetic", "euphoric"}:
            return "uplifting"
        return "neutral"

    @staticmethod
    def _pace_label(value: float) -> str:
        if value < 0.33:
            return "slow"
        if value < 0.66:
            return "medium"
        return "fast"
