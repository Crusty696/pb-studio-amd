"""Brain module — online learning over 17 bridge axes (Plan Phase 3+)."""

from .bridge_dimensions import BRIDGE_AXES, BridgeDimensions
from .cold_start import COLD_START_DEFAULTS
from .context_resolver import ContextResolver, CutContext
from .cross_modal_projector import (
    CrossModalProjector,
    get_default_projector,
    reset_default_projector,
)
from .feedback_logger import FeedbackLogger, RATING_MAP
from .scorer import BrainScorer, ScoredCandidate
from .weight_store import WeightStore, MIN_CONFIDENT_SAMPLES

__all__ = [
    "BRIDGE_AXES",
    "BridgeDimensions",
    "COLD_START_DEFAULTS",
    "ContextResolver",
    "CrossModalProjector",
    "CutContext",
    "FeedbackLogger",
    "RATING_MAP",
    "BrainScorer",
    "ScoredCandidate",
    "WeightStore",
    "MIN_CONFIDENT_SAMPLES",
    "get_default_projector",
    "reset_default_projector",
]
