"""DEPRECATED - durch pb_studio.ai.lmstudio_client ersetzt.

Im Zuge des LM-Studio-Refactors am 2026-05-17 wurde der Ollama-spezifische
HTTP-Client (/api/tags, /api/chat) durch den OpenAI-kompatiblen
LM-Studio-Client (/v1/models, /v1/chat/completions) ersetzt.

Diese Datei bleibt nur als Deprecation-Shim zurueck - sie re-exportiert die
Aequivalente aus lmstudio_client, damit Legacy-Aufrufer beim Import nicht
sofort brechen. Im naechsten Major-Cleanup wird sie entfernt.

Aktuelle Aufrufer sollen direkt aus pb_studio.ai.lmstudio_client importieren.
"""
from __future__ import annotations

import warnings

from .lmstudio_client import (  # noqa: F401
    LMStudioClient as OllamaClient,
    LMStudioConnectionError as OllamaConnectionError,
    LMStudioError as OllamaError,
    LMStudioModelInfo as OllamaModelInfo,
    LMStudioResponseError as OllamaResponseError,
)

warnings.warn(
    "pb_studio.ai.ollama_client ist deprecated - bitte "
    "pb_studio.ai.lmstudio_client importieren.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "OllamaClient",
    "OllamaError",
    "OllamaConnectionError",
    "OllamaResponseError",
    "OllamaModelInfo",
]
