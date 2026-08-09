"""KI-Chat-Agent fuer PB Studio.

Orchestriert den Konversationsfluss zwischen User und LLM (LM Studio) mit
Tool-Use. Der Agent:

1. Nimmt eine User-Message + History entgegen.
2. Fragt das LLM (mit registriertem ``tools``-Inventar).
3. Wenn das LLM ``tool_calls`` zurueckliefert, dispatched der Agent auf die
   passenden Handler in ``tool_registry``.
4. Tool-Results gehen als ``role=tool``-Messages zurueck ins LLM.
5. Schleife laeuft maximal ``max_tool_turns``-mal, dann finaler Text.

LM Studio Refactor 2026-05-17: Drop-in von ``OllamaClient`` auf
``LMStudioClient``. Tool-Call-Format ist OpenAI-style (assistant
``tool_calls`` array + separate ``tool`` message mit ``tool_call_id``).
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from .model_registry import ModelRegistry, ModelRegistryError, NoSuitableModelError
from .lmstudio_client import (
    LMStudioClient,
    LMStudioConnectionError,
    LMStudioError,
    is_provider_failure,
)
from .tool_registry import (
    ToolRegistry,
    _get_backend_base_url,
    build_default_registry,
    project_capability_scope,
)

logger = logging.getLogger(__name__)

# Audit-Fix (2026-07-10): gleiches injizierbares Publisher-Pattern wie
# lmstudio_vision_wrapper.py, damit die WPF-Statusleiste auch waehrend
# Chat-Turns (nicht nur Video-Frame-Tagging) llm_status-Events bekommt.
from typing import Callable

_status_publisher: Callable[[str, dict[str, Any]], None] | None = None


def set_status_publisher(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    global _status_publisher
    _status_publisher = fn


def _publish_status(
    model: str,
    status: str,
    percent: float,
    provider: str | None = None,
) -> None:
    """
    Best-effort llm_status-Event. Darf NIE den Chat-Turn abbrechen.

    Audit 2026-08-05 (H-4): ``provider`` war fest auf "LM Studio" verdrahtet.
    Antwortete ein Ollama-Modell, zeigte die Statusleiste trotzdem "LM Studio" —
    Falschinformation, die IRON RULE 10 widerspricht. Der Aufrufer reicht den
    Provider jetzt aus dem ModelSelectionReceipt durch; ohne Angabe bleibt das
    Feld leer, damit die UI ihren neutralen Default nutzt statt zu raten.
    """
    fn = _status_publisher
    if fn is None:
        return
    try:
        fn("llm_status", {
            "model": model,
            "provider": provider or "",
            "status": status,
            "percent": percent,
        })
    except Exception as exc:  # noqa: BLE001 - Status ist rein kosmetisch
        logger.debug("llm_status publish fehlgeschlagen: %s", exc)


DEFAULT_SYSTEM_PROMPT = (
    "Du bist der KI-Assistent von PB Studio - einer Desktop-App fuer "
    "DJ-Mix-Video-Editing mit KI (AMD DirectML, lokal). Du kannst per "
    "Tool-Calls jede Funktion der App aufrufen.\n\n"
    "WICHTIG:\n"
    "- Antworte in der Sprache der Benutzeranfrage (Deutsch oder Englisch).\n"
    "- Nutze Tool-Calls statt zu raten. Wenn du Daten brauchst, hole sie via Tool.\n"
    "- Bevor du destruktive Aktionen ausfuehrst, bestaetige kurz mit dem User.\n"
    "- Halte Antworten knapp und konkret. Lange Listen kuerzen.\n"
    "- Bei Fehlern: zeige den Fehler und schlage eine Alternative vor.\n"
)


@dataclass(frozen=True)
class ChatEvent:
    type: str
    payload: dict

    def to_dict(self):
        return {"type": self.type, **self.payload}


@dataclass
class _PendingToolConfirmation:
    confirmation_id: str
    stream_id: str
    tool_name: str
    canonical_args: dict[str, Any]
    expires_at: float
    decision: asyncio.Future[bool]
    state: str = "pending"


class ToolConfirmationBroker:
    """Atomic one-time authority for mutating chat-tool dispatch."""

    def __init__(self) -> None:
        self._entries: dict[str, _PendingToolConfirmation] = {}
        self._lock = asyncio.Lock()

    async def request(
        self, *, stream_id: str, tool_name: str, args: dict[str, Any],
        timeout_seconds: float,
    ) -> _PendingToolConfirmation:
        canonical = json.loads(json.dumps(
            args, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ))
        loop = asyncio.get_running_loop()
        entry = _PendingToolConfirmation(
            secrets.token_urlsafe(32), stream_id, tool_name, canonical,
            loop.time() + timeout_seconds, loop.create_future(),
        )
        async with self._lock:
            self._entries[entry.confirmation_id] = entry
        return entry

    async def decide(self, confirmation_id: str, *, approve: bool) -> bool:
        async with self._lock:
            entry = self._entries.get(confirmation_id)
            if entry is None or entry.state != "pending":
                return False
            if asyncio.get_running_loop().time() >= entry.expires_at:
                entry.state = "expired"
                if not entry.decision.done():
                    entry.decision.set_result(False)
                return False
            entry.state = "approved" if approve else "rejected"
            if not entry.decision.done():
                entry.decision.set_result(approve)
            return True

    async def wait(self, entry: _PendingToolConfirmation) -> bool:
        remaining = max(0.0, entry.expires_at - asyncio.get_running_loop().time())
        try:
            return await asyncio.wait_for(asyncio.shield(entry.decision), remaining)
        except asyncio.TimeoutError:
            async with self._lock:
                if entry.state == "pending":
                    entry.state = "expired"
                    if not entry.decision.done():
                        entry.decision.set_result(False)
            return False

    async def consume(
        self, confirmation_id: str, *, stream_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        async with self._lock:
            entry = self._entries.get(confirmation_id)
            if (
                entry is None
                or entry.stream_id != stream_id
                or entry.state != "approved"
                or asyncio.get_running_loop().time() >= entry.expires_at
            ):
                return None
            entry.state = "consumed"
            return entry.tool_name, json.loads(json.dumps(entry.canonical_args))

    async def cancel_stream(self, stream_id: str) -> None:
        async with self._lock:
            owned_ids = [
                confirmation_id
                for confirmation_id, entry in self._entries.items()
                if entry.stream_id == stream_id
            ]
            for confirmation_id in owned_ids:
                entry = self._entries[confirmation_id]
                if entry.state in {"pending", "approved"}:
                    entry.state = "disconnected"
                if not entry.decision.done():
                    entry.decision.set_result(False)
                del self._entries[confirmation_id]


tool_confirmation_broker = ToolConfirmationBroker()


class ChatAgent:
    """Stateless Agent - eine Instanz pro Conversation OK."""

    def __init__(
        self,
        *,
        registry: Optional[ToolRegistry] = None,
        lmstudio_client: Optional[LMStudioClient] = None,
        ollama_client: Optional[LMStudioClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        model_registry: Optional[ModelRegistry] = None,
        system_prompt: Optional[str] = None,
        max_tool_turns: int = 6,
        backend_base_url: Optional[str] = None,
        confirmation_timeout_seconds: float = 60.0,
        project_capability: Optional[str] = None,
    ) -> None:
        self._registry = registry or build_default_registry()
        injected_client = lmstudio_client if lmstudio_client is not None else ollama_client
        self._llm: Optional[LMStudioClient] = injected_client
        self._owned_llm = injected_client is None
        self._http: Optional[httpx.AsyncClient] = http_client
        self._owned_http = http_client is None
        self._model_registry = model_registry
        self._owned_model_registry = model_registry is None
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._max_tool_turns = max(1, int(max_tool_turns))
        self._backend_base_url = backend_base_url or _get_backend_base_url()
        self._confirmation_timeout_seconds = max(0.01, float(confirmation_timeout_seconds))
        self._confirmation_stream_id = secrets.token_urlsafe(24)
        self._project_capability = project_capability
        self._active_selection_receipt = None
        self._active_client_provider: Optional[str] = (
            "lmstudio"
            if lmstudio_client is not None
            else "ollama"
            if ollama_client is not None
            else None
        )
        self._provider_failure_refresh_used = False

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    async def __aenter__(self) -> "ChatAgent":
        await self._ensure_resources()
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        await self.aclose()

    async def _ensure_resources(self) -> None:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._backend_base_url,
                timeout=httpx.Timeout(60.0, connect=5.0),
            )
        if self._model_registry is None:
            ai_cfg = self._load_ai_config()
            self._model_registry = ModelRegistry(ai_cfg)

    async def aclose(self) -> None:
        await tool_confirmation_broker.cancel_stream(self._confirmation_stream_id)
        if self._owned_http and self._http is not None:
            try:
                await self._http.aclose()
            finally:
                self._http = None
        if self._owned_llm and self._llm is not None:
            try:
                await self._llm.aclose()
            finally:
                self._llm = None
                self._active_client_provider = None

    async def _attempt_fallback(self) -> bool:
        """Invalidate once and let the next receipt select the live provider."""
        from .model_inventory import get_model_inventory_service

        if self._provider_failure_refresh_used:
            return False
        self._provider_failure_refresh_used = True
        inventory = get_model_inventory_service()
        inventory.invalidate()
        snapshot = await inventory.refresh()
        return any(
            model.installed and model.usable and "chat" in model.capabilities
            for model in snapshot.models
        )

    @staticmethod
    def _load_ai_config() -> dict:
        try:
            from pb_studio.config_manager import ConfigManager
            ai = ConfigManager().get("ai") or {}
            if isinstance(ai, dict):
                return ai
        except Exception as exc:
            logger.debug("AI-Config nicht ladbar fuer ChatAgent: %s", exc)
        return {}

    async def _pick_chat_model(
        self,
        mode: str,
        *,
        exclude: set[tuple[str, str]] | None = None,
        explicit_model: Optional[str] = None,
    ):
        """Select a receipt and bind the HTTP client to its exact provider."""
        await self._ensure_resources()
        assert self._model_registry is not None
        from .llm_provider import DEFAULT_GENERATION_TIMEOUT, get_llm_client
        from .model_inventory import get_model_inventory_service

        snapshot = await get_model_inventory_service().refresh()
        excluded = set(exclude or set())

        for task in ("chat_tool_use", "chat_general", "chat"):
            try:
                receipt = self._model_registry.select_receipt_for_task(
                    snapshot,
                    task,
                    mode,
                    explicit_model=explicit_model,
                    exclude=excluded,
                )
                if self._active_client_provider != receipt.provider:
                    if self._llm is not None and self._owned_llm:
                        await self._llm.aclose()
                    self._llm = get_llm_client(
                        provider=receipt.provider,
                        timeout_seconds=DEFAULT_GENERATION_TIMEOUT,
                    )
                    self._owned_llm = True
                    self._active_client_provider = receipt.provider
                self._active_selection_receipt = receipt
                logger.info("ModelSelectionReceipt: %s", receipt.to_dict())
                return (
                    receipt.model_id,
                    f"{receipt.reason} provider={receipt.provider} source={receipt.source}",
                )
            except (NoSuitableModelError, ModelRegistryError):
                continue
        raise NoSuitableModelError(
            "Kein chat-fähiges Modell mit verifizierter Provider-Capability verfügbar."
        )

    def _selection_event_payload(
        self,
        model: str,
        reason: str,
        mode: str,
    ) -> dict[str, Any]:
        receipt = self._active_selection_receipt
        return {
            "model": model,
            "provider": getattr(receipt, "provider", None),
            "reason": reason,
            "mode": mode,
            "selection_receipt": (
                receipt.to_dict() if receipt is not None else None
            ),
        }

    def _current_provider(self) -> str:
        return (
            getattr(self._active_selection_receipt, "provider", None)
            or self._active_client_provider
            or "unknown"
        )

    @staticmethod
    def _provider_label(provider: str) -> str:
        return {
            "lmstudio": "LM Studio",
            "ollama": "Ollama",
        }.get(provider, provider)

    def _parse_tool_call(
        self, tool_call: dict[str, Any]
    ) -> tuple[str, dict[str, Any], Any]:
        function = tool_call.get("function") or {}
        name = function.get("name") or tool_call.get("name") or ""
        raw_args = function.get("arguments") if "arguments" in function else tool_call.get("arguments")
        if isinstance(raw_args, dict):
            args = raw_args
        elif isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                args = parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                args = {"_raw_arguments": raw_args}
        else:
            args = {}
        return name, args, self._registry.get(name)

    async def _dispatch_tool(
        self,
        tool_call: Optional[dict[str, Any]] = None,
        *,
        confirmation_id: Optional[str] = None,
    ):
        if confirmation_id is not None:
            confirmed = await tool_confirmation_broker.consume(
                confirmation_id, stream_id=self._confirmation_stream_id
            )
            if confirmed is None:
                return {"error": "Tool-Bestaetigung ungueltig, abgelaufen oder bereits verwendet"}
            name, args = confirmed
            tool = self._registry.get(name)
        else:
            if tool_call is None:
                return {"error": "Tool-Aufruf fehlt"}
            name, args, tool = self._parse_tool_call(tool_call)
        if tool is None:
            return {
                "error": f"Unbekanntes Tool: {name!r}",
                "available_tools": [t.name for t in self._registry.all()],
            }
        if tool.destructive and confirmation_id is None:
            return {
                "error": "Serverseitige Tool-Bestaetigung erforderlich",
                "tool": tool.name,
            }
        await self._ensure_resources()
        assert self._http is not None
        return await self._invoke_tool_handler(tool, name, args)

    async def _invoke_tool_handler(self, tool: Any, name: str, args: dict[str, Any]):
        # P-H2 (Audit V2): long-running Tools (Render, Stems) brauchen
        # erweiterten Timeout — default 60s killt sonst aktive GPU-Tasks
        # unter dem ChatAgent. 600s = 10min Headroom.
        with project_capability_scope(self._project_capability):
            if getattr(tool, "long_running", False):
                extended_http = httpx.AsyncClient(
                    base_url=self._backend_base_url,
                    timeout=httpx.Timeout(600.0, connect=5.0),
                )
                try:
                    result = await tool.handler(args, http_client=extended_http)
                except Exception as exc:
                    logger.exception("Tool-Handler %s failed: %s", name, exc)
                    return {"error": f"Tool-Handler-Exception: {exc}", "tool": name}
                finally:
                    await extended_http.aclose()
                return result

            try:
                result = await tool.handler(args, http_client=self._http)
            except Exception as exc:
                logger.exception("Tool-Handler %s failed: %s", name, exc)
                return {
                    "error": f"Tool-Handler-Exception: {exc}",
                    "tool": name,
                }
            return result

    @staticmethod
    def _truncate_tool_result(result, *, max_chars: int = 4000) -> str:
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 50] + " ...[TRUNCATED]"

    async def process_message(
        self,
        user_text: str,
        history=None,
        *,
        mode: str = "balance",
        model_override: Optional[str] = None,
    ) -> AsyncIterator[ChatEvent]:
        await self._ensure_resources()
        self._provider_failure_refresh_used = False

        try:
            model, reason = await self._pick_chat_model(
                mode,
                explicit_model=model_override,
            )
        except NoSuitableModelError as exc:
            _publish_status("none", "failed", 0.0)
            yield ChatEvent("error", {"message": str(exc), "stage": "model_selection"})
            yield ChatEvent("done", {"reason": "no_model"})
            return
        assert self._llm is not None

        model_payload = self._selection_event_payload(model, reason, mode)
        active_provider = model_payload["provider"] or ""
        yield ChatEvent("model", model_payload)
        _publish_status(model, "loading", 50.0, provider=active_provider)

        messages = [{"role": "system", "content": self._system_prompt}]
        if history:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content")
                if role in {"user", "assistant", "system"} and isinstance(content, str):
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})

        tools_schema = self._registry.openai_schema()

        final_text = ""
        # Set von Modellen die fehlgeschlagen sind (z.B. nicht geladen in LM Studio)
        # Bei Model-Fehlern wird das naechste Modell probiert statt sofort Provider-Fallback.
        _failed_models: set[tuple[str, str]] = set()
        # Two local model failures plus one receipt after the single provider
        # refresh yields the contract maximum of three distinct candidates.
        MAX_MODEL_RETRIES = 2
        # Audit-Fix 2026-07-10 (Sweep-Finding CHAT-7): 8 von 9 Fehler-Pfaden unten
        # (return nach yield ChatEvent("done",...)) publizierten nie einen
        # finalen llm_status — Widget blieb bei "loading" haengen. Statt jeden
        # der 8 Pfade einzeln zu patchen: try/finally garantiert GENAU EINEN
        # finalen Status-Publish, egal welcher Pfad greift oder ob spaeter ein
        # neuer Pfad hinzukommt. finally darf NICHT yielden (Generator-Semantik
        # bei aclose()) — nur der reine _publish_status()-Funktionsaufruf.
        _status_final_published = False

        try:
            for turn in range(self._max_tool_turns):
                try:
                    response = await self._llm.chat(
                        model=model,
                        messages=messages,
                        tools=tools_schema,
                        options={"temperature": 0.2},
                    )
                except LMStudioError as exc:
                    msg_lower = str(exc).lower()
                    status_code = getattr(exc, "status_code", None)
                    tools_retry_succeeded = False

                    # Fall 1: Modell unterstuetzt keine Tools → Retry ohne Tools
                    if (
                        ("tools" in msg_lower or "function" in msg_lower)
                        and status_code in {None, 400, 422}
                    ):
                        logger.info("Modell %s unterstuetzt 'tools' nicht - Retry ohne Tool-Use", model)
                        try:
                            response = await self._llm.chat(
                                model=model,
                                messages=messages,
                                options={"temperature": 0.2},
                            )
                        except LMStudioError as exc2:
                            # Der Retry ohne Tool-Schema ist ein normaler
                            # Provider-Call. Sein Fehler muss durch dieselbe
                            # statusbasierte Kette wie der erste Call laufen.
                            exc = exc2
                            msg_lower = str(exc2).lower()
                            status_code = getattr(exc2, "status_code", None)
                        else:
                            tools_retry_succeeded = True

                    # Fall 1b: Read-Timeout → Modell ist zu langsam, NICHT "nicht geladen".
                    # Auf andere (evtl. ungeladene) Modelle zu wechseln macht es schlimmer,
                    # daher ehrlich melden und abbrechen statt durch alle Modelle zu churnen.
                    if tools_retry_succeeded:
                        pass
                    elif ("timeout" in msg_lower) and not isinstance(exc, LMStudioConnectionError):
                        provider = self._current_provider()
                        logger.warning("Read-Timeout bei Modell %r (Turn %s): %s", model, turn, exc)
                        yield ChatEvent("error", {
                            "message": (
                                f"Modell '{model}' hat nicht rechtzeitig geantwortet (Timeout). "
                                f"Das Modell ist geladen, braucht aber laenger als erlaubt — "
                                f"evtl. ein langsames Reasoning-Modell oder gerade beim Laden. "
                                f"Bitte erneut versuchen oder ein schnelleres Modell waehlen."
                            ),
                            "stage": "chat",
                            "provider": provider,
                            "model": model,
                        })
                        yield ChatEvent("done", {"reason": "timeout"})
                        return

                    # Fall 1c: Request-/Auth-4xx sind weder Provider-Ausfall noch
                    # "Modell nicht geladen" und duerfen keine Modellkaskade starten.
                    elif status_code in {400, 401, 403, 422}:
                        provider = self._current_provider()
                        provider_label = self._provider_label(provider)
                        logger.warning(
                            "Request von %s abgelehnt (HTTP %s) bei Modell %r: %s",
                            provider_label,
                            status_code,
                            model,
                            exc,
                        )
                        if status_code in {401, 403}:
                            detail = (
                                f"{provider_label} hat die Anfrage wegen fehlender "
                                "oder ungueltiger Authentifizierung abgelehnt."
                            )
                            reason_code = "provider_auth"
                        else:
                            detail = (
                                f"{provider_label} hat die Anfrage abgelehnt "
                                f"(HTTP {status_code}).\n\n"
                                f"Moegliche Ursache: Der Chat-Verlauf passt nicht in "
                                f"das Kontextfenster von '{model}' oder der Request "
                                "enthaelt ungueltige Parameter."
                            )
                            reason_code = "request_rejected"
                        yield ChatEvent("error", {
                            "message": detail,
                            "stage": "chat",
                            "provider": provider,
                            "model": model,
                            "status_code": status_code,
                        })
                        yield ChatEvent("done", {"reason": reason_code})
                        return

                    # Fall 2: Provider-Fehler (Connection, 429, 5xx) →
                    # genau ein Live-Inventar-Refresh, danach Receipt-Wahrheit.
                    elif is_provider_failure(exc):
                        logger.warning(
                            "Provider-Fehler im Chat-Turn %s: %s. "
                            "Versuche Live-Inventar-Refresh...",
                            turn,
                            exc,
                        )
                        failed_provider = self._current_provider()
                        _failed_models.add((failed_provider, model))

                        if await self._attempt_fallback():
                            try:
                                model, reason = await self._pick_chat_model(
                                    mode,
                                    explicit_model=model_override,
                                    exclude=_failed_models,
                                )

                                model_payload = self._selection_event_payload(
                                    model,
                                    reason,
                                    mode,
                                )
                                active_provider = model_payload["provider"] or ""
                                selected_provider = active_provider or "unknown"
                                if selected_provider == failed_provider:
                                    fallback_message = (
                                        f"{self._provider_label(failed_provider)} ist "
                                        f"weiter erreichbar; versuche den naechsten "
                                        f"verwendbaren Kandidaten '{model}'."
                                    )
                                else:
                                    fallback_message = (
                                        f"{self._provider_label(failed_provider)} ist "
                                        f"fehlgeschlagen. Wechsle automatisch auf "
                                        f"{selected_provider}."
                                    )
                                yield ChatEvent("error", {
                                    "message": fallback_message,
                                    "stage": "fallback",
                                    "provider": failed_provider,
                                    "fallback_provider": selected_provider,
                                    "model": model,
                                })
                                yield ChatEvent("model", model_payload)
                                _publish_status(
                                    model,
                                    "loading",
                                    50.0,
                                    provider=active_provider,
                                )

                                response = await self._llm.chat(
                                    model=model,
                                    messages=messages,
                                    tools=tools_schema,
                                    options={"temperature": 0.2},
                                )
                            except Exception as exc_fallback:
                                fallback_provider = self._current_provider()
                                yield ChatEvent("error", {
                                    "message": (
                                        "Chat nach Live-Inventar-Refresh mit "
                                        f"{self._provider_label(fallback_provider)} "
                                        f"fehlgeschlagen: {exc_fallback}"
                                    ),
                                    "stage": "chat_fallback",
                                    "provider": fallback_provider,
                                    "model": model,
                                })
                                yield ChatEvent("done", {"reason": "llm_error"})
                                return
                        else:
                            provider_label = self._provider_label(failed_provider)
                            error_msg = (
                                f"{provider_label} ist fuer diesen Chat nicht mehr "
                                "verwendbar; das aktualisierte Live-Inventar enthaelt "
                                "keinen weiteren Chat-Kandidaten.\n\n"
                                f"Fehlerklasse: {type(exc).__name__}"
                            )
                            yield ChatEvent("error", {
                                "message": error_msg,
                                "stage": "chat",
                                "provider": failed_provider,
                                "model": model,
                            })
                            yield ChatEvent("done", {"reason": "llm_error"})
                            return

                    # Fall 3: Model-Fehler (z.B. nicht geladen) → naechstes Modell versuchen
                    else:
                        failed_provider = self._current_provider()
                        _failed_models.add((failed_provider, model))
                        logger.warning(
                            "Modell %r fehlgeschlagen (Turn %s): %s. Versuche naechstes Modell... (fehlgeschlagen: %s)",
                            model, turn, exc, _failed_models
                        )

                        if len(_failed_models) >= MAX_MODEL_RETRIES:
                            # Zu viele Modell-Fehler → Provider-Fallback versuchen
                            logger.warning(
                                "%d Modelle fehlgeschlagen auf diesem Provider. Versuche Provider-Fallback...",
                                len(_failed_models)
                            )
                            if await self._attempt_fallback():
                                try:
                                    model, reason = await self._pick_chat_model(
                                        mode,
                                        exclude=_failed_models,
                                    )
                                    reason = f"{reason} (nach Live-Inventar-Refresh)"
                                    model_payload = self._selection_event_payload(
                                        model,
                                        reason,
                                        mode,
                                    )
                                    active_provider = model_payload["provider"] or ""
                                    yield ChatEvent("model", model_payload)
                                    _publish_status(
                                        model,
                                        "loading",
                                        50.0,
                                        provider=active_provider,
                                    )
                                    continue  # Retry den Turn mit neuem Modell+Provider
                                except NoSuitableModelError as exc_no_model:
                                    yield ChatEvent("error", {"message": str(exc_no_model), "stage": "model_selection"})
                                    yield ChatEvent("done", {"reason": "no_model"})
                                    return
                            else:
                                yield ChatEvent("error", {
                                    "message": (
                                        "Kein Modell konnte den Chat ausfuehren. "
                                        f"{len(_failed_models)} Kandidaten fehlgeschlagen: "
                                        f"{_failed_models}. Das Live-Inventar enthaelt "
                                        "keinen weiteren verwendbaren Chat-Kandidaten."
                                    ),
                                    "stage": "chat"
                                })
                                yield ChatEvent("done", {"reason": "llm_error"})
                                return

                        # Naechstes Modell auswaehlen (ohne die fehlgeschlagenen)
                        try:
                            if not model_override:
                                new_model, new_reason = await self._pick_chat_model(mode, exclude=_failed_models)
                                yield ChatEvent("error", {
                                    "message": f"Modell '{model}' nicht verfuegbar (evtl. nicht geladen). Wechsle auf '{new_model}'...",
                                    "stage": "model_retry"
                                })
                                model = new_model
                                reason = new_reason
                                model_payload = self._selection_event_payload(
                                    model,
                                    reason,
                                    mode,
                                )
                                active_provider = model_payload["provider"] or ""
                                yield ChatEvent("model", model_payload)
                                _publish_status(
                                    model,
                                    "loading",
                                    50.0,
                                    provider=active_provider,
                                )
                                continue  # Retry den Turn mit neuem Modell
                            else:
                                # Bei model_override kein Retry mit anderem Modell
                                yield ChatEvent("error", {
                                    "message": (
                                        f"Explizites Modell '{model}' "
                                        f"fehlgeschlagen ({type(exc).__name__})."
                                    ),
                                    "stage": "chat",
                                })
                                yield ChatEvent("done", {"reason": "llm_error"})
                                return
                        except NoSuitableModelError:
                            yield ChatEvent("error", {
                                "message": f"Kein weiteres Modell verfuegbar. Fehlgeschlagen: {_failed_models}.",
                                "stage": "chat"
                            })
                            yield ChatEvent("done", {"reason": "no_model"})
                            return

                message = response.get("message") or {}
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls") or []

                if content and not tool_calls:
                    final_text = content
                    yield ChatEvent("text", {"content": content})
                    break

                if tool_calls:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": tool_calls,
                    }
                    messages.append(assistant_msg)

                    for tc in tool_calls:
                        function = tc.get("function") or {}
                        tool_name = function.get("name") or tc.get("name") or ""
                        raw_args = function.get("arguments")
                        tool_call_id = tc.get("id") or ""
                        yield ChatEvent("tool_call", {
                            "name": tool_name,
                            "arguments": raw_args,
                            "id": tool_call_id,
                        })

                        _parsed_name, parsed_args, parsed_tool = self._parse_tool_call(tc)
                        if parsed_tool is not None and parsed_tool.destructive:
                            pending = await tool_confirmation_broker.request(
                                stream_id=self._confirmation_stream_id,
                                tool_name=parsed_tool.name,
                                args=parsed_args,
                                timeout_seconds=self._confirmation_timeout_seconds,
                            )
                            yield ChatEvent("tool_confirmation_required", {
                                "confirmation_id": pending.confirmation_id,
                                "name": parsed_tool.name,
                                "arguments": pending.canonical_args,
                                "expires_in_seconds": self._confirmation_timeout_seconds,
                            })
                            if await tool_confirmation_broker.wait(pending):
                                result = await self._dispatch_tool(
                                    confirmation_id=pending.confirmation_id
                                )
                            else:
                                result = {
                                    "error": "Tool-Aufruf abgelehnt oder Bestaetigung abgelaufen",
                                    "tool": parsed_tool.name,
                                }
                        else:
                            result = await self._dispatch_tool(tc)
                        # M3-Fix (P-M1, 2026-05-20): Wenn Tool-Result einen "error"-key
                        # hat (Tool-Handler-Exception oder unknown-tool), zusaetzlich
                        # ChatEvent("error",...) emittieren — sonst sieht UI im Frontend
                        # nur ein normales tool_result und der User merkt nicht, dass
                        # das Tool versagt hat.
                        if isinstance(result, dict) and "error" in result:
                            yield ChatEvent("error", {
                                "message": str(result.get("error", "Tool failure")),
                                "stage": "tool_dispatch",
                                "tool": tool_name,
                                "tool_call_id": tool_call_id,
                            })
                        yield ChatEvent("tool_result", {
                            "name": tool_name,
                            "result": result,
                            "id": tool_call_id,
                        })

                        tool_msg = {
                            "role": "tool",
                            "content": self._truncate_tool_result(result),
                            "name": tool_name,
                        }
                        if tool_call_id:
                            tool_msg["tool_call_id"] = tool_call_id
                        messages.append(tool_msg)
                    continue

                yield ChatEvent("text", {"content": ""})
                break
            else:
                try:
                    response = await self._llm.chat(
                        model=model,
                        messages=messages + [{
                            "role": "user",
                            "content": (
                                "Bitte fasse das Ergebnis der bisherigen Tool-Aufrufe "
                                "in 1-3 Saetzen zusammen - keine weiteren Tool-Calls."
                            ),
                        }],
                        options={"temperature": 0.2},
                    )
                    final_text = (response.get("message") or {}).get("content") or ""
                    yield ChatEvent("text", {"content": final_text})
                except LMStudioError as exc:
                    logger.warning(
                        "LMStudioError bei finaler Zusammenfassung: %s",
                        exc,
                    )
                    failed_provider = self._current_provider()
                    _failed_models.add((failed_provider, model))
                    if not is_provider_failure(exc):
                        yield ChatEvent("error", {
                            "message": (
                                "Zusammenfassung von "
                                f"{self._provider_label(failed_provider)} "
                                f"abgelehnt ({type(exc).__name__}: {exc})."
                            ),
                            "stage": "summary",
                            "provider": failed_provider,
                            "model": model,
                            "status_code": getattr(exc, "status_code", None),
                        })
                    elif await self._attempt_fallback():
                        try:
                            model, reason = await self._pick_chat_model(
                                mode,
                                explicit_model=model_override,
                                exclude=_failed_models,
                            )
                            model_payload = self._selection_event_payload(
                                model,
                                reason,
                                mode,
                            )
                            active_provider = model_payload["provider"] or ""
                            selected_provider = active_provider or "unknown"
                            yield ChatEvent("error", {
                                "message": (
                                    f"{self._provider_label(failed_provider)} ist "
                                    "beim Zusammenfassen fehlgeschlagen. "
                                    f"Versuche {selected_provider} mit '{model}'."
                                ),
                                "stage": "fallback",
                                "provider": failed_provider,
                                "fallback_provider": selected_provider,
                                "model": model,
                            })
                            yield ChatEvent("model", model_payload)
                            _publish_status(
                                model,
                                "loading",
                                50.0,
                                provider=active_provider,
                            )

                            response = await self._llm.chat(
                                model=model,
                                messages=messages + [{
                                    "role": "user",
                                    "content": (
                                        "Bitte fasse das Ergebnis der bisherigen Tool-Aufrufe "
                                        "in 1-3 Saetzen zusammen - keine weiteren Tool-Calls."
                                    ),
                                }],
                                options={"temperature": 0.2},
                            )
                            final_text = (response.get("message") or {}).get("content") or ""
                            yield ChatEvent("text", {"content": final_text})
                        except Exception as exc_fallback:
                            fallback_provider = self._current_provider()
                            yield ChatEvent("error", {
                                "message": (
                                    "Zusammenfassung nach Live-Inventar-Refresh mit "
                                    f"{self._provider_label(fallback_provider)} "
                                    f"fehlgeschlagen ({type(exc_fallback).__name__})."
                                ),
                                "stage": "summary_fallback",
                                "provider": fallback_provider,
                                "model": model,
                            })
                    else:
                        yield ChatEvent("error", {
                            "message": (
                                f"{self._provider_label(failed_provider)} ist beim "
                                "Zusammenfassen fehlgeschlagen; das aktualisierte "
                                "Live-Inventar enthaelt keinen weiteren Kandidaten."
                            ),
                            "stage": "summary",
                            "provider": failed_provider,
                            "model": model,
                        })

            # Audit 2026-08-05 (M-5): Bei Erfolg wurde "active" gesendet und nie
            # zurueckgesetzt -- der Statusbalken blieb dauerhaft gruen auf "Aktiv",
            # auch wenn seit einer halben Stunde nichts lief. Ein beendeter Turn
            # ist "idle", nicht "active".
            if final_text:
                _publish_status(model, "idle", 100.0, provider=active_provider)
            else:
                _publish_status(model, "failed", 0.0, provider=active_provider)
            _status_final_published = True
            yield ChatEvent("done", {"final_text": final_text})
        finally:
            if not _status_final_published:
                _publish_status(model, "failed", 0.0, provider=active_provider)


__all__ = [
    "ChatAgent",
    "ChatEvent",
    "DEFAULT_SYSTEM_PROMPT",
    "ToolConfirmationBroker",
    "tool_confirmation_broker",
]
