"""BrainReranker — Eingriffspunkt in clip_selector.select_clip (Plan Phase 4).

Bewertet jeden Kandidaten via Brücken × Posterior-Gewichte. Liefert
Liste von ScoredCandidate sortiert nach final_score absteigend.

Threshold-Filter: brain_min_confidence aus PacingConfigSchema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .bridge_dimensions import BRIDGE_AXES, BridgeDimensions, CandidateFeatures
from .scorer import BrainScorer, ScoredCandidate
from .weight_store import WeightStore


@dataclass
class RerankInput:
    candidate: Any
    features: CandidateFeatures


class BrainReranker:
    def __init__(self, *, weight_store: WeightStore):
        self.weights = weight_store
        self.bridge = BridgeDimensions()
        self.scorer = BrainScorer(bridge=self.bridge, weight_store=weight_store)

    def rerank(
        self,
        candidates: Iterable[RerankInput],
        *,
        context_keys: list[str],
        min_confidence: float = 0.0,
    ) -> list[ScoredCandidate]:
        scored: list[ScoredCandidate] = []
        for ri in candidates:
            if (
                min_confidence > 0.0
                and ri.features.confidence < min_confidence
            ):
                continue
            sc = self.scorer.score(
                candidate=ri.candidate,
                features=ri.features,
                context_keys=context_keys,
            )
            scored.append(sc)

        scored.sort(key=lambda s: s.final_score, reverse=True)
        return scored
