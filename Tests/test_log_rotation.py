"""
Tests für ``pb_studio.utils.log_rotation`` — Aufgabe J.

Geprüft werden:
- Größenbasierte Rotation erzeugt Backup-Files
- Rotierte Files sind gzip-komprimiert (.log.N.gz)
- Aktive ``.log``-Datei bleibt unkomprimiert
- Retention löscht Files älter als ``retention_days``
- Aktive ``.log``-Datei wird bei Cleanup NIE gelöscht
- ``setup_rotating_logging`` liefert konfigurierten Handler
- Defaults stimmen mit der Spezifikation überein (10 MB, 7 Tage)
"""
from __future__ import annotations

import gzip
import logging
import os
import time
from pathlib import Path

import pytest

from pb_studio.utils.log_rotation import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_BYTES,
    DEFAULT_RETENTION_DAYS,
    cleanup_old_logs,
    create_rotating_handler,
    setup_rotating_logging,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


def _attach_isolated_logger(name: str, handler: logging.Handler) -> logging.Logger:
    """Liefert einen logger ohne Propagation und mit nur diesem Handler."""
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _shutdown(logger: logging.Logger, handler: logging.Handler) -> None:
    handler.flush()
    handler.close()
    logger.removeHandler(handler)


def _spam(logger: logging.Logger, count: int = 200, payload: str = "X" * 80) -> None:
    for i in range(count):
        logger.info("%s iter=%d", payload, i)


# ---------------------------------------------------------------------------
# Default-Konstanten
# ---------------------------------------------------------------------------
def test_default_constants_match_spec() -> None:
    """10 MB pro File, 7 Tage Retention — wie in CLAUDE.md/Spec gefordert."""
    assert DEFAULT_MAX_BYTES == 10 * 1024 * 1024
    assert DEFAULT_RETENTION_DAYS == 7
    assert DEFAULT_BACKUP_COUNT >= 1


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------
def test_rotation_creates_backup_files(log_dir: Path) -> None:
    """Genug Logs schreiben -> Rotation muss Backup-Files erzeugen."""
    log_file = log_dir / "rot.log"
    handler = create_rotating_handler(log_file, max_bytes=1024, backup_count=5)
    logger = _attach_isolated_logger("test_rot_creates_backup", handler)

    _spam(logger, count=300)
    _shutdown(logger, handler)

    rotated = sorted(p.name for p in log_dir.iterdir() if p.name != "rot.log")
    assert rotated, f"Erwartete rotierte Files, gefunden: {list(log_dir.iterdir())}"


def test_rotated_files_are_gzipped(log_dir: Path) -> None:
    """Alle rotierten Files (außer der aktiven .log) tragen .gz-Suffix."""
    log_file = log_dir / "rot.log"
    handler = create_rotating_handler(log_file, max_bytes=512, backup_count=4)
    logger = _attach_isolated_logger("test_rot_gz", handler)

    _spam(logger, count=300)
    _shutdown(logger, handler)

    gz_files = list(log_dir.glob("rot.log.*.gz"))
    plain_rotated = [
        p for p in log_dir.iterdir()
        if p.name != "rot.log" and not p.name.endswith(".gz")
    ]
    assert gz_files, f"Keine gzip-Files: {list(log_dir.iterdir())}"
    assert not plain_rotated, (
        f"Unkomprimierte rotierte Files entdeckt: {plain_rotated}"
    )

    # Gzip ist gültig + enthält erwarteten Inhalt
    with gzip.open(gz_files[0], "rb") as f:
        content = f.read().decode("utf-8")
    assert "iter=" in content


def test_active_log_is_not_gzipped(log_dir: Path) -> None:
    """Die aktive ``rot.log`` darf NIEMALS gezippt sein."""
    log_file = log_dir / "rot.log"
    handler = create_rotating_handler(log_file, max_bytes=512, backup_count=3)
    logger = _attach_isolated_logger("test_active_plain", handler)

    _spam(logger, count=200)
    _shutdown(logger, handler)

    assert log_file.exists(), "Aktive Log-Datei muss existieren"
    # Plain-Text-lesbar?
    text = log_file.read_text(encoding="utf-8")
    assert "iter=" in text


def test_backup_count_caps_total_files(log_dir: Path) -> None:
    """Mehr Logs als backupCount -> älteste werden verworfen."""
    log_file = log_dir / "rot.log"
    handler = create_rotating_handler(log_file, max_bytes=256, backup_count=2)
    logger = _attach_isolated_logger("test_cap", handler)

    _spam(logger, count=600)
    _shutdown(logger, handler)

    rotated_count = len(list(log_dir.glob("rot.log.*")))
    # Mit backupCount=2 darf es max. 2 rotierte Files geben
    assert rotated_count <= 2, f"Erwartete <=2 rotierte Files, fand {rotated_count}"


