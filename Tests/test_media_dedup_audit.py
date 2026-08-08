import json
import sqlite3

from scripts import media_dedup_audit


def test_main_discovers_media_foreign_keys_with_one_query(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    output_dir = tmp_path / "audit"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE media (
            id INTEGER PRIMARY KEY,
            project_id INTEGER,
            file_path TEXT,
            status TEXT,
            ai_data_json TEXT,
            metadata_json TEXT,
            duration_sec REAL,
            file_hash TEXT
        );
        CREATE TABLE alpha_refs (
            id INTEGER PRIMARY KEY,
            media_id INTEGER,
            FOREIGN KEY (media_id) REFERENCES media(id)
                ON UPDATE CASCADE ON DELETE SET NULL
        );
        CREATE TABLE beta_refs (
            id INTEGER PRIMARY KEY,
            media_id INTEGER,
            FOREIGN KEY (media_id) REFERENCES media(id)
                ON DELETE CASCADE
        );
        CREATE TABLE unrelated (
            id INTEGER PRIMARY KEY,
            alpha_id INTEGER REFERENCES alpha_refs(id)
        );
        """
    )
    connection.close()

    statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        traced_connection = real_connect(*args, **kwargs)
        traced_connection.set_trace_callback(statements.append)
        return traced_connection

    monkeypatch.setattr(media_dedup_audit.sqlite3, "connect", traced_connect)
    monkeypatch.setattr(
        "sys.argv",
        [
            "media_dedup_audit.py",
            "--db",
            str(db_path),
            "--out-dir",
            str(output_dir),
        ],
    )

    assert media_dedup_audit.main() == 0

    summary = json.loads((output_dir / "media_dedup_summary.json").read_text())
    assert summary["media_reference_tables"] == [
        {
            "table": "alpha_refs",
            "from_column": "media_id",
            "to_column": "id",
            "on_delete": "SET NULL",
            "on_update": "CASCADE",
        },
        {
            "table": "beta_refs",
            "from_column": "media_id",
            "to_column": "id",
            "on_delete": "CASCADE",
            "on_update": "NO ACTION",
        },
    ]
    assert sum(
        "pragma_foreign_key_list" in statement.lower()
        for statement in statements
    ) == 1
