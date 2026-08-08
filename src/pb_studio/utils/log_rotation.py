"""
Log-Rotation + Retention für PB Studio AMD.

Aufgabe J:
- Größenbasierte Rotation pro File (Default: 10 MB)
- 7-Tage-Retention für alte Logs
- gzip-Compression rotierter Files (.log.1 -> .log.1.gz)
- Reine Python 3.11 stdlib (R3): logging.handlers, gzip, shutil, pathlib

Beispiel
--------
>>> from pb_studio.utils.log_rotation import setup_rotating_logging
>>> handler = setup_rotating_logging(Path("logs/backend.log"))
>>> logging.basicConfig(handlers=[handler])

Architektur
-----------
1. ``RotatingFileHandler`` (size-based) erzeugt ``foo.log.N``
2. ``namer``  -> hängt ``.gz`` an  (foo.log.N -> foo.log.N.gz)
3. ``rotator`` -> gzipt source -> dest und löscht source
4. ``cleanup_old_logs`` läuft beim Setup einmalig und löscht
   rotierte Files älter als ``retention_days`` (mtime-basiert)

Retention-Policy
----------------
Cleanup ist absichtlich konservativ:
- Aktive ``*.log``-Dateien werden NIE gelöscht
- Nur Files mit ``.log.`` im Namen (z.B. ``backend.log.1.gz``) gelten als rotiert
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Konfiguration (Defaults)
# ---------------------------------------------------------------------------
DEFAULT_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB pro File
DEFAULT_BACKUP_COUNT: int = 20              # Reservepuffer; Retention räumt auf
DEFAULT_RETENTION_DAYS: int = 7             # Tage bis rotierte Logs gelöscht werden
DEFAULT_LOG_FORMAT: str = (
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
# Audit 2026-08-05 (Querschnittsbefund): Der Zeitstempel enthielt nur "%H:%M:%S".
# backend.log wird ueber Wochen angehaengt (50.658 Zeilen zum Auditzeitpunkt), und
# ohne Datum sahen laengst behobene Fehler aus wie aktuelle -- zwei Befunde wurden
# dadurch zunaechst falsch als offen bewertet. Datum ist Pflicht.
DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# gzip-Hooks für RotatingFileHandler
# ---------------------------------------------------------------------------
def _gzip_namer(name: str) -> str:
    """Namer-Hook: hängt ``.gz`` an den rotierten Filenamen.

    Wird vom RotatingFileHandler aufgerufen, um aus
    ``backend.log.1`` -> ``backend.log.1.gz`` zu machen.
    """
    return name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:
    """Rotator-Hook: gzip-komprimiert ``source`` nach ``dest`` und löscht source.

    Wird vom RotatingFileHandler nach jeder Rotation aufgerufen.
    Der Handler ruft uns nur für die *aktive* Datei auf; bereits rotierte
    Files werden vom Handler intern via ``os.rename`` umbenannt
    (``foo.log.1.gz`` -> ``foo.log.2.gz``), so dass sie komprimiert bleiben.
    """
    src = Path(source)
    dst = Path(dest)
    if not src.exists():
        return
    with src.open("rb") as f_in, gzip.open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        src.unlink()
    except OSError:
        # Falls die Quelle bereits weg ist (z.B. Race) — nicht fatal
        pass


# ---------------------------------------------------------------------------
# Retention-Cleanup
# ---------------------------------------------------------------------------
def cleanup_old_logs(
    log_dir: Path | str,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> int:
    """Löscht rotierte Log-Files älter als ``retention_days``.

    Aktive ``*.log``-Dateien werden NIE gelöscht. Nur Files, deren Name
    ``.log.`` enthält (also ``backend.log.1`` oder ``backend.log.1.gz``),
    sind Kandidaten.

    Args:
        log_dir: Verzeichnis, das die Logs enthält.
        retention_days: Maximales Alter in Tagen (mtime-basiert).

    Returns:
        Anzahl gelöschter Dateien.
    """
    log_dir = Path(log_dir)
    if not log_dir.exists() or not log_dir.is_dir():
        return 0

    cutoff = time.time() - (retention_days * 86400)
    deleted = 0

    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        # Nur rotierte Files: Name enthält ``.log.`` (also Suffix nach .log)
        if ".log." not in path.name:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except OSError:
            # Datei verschwand zwischen iterdir() und unlink() oder
            # Berechtigungsproblem — bewusst still ignorieren.
            continue

    return deleted


# ---------------------------------------------------------------------------
# Handler-Factory + Setup
# ---------------------------------------------------------------------------
def create_rotating_handler(
    log_file: Path | str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    encoding: str = "utf-8",
) -> RotatingFileHandler:
    """Baut einen RotatingFileHandler mit gzip-Compression-Hooks.

    Args:
        log_file: Pfad zur aktiven Log-Datei.
        max_bytes: Maximale Bytes pro File vor Rotation.
        backup_count: Wie viele rotierte Backups behalten werden.
        encoding: Datei-Encoding.

    Returns:
        Konfigurierter ``RotatingFileHandler``.
    """
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding=encoding,
    )
    handler.namer = _gzip_namer
    handler.rotator = _gzip_rotator
    return handler


def setup_rotating_logging(
    log_file: Path | str,
    *,
    level: int = logging.INFO,
    fmt: str = DEFAULT_LOG_FORMAT,
    datefmt: str = DEFAULT_DATE_FORMAT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> RotatingFileHandler:
    """High-Level Setup: Handler bauen + Initial-Cleanup ausführen.

    Wird typischerweise einmal beim Backend-Start aufgerufen, der Handler
    danach in ``logging.basicConfig(handlers=[...])`` eingehängt.

    Args:
        log_file: Pfad zur aktiven Log-Datei.
        level: Log-Level für den Handler.
        fmt: Format-String.
        datefmt: Date-Format-String.
        max_bytes: Rotation-Schwelle in Bytes.
        backup_count: Anzahl rotierter Backups.
        retention_days: Alter in Tagen, ab dem rotierte Files gelöscht werden.

    Returns:
        Konfigurierter, sofort einsatzbereiter ``RotatingFileHandler``.
    """
    log_file = Path(log_file)
    handler = create_rotating_handler(
        log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # Beim Boot einmal aufräumen
    cleanup_old_logs(log_file.parent, retention_days=retention_days)

    return handler


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_BACKUP_COUNT",
    "DEFAULT_RETENTION_DAYS",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_DATE_FORMAT",
    "cleanup_old_logs",
    "create_rotating_handler",
    "setup_rotating_logging",
]
