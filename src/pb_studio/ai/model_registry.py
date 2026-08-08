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
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, TypeVar

from .lmstudio_client import LMStudioClient, LMStudioError, LMStudioModelInfo

if TYPE_CHECKING:
    from .model_inventory import ModelInventoryEntry, ModelInventorySnapshot

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


@dataclass(frozen=True)
class ModelSelectionReceipt:
    provider: str
    model_id: str
    task: str
    mode: str
    required_capabilities: tuple[str, ...]
    verified_capabilities: tuple[str, ...]
    source: str
    reason: str
    selected_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelFailoverExhaustedError(ModelRegistryError):
    """All bounded, capability-valid candidates failed."""

    def __init__(
        self,
        message: str,
        *,
        receipts: list[ModelSelectionReceipt],
    ) -> None:
        super().__init__(message)
        self.receipts = tuple(receipts)


_ResultT = TypeVar("_ResultT")


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
        self._model_capabilities: dict[str, frozenset[str]] = {}
        self._loaded = False

    @property
    def installed_models(self) -> list[LMStudioModelInfo]:
        return list(self._installed)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

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
            self._model_capabilities = {}
            self._loaded = True
            raise
        # Native Provider-Metadaten sind autoritativ. Fehlt deren Endpoint,
        # bleiben konservative Namensheuristiken als Compatibility-Fallback.
        try:
            self._model_capabilities = await client.get_model_capabilities()
        except Exception:  # noqa: BLE001
            self._model_capabilities = {}
        self._vision_models = {
            name
            for name, capabilities in self._model_capabilities.items()
            if "vision" in capabilities
        }
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
    # Zu "qwen/qwen3.5-" und "qwen/qwen3.6-" (Audit 2026-08-07): sie decken nur
    # die praefigierte Namensform ab (Ollama, aeltere LM-Studio-Staende). Die
    # aktuell hier installierten IDs heissen bloss "qwen3.5-9b" bzw.
    # "qwen3.6-35b-a3b-...", werden von diesen Tokens also nicht getroffen.
    #
    # Verkuerzen waere trotzdem falsch — beide Kurzformen fangen ein reines
    # Textmodell mit ein, live gegengeprueft:
    #   "qwen3.5-" -> kshitijthakkar-qwen3.5-moe-0.87b-d0.8b  (type=llm)
    #   "qwen3.6-" -> qwen3.6-27b-mtp-pi-reasoning            (type=llm)
    # Ein falsch als vision-faehig markiertes Textmodell kostet im Failover
    # einen kompletten Modellwechsel (live 72-120 s) und liefert nichts.
    #
    # Aus Namen laesst sich das nicht sauber trennen. Die belastbare Aussage
    # kommt aus ``type == "vlm"``; diese Liste ist nur der Notnagel, wenn
    # /api/v0/models nicht antwortet, und bleibt deshalb bewusst strikt.
    _VISION_NAME_TOKENS = (
        "-vl", "vl-", "vl:", "vision", "vlm", "llava", "moondream", "multimodal",
        "minicpm-v", "internvl", "pixtral", "smolvlm", "gemma-3n", "gemma3n",
        "e4b", "e2b", "cpm-v", "-vl-", "qwen/qwen3.5-", "qwen/qwen3.6-",
    )

    def _is_vision_capable(self, model_name: str) -> bool:
        """True wenn das Modell Bilder verarbeiten kann.

        Primaer autoritativ ueber das von ``/api/v0/models`` gemeldete ``type==vlm``
        (``self._vision_models``); sekundaer ueber strikte Namens-Tokens.
        """
        if self._vision_models:
            return any(_name_matches(name, model_name) for name in self._vision_models)
        matched_capabilities = self._capabilities_for_model(model_name)
        if matched_capabilities is not None:
            return "vision" in matched_capabilities
        low = model_name.lower()
        return any(tok in low for tok in self._VISION_NAME_TOKENS)

    def _capabilities_for_model(self, model_name: str) -> Optional[frozenset[str]]:
        for capability_name, capabilities in self._model_capabilities.items():
            if _name_matches(capability_name, model_name):
                return capabilities
        return None

    def _is_chat_capable(self, model_name: str) -> bool:
        matched_capabilities = self._capabilities_for_model(model_name)
        if matched_capabilities is not None:
            return "chat" in matched_capabilities
        return "embed" not in model_name.lower()

    def is_model_capable(self, model_name: str, capability: str) -> bool:
        """Prueft ein installiertes Modell gegen die benoetigte Task-Capability."""
        installed_name = next(
            (
                model.name
                for model in self._installed
                if _name_matches(model_name, model.name)
            ),
            None,
        )
        if installed_name is None:
            return False
        if capability == "vision":
            return self._is_vision_capable(installed_name)
        if capability == "chat":
            return self._is_chat_capable(installed_name)
        raise ModelRegistryError(f"Unbekannte Modell-Capability: {capability!r}")

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

    def get_provider_override(self, task: str) -> Optional[str]:
        overrides = self._config.get("task_provider_overrides") or {}
        value = overrides.get(task) if isinstance(overrides, dict) else None
        text = str(value or "").strip().lower()
        return text if text in {"lmstudio", "ollama"} else None

    @staticmethod
    def _required_capability(task: str) -> str:
        return (
            "vision"
            if task in {"video_captioning", "image_captioning"}
            else "chat"
        )

    def selection_receipts_for_task(
        self,
        snapshot: ModelInventorySnapshot,
        task: str,
        mode: str = "balance",
        *,
        explicit_model: Optional[str] = None,
        explicit_provider: Optional[str] = None,
        exclude: Optional[set[tuple[str, str]]] = None,
        limit: int = 3,
    ) -> list[ModelSelectionReceipt]:
        """Return at most ``limit`` provider/model candidates in contract order."""
        if mode not in VALID_MODES:
            raise ModelRegistryError(
                f"Unbekannter mode={mode!r} (erlaubt: {sorted(VALID_MODES)})"
            )
        required = self._required_capability(task)
        excluded = {
            (provider.lower(), model.lower())
            for provider, model in (exclude or set())
        }
        eligible = [
            model
            for model in snapshot.models
            if model.installed
            and model.usable
            and required in model.capabilities
            and (model.provider.lower(), model.name.lower()) not in excluded
        ]
        if not eligible:
            raise NoSuitableModelError(
                f"Kein nutzbares {required}-Modell für task={task!r}; "
                f"Inventargeneration={snapshot.generation}."
            )

        configured_provider = str(
            self._config.get("provider") or "auto"
        ).strip().lower()
        preferred_provider = (
            configured_provider
            if configured_provider in {"lmstudio", "ollama"}
            else None
        )

        def tie_key(model: ModelInventoryEntry) -> tuple[int, int, str, str]:
            return (
                0 if model.loaded else 1,
                0 if preferred_provider and model.provider == preferred_provider else 1,
                model.provider.lower(),
                model.name.lower(),
            )

        remaining = list(eligible)
        ranked: list[tuple[ModelInventoryEntry, str, str]] = []

        def consume_matches(
            names: list[str],
            *,
            provider: Optional[str],
            source: str,
            reason: str,
            require_unique_without_provider: bool = False,
        ) -> None:
            nonlocal remaining
            for requested_name in names:
                scoped = [
                    model
                    for model in remaining
                    if provider is None or model.provider == provider
                ]
                normalized = str(requested_name).strip().casefold()
                exact_matches = [
                    model
                    for model in scoped
                    if model.name.strip().casefold() == normalized
                ]
                matches = exact_matches or [
                    model
                    for model in scoped
                    if _name_matches(requested_name, model.name)
                ]
                if not exact_matches and len(matches) > 1:
                    identities = ", ".join(
                        sorted(
                            f"{model.provider}:{model.name}"
                            for model in matches
                        )
                    )
                    raise ModelRegistryError(
                        f"Legacy-Modellalias {requested_name!r} ist "
                        f"mehrdeutig ({identities}); exakte Modell-ID und "
                        "Provider sind erforderlich."
                    )
                if (
                    require_unique_without_provider
                    and provider is None
                    and len(matches) > 1
                ):
                    providers = ", ".join(
                        sorted(model.provider for model in matches)
                    )
                    raise ModelRegistryError(
                        f"Persistiertes Modell {requested_name!r} für {task!r} "
                        f"ist bei mehreren Providern nutzbar ({providers}); "
                        "task_provider_overrides muss den Provider festlegen."
                    )
                for model in sorted(matches, key=tie_key):
                    ranked.append((model, source, reason))
                    remaining.remove(model)

        explicit_name = str(explicit_model or "").strip()
        explicit_provider_name = str(explicit_provider or "").strip().lower()
        if explicit_provider_name not in {"lmstudio", "ollama"}:
            explicit_provider_name = ""
        if explicit_name:
            ranked_before = len(ranked)
            consume_matches(
                [explicit_name],
                provider=explicit_provider_name or None,
                source="explicit_override",
                reason="Nutzbarer expliziter Provider-/Modell-Override.",
                require_unique_without_provider=True,
            )
            if len(ranked) == ranked_before:
                raise NoSuitableModelError(
                    f"Explizites Modell {explicit_name!r} ist beim "
                    "angeforderten Provider nicht exakt oder eindeutig als "
                    f"nutzbares {required}-Modell verifiziert."
                )

        persisted_model = self.get_user_override(task)
        persisted_provider = self.get_provider_override(task)
        if persisted_model:
            consume_matches(
                [persisted_model],
                provider=persisted_provider,
                # Audit 2026-08-07: hiess frueher ebenfalls
                # "persisted_task_preference" — am Receipt war damit nicht
                # erkennbar, ob ein harter Override (ai.task_overrides) oder
                # die Modus-Praeferenzliste gegriffen hat. Genau diese
                # Unterscheidung braucht man bei der Diagnose zuerst.
                source="user_task_override",
                reason="Harter Override aus ai.task_overrides ist live nutzbar.",
                require_unique_without_provider=True,
            )

        user_preferences = (
            (self._config.get("task_preferences") or {}).get(task) or {}
        )
        persisted_names = (
            list(user_preferences.get(mode) or [])
            if isinstance(user_preferences, dict)
            else []
        )
        consume_matches(
            persisted_names,
            provider=None,
            source="persisted_task_preference",
            reason=f"Persistierte {mode}-Präferenz mit verifizierter Capability.",
        )

        default_names = list(
            (DEFAULT_TASK_PREFERENCES.get(task) or {}).get(mode) or []
        )
        consume_matches(
            default_names,
            provider=None,
            source="capability_recommendation",
            reason=f"Capability-basierte {mode}-Empfehlung.",
        )

        for model in sorted(remaining, key=tie_key):
            ranked.append(
                (
                    model,
                    "live_fallback",
                    "Anderes geeignetes Live-Modell mit verifizierter Capability.",
                )
            )

        receipts = [
            ModelSelectionReceipt(
                provider=model.provider,
                model_id=model.name,
                task=task,
                mode=mode,
                required_capabilities=(required,),
                verified_capabilities=tuple(sorted(model.capabilities)),
                source=source,
                reason=reason,
                selected_at=datetime.now(timezone.utc).isoformat(),
            )
            for model, source, reason in ranked[: max(1, min(int(limit), 3))]
        ]
        if not receipts:
            raise NoSuitableModelError(
                f"Kein Modell nach Ausschlüssen für task={task!r} verfügbar."
            )
        return receipts

    def select_receipt_for_task(
        self,
        snapshot: ModelInventorySnapshot,
        task: str,
        mode: str = "balance",
        **kwargs: Any,
    ) -> ModelSelectionReceipt:
        return self.selection_receipts_for_task(
            snapshot,
            task,
            mode,
            limit=1,
            **kwargs,
        )[0]

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

        required_capability = (
            "vision"
            if task in ("video_captioning", "image_captioning")
            else "chat"
        )
        eligible_names = [
            name
            for name in installed_names
            if self.is_model_capable(name, required_capability)
        ]
        if not eligible_names:
            raise NoSuitableModelError(
                f"Kein {required_capability}-faehiges Modell verfuegbar "
                f"fuer task={task!r}. Installiert: {installed_names}."
            )
        installed_names = eligible_names

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


