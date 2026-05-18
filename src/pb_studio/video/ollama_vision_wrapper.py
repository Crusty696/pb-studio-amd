"""DEPRECATED - re-export shim fuer lmstudio_vision_wrapper.

Das Modul wurde am 2026-05-17 in lmstudio_vision_wrapper umbenannt, weil
PB Studio von Ollama auf LM Studio gewechselt ist. Alte Imports funktionieren
weiter via diesem Shim; im naechsten Major-Cleanup wird er entfernt.

Neue Aufrufe sollen direkt von pb_studio.video.lmstudio_vision_wrapper
importieren.
"""
from __future__ import annotations

import warnings

from .lmstudio_vision_wrapper import (  # noqa: F401
    DEFAULT_MODE,
    DEFAULT_PROMPT,
    DEFAULT_TASK,
    _async_extract_tags,
    _cache_get,
    _cache_put,
    _frame_hash,
    _load_ai_config,
    _parse_tags,
    _STOPWORDS,
    _TAG_CACHE,
    _CACHE_MAX,
    clear_tag_cache,
    extract_tags_via_lmstudio,
    extract_tags_via_ollama,
)

warnings.warn(
    "pb_studio.video.ollama_vision_wrapper ist deprecated - bitte "
    "pb_studio.video.lmstudio_vision_wrapper importieren.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "extract_tags_via_lmstudio",
    "extract_tags_via_ollama",
    "clear_tag_cache",
    "DEFAULT_TASK",
    "DEFAULT_MODE",
    "DEFAULT_PROMPT",
]