# ---------------------------------------------------------------------------
# Retention / Cleanup
# ---------------------------------------------------------------------------
def test_cleanup_deletes_files_older_than_retention(log_dir: Path) -> None:
    """Files >= retention_days alt -> gelöscht; jüngere bleiben."""
    old = log_dir / "x.log.1.gz"
    young = log_dir / "x.log.2.gz"
    active = log_dir / "x.log"
    old.write_bytes(b"old")
    young.write_bytes(b"young")
    active.write_bytes(b"active")

    very_old = time.time() - 10 * 86400
    one_day_ago = time.time() - 86400
    os.utime(old, (very_old, very_old))
    os.utime(young, (one_day_ago, one_day_ago))

    deleted = cleanup_old_logs(log_dir, retention_days=7)

    assert deleted == 1
    assert not old.exists()
    assert young.exists()
    assert active.exists()


def test_cleanup_never_deletes_active_log(log_dir: Path) -> None:
    """Auch wenn alt: ``backend.log`` ohne ``.log.``-Suffix wird nie gelöscht."""
    active = log_dir / "backend.log"
    active.write_bytes(b"alt aber aktiv")

    very_old = time.time() - 30 * 86400
    os.utime(active, (very_old, very_old))

    deleted = cleanup_old_logs(log_dir, retention_days=7)

    assert deleted == 0
    assert active.exists()


def test_cleanup_handles_missing_directory(tmp_path: Path) -> None:
    """Nicht-existentes Verzeichnis -> 0, keine Exception."""
    nonexistent = tmp_path / "does_not_exist"
    assert cleanup_old_logs(nonexistent, retention_days=7) == 0


def test_cleanup_handles_uncompressed_rotated_files(log_dir: Path) -> None:
    """Nicht nur .gz, auch z.B. backend.log.1 (ohne gz) wird aufgeräumt."""
    plain = log_dir / "backend.log.1"
    plain.write_bytes(b"plain rotated")
    very_old = time.time() - 14 * 86400
    os.utime(plain, (very_old, very_old))

    deleted = cleanup_old_logs(log_dir, retention_days=7)

    assert deleted == 1
    assert not plain.exists()


# ---------------------------------------------------------------------------
# Setup-Funktion
# ---------------------------------------------------------------------------
def test_setup_returns_configured_handler(log_dir: Path) -> None:
    log_file = log_dir / "setup.log"
    handler = setup_rotating_logging(log_file=log_file)

    try:
        assert handler is not None
        assert handler.maxBytes == DEFAULT_MAX_BYTES
        assert handler.backupCount == DEFAULT_BACKUP_COUNT
        assert handler.formatter is not None
        # gzip-Hooks sind installiert
        assert handler.namer is not None
        assert handler.rotator is not None
        # Parent-Verzeichnis wurde angelegt
        assert log_file.parent.exists()
    finally:
        handler.close()


def test_setup_respects_custom_kwargs(log_dir: Path) -> None:
    log_file = log_dir / "custom.log"
    handler = setup_rotating_logging(
        log_file=log_file,
        max_bytes=2048,
        backup_count=3,
        retention_days=1,
    )
    try:
        assert handler.maxBytes == 2048
        assert handler.backupCount == 3
    finally:
        handler.close()


def test_setup_runs_initial_cleanup(log_dir: Path) -> None:
    """Beim Setup wird einmal cleanup_old_logs aufgerufen — alte Files weg."""
    stale = log_dir / "boot.log.99.gz"
    stale.write_bytes(b"sehr alt")
    very_old = time.time() - 30 * 86400
    os.utime(stale, (very_old, very_old))

    log_file = log_dir / "boot.log"
    handler = setup_rotating_logging(log_file=log_file, retention_days=7)
    try:
        assert not stale.exists(), "Initial-Cleanup sollte stale Files entfernen"
    finally:
        handler.close()


# ---------------------------------------------------------------------------
# End-to-End: Rotation + Retention zusammen
# ---------------------------------------------------------------------------
def test_end_to_end_rotation_and_retention(log_dir: Path) -> None:
    """Schreibt viele Logs, prüft .gz, manipuliert mtime, verifiziert Cleanup."""
    log_file = log_dir / "e2e.log"
    handler = create_rotating_handler(log_file, max_bytes=512, backup_count=5)
    logger = _attach_isolated_logger("test_e2e", handler)

    _spam(logger, count=400)
    _shutdown(logger, handler)

    gz_before = list(log_dir.glob("e2e.log.*.gz"))
    assert gz_before, "Erwartete .gz Backups vor Cleanup"

    # mtime aller rotierten Files weit in die Vergangenheit
    far_past = time.time() - 14 * 86400
    for p in gz_before:
        os.utime(p, (far_past, far_past))

    deleted = cleanup_old_logs(log_dir, retention_days=7)

    assert deleted == len(gz_before)
    assert not list(log_dir.glob("e2e.log.*.gz"))
    assert log_file.exists(), "Aktive Datei muss überleben"
