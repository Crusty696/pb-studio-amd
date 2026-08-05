"""
Shared Dependencies für FastAPI Dependency Injection.

GPU-Lock, DB-Session, Config — alles was Router brauchen.
"""

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Optional

from .config import config
from .app_state import AppState, get_app_state  # noqa: F401 — re-export für Router

logger = logging.getLogger(__name__)

# Globaler GPU-Lock: Nur 1 ONNX DirectML Session gleichzeitig
gpu_lock = asyncio.Lock()
_gpu_cleanup_tasks: set[asyncio.Task[None]] = set()

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
    manage_vram: bool = True,
    timeout_seconds: int | None = None,
    **kwargs: Any,
) -> Any:
    """
    Führt eine GPU-Funktion thread-sicher unter dem globalen GPU-Lock aus.
    Integrierte VRAM-Budget-Verwaltung (Reserve -> Commit -> Release) plus
    Telemetrie (Histogram über Dauer + VRAM-Peak pro model_id).

    ``manage_vram=False`` ist für zusammengesetzte Tasks, deren interne
    Modell-Owner ihre einzelnen Sessions selbst reservieren und freigeben.
    GPU-Lock und Telemetrie bleiben dabei aktiv.
    """
    manager = None
    vram_reserved = False

    # VRAM-Reservierung (vor dem Lock-Erwerb)
    if model_id and manage_vram:
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

    await gpu_lock.acquire()
    lock_handed_to_cleanup = False
    try:
        if vram_reserved and manager and not manager.commit(model_id):
            manager.cancel_reservation(model_id)
            raise RuntimeError(f"VRAM-Commit fehlgeschlagen: {model_id}")

        logger.debug(f"GPU-Lock erworben fuer: {func.__name__}")
        start_ts = time.perf_counter()
        vram_baseline_mb = float(manager.total_committed_mb) if manager else 0.0
        task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))

        async def finalize_after_worker(
            *,
            success: bool,
            error_payload: dict[str, Any] | None,
        ) -> None:
            try:
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    # Shutdown/caller cancellation must not shorten the physical
                    # worker lifetime guarded by the GPU lock.
                    try:
                        await task
                    except BaseException as worker_exc:
                        logger.debug(
                            "GPU-Hintergrund-Worker '%s' endete mit %s",
                            func.__name__,
                            type(worker_exc).__name__,
                        )
                except BaseException as worker_exc:
                    logger.debug(
                        "GPU-Hintergrund-Worker '%s' endete mit %s",
                        func.__name__,
                        type(worker_exc).__name__,
                    )

                duration_ms = (time.perf_counter() - start_ts) * 1000.0
                if manager:
                    vram_now_mb = float(manager.total_committed_mb)
                    try:
                        manager.record_task_observation(
                            model_id=model_id,
                            duration_ms=duration_ms,
                            vram_peak_mb=max(vram_baseline_mb, vram_now_mb),
                            success=success,
                            error=error_payload,
                        )
                    except Exception as obs_err:  # pragma: no cover
                        logger.debug(f"Telemetrie-Update fehlgeschlagen: {obs_err}")

                if vram_reserved and manager:
                    try:
                        budget = manager.get_model(model_id)
                    except Exception:
                        budget = None
                    if (
                        budget is not None
                        and getattr(budget, "unload_callback", None) is None
                        and getattr(budget, "is_loaded", False)
                    ):
                        manager.release(model_id)
                    else:
                        manager.cancel_reservation(model_id)
            finally:
                gpu_lock.release()
                logger.debug(f"GPU-Lock freigegeben fuer: {func.__name__}")

        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            error_payload = {
                "type": "TimeoutError",
                "message": f"GPU-Task Timeout: {func.__name__} ({timeout_seconds}s)",
                "task": func.__name__,
            }
            logger.error(error_payload["message"])
            await publish_event(
                "gpu_error",
                {"message": error_payload["message"], "task": func.__name__},
            )
            cleanup_task = asyncio.create_task(
                finalize_after_worker(success=False, error_payload=error_payload)
            )
            _gpu_cleanup_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(_gpu_cleanup_tasks.discard)
            lock_handed_to_cleanup = True
            raise TimeoutError(f"GPU-Task '{func.__name__}' Timeout")
        except asyncio.CancelledError:
            error_payload = {
                "type": "CancelledError",
                "message": f"GPU-Task abgebrochen: {func.__name__}",
                "task": func.__name__,
            }
            cleanup_task = asyncio.create_task(
                finalize_after_worker(success=False, error_payload=error_payload)
            )
            _gpu_cleanup_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(_gpu_cleanup_tasks.discard)
            lock_handed_to_cleanup = True
            raise
        except Exception as exc:
            lock_handed_to_cleanup = True
            await finalize_after_worker(
                success=False,
                error_payload={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "task": func.__name__,
                },
            )
            raise
        else:
            lock_handed_to_cleanup = True
            await finalize_after_worker(success=True, error_payload=None)
            return result
    finally:
        if not lock_handed_to_cleanup and gpu_lock.locked():
            gpu_lock.release()


