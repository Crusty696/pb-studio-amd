"""Project anchor file contract shared by HTTP routers."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_ANCHORS_FILE = "anchors.json"


def _anchors_path(project_root: str | Path) -> Path:
    return Path(project_root) / _ANCHORS_FILE


def load_project_anchors(project_root: str | Path) -> list[dict]:
    """Liest die manuellen Anker eines Projekts. Fehler ergeben eine leere Liste."""
    path = _anchors_path(project_root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("anchors.json nicht lesbar: %s", path)
        return []
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            seconds = float(item.get("time", -1.0))
        except (TypeError, ValueError):
            continue
        if seconds < 0.0:
            continue
        result.append({
            "time": seconds,
            "label": str(item.get("label") or ""),
            "video_clip_id": item.get("video_clip_id"),
        })
    result.sort(key=lambda entry: entry["time"])
    return result


