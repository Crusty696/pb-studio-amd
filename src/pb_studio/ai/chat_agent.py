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
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from .model_registry import ModelRegistry, ModelRegistryError, NoSuitableModelError
from .lmstudio_client import LMStudioClient, LMStudioError
from .tool_registry import ToolRegistry, build_default_registry, _get_backend_base_url

logger = logging.getLogger(__name__)


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
        if self._llm is None:
            from .llm_provider import get_llm_client, get_alive_client, get_provider
            env_override = os.environ.get("PBSTUDIO_LMSTUDIO_URL") or os.environ.get("PBSTUDIO_OLLAMA_URL")
            if env_override:
                self._llm = LMStudioClient(base_url=env_override)
            else:
                provider = get_provider()
                if provider == "auto":
                    alive = await get_alive_client(timeout_seconds=5.0)
                    self._llm = alive if alive is not None else get_llm_client()
                else:
                    primary = get_llm_client(provider=provider)
                    primary_alive = False
                    try:
                        primary_alive = await primary.is_alive()
                    except Exception:
                        pass
                    
                    if primary_alive:
                        self._llm = primary
                    else:
                        other_provider = "ollama" if provider == "lmstudio" else "lmstudio"
                        secondary = get_llm_client(provider=other_provider)
                        secondary_alive = False
                        try:
                            secondary_alive = await secondary.is_alive()
                        except Exception:
                            pass
                        
                        if secondary_alive:
                            logger.warning(
                                "Primärer LLM-Provider %s ist offline. Weiche autonom im Chat auf %s aus!",
                                provider, other_provider
                            )
                            await primary.aclose()
                            self._llm = secondary
                        else:
                            await secondary.aclose()
                            self._llm = primary

        if self._model_registry is None:
            ai_cfg = self._load_ai_config()
            self._model_registry = ModelRegistry(ai_cfg, client=self._llm)

    async def aclose(self) -> None:
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

    async def _attempt_fallback(self) -> bool:
        """Versucht autonom auf den alternativen LLM-Provider zu wechseln.

        Prueft, ob der alternative Provider alive ist. Wenn ja, wird der aktuelle
        Client geschlossen, der neue Client initialisiert, die ModelRegistry
        aktualisiert und True zurueckgegeben.
        """
        if self._llm is None:
            return False

        current_url = self._llm.base_url
        from .llm_provider import get_base_url, get_llm_client

        ollama_url = get_base_url("ollama")
        # Bestimme alternative Provider
        if "11434" in current_url or current_url == ollama_url:
            other_provider = "lmstudio"
        else:
            other_provider = "ollama"

        logger.warning(
            "Verbindungsproblem mit aktuellem Provider (%s). Pruefe Fallback auf %s...",
            current_url, other_provider
        )

        secondary = get_llm_client(provider=other_provider, timeout_seconds=5.0)
        secondary_alive = False
        try:
            secondary_alive = await secondary.is_alive()
        except Exception:
            pass

        if secondary_alive:
            logger.warning(
                "Fallback-Provider %s ist online! Wechsle Client...", other_provider
            )
            # Alten Client schliessen
            if self._owned_llm:
                try:
                    await self._llm.aclose()
                except Exception:
                    pass

            # Neuen Client setzen
            self._llm = secondary
            self._owned_llm = True

            # ModelRegistry fuer den neuen Client neu erstellen/aktualisieren
            ai_cfg = self._load_ai_config()
            self._model_registry = ModelRegistry(ai_cfg, client=self._llm)
            try:
                await self._model_registry.refresh()
            except Exception as exc:
                logger.error("Fehler beim Aktualisieren der Registry nach Fallback: %s", exc)
                return False

            return True
        else:
            try:
                await secondary.aclose()
            except Exception:
                pass
            logger.error("Alternativer LLM-Provider %s ist ebenfalls offline.", other_provider)
            return False

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

    async def _pick_chat_model(self, mode: str):
        await self._ensure_resources()
        assert self._model_registry is not None
        try:
            await self._model_registry.refresh()
        except LMStudioError as exc:
            logger.warning("Fehler beim Aktualisieren der Registry: %s. Versuche Fallback...", exc)
            if await self._attempt_fallback():
                try:
                    await self._model_registry.refresh()
                except Exception as exc2:
                    raise NoSuitableModelError(
                        f"Fehler bei Registry-Refresh nach Fallback: {exc2}"
                    ) from exc2
            else:
                raise NoSuitableModelError(
                    f"LM Studio nicht erreichbar - Chat kann nicht laufen: {exc}"
                ) from exc

        for task in ("chat_tool_use", "chat_general", "chat"):
            try:
                model = self._model_registry.select_best_for_task(task, mode)
                return model, f"task={task}, mode={mode}"
            except (NoSuitableModelError, ModelRegistryError):
                continue
        try:
            model = self._model_registry.select_best_for_task(
                "chat", mode, allow_any_installed=True
            )
            return model, "fallback: irgendein installiertes Modell"
        except (NoSuitableModelError, ModelRegistryError) as exc:
            raise NoSuitableModelError(
                f"Kein chat-faehiges Modell installiert: {exc}"
            ) from exc

    async def _dispatch_tool(self, tool_call):
        await self._ensure_resources()
        assert self._http is not None

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

        tool = self._registry.get(name)
        if tool is None:
            return {
                "error": f"Unbekanntes Tool: {name!r}",
                "available_tools": [t.name for t in self._registry.all()],
            }
        # P-H2 (Audit V2): long-running Tools (Render, Stems) brauchen
        # erweiterten Timeout — default 60s killt sonst aktive GPU-Tasks
        # unter dem ChatAgent. 600s = 10min Headroom.
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
        assert self._llm is not None

        try:
            if model_override:
                model = model_override
                reason = "explicit override"
            else:
                model, reason = await self._pick_chat_model(mode)
        except NoSuitableModelError as exc:
            yield ChatEvent("error", {"message": str(exc), "stage": "model_selection"})
            yield ChatEvent("done", {"reason": "no_model"})
            return

        yield ChatEvent("model", {"model": model, "reason": reason, "mode": mode})

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
                if "tools" in msg_lower or "function" in msg_lower:
                    logger.info("Modell %s unterstuetzt 'tools' nicht - Retry ohne Tool-Use", model)
                    try:
                        response = await self._llm.chat(
                            model=model,
                            messages=messages,
                            options={"temperature": 0.2},
                        )
                    except LMStudioError as exc2:
                        yield ChatEvent("error", {"message": f"LM-Studio-Fehler: {exc2}", "stage": "chat"})
                        yield ChatEvent("done", {"reason": "llm_error"})
                        return
                else:
                    logger.warning("Verbindungsfehler im Chat-Turn %s: %s. Versuche Fallback...", turn, exc)
                    other_prov = "ollama" if "11434" not in (self._llm.base_url if self._llm else "") else "lmstudio"
                    yield ChatEvent("error", {
                        "message": f"Verbindung zu {self._llm.base_url if self._llm else 'LLM'} verloren. Wechsle automatisch auf {other_prov}...",
                        "stage": "fallback"
                    })

                    if await self._attempt_fallback():
                        try:
                            if model_override:
                                model = model_override
                                reason = "explicit override (fallback)"
                            else:
                                model, reason = await self._pick_chat_model(mode)

                            yield ChatEvent("model", {"model": model, "reason": reason, "mode": mode})

                            response = await self._llm.chat(
                                model=model,
                                messages=messages,
                                tools=tools_schema,
                                options={"temperature": 0.2},
                            )
                        except Exception as exc_fallback:
                            yield ChatEvent("error", {
                                "message": f"Fehler bei Chat nach Fallback auf {other_prov}: {exc_fallback}",
                                "stage": "chat_fallback"
                            })
                            yield ChatEvent("done", {"reason": "llm_error"})
                            return
                    else:
                        yield ChatEvent("error", {"message": f"LLM-Fehler (kein Fallback möglich): {exc}", "stage": "chat"})
                        yield ChatEvent("done", {"reason": "llm_error"})
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
                logger.warning("LMStudioError bei finaler Zusammenfassung: %s. Versuche Fallback...", exc)
                other_prov = "ollama" if "11434" not in (self._llm.base_url if self._llm else "") else "lmstudio"
                yield ChatEvent("error", {
                    "message": f"Verbindung verloren beim Zusammenfassen. Wechsle automatisch auf {other_prov}...",
                    "stage": "fallback"
                })
                if await self._attempt_fallback():
                    try:
                        if model_override:
                            model = model_override
                        else:
                            model, _ = await self._pick_chat_model(mode)

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
                        yield ChatEvent("error", {"message": f"Fehler bei Summary nach Fallback: {exc_fallback}", "stage": "summary_fallback"})
                else:
                    yield ChatEvent("error", {"message": f"LM-Studio-Fehler beim Summary: {exc}", "stage": "summary"})

        yield ChatEvent("done", {"final_text": final_text})


__all__ = ["ChatAgent", "ChatEvent", "DEFAULT_SYSTEM_PROMPT"]