# SSE Event Queues für Progress- und Log-Updates
EVENT_QUEUE_MAXSIZE = 500
_event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
_event_queue_filters: dict[str, frozenset[str] | None] = {}
_event_queue_drop_count = 0
_event_queue_drop_counts: dict[str, int] = {}

# Review-Fix HIGH-1 (2026-07-09): Referenz auf den uvicorn-Main-Loop, damit
# Worker-Threads (asyncio.to_thread + eigener Loop) Events thread-safe via
# call_soon_threadsafe einspeisen können. put_nowait aus fremdem Thread weckt
# den Selector nicht -> Events kamen bis zu 15s verspätet (Keepalive-Timeout).
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Wird im Lifespan-Startup gesetzt (und in Tests)."""
    global _main_loop
    _main_loop = loop


def get_event_queue(
    client_id: str = "default",
    event_filter: set[str] | frozenset[str] | None = None,
) -> asyncio.Queue[dict[str, Any]]:
    """Registriert eine Queue samt Publish-seitigem Eventfilter."""
    if client_id not in _event_queues:
        _event_queues[client_id] = asyncio.Queue(maxsize=EVENT_QUEUE_MAXSIZE)
        _event_queue_filters[client_id] = (
            frozenset(event_filter) if event_filter else None
        )
    elif event_filter is not None:
        requested_filter = frozenset(event_filter)
        if _event_queue_filters.get(client_id) != requested_filter:
            raise RuntimeError(
                f"SSE Client {client_id!r} wurde mit anderem Filter registriert"
            )
    return _event_queues[client_id]


def unregister_event_queue(client_id: str) -> int:
    """Deregistriert einen SSE-Client und gibt dessen Drop-Anzahl zurück."""
    _event_queues.pop(client_id, None)
    _event_queue_filters.pop(client_id, None)
    return _event_queue_drop_counts.pop(client_id, 0)


def get_event_queue_drop_metrics() -> dict[str, Any]:
    """Liefert einen Snapshot der sichtbaren SSE-Drop-Counter."""
    return {
        "total": _event_queue_drop_count,
        "by_client": dict(_event_queue_drop_counts),
    }


def _record_event_drop(client_id: str, event: dict[str, Any]) -> None:
    global _event_queue_drop_count
    _event_queue_drop_count += 1
    client_drop_count = _event_queue_drop_counts.get(client_id, 0) + 1
    _event_queue_drop_counts[client_id] = client_drop_count
    logger.warning(
        "SSE Event verworfen (drop-oldest): client=%s, event=%s, "
        "client_drops=%d, total_drops=%d",
        client_id,
        event.get("event", "message"),
        client_drop_count,
        _event_queue_drop_count,
    )


def _enqueue_event(
    client_id: str,
    queue: asyncio.Queue[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    """Fügt ein Event bounded ein; bei Full wird deterministisch das älteste entfernt."""
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass

    try:
        dropped_event = queue.get_nowait()
    except asyncio.QueueEmpty:
        # Defensive Race-Absicherung: Der Publish-Pfad darf nie QueueFull propagieren.
        _record_event_drop(client_id, event)
        return

    _record_event_drop(client_id, dropped_event)
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        # Nur bei regelwidrigem Cross-Thread-Zugriff möglich; auch dann exceptionfrei.
        _record_event_drop(client_id, event)


# ---------------------------------------------------------------------------
# Audit 2026-08-05 (H-1/T3.13): SSE-Journal fuer Reconnect-Replay.
#
# Bisher hatte der Stream weder ``id:``-Zeilen noch einen Puffer. Folgen:
#   * Bei Queue-Overflow (500 Events) wurde still das aelteste verworfen — der
#     Client erfuhr nie, dass er etwas verpasst hat.
#   * Beim WPF-Reconnect (Backoff 3-30 s) war die alte per-connection Queue
#     bereits geloescht. Fiel ein ``status="completed"`` in dieses Fenster,
#     blieb die Fortschrittsanzeige dauerhaft bei z.B. 87 % stehen.
#
# Der WHATWG-Standard loest genau das mit ``id:`` plus ``Last-Event-ID``. Das
# Journal ist absichtlich klein und rein im Speicher: es soll einen kurzen
# Verbindungsabbruch ueberbruecken, kein Event-Store sein.
# ---------------------------------------------------------------------------
EVENT_JOURNAL_MAXLEN = 500

_event_journal: deque[tuple[int, dict[str, Any]]] = deque(maxlen=EVENT_JOURNAL_MAXLEN)
_event_sequence = 0


def _next_event_sequence() -> int:
    global _event_sequence
    _event_sequence += 1
    return _event_sequence


def get_journaled_events_since(
    last_event_id: int,
    event_filter: Optional[set[str]] = None,
) -> list[tuple[int, dict[str, Any]]]:
    """
    Liefert die noch gepufferten Events nach ``last_event_id``.

    Wird beim Reconnect genutzt, damit ein verpasstes Abschluss-Event nicht zu
    einer dauerhaft haengenden Fortschrittsanzeige fuehrt.
    """
    if last_event_id <= 0:
        return []
    result: list[tuple[int, dict[str, Any]]] = []
    for sequence, event in list(_event_journal):
        if sequence <= last_event_id:
            continue
        if event_filter is not None:
            if str(event.get("event", "message")) not in event_filter:
                continue
        result.append((sequence, event))
    return result


def reset_event_journal() -> None:
    """Setzt Journal und Sequenz zurueck (Tests, Prozessneustart-Simulation)."""
    global _event_sequence
    _event_journal.clear()
    _event_sequence = 0


def _fanout_event(event: dict[str, Any]) -> None:
    """Synchroner Fan-out an alle Queues. NUR im Main-Loop-Thread aufrufen."""
    event_type = str(event.get("event", "message"))
    # Sequenznummer vergeben und journalisieren, BEVOR gefiltert wird — damit
    # ein Reconnect auch Events sieht, fuer die zum Publish-Zeitpunkt kein
    # passender Client verbunden war.
    if "_seq" not in event:
        event["_seq"] = _next_event_sequence()
    _event_journal.append((int(event["_seq"]), event))

    for client_id, queue in list(_event_queues.items()):
        event_filter = _event_queue_filters.get(client_id)
        if event_filter is not None and event_type not in event_filter:
            continue
        _enqueue_event(client_id, queue, event)


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

            # BUGFIX M13: use the shared main loop (set via set_main_loop), not
            # asyncio.get_running_loop(). emit() runs in worker threads (all heavy
            # work goes through asyncio.to_thread), where get_running_loop() raises
            # RuntimeError -> loop=None -> every worker-thread log was silently
            # dropped from the SSE live-log.
            publish_event_threadsafe("log", payload)
        except Exception:
            pass
