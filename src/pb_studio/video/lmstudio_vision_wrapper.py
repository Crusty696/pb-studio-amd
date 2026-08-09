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
import threading
import time
from collections import defaultdict
from typing import Any, Callable, Optional

import numpy as np
from pb_studio.ai.config_loader import load_ai_config as _load_ai_config

logger = logging.getLogger(__name__)

DEFAULT_TASK = "video_captioning"
DEFAULT_MODE = "balance"

# ---------------------------------------------------------------------------
# Audit 2026-08-07: Kaltstart-Budget fuer LM Studios JIT-Load.
#
# ``timeout_seconds`` war 15.0 und galt fuer JEDEN Call. LM Studio laedt ein
# Modell aber erst beim ersten Request (JIT) — live gemessen 15.8 s fuer
# qwen3.5-9b, danach 1.2–6.2 s pro Frame. Der erste Call lief damit immer in
# den Timeout, der Failover probierte drei Kandidaten a 15 s, und das pro
# Frame: 3 Frames = 150.69 s je Clip mit dem Ergebnis "0 tags (none)".
# Kein Kandidat wurde je warm, weil jeder Ladeversuch vorher abgebrochen wurde.
#
# Der erste Call gegen ein Modell bekommt jetzt ein Ladebudget; ist das Modell
# einmal warm, gilt wieder das kurze Timeout. Das Ladebudget wird pro Modell
# und Prozess genau einmal vergeben — sonst kostet ein wirklich totes Modell
# das Vielfache des alten Zustands.
# ---------------------------------------------------------------------------
# Knapp unter DEFAULT_GENERATION_TIMEOUT (180 s) des HTTP-Clients, damit bei
# Ueberschreitung deterministisch dieser Timeout greift und nicht httpx.
DEFAULT_LOAD_TIMEOUT_SECONDS = 165.0

# Nach erschoepftem Failover ist LM Studio fuer diesen Task nachweislich nicht
# nutzbar. Ohne Sperre wiederholt jeder weitere Frame dieselbe Kette.
# Bewusst kurz: startet der Nutzer LM Studio direkt nach einem Fehlschlag, soll
# der naechste Clip wieder Tags bekommen und nicht minutenlang leer bleiben.
# Die Frames innerhalb dieses Fensters werden als "analysiert, keine Tags"
# persistiert — je laenger die Sperre, desto mehr falsch-leere Clips.
_UNAVAILABLE_COOLDOWN_SECONDS = 60.0

# Warm heisst: dieses Modell hat kuerzlich geantwortet, ohne geladen werden zu
# muessen. LM Studio entlaedt per JIT-TTL (Default 3600 s) wieder. Ein
# unbefristetes "warm" wuerde nach einer Pause genau den Zustand herstellen,
# den dieser Fix beseitigt: kaltes Modell, kurzes Timeout, Failover.
_WARM_WINDOW_SECONDS = 600.0

_WARM_MODELS: dict[tuple[str, str], float] = {}
_LOAD_BUDGET_SPENT: set[tuple[str, str]] = set()
_TASK_UNAVAILABLE_UNTIL: dict[str, float] = {}
_COLD_START_STATE_LOCK = threading.RLock()
_COLD_START_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_COLD_START_LOCK_POLL_SECONDS = 0.05


def _ist_warm_unlocked(model_key: tuple[str, str]) -> bool:
    """True, solange das Modell innerhalb des Warm-Fensters geantwortet hat."""
    zuletzt = _WARM_MODELS.get(model_key)
    if zuletzt is None:
        return False
    if time.monotonic() - zuletzt > _WARM_WINDOW_SECONDS:
        # Abgekuehlt: Warm-Status faellt weg UND das Ladebudget wird neu
        # gewaehrt, sonst laeuft der Reload in das kurze Timeout.
        _WARM_MODELS.pop(model_key, None)
        _LOAD_BUDGET_SPENT.discard(model_key)
        return False
    return True


