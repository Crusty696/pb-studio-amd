"""Ollama-Vision-Wrapper fuer Video-Frame Tag-Extraktion.

Ersetzt ``extract_tags_via_moondream`` (Phase 4 / L-K2) durch einen
Ollama-Call gegen ein installiertes Vision-Modell (Auto-Selection via
``ModelRegistry``). Moondream bleibt als Fallback im
``backend.routers.video_router`` erhalten.

Diese Schicht ist bewusst syncron — Phase 4 laeuft schon im Thread-Pool,
und der Aufrufer (`_run_video_analysis`) ist eine reine sync-Funktion.
Wir betreiben den ``asyncio``-Loop intern (`asyncio.run`) damit das HTTP
nicht blockiert wird.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_TASK = "video_captioning"
DEFAULT_MODE = "balance"

# Deutscher Prompt — Tags kommagetrennt, knapp, keine Erklaerung.
DEFAULT_PROMPT = (
    "Analysiere dieses Video-Frame. Gib 5-10 praegnante Tags zurueck, "
    "kommagetrennt, deutsch. Beispiel: 'tanzen, club, neonlicht, gruppe, "
    "energetisch'. Nur die Tags, keine Erklaerung, keine Aufzaehlung mit "
    "Nummern."
)

_STOPWORDS = frozenset({
    "und", "oder", "die", "der", "das", "ein", "eine", "ist", "sind", "war",
    "mit", "ohne", "im", "in", "an", "auf", "von", "fuer", "auch",
    "image", "picture", "photo", "frame", "bild", "szene", "scene",
})


def _parse_tags(raw: str, *, max_tags: int = 10) -> list[str]:
    """Parsed kommagetrennte (oder Zeilen-getrennte) Tags zu sauberer Liste.

    Defensive: Ollama-Modelle koennen Bullet-Listen, Punkte am Ende, etc.
    liefern. Wir extrahieren bis zu ``max_tags`` lowercased Tokens, gefiltert
    nach Stopwords + Mindestlaenge.
    """
    if not raw:
        return []
    text = raw.strip()
    # Falls Modell mit ``"Tags: ..."``-Praefix antwortet, abschneiden.
    for prefix in ("tags:", "ergebnis:", "antwort:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    # Split: Komma -> dann Zeilenumbruch als Fallback
    parts: list[str] = []
    for chunk in text.replace("\n", ",").split(","):
        parts.append(chunk.strip())
    tags: list[str] = []
    seen: set[str] = set()
    for part in parts:
        # entferne fuehrende Bulletpoints/Nummern (-, *, 1., usw.)
        cleaned = part.lstrip("-*0123456789. )").strip(".;:!?\"'()[]")
        cleaned = cleaned.strip().lower()
        if not cleaned or len(cleaned) < 3:
            continue
        if cleaned in _STOPWORDS or cleaned in seen:
            continue
        # Nur wenn es ueberwiegend Wortzeichen enthaelt
        if not any(c.isalpha() for c in cleaned):
            continue
        # Mehr-Wort-Tags begrenzen
        if len(cleaned.split()) > 4:
            continue
        tags.append(cleaned)
        seen.add(cleaned)
        if len(tags) >= max_tags:
            break
    return tags


def _frame_hash(frame_rgb: np.ndarray) -> str:
    """Kurzer Inhalts-Hash fuer Cache-Key (32-Pixel-Downsample, blake2b)."""
    try:
        small = frame_rgb[::max(1, frame_rgb.shape[0] // 32), :: max(1, frame_rgb.shape[1] // 32)]
        return hashlib.blake2b(small.tobytes(), digest_size=8).hexdigest()
    except Exception:
        return hashlib.blake2b(frame_rgb.tobytes(), digest_size=8).hexdigest()


# Sehr leichter In-Memory-Cache (process-lifetime).
# Key = (frame_hash, model, mode), Value = list[str].
_TAG_CACHE: dict[tuple[str, str, str], list[str]] = {}
_CACHE_MAX = 256


def _cache_get(key: tuple[str, str, str]) -> Optional[list[str]]:
    return _TAG_CACHE.get(key)


def _cache_put(key: tuple[str, str, str], value: list[str]) -> None:
    if len(_TAG_CACHE) >= _CACHE_MAX:
        # LRU-ish: einfach den ersten Eintrag entfernen
        try:
            _TAG_CACHE.pop(next(iter(_TAG_CACHE)))
        except StopIteration:
            pass
    _TAG_CACHE[key] = list(value)


def _load_ai_config() -> dict[str, Any]:
    """Liest die ``ai``-Sektion aus ``config.json`` (best-effort)."""
    try:
        from pb_studio.config_manager import ConfigManager

        cfg = ConfigManager()
        ai_section = cfg.get("ai") or {}
        if isinstance(ai_section, dict):
            return ai_section
    except Exception as exc:
        logger.debug("config_manager nicht verfuegbar: %s", exc)
    # Fallback: config.json direkt lesen (Test-Fixtures patchen ConfigManager)
    try:
        root = Path(__file__).resolve().parents[3]
        cfg_file = root / "config.json"
        if cfg_file.exists():
            with cfg_file.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            ai = data.get("ai") or {}
            if isinstance(ai, dict):
                return ai
    except Exception as exc:
        logger.debug("config.json direct-read fehlgeschlagen: %s", exc)
    return {}


async def _async_extract_tags(
    frame_rgb: np.ndarray,
    *,
    mode: str,
    task: str,
    prompt: str,
    model_override: Optional[str],
    timeout_seconds: float,
) -> list[str]:
    from pb_studio.ai.model_registry import (
        ModelRegistry,
        NoSuitableModelError,
    )
    from pb_studio.ai.ollama_client import OllamaClient, OllamaError

    ai_cfg = _load_ai_config()

    async with OllamaClient(timeout_seconds=timeout_seconds) as client:
        registry = ModelRegistry(ai_cfg, client=client)
        try:
            await registry.refresh()
        except OllamaError as exc:
            logger.warning("Ollama nicht erreichbar — keine Tags: %s", exc)
            return []

        if model_override:
            model = model_override
        else:
            try:
                model = registry.select_best_for_task(task, mode)
            except NoSuitableModelError as exc:
                logger.warning("Keine Modell-Auswahl fuer Tags: %s", exc)
                return []

        cache_key = (_frame_hash(frame_rgb), model, mode)
        cached = _cache_get(cache_key)
        if cached is not None:
            return list(cached)

        try:
            response = await client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                images=[frame_rgb],
                options={"temperature": 0.2},
            )
        except OllamaError as exc:
            logger.warning("Ollama chat fehlgeschlagen (Tags): %s", exc)
            return []

        message = response.get("message") or {}
        raw = message.get("content") or response.get("response") or ""
        tags = _parse_tags(str(raw))
        _cache_put(cache_key, tags)
        return tags


def extract_tags_via_ollama(
    frame_rgb: Optional[np.ndarray],
    *,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    prompt: str = DEFAULT_PROMPT,
    model_override: Optional[str] = None,
    timeout_seconds: float = 60.0,
) -> list[str]:
    """Synchrone Tag-Extraktion via Ollama-Vision-Modell.

    Bei Fehlern (Ollama down, kein Modell, Timeout) -> leere Liste +
    Warnlog. Der Aufrufer kann dann auf Moondream-Fallback umschalten.

    Args:
        frame_rgb: RGB-Frame als (H,W,3) uint8 numpy-Array.
        mode: ``speed`` / ``balance`` / ``quality`` fuer Auto-Selection.
        task: Task-Schluessel in ``ai.task_preferences`` (Default
            ``video_captioning``).
        prompt: Override fuer den Default-Prompt (deutsch).
        model_override: Wenn gesetzt, ueberspringt Auto-Selection.
        timeout_seconds: HTTP-Timeout fuer den Chat-Call.

    Returns:
        Liste von max 10 Tags (lowercased, Stopwords gefiltert).
    """
    if frame_rgb is None:
        return []
    try:
        if frame_rgb.size == 0:
            return []
    except AttributeError:
        return []

    try:
        return asyncio.run(
            _async_extract_tags(
                frame_rgb,
                mode=mode,
                task=task,
                prompt=prompt,
                model_override=model_override,
                timeout_seconds=timeout_seconds,
            )
        )
    except RuntimeError as exc:
        # Falls schon ein Loop laeuft (z.B. innerhalb von async-Tests),
        # nutze get_event_loop + run_until_complete in einem neuen Loop.
        logger.debug("asyncio.run nicht moeglich (%s) — fallback loop", exc)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                _async_extract_tags(
                    frame_rgb,
                    mode=mode,
                    task=task,
                    prompt=prompt,
                    model_override=model_override,
                    timeout_seconds=timeout_seconds,
                )
            )
        except Exception as inner:
            logger.warning("Ollama tag extraction failed: %s", inner)
            return []
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("Ollama tag extraction failed: %s", exc)
        return []


def clear_tag_cache() -> None:
    """Test-Helper: leert den prozesslokalen Tag-Cache."""
    _TAG_CACHE.clear()
