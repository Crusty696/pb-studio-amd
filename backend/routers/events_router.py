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
from ..dependencies import get_event_queue, get_journaled_events_since

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events (SSE)"])

KEEPALIVE_TIMEOUT_SECONDS = 15.0
GPU_POLL_SECONDS = 5.0


def _register_client_queue(prefix: str) -> str:
    """Erzeugt nur die Client-ID.

    AP1.5 (Audit 2026-06-10): Die Queue wird NICHT mehr hier registriert,
    sondern erst in der ersten Generator-Iteration von _event_stream.
    Vorher: Client bricht ab bevor Starlette den Stream startet -> finally
    des Generators läuft nie -> Queue leakt dauerhaft in _event_queues
    (und hielt has_client=True im Zombie-Watcher künstlich aufrecht).
    """
    return f"{prefix}:{uuid.uuid4().hex}"


def _cleanup_client_queue(client_id: Optional[str]) -> None:
    if not client_id:
        return
    dropped_events = dependencies.unregister_event_queue(client_id)
    if dropped_events:
        logger.warning(
            "SSE Client deregistriert: %s (verworfene Events: %d)",
            client_id,
            dropped_events,
        )
    else:
        logger.debug("SSE Client deregistriert: %s", client_id)


async def _event_stream(
    request: Request,
    *,
    client_id: str,
    event_filter: Optional[set[str]] = None,
) -> AsyncIterator[str]:
    """Generiert SSE Events aus einer dedizierten per-connection Queue.

    Queue-Registrierung passiert hier (erste Generator-Iteration), damit
    das finally-Cleanup garantiert zur Registrierung gehört (AP1.5).
    """
    try:
        queue = get_event_queue(client_id, event_filter)

        # Audit 2026-08-05 (H-1/T3.13): Reconnect-Replay nach WHATWG-SSE.
        # Der Client schickt beim Wiederverbinden "Last-Event-ID"; alles was
        # seither publiziert wurde, wird nachgeliefert. Ohne das blieb eine
        # Fortschrittsanzeige dauerhaft haengen, wenn das abschliessende
        # "completed" in das Reconnect-Fenster fiel.
        last_event_id = _parse_last_event_id(request)
        if last_event_id > 0:
            missed = get_journaled_events_since(last_event_id, event_filter)
            if missed:
                logger.info(
                    "SSE Reconnect %s: liefere %d verpasste Events ab id=%d nach",
                    client_id,
                    len(missed),
                    last_event_id,
                )
            for sequence, event in missed:
                data = json.dumps(event.get("data", {}), ensure_ascii=False)
                event_type = event.get("event", "message")
                yield f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n"

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
            sequence = event.get("_seq")
            if sequence is not None:
                yield f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n"
            else:
                yield f"event: {event_type}\ndata: {data}\n\n"
    finally:
        _cleanup_client_queue(client_id)


def _parse_last_event_id(request: Request) -> int:
    """Liest den ``Last-Event-ID``-Header robust; ungueltige Werte ergeben 0."""
    raw = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    if not raw:
        return 0
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        logger.debug("Ungueltige Last-Event-ID ignoriert: %r", raw)
        return 0


@router.get("/progress")
async def progress_stream(request: Request) -> StreamingResponse:
    """SSE Stream für Progress-Updates (Analyse, Rendering, Import)."""
    client_id = _register_client_queue("progress")
    logger.info("SSE Client verbunden: /events/progress (%s)", client_id)
    # Audit 2026-08-05 (C-A): "persist_error" fehlte hier. app_state._emit_persist_error
    # publisht diesen Typ genau deshalb, weil IRON RULE 10 verlangt, dass der User
    # einen fehlgeschlagenen Speichervorgang sieht -- der Filter hat ihn still
    # verworfen, und der SSEClient hatte zusaetzlich keinen Handler dafuer.
    # Gleiche Fehlerklasse wie 2026-07-09, als llm_status hier fehlte.
    progress_events = {
        "analysis_progress",
        "render_progress",
        "stem_progress",
        "import_progress",
        "pacing_progress",
        "gpu_error",
        "llm_status",
        "persist_error",
    }
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
                # Audit 2026-08-05 (H-5/T3.7): Hier wurden vier von rund zwanzig
                # erhobenen Sensorwerten weitergegeben, der Rest fiel weg. Die
                # zusaetzlichen Felder kommen additiv dazu, damit bestehende
                # Konsumenten unveraendert weiterlaufen.
                payload = {
                    "vram_used_mb": gpu_info.get("gpu_memory_used", 0),
                    "vram_total_mb": gpu_info.get("gpu_memory_total", 0),
                    "temperature_c": gpu_info.get("gpu_temp", 0),
                    "gpu_load": gpu_info.get("gpu_load", 0),
                    "timestamp": time.time(),
                }
                for extra_key in (
                    "cpu_load",
                    "driver_version",
                    "adapter_name",
                    "adapter_index",
                    "monitoring_status",
                ):
                    if extra_key in gpu_info:
                        payload[extra_key] = gpu_info[extra_key]
                sensors = gpu_info.get("gpu_sensors")
                if sensors:
                    payload["sensors"] = sensors
                data = json.dumps(payload, ensure_ascii=False)
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
