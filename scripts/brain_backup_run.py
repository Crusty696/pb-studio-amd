"""Standalone backup runner for Windows Task Scheduler (Plan Phase 6).

Backs up %APPDATA%\\PB_Studio\\brain\\*.db to
%APPDATA%\\PB_Studio\\backups\\brain_backup_<ts>\\, prunes to keep newest 4.

Exit 0 success, non-zero on failure.

Schedule weekly via:
    scripts\\install_brain_backup_task.ps1
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from pb_studio.storage.backup import backup_brain_store, prune_backups
    from pb_studio.storage.brain_store import default_brain_dir

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    brain_dir = default_brain_dir()
    backup_root = brain_dir.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)

    if not brain_dir.is_dir():
        logging.warning("Brain dir missing: %s — nothing to back up", brain_dir)
        return 0

    target = backup_brain_store(brain_dir, backup_root)
    logging.info("Backup created: %s", target)

    deleted = prune_backups(backup_root, keep=4)
    if deleted:
        logging.info("Pruned %d old backup(s)", len(deleted))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        logging.exception("Backup failed: %s", e)
        raise SystemExit(1)
