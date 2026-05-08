"""Smart-Sampler — Top-N Cuts fuer aktives Lernen (Plan Phase 4 + R-Brain-06).

Auswahl-Strategien:

1. **uncertainty (legacy)**: rein nach Summe Bayes-Variance ueber 17 Achsen
   absteigend.

2. **stratified (R-Brain-06, default)**: Diversitaet x Variance.
   - gruppiere cuts nach Level-5 context_key (spezifischster Bucket)
   - sortiere innerhalb jedes Buckets nach Variance absteigend
   - round-robin durch Buckets bis N erreicht ist
   - falls weniger distinct Buckets als N -> fuelle Rest mit Variance-Ranking
     der noch-nicht-gewaehlten Cuts auf

Der User klickt damit Cuts mit moeglichst breitem Kontext-Spektrum, was die
Bayes-Updates ueber mehr (axis, context_level)-Buckets verteilt -> schnellere
Konvergenz aus dem Cold-Start.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .bridge_dimensions import BRIDGE_AXES
from .weight_store import WeightStore


@dataclass
class CutForSampling:
    cut_id: int
    context_keys: list[str]


SamplingStrategy = Literal["stratified", "uncertainty"]


class SmartSampler:
    def __init__(self, weight_store: WeightStore):
        self.weights = weight_store

    # ---------- public API ----------

    def select_uncertain(
        self,
        cuts: Iterable[CutForSampling],
        n: int = 15,
        *,
        strategy: SamplingStrategy = "stratified",
    ) -> list[CutForSampling]:
        """Returns up to N cuts.

        Args:
            cuts: candidate cuts (ueblicherweise alle Cuts der aktuellen Timeline).
            n: max number of cuts to return.
            strategy: "stratified" (R-Brain-06, diversity x variance) oder
                "uncertainty" (legacy, reine Variance).
        """
        n = max(0, int(n))
        if n == 0:
            return []
        cut_list = list(cuts)
        if not cut_list:
            return []

        if strategy == "uncertainty":
            return self._select_uncertainty_only(cut_list, n)
        return self._select_stratified(cut_list, n)

    # ---------- legacy ----------

    def _select_uncertainty_only(
        self, cuts: list[CutForSampling], n: int
    ) -> list[CutForSampling]:
        scored = self._score_all(cuts)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:n]]

    # ---------- stratified ----------

    def _select_stratified(
        self, cuts: list[CutForSampling], n: int
    ) -> list[CutForSampling]:
        """Round-robin durch Kontext-Buckets, innerhalb absteigend nach Variance.

        Bucket-Key: Level-5 context_key (der spezifischste). Wenn ein Cut keine
        context_keys hat, landet er im Bucket "" (zusammen mit cold-start cuts).
        """
        scored = self._score_all(cuts)

        # Gruppiere nach bucket-key
        buckets: dict[str, list[tuple[float, CutForSampling]]] = {}
        for variance_total, cut in scored:
            key = self._bucket_key(cut)
            buckets.setdefault(key, []).append((variance_total, cut))

        # Sortiere jedes Bucket nach Variance absteigend
        for key in buckets:
            buckets[key].sort(key=lambda x: x[0], reverse=True)

        # Sortiere die Bucket-Keys deterministisch:
        # zuerst die mit hoechster max-Variance (interessantester Bucket), bei
        # Gleichstand alphabetisch. Garantiert reproduzierbare Reihenfolge fuer
        # den Round-Robin.
        bucket_order = sorted(
            buckets.keys(),
            key=lambda k: (-buckets[k][0][0], k),
        )

        # Round-Robin: pro Runde nimm 1 cut aus jedem nicht-leeren Bucket
        selected: list[CutForSampling] = []
        selected_ids: set[int] = set()
        while len(selected) < n:
            picked_in_round = False
            for key in bucket_order:
                if not buckets[key]:
                    continue
                _, cut = buckets[key].pop(0)
                if cut.cut_id in selected_ids:
                    continue
                selected.append(cut)
                selected_ids.add(cut.cut_id)
                picked_in_round = True
                if len(selected) >= n:
                    break
            if not picked_in_round:
                break  # alle Buckets leer

        return selected

    # ---------- helpers ----------

    def _score_all(
        self, cuts: list[CutForSampling]
    ) -> list[tuple[float, CutForSampling]]:
        """Compute summed-variance score per cut over all 17 axes."""
        out: list[tuple[float, CutForSampling]] = []
        for cut in cuts:
            total = 0.0
            for axis in BRIDGE_AXES:
                total += float(self.weights.get_variance(axis, cut.context_keys))
            out.append((total, cut))
        return out

    @staticmethod
    def _bucket_key(cut: CutForSampling) -> str:
        """Most-specific available context_key (level 5) as bucket id.

        Ein Cut ohne context_keys landet im Bucket "" (cold-start group). Ein
        Cut mit nur Level-0 (also context_keys=[""]) landet ebenfalls in "".
        Cuts mit voller Hierarchie (Level 5) landen jeweils in ihrem eigenen
        spezifischen Bucket.
        """
        if not cut.context_keys:
            return ""
        return str(cut.context_keys[-1])
