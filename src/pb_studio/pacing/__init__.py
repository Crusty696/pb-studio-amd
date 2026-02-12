"""
PB Studio Pacing Engine - Rhythm-based Video Editing

This module provides intelligent video pacing algorithms that synchronize
cuts and transitions with audio beats and energy curves.

Key Components:
- ClipSelector: Vector-based clip selection using FAISS embeddings
- AdvancedPacingEngine: Musical intelligence for cut timing and sequencing
- PacingConfig: Configuration dataclass for pacing parameters
"""

from .clip_selector import ClipSelector
from .advanced_pacing_engine import AdvancedPacingEngine, PacingConfig, CutPoint

__all__ = [
    "ClipSelector",
    "AdvancedPacingEngine",
    "PacingConfig",
    "CutPoint"
]
