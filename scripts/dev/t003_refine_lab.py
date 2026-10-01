"""T003 lab: test boundary refinements on cached mix features (read-only).

    PYTHONPATH=src python scripts/dev/t003_refine_lab.py CACHE.npz GT.txt [CACHE GT ...]

Wraps `SubtrackDetector._optimal_partition` and post-processes its cuts with
candidate refinements, then scores every variant on all given mixes with the
same evaluator as `t003_boundary_lab.py` (15-s tolerance). Also reports the
share of reference boundaries for which *some* detection lies within
+-30 s ("inside a long blend") as a diagnostic, not as an acceptance metric.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import t003_boundary_lab as lab  # noqa: E402
from verify_subtrack_detection import _load_gt, evaluate_boundaries  # noqa: E402

from pb_studio.audio import subtrack_detector as sd  # noqa: E402

_ORIG = sd.SubtrackDetector._optimal_partition


def _crossover(sim: np.ndarray, cuts: list[int], frame_sec: float, search_sec: float,
               core_gap_sec: float) -> list[int]:
    """Move each cut to the sign change of (fit to left core - fit to right core)."""
    m = sim.shape[0]
    edges = [0, *cuts, m]
    gap = max(1, int(round(core_gap_sec / frame_sec)))
    reach = max(1, int(round(search_sec / frame_sec)))
    out: list[int] = []
    for k in range(1, len(edges) - 1):
        c = edges[k]
        left = np.arange(edges[k - 1], max(edges[k - 1] + 1, c - gap))
        right = np.arange(min(edges[k + 1] - 1, c + gap), edges[k + 1])
        if left.size < 3 or right.size < 3:
            out.append(c)
            continue
        lo, hi = max(edges[k - 1] + 1, c - reach), min(edges[k + 1] - 1, c + reach)
        t = np.arange(lo, hi + 1)
        d = sim[np.ix_(t, left)].mean(axis=1) - sim[np.ix_(t, right)].mean(axis=1)
        # first frame (from the left) whose fit flips towards the right track
        flip = np.where((d[:-1] > 0) & (d[1:] <= 0))[0]
        if flip.size:
            best = flip[np.argmin(np.abs(t[flip + 1] - c))]
            out.append(int(t[best + 1]))
        else:
            out.append(c)
    return out


def _variant(kind: str, **kw):
    def part(similarity, frame_sec):
        cuts = _ORIG(similarity, frame_sec)
        if kind == "crossover":
            return _crossover(similarity, cuts, frame_sec, **kw)
        return cuts
    return staticmethod(part)


VARIANTS = {
    "production": ("none", {}),
    "xo_s40_g40": ("crossover", {"search_sec": 40.0, "core_gap_sec": 40.0}),
    "xo_s40_g60": ("crossover", {"search_sec": 40.0, "core_gap_sec": 60.0}),
    "xo_s30_g30": ("crossover", {"search_sec": 30.0, "core_gap_sec": 30.0}),
    "xo_s60_g60": ("crossover", {"search_sec": 60.0, "core_gap_sec": 60.0}),
}


def main(argv: list[str]) -> None:
    pairs = list(zip(argv[0::2], argv[1::2]))
    data = [(Path(c).stem, np.load(c), _load_gt(Path(g))) for c, g in pairs]
    for name, (kind, kw) in VARIANTS.items():
        sd.SubtrackDetector._optimal_partition = _variant(kind, **kw)
        f1s, inside, rows = [], [], []
        for stem, z, gt in data:
            found = lab.run(z, {})
            m = evaluate_boundaries(found, gt, 15.0)
            f1s.append(m["f1"])
            hit30 = sum(1 for g in gt if found and min(abs(x - g) for x in found) <= 30.0)
            inside.append(hit30 / len(gt))
            rows.append(f"{stem}: F1 {m['f1']:.3f} n={len(found)} "
                        f"err={[round(min(abs(x - g) for x in found)) if found else None for g in gt]}")
        sd.SubtrackDetector._optimal_partition = staticmethod(_ORIG)
        print(f"== {name}  mean F1 {np.mean(f1s):.3f}  min {np.min(f1s):.3f}  "
              f"recall@30s {np.mean(inside):.3f}")
        for r in rows:
            print("   " + r)


if __name__ == "__main__":
    main(sys.argv[1:])
