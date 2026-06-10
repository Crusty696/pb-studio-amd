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
import uuid
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .. import dependencies
from ..dependencies import get_event_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events (SSE)"])

KEEPALIVE_TIMEOUT_SECONDS = 15.0
GPU_POLL_SECONDS = 5.0


def _register_client_queue(prefix: str) -> str:
    client_id = f"{prefix}:{uuid.uuid4().hex}"
    get_event_queue(client_id)
    return client_id


def _cleanup_client_queue(client_id: Optional[str]) -> None:
    if not client_id:
        return
    dependencies._event_queues.pop(client_id, None)


async def _event_stream(
    request: Request,
    *,
    client_id: str,
    event_filter: Optional[set[str]] = None,
) -> AsyncIterator[str]:
    """Generiert SSE Events aus einer dedizierten per-connection Queue."""
    queue = get_event_queue(client_id)

    try:
        while True:
            if await request.is_disconnected():
                logger.debug("SSE Client getrennt: %s", client_id)
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                yield f": keepalive {int(time.monotonic())}\n\n"
                continue

            event_type = event.get("event", "message")
            if event_filter and event_type not in event_filter:
                continue

            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"
    finally:
        _cleanup_client_queue(client_id)


@router.get("/progress")
async def progress_stream(request: Request) -> StreamingResponse:
    """SSE Stream für Progress-Updates (Analyse, Rendering, Import)."""
    client_id = _register_client_queue("progress")
    logger.info("SSE Client verbunden: /events/progress (%s)", client_id)
    progress_events = {"analysis_progress", "render_progress", "stem_progress", "import_progress", "pacing_progress", "gpu_error"}
    return StreamingResponse(
        _event_stream(request, client_id=client_id, event_filter=progress_events),
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
    client_id = _register_client_queue("log")
    logger.info("SSE Client verbunden: /events/log (%s)", client_id)
    return StreamingResponse(
        _event_stream(request, client_id=client_id, event_filter={"log"}),
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
        monitor = None
        try:
            from pb_studio.core.system_monitor import SystemMonitor

            monitor = SystemMonitor()
        except Exception as exc:
            logger.debug("GPU-Monitor Initialisierung fehlgeschlagen: %s", exc)

        while True:
            if await request.is_disconnected():
                break
            try:
                if monitor is None:
                    raise RuntimeError("GPU-Monitor nicht verfügbar")

                gpu_info = await asyncio.to_thread(monitor.get_stats) or {}
                data = json.dumps(
                    {
                        "vram_used_mb": gpu_info.get("gpu_memory_used", 0),
                        "vram_total_mb": gpu_info.get("gpu_memory_total", 0),
                        "temperature_c": gpu_info.get("gpu_temp", 0),
                        "gpu_load": gpu_info.get("gpu_load", 0),
                        "timestamp": time.time(),
                    },
                    ensure_ascii=False,
                )
                yield f"event: gpu_status\ndata: {data}\n\n"
            except Exception as exc:
                logger.debug("GPU-Status nicht verfügbar: %s", exc)
                yield "event: gpu_status\ndata: {\"error\": \"nicht verfügbar\"}\n\n"

            try:
                await asyncio.sleep(GPU_POLL_SECONDS)
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        _gpu_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
