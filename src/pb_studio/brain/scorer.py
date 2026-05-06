"""BrainScorer — kombiniert 17 Brücken-Werte × Posterior-Gewichte (Plan Phase 3+4).

Eingabe pro Kandidat: BridgeDimensions.compute_all -> dict[axis -> 0..1]
Lookup je Achse: WeightStore.get_posterior_mean(axis, context_keys)
Final-Score: mean(bridge_value * weight) über alle 17 Achsen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bridge_dimensions import BRIDGE_AXES


@dataclass
class ScoredCandidate:
    """Result entry for a scored candidate."""
    candidate: Any
    final_score: float
    brain_scores: dict[str, float] = field(default_factory=dict)


class BrainScorer:
    def __init__(self, *, bridge, weight_store):
        self.bridge = bridge
        self.weights = weight_store

    def score(self, *, candidate: Any, features, context_keys: list[str]) -> ScoredCandidate:
        bridge_values = self.bridge.compute_all(features)
        sub_scores: dict[str, float] = {}
        for axis in BRIDGE_AXES:
            bv = float(bridge_values.get(axis, 0.0))
            w = float(self.weights.get_posterior_mean(axis, context_keys))
            sub_scores[axis] = bv * w
        if sub_scores:
            final = sum(sub_scores.values()) / len(sub_scores)
        else:
            final = 0.0
        return ScoredCandidate(
            candidate=candidate,
            final_score=final,
            brain_scores=sub_scores,
        )
