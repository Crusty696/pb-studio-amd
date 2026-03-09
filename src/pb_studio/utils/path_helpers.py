"""
Path Helpers
============

Zentralisierte Pfad-Handling-Funktionen.
"""

from pathlib import Path
from typing import Dict, Any, Optional


def get_clip_path(clip: Dict[str, Any]) -> Optional[Path]:
    """Extrahiert den Pfad aus einem Clip-Dict als Path-Objekt."""
    raw = clip.get("file_path") or clip.get("path") or clip.get("clip_path")
    if raw:
        return Path(raw)
    return None


def get_clip_path_str(clip: Dict[str, Any]) -> Optional[str]:
    """Extrahiert den Pfad aus einem Clip-Dict als String."""
    p = get_clip_path(clip)
    return str(p) if p else None


def normalize_path(path: str | Path) -> Path:
    """Normalisiert einen Pfad (absolute, resolved)."""
    return Path(path).resolve()


def ensure_parent_exists(path: Path) -> Path:
    """Stellt sicher dass das Parent-Verzeichnis existiert."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def escape_path_for_ffmpeg(path: str | Path) -> str:
    """Escaped einen Pfad für FFmpeg-Concat-Listen."""
    p_str = str(Path(path).absolute()).replace("\\", "/")
    return p_str.replace("'", "'\\''")
