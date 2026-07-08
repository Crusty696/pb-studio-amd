"""
Shared Dependencies für FastAPI Dependency Injection.

GPU-Lock, DB-Session, Config — alles was Router brauchen.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from .config import config
from .app_state import AppState, get_app_state  # noqa: F401 — re-export für Router

logger = logging.getLogger(__name__)

# Globaler GPU-Lock: Nur 1 ONNX DirectML Session gleichzeitig
gpu_lock = asyncio.Lock()

# Globaler DB-Schreib-Lock: Verhindert WAL-Lock-Contention bei gleichzeitigen Schreibzugriffen
db_write_lock = asyncio.Lock()


async def get_gpu_lock() -> asyncio.Lock:
    """Dependency: GPU-Lock für DirectML Serialisierung."""
    return gpu_lock


async def get_db_write_lock() -> asyncio.Lock:
    """Dependency: Globales Lock für SQLite-Schreibzugriffe (Vermeidung von WAL-Lock-Contention)."""
    return db_write_lock


async def with_gpu_task(
    func: Callable[..., Any],
    *args: Any,
    model_id: str = "",
    timeout_seconds: int | None = None,
    **kwargs: Any,
) -> Any:
    """
    Führt eine GPU-Funktion thread-sicher unter dem globalen GPU-Lock aus.
    Integrierte VRAM-Budget-Verwaltung (Reserve -> Commit -> Release) plus
    Telemetrie (Histogram über Dauer + VRAM-Peak pro model_id).
    """
    manager = None
    vram_reserved = False

    # VRAM-Reservierung (vor dem Lock-Erwerb)
    if model_id:
        try:
            from pb_studio.core.vram_budget_manager import get_vram_manager, VRAMAllocationError
            manager = get_vram_manager()
            
            # C1/FIX: Retry-Loop mit Timeout für VRAM-Allokation
            # Versuche bis zu 10 Sekunden lang (10 Ticks à 1 Sekunde), den VRAM zu reservieren.
            # Falls andere Tasks ihren VRAM freigeben (z.B. durch automatische Eviction), wird er frei.
            vram_timeout = 10
            start_alloc = time.time()
            while time.time() - start_alloc < vram_timeout:
                if manager.reserve(model_id, force=True):
                    vram_reserved = True
                    logger.debug(f"VRAM-Budget reserviert fuer: {model_id}")
                    break
                logger.warning(f"VRAM knapp für '{model_id}' — warte auf Freigabe (evict)...")
                await asyncio.sleep(1.0)
                
            if not vram_reserved:
                raise VRAMAllocationError(f"VRAM-Ressourcen erschöpft: Reservierung für Modell '{model_id}' fehlgeschlagen.")
        except Exception as e:
            logger.error(f"VRAM-Reservierung fehlgeschlagen: {e}")
            raise

    # Timeout bestimmen
    if timeout_seconds is None:
        timeout_seconds = config.gpu_timeout_seconds

    # Telemetrie auch ohne erfolgreiche VRAM-Reservierung erfassen
    if manager is None:
        try:
            from pb_studio.core.vram_budget_manager import get_vram_manager
            manager = get_vram_manager()
        except Exception as e:  # pragma: no cover — defensiv, Manager sollte verfuegbar sein
            logger.debug(f"VRAM-Manager fuer Telemetrie nicht verfuegbar: {e}")

    async with gpu_lock:
        if vram_reserved and manager:
            manager.commit(model_id)

        logger.debug(f"GPU-Lock erworben fuer: {func.__name__}")

        start_ts = time.perf_counter()
        # Snapshot zu Beginn — committed_mb ist unter Lock konstant fuer dieses Modell
        vram_baseline_mb = float(manager.total_committed_mb) if manager else 0.0
        success = False
        error_payload: dict[str, Any] | None = None
        try:
            task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
            result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
            success = True
            return result
        except asyncio.TimeoutError:
            logger.error(f"GPU-Task '{func.__name__}' Timeout nach {timeout_seconds}s!")
            error_payload = {
                "type": "TimeoutError",
                "message": f"GPU-Task Timeout: {func.__name__} ({timeout_seconds}s)",
                "task": func.__name__,
            }
            await publish_event("gpu_error", {
                "message": error_payload["message"],
                "task": func.__name__,
            })
            raise TimeoutError(f"GPU-Task '{func.__name__}' Timeout")
        except asyncio.CancelledError:
            logger.warning(f"GPU-Task '{func.__name__}' abgebrochen (CancelledError)!")
            error_payload = {
                "type": "CancelledError",
                "message": f"GPU-Task abgebrochen: {func.__name__}",
                "task": func.__name__,
            }
            raise
        except Exception as exc:
            error_payload = {
                "type": type(exc).__name__,
                "message": str(exc),
                "task": func.__name__,
            }
            raise
        finally:
            if 'task' in locals() and not task.done():
                logger.warning(f"GPU-Thread fuer '{func.__name__}' laeuft noch. Warte auf Beendigung, um parallele GPU-Interferenz zu verhindern...")
                try:
                    await task
                except Exception as thread_exc:
                    logger.debug(f"Hintergrund-Thread warf Exception beim Warten: {thread_exc}")

            duration_ms = (time.perf_counter() - start_ts) * 1000.0
            # VRAM-Peak: groesserer Wert aus Anfangs-Snapshot und aktuellem committed_mb
            if manager:
                vram_now_mb = float(manager.total_committed_mb)
                vram_peak_mb = max(vram_baseline_mb, vram_now_mb)
                try:
                    manager.record_task_observation(
                        model_id=model_id,
                        duration_ms=duration_ms,
                        vram_peak_mb=vram_peak_mb,
                        success=success,
                        error=error_payload,
                    )
                except Exception as obs_err:  # pragma: no cover — Telemetrie darf Task nie kippen
                    logger.debug(f"Telemetrie-Update fehlgeschlagen: {obs_err}")

            if vram_reserved and manager:
                # B-5 Fix: Storniere Reservierung (wirkt nur wenn nicht committed). 
                # Freigabe passiert erst im ModelLoader beim Entladen.
                manager.cancel_reservation(model_id)
            logger.debug(f"GPU-Lock freigegeben fuer: {func.__name__}")


# SSE Event Queue für Progress-Updates
_event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

# Review-Fix HIGH-1 (2026-07-09): Referenz auf den uvicorn-Main-Loop, damit
# Worker-Threads (asyncio.to_thread + eigener Loop) Events thread-safe via
# call_soon_threadsafe einspeisen können. put_nowait aus fremdem Thread weckt
# den Selector nicht -> Events kamen bis zu 15s verspätet (Keepalive-Timeout).
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Wird im Lifespan-Startup gesetzt (und in Tests)."""
    global _main_loop
    _main_loop = loop


