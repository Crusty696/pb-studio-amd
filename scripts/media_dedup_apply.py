from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


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


def backup_db(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_pre_dedup_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    wal = db_path.with_name(db_path.name + "-wal")
    shm = db_path.with_name(db_path.name + "-shm")
    if wal.exists():
        shutil.copy2(wal, backup_dir / f"{wal.name}_{stamp}")
    if shm.exists():
        shutil.copy2(shm, backup_dir / f"{shm.name}_{stamp}")
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply duplicate cleanup for media table")
    parser.add_argument("--db", default="data/pb_studio.db")
    parser.add_argument("--backup-dir", default="temp/db_backups")
    parser.add_argument("--journal-dir", default="temp/dedup_apply")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    backup_dir = Path(args.backup_dir).resolve()
    journal_dir = Path(args.journal_dir).resolve()
    journal_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_db(db_path, backup_dir)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")

    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    ref_tables: list[dict[str, Any]] = []
    for table in tables:
        for fk in cur.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk[2] == "media":
                ref_tables.append({
                    "table": table,
                    "from_column": fk[3],
                    "to_column": fk[4],
                    "on_delete": fk[6],
                    "on_update": fk[5],
                })

    vector_ref_map = {
        row[0]: row[1]
        for row in cur.execute("SELECT media_id, COUNT(*) FROM vector_map GROUP BY media_id")
    } if "vector_map" in tables else {}

    dup_rows = cur.execute(
        """
        SELECT *
        FROM media
        WHERE (project_id, file_path) IN (
            SELECT project_id, file_path
            FROM media
            GROUP BY project_id, file_path
            HAVING COUNT(*) > 1
        )
        ORDER BY project_id, file_path, id
        """
    ).fetchall()

    groups: dict[tuple[Any, Any], list[sqlite3.Row]] = {}
    for row in dup_rows:
        groups.setdefault((row["project_id"], row["file_path"]), []).append(row)

    actions: list[dict[str, Any]] = []
    for (project_id, file_path), rows in groups.items():
        ranked = sorted(rows, key=lambda row: winner_sort_key(row, vector_ref_map), reverse=True)
        winner = ranked[0]
        for loser in ranked[1:]:
            actions.append({
                "project_id": project_id,
                "file_path": file_path,
                "winner_id": winner["id"],
                "loser_id": loser["id"],
                "winner_status": winner["status"],
                "loser_status": loser["status"],
                "winner_has_ai": nonempty_json(winner["ai_data_json"]),
                "loser_has_ai": nonempty_json(loser["ai_data_json"]),
                "winner_has_metadata": nonempty_json(winner["metadata_json"]),
                "loser_has_metadata": nonempty_json(loser["metadata_json"]),
                "winner_vector_refs_before": vector_ref_map.get(winner["id"], 0),
                "loser_vector_refs_before": vector_ref_map.get(loser["id"], 0),
            })

    pre_counts = {
        "media_total": cur.execute("SELECT COUNT(*) FROM media").fetchone()[0],
        "vector_map_total": cur.execute("SELECT COUNT(*) FROM vector_map").fetchone()[0] if "vector_map" in tables else 0,
        "dup_groups": len(groups),
        "redundant_rows": len(actions),
    }

    with conn:
        for ref in ref_tables:
            table = ref["table"]
            col = ref["from_column"]
            for action in actions:
                cur.execute(
                    f'UPDATE "{table}" SET "{col}" = ? WHERE "{col}" = ?',
                    (action["winner_id"], action["loser_id"]),
                )

        cur.executemany(
            "DELETE FROM media WHERE id = ?",
            [(action["loser_id"],) for action in actions],
        )

    post_counts = {
        "media_total": cur.execute("SELECT COUNT(*) FROM media").fetchone()[0],
        "vector_map_total": cur.execute("SELECT COUNT(*) FROM vector_map").fetchone()[0] if "vector_map" in tables else 0,
        "dup_groups": cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT 1
                FROM media
                GROUP BY project_id, file_path
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0],
        "foreign_key_check_issues": len(cur.execute("PRAGMA foreign_key_check").fetchall()),
        "integrity_check": cur.execute("PRAGMA integrity_check").fetchone()[0],
    }

    remaining_dup_sample = [
        dict(row) for row in cur.execute(
            """
            SELECT project_id, file_path, COUNT(*) AS cnt
            FROM media
            GROUP BY project_id, file_path
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC, project_id, file_path
            LIMIT 20
            """
        ).fetchall()
    ]

    journal = {
        "timestamp": datetime.now().isoformat(),
        "db_path": str(db_path),
        "backup_path": str(backup_path),
        "reference_tables": ref_tables,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "remaining_dup_sample": remaining_dup_sample,
    }

    (journal_dir / "media_dedup_apply_summary.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
    with (journal_dir / "media_dedup_apply_actions.csv").open("w", newline="", encoding="utf-8") as fh:
        fieldnames = list(actions[0].keys()) if actions else ["winner_id", "loser_id"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(actions)

    print(json.dumps(journal, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
