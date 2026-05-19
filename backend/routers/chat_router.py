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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ----------------------------------------------------------------------
# In-Memory History (Server-Side, optional)
# ----------------------------------------------------------------------
class _ChatHistoryStore:
    """Thread-safe (single-process) Speicher fuer die Chat-History.

    Begrenzte Laenge — aelteste Eintraege fallen weg.
    """
    MAX_ENTRIES = 200

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def append(self, role: str, content: str) -> None:
        async with self._lock:
            self._entries.append({"role": role, "content": content})
            if len(self._entries) > self.MAX_ENTRIES:
                # Behalte die letzten MAX_ENTRIES
                self._entries = self._entries[-self.MAX_ENTRIES:]

    async def snapshot(self) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._entries)

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
        history = await _history_store.snapshot()

    user_text = request.message
    save_history = request.save_history
    mode = request.mode
    model_override = request.model_override

    async def _generator():
        # Save user message to history early (before LLM call)
        if save_history:
            await _history_store.append("user", user_text)

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
                        yield _sse_frame("tool_call", ev.payload)
                    elif ev.type == "tool_result":
                        yield _sse_frame("tool_result", ev.payload)
                    elif ev.type == "model":
                        yield _sse_frame("model", ev.payload)
                    elif ev.type == "error":
                        yield _sse_frame("error", ev.payload)
                    elif ev.type == "done":
                        if save_history and final_text:
                            await _history_store.append("assistant", final_text)
                        yield _sse_frame("done", ev.payload)
                    else:
                        yield _sse_frame(ev.type, ev.payload)
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("chat_router: unerwarteter Fehler: %s", exc)
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
