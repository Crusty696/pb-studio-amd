"""Wertet die Kick-Alignment-Messung aus und prueft die Produktionsschwelle.

Gefragt ist nicht, wie `kick_alignment` verteilt ist, sondern ob der Wert die
Faelle mit korrekt erkanntem Tempo von denen mit falschem trennt - und ob 0.75
dafuer der richtige Schnitt ist.

Aufruf:
    python scripts/dev/evaluate_kick_alignment.py docs/measurements/<datei>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def _summary(name: str, values: np.ndarray) -> str:
    if values.size == 0:
        return f"  {name:<24} (keine)"
    return (
        f"  {name:<24} n={values.size:>4}  Median {np.median(values):.3f}  "
        f"Mittel {np.mean(values):.3f}  "
        f"10-P {np.percentile(values, 10):.3f}  90-P {np.percentile(values, 90):.3f}"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("Aufruf: evaluate_kick_alignment.py <messdatei.json>", file=sys.stderr)
        return 2
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rows = [r for r in payload["measurements"] if r.get("kick_alignment") is not None]
    threshold = float(payload["parameters"]["production_threshold"])

    if not rows:
        print("Keine Messwerte mit kick_alignment.", file=sys.stderr)
        return 1

    alignment = np.array([r["kick_alignment"] for r in rows], dtype=float)
    correct = np.array([r["tempo_correct"] for r in rows], dtype=bool)
    ratio = np.array([r["tempo_ratio"] for r in rows], dtype=float)

    print(f"{len(rows)} Fenster, {len({r['file'] for r in rows})} Dateien")
    print(f"Produktionsschwelle: {threshold}\n")

    print("Verteilung von kick_alignment:")
    print(_summary("Tempo korrekt", alignment[correct]))
    print(_summary("Tempo falsch", alignment[~correct]))

    # Nach Tempo-Verhaeltnis aufgeschluesselt - Halbtempo soll fallen,
    # Doppeltempo kann die Probe bauartbedingt nicht fangen.
    print("\nNach Tempo-Verhaeltnis (erkannt / wahr, oktavnormiert):")
    for label, mask in (
        ("~1x (korrekt)", np.abs(ratio - 1.0) <= 0.02),
        ("~0.5x (halb)", np.abs(ratio - 0.5) <= 0.02),
        ("~2x (doppelt)", np.abs(ratio - 2.0) <= 0.04),
        ("~0.75x / 1.5x", (np.abs(ratio - 0.75) <= 0.03) | (np.abs(ratio - 1.5) <= 0.03)),
        ("unverwandt", ~(
            (np.abs(ratio - 1.0) <= 0.02) | (np.abs(ratio - 0.5) <= 0.02)
            | (np.abs(ratio - 2.0) <= 0.04)
            | (np.abs(ratio - 0.75) <= 0.03) | (np.abs(ratio - 1.5) <= 0.03)
        )),
    ):
        print(_summary(label, alignment[mask]))

    # Wie gut trennt der Wert? Trennschaerfe ueber alle Schwellen.
    print(f"\n{'Schwelle':>9} {'faengt Falsche':>15} {'verwirft Richtige':>19} {'Youden':>8}")
    best = (-1.0, 0.0)
    for candidate in np.arange(0.30, 1.00, 0.05):
        flagged_wrong = float(np.mean(alignment[~correct] < candidate)) if (~correct).any() else 0.0
        flagged_right = float(np.mean(alignment[correct] < candidate)) if correct.any() else 0.0
        youden = flagged_wrong - flagged_right
        mark = "  <- Produktion" if abs(candidate - threshold) < 0.001 else ""
        print(f"{candidate:>9.2f} {100*flagged_wrong:>13.0f} % {100*flagged_right:>17.0f} %"
              f" {youden:>+8.3f}{mark}")
        if youden > best[0]:
            best = (youden, float(candidate))

    print(f"\nBeste Trennung bei Schwelle {best[1]:.2f} (Youden {best[0]:+.3f})")

    # Was die Produktionsschwelle konkret tut.
    flagged = alignment < threshold
    print(f"\nBei {threshold}:")
    print(f"  als suspect gemeldet: {int(flagged.sum())} von {len(rows)} "
          f"({100*flagged.mean():.0f} %)")
    if (~correct).any():
        print(f"  davon zu Recht (Tempo falsch): {int((flagged & ~correct).sum())} "
              f"von {int((~correct).sum())} falschen "
              f"({100*np.mean(alignment[~correct] < threshold):.0f} % der Falschen gefangen)")
    if correct.any():
        print(f"  Fehlalarm (Tempo korrekt, trotzdem suspect): "
              f"{int((flagged & correct).sum())} von {int(correct.sum())} "
              f"({100*np.mean(alignment[correct] < threshold):.0f} %)")

    # Der Status insgesamt, inklusive Gleichmaessigkeitsteil.
    status = [r["status"] for r in rows]
    print(f"\nGemeldeter Status insgesamt: "
          f"plausible {status.count('plausible')}, suspect {status.count('suspect')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
