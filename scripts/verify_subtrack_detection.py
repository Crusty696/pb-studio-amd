"""Verify Sub-Track-Detection on a 2h DJ-mix (Plan Phase 1 DoD).

Usage:
    python scripts/verify_subtrack_detection.py <audio_file> [<ground_truth_file>]

Ground-truth file format: one boundary per line, "<seconds>\\n" each.
F-Measure target: >= 0.65 with tolerance 15s. If a sibling ``*.tracks.json``
(constructed reference mix) exists, the acceptance score uses the crossfade
windows instead of the centres (rule of 2026-10-01, see
specs/00035-full-audit-remediation/clarifications.md).
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


def evaluate_boundaries(
    predicted: list[float], gt: list[float], tolerance: float
) -> dict:
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


def load_blend_windows(tracks_json: Path) -> list[tuple[float, float]]:
    """Crossfade regions of a constructed reference mix (`*.tracks.json`).

    Transition k runs from the start of track k+1 to the end of track k.
    """
    import json

    tracks = sorted(
        json.loads(tracks_json.read_text(encoding="utf-8"))["tracks"],
        key=lambda t: t["order"],
    )
    return [
        (float(nxt["mix_start"]), float(cur["mix_end"]))
        for cur, nxt in zip(tracks, tracks[1:])
    ]


def evaluate_blend_windows(
    predicted: list[float], windows: list[tuple[float, float]], tolerance: float
) -> dict:
    """F-measure where a change counts anywhere inside its crossfade.

    Acceptance rule (David, 2026-10-01, Spec 00035 T003): a detected track
    change is correct if it lies within [blend start - tolerance,
    blend end + tolerance], not only near the blend centre. One detection
    matches at most one window and vice versa; among the windows containing a
    detection, the one with the nearest centre is used.
    """
    matched_gt: set[int] = set()
    tp = 0
    for p in sorted(predicted):
        candidates = [
            (abs(p - 0.5 * (s + e)), j)
            for j, (s, e) in enumerate(windows)
            if j not in matched_gt and s - tolerance <= p <= e + tolerance
        ]
        if candidates:
            matched_gt.add(min(candidates)[1])
            tp += 1
    fp = len(predicted) - tp
    fn = len(windows) - len(matched_gt)
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
        m = evaluate_boundaries(boundaries, gt, tolerance=15.0)
        print(f"Ground truth: {len(gt)} boundaries")
        print(f"  TP={m['tp']} FP={m['fp']} FN={m['fn']}")
        print(f"  precision={m['precision']:.3f} recall={m['recall']:.3f} f1={m['f1']:.3f}")
        tracks = gt_file.with_name(gt_file.name.replace(".boundaries.txt", ".tracks.json"))
        if tracks.is_file():
            # Acceptance rule since 2026-10-01: anywhere inside the crossfade.
            m = evaluate_blend_windows(boundaries, load_blend_windows(tracks), 15.0)
            print(f"  Blendenfenster: TP={m['tp']} FP={m['fp']} FN={m['fn']} f1={m['f1']:.3f}")
        if m["f1"] < 0.65:
            print("FAIL: F-Measure unter 0.65")
            return 1
        print("OK")
    else:
        print("Skip F-Measure (kein Ground-Truth-File übergeben)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
