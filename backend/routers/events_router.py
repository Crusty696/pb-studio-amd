"""
Events Router – Server-Sent Events (SSE) für Echtzeit-Updates.

Endpoints:
  GET /events/progress — SSE Stream für Progress-Updates
  GET /events/log      — SSE Stream für Log-Nachrichten
  GET /events/gpu      — SSE Stream für GPU-Status Updates
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..dependencies import get_event_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events (SSE)"])


async def _sse_generator(request: Request, event_filter: Optional[str] = None) -> AsyncIterator[str]:
    """Generiert SSE Events aus der Event-Queue."""
    queue = get_event_queue()

    # Keepalive alle 15 Sekunden
    last_event = time.monotonic()

    while True:
        # Prüfe ob Client noch verbunden ist
        if await request.is_disconnected():
            logger.debug("SSE Client getrennt")
            break

        try:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)

            if event_filter and event.get("event") != event_filter:
                continue

            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)

            yield f"event: {event_type}\ndata: {data}\n\n"
            last_event = time.monotonic()

        except asyncio.TimeoutError:
            # Keepalive senden
            yield f": keepalive {int(time.monotonic())}\n\n"


@router.get("/progress")
async def progress_stream(request: Request) -> StreamingResponse:
    """SSE Stream für Progress-Updates (Analyse, Rendering, Import)."""
    logger.info("SSE Client verbunden: /events/progress")
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/log")
async def log_stream(request: Request) -> StreamingResponse:
    """SSE Stream für Log-Nachrichten."""
    logger.info("SSE Client verbunden: /events/log")

    async def _log_generator() -> AsyncIterator[str]:
        """Generiert Log-Events aus der dedizierten Log-Queue (event_type='log').
        BUG-005 Fix: Default-Queue nutzen, nicht "logs"-Queue die nie befüllt wurde.
        BUG-028 Fix: Eigene "log"-Queue statt Default-Queue (Fan-out in publish_event).
        """
        queue = get_event_queue("log")  # Eigene Queue — kein Event-Diebstahl von /events/progress
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                # Nur Log-Events dieses Streams weiterleiten
                if event.get("event") != "log":
                    continue
                data = json.dumps(event.get("data", {}), ensure_ascii=False)
                yield f"event: log\ndata: {data}\n\n"
            except asyncio.TimeoutError:
                yield f": keepalive\n\n"

    return StreamingResponse(
        _log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/gpu")
async def gpu_stream(request: Request) -> StreamingResponse:
    """SSE Stream für GPU-Status Updates (VRAM, Temperatur)."""
    logger.info("SSE Client verbunden: /events/gpu")

    async def _gpu_generator() -> AsyncIterator[str]:
        """Generiert periodische GPU-Status Events."""
        while True:
            if await request.is_disconnected():
                break
            try:
                from pb_studio.core.system_monitor import SystemMonitor
                monitor = SystemMonitor()
                # BUG-024 Fix: get_gpu_info() → get_stats(); Keys an get_stats()-Format angepasst
                gpu_info = monitor.get_stats()
                data = json.dumps({
                    "vram_used_mb": gpu_info.get("gpu_memory_used", 0),
                    "vram_total_mb": gpu_info.get("gpu_memory_total", 0),
                    "temperature_c": gpu_info.get("gpu_temp", 0),
                    "gpu_load": gpu_info.get("gpu_load", 0),
                    "timestamp": time.time(),
                }, ensure_ascii=False)
                yield f"event: gpu_status\ndata: {data}\n\n"
            except Exception as e:
                logger.debug(f"GPU-Status nicht verfügbar: {e}")
                yield f"event: gpu_status\ndata: {{\"error\": \"nicht verfügbar\"}}\n\n"

            await asyncio.sleep(5.0)  # Alle 5 Sekunden

    return StreamingResponse(
        _gpu_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
