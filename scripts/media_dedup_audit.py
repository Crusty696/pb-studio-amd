from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def normalize_media_path(file_path: str | None) -> str:
    if not file_path:
        return ""
    try:
        resolved = Path(file_path).expanduser().resolve(strict=False)
    except Exception:
        resolved = Path(file_path).expanduser()
    return os.path.normcase(os.path.normpath(str(resolved)))


def nonempty_json(value: str | None) -> bool:
    if value is None:
        return False
    text = value.strip()
    return text not in {"", "{}", "null"}


def status_rank(status: str | None) -> int:
    order = {
        "ready": 4,
        "analyzed": 4,
        "analyzing": 3,
        "pending": 2,
        "error": 1,
        None: 0,
    }
    return order.get(status, 0)


def winner_sort_key(row: sqlite3.Row, vector_ref_map: dict[int, int]) -> tuple[Any, ...]:
    return (
        vector_ref_map.get(row["id"], 0),
        status_rank(row["status"]),
        int(nonempty_json(row["ai_data_json"])),
        int(nonempty_json(row["metadata_json"])),
        int(row["duration_sec"] is not None),
        int(bool((row["file_hash"] or "").strip())),
        -row["id"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run audit for duplicate media rows")
    parser.add_argument("--db", default="data/pb_studio.db")
    parser.add_argument("--out-dir", default="temp/dedup_audit")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("normalize_media_path", 1, normalize_media_path)
    cur = conn.cursor()

    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    ref_tables: list[dict[str, Any]] = []

    # Optimization: Use a single query to find all foreign keys referencing 'media'.
    # This avoids the N+1 query pattern (calling PRAGMA foreign_key_list for each table).
    fk_query = """
        SELECT m.name AS source_table, fk.*
        FROM sqlite_master m
        JOIN pragma_foreign_key_list(m.name) fk ON fk.[table] = 'media'
        WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'
        ORDER BY m.name
    """
    for fk_row in cur.execute(fk_query).fetchall():
        ref_tables.append({
            "table": fk_row["source_table"],
            "from_column": fk_row["from"],
            "to_column": fk_row["to"],
            "on_delete": fk_row["on_delete"],
            "on_update": fk_row["on_update"],
        })

    vector_ref_map = {
        row[0]: row[1]
        for row in cur.execute("SELECT media_id, COUNT(*) FROM vector_map GROUP BY media_id")
    } if "vector_map" in tables else {}

    dup_rows = cur.execute(
        """
        SELECT *
        FROM media
        WHERE (project_id, normalize_media_path(file_path)) IN (
            SELECT project_id, normalize_media_path(file_path)
            FROM media
            GROUP BY project_id, normalize_media_path(file_path)
            HAVING COUNT(*) > 1
        )
        ORDER BY project_id, file_path, id
        """
    ).fetchall()

    groups: dict[tuple[Any, Any], list[sqlite3.Row]] = {}
    for row in dup_rows:
        groups.setdefault((row["project_id"], normalize_media_path(row["file_path"])), []).append(row)

    group_rows: list[dict[str, Any]] = []
    loser_rows: list[dict[str, Any]] = []
    status_mix = Counter()
    redundant_rows = 0
    analyzed_winners = 0
    vector_moves_needed = 0

    for (project_id, normalized_file_path), rows in groups.items():
        ranked = sorted(rows, key=lambda row: winner_sort_key(row, vector_ref_map), reverse=True)
        winner = ranked[0]
        winner_id = winner["id"]
        winner_vectors = vector_ref_map.get(winner_id, 0)
        if status_rank(winner["status"]) >= status_rank("analyzed"):
            analyzed_winners += 1

        mix = sorted({(r["status"] or "<null>") for r in rows})
        status_mix[",".join(mix)] += 1

        group_rows.append({
            "project_id": project_id,
            "normalized_file_path": normalized_file_path,
            "sample_file_path": winner["file_path"],
            "group_size": len(rows),
            "winner_id": winner_id,
            "winner_status": winner["status"],
            "winner_has_ai": nonempty_json(winner["ai_data_json"]),
            "winner_has_metadata": nonempty_json(winner["metadata_json"]),
            "winner_has_hash": bool((winner["file_hash"] or "").strip()),
            "winner_vector_refs": winner_vectors,
            "loser_ids": ",".join(str(r["id"]) for r in ranked[1:]),
        })

        for loser in ranked[1:]:
            redundant_rows += 1
            loser_vectors = vector_ref_map.get(loser["id"], 0)
            vector_moves_needed += loser_vectors
            loser_rows.append({
                "project_id": project_id,
                "normalized_file_path": normalized_file_path,
                "sample_file_path": winner["file_path"],
                "winner_id": winner_id,
                "loser_id": loser["id"],
                "winner_status": winner["status"],
                "loser_status": loser["status"],
                "winner_has_ai": nonempty_json(winner["ai_data_json"]),
                "loser_has_ai": nonempty_json(loser["ai_data_json"]),
                "winner_has_metadata": nonempty_json(winner["metadata_json"]),
                "loser_has_metadata": nonempty_json(loser["metadata_json"]),
                "winner_has_hash": bool((winner["file_hash"] or "").strip()),
                "loser_has_hash": bool((loser["file_hash"] or "").strip()),
                "winner_vector_refs": winner_vectors,
                "loser_vector_refs": loser_vectors,
            })

    summary = {
        "db_path": str(db_path),
        "table_count": len(tables),
        "tables": tables,
        "media_reference_tables": ref_tables,
        "guard_rows": cur.execute("SELECT COUNT(*) FROM media_import_guard").fetchone()[0] if "media_import_guard" in tables else 0,
        "duplicate_groups": len(groups),
        "duplicate_rows_total": sum(len(rows) for rows in groups.values()),
        "redundant_rows": redundant_rows,
        "analyzed_or_ready_winners": analyzed_winners,
        "vector_moves_needed": vector_moves_needed,
        "status_mix": dict(status_mix),
        "notes": [
            "Dry-run only. No rows were updated or deleted.",
            "The audit groups by normalized path so relative/case variants are treated as the same media import target.",
            "Winner preference: vector refs > analyzed/ready status > AI data > metadata > duration > file hash > stable lowest-id tie-break.",
        ],
    }

    (out_dir / "media_dedup_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with (out_dir / "media_dedup_groups.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(group_rows[0].keys()) if group_rows else ["project_id", "file_path"])
        writer.writeheader()
        writer.writerows(group_rows)

    with (out_dir / "media_dedup_losers.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(loser_rows[0].keys()) if loser_rows else ["project_id", "file_path"])
        writer.writeheader()
        writer.writerows(loser_rows)

    print(json.dumps(summary, indent=2))
    print(f"Wrote audit files to: {out_dir}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
