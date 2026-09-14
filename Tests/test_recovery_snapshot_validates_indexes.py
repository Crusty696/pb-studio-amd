"""Ein Recovery-Snapshot darf keine beschaedigten Indizes durchlassen.

Befund 2026-08-30. Die Kette, die dahintersteckt, ist am realen Artefakt belegt:

1. `backend/main.py:271` markiert die Laufzeit beim Backendstart als DIRTY;
   geraeumt wird der Marker nur beim SAUBEREN Shutdown (`:385`).
2. Endet das Backend unsauber, faehrt der naechste Bootstrap
   `_recover_generation` und stellt ALLE verwalteten Artefakte wieder her -
   398 Stueck, darunter `data/pb_studio.db`, 349 BrainStore-Dateien, 30
   `project.json` und `config.json`.
3. Der Snapshot vom 2026-08-29 enthielt eine beschaedigte Indexstruktur
   (`row 604 missing from index idx_media_status`). Der Restore hat sie in die
   Live-Datenbank zurueckgespielt.

Warum das durchkam: `_backup_sqlite` validiert mit `PRAGMA quick_check`, und
quick_check prueft die Uebereinstimmung von Tabelle und Index **nicht**. Genau
diese Fehlerklasse liegt hier vor. `PRAGMA integrity_check` findet sie - und
kostet auf der 29-MB-Produktionsdatenbank gemessen dasselbe (je 14,5 ms).

Der Test baut die Beschaedigung selbst, statt sie zu behaupten: der Index wird
dem Schema kurz entzogen, waehrenddessen werden Zeilen eingefuegt, danach
bekommt er seinen Schemaeintrag zurueck. Die Tabelle traegt dann Zeilen, die
im Index fehlen - dasselbe Muster wie im echten Artefakt.
"""

import sqlite3
from pathlib import Path

import pytest

from pb_studio.storage.recovery_generation import (
    RecoveryGenerationValidationError,
    _backup_sqlite,
)


def _make_db_with_orphaned_index_rows(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE media(id INTEGER PRIMARY KEY, status TEXT);
        CREATE INDEX idx_media_status ON media(status);
        INSERT INTO media(id, status) VALUES (1,'a'),(2,'b'),(3,'c');
        """
    )
    connection.commit()
    schema_row = connection.execute(
        "SELECT type, name, tbl_name, rootpage, sql "
        "FROM sqlite_master WHERE name='idx_media_status'"
    ).fetchone()
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute("DELETE FROM sqlite_master WHERE name='idx_media_status'")
    connection.commit()
    connection.close()

    # Der Index ist dem Schema jetzt unbekannt: diese Zeilen landen nicht darin.
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO media(id, status) VALUES (604,'x'),(605,'y')")
    connection.commit()
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "INSERT INTO sqlite_master(type, name, tbl_name, rootpage, sql) "
        "VALUES (?,?,?,?,?)",
        schema_row,
    )
    connection.commit()
    connection.close()


def test_the_corruption_fixture_is_the_real_thing(tmp_path):
    """Vorbedingung: quick_check ist blind, integrity_check nicht.

    Faellt dieser Test, ist die Beschaedigung nicht mehr die, um die es geht -
    dann sagt der Haupttest unten nichts mehr aus.
    """
    source = tmp_path / "source.db"
    _make_db_with_orphaned_index_rows(source)

    connection = sqlite3.connect(source)
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        findings = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    finally:
        connection.close()

    assert any("missing from index" in finding for finding in findings), findings


def test_backup_refuses_a_source_with_broken_indexes(tmp_path):
    """Der eigentliche Waechter: so ein Snapshot darf gar nicht erst entstehen."""
    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    _make_db_with_orphaned_index_rows(source)

    with pytest.raises(RecoveryGenerationValidationError, match="integrity"):
        _backup_sqlite(source, destination)


def test_backup_accepts_a_healthy_source(tmp_path):
    """Gegenprobe: die strengere Pruefung darf nichts Gesundes ablehnen."""
    source = tmp_path / "healthy.db"
    destination = tmp_path / "healthy-snapshot.db"
    connection = sqlite3.connect(source)
    connection.executescript(
        """
        CREATE TABLE media(id INTEGER PRIMARY KEY, status TEXT);
        CREATE INDEX idx_media_status ON media(status);
        INSERT INTO media(id, status) VALUES (1,'a'),(2,'b'),(604,'x');
        """
    )
    connection.commit()
    connection.close()

    user_version, check_result = _backup_sqlite(source, destination)
    assert check_result == "ok"
    assert user_version == 0          # frische DB, kein PRAGMA user_version gesetzt
    assert destination.exists() and destination.stat().st_size > 0
