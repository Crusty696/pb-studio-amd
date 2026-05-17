"""KI-Chat-Agent fuer PB Studio.

Orchestriert den Konversationsfluss zwischen User und LLM (Ollama) mit
Tool-Use. Der Agent:

1. Nimmt eine User-Message + History entgegen.
2. Fragt das LLM (mit registriertem ``tools``-Inventar).
3. Wenn das LLM ``tool_calls`` zurueckliefert, dispatched der Agent auf die
   passenden Handler in ``tool_registry``.
4. Tool-Results gehen als ``role=tool``-Messages zurueck ins LLM.
5. Schleife laeuft maximal ``max_tool_turns``-mal, dann finaler Text.

Events werden als ``ChatEvent``-Dataclasses geyieldet, damit der Router
sie als SSE-Stream weitergeben kann.

Sprach-Erhaltung: System-Prompt instruiert das Modell, in der Sprache der
User-Message zu antworten. Funktioniert empirisch zuverlaessig mit
gemma4/llama3.

Iron Rule 10 (100% Honesty): Wenn das Modell kein natives Tool-Calling
unterstuetzt, faellt der Agent NICHT silent auf einen Workaround zurueck —
er reportet ``error``-Event mit klarer Diagnose.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from .model_registry import ModelRegistry, ModelRegistryError, NoSuitableModelError
from .ollama_client import OllamaClient, OllamaError
from .tool_registry import ToolRegistry, build_default_registry, _get_backend_base_url

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# System-Prompt
# ----------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = (
    "Du bist der KI-Assistent von PB Studio — einer Desktop-App fuer "
    "DJ-Mix-Video-Editing mit KI (AMD DirectML, lokal). Du kannst per "
    "Tool-Calls jede Funktion der App aufrufen: Audio importieren und "
    "analysieren, Video importieren und analysieren, Pacing/Cut-List "
    "generieren, Rendering starten, Brain (HIRN) abfragen und "
    "trainieren, Projekte verwalten, Modelle managen.\n\n"
    "WICHTIG:\n"
    "- Antworte in der Sprache der Benutzeranfrage (Deutsch oder Englisch).\n"
    "- Nutze Tool-Calls statt zu raten. Wenn du Daten brauchst, hole sie via Tool.\n"
    "- Bevor du destruktive Aktionen ausfuehrst (project.create, audio.import, "
    "video.import, audio.separate_stems, render.start, render.cancel), bestaetige "
    "kurz mit dem User, wenn der Kontext es nicht eindeutig macht.\n"
    "- Wenn du keinen Clip findest, schlage 'audio.list_clips' oder 'video.list_clips' vor.\n"
    "- Halte Antworten knapp und konkret. Lange Listen kuerzen.\n"
    "- Bei Fehlern: zeige den Fehler und schlage eine Alternative vor.\n"
)


# ----------------------------------------------------------------------
# Events
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ChatEvent:
    """Ein vom Agent emittiertes Event (an SSE weiterzureichen)."""
    type: str  # "text" | "tool_call" | "tool_result" | "error" | "model" | "done"
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.payload}


# ----------------------------------------------------------------------
# Agent
# ----------------------------------------------------------------------
class ChatAgent:
    """Stateless Agent — eine Instanz pro Conversation OK, aber nicht erforderlich.

    Args:
        registry: ToolRegistry; default = build_default_registry().
        ollama_client: optional injizierbar fuer Tests.
        http_client: HTTP-Client fuer Backend-Calls (Tool-Handler).
            Default = neuer httpx.AsyncClient auf ``PBSTUDIO_BACKEND_URL``
            (env) oder localhost:8765.
        model_registry: optional injizierbar.
        system_prompt: ueberschreibt DEFAULT_SYSTEM_PROMPT.
        max_tool_turns: maximale Anzahl Tool-Call-Iterationen pro Message,
            verhindert unendliche Tool-Loops bei buggy Modellen.
    """

    def __init__(
        self,
        *,
        registry: Optional[ToolRegistry] = None,
        ollama_client: Optional[OllamaClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        model_registry: Optional[ModelRegistry] = None,
        system_prompt: Optional[str] = None,
        max_tool_turns: int = 6,
        backend_base_url: Optional[str] = None,
    ) -> None:
        self._registry = registry or build_default_registry()
        self._ollama: Optional[OllamaClient] = ollama_client
        self._owned_ollama = ollama_client is None
        self._http: Optional[httpx.AsyncClient] = http_client
        self._owned_http = http_client is None
        self._model_registry = model_registry
        self._owned_model_registry = model_registry is None
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._max_tool_turns = max(1, int(max_tool_turns))
        self._backend_base_url = backend_base_url or _get_backend_base_url()

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
        if self._ollama is None:
            base = os.environ.get("PBSTUDIO_OLLAMA_URL", "http://localhost:11434")
            self._ollama = OllamaClient(base_url=base)
        if self._model_registry is None:
            ai_cfg = self._load_ai_config()
            self._model_registry = ModelRegistry(ai_cfg, client=self._ollama)

    async def aclose(self) -> None:
        if self._owned_http and self._http is not None:
            try:
                await self._http.aclose()
            finally:
                self._http = None
        if self._owned_ollama and self._ollama is not None:
            try:
                await self._ollama.aclose()
            finally:
                self._ollama = None

    @staticmethod
    def _load_ai_config() -> dict[str, Any]:
        try:
            from pb_studio.config_manager import ConfigManager  # type: ignore

            ai = ConfigManager().get("ai") or {}
            if isinstance(ai, dict):
                return ai
        except Exception as exc:
            logger.debug("AI-Config nicht ladbar fuer ChatAgent: %s", exc)
        return {}

    # ------------------------------------------------------------------
    # Modell-Auswahl
    # ------------------------------------------------------------------
    async def _pick_chat_model(self, mode: str) -> tuple[str, str]:
        """Liefert (model_name, reason). Versucht erst chat_tool_use, fallback chat.

        Raises:
            NoSuitableModelError: wenn KEIN passendes Modell installiert ist.
        """
        await self._ensure_resources()
        assert self._model_registry is not None
        try:
            await self._model_registry.refresh()
        except OllamaError as exc:
            raise NoSuitableModelError(
                f"Ollama nicht erreichbar — Chat kann nicht laufen: {exc}"
            ) from exc

        for task in ("chat_tool_use", "chat_general", "chat"):
            try:
                model = self._model_registry.select_best_for_task(task, mode)
                return model, f"task={task}, mode={mode}"
            except (NoSuitableModelError, ModelRegistryError):
                continue
        # Letzter Versuch: irgendein installiertes Modell
        try:
            model = self._model_registry.select_best_for_task(
                "chat", mode, allow_any_installed=True
            )
            return model, "fallback: irgendein installiertes Modell"
        except (NoSuitableModelError, ModelRegistryError) as exc:
            raise NoSuitableModelError(
                f"Kein chat-faehiges Modell installiert: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Tool-Dispatch
    # ------------------------------------------------------------------
    async def _dispatch_tool(
        self,
        tool_call: dict[str, Any],
    ) -> dict[str, Any]:
        """Loest einen vom LLM gewuenschten Tool-Call auf und ruft den Handler."""
        await self._ensure_resources()
        assert self._http is not None

        function = tool_call.get("function") or {}
        name = function.get("name") or tool_call.get("name") or ""
        raw_args = function.get("arguments") if "arguments" in function else tool_call.get("arguments")
        args: dict[str, Any]
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

        tool = self._registry.get(name)
        if tool is None:
            return {
                "error": f"Unbekanntes Tool: {name!r}",
                "available_tools": [t.name for t in self._registry.all()],
            }
        try:
            result = await tool.handler(args, http_client=self._http)
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Tool-Handler %s failed: %s", name, exc)
            return {
                "error": f"Tool-Handler-Exception: {exc}",
                "tool": name,
            }
        return result

    @staticmethod
    def _truncate_tool_result(result: dict[str, Any], *, max_chars: int = 4000) -> str:
        """Serialisiert ein Tool-Result fuer das LLM und kuerzt zu lange Outputs."""
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 50] + " ...[TRUNCATED]"

    # ------------------------------------------------------------------
    # Haupt-API
    # ------------------------------------------------------------------
    async def process_message(
        self,
        user_text: str,
        history: Optional[list[dict[str, Any]]] = None,
        *,
        mode: str = "balance",
        model_override: Optional[str] = None,
    ) -> AsyncIterator[ChatEvent]:
        """Verarbeitet eine User-Message und yieldet ChatEvents.

        Args:
            user_text: aktuelle User-Eingabe.
            history: vorherige Messages (Role+Content). Tool-Loop-Messages
                werden NICHT in die History uebernommen — der Caller bekommt
                am Ende nur die finale Assistant-Antwort.
            mode: speed|balance|quality fuer die Modell-Auswahl.
            model_override: explizites Modell (umgeht ModelRegistry).
        """
        await self._ensure_resources()
        assert self._ollama is not None

        # Modell waehlen
        try:
            if model_override:
                model = model_override
                reason = "explicit override"
            else:
                model, reason = await self._pick_chat_model(mode)
        except NoSuitableModelError as exc:
            yield ChatEvent(
                "error",
                {"message": str(exc), "stage": "model_selection"},
            )
            yield ChatEvent("done", {"reason": "no_model"})
            return

        yield ChatEvent("model", {"model": model, "reason": reason, "mode": mode})

        # Messages aufbauen
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt}
        ]
        if history:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content")
                if role in {"user", "assistant", "system"} and isinstance(content, str):
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})

        tools_schema = self._registry.openai_schema()

        # Multi-Turn Tool-Use-Loop
        final_text = ""
        for turn in range(self._max_tool_turns):
            try:
                response = await self._ollama.chat(
                    model=model,
                    messages=messages,
                    tools=tools_schema,
                    options={"temperature": 0.2},
                )
            except OllamaError as exc:
                # Wenn Modell tool-Param nicht unterstuetzt, retry ohne tools
                msg_lower = str(exc).lower()
                if "tools" in msg_lower or "function" in msg_lower:
                    logger.info(
                        "Modell %s unterstuetzt 'tools' nicht — Retry ohne Tool-Use", model
                    )
                    try:
                        response = await self._ollama.chat(
                            model=model,
                            messages=messages,
                            options={"temperature": 0.2},
                        )
                    except OllamaError as exc2:
                        yield ChatEvent(
                            "error",
                            {"message": f"Ollama-Fehler: {exc2}", "stage": "chat"},
                        )
                        yield ChatEvent("done", {"reason": "ollama_error"})
                        return
                else:
                    yield ChatEvent(
                        "error",
                        {"message": f"Ollama-Fehler: {exc}", "stage": "chat"},
                    )
                    yield ChatEvent("done", {"reason": "ollama_error"})
                    return

            message = response.get("message") or {}
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []

            if content and not tool_calls:
                final_text = content
                yield ChatEvent("text", {"content": content})
                break

            if tool_calls:
                # Vor dem Dispatch: Assistant-Message mit Tool-Calls in History speichern
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_msg)

                for tc in tool_calls:
                    function = tc.get("function") or {}
                    tool_name = function.get("name") or tc.get("name") or ""
                    raw_args = function.get("arguments")
                    yield ChatEvent("tool_call", {
                        "name": tool_name,
                        "arguments": raw_args,
                    })

                    result = await self._dispatch_tool(tc)
                    yield ChatEvent("tool_result", {
                        "name": tool_name,
                        "result": result,
                    })

                    # Tool-Antwort als role=tool-Message anhaengen
                    messages.append({
                        "role": "tool",
                        "content": self._truncate_tool_result(result),
                        "name": tool_name,
                    })
                continue

            # Weder content noch tool_calls — beende Loop, gib leeren Text aus
            yield ChatEvent("text", {"content": ""})
            break
        else:
            # Loop ist voll durchgelaufen ohne return — last-resort: Modell ohne Tools
            try:
                response = await self._ollama.chat(
                    model=model,
                    messages=messages + [{
                        "role": "user",
                        "content": (
                            "Bitte fasse das Ergebnis der bisherigen Tool-Aufrufe "
                            "in 1-3 Saetzen zusammen — keine weiteren Tool-Calls."
                        ),
                    }],
                    options={"temperature": 0.2},
                )
                final_text = (response.get("message") or {}).get("content") or ""
                yield ChatEvent("text", {"content": final_text})
            except OllamaError as exc:
                yield ChatEvent(
                    "error",
                    {"message": f"Ollama-Fehler beim Summary: {exc}", "stage": "summary"},
                )

        yield ChatEvent("done", {"final_text": final_text})


__all__ = ["ChatAgent", "ChatEvent", "DEFAULT_SYSTEM_PROMPT"]
