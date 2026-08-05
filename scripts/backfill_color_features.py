"""
Backfill fuer avg_brightness / avg_saturation / avg_color_temp / mood_tags.

Audit 2026-08-05 (H-6/T2.6)
---------------------------
Der Producer ``compute_color_features`` wurde erst am 2026-07-10 in die
Video-Pipeline eingehaengt. Aeltere Rows haben die drei Felder deshalb gar
nicht — empirisch 577 von 1359 Rows gefuellt, 782 ohne.

Der Konsument ``brain/feature_adapter.py`` liest sie mit Defaults:

    brightness=_clip01(video.get("avg_brightness", 0.5)),
    saturation=_clip01(video.get("avg_saturation", 0.5)),
    color_temp=... video.get("avg_color_temp") ... 0.0

Fuer die 782 Legacy-Clips liefert das Brain also 0.5/0.5/0.0 als waeren es
Messwerte. Das ist kein Rauschen, sondern eine gerichtete Verzerrung: dunkle
Clips werden wie neutrale behandelt, und die Bridge-Achse
``color_temp_match_weight`` wird fuer diese Clips zur Konstante.

Der Backfill ist eine reine Berechnung aus den bereits persistierten
``dominant_colors`` — kein Modell, keine GPU, keine Neuanalyse. Aufwand rund
8 Sekunden statt ~65 Minuten Reanalyse.

Aufruf (aus dem Projektverzeichnis):
    $env:PYTHONPATH = (Join-Path (Get-Location) "src")
    .\.venv\Scripts\python.exe scripts\backfill_color_features.py --dry-run
    .\.venv\Scripts\python.exe scripts\backfill_color_features.py --apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "pb_studio.db"

COLOR_FIELDS = ("avg_brightness", "avg_saturation", "avg_color_temp")


def _load_compute_color_features():
    """Importiert den Producer erst zur Laufzeit (PYTHONPATH=src noetig)."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from pb_studio.video.moondream_wrapper import compute_color_features

    return compute_color_features


def backfill(db_path: Path, apply: bool) -> int:
    compute_color_features = _load_compute_color_features()

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA journal_mode=WAL")
    cursor = connection.cursor()
    cursor.execute(
        "SELECT id, ai_data_json FROM media "
        "WHERE ai_data_json IS NOT NULL AND ai_data_json != ''"
    )
    rows = cursor.fetchall()

    total = 0
    already_complete = 0
    no_colors = 0
    updated = 0
    updates: list[tuple[str, int]] = []

    for media_id, raw in rows:
        try:
            blob = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(blob, dict):
            continue

        # Nur Video-Rows: Audio-Analysen haben kein dominant_colors-Feld.
        if "dominant_colors" not in blob:
            continue
        total += 1

        if all(field in blob for field in COLOR_FIELDS):
            already_complete += 1
            continue

        colors = blob.get("dominant_colors") or []
        if not isinstance(colors, list) or not colors:
            no_colors += 1
            continue

        features = compute_color_features([str(color) for color in colors])
        for field in COLOR_FIELDS:
            blob[field] = features[field]
        # mood_tags nur setzen wenn bisher leer -- vorhandene Werte gewinnen.
        if not blob.get("mood_tags"):
            blob["mood_tags"] = features.get("mood_tags", [])

        updates.append((json.dumps(blob, ensure_ascii=False), int(media_id)))
        updated += 1

    if apply and updates:
        cursor.executemany(
            "UPDATE media SET ai_data_json = ? WHERE id = ?", updates
        )
        connection.commit()

    connection.close()

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] Video-Rows mit ai_data:        {total}")
    print(f"[{mode}] bereits vollstaendig:         {already_complete}")
    print(f"[{mode}] ohne dominant_colors (Skip):  {no_colors}")
    print(f"[{mode}] backfillbar / geschrieben:    {updated}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"DB nicht gefunden: {args.db}", file=sys.stderr)
        return 2

    backfill(args.db, apply=bool(args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
