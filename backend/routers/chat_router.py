"""Chat Router — KI-Chat-Endpoints fuer PB Studio (LM Studio Tool-Use).

Endpoints:
  POST /chat/message     — SSE-Stream mit ChatEvents (text/tool_call/tool_result/...)
  GET  /chat/tools       — Inventar aller verfuegbaren Tools (Debug/UI)
  GET  /chat/history     — In-Memory-History des aktuellen Servers (optional)
  DELETE /chat/history   — History leeren

Architektur:
  * Pro Request wird ein frischer ``ChatAgent`` erzeugt (kein global state).
  * Tool-Calls gehen via HTTP-Loopback aufs eigene Backend.
  * History wird im AppState (Singleton) gehalten — vom Frontend kann auch
    eigene History-Liste mitgesendet werden, dann ueberschreibt die Request-
    History den Server-State.

Iron Rule 10: Bei Errors emittiert der Router ein ``event: error``-SSE-
Frame und beendet den Stream sauber.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pb_studio.storage.recovery_barrier import recovery_write_operation

from ..dependencies import publish_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ----------------------------------------------------------------------
# In-Memory History (Server-Side, optional)
# ----------------------------------------------------------------------
class _ChatHistoryStore:
    """Thread-safe (single-process) Speicher fuer die Chat-History.

    Begrenzte Laenge — aelteste Eintraege fallen weg.

    I-H1 (Audit V2): snapshot_for_llm(max_tokens) trimmt token-aware via
    Zeichen-Heuristik (~3 Zeichen/Token, max(1, len//3)) statt blind 200
    entries. tiktoken wurde 2026-07-08 entfernt (Offline-Robustheit, Latenz).
    Sonst silent context-overflow bei LM-Studio (typ. 32k Modelle).
    """
    MAX_ENTRIES = 200
    # I-H1 Default: 8192 ist konservativ für die meisten lokalen Modelle.
    # Caller (process_message) kann mit model-spezifischer Obergrenze überschreiben.
    DEFAULT_TOKEN_BUDGET = 8192
    # Per-Message Overhead (role-marker, separator-tokens) ChatML/OpenAI-Format.
    PER_MESSAGE_OVERHEAD_TOKENS = 4
    # Reserve fuer System-Prompt + erwartete Response.
    PROMPT_OVERHEAD_TOKENS = 1024

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Audit 2026-08-05 (H-1/T3.8): Der Store war ein reines Prozess-Singleton
        # ohne Projektbindung und ohne Serialisierung. Zwei Folgen gleichzeitig:
        # (1) nach jedem Backend-Neustart war der Verlauf weg, obwohl der User
        #     nie "leeren" gedrueckt hatte, und
        # (2) solange das Backend lief, wanderten Chats aus Projekt A ungefragt
        #     in den Kontext von Projekt B (Cross-Project-Leak).
        self._entries_by_project: dict[str | None, list[dict[str, Any]]] = {}
        self._loaded_project_keys: set[str | None] = set()
        self._active_project_key: str | None = None

    # -- Persistenz -------------------------------------------------------
    # Bewusst als JSON neben timeline.json im Projektordner statt als
    # DB-Migration: gleiches Muster wie die uebrige Projekt-Persistenz,
    # kein Schema-Bump, und beim Loeschen des Projekts verschwindet der
    # Verlauf automatisch mit.

    @staticmethod
    def _history_file(project_root: str) -> Path:
        return Path(project_root) / "chat_history.json"

    async def bind_project(self, project_root: str | None) -> str | None:
        """
        Bindet den Store an ein Projekt und laedt dessen Verlauf.

        Wird beim ersten Zugriff nach einem Projektwechsel aufgerufen. Bei
        gleichem Projekt ist der Aufruf ein No-op.
        """
        key = str(project_root) if project_root else None
        async with self._lock:
            self._active_project_key = key
            if key in self._loaded_project_keys:
                return key
            self._loaded_project_keys.add(key)
            entries: list[dict[str, Any]] = []
            self._entries_by_project[key] = entries
            if not key:
                return key
            try:
                path = self._history_file(key)
                if path.is_file():
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        entries = [
                            entry for entry in raw
                            if isinstance(entry, dict)
                            and entry.get("role") in {"user", "assistant", "system"}
                            and isinstance(entry.get("content"), str)
                        ][-self.MAX_ENTRIES:]
                        self._entries_by_project[key] = entries
            except Exception as exc:  # noqa: BLE001 - Verlauf ist nicht kritisch
                logger.warning(
                    "Chat-Verlauf konnte nicht geladen werden: %s: %r",
                    type(exc).__name__,
                    exc,
                )
            return key

    def _persist_unlocked(
        self,
        project_key: str | None,
        entries: list[dict[str, Any]],
    ) -> None:
        """Schreibt den Verlauf. Aufrufer haelt bereits den Lock."""
        if not project_key:
            return
        try:
            path = self._history_file(project_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(entries, handle, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Chat-Verlauf konnte nicht gespeichert werden: %s: %r",
                type(exc).__name__,
                exc,
            )
            raise

    def _count_tokens(self, text: str) -> int:
        """Token-count via max(1, len(text) // 3) heuristic."""
        return max(1, len(text) // 3)

    @recovery_write_operation("chat-history")
    async def append(
        self,
        role: str,
        content: str,
        *,
        project_key: str | None,
        commit_guard: Callable[[], Any] | None = None,
    ) -> None:
        async with self._lock:
            guard = commit_guard() if commit_guard is not None else nullcontext()
            with guard:
                entries = self._entries_by_project.setdefault(project_key, [])
                entries.append({"role": role, "content": content})
                if len(entries) > self.MAX_ENTRIES:
                    # Behalte die letzten MAX_ENTRIES
                    entries = entries[-self.MAX_ENTRIES:]
                    self._entries_by_project[project_key] = entries
                self._persist_unlocked(project_key, entries)

    async def snapshot(
        self,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            key = self._active_project_key if project_key is None else project_key
            return list(self._entries_by_project.get(key, []))

    def trim_for_llm(
        self,
        entries: list[dict[str, Any]],
        *,
        max_tokens: int = DEFAULT_TOKEN_BUDGET,
        reserved_tokens: int = 0,
    ) -> list[dict[str, Any]]:
        budget = max(
            0,
            max_tokens - self.PROMPT_OVERHEAD_TOKENS - max(0, reserved_tokens),
        )
        kept: list[dict[str, Any]] = []
        total = 0
        for entry in reversed(entries):
            entry_tokens = (
                self._count_tokens(entry.get("content", ""))
                + self.PER_MESSAGE_OVERHEAD_TOKENS
            )
            if total + entry_tokens > budget:
                break
            kept.append(entry)
            total += entry_tokens
        kept.reverse()
        return kept

    async def snapshot_for_llm(
        self,
        max_tokens: int = DEFAULT_TOKEN_BUDGET,
        *,
        reserved_tokens: int = 0,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """I-H1 fix: liefert History oldest-first-trimmed bis token-budget erfuellt ist.

        Rechnet pro Eintrag content-tokens + PER_MESSAGE_OVERHEAD_TOKENS,
        reserviert PROMPT_OVERHEAD_TOKENS fuer System + Response.
        """
        async with self._lock:
            key = self._active_project_key if project_key is None else project_key
            entries = list(self._entries_by_project.get(key, []))
        return self.trim_for_llm(
            entries,
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens,
        )

    @recovery_write_operation("chat-history")
    async def clear(self, project_key: str | None = None) -> None:
        async with self._lock:
            key = self._active_project_key if project_key is None else project_key
            entries = self._entries_by_project.setdefault(key, [])
            entries.clear()
            self._persist_unlocked(key, entries)


_history_store = _ChatHistoryStore()


async def _bind_history_to_active_project() -> str | None:
    """
    Bindet den Chat-Verlauf an das aktuell geoeffnete Projekt.

    Audit 2026-08-05 (H-1/T3.8): Ohne diese Bindung teilten sich alle Projekte
    denselben Prozess-Speicher — Chats aus Projekt A landeten im Kontext von
    Projekt B. Wird vor jedem Zugriff aufgerufen; bei unveraendertem Projekt
    ist es ein No-op.
    """
    try:
        from ..app_state import get_app_state

        state = get_app_state()
        async with state.project_operation() as context:
            return await _history_store.bind_project(str(context.project_root))
    except Exception as exc:  # noqa: BLE001 - Chat darf daran nie scheitern
        logger.debug("Chat-Projektbindung uebersprungen: %r", exc)
        return await _history_store.bind_project(None)


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------
class ChatHistoryEntry(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    history: Optional[list[ChatHistoryEntry]] = Field(
        default=None,
        description="Optional: vom Frontend gemanagte History. None = Server-History benutzen.",
    )
    mode: str = Field(default="balance", pattern="^(speed|balance|quality)$")
    model_override: Optional[str] = Field(default=None, description="Explizites Modell")
    save_history: bool = Field(default=True)


class ToolInventoryEntry(BaseModel):
    name: str
    llm_name: str
    description: str
    category: str
    destructive: bool
    parameters: dict[str, Any]


class ToolInventoryResponse(BaseModel):
    count: int
    tools: list[ToolInventoryEntry]


class HistoryResponse(BaseModel):
    entries: list[ChatHistoryEntry]
    count: int


class StatusResponse(BaseModel):
    status: str


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
def _sse_frame(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/message")
async def post_message(request: ChatMessageRequest) -> StreamingResponse:
    """SSE-Stream — verarbeitet eine User-Message und liefert ChatEvents."""
    # Wichtig: Agent + Resourcen sind PRO Request — sonst Lebenszyklus-Konflikte.
    from pb_studio.ai.chat_agent import ChatAgent  # lazy

    user_text = request.message
    reserved_tokens = (
        _history_store._count_tokens(user_text)
        + _history_store.PER_MESSAGE_OVERHEAD_TOKENS
    )
    save_history = request.save_history
    mode = request.mode
    model_override = request.model_override

    async def _generator():
        from ..app_state import (
            ProjectContextChangedError,
            ProjectContextUnavailableError,
            get_app_state,
        )

        state = get_app_state()
        context = None
        project_capability: str | None = None
        try:
            async with state.project_operation() as context:
                project_key = await _history_store.bind_project(
                    str(context.project_root)
                )
                if request.history is not None:
                    history = _history_store.trim_for_llm(
                        [h.model_dump() for h in request.history],
                        reserved_tokens=reserved_tokens,
                    )
                else:
                    history = await _history_store.snapshot_for_llm(
                        reserved_tokens=reserved_tokens,
                        project_key=project_key,
                    )

                project_capability = state.issue_project_capability(context)
                commit_guard = lambda: state.project_commit(context)

                if save_history:
                    await _history_store.append(
                        "user",
                        user_text,
                        project_key=project_key,
                        commit_guard=commit_guard,
                    )

                await publish_log(
                    "Chat-Anfrage erhalten",
                    level="info",
                    detail=f"characters={len(user_text)}",
                    source="chat.user",
                )

                final_text = ""
                agent = ChatAgent(project_capability=project_capability)
                async with agent:
                    async for ev in agent.process_message(
                        user_text,
                        history=history,
                        mode=mode,
                        model_override=model_override,
                    ):
                        state.require_project_context_current(context)
                        if ev.type == "text":
                            content = ev.payload.get("content", "")
                            final_text = content
                            yield _sse_frame("text", {"content": content})
                        elif ev.type == "tool_call":
                            await publish_log(
                                "Chat-Toolaufruf gestartet",
                                level="info",
                                source="chat.tool",
                            )
                            yield _sse_frame("tool_call", ev.payload)
                        elif ev.type == "tool_result":
                            await publish_log(
                                "Chat-Toolaufruf beendet",
                                level="info",
                                source="chat.tool",
                            )
                            yield _sse_frame("tool_result", ev.payload)
                        elif ev.type == "model":
                            yield _sse_frame("model", ev.payload)
                        elif ev.type == "error":
                            await publish_log(
                                "Chat-Modellfehler",
                                level="error",
                                source="chat.error",
                            )
                            yield _sse_frame("error", ev.payload)
                        elif ev.type == "done":
                            if save_history and final_text:
                                await _history_store.append(
                                    "assistant",
                                    final_text,
                                    project_key=project_key,
                                    commit_guard=commit_guard,
                                )
                            await publish_log(
                                "Chat-Antwort abgeschlossen",
                                level="info",
                                detail=f"characters={len(final_text)}",
                                source="chat.assistant",
                            )
                            yield _sse_frame("done", ev.payload)
                        else:
                            yield _sse_frame(ev.type, ev.payload)
        except asyncio.CancelledError:
            if context is None or state.is_project_context_current(context):
                raise
            yield _sse_frame("error", {
                "message": "Projekt wurde während des Chat-Turns gewechselt",
                "stage": "project_context",
                "code": "project_context_changed",
                "status_code": 409,
            })
            yield _sse_frame("done", {"reason": "project_context_changed"})
        except ProjectContextUnavailableError as exc:
            yield _sse_frame("error", {
                "message": str(exc),
                "stage": "project_context",
                "code": "project_context_unavailable",
                "status_code": 409,
            })
            yield _sse_frame("done", {"reason": "project_context_unavailable"})
        except ProjectContextChangedError as exc:
            yield _sse_frame("error", {
                "message": str(exc),
                "stage": "project_context",
                "code": "project_context_changed",
                "status_code": 409,
            })
            yield _sse_frame("done", {"reason": "project_context_changed"})
        except Exception as exc:  # pragma: no cover — defensive
            logger.error("chat_router: unerwarteter Fehler ohne Payload")
            await publish_log(
                "Chat-Anfrage fehlgeschlagen",
                level="error",
                source="chat.error",
            )
            yield _sse_frame("error", {
                "message": f"Unerwarteter Server-Fehler: {exc}",
                "stage": "stream",
                "code": "stream_error",
            })
            yield _sse_frame("done", {"reason": "exception"})
        finally:
            state.revoke_project_capability(project_capability)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm/{confirmation_id}/approve", response_model=StatusResponse)
async def approve_tool_confirmation(confirmation_id: str) -> StatusResponse:
    """Approves exactly the server-stored tool name and arguments."""
    from pb_studio.ai.chat_agent import tool_confirmation_broker

    if not await tool_confirmation_broker.decide(confirmation_id, approve=True):
        raise HTTPException(
            status_code=409,
            detail="Bestaetigung ungueltig, abgelaufen oder bereits entschieden",
        )
    return StatusResponse(status="approved")


@router.post("/confirm/{confirmation_id}/reject", response_model=StatusResponse)
async def reject_tool_confirmation(confirmation_id: str) -> StatusResponse:
    """Rejects a pending tool call; no arguments are accepted from the client."""
    from pb_studio.ai.chat_agent import tool_confirmation_broker

    if not await tool_confirmation_broker.decide(confirmation_id, approve=False):
        raise HTTPException(
            status_code=409,
            detail="Bestaetigung ungueltig, abgelaufen oder bereits entschieden",
        )
    return StatusResponse(status="rejected")


@router.get("/tools", response_model=ToolInventoryResponse)
async def get_tools() -> ToolInventoryResponse:
    """Liefert das Inventar aller registrierten Chat-Tools (Debug/UI)."""
    from pb_studio.ai.tool_registry import build_default_registry  # lazy

    registry = build_default_registry()
    items = registry.inventory()
    return ToolInventoryResponse(
        count=len(items),
        tools=[ToolInventoryEntry(**i) for i in items],
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    """Liefert die Server-Side Chat-History des aktiven Projekts."""
    project_key = await _bind_history_to_active_project()
    entries = await _history_store.snapshot(project_key)
    return HistoryResponse(
        entries=[ChatHistoryEntry(**e) for e in entries],
        count=len(entries),
    )


@router.delete("/history", response_model=StatusResponse)
async def clear_history() -> StatusResponse:
    """Leert die Server-Side Chat-History des aktiven Projekts."""
    project_key = await _bind_history_to_active_project()
    await _history_store.clear(project_key)
    return StatusResponse(status="cleared")


__all__ = ["router"]
