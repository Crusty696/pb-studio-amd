"""Atomare VACUUM INTO Backups für den Hirn-Store (Plan Phase 6).

VACUUM INTO ist atomar online, sicher unter aktiven WAL-Writes.
Retention: letzte N Backup-Verzeichnisse, ältere automatisch gelöscht.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def backup_brain_store(
    brain_dir: str | Path,
    backup_dir: str | Path,
    *,
    files: Iterable[str] = ("weights.db", "patterns.db", "embedding_cache.db"),
) -> Path:
    """Erstellt timestamped Backup-Verzeichnis mit VACUUM INTO copies.

    Returns:
        Pfad zum erstellten Backup-Verzeichnis.
    """
    brain_dir = Path(brain_dir)
    backup_dir = Path(backup_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"brain_backup_{timestamp}"
    staging = backup_dir / f".{target.name}.tmp"
    backup_dir.mkdir(parents=True, exist_ok=True)
    staging.mkdir()

    try:
        for db_file in files:
            src = brain_dir / db_file
            if not src.exists():
                logger.info("Skipping missing %s", src)
                continue
            dst = staging / db_file
            conn = sqlite3.connect(str(src))
            try:
                conn.execute("VACUUM INTO ?", (str(dst),))
            finally:
                conn.close()
            verify = sqlite3.connect(str(dst))
            try:
                if verify.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError(f"Backup-Integritätsprüfung fehlgeschlagen: {db_file}")
            finally:
                verify.close()
        staging.replace(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    logger.info("Brain backup at %s", target)
    return target


def prune_backups(backup_dir: str | Path, keep: int = 4) -> list[Path]:
    """Behält die `keep` neuesten Backups, löscht ältere. Returns deleted paths."""
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    backups = sorted(
        [p for p in backup_dir.iterdir() if p.is_dir() and p.name.startswith("brain_backup_")],
        key=lambda p: p.name,
        reverse=True,
    )
    deleted: list[Path] = []
    for old in backups[keep:]:
        try:
            shutil.rmtree(old)
            deleted.append(old)
        except OSError as e:
            logger.warning("Could not delete old backup %s: %s", old, e)
    return deleted
