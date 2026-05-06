"""Smart-Sampler — Top-N Cuts mit höchster Bayes-Varianz (Plan Phase 4).

Sortiert Cuts absteigend nach summe variance über alle 17 Achsen für
ihren context_keys-Vektor. Dadurch klickt der User die unsichersten zuerst.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .bridge_dimensions import BRIDGE_AXES
from .weight_store import WeightStore


@dataclass
class CutForSampling:
    cut_id: int
    context_keys: list[str]


class SmartSampler:
    def __init__(self, weight_store: WeightStore):
        self.weights = weight_store

    def select_uncertain(
        self, cuts: Iterable[CutForSampling], n: int = 15
    ) -> list[CutForSampling]:
        scored: list[tuple[float, CutForSampling]] = []
        for cut in cuts:
            total = 0.0
            for axis in BRIDGE_AXES:
                total += float(self.weights.get_variance(axis, cut.context_keys))
            scored.append((total, cut))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[: max(0, int(n))]]
