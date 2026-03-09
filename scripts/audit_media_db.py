from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pb_studio.db"
REPORT_DIR = ROOT / "temp" / "db_audit"


@dataclass
class MediaRow:
    id: int
    project_id: int | None
    file_path: str
    status: str | None


def load_rows(conn: sqlite3.Connection) -> list[MediaRow]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, project_id, file_path, status FROM media ORDER BY id"
    ).fetchall()
    return [MediaRow(**dict(row)) for row in rows]


def audit(rows: Iterable[MediaRow]) -> dict:
    rows = list(rows)
    missing = [row for row in rows if not Path(row.file_path).exists()]
    status_counts = Counter(row.status or "<null>" for row in rows)
    path_map: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        path_map[row.file_path].append(row.id)
    duplicate_groups = {path: ids for path, ids in path_map.items() if len(ids) > 1}
    return {
        "total_rows": len(rows),
        "missing_rows": len(missing),
        "status_counts": dict(status_counts),
        "duplicate_path_groups": len(duplicate_groups),
        "duplicate_extra_rows": sum(len(ids) - 1 for ids in duplicate_groups.values()),
        "missing": [asdict(row) for row in missing],
        "duplicate_examples": [
            {"file_path": path, "ids": ids[:10], "count": len(ids)}
            for path, ids in sorted(duplicate_groups.items(), key=lambda item: (-len(item[1]), item[0]))[:25]
        ],
    }


def write_report(report: dict) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"media_audit_{stamp}.json"
    csv_path = REPORT_DIR / f"media_missing_{stamp}.csv"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "project_id", "file_path", "status"])
        writer.writeheader()
        for row in report["missing"]:
            writer.writerow(row)
    return json_path, csv_path


def cleanup_missing(conn: sqlite3.Connection, missing: list[dict]) -> int:
    if not missing:
        return 0
    ids = [row["id"] for row in missing]
    placeholders = ",".join("?" for _ in ids)
    with conn:
        conn.execute(f"DELETE FROM media WHERE id IN ({placeholders})", ids)
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit/Cleanup der media-Tabelle gegen reale Dateiexistenz")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--cleanup-missing", action="store_true", help="Löscht nur verwaiste media-Zeilen aus der DB")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    try:
        rows = load_rows(conn)
        report = audit(rows)
        json_path, csv_path = write_report(report)
        print(json.dumps({
            "db": str(args.db),
            "total_rows": report["total_rows"],
            "missing_rows": report["missing_rows"],
            "duplicate_path_groups": report["duplicate_path_groups"],
            "duplicate_extra_rows": report["duplicate_extra_rows"],
            "report_json": str(json_path),
            "report_csv": str(csv_path),
        }, ensure_ascii=False, indent=2))

        if args.cleanup_missing:
            deleted = cleanup_missing(conn, report["missing"])
            print(json.dumps({"deleted_missing_rows": deleted}, ensure_ascii=False))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
