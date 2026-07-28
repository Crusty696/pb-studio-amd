"""Model-Registry und Auto-Selection fuer PB Studio AI-Tasks.

Wrapped ``LMStudioClient.list_models()`` und matcht pro Task (z.B. Video-
Captioning) gegen eine kuratierte Preferenz-Liste, je nach Modus
``speed``/``balance``/``quality``. Per-Task User-Overrides ueberschreiben
das Mapping immer.

Beispiel::

    registry = ModelRegistry()
    await registry.refresh()
    model = registry.select_best_for_task("video_captioning", mode="balance")

Quelle der Preferenzen:
    1. ``config.ai.task_overrides[task]``  (immer, falls gesetzt)
    2. ``config.ai.task_preferences[task][mode]``  (falls gesetzt)
    3. ``DEFAULT_TASK_PREFERENCES[task][mode]``  (Built-in Fallback)

LM Studio Refactor 2026-05-17: Drop-in-Swap von ``OllamaClient`` auf
``LMStudioClient``. Modell-Tags wechseln von Ollama-Format (``gemma4:latest``)
auf LM-Studio-Format (``qwen/qwen3-vl-8b`` etc.).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .lmstudio_client import LMStudioClient, LMStudioError, LMStudioModelInfo

logger = logging.getLogger(__name__)

DEFAULT_TASK_PREFERENCES: dict[str, dict[str, list[str]]] = {
    # Audit-Fix (2026-07-10): erneut gegen `curl http://127.0.0.1:1234/v1/models`
    # abgeglichen (live, nicht nur Log-Datei). chat/chat_general/chat_tool_use/
    # brain_explanation zeigten davor auf Fine-Tune-Namen, die zu diesem
    # Zeitpunkt NICHT installiert waren (z.B. "gemma-4-31b-it-uncensored").
    # LM-Studio-Modell-Sets aendern sich zwischen Sessions haeufig (belegt:
    # Log vom 2026-06-08 vs. Live-Check 2026-07-10 haben fast keine Ueberschneidung)
    # -> diese Liste ist ein Best-Effort-Startpunkt, keine Garantie. Der
    # 3-Stufen-Fallback (Praeferenz -> Keyword -> irgendein installiertes Modell,
    # siehe select_best_for_task) faengt veraltete Eintraege automatisch ab.
    "video_captioning": {
        "speed":   ["qwen/qwen3.5-9b", "google/gemma-4-e4b", "qwen/qwen3-vl-8b"],
        "balance": ["qwen/qwen3.5-9b", "qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3.6-27b", "qwen/qwen3.5-9b", "qwen/qwen3-vl-8b"],
    },
    "image_captioning": {
        "speed":   ["qwen/qwen3.5-9b", "google/gemma-4-e4b", "qwen/qwen3-vl-8b"],
        "balance": ["qwen/qwen3.5-9b", "qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3.6-27b", "qwen/qwen3.5-9b", "qwen/qwen3-vl-8b"],
    },
    "chat": {
        "speed":   ["google/gemma-4-e4b", "qwen/qwen3.5-9b"],
        "balance": ["gemma-4-12b-it-uncensored@q4_k_s", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3.6-27b", "gemma-4-12b-it-uncensored@q4_k_s"],
    },
    "chat_general": {
        "speed":   ["google/gemma-4-e4b", "qwen/qwen3.5-9b"],
        "balance": ["gemma-4-12b-it-uncensored@q4_k_s", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3.6-27b", "gemma-4-12b-it-uncensored@q4_k_s"],
    },
    "chat_tool_use": {
        "speed":   ["distil-home-assistant-functiongemma", "google/gemma-4-e4b"],
        "balance": ["qwen/qwen3-coder-30b", "distil-home-assistant-functiongemma"],
        "quality": ["qwen/qwen3-coder-30b", "qwen/qwen3.6-27b"],
    },
    "brain_explanation": {
        "speed":   ["qwen/qwen3-4b-thinking-2507", "google/gemma-4-e4b"],
        "balance": ["qwen/qwen3-4b-thinking-2507", "qwen/qwen3.6-27b", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3.6-27b", "qwen/qwen3-4b-thinking-2507", "google/gemma-4-e4b"],
    },
}

VALID_MODES = frozenset({"speed", "balance", "quality"})


class ModelRegistryError(RuntimeError):
    """Basis-Exception fuer Registry-Probleme."""


class NoSuitableModelError(ModelRegistryError):
    """Kein installiertes Modell erfuellt die Preferenz-Kette fuer den Task."""


def _parse_parameter_size(name: str) -> float:
    """Parses parameter size (e.g. 1.5b, 8b, 14b, 32b, 70b) from model name.
    Returns size in billions as float, or 0.0 if not found.
    """
    match = re.search(r'(\d+(?:\.\d+)?)\s*[bB]', name)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    # If not found, look for numbers that look like parameter size
    # E.g. gemma-2, phi-3, qwen-7
    match = re.search(r'(?:gemma|phi|qwen|llama|gemma-3|gemma-4)\D*(\d+)', name.lower())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _sort_models_by_mode(installed: list[str], mode: str) -> list[str]:
    """Sorts model names based on the mode and their parsed parameter sizes."""
    pairs = [(name, _parse_parameter_size(name)) for name in installed]
    
    if mode == "speed":
        # Sort ascending by size (smaller models first), push unknowns (0.0) to the end
        pairs.sort(key=lambda x: (x[1] if x[1] > 0 else 999.0))
    elif mode == "quality":
        # Sort descending by size (larger models first), push unknowns (0.0) to the end
        pairs.sort(key=lambda x: (x[1] if x[1] > 0 else -1.0), reverse=True)
    else:  # balance
        # Sort by distance to 8B (balanced model size), push unknowns (0.0) to the end by giving them a high distance of 10.0
        pairs.sort(key=lambda x: (abs(x[1] - 8.0) if x[1] > 0 else 10.0))
        
    return [name for name, _ in pairs]


TASK_KEYWORDS: dict[str, list[str]] = {
    "video_captioning": ["vl", "vision", "vlm", "moondream", "llava", "multimodal", "minicpm", "internvl", "pixtral", "smolvlm", "gemma-3n", "e4b", "e2b"],
    "image_captioning": ["vl", "vision", "vlm", "moondream", "llava", "multimodal", "minicpm", "internvl", "pixtral", "smolvlm", "gemma-3n", "e4b", "e2b"],
    "chat": ["chat", "instruct", "it", "deepseek", "llama", "gemma", "qwen", "phi", "mistral"],
    "chat_general": ["chat", "instruct", "it", "deepseek", "llama", "gemma", "qwen", "phi", "mistral"],
    "chat_tool_use": ["tool", "function", "agent", "qwen", "llama", "phi", "gemma"],
    "brain_explanation": ["thinking", "reasoning", "r1", "deepseek", "phi", "llama"],
}


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


def _name_matches(candidate: str, installed: str) -> bool:
    """Tag-Match: tolerant gegenueber Ollama-/LM-Studio-Variationen."""
    cand = _normalize_model_name(candidate)
    inst = _normalize_model_name(installed)
    if cand == inst:
        return True
    if "/" in inst and inst.rsplit("/", 1)[1] == cand:
        return True
    if "/" in cand and cand.rsplit("/", 1)[1] == inst:
        return True
    if ":" not in cand and inst.split(":", 1)[0] == cand:
        return True
    if ":" not in inst and cand.split(":", 1)[0] == inst:
        return True
    return False


class ModelRegistry:
    """Haelt eine Liste verfuegbarer Modelle + waehlt das passende fuer Tasks."""

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        *,
        client: Optional[LMStudioClient] = None,
    ) -> None:
        self._config = config or {}
        self._client = client
        self._installed: list[LMStudioModelInfo] = []
        self._vision_models: set[str] = set()
        self._loaded = False

    @property
    def installed_models(self) -> list[LMStudioModelInfo]:
        return list(self._installed)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _resolve_client(self) -> LMStudioClient:
        if self._client is None:
            from pb_studio.ai.llm_provider import get_llm_client
            self._client = get_llm_client()
        return self._client


    async def _resolve_client_async(self) -> LMStudioClient:
        """W-QA-2 (2026-05-22): respektiert config.ai.provider mit Auto-Fallback.

        Wenn kein Client injiziert ist, holt get_alive_client den live-erreichbaren
        Provider (LM Studio first, Ollama Fallback bei provider="auto"). Damit
        funktioniert /models/recommendations auch wenn LM Studio down ist.
        """
        if self._client is None:
            from pb_studio.ai.llm_provider import get_alive_client, get_llm_client, get_provider
            if get_provider() == "auto":
                alive = await get_alive_client(timeout_seconds=5.0)
                self._client = alive if alive is not None else get_llm_client()
            else:
                self._client = get_llm_client()
        return self._client

    async def refresh(self) -> list[LMStudioModelInfo]:
        client = await self._resolve_client_async()
        try:
            self._installed = await client.list_models()
        except LMStudioError:
            self._installed = []
            self._vision_models = set()
            self._loaded = True
            raise
        # Vision-Capability autoritativ via LM Studio /api/v0/models (type==vlm).
        # Best-effort: leeres Set bei Ollama / fehlendem Endpoint -> Keyword-Fallback.
        try:
            self._vision_models = await client.get_vision_model_names()
        except Exception:  # noqa: BLE001
            self._vision_models = set()
        self._loaded = True
        logger.info(
            "ModelRegistry refresh: %d Modelle verfuegbar (%s)",
            len(self._installed),
            ", ".join(m.name for m in self._installed) or "-",
        )
        return list(self._installed)

    # Strikte Vision-Tokens fuer den Keyword-Fallback (wenn /api/v0/models keine
    # Capability liefert, z.B. bei Ollama). Bewusst KEIN bare "qwen" — das matchte
    # Text-Modelle wie deepseek-r1-qwen3 faelschlich als Vision.
    _VISION_NAME_TOKENS = (
        "-vl", "vl-", "vl:", "vision", "vlm", "llava", "moondream", "multimodal",
        "minicpm-v", "internvl", "pixtral", "smolvlm", "gemma-3n", "gemma3n",
        "e4b", "e2b", "cpm-v", "-vl-",
    )

    def _is_vision_capable(self, model_name: str) -> bool:
        """True wenn das Modell Bilder verarbeiten kann.

        Primaer autoritativ ueber das von ``/api/v0/models`` gemeldete ``type==vlm``
        (``self._vision_models``); sekundaer ueber strikte Namens-Tokens.
        """
        if model_name in self._vision_models:
            return True
        low = model_name.lower()
        return any(tok in low for tok in self._VISION_NAME_TOKENS)

    def get_preference_list(self, task: str, mode: str) -> list[str]:
        if mode not in VALID_MODES:
            raise ModelRegistryError(
                f"Unbekannter mode={mode!r} (erlaubt: {sorted(VALID_MODES)})"
            )
        user_prefs = (self._config.get("task_preferences") or {}).get(task) or {}
        if mode in user_prefs and user_prefs[mode]:
            return list(user_prefs[mode])
        defaults = DEFAULT_TASK_PREFERENCES.get(task) or {}
        return list(defaults.get(mode) or [])

    def get_user_override(self, task: str) -> Optional[str]:
        overrides = self._config.get("task_overrides") or {}
        value = overrides.get(task)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def select_best_for_task(
        self,
        task: str,
        mode: str = "balance",
        *,
        allow_any_installed: bool = True,
        exclude: Optional[set[str]] = None,
    ) -> str:
        if not self._loaded:
            raise ModelRegistryError(
                "ModelRegistry nicht initialisiert - refresh() vor select aufrufen"
            )

        # Filtere ausgeschlossene Modelle (z.B. nicht-geladene die schon fehlgeschlagen sind)
        _exclude = exclude or set()
        installed_names = [
            m.name for m in self._installed
            if m.name not in _exclude
        ]

        if not installed_names and self._installed:
            raise NoSuitableModelError(
                f"Alle verfuegbaren Modelle wurden ausgeschlossen (exclude={_exclude}). "
                f"Installiert: {[m.name for m in self._installed]}"
            )

        # Vision-Tasks: NUR vision-faehige Modelle zulassen. Autoritativ via
        # /api/v0/models (type==vlm); sonst Keyword-Heuristik. Verhindert, dass
        # ein Text-Modell mit "qwen" im Namen (z.B. deepseek-r1-qwen3) fuer
        # Bild-Captioning gewaehlt wird -> "Model does not support images".
        if task in ("video_captioning", "image_captioning"):
            vision_only = [n for n in installed_names if self._is_vision_capable(n)]
            if vision_only:
                installed_names = vision_only
            elif self._vision_models:
                # Es gibt vlm-Modelle, aber keines davon ist installiert/verfuegbar.
                raise NoSuitableModelError(
                    f"Kein vision-faehiges Modell verfuegbar fuer task={task!r}. "
                    f"Bekannte Vision-Modelle: {sorted(self._vision_models)}. "
                    f"Installiert: {installed_names}."
                )
            # else: keine Capability-Info -> unten Keyword-Fallback (gehaertet)

        override = self.get_user_override(task)
        if override:
            for inst in installed_names:
                if _name_matches(override, inst):
                    return inst
            logger.warning(
                "User-Override %r fuer Task %r nicht installiert - Fallback auf Preferenzen",
                override, task,
            )

        # 1. Stufe: Direkter Praeferenz-Match
        prefs = self.get_preference_list(task, mode)
        for candidate in prefs:
            for inst in installed_names:
                if _name_matches(candidate, inst):
                    return inst

        # 2. Stufe: Smart Keyword Fallback (inkl. Vision & Chat/Tool/Reasoning)
        task_kws = TASK_KEYWORDS.get(task, [])
        keyword_matches = []
        for inst in installed_names:
            inst_lower = inst.lower()
            if any(kw in inst_lower for kw in task_kws):
                keyword_matches.append(inst)

        if keyword_matches:
            sorted_matches = _sort_models_by_mode(keyword_matches, mode)
            logger.info(
                "Auto-selection: Keyword Fallback fuer Task %r / Mode %s: waehle %r aus %r",
                task, mode, sorted_matches[0], keyword_matches
            )
            return sorted_matches[0]

        # 3. Stufe: Generischer Fallback (beliebiges installiertes Modell, mode-sortiert mit Eignungsprüfung)
        if allow_any_installed and installed_names:
            if task in ("video_captioning", "image_captioning"):
                # installed_names ist hier bereits auf vision-faehige Modelle
                # vorgefiltert (siehe oben) — daher direkt nutzbar. Kein erneutes
                # Keyword-Filtern, das z.B. google/gemma-4-e4b verpassen wuerde.
                eligible = list(installed_names)
            else:
                eligible = [inst for inst in installed_names if "embedding" not in inst.lower()]

            if eligible:
                sorted_all = _sort_models_by_mode(eligible, mode)
                chosen = sorted_all[0]
                logger.warning(
                    "Keine Praeferenz oder Keyword-Match fuer Task %r/%s installiert - nutze passendes Fallback-Modell %r",
                    task, mode, chosen,
                )
                return chosen

        raise NoSuitableModelError(
            f"Kein installiertes Modell fuer task={task!r} mode={mode!r}. "
            f"Preferenzen={prefs}. Installiert={installed_names}. Ausgeschlossen={_exclude}."
        )

    def recommendation_with_reason(
        self,
        task: str,
        mode: str = "balance",
    ) -> dict[str, Any]:
        override = self.get_user_override(task)
        prefs = self.get_preference_list(task, mode)
        installed_names = [m.name for m in self._installed]

        try:
            model = self.select_best_for_task(task, mode)
            if override and any(_name_matches(override, m) for m in installed_names):
                reason = f"user override fuer {task}: {override}"
            else:
                idx = next(
                    (i for i, p in enumerate(prefs) if any(_name_matches(p, n) for n in installed_names)),
                    -1,
                )
                if idx == 0:
                    reason = f"top preference fuer {mode}-mode"
                elif idx > 0:
                    reason = (
                        f"fallback #{idx} - top {idx} preference(s) nicht installiert"
                    )
                else:
                    reason = "keine Preferenz getroffen"
            return {
                "task": task,
                "mode": mode,
                "model": model,
                "reason": reason,
                "preference_list": prefs,
                "override": override,
                "installed": installed_names,
            }
        except NoSuitableModelError as exc:
            return {
                "task": task,
                "mode": mode,
                "model": None,
                "reason": str(exc),
                "preference_list": prefs,
                "override": override,
                "installed": installed_names,
            }
