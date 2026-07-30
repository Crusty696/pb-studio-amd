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
import re
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
    "einen", "einem", "einer", "eines", "mit", "ohne", "im", "in", "an",
    "auf", "von", "fuer", "auch", "zeigt", "zeigen",
    "image", "picture", "photo", "frame", "bild", "szene", "scene",
    "the", "and", "or", "a", "an", "is", "are", "was", "with", "without",
    "of", "to", "as", "it", "this", "that", "be", "can", "which", "while",
    "show", "shows", "showing", "depicts", "depicting",
})

_INVALID_RESPONSE_PATTERNS = (
    re.compile(r"\b(?:sorry|cannot|can['’]t|unable\s+to|not\s+able\s+to)\b", re.IGNORECASE),
    re.compile(r"\b(?:tut\s+mir\s+leid|entschuldigung|nicht\s+in\s+der\s+lage)\b", re.IGNORECASE),
    re.compile(r"\bich\s+kann\b.{0,80}\bnicht\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*(?:error|fehler)\s*:", re.IGNORECASE),
    re.compile(
        r"\b(?:no\s+image\s+(?:was\s+)?(?:provided|attached|available)|"
        r"kein\s+bild\s+(?:bereitgestellt|angehaengt|verfuegbar))\b",
        re.IGNORECASE,
    ),
)
_INVALID_RESPONSES = frozenset({
    "none", "n/a", "null", "no tags", "keine tags", "keine",
})


def _is_invalid_response(text: str) -> bool:
    normalized = " ".join(text.lower().split()).strip(" .!?:;\"'()[]")
    if not normalized or normalized in _INVALID_RESPONSES:
        return True
    return any(pattern.search(text) for pattern in _INVALID_RESPONSE_PATTERNS)


def _looks_like_prose(
    text: str,
    parts: list[str],
    *,
    has_list_prefix: bool,
) -> bool:
    if has_list_prefix or re.search(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", text):
        return False
    word_counts = [
        len(re.findall(r"[^\W\d_]+", part, flags=re.UNICODE))
        for part in parts
    ]
    return (
        any(count > 4 for count in word_counts)
        or (
            bool(re.search(r"[.!?]\s*$", text))
            and sum(word_counts) > 2
        )
    )


def _parse_tags(raw: str, *, max_tags: int = 10) -> list[str]:
    """Parsed kommagetrennte (oder Zeilen-getrennte) Tags zu sauberer Liste.

    Defensive: Vision-Modelle koennen Bullet-Listen, Punkte am Ende, etc.
    liefern. Wir extrahieren bis zu ``max_tags`` lowercased Tokens, gefiltert
    nach Stopwords + Mindestlaenge.
    """
    if not raw:
        return []
    text = raw.strip()
    if _is_invalid_response(text):
        return []
    # Falls Modell mit ``"Tags: ..."``-Praefix antwortet, abschneiden.
    has_list_prefix = False
    for prefix in ("tags:", "ergebnis:", "antwort:"):
        if text.lower().startswith(prefix):
            has_list_prefix = True
            text = text[len(prefix):].strip()
            break
    # Split: Komma -> dann Zeilenumbruch als Fallback
    parts = [chunk.strip() for chunk in text.replace("\n", ",").split(",")]
    tags: list[str] = []
    seen: set[str] = set()
    prose = _looks_like_prose(text, parts, has_list_prefix=has_list_prefix)
    candidates = (
        re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
        if prose
        else parts
    )
    for candidate in candidates:
        # entferne fuehrende Bulletpoints/Nummern (-, *, 1., usw.)
        cleaned = candidate.lstrip("-*0123456789. )").strip(".;:!?\"'()[]")
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
    if not tags and not prose:
        for word in re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE):
            if len(word) < 3 or word in _STOPWORDS or word in seen:
                continue
            tags.append(word)
            seen.add(word)
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
    if not value:
        return
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
        ModelFailoverExhaustedError,
        ModelRegistry,
        ModelSelectionReceipt,
        execute_with_model_failover,
    )
    from pb_studio.ai.lmstudio_client import (
        LMStudioClient,
        LMStudioError,
        is_provider_failure,
    )

    ai_cfg = _load_ai_config()
    registry = ModelRegistry(ai_cfg)

    class _NoUsableTagsError(RuntimeError):
        pass

    async def _call(
        client: LMStudioClient,
        receipt: ModelSelectionReceipt,
    ) -> list[str]:
        provider_name = (
            "Ollama" if receipt.provider == "ollama" else "LM Studio"
        )
        cache_key = (
            _frame_hash(frame_rgb),
            f"{receipt.provider}:{receipt.model_id}",
            mode,
        )
        cached = _cache_get(cache_key)
        if cached:
            _publish_status(receipt.model_id, provider_name, "active", 100.0)
            return list(cached)
        _publish_status(receipt.model_id, provider_name, "loading", 25.0)
        response = await asyncio.wait_for(
            client.chat(
                model=receipt.model_id,
                messages=[{"role": "user", "content": prompt}],
                images=[frame_rgb],
                options={"temperature": 0.2},
            ),
            timeout=timeout_seconds,
        )
        message = response.get("message") or {}
        raw = message.get("content") or response.get("response") or ""
        tags = _parse_tags(str(raw))
        if not tags:
            _publish_status(receipt.model_id, provider_name, "failed", 0.0)
            raise _NoUsableTagsError(
                f"Vision-Modell {receipt.model_id!r} lieferte keine nutzbaren Tags"
            )
        _cache_put(cache_key, tags)
        _publish_status(receipt.model_id, provider_name, "active", 100.0)
        return tags

    try:
        tags, receipt, _attempts = await execute_with_model_failover(
            registry,
            task,
            mode,
            _call,
            is_retryable=lambda exc: isinstance(
                exc,
                (asyncio.TimeoutError, LMStudioError, _NoUsableTagsError),
            ),
            is_provider_failure=is_provider_failure,
            explicit_model=model_override,
        )
        return tags, receipt.model_id
    except ModelFailoverExhaustedError as exc:
        logger.warning("Keine nutzbare Receipt-Auswahl für Tags: %s", exc)
        _publish_status("none", "LLM", "unavailable", 0.0)
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