def get_event_queue(client_id: str = "default") -> asyncio.Queue[dict[str, Any]]:
    """Gibt die Event-Queue für einen Client zurück (per-Client Queue)."""
    if client_id not in _event_queues:
        _event_queues[client_id] = asyncio.Queue(maxsize=500)
    return _event_queues[client_id]


def _fanout_event(event: dict[str, Any]) -> None:
    """Synchroner Fan-out an alle Queues. NUR im Main-Loop-Thread aufrufen."""
    for queue in list(_event_queues.values()):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                f"Event-Queue voll (maxsize=500) — ältestes Event wird verworfen. "
                f"Event-Typ: {event['event']}"
            )
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(event)


async def publish_event(event_type: str, data: dict[str, Any], client_id: str = "default") -> None:
    """Publiziert ein Event an alle verbundenen SSE-Clients (Fan-out).

    BUG-028 Fix: Fan-out an alle registrierten Queues, damit /events/progress und
    /events/log gleichzeitig betrieben werden können ohne sich Events zu stehlen.
    """
    if not _event_queues:
        return
    _fanout_event({"event": event_type, "data": data})


def publish_event_threadsafe(event_type: str, data: dict[str, Any]) -> None:
    """Thread-sichere Variante für Worker-Threads/-Loops (Review-Fix HIGH-1).

    Best-effort: ohne gesetzten Main-Loop oder ohne Queues wird still verworfen
    (Status-Events sind rein kosmetisch, dürfen nie Inferenz abbrechen).
    """
    loop = _main_loop
    if loop is None or loop.is_closed() or not _event_queues:
        return
    event = {"event": event_type, "data": data}
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    try:
        if running is loop:
            _fanout_event(event)
        else:
            loop.call_soon_threadsafe(_fanout_event, event)
    except RuntimeError:
        # Loop wird gerade heruntergefahren — Event verwerfen
        pass


async def publish_log(message: str, *, level: str = "info", detail: str | None = None, source: str | None = None) -> None:
    """Publiziert ein strukturiertes Log-Event für /events/log."""
    payload: dict[str, Any] = {
        "level": (level or "info").lower(),
        "message": message,
    }
    if detail:
        payload["detail"] = detail
    if source:
        payload["source"] = source
    await publish_event("log", payload)


class SSELogHandler(logging.Handler):
    """Logging Handler, der alle Log-Records in die SSE Event-Queue leitet."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Endlosschleife vermeiden
            name = record.name
            if (name.startswith("backend.routers.events") or
                name.startswith("pb_studio.backend.routers.events") or
                "events_router" in name or
                "dependencies" in name or
                "uvicorn" in name or 
                "fastapi" in name):
                return

            message = self.format(record)
            payload = {
                "level": record.levelname.lower(),
                "message": message,
                "source": name
            }
            event = {"event": "log", "data": payload}

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                for queue in list(_event_queues.values()):
                    try:
                        loop.call_soon_threadsafe(queue.put_nowait, event)
                    except Exception:
                        pass
        except Exception:
            pass
