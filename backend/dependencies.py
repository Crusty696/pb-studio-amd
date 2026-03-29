"""
Shared Dependencies für FastAPI Dependency Injection.

GPU-Lock, DB-Session, Config — alles was Router brauchen.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, AsyncGenerator

from .config import config
from .app_state import AppState, get_app_state  # noqa: F401 — re-export für Router

logger = logging.getLogger(__name__)

# Globaler GPU-Lock: Nur 1 ONNX DirectML Session gleichzeitig
gpu_lock = asyncio.Lock()


async def get_gpu_lock() -> asyncio.Lock:
    """Dependency: GPU-Lock für DirectML Serialisierung."""
    return gpu_lock


async def with_gpu_task(
    func: Callable[..., Any],
    *args: Any,
    model_id: str = "",
    timeout_seconds: int | None = None,
    **kwargs: Any,
) -> Any:
    """
    Führt eine GPU-Funktion thread-sicher unter dem globalen GPU-Lock aus.

    Optionaler VRAM-Budget-Check vor dem Lock-Erwerb:
    - Falls model_id gesetzt ist, wird VRAMBudgetManager gefragt
    - Bei Speichermangel: automatisches Evict von LOW/BACKGROUND Modellen
    - Fehler im VRAM-Check blockieren NICHT den Task (nur Warning)

    Args:
        func:             Blockierende Funktion (wird via asyncio.to_thread ausgeführt)
        *args:            Positional-Argumente für func
        model_id:         Optionale Modell-ID aus KNOWN_MODEL_BUDGETS (z.B. "mdx_net_inst")
        timeout_seconds:  GPU-Timeout (None = config.gpu_timeout_seconds)
        **kwargs:         Keyword-Argumente für func
    """
    # VRAM-Budget-Check (nur wenn model_id gesetzt)
    if model_id:
        try:
            from pb_studio.core.vram_budget_manager import get_vram_manager, KNOWN_MODEL_BUDGETS, ModelPriority
            manager = get_vram_manager()
            required_mb = KNOWN_MODEL_BUDGETS.get(model_id, 0)
            if required_mb > 0:
                available = manager.available_vram_mb
                if available < required_mb:
                    logger.info(
                        f"VRAM-Check '{model_id}': Braucht {required_mb}MB, "
                        f"Verfügbar {available}MB — starte Eviction"
                    )
                    manager.evict_all(min_priority=ModelPriority.MEDIUM)
                else:
                    logger.debug(
                        f"VRAM-Check '{model_id}': OK ({available}MB verfügbar, "
                        f"{required_mb}MB benötigt)"
                    )
        except Exception as e:
            # VRAM-Check ist optional — nie einen Task blockieren
            logger.warning(f"VRAM-Check fehlgeschlagen (wird ignoriert): {e}")

    # Timeout bestimmen
    if timeout_seconds is None:
        timeout_seconds = config.gpu_timeout_seconds

    async with gpu_lock:
        logger.debug(f"GPU-Lock erworben für: {func.__name__}")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"GPU-Task '{func.__name__}' Timeout nach {timeout_seconds}s! "
                f"GPU-Lock wird freigegeben."
            )
            await publish_event("gpu_error", {
                "message": f"GPU-Task Timeout: {func.__name__} ({timeout_seconds}s)",
                "task": func.__name__,
            })
            # VRAM-Reservation freigeben — sonst driftet das Budget permanent
            if model_id:
                try:
                    from pb_studio.core.vram_budget_manager import get_vram_manager
                    get_vram_manager().release(model_id)
                except Exception as _vram_err:
                    logger.debug(f"VRAM-Release nach Timeout fehlgeschlagen (ignoriert): {_vram_err}")
            raise TimeoutError(
                f"GPU-Task '{func.__name__}' hat Timeout von {timeout_seconds}s überschritten"
            )
        finally:
            logger.debug(f"GPU-Lock freigegeben für: {func.__name__}")


# SSE Event Queue für Progress-Updates
_event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}


def get_event_queue(client_id: str = "default") -> asyncio.Queue[dict[str, Any]]:
    """Gibt die Event-Queue für einen Client zurück (per-Client Queue)."""
    if client_id not in _event_queues:
        _event_queues[client_id] = asyncio.Queue(maxsize=500)
    return _event_queues[client_id]


async def publish_event(event_type: str, data: dict[str, Any], client_id: str = "default") -> None:
    """Publiziert ein Event an alle verbundenen SSE-Clients (Fan-out).

    BUG-028 Fix: Fan-out an alle registrierten Queues, damit /events/progress und
    /events/log gleichzeitig betrieben werden können ohne sich Events zu stehlen.
    """
    if not _event_queues:
        return
    event = {"event": event_type, "data": data}
    # Fan-out: alle registrierten Queues beliefern
    for queue in list(_event_queues.values()):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                f"Event-Queue voll (maxsize=500) — ältestes Event wird verworfen. "
                f"Event-Typ: {event_type}"
            )
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(event)


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
