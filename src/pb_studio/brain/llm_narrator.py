"""LLM-Narrator fuer das Brain-Modul.

Liefert eine natuerlichsprachliche Erklaerung fuer einen Cut, basierend auf den
strukturierten Achsen-Scores aus ``BrainExplainResponse``. Augmentiert die
Beta-Bernoulli-Logik, ohne sie anzutasten — bei LM-Studio-Fehler oder Timeout
liefert die Funktion ``None`` und der Caller faellt auf die rein strukturierte
Anzeige zurueck (Iron Rule 10 / 100 % Honesty).

Beispiel-Output (DE):
    "Dieser Cut funktioniert besonders gut, weil der Schnittpunkt genau auf
    dem Beat liegt und die Bewegung mit der Audio-Hookline laeuft. Die
    Stimmungs-Anpassung koennte etwas dichter sein."

Architektur:
    Brain-Endpoint -> generate_explanation(...) -> ModelRegistry-Auswahl
    -> LMStudioClient.chat(...) -> Text-Parsing + Cache (per cut_id, content_hash, mode).

Iron Rules:
    * Iron Rule 1: AMD DirectML only — LM Studio laeuft als externer Daemon
      mit Vulkan-Runtime (RX 7800 XT), kein CUDA.
    * Iron Rule 10: Bei Fehler ``None`` zurueckgeben + Warnlog, KEIN silent OK.
    * Iron Rule 13: Helper fuer das Brain-Modul; tastet die Beta-Bernoulli-
      Logik / WeightStore / Scorer nicht an.

LM Studio Refactor 2026-05-17: Drop-in von ``OllamaClient`` auf
``LMStudioClient``. API-Surface (chat-Methode) ist identisch — kein
Logik-Change, nur Imports.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Callable, Optional

from pb_studio.ai.config_loader import load_ai_config as _load_ai_config

logger = logging.getLogger(__name__)

# Audit-Fix (2026-07-10): gleiches injizierbares Publisher-Pattern wie
# lmstudio_vision_wrapper.py / chat_agent.py, damit die WPF-Statusleiste
# auch bei Brain-Explain-LLM-Calls reagiert.
_status_publisher: Callable[[str, dict[str, Any]], None] | None = None


def set_status_publisher(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    global _status_publisher
    _status_publisher = fn


def _publish_status(model: str, status: str, percent: float) -> None:
    """Best-effort llm_status-Event. Darf NIE die Explain-Generierung abbrechen."""
    fn = _status_publisher
    if fn is None:
        return
    try:
        fn("llm_status", {
            "model": model,
            "provider": "LM Studio",
            "status": status,
            "percent": percent,
        })
    except Exception as exc:  # noqa: BLE001 - Status ist rein kosmetisch
        logger.debug("llm_status publish fehlgeschlagen: %s", exc)

DEFAULT_TASK = "brain_explanation"
DEFAULT_MODE = "balance"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TOKENS = 220
DEFAULT_TEMPERATURE = 0.4
CACHE_MAX = 512

# Prompt-Template (DE). Wir bauen daraus einen System+User-Pair.
SYSTEM_PROMPT = (
    "Du bist ein erfahrener Video-Editor. Du erklaerst kurz und verstaendlich, "
    "warum ein bestimmter Cut zu Audio passt oder eben nicht. Du verwendest "
    "keine Fachbegriffe wie 'Achsen', 'Score' oder 'Posterior', sondern "
    "beschreibst nur, was der Zuschauer wahrnimmt: Beat, Bewegung, Stimmung, "
    "Energie, Bildkomposition."
)

USER_PROMPT_TEMPLATE = (
    "Hier sind die Daten fuer den Cut:\n"
    "- Segment-Typ: {segment_type}\n"
    "- Wichtigste Staerken: {strengths}\n"
    "- Wichtigste Schwaechen: {weaknesses}\n"
    "- Gesamt-Anpassung: {final_pct} %\n"
    "{cold_start_hint}"
    "\n"
    "Antworte mit genau zwei Saetzen auf Deutsch.\n"
    "Erster Satz: warum dieser Cut funktioniert (oder funktionieren wuerde).\n"
    "Zweiter Satz: was eventuell besser sein koennte.\n"
    "Keine Fachbegriffe, keine Auflistungen, keine Klammern, keine "
    "Prozentangaben."
)


# Sehr leichter Prozess-lokaler Cache (LRU-ish).
# Key = (cut_id, content_hash, mode), Value = narrative-Text.
_NARRATIVE_CACHE: dict[tuple[int, str, str], str] = {}


def _cache_get(key: tuple[int, str, str]) -> Optional[str]:
    return _NARRATIVE_CACHE.get(key)


def _cache_put(key: tuple[int, str, str], value: str) -> None:
    if len(_NARRATIVE_CACHE) >= CACHE_MAX:
        # einfache FIFO-Eviction
        try:
            _NARRATIVE_CACHE.pop(next(iter(_NARRATIVE_CACHE)))
        except StopIteration:
            pass
    _NARRATIVE_CACHE[key] = str(value)


def clear_narrative_cache() -> None:
    """Test-Helper: leert den Cache vollstaendig."""
    _NARRATIVE_CACHE.clear()


def _humanize_axis(axis: str) -> str:
    """Kosmetische Umsetzung Achsenname -> menschlicher Begriff."""
    mapping = {
        "beat_align_strength": "Schnitt auf Beat",
        "kick_weight": "Kick-Druck",
        "motion_match": "Bewegungs-Anpassung",
        "energy_match": "Energie-Anpassung",
        "mood_match": "Stimmungs-Anpassung",
        "color_match": "Farb-Stimmung",
        "section_match": "Strukturwechsel",
        "tempo_match": "Tempo-Anpassung",
        "lyric_match": "Text-Bezug",
        "instrument_match": "Instrument-Bezug",
        "pace_match": "Schnittfrequenz",
        "spectral_match": "Klangbild",
        "scene_match": "Szenen-Wechsel",
        "subpos_match": "Subdivision-Position",
        "max_clip_length": "Cut-Laenge",
        "min_clip_length": "Cut-Laenge",
        "structure_match": "Song-Aufbau",
    }
    return mapping.get(axis, axis.replace("_", " "))


def _format_axis_list(
    items: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> str:
    """Formatiert top/bottom-axes als kurze, lesbare Aufzaehlung fuer den Prompt."""
    if not items:
        return "(keine)"
    chosen = items[:limit]
    parts: list[str] = []
    for it in chosen:
        axis = str(it.get("axis", "?"))
        score = float(it.get("score", 0.0) or 0.0)
        pct = max(0, min(100, int(round(score * 100))))
        parts.append(f"{_humanize_axis(axis)} ({pct} %)")
    return ", ".join(parts)


def _build_user_prompt(
    *,
    segment_type: Optional[str],
    top_axes: list[dict[str, Any]],
    bottom_axes: list[dict[str, Any]],
    cold_start_axes: list[str],
    final_score: float,
) -> str:
    strengths = _format_axis_list(top_axes, limit=3)
    weaknesses = _format_axis_list(bottom_axes, limit=3)
    final_pct = max(0, min(100, int(round(float(final_score) * 100))))
    if cold_start_axes:
        cold_count = len(cold_start_axes)
        cold_hint = (
            f"- Hinweis: {cold_count} Dimension(en) sind noch nicht gelernt "
            "(Cold-Start); halte die Aussage hier vorsichtig.\n"
        )
    else:
        cold_hint = ""
    return USER_PROMPT_TEMPLATE.format(
        segment_type=segment_type or "unbekannt",
        strengths=strengths,
        weaknesses=weaknesses,
        final_pct=final_pct,
        cold_start_hint=cold_hint,
    )


def _content_hash(
    *,
    segment_type: Optional[str],
    top_axes: list[dict[str, Any]],
    bottom_axes: list[dict[str, Any]],
    final_score: float,
) -> str:
    """Stabiler Hash ueber die fuer das Narrativ relevanten Eingaben.

    Wir runden Scores auf 2 Nachkommastellen, damit minimale Float-Schwankungen
    den Cache nicht entwerten.
    """
    payload = {
        "segment_type": segment_type or "",
        "top": [
            {"axis": a.get("axis"), "score": round(float(a.get("score", 0.0)), 2)}
            for a in (top_axes or [])
        ],
        "bottom": [
            {"axis": a.get("axis"), "score": round(float(a.get("score", 0.0)), 2)}
            for a in (bottom_axes or [])
        ],
        "final": round(float(final_score or 0.0), 2),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=8).hexdigest()


def _post_process_narrative(raw: str) -> str:
    """Saeubert die LLM-Antwort: Whitespace, Praefixe, max 2 Saetze."""
    text = (raw or "").strip()
    if not text:
        return ""
    # Bekannte Praefixe wegschneiden.
    for prefix in ("antwort:", "ergebnis:", "narrativ:", "kommentar:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    # Markdown-Code-Blocks / Anfuehrungszeichen entfernen.
    text = text.strip().strip("`")
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1].strip()
    # Vermeide Aufzaehlungs-Marker am Zeilenanfang.
    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            line = line.lstrip("-*• ").strip()
        if line:
            cleaned_lines.append(line)
    text = " ".join(cleaned_lines).strip()
    if not text:
        return ""
    # Hartes Limit von ~3 Saetzen, damit der Tooltip kompakt bleibt.
    # Wir koennen nicht zuverlaessig in mehreren Sprachen splitten — heuristisch
    # auf Punkt+Leerzeichen.
    parts = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in ".!?":
            parts.append("".join(buf).strip())
            buf = []
    if buf:
        parts.append("".join(buf).strip())
    parts = [p for p in parts if p]
    if len(parts) > 3:
        parts = parts[:3]
    return " ".join(parts).strip()


async def _async_generate_explanation(
    *,
    cut_id: int,
    segment_type: Optional[str],
    top_axes: list[dict[str, Any]],
    bottom_axes: list[dict[str, Any]],
    cold_start_axes: list[str],
    final_score: float,
    mode: str,
    task: str,
    model_override: Optional[str],
    timeout_seconds: float,
    client: Optional[Any] = None,
) -> Optional[str]:
    """Async-Variante. Returnt ``None`` bei jedem nicht-recoverable Fehler."""
    # Late imports — wir wollen Brain-Tests nicht zwingen, den ganzen
    # LM-Studio-Stack zu laden.
    from pb_studio.ai.model_registry import (
        ModelRegistry,
        ModelRegistryError,
        NoSuitableModelError,
    )
    from pb_studio.ai.lmstudio_client import LMStudioClient, LMStudioError

    ai_cfg = _load_ai_config()
    chash = _content_hash(
        segment_type=segment_type,
        top_axes=top_axes,
        bottom_axes=bottom_axes,
        final_score=final_score,
    )
    cache_key = (int(cut_id), chash, mode)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user_prompt = _build_user_prompt(
        segment_type=segment_type,
        top_axes=top_axes,
        bottom_axes=bottom_axes,
        cold_start_axes=cold_start_axes,
        final_score=final_score,
    )

    def get_offline_explanation() -> str:
        top_names = []
        if top_axes:
            for a in top_axes[:2]:
                axis_name = a.get("axis", "Unbekannt")
                translations = {
                    "beat": "Rhythmus-Synchronität (Beat)",
                    "onset": "Einsatz-Dynamik (Onset)",
                    "kick": "Bass-Präsenz (Kick)",
                    "snare": "Snare-Taktung (Snare)",
                    "hihat": "Hihat-Frequenz (Hihat)",
                    "energy": "Energieverlauf",
                    "motion": "Bewegungsintensität (Motion)",
                    "scene_cut": "Schnittfrequenz (Scene Cuts)",
                    "brightness_match": "Helligkeitsverlauf",
                    "color_temp_match": "Farbtemperatur",
                    "pace_match": "Pacing-Geschwindigkeit",
                    "semantic_match": "Thematischer Inhalt (Semantic)",
                    "mood_match": "Stimmung (Mood)",
                }
                top_names.append(translations.get(axis_name, axis_name))
        
        axes_str = " und ".join(top_names) if top_names else "allgemeine Pacing-Faktoren"
        return (
            f"Dieses Video-Segment wurde ausgewählt, da es eine hohe mathematische Übereinstimmung "
            f"in den Bereichen {axes_str} aufweist (Gesamt-Confidence: {final_score:.2f}).\n\n"
            f"[Hinweis: Detaillierte KI-Erklärung ist offline. Bitte starten Sie LM Studio oder Ollama, "
            f"um die automatische Textgenerierung zu aktivieren.]"
        )

    # Caller kann einen vorbereiteten Client uebergeben (Tests via MockTransport).
    # M2-Fix (W-M2, 2026-05-20): get_alive_client wired — Auto-Fallback LM Studio
    # → Ollama wenn primary down. Vorher: Wenn LM Studio down, sofort None
    # (kein Versuch Ollama). Jetzt: get_alive_client testet beide Provider.
    owns_client = False
    if client is None:
        from pb_studio.ai.llm_provider import get_alive_client
        client = await get_alive_client(timeout_seconds=min(timeout_seconds, 5.0))
        if client is None:
            logger.warning(
                "LLM-Narrator: kein LLM-Provider erreichbar (LM Studio + Ollama beide down) — Fallback auf offline Text"
            )
            return get_offline_explanation()
        owns_client = True

    try:
        registry = ModelRegistry(ai_cfg, client=client)
        try:
            await registry.refresh()
        except LMStudioError as exc:
            logger.warning(
                "LLM-Narrator: LM Studio nicht erreichbar (%s) — Fallback auf offline Text",
                exc,
            )
            return get_offline_explanation()
        if model_override:
            model = model_override
        else:
            try:
                model = registry.select_best_for_task(task, mode, allow_any_installed=False)
            except (NoSuitableModelError, ModelRegistryError) as exc:
                logger.warning(
                    "LLM-Narrator: kein passendes Modell fuer task=%r mode=%r: %s — Fallback auf offline Text",
                    task,
                    mode,
                    exc,
                )
                return get_offline_explanation()

        _publish_status(model, "loading", 50.0)
        try:
            response = await client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": DEFAULT_TEMPERATURE,
                    "num_predict": DEFAULT_MAX_TOKENS,
                },
            )
        except LMStudioError as exc:
            logger.warning("LLM-Narrator: chat() fehlgeschlagen: %s — Fallback auf offline Text", exc)
            _publish_status(model, "failed", 0.0)
            return get_offline_explanation()

        message = response.get("message") or {}
        raw = (
            message.get("content")
            or response.get("response")
            or ""
        )
        text = _post_process_narrative(str(raw))
        if not text:
            logger.warning(
                "LLM-Narrator: leere Antwort vom Modell %s — Fallback auf offline Text",
                model,
            )
            _publish_status(model, "failed", 0.0)
            return get_offline_explanation()
        _publish_status(model, "active", 100.0)
        _cache_put(cache_key, text)
        return text
    finally:
        if owns_client:
            try:
                await client.aclose()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("LLM-Narrator: aclose() ignored: %s", exc)


async def generate_explanation(
    *,
    cut_id: int,
    segment_type: Optional[str],
    top_axes: list[dict[str, Any]],
    bottom_axes: list[dict[str, Any]],
    cold_start_axes: Optional[list[str]] = None,
    final_score: float,
    mode: str = DEFAULT_MODE,
    task: str = DEFAULT_TASK,
    model_override: Optional[str] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: Optional[Any] = None,
) -> Optional[str]:
    """Erzeugt eine natuerlichsprachliche Erklaerung fuer einen Cut.

    Args:
        cut_id: Datenbank-ID des Cuts (geht in den Cache-Key).
        segment_type: ``intro`` / ``drop`` / ``bridge`` / ``outro`` / ``None``.
        top_axes/bottom_axes: Listen aus ``BrainAxisContribution.model_dump()``
            oder vergleichbare Dicts mit Feldern ``axis`` und ``score``.
        cold_start_axes: Achsen mit < 10 Samples (Cold-Start-Defaults).
        final_score: Gesamt-Score 0..1.
        mode: ``speed`` / ``balance`` / ``quality`` fuer Model-Auswahl.
        task: ``brain_explanation`` (Default; Caller kann andere Tasks nutzen).
        model_override: Wenn gesetzt, ueberspringt Auto-Selection.
        timeout_seconds: HTTP-Timeout fuer den LM-Studio-Chat-Call.
        client: Test-Hook fuer MockTransport-LMStudioClient.

    Returns:
        Cleaner Narrativ-Text (1-3 Saetze) oder ``None`` wenn LLM nicht
        verfuegbar / kein passendes Modell / leere Antwort.
    """
    try:
        return await _async_generate_explanation(
            cut_id=int(cut_id),
            segment_type=segment_type,
            top_axes=list(top_axes or []),
            bottom_axes=list(bottom_axes or []),
            cold_start_axes=list(cold_start_axes or []),
            final_score=float(final_score),
            mode=mode,
            task=task,
            model_override=model_override,
            timeout_seconds=timeout_seconds,
            client=client,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM-Narrator: unerwarteter Fehler: %s", exc)
        return None


__all__ = [
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "DEFAULT_TASK",
    "DEFAULT_MODE",
    "generate_explanation",
    "clear_narrative_cache",
]
