"""Model-Registry und Auto-Selection fuer PB Studio AI-Tasks.

Wrapped ``OllamaClient.list_models()`` und matcht pro Task (z.B. Video-
Captioning) gegen eine kuratierte Preferenz-Liste, je nach Modus
``speed``/``balance``/``quality``. Per-Task User-Overrides ueberschreiben
das Mapping immer.

Beispiel::

    registry = ModelRegistry()
    await registry.refresh()
    model = registry.select_best_for_task("video_captioning", mode="balance")
    # -> "gemma4:latest"  (falls installiert; sonst naechstes Fallback)

Quelle der Preferenzen:
    1. ``config.ai.task_overrides[task]``  (immer, falls gesetzt)
    2. ``config.ai.task_preferences[task][mode]``  (falls gesetzt)
    3. ``DEFAULT_TASK_PREFERENCES[task][mode]``  (Built-in Fallback)

Die Registry installiert KEINE Modelle automatisch — sie waehlt nur aus
dem aus, was bereits installiert ist. Wenn KEIN Preferenz-Modell installiert
ist, raise ``NoSuitableModelError``.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .ollama_client import OllamaClient, OllamaError, OllamaModelInfo

logger = logging.getLogger(__name__)

# Built-in Default-Preferenzen (kuratierte Vision-Modell-Liste).
# Reihenfolge: hoechste Praeferenz zuerst. Erste installierte gewinnt.
DEFAULT_TASK_PREFERENCES: dict[str, dict[str, list[str]]] = {
    "video_captioning": {
        "speed":   ["minicpm-v:8b-q4",   "gemma4:latest",  "moondream:latest"],
        "balance": ["gemma4:latest",     "llava:13b",      "minicpm-v:8b"],
        "quality": ["llava:34b",         "qwen2-vl:7b",    "gemma4:latest"],
    },
    "image_captioning": {
        "speed":   ["moondream:latest",  "gemma4:latest"],
        "balance": ["gemma4:latest",     "llava:13b"],
        "quality": ["llava:34b",         "qwen2-vl:7b"],
    },
    "chat": {
        "speed":   ["gemma2:2b",         "phi3:mini",      "llama3.2:3b"],
        "balance": ["llama3.1:8b",       "mistral:7b",     "gemma2:9b"],
        "quality": ["llama3.1:70b",      "qwen2.5:32b",    "llama3.1:8b"],
    },
}

VALID_MODES = frozenset({"speed", "balance", "quality"})


class ModelRegistryError(RuntimeError):
    """Basis-Exception fuer Registry-Probleme."""


class NoSuitableModelError(ModelRegistryError):
    """Kein installiertes Modell erfuellt die Preferenz-Kette fuer den Task."""


def _normalize_model_name(name: str) -> str:
    """Ollama haengt oft ``:latest`` an. Wir matchen tolerant."""
    return name.strip().lower()


def _name_matches(candidate: str, installed: str) -> bool:
    """Tag-Match: 'gemma4:latest' == 'gemma4:latest' oder 'gemma4' == 'gemma4:latest'.

    Akzeptiert exakte Gleichheit ODER candidate ohne Tag matched installed mit
    beliebigem Tag (z.B. 'gemma4' matched 'gemma4:9b').
    """
    cand = _normalize_model_name(candidate)
    inst = _normalize_model_name(installed)
    if cand == inst:
        return True
    if ":" not in cand and inst.split(":", 1)[0] == cand:
        return True
    if ":" not in inst and cand.split(":", 1)[0] == inst:
        return True
    return False


class ModelRegistry:
    """Haelt eine Liste installierter Modelle + waehlt das passende fuer Tasks.

    ``config`` ist ein dict mit der ``ai``-Sektion aus ``config.json``. Beispiel::

        {
          "task_preferences": {"video_captioning": {"balance": ["gemma4:latest"]}},
          "task_overrides":   {"video_captioning": "llava:13b"}
        }

    ``client`` ist optional — wird bei Bedarf neu erzeugt (mit Default-URL).
    Tests sollten einen ``OllamaClient`` mit ``MockTransport`` injecten.
    """

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        *,
        client: Optional[OllamaClient] = None,
    ) -> None:
        self._config = config or {}
        self._client = client
        self._installed: list[OllamaModelInfo] = []
        self._loaded = False

    @property
    def installed_models(self) -> list[OllamaModelInfo]:
        return list(self._installed)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _resolve_client(self) -> OllamaClient:
        if self._client is None:
            self._client = OllamaClient()
        return self._client

    async def refresh(self) -> list[OllamaModelInfo]:
        """Holt die aktuell installierten Modelle via Ollama."""
        client = self._resolve_client()
        try:
            self._installed = await client.list_models()
        except OllamaError:
            self._installed = []
            self._loaded = True
            raise
        self._loaded = True
        logger.info(
            "ModelRegistry refresh: %d Modelle installiert (%s)",
            len(self._installed),
            ", ".join(m.name for m in self._installed) or "-",
        )
        return list(self._installed)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def get_preference_list(self, task: str, mode: str) -> list[str]:
        """Liefert die effektive Preferenz-Liste (User > Defaults)."""
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
        """User-Override fuer einen Task (immer Vorrang). ``None`` wenn unset."""
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
        """Waehlt das beste installierte Modell fuer einen Task.

        Reihenfolge:
            1. ``task_overrides[task]`` (wenn installiert)
            2. Erste installierte Entry aus ``preference_list(task, mode)``
            3. (optional, falls ``allow_any_installed=True``) irgendein
               installiertes Modell

        Raises:
            NoSuitableModelError: kein installiertes Modell passt.
            ModelRegistryError: ungueltiger mode.
        """
        if not self._loaded:
            raise ModelRegistryError(
                "ModelRegistry nicht initialisiert — refresh() vor select aufrufen"
            )

        installed_names = [m.name for m in self._installed]

        override = self.get_user_override(task)
        if override:
            for inst in installed_names:
                if _name_matches(override, inst):
                    return inst
            logger.warning(
                "User-Override %r fuer Task %r nicht installiert — Fallback auf Preferenzen",
                override,
                task,
            )

        prefs = self.get_preference_list(task, mode)
        for candidate in prefs:
            for inst in installed_names:
                if _name_matches(candidate, inst):
                    return inst

        if allow_any_installed and installed_names:
            chosen = installed_names[0]
            logger.warning(
                "Keine Preferenz fuer Task %r/%s installiert — nutze beliebiges %r",
                task,
                mode,
                chosen,
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
        """Liefert das gewaehlte Modell + Begruendung (fuer Backend-Endpoint)."""
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
                        f"fallback #{idx} — top {idx} preference(s) nicht installiert"
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
