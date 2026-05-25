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
from typing import Any, Optional

from .lmstudio_client import LMStudioClient, LMStudioError, LMStudioModelInfo

logger = logging.getLogger(__name__)

DEFAULT_TASK_PREFERENCES: dict[str, dict[str, list[str]]] = {
    "video_captioning": {
        "speed":   ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "balance": ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
    },
    "image_captioning": {
        "speed":   ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "balance": ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
        "quality": ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"],
    },
    "chat": {
        "speed":   ["google/gemma-4-e4b", "gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf"],
        "balance": ["qwen3.5-9b-uncensored-hauhaucs-aggressive", "google/gemma-4-e4b"],
        "quality": ["gemma-4-31b-it-uncensored", "gemma-4-26b-a4b-it-ultra-uncensored-heretic"],
    },
    "chat_general": {
        "speed":   ["google/gemma-4-e4b", "gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf"],
        "balance": ["qwen3.5-9b-uncensored-hauhaucs-aggressive", "google/gemma-4-e4b"],
        "quality": ["gemma-4-31b-it-uncensored", "gemma-4-26b-a4b-it-ultra-uncensored-heretic"],
    },
    "chat_tool_use": {
        "speed":   ["qwen3.5-9b-uncensored-hauhaucs-aggressive", "google/gemma-4-e4b"],
        "balance": ["raw-uncensored-qwen3-14b-heretic-recovered", "qwen3.5-9b-uncensored-hauhaucs-aggressive"],
        "quality": ["raw-uncensored-qwen3-14b-heretic-recovered", "gemma-4-31b-it-uncensored"],
    },
    "brain_explanation": {
        "speed":   ["google/gemma-4-e4b", "gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf"],
        "balance": ["qwen3.5-9b-uncensored-hauhaucs-aggressive", "google/gemma-4-e4b"],
        "quality": ["gemma-4-26b-a4b-it-ultra-uncensored-heretic", "google/gemma-4-e4b"],
    },
}

VALID_MODES = frozenset({"speed", "balance", "quality"})


class ModelRegistryError(RuntimeError):
    """Basis-Exception fuer Registry-Probleme."""


class NoSuitableModelError(ModelRegistryError):
    """Kein installiertes Modell erfuellt die Preferenz-Kette fuer den Task."""


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
        self._loaded = False

    @property
    def installed_models(self) -> list[LMStudioModelInfo]:
        return list(self._installed)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _resolve_client(self) -> LMStudioClient:
        if self._client is None:
            self._client = LMStudioClient()
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
            self._loaded = True
            raise
        self._loaded = True
        logger.info(
            "ModelRegistry refresh: %d Modelle verfuegbar (%s)",
            len(self._installed),
            ", ".join(m.name for m in self._installed) or "-",
        )
        return list(self._installed)

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
        allow_any_installed: bool = False,
    ) -> str:
        if not self._loaded:
            raise ModelRegistryError(
                "ModelRegistry nicht initialisiert - refresh() vor select aufrufen"
            )

        installed_names = [m.name for m in self._installed]

        override = self.get_user_override(task)
        if override:
            for inst in installed_names:
                if _name_matches(override, inst):
                    return inst
            logger.warning(
                "User-Override %r fuer Task %r nicht installiert - Fallback auf Preferenzen",
                override, task,
            )

        prefs = self.get_preference_list(task, mode)
        for candidate in prefs:
            for inst in installed_names:
                if _name_matches(candidate, inst):
                    return inst

        # Smart Vision Fallback: Falls kein praeferiertes Modell passt und es ein Vision-Task ist,
        # suchen wir nach dem ersten installierten Modell mit Vision-Faehigkeiten.
        if task in ("video_captioning", "image_captioning"):
            vision_keywords = ["vl", "vision", "moondream", "llava", "multimodal", "clip", "gemma-4", "minicpm"]
            for inst in installed_names:
                inst_lower = inst.lower()
                if any(kw in inst_lower for kw in vision_keywords):
                    logger.info(
                        "Auto-selection: Smart Vision Fallback auf Modell %r fuer Task %r",
                        inst, task
                    )
                    return inst

        if allow_any_installed and installed_names:
            chosen = installed_names[0]
            logger.warning(
                "Keine Preferenz fuer Task %r/%s installiert - nutze beliebiges %r",
                task, mode, chosen,
            )
            return chosen

        raise NoSuitableModelError(
            f"Kein installiertes Modell fuer task={task!r} mode={mode!r}. "
            f"Preferenzen={prefs}. Installiert={installed_names}."
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
