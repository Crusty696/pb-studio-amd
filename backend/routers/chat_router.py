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
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
        self._entries: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def _count_tokens(self, text: str) -> int:
        """Token-count via max(1, len(text) // 3) heuristic."""
        return max(1, len(text) // 3)

    async def append(self, role: str, content: str) -> None:
        async with self._lock:
            self._entries.append({"role": role, "content": content})
            if len(self._entries) > self.MAX_ENTRIES:
                # Behalte die letzten MAX_ENTRIES
                self._entries = self._entries[-self.MAX_ENTRIES:]

    async def snapshot(self) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._entries)

    async def snapshot_for_llm(
        self, max_tokens: int = DEFAULT_TOKEN_BUDGET
    ) -> list[dict[str, Any]]:
        """I-H1 fix: liefert History oldest-first-trimmed bis token-budget erfuellt ist.

        Rechnet pro Eintrag content-tokens + PER_MESSAGE_OVERHEAD_TOKENS,
        reserviert PROMPT_OVERHEAD_TOKENS fuer System + Response.
        """
        budget = max(0, max_tokens - self.PROMPT_OVERHEAD_TOKENS)
        async with self._lock:
            entries = list(self._entries)
        # Reverse iteration: keep newest first, drop oldest until budget hits.
        kept: list[dict[str, Any]] = []
        total = 0
        for entry in reversed(entries):
            entry_tokens = self._count_tokens(entry.get("content", "")) + self.PER_MESSAGE_OVERHEAD_TOKENS
            if total + entry_tokens > budget:
                break
            kept.append(entry)
            total += entry_tokens
        kept.reverse()
        return kept

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()


_history_store = _ChatHistoryStore()


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

    if request.history is not None:
        history = [h.model_dump() for h in request.history]
    else:
        # I-H1 (Audit V2): token-aware Trim statt blind 200 entries — verhindert
        # silent LM-Studio context-overflow.
        history = await _history_store.snapshot_for_llm()

    user_text = request.message
    save_history = request.save_history
    mode = request.mode
    model_override = request.model_override

    async def _generator():
        # Save user message to history early (before LLM call)
        if save_history:
            await _history_store.append("user", user_text)

        await publish_log(
            "Chat-Anfrage erhalten",
            level="info",
            detail=f"characters={len(user_text)}",
            source="chat.user",
        )

        agent: Optional[ChatAgent] = None
        final_text = ""
        try:
            agent = ChatAgent()
            async with agent:
                async for ev in agent.process_message(
                    user_text,
                    history=history,
                    mode=mode,
                    model_override=model_override,
                ):
                    if ev.type == "text":
                        # Stueck fuer Stueck weiterleiten
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
                            await _history_store.append("assistant", final_text)
                        await publish_log(
                            "Chat-Antwort abgeschlossen",
                            level="info",
                            detail=f"characters={len(final_text)}",
                            source="chat.assistant",
                        )
                        yield _sse_frame("done", ev.payload)
                    else:
                        yield _sse_frame(ev.type, ev.payload)
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
            })
            yield _sse_frame("done", {"reason": "exception"})

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
    """Liefert die Server-Side Chat-History."""
    entries = await _history_store.snapshot()
    return HistoryResponse(
        entries=[ChatHistoryEntry(**e) for e in entries],
        count=len(entries),
    )


@router.delete("/history", response_model=StatusResponse)
async def clear_history() -> StatusResponse:
    """Leert die Server-Side Chat-History."""
    await _history_store.clear()
    return StatusResponse(status="cleared")


__all__ = ["router"]
