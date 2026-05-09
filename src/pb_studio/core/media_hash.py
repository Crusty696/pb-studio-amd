"""Streaming sha256 hash for media files.

Plan Phase 1 #1: 4 MB chunks for large files.
Used by audio_router and video_router on import.

User-Anforderung 2026-05-09: feingranulares Progress alle 0.01% via
on_progress-Callback. Kleinere Chunks (256 KB) damit Callback haeufig
feuert.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

CHUNK_BYTES = 256 * 1024  # 256 KB - feiner als 4 MB fuer 0.01% Aufloesung


def media_hash(
    path: str | Path,
    on_progress: Optional[Callable[[float], None]] = None,
) -> str:
    """Streaming SHA256 mit optionalem Progress-Callback.

    on_progress(percent: float in 0..100) wird nach jedem Chunk aufgerufen,
    aber nur wenn percent sich um >= 0.01 vom letzten Aufruf unterscheidet
    (verhindert SSE-Flood bei kleinen Files).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")
    total_bytes = p.stat().st_size
    h = hashlib.sha256()
    bytes_read = 0
    last_emitted = -1.0
    with p.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
            bytes_read += len(chunk)
            if on_progress is not None and total_bytes > 0:
                pct = bytes_read * 100.0 / total_bytes
                if pct - last_emitted >= 0.01:
                    on_progress(pct)
                    last_emitted = pct
    if on_progress is not None:
        on_progress(100.0)
    return h.hexdigest()