# ---------------------------------------------------------------------------
# Audit 2026-08-05 (C-2/T2.3): Sessionweite Sperre nicht-ladbarer Modelle.
#
# ``excluded`` war zuvor rein call-lokal. Nach ModelFailoverExhaustedError begann
# der naechste Aufruf wieder bei denselben drei Kandidaten. Beim frameweisen
# Video-Tagging ergab das 467 Wiederholungen mit je ~15 s LM-Studio-Ladeversuch —
# rund zwei Stunden reine Wartezeit in einer einzigen Session.
#
# Gesperrt wird nur bei Fehlern, die belegen, dass das Modell ueberhaupt nicht
# geladen werden kann. Transiente Fehler (Timeout, Verbindungsabbruch) fuehren
# bewusst NICHT zur Sperre.
# ---------------------------------------------------------------------------
# Audit 2026-08-07: die Sperre war unbefristet. Live reproduziert: liegt in
# LM Studio noch ein grosses Modell mit JIT-TTL im VRAM, scheitert der Ladeversuch
# mit "Failed to load model ... Engine protocol startup was aborted" — ein
# Marker aus dieser Liste. Nach dem Entladen laedt dasselbe Modell wieder
# problemlos. Eine unbefristete Sperre haette das Vision-Tagging fuer den Rest
# der Backend-Laufzeit deaktiviert. Die Sperre laeuft daher ab.
_UNLOADABLE_LOCK_SECONDS = 900.0