def _ist_warm(model_key: tuple[str, str]) -> bool:
    """Thread-safe warm-state query used by concurrent analysis workers."""
    with _COLD_START_STATE_LOCK:
        return _ist_warm_unlocked(model_key)


def _cold_start_lock_for(model_key: tuple[str, str]) -> threading.Lock:
    with _COLD_START_STATE_LOCK:
        return _COLD_START_LOCKS.setdefault(model_key, threading.Lock())


async def _acquire_cold_start_lock(lock: threading.Lock) -> None:
    """Acquire a cross-thread model lock without blocking the asyncio loop."""
    while not lock.acquire(blocking=False):
        await asyncio.sleep(_COLD_START_LOCK_POLL_SECONDS)


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

# Wortschleifen-Bremse: hoechstens ``_MAX_PER_STEM`` Tags duerfen sich die
# ersten ``_STEM_LEN`` Zeichen teilen.
#
# Kurze Tags sind nicht betroffen, weil ein Tag kuerzer als _STEM_LEN seinen
# eigenen Schluessel bildet: 'tanz' und 'tanzen' kollidieren nicht.
#
# Ehrlich benannter Preis: bei drei oder mehr echten Komposita mit gleichem
# Stamm faellt das dritte weg — 'schwarz, schwarzlicht, schwarzweiss' verliert
# 'schwarzweiss'. Das ist in Kauf genommen, weil die beobachtete Alternative
# zehn Varianten desselben Wortes waren und der Informationsverlust dort
# ungleich groesser ist.
_STEM_LEN = 7
_MAX_PER_STEM = 2

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
    stem_counts: dict[str, int] = defaultdict(int)
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
        # Audit 2026-08-07: VLMs geraten bei Tag-Listen in Wortschleifen —
        # live beobachtet 'fetisch, fetischkleidung, fetischmode, fetischlook,
        # fetischtanz, fetischparty, ...' (8 von 10 Tags mit gleichem Stamm).
        # frequency_penalty daempft das, beseitigt es aber nicht zuverlaessig.
        stem = cleaned[:_STEM_LEN]
        if stem_counts[stem] >= _MAX_PER_STEM:
            continue
        stem_counts[stem] += 1
        tags.append(cleaned)
        seen.add(cleaned)
        if len(tags) >= max_tags:
            break
    if not tags and not prose:
        for word in re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE):
            if len(word) < 3 or word in _STOPWORDS or word in seen:
                continue
            # Gleiche Bremse wie oben — sonst ist dieser Pfad ein Schlupfloch.
            stem = word[:_STEM_LEN]
            if stem_counts[stem] >= _MAX_PER_STEM:
                continue
            stem_counts[stem] += 1
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
    load_timeout_seconds: float = DEFAULT_LOAD_TIMEOUT_SECONDS,
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

    now = time.monotonic()
    with _COLD_START_STATE_LOCK:
        blocked_until = _TASK_UNAVAILABLE_UNTIL.get(task)
        task_blocked = blocked_until is not None and now < blocked_until
        if blocked_until is not None and not task_blocked:
            _TASK_UNAVAILABLE_UNTIL.pop(task, None)
    if blocked_until is not None:
        if task_blocked:
            # Kein erneuter Failover-Durchlauf — der letzte hat bewiesen, dass
            # kein Kandidat liefert. Sonst zahlt jeder Frame denselben Preis.
            _publish_status("none", "LLM", "unavailable", 0.0)
            return [], "none"

    ai_cfg = _load_ai_config()
    registry = ModelRegistry(ai_cfg)

    class _NoUsableTagsError(RuntimeError):
        pass

    # Nur EIN Kandidat pro Frame darf das Ladebudget ziehen. Ohne diese Grenze
    # kostet ein einziger Frame im schlechtesten Fall 3 x load_timeout_seconds
    # — mehr als der Zustand, den dieser Fix beseitigen soll.
    budget_granted_here = False

    async def _call(
        client: LMStudioClient,
        receipt: ModelSelectionReceipt,
    ) -> list[str]:
        nonlocal budget_granted_here
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

        model_key = (receipt.provider, receipt.model_id)
        held_cold_start_lock: threading.Lock | None = None
        try:
            with _COLD_START_STATE_LOCK:
                needs_cold_start_sync = not _ist_warm_unlocked(model_key)
            if needs_cold_start_sync:
                cold_start_lock = _cold_start_lock_for(model_key)
                await _acquire_cold_start_lock(cold_start_lock)
                with _COLD_START_STATE_LOCK:
                    warmed_while_waiting = _ist_warm_unlocked(model_key)
                if warmed_while_waiting:
                    cold_start_lock.release()
                    cached = _cache_get(cache_key)
                    if cached:
                        _publish_status(
                            receipt.model_id,
                            provider_name,
                            "active",
                            100.0,
                        )
                        return list(cached)
                else:
                    held_cold_start_lock = cold_start_lock

            with _COLD_START_STATE_LOCK:
                gewaehrt_budget = (
                    not _ist_warm_unlocked(model_key)
                    and model_key not in _LOAD_BUDGET_SPENT
                    and not budget_granted_here
                )
                if gewaehrt_budget:
                    budget_granted_here = True
            if gewaehrt_budget:
                effective_timeout = max(timeout_seconds, load_timeout_seconds)
                logger.info(
                    "Kalter Vision-Call gegen %s/%s — Ladebudget %.0fs (JIT-Load).",
                    receipt.provider,
                    receipt.model_id,
                    effective_timeout,
                )
            else:
                effective_timeout = timeout_seconds

            try:
                response = await asyncio.wait_for(
                    client.chat(
                        model=receipt.model_id,
                        messages=[{"role": "user", "content": prompt}],
                        images=[frame_rgb],
                        # Kein frequency_penalty: gegen die Wortschleifen wirkt
                        # bereits _MAX_PER_STEM im Parser, und zwar deterministisch.
                        # Die Penalty wurde live gegengemessen (2 Laeufe x 3 Frames)
                        # und war schlechter — ohne sie 41 Tags/0 verklebt, mit 0.6
                        # nur 30 Tags/4 verklebt ("bewegtefiguren").
                        options={"temperature": 0.2},
                    ),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                if gewaehrt_budget:
                    # Das Ladebudget hat nicht gereicht. Kein zweiter Langlaeufer
                    # fuer dieses Modell, bis es nachweislich wieder warm war.
                    # Wichtig: NUR beim Timeout sperren — ein HTTP-500 oder ein
                    # Verbindungsabbruch sagt nichts ueber die Ladezeit aus und
                    # darf das einmalige Budget nicht verbrennen.
                    with _COLD_START_STATE_LOCK:
                        _LOAD_BUDGET_SPENT.add(model_key)
                raise
            with _COLD_START_STATE_LOCK:
                _WARM_MODELS[model_key] = time.monotonic()
                _LOAD_BUDGET_SPENT.discard(model_key)
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
        finally:
            if held_cold_start_lock is not None:
                held_cold_start_lock.release()

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
        with _COLD_START_STATE_LOCK:
            _TASK_UNAVAILABLE_UNTIL[task] = (
                time.monotonic() + _UNAVAILABLE_COOLDOWN_SECONDS
            )
        logger.warning(
            "Keine nutzbare Receipt-Auswahl für Tags: %s — Task %r fuer %.0fs "
            "gesperrt, sonst wiederholt jeder Frame dieselbe Kette.",
            exc,
            task,
            _UNAVAILABLE_COOLDOWN_SECONDS,
        )
        _publish_status("none", "LLM", "unavailable", 0.0)
        return [], "none"


async def extract_tags_and_model_via_lmstudio_async(
    frame_rgb: Optional[np.ndarray],
    *,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    prompt: str = DEFAULT_PROMPT,
    model_override: Optional[str] = None,
    # 15.0 war zu knapp: die installierten VLMs (qwen3.5-9b,
    # ministral-3-14b-reasoning) sind Reasoning-Modelle und verbrauchen vor der
    # Tag-Zeile mehrere hundert Denk-Token — warm gemessen 1.2 s bis 10.6 s je
    # nach Bildinhalt. Ein knappes Timeout wirft den Frame in den Failover,
    # obwohl das Modell laeuft.
    timeout_seconds: float = 45.0,
    load_timeout_seconds: float = DEFAULT_LOAD_TIMEOUT_SECONDS,
) -> tuple[list[str], str]:
    """Asynchrone Tag-Extraktion inkl. verwendetem Modellnamen.

    Bei Fehlern (LM Studio down, kein Modell, Timeout) -> (leere Liste, "none") +
    Warnlog. Der Aufrufer kann dann auf Moondream-Fallback umschalten.

    Args:
        frame_rgb: RGB-Frame als (H,W,3) uint8 numpy-Array.
        mode: ``speed`` / ``balance`` / ``quality`` fuer Auto-Selection.
        task: Task-Schluessel in ``ai.task_preferences`` (Default
            ``video_captioning``).
        prompt: Override fuer den Default-Prompt (deutsch).
        model_override: Wenn gesetzt, ueberspringt Auto-Selection.
        timeout_seconds: Timeout fuer einen Call gegen ein bereits warmes Modell.
        load_timeout_seconds: Einmaliges Budget fuer den ersten Call gegen ein
            Modell, das LM Studio noch laden muss (JIT). Pro Modell und Prozess
            genau einmal vergeben.

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
        return await _async_extract_tags(
            frame_rgb,
            mode=mode,
            task=task,
            prompt=prompt,
            model_override=model_override,
            timeout_seconds=timeout_seconds,
            load_timeout_seconds=load_timeout_seconds,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("LM Studio tag extraction failed: %s", exc)
        return [], "none"


def extract_tags_and_model_via_lmstudio(
    frame_rgb: Optional[np.ndarray],
    *,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    prompt: str = DEFAULT_PROMPT,
    model_override: Optional[str] = None,
    timeout_seconds: float = 45.0,
    load_timeout_seconds: float = DEFAULT_LOAD_TIMEOUT_SECONDS,
) -> tuple[list[str], str]:
    """Synchrone CLI-/Legacy-Fassade fuer die asynchrone Extraktion."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        logger.warning(
            "Sync Vision-API in laufendem Eventloop abgelehnt; "
            "extract_tags_and_model_via_lmstudio_async verwenden"
        )
        return [], "none"
    try:
        return asyncio.run(
            extract_tags_and_model_via_lmstudio_async(
                frame_rgb,
                mode=mode,
                task=task,
                prompt=prompt,
                model_override=model_override,
                timeout_seconds=timeout_seconds,
                load_timeout_seconds=load_timeout_seconds,
            )
        )
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
    """Test-Helper: leert Tag-Cache, Warm-Status und Task-Sperre."""
    _TAG_CACHE.clear()
    with _COLD_START_STATE_LOCK:
        _WARM_MODELS.clear()
        _LOAD_BUDGET_SPENT.clear()
        _TASK_UNAVAILABLE_UNTIL.clear()
        _COLD_START_LOCKS.clear()


# Backwards-compatibility-Alias: alter Name funktioniert noch (Deprecated).
# Wird im naechsten Major-Cleanup entfernt.
extract_tags_via_ollama = extract_tags_via_lmstudio


__all__ = [
    "extract_tags_and_model_via_lmstudio_async",
    "extract_tags_and_model_via_lmstudio",
    "extract_tags_via_lmstudio",
    "extract_tags_via_ollama",  # deprecated alias
    "clear_tag_cache",
    "DEFAULT_TASK",
    "DEFAULT_MODE",
    "DEFAULT_PROMPT",
]
