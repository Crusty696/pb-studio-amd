"""
PB Studio Pacing Engine - Rhythm-based Video Editing

This module provides intelligent video pacing algorithms that synchronize
cuts and transitions with audio beats and energy curves.

Key Components:
- ClipSelector: Vector-based clip selection using FAISS embeddings
- AdvancedPacingEngine: Musical intelligence for cut timing and sequencing
- PacingConfig: Configuration dataclass for pacing parameters
- SemanticMatcher: Intelligente Clip-Auswahl via Embeddings
- MoodGenerator: Energy-basierte Mood-Text-Generierung
- MotionPreferenceCalculator: Motion-Präferenz basierend auf Struktur/Spektral
- AnchorManager: Few-Shot Learning via User-definierte Audio-Video-Anchors
- ExportHandler: Timeline Import/Export (JSON, FFmpeg, DaVinci)
"""

from .clip_selector import ClipSelector
from .advanced_pacing_engine import AdvancedPacingEngine, PacingConfig, CutPoint
from .pacing_models import (
    PacingCut, CutListEntry, SelectedClip,
    TriggerSettings, SongSection, TimelineEntry
)
from .timeline_models import TimelineClip
from .constants import (
    HARD_CUT_THRESHOLD, SEMANTIC_CANDIDATES_COUNT,
    VARIETY_HISTORY_SIZE, EMBEDDING_DIM
)

__all__ = [
    # Bestehend
    "ClipSelector",
    "AdvancedPacingEngine",
    "PacingConfig",
    "CutPoint",
    # Neu portiert
    "PacingCut",
    "CutListEntry",
    "SelectedClip",
    "TriggerSettings",
    "SongSection",
    "TimelineEntry",
    "TimelineClip",
    "HARD_CUT_THRESHOLD",
    "SEMANTIC_CANDIDATES_COUNT",
    "VARIETY_HISTORY_SIZE",
    "EMBEDDING_DIM",
]