_UNLOADABLE_MODELS: dict[tuple[str, str], float] = {}

_UNLOADABLE_ERROR_MARKERS = (
    "failed to load model",
    "exited before becoming healthy",
    "no lm runtime found",
    "unable to load model",
)


def _is_unloadable_error(exc: Exception) -> bool:
    """True wenn die Fehlermeldung belegt, dass das Modell nicht ladbar ist."""
    text = f"{exc}".lower()
    return any(marker in text for marker in _UNLOADABLE_ERROR_MARKERS)


def get_unloadable_models() -> frozenset[tuple[str, str]]:
    """Aktuell gesperrte (provider, model_id)-Paare; abgelaufene fallen raus."""
    now = time.monotonic()
    # list(...) kopiert auf C-Ebene in einem Schritt. Eine Comprehension mit
    # Bedingung iteriert dagegen auf Python-Ebene und kann von einem parallelen
    # Schreiber (Vision laeuft in asyncio.to_thread, der Brain-Narrator im
    # Event-Loop) mit "dictionary changed size during iteration" abgebrochen
    # werden — mitten in der Modellauswahl, ausserhalb jedes Retry-Pfads.
    for key, until in list(_UNLOADABLE_MODELS.items()):
        if until <= now:
            _UNLOADABLE_MODELS.pop(key, None)
    return frozenset(_UNLOADABLE_MODELS)


