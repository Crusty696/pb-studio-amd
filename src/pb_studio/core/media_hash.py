"""Streaming sha256 hash for media files.

Plan Phase 1 #1: 4 MB chunks for large files.
Used by audio_router and video_router on import.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_BYTES = 4 * 1024 * 1024  # 4 MB


def media_hash(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
