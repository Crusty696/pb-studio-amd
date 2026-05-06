"""Verify Sub-Track-Detection on a 2h DJ-mix (Plan Phase 1 DoD).

Usage:
    python scripts/verify_subtrack_detection.py <audio_file> [<ground_truth_file>]

Ground-truth file format: one boundary per line, "<seconds>\\n" each.
F-Measure target: >= 0.65 with tolerance 15s.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _load_gt(path: Path) -> list[float]:
    out: list[float] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(float(line.split()[0]))
    return out


def _f_measure(predicted: list[float], gt: list[float], tolerance: float) -> dict:
    matched_pred = set()
    matched_gt = set()
    for i, p in enumerate(predicted):
        for j, g in enumerate(gt):
            if j in matched_gt:
                continue
            if abs(p - g) <= tolerance:
                matched_pred.add(i)
                matched_gt.add(j)
                break
    tp = len(matched_pred)
    fp = len(predicted) - tp
    fn = len(gt) - len(matched_gt)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
    }


def main() -> int:
    sys.path.insert(0, "src")
    from pb_studio.audio.subtrack_detector import SubtrackDetector

    if len(sys.argv) < 2:
        print("Usage: verify_subtrack_detection.py <audio_file> [<gt_file>]")
        return 2
    audio = Path(sys.argv[1])
    gt_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Audio: {audio}")
    detector = SubtrackDetector()
    t0 = time.time()
    result = detector.detect(audio)
    dt = time.time() - t0

    boundaries = [b.time for b in result.boundaries]
    print(f"Detected boundaries: {len(boundaries)} in {dt:.2f}s")
    print(f"Segments:            {len(result.segments)}")

    if gt_file and gt_file.is_file():
        gt = _load_gt(gt_file)
        m = _f_measure(boundaries, gt, tolerance=15.0)
        print(f"Ground truth: {len(gt)} boundaries")
        print(f"  TP={m['tp']} FP={m['fp']} FN={m['fn']}")
        print(f"  precision={m['precision']:.3f} recall={m['recall']:.3f} f1={m['f1']:.3f}")
        if m["f1"] < 0.65:
            print("FAIL: F-Measure unter 0.65")
            return 1
        print("OK")
    else:
        print("Skip F-Measure (kein Ground-Truth-File übergeben)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