def reset_unloadable_models() -> None:
    """Hebt die Sperre sofort auf (Tests, sowie nach Modell-Installation)."""
    _UNLOADABLE_MODELS.clear()


async def execute_with_model_failover(
    registry: ModelRegistry,
    task: str,
    mode: str,
    operation: Callable[
        [LMStudioClient, ModelSelectionReceipt],
        Awaitable[_ResultT],
    ],
    *,
    is_retryable: Callable[[Exception], bool],
    is_provider_failure: Optional[Callable[[Exception], bool]] = None,
    explicit_model: Optional[str] = None,
    explicit_provider: Optional[str] = None,
) -> tuple[_ResultT, ModelSelectionReceipt, tuple[ModelSelectionReceipt, ...]]:
    """Execute against receipt-bound clients with one refresh and three attempts."""
    from .llm_provider import DEFAULT_GENERATION_TIMEOUT, get_llm_client
    from .model_inventory import get_model_inventory_service

    inventory = get_model_inventory_service()
    snapshot = await inventory.refresh()
    # Sessionweite Sperre als Startmenge: Modelle, die in dieser Session
    # nachweislich nicht ladbar waren, werden gar nicht erst erneut probiert.
    excluded: set[tuple[str, str]] = set(get_unloadable_models())
    attempts: list[ModelSelectionReceipt] = []
    refreshed_after_failure = False
    last_error: Optional[Exception] = None

    while len(attempts) < 3:
        try:
            receipt = registry.select_receipt_for_task(
                snapshot,
                task,
                mode,
                explicit_model=explicit_model if not attempts else None,
                explicit_provider=explicit_provider if not attempts else None,
                exclude=excluded,
            )
        except NoSuitableModelError as exc:
            last_error = exc
            break

        attempts.append(receipt)
        logger.info("ModelSelectionReceipt: %s", receipt.to_dict())
        client = get_llm_client(
            provider=receipt.provider,
            timeout_seconds=DEFAULT_GENERATION_TIMEOUT,
        )
        try:
            async with client:
                result = await operation(client, receipt)
            return result, receipt, tuple(attempts)
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_error = exc
            excluded.add((receipt.provider, receipt.model_id))
            if _is_unloadable_error(exc):
                key = (receipt.provider, receipt.model_id)
                first_lock = key not in _UNLOADABLE_MODELS
                _UNLOADABLE_MODELS[key] = (
                    time.monotonic() + _UNLOADABLE_LOCK_SECONDS
                )
                if first_lock:
                    logger.warning(
                        "Modell fuer %.0fs gesperrt (nicht ladbar): "
                        "provider=%s model=%s grund=%s",
                        _UNLOADABLE_LOCK_SECONDS,
                        receipt.provider,
                        receipt.model_id,
                        exc,
                    )
            # Audit 2026-08-05 (C-2, Nebenbefund): %s auf eine Exception mit
            # leerem str() ergab "error=" ohne Inhalt -- die eigentliche
            # LM-Studio-Fehlermeldung ging komplett verloren und hat die
            # Diagnose der Failover-Kette massiv erschwert.
            logger.warning(
                "Receipt-bound provider call failed: provider=%s model=%s "
                "attempt=%d/3 error=%s: %r",
                receipt.provider,
                receipt.model_id,
                len(attempts),
                type(exc).__name__,
                exc,
            )
            provider_failure = (
                is_provider_failure(exc)
                if is_provider_failure is not None
                else True
            )
            if provider_failure and not refreshed_after_failure:
                inventory.invalidate()
                snapshot = await inventory.refresh()
                refreshed_after_failure = True

    if last_error is not None:
        # str(exc) ist bei manchen Client-Exceptions leer -- dann bleibt sonst
        # nur "erschoepft: " ohne Grund uebrig (Audit 2026-08-05).
        detail = str(last_error) or f"{type(last_error).__name__}: {last_error!r}"
    else:
        detail = "keine weiteren Kandidaten"
    raise ModelFailoverExhaustedError(
        f"Modellauswahl für task={task!r} nach {len(attempts)} "
        f"verschiedenen Kandidaten erschöpft: {detail}",
        receipts=attempts,
    )
