"""17 Bridge-Achsen Berechnungen (Plan Decision #10 + Section 5).

10 Audio-Achsen: aus TriggerSettings (beat/onset/kick/snare/hihat/energy/...)
 7 Video-Achsen: motion_match, scene_cut, brightness_match, color_temp_match,
                 pace_match, semantic_match, mood_match

Eingabe pro Achse: (cut_context, candidate_features) -> normalisierter Wert in [0,1].
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Audio axes - taken straight from candidate-trigger-strength normalised
AUDIO_AXES: tuple[str, ...] = (
    "beat_weight",
    "onset_weight",
    "kick_weight",
    "snare_weight",
    "hihat_weight",
    "energy_weight",
    "energy_threshold",
    "onset_sensitivity",
    "min_clip_length",
    "max_clip_length",
)

# Video axes - derived from audio<->video correlation
VIDEO_AXES: tuple[str, ...] = (
    "motion_match_weight",
    "scene_cut_weight",
    "brightness_match_weight",
    "color_temp_match_weight",
    "pace_match_weight",
    "semantic_match_weight",
    "mood_match_weight",
)

BRIDGE_AXES: tuple[str, ...] = AUDIO_AXES + VIDEO_AXES


@dataclass
class CandidateFeatures:
    """Feature snapshot for one (audio cut, candidate clip) pair."""

    # Audio side
    trigger_type: str = ""
    trigger_strength: float = 0.0
    audio_energy: float = 0.0
    audio_centroid: float = 0.0
    audio_embedding: Optional[np.ndarray] = None

    # Video side
    motion_score: float = 0.0
    scene_distance_sec: float = 1.0
    brightness: float = 0.5
    saturation: float = 0.5
    color_temp: float = 0.0
    pace_class_score: float = 0.5
    video_embedding: Optional[np.ndarray] = None
    mood_tags: list[str] = field(default_factory=list)
    audio_mood_tags: list[str] = field(default_factory=list)

    cut_duration_sec: float = 1.0


class BridgeDimensions:
    """Computes 17 bridge values for a candidate."""

    def compute_all(self, features: CandidateFeatures) -> dict[str, float]:
        out: dict[str, float] = {}
        for axis in AUDIO_AXES:
            out[axis] = self._audio_axis(axis, features)
        for axis in VIDEO_AXES:
            out[axis] = self._video_axis(axis, features)
        return out

    def _audio_axis(self, axis: str, f: CandidateFeatures) -> float:
        type_match = {
            "beat_weight": f.trigger_type == "beat",
            "onset_weight": f.trigger_type == "onset",
            "kick_weight": f.trigger_type == "kick",
            "snare_weight": f.trigger_type == "snare",
            "hihat_weight": f.trigger_type == "hihat",
            "energy_weight": f.trigger_type == "energy",
        }
        if axis in type_match:
            return _clip01(f.trigger_strength) if type_match[axis] else 0.0

        if axis == "energy_threshold":
            return _clip01(f.audio_energy)
        if axis == "onset_sensitivity":
            return _clip01(f.audio_centroid)
        if axis == "min_clip_length":
            return _clip01(1.0 - min(1.0, f.cut_duration_sec / 4.0))
        if axis == "max_clip_length":
            return _clip01(min(1.0, f.cut_duration_sec / 8.0))
        return 0.0

    def _video_axis(self, axis: str, f: CandidateFeatures) -> float:
        if axis == "motion_match_weight":
            return 1.0 - abs(_clip01(f.motion_score) - _clip01(f.audio_energy))

        if axis == "scene_cut_weight":
            return math.exp(-abs(f.scene_distance_sec) / 0.5)

        if axis == "brightness_match_weight":
            return 1.0 - abs(_clip01(f.brightness) - _clip01(f.audio_centroid))

        if axis == "color_temp_match_weight":
            mood = _audio_mood_score(f.audio_mood_tags)
            return 1.0 - 0.5 * abs(mood - f.color_temp)

        if axis == "pace_match_weight":
            return _clip01(f.pace_class_score)

        if axis == "semantic_match_weight":
            if f.audio_embedding is None or f.video_embedding is None:
                return 0.5
            return _cosine_zero_one(f.audio_embedding, f.video_embedding)

        if axis == "mood_match_weight":
            if not f.mood_tags or not f.audio_mood_tags:
                return 0.5
            overlap = len(set(f.mood_tags) & set(f.audio_mood_tags))
            denom = max(len(set(f.audio_mood_tags) | set(f.mood_tags)), 1)
            return overlap / denom

        return 0.5


def _clip01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(x)))


def _audio_mood_score(tags: list[str]) -> float:
    """Map mood tags to scalar in [-1, 1] (cool..warm)."""
    if not tags:
        return 0.0
    score = 0.0
    n = 0
    for t in tags:
        tl = t.lower()
        if tl in ("dark", "cold", "cool", "moody"):
            score -= 1.0
            n += 1
        elif tl in ("uplifting", "warm", "happy", "energetic"):
            score += 1.0
            n += 1
    if n == 0:
        return 0.0
    return score / n


def _cosine_zero_one(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    if a.size == 0 or b.size == 0:
        return 0.5
    if a.size != b.size:
        n = min(a.size, b.size)
        a = a[:n]
        b = b[:n]
    # R-Brain-09: NaN/Inf-Guard auf Inputs
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    b = np.nan_to_num(b, nan=0.0, posinf=0.0, neginf=0.0)
    na = np.linalg.norm(a) + 1e-9
    nb = np.linalg.norm(b) + 1e-9
    cos = float(np.dot(a, b) / (na * nb))
    if cos != cos:  # NaN-Guard nach Berechnung
        return 0.5
    res = (cos + 1.0) / 2.0  # [-1,1] -> [0,1]
    return max(0.0, min(1.0, res))
