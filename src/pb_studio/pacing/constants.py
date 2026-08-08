"""
Pacing Constants
================

Zentrale Konfigurationswerte für das Pacing-System.
Alle Magic Numbers an einem Ort statt verstreut im Code.

Portiert von NVIDIA-Version, angepasst für AMD DirectML.
"""

# =============================================================================
# Adaptive Segment-Fusion (SmartDirector)
# =============================================================================
HARD_CUT_THRESHOLD = 0.7       # Ab dieser Strength MUSS geschnitten werden
MIN_DURATION_DROP = 0.3         # Min-Duration bei erkanntem Drop (sehr kurz!)
MIN_DURATION_BUILDUP = 2.0     # Min-Duration bei Build-up (Spannung halten)
MIN_DURATION_BREAKDOWN = 3.5   # Min-Duration bei Breakdown (ruhig, lang)
DEFAULT_MIN_DURATION = 1.5     # Fallback wenn keine Struktur erkannt

# =============================================================================
# Struktur-basierte Min-Durations (Song-Sektionen)
# =============================================================================
STRUCTURE_MIN_DURATIONS = {
    "intro": 3.0,
    "verse": 2.0,
    "chorus": 1.0,
    "drop": 0.3,
    "breakdown": 3.5,
    "buildup": 2.0,
    "bridge": 2.5,
    "outro": 3.0,
    # DJ-Mix Phasen
    "high_energy": 0.5,
    "rising": 1.0,
    "falling": 2.0,
    "low_energy": 3.0,
    "plateau": 2.0,
}

# =============================================================================
# Motion Preferences (Struktur -> gewünschte Bewegung)
# =============================================================================
MOTION_PREFERENCES = {
    "intro": 0.3,
    "verse": 0.4,
    "chorus": 0.7,
    "drop": 0.9,
    "breakdown": 0.2,
    "buildup": 0.5,
    "bridge": 0.4,
    "outro": 0.3,
    # DJ-Mix Phasen
    "high_energy": 0.85,
    "rising": 0.6,
    "falling": 0.35,
    "low_energy": 0.2,
    "plateau": 0.5,
}

# =============================================================================
# Semantic Matcher
# =============================================================================
SEMANTIC_CANDIDATES_COUNT = 60   # Suchradius für Clip-Kandidaten
VARIETY_HISTORY_SIZE = 15        # Wie viele letzte Videos merken (Variety)
MAX_SCENE_HISTORY = 5000         # Max Scene-IDs im RAM (verhindert Explosion)
MAX_SCENE_REUSES = 3             # Wie oft eine Szene wiederverwendet werden darf
SCENE_RECYCLE_INTERVAL = 200     # Nach X Segmenten: Scene-Sperren resetten

# Visual Similarity Thresholds
VISUAL_SIMILARITY_THRESHOLD = 0.85  # Ab diesem Wert gilt Clip als "zu ähnlich"
VISUAL_PENALTY_FACTOR = 0.3         # Strafgewicht für visuelle Ähnlichkeit

# Continuity (Roter Faden)
CONTINUITY_WEIGHT = 0.35        # 35% Einfluss des roten Fadens

# =============================================================================
# Anchor System (Few-Shot Learning)
# =============================================================================
ANCHOR_MIN_SIMILARITY = 0.5     # Minimale Similarity für Anchor-Match
ANCHOR_BLEND_HIGH = 0.7         # Anchor-Weight bei hoher Similarity
ANCHOR_BLEND_NORMAL = 0.5       # Anchor-Weight bei normaler Similarity
ANCHOR_HIGH_SIMILARITY_THRESHOLD = 0.8  # Ab hier gilt "hohe Similarity"

# =============================================================================
# Embedding Dimensions (AMD SigLIP ONNX)
# =============================================================================
EMBEDDING_DIM = 1152             # SigLIP so400m Embedding-Dimension
AUDIO_FEATURE_DIM = 20           # 8 band means + 8 band vars + 3 energy + 1 beat
EMBEDDING_CACHE_SIZE = 150       # Max gecachte Mood-Embeddings

# =============================================================================
# Clip-Selector (Blacklist / Roter Faden)
# =============================================================================
BLACKLIST_PERCENTAGE = 0.8       # NEU: Bis zu 80% der Clips können geblockt sein
MAX_BLACKLIST_SIZE = 20          # NEU: Maximale Blacklist-Größe (absolute Obergrenze)
SMALL_LIBRARY_THRESHOLD = 8
SMALL_LIBRARY_MAX_BLACKLIST_PERCENTAGE = 0.5
MIN_SELECTABLE_CLIPS = 3

# =============================================================================
# Motion Analysis
# =============================================================================
MOTION_TOLERANCE = 0.2           # Toleranz beim Motion-Matching
