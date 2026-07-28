"""Cold-start defaults für 17 Brücken-Achsen (Plan Decision #9 + Section 5).

Audio-Achsen aus TriggerSettings-Defaults, Video-Achsen neutrale Mitte.
Sobald für (axis, context) >=10 Samples vorliegen, ersetzt Posterior diese.
"""

from __future__ import annotations

COLD_START_DEFAULTS: dict[str, float] = {
    # Audio (10) — TriggerSettings dataclass defaults
    "beat_weight": 1.0,
    "onset_weight": 0.5,
    "kick_weight": 1.2,
    "snare_weight": 1.0,
    "hihat_weight": 0.3,
    "energy_weight": 0.8,
    "energy_threshold": 0.6,
    "onset_sensitivity": 0.5,
    # AUDIT-FIX #6: Diese Achsen fliessen als Gewicht (bridge_value * weight) in den Score ein.
    # Roh-Sekunden (bis 8.0) sprengten [0,1] und dominierten das Cold-Start-Ranking.
    # Neutraler In-Range-Wert wie die Video-Achsen.
    "min_clip_length": 0.5,
    "max_clip_length": 0.5,
    # Video (7) — neutral midpoint
    "motion_match_weight": 0.5,
    "scene_cut_weight": 0.5,
    "brightness_match_weight": 0.5,
    "color_temp_match_weight": 0.5,
    "pace_match_weight": 0.5,
    "semantic_match_weight": 0.5,
    "mood_match_weight": 0.5,
}
