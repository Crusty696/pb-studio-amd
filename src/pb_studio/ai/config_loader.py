"""Shared best-effort readers for AI configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_ai_config(*, fallback_path: Path | None = None) -> dict[str, Any]:
    """Return the ``ai`` section, preferring the cached ConfigManager."""
    try:
        from pb_studio.config_manager import ConfigManager

        ai_section = ConfigManager().get("ai") or {}
        if isinstance(ai_section, dict):
            return ai_section
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("config_manager nicht verfuegbar: %s", exc)

    config_path = fallback_path or Path(__file__).resolve().parents[3] / "config.json"
    try:
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            ai_section = data.get("ai") or {}
            if isinstance(ai_section, dict):
                return ai_section
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("config.json direct-read fehlgeschlagen: %s", exc)
    return {}
