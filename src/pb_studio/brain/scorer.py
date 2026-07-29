"""BrainScorer — kombiniert verfügbare Brücken-Werte × Posterior-Gewichte.

Nicht verfügbare Achsen werden ausgelassen und fließen weder als synthetischer
Wert noch in den Nenner des Final-Scores ein.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoredCandidate:
    """Result entry for a scored candidate."""
    candidate: Any
    final_score: float
    brain_scores: dict[str, float] = field(default_factory=dict)
    features: Any = None


class BrainScorer:
    def __init__(self, *, bridge, weight_store):
        self.bridge = bridge
        self.weights = weight_store

    def score(self, *, candidate: Any, features, context_keys: list[str]) -> ScoredCandidate:
        bridge_values = self.bridge.compute_all(features)
        sub_scores: dict[str, float] = {}
        for axis, bridge_value in bridge_values.items():
            bv = float(bridge_value)
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
            features=features,
        )
