import json
import sqlite3
from pathlib import Path


PROJECT_ROOTS = (
    Path(r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245"),
    Path(r"C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260727_083320"),
    Path(r"C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260727_083216"),
)
GLOBAL_DB = Path(r"C:\Users\david\Documents\Pb_studio_AMD_version\data\pb_studio.db")


def main() -> None:
    report = []
    for root in PROJECT_ROOTS:
        connection = sqlite3.connect(
            f"file:{root / 'state.db'}?mode=ro",
            uri=True,
        )
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' ORDER BY name"
                )
            ]
            columns = {
                table: [
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    )
                ]
                for table in tables
            }
            report.append(
                {
                    "root": str(root),
                    "tables": tables,
                    "columns": columns,
                }
            )
        finally:
            connection.close()

    global_connection = sqlite3.connect(
        f"file:{GLOBAL_DB}?mode=ro",
        uri=True,
    )
    global_connection.row_factory = sqlite3.Row
    try:
        global_tables = [
            row[0]
            for row in global_connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' ORDER BY name"
            )
        ]
        global_columns = {
            table: [
                row[1]
                for row in global_connection.execute(
                    f"PRAGMA table_info({table})"
                )
            ]
            for table in global_tables
        }
        media_rows = []
        for row in global_connection.execute(
            "SELECT id, project_id, file_path, status, metadata_json, ai_data_json "
            "FROM media WHERE project_id IN (32, 33, 34) "
            "ORDER BY project_id, id"
        ):
            metadata = json.loads(row["metadata_json"] or "{}")
            ai_data = json.loads(row["ai_data_json"] or "{}")
            media_rows.append(
                {
                    "id": row["id"],
                    "project_id": row["project_id"],
                    "file_path": row["file_path"],
                    "status": row["status"],
                    "metadata_keys": sorted(metadata),
                    "ai_data_keys": sorted(ai_data),
                    "analysis_status": ai_data.get("analysis_status"),
                    "stage_status": ai_data.get("stage_status"),
                    "stage_errors": ai_data.get("stage_errors"),
                }
            )
        issue_rows = []
        for row in global_connection.execute(
            "SELECT id, project_id, file_path, status, ai_data_json FROM media "
            "WHERE ai_data_json IS NOT NULL AND ai_data_json <> '' "
            "ORDER BY project_id, id"
        ):
            ai_data = json.loads(row["ai_data_json"] or "{}")
            analysis_status = ai_data.get("analysis_status")
            stage_errors = ai_data.get("stage_errors")
            if analysis_status in {"partial", "failed"} or stage_errors:
                issue_rows.append(
                    {
                        "id": row["id"],
                        "project_id": row["project_id"],
                        "file_path": row["file_path"],
                        "status": row["status"],
                        "analysis_status": analysis_status,
                        "stage_status": ai_data.get("stage_status"),
                        "stage_errors": stage_errors,
                    }
                )
    finally:
        global_connection.close()

    print(
        json.dumps(
            {
                "project_databases": report,
                "global_database": {
                    "path": str(GLOBAL_DB),
                    "tables": global_tables,
                    "columns": global_columns,
                    "media_rows": media_rows,
                    "issue_rows": issue_rows,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
