"""LM-Studio-Vision-Wrapper fuer Video-Frame Tag-Extraktion.

Ersetzt den frueheren ``ollama_vision_wrapper`` (Phase 4 / L-K2). Ruft ein
LM-Studio-Vision-Modell via OpenAI-kompatibler REST-API auf
(Auto-Selection via ``ModelRegistry`` — default Praeferenz ist
``qwen/qwen3-vl-8b``). Moondream bleibt als Fallback im
``backend.routers.video_router`` erhalten.

Diese Schicht ist bewusst syncron — Phase 4 laeuft schon im Thread-Pool,
und der Aufrufer (`_run_video_analysis`) ist eine reine sync-Funktion.
Wir betreiben den ``asyncio``-Loop intern (`asyncio.run`) damit das HTTP
nicht blockiert wird.

Iron Rule 1: AMD DirectML only — LM Studio nutzt Vulkan-Runtime (RX 7800 XT
verifiziert 2026-05-17). Kein ROCm/CUDA.
Iron Rule 10: Bei Fehler leere Liste + Warnlog, KEIN silent OK.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Callable, Optional

import numpy as np
from pb_studio.ai.config_loader import load_ai_config as _load_ai_config

logger = logging.getLogger(__name__)

DEFAULT_TASK = "video_captioning"
DEFAULT_MODE = "balance"

# Review-Fix 2026-07-09: injizierbarer Status-Publisher statt Direktimport von
# backend.dependencies (Layering-Inversion). Backend wired beim Startup
# publish_event_threadsafe hier ein; ohne Wiring (pytest, CLI) -> no-op.
_status_publisher: Callable[[str, dict[str, Any]], None] | None = None


def set_status_publisher(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    global _status_publisher
    _status_publisher = fn


def _publish_status(model: str, provider: str, status: str, percent: float) -> None:
    """Best-effort llm_status-Event. Darf NIE die Tag-Extraktion abbrechen."""
    fn = _status_publisher
    if fn is None:
        return
    try:
        fn("llm_status", {
            "model": model,
            "provider": provider,
            "status": status,
            "percent": percent,
        })
    except Exception as exc:  # noqa: BLE001 - Status ist rein kosmetisch
        logger.debug("llm_status publish fehlgeschlagen: %s", exc)

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

    Defensive: Vision-Modelle koennen Bullet-Listen, Punkte am Ende, etc.
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


async def _async_extract_tags(
    frame_rgb: np.ndarray,
    *,
    mode: str,
    task: str,
    prompt: str,
    model_override: Optional[str],
    timeout_seconds: float,
) -> tuple[list[str], str]:
    from pb_studio.ai.model_registry import (
        ModelRegistry,
        NoSuitableModelError,
    )
    from pb_studio.ai.lmstudio_client import LMStudioClient, LMStudioError

    ai_cfg = _load_ai_config()

    # W-QA-2 (2026-05-22): Hybrid-Auto-Fallback fuer Video-Captioning. Vorher
    # hartcodiert LMStudioClient() default-URL → kein Tag-Capture wenn nur
    # Ollama up war. get_alive_client probiert beide.
    from pb_studio.ai.llm_provider import get_alive_client, get_llm_client, get_provider

    if get_provider() == "auto":
        client = await get_alive_client(
            timeout_seconds=min(timeout_seconds, 5.0),
            required_capability="vision",
        )
        if client is None:
            logger.warning("Kein Provider mit nutzbarem Vision-Modell verfuegbar")
            _publish_status("none", "LLM", "unavailable", 0.0)
            return [], "none"
    else:
        client = get_llm_client(timeout_seconds=timeout_seconds)

    # Review-Fix LOW (2026-07-09): Provider-Name VOR registry.refresh, damit
    # auch der Provider-down-Fall ein failed-Event senden kann.
    base_url_lower = client.base_url.lower()
    is_ollama = "11434" in base_url_lower or "ollama" in base_url_lower
    provider_name = "Ollama" if is_ollama else "LM Studio"

    async with client:
        registry = ModelRegistry(ai_cfg, client=client)
        try:
            await registry.refresh()
        except LMStudioError as exc:
            logger.warning("LLM-Provider nicht erreichbar - keine Tags: %s", exc)
            _publish_status("none", provider_name, "failed", 0.0)
            return [], "none"

        exclude_models = set()
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            if model_override:
                if not registry.is_model_capable(model_override, "vision"):
                    logger.warning(
                        "Vision-Override %r ist nicht installiert oder nicht vision-faehig",
                        model_override,
                    )
                    _publish_status(model_override, provider_name, "unavailable", 0.0)
                    return [], "none"
                model = model_override
            else:
                try:
                    model = registry.select_best_for_task(task, mode, exclude=exclude_models)
                except NoSuitableModelError as exc:
                    logger.warning("Keine Modell-Auswahl fuer Tags: %s", exc)
                    _publish_status("none", provider_name, "unavailable", 0.0)
                    return [], "none"

            # Review-Fix LOW (2026-07-09): Cache-Lookup VOR loading-Event —
            # Cache-Hits erzeugen sonst pro Frame ein loading/active-Flicker.
            cache_key = (_frame_hash(frame_rgb), model, mode)
            cached = _cache_get(cache_key)
            if cached is not None:
                _publish_status(model, provider_name, "active", 100.0)
                return list(cached), model

            _publish_status(model, provider_name, "loading", 25.0)

            try:
                # C-F3: Hard 15s timeout wrapper for the chat call to prevent hangs
                response = await asyncio.wait_for(
                    client.chat(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        images=[frame_rgb],
                        options={"temperature": 0.2},
                    ),
                    timeout=timeout_seconds
                )
                message = response.get("message") or {}
                raw = message.get("content") or response.get("response") or ""
                tags = _parse_tags(str(raw))
                _cache_put(cache_key, tags)

                _publish_status(model, provider_name, "active", 100.0)
                return tags, model
            except asyncio.TimeoutError as exc:
                logger.warning("LM Studio Chat-Timeout (%ss) erreicht mit Modell '%s': %s", timeout_seconds, model, exc)
                _publish_status(model, provider_name, "failed", 0.0)
                if model_override:
                    # Bei explizitem Override macht ein Fallback keinen Sinn
                    return [], model
                # Modell ausschließen und nächstes versuchen
                logger.info("Schliesse Modell '%s' wegen Timeout aus und versuche das naechste...", model)
                exclude_models.add(model)
            except LMStudioError as exc:
                logger.warning("LM Studio chat mit Modell '%s' fehlgeschlagen (Tags): %s", model, exc)
                _publish_status(model, provider_name, "failed", 0.0)
                if model_override:
                    # Bei explizitem Override macht ein Fallback keinen Sinn
                    return [], model
                # Modell ausschließen und nächstes versuchen
                logger.info("Schliesse Modell '%s' aus und versuche das naechste geeignete Modell...", model)
                exclude_models.add(model)

        return [], "none"


def extract_tags_and_model_via_lmstudio(
    frame_rgb: Optional[np.ndarray],
    *,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    prompt: str = DEFAULT_PROMPT,
    model_override: Optional[str] = None,
    timeout_seconds: float = 15.0,
) -> tuple[list[str], str]:
    """Synchrone Tag-Extraktion via LM-Studio-Vision-Modell inkl. verwendetem Modellnamen.

    Bei Fehlern (LM Studio down, kein Modell, Timeout) -> (leere Liste, "none") +
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
        Tuple aus:
            - Liste von max 10 Tags (lowercased, Stopwords gefiltert)
            - Name des benutzten Modells (z.B. "qwen3-vl-8b" oder "none")
    """
    if frame_rgb is None:
        return [], "none"
    try:
        if frame_rgb.size == 0:
            return [], "none"
    except AttributeError:
        return [], "none"

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
            logger.warning("LM Studio tag extraction failed: %s", inner)
            return [], "none"
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("LM Studio tag extraction failed: %s", exc)
        return [], "none"


def extract_tags_via_lmstudio(
    frame_rgb: Optional[np.ndarray],
    *,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    prompt: str = DEFAULT_PROMPT,
    model_override: Optional[str] = None,
    timeout_seconds: float = 60.0,
) -> list[str]:
    """Synchrone Tag-Extraktion via LM-Studio-Vision-Modell (Abwaertskompatibel).

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
    tags, _ = extract_tags_and_model_via_lmstudio(
        frame_rgb,
        mode=mode,
        task=task,
        prompt=prompt,
        model_override=model_override,
        timeout_seconds=timeout_seconds,
    )
    return tags


def clear_tag_cache() -> None:
    """Test-Helper: leert den prozesslokalen Tag-Cache."""
    _TAG_CACHE.clear()


# Backwards-compatibility-Alias: alter Name funktioniert noch (Deprecated).
# Wird im naechsten Major-Cleanup entfernt.
extract_tags_via_ollama = extract_tags_via_lmstudio


__all__ = [
    "extract_tags_via_lmstudio",
    "extract_tags_via_ollama",  # deprecated alias
    "clear_tag_cache",
    "DEFAULT_TASK",
    "DEFAULT_MODE",
    "DEFAULT_PROMPT",
]
