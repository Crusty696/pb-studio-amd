"""R-Brain-08: Process-level LRU cache for loaded raw embeddings.

Auto-invalidation: cache key contains (media_hash, model_name, model_version),
so a re-embedded file with a new hash or version naturally maps to a new entry.

Why a separate module: the brain modules use this transparently, but tests
need a reset-hook (`clear_default_loader_cache`) and the singleton itself.
Stays well clear of `_brain_singleton.py` (Tabu-Zone).
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

import numpy as np

_DEFAULT_MAX = 256


class LoaderCache:
    """Tiny LRU keyed by (media_hash, model_name, model_version) -> ndarray."""

    def __init__(self, max_items: int = _DEFAULT_MAX):
        self._max_items = max(2, int(max_items))
        self._data: "OrderedDict[tuple[str, str, str], np.ndarray]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(
        self, media_hash: str, model_name: str, model_version: str
    ) -> Optional[np.ndarray]:
        if not media_hash:
            return None
        key = (media_hash, model_name, model_version)
        with self._lock:
            arr = self._data.get(key)
            if arr is None:
                self._misses += 1
                return None
            # LRU: move to end
            self._data.move_to_end(key)
            self._hits += 1
            return arr

    def put(
        self,
        media_hash: str,
        model_name: str,
        model_version: str,
        embedding: np.ndarray,
    ) -> None:
        if not media_hash or embedding is None:
            return
        key = (media_hash, model_name, model_version)
        with self._lock:
            self._data[key] = embedding
            self._data.move_to_end(key)
            while len(self._data) > self._max_items:
                self._data.popitem(last=False)  # FIFO eviction of oldest

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._data),
                "max": self._max_items,
                "hits": self._hits,
                "misses": self._misses,
            }


# ---------- Module-level singleton ----------

_default: Optional[LoaderCache] = None
_default_lock = threading.Lock()


def get_default_loader_cache(max_items: int = _DEFAULT_MAX) -> LoaderCache:
    global _default
    if _default is not None:
        return _default
    with _default_lock:
        if _default is None:
            _default = LoaderCache(max_items=max_items)
    return _default


def clear_default_loader_cache() -> None:
    """Test helper. Drops the singleton -> next get_default_loader_cache()
    creates a fresh empty one."""
    global _default
    with _default_lock:
        _default = None
