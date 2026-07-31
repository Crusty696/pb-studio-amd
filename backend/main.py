"""
PB Studio AMD – FastAPI Backend

Lokaler HTTP-Server (localhost:8765) als Wrapper um die bestehende
Python Core-Logik. Kommuniziert mit dem C# WPF Frontend via REST + SSE.

WICHTIG: Dieser Server ist NUR für lokale Desktop-Nutzung gedacht.
Kein Auth, kein HTTPS, kein Multi-User.
"""

import asyncio
import logging
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import config
from .owner_capability import OWNER_CAPABILITY_HEADER, authorize_owner
from .middleware.gpu_lock import GPULockMiddleware

# --------------------------------------------------------------------------
# Logging Setup (Aufgabe J: Rotation + Retention)
# - 10 MB pro File, gzip-Compression rotierter Logs
# - 7-Tage-Retention für rotierte Files
# - Konsolen-Output zusätzlich auf stdout
# Konfiguration zentral in pb_studio.utils.log_rotation
# --------------------------------------------------------------------------
from pb_studio.utils.log_rotation import (  # noqa: E402
    DEFAULT_DATE_FORMAT,
    DEFAULT_LOG_FORMAT,
    setup_rotating_logging,
)

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Native C++ Crash Handler (faulthandler) aktivieren
try:
    import faulthandler
    crash_log_file = open(log_dir / "native_crash.log", "ab", buffering=0)
    faulthandler.enable(file=crash_log_file, all_threads=True)
    logging.getLogger("backend.main").info(f"Native Crash Handler (faulthandler) aktiviert.")
except Exception as e:
    logging.getLogger("backend.main").error(f"Failed to enable faulthandler: {e}")

log_file = log_dir / "backend.log"


_log_level = getattr(logging, config.log_level.upper(), logging.INFO)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(_log_level)
_console_handler.setFormatter(
    logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
)

_file_handler = setup_rotating_logging(
    log_file=log_file,
    level=_log_level,
    fmt=DEFAULT_LOG_FORMAT,
    datefmt=DEFAULT_DATE_FORMAT,
)

from .dependencies import SSELogHandler

_sse_handler = SSELogHandler()
_sse_handler.setLevel(_log_level)
_sse_handler.setFormatter(
    logging.Formatter("%(name)s: %(message)s")
)

logging.basicConfig(
    level=_log_level,
    format=DEFAULT_LOG_FORMAT,
    datefmt=DEFAULT_DATE_FORMAT,
    handlers=[_console_handler, _file_handler, _sse_handler],
)
logger = logging.getLogger("pb_studio.backend")

# Server-Startzeit für Uptime
_start_time = time.time()


def get_uptime() -> float:
    """Gibt die Server-Uptime in Sekunden zurück."""
    return time.time() - _start_time


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup und Shutdown Events."""
    logger.info("=" * 60)
    logger.info("PB Studio AMD Backend startet...")
    logger.info(f"  Host: {config.host}:{config.port}")
    logger.info(f"  Python: {sys.version}")
    logger.info(f"  FFmpeg: {config.ffmpeg_path}")
    logger.info("=" * 60)

    # Review-Fix HIGH-1 (2026-07-09): Main-Loop für thread-sichere SSE-Publishes
    from backend.dependencies import publish_event_threadsafe, set_main_loop
    set_main_loop(asyncio.get_running_loop())
    # Review-Fix 2026-07-09: llm_status-Publisher in den Vision-Wrapper injizieren
    try:
        from pb_studio.video.lmstudio_vision_wrapper import set_status_publisher
        set_status_publisher(publish_event_threadsafe)
    except ImportError as e:
        logger.warning(f"  llm_status-Publisher nicht verdrahtet: {e}")

    # Audit-Fix (2026-07-10): gleiches Wiring fuer Chat-Agent und Brain-Narrator,
    # damit die WPF-Statusleiste auch bei Chat/Brain-Explain-LLM-Calls reagiert
    # (vorher nur Video-Frame-Tagging abgedeckt).
    try:
        from pb_studio.ai.chat_agent import set_status_publisher as set_chat_status_publisher
        set_chat_status_publisher(publish_event_threadsafe)
    except ImportError as e:
        logger.warning(f"  llm_status-Publisher (chat_agent) nicht verdrahtet: {e}")
    try:
        from pb_studio.brain.llm_narrator import set_status_publisher as set_narrator_status_publisher
        set_narrator_status_publisher(publish_event_threadsafe)
    except ImportError as e:
        logger.warning(f"  llm_status-Publisher (llm_narrator) nicht verdrahtet: {e}")

    # Prüfe ob src/ importierbar ist
    try:
        import pb_studio
        logger.info(f"  pb_studio Modul gefunden: {pb_studio.__file__}")
    except ImportError as e:
        logger.error(f"  pb_studio NICHT importierbar: {e}")
        logger.error(f"  sys.path enthält: {[p for p in sys.path if 'pb_studio' in p.lower() or 'src' in p.lower()]}")

    try:
        from pb_studio.core.crash_handler import CrashHandler
        CrashHandler()
        logger.info("  CrashHandler aktiv")
    except Exception as e:
        logger.warning(f"  CrashHandler nicht verfügbar: {e}")

    try:
        config.project_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"  Projekt-Verzeichnis bereit: {config.project_dir}")
    except Exception as e:
        logger.warning(f"  Projekt-Verzeichnis konnte nicht angelegt werden: {e}")

    # Provider-/Modellwahrheit einmal pro Backendstart neu erfassen. Der
    # Service bündelt LM-Studio- und Ollama-Abfragen und publiziert atomar.
    try:
        from pb_studio.ai.model_inventory import get_model_inventory_service

        model_inventory = await get_model_inventory_service().refresh(force=True)
        provider_states = ", ".join(
            f"{provider.provider}={provider.status}"
            for provider in model_inventory.providers
        )
        logger.info(
            "  Modellinventar aktualisiert: %d Modelle (%s)",
            len(model_inventory.models),
            provider_states or "keine Provider",
        )
    except Exception as e:
        logger.warning(f"  Modellinventar-Startup-Refresh fehlgeschlagen: {e}")

    # Kein automatischer Medien-Restore beim Startup:
    # Der aktive Projektkontext entsteht erst via /project/open oder /project/create.

    # Render-Queue Resume-on-Startup: Jobs werden nicht nur als interrupted
    # markiert, sondern aus ihrem persistierten Request-/Timeline-Snapshot
    # rekonstruiert und erneut eingeplant.
    try:
        from .app_state import get_app_state
        from .routers.render_router import (
            _reset_render_runtime_for_startup,
            _resume_render_queue_on_startup,
        )
        _reset_render_runtime_for_startup()
        await _resume_render_queue_on_startup(get_app_state())
    except Exception as e:
        logger.warning(f"  Render-Queue Restore-on-Startup übersprungen: {e}")

    # M8-Fix (I-M2, 2026-05-20): Startup-Cleanup von verwaisten temp-Dirs aelter
    # als 24h. Vor Fix: temp/ wurde nur bei Render-Cancel/Fail aufgeraeumt
    # (_cleanup_render_temps), nach Crash blieben .temp_render-Verzeichnisse mit
    # Stale-Files liegen. Jetzt: Startup-sweep aller .temp_render-Dirs > 24h.
    try:
        import time
        import shutil
        from pathlib import Path
        threshold = time.time() - 24 * 3600
        cleaned = 0
        # Project-Dir scan nach .temp_render
        proj_root = Path(config.project_dir)
        if proj_root.exists():
            for temp_dir in proj_root.rglob(".temp_render"):
                try:
                    mtime = temp_dir.stat().st_mtime
                    if mtime < threshold:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        cleaned += 1
                except Exception as cleanup_err:
                    logger.debug(f"  temp-cleanup skipped {temp_dir}: {cleanup_err}")
        if cleaned:
            logger.info(f"  Stale temp-Dirs entfernt: {cleaned} (älter als 24h)")
    except Exception as e:
        logger.warning(f"  temp-Cleanup-on-Startup übersprungen: {e}")

    # Zombie-Prozess-Wächter (Heartbeat-Schutz)
    async def _zombie_watcher():
        logger.info("  Zombie-Prozess-Wächter aktiv (Toleranz: 120s ab Start / 120s nach Client-Verlust)")
        from .dependencies import _event_queues, gpu_lock
        from .app_state import get_app_state
        
        # Grace-Period ab Start: 120 Sekunden, damit sich der C#-WPF-Client in Ruhe verbinden kann
        await asyncio.sleep(120)
        
        consecutive_idle_checks = 0
        while True:
            await asyncio.sleep(5)
            
            # Wenn keine aktiven SSE-Event-Queues registriert sind
            has_client = len(_event_queues) > 0
            
            # Prüfen, ob GPU-Tasks aktiv sind oder ein Rendering läuft
            gpu_active = gpu_lock.locked()
            render_active = False
            try:
                render_active = get_app_state().is_render_active()
            except Exception as e:
                logger.debug(f"is_render_active Check fehlgeschlagen: {e}")
            
            if not has_client and not gpu_active and not render_active:
                consecutive_idle_checks += 1
                # 24 Checks * 5 Sekunden = 120 Sekunden ohne Client und ohne Hintergrundaktivität
                if consecutive_idle_checks >= 24:
                    logger.warning("Kein aktiver Client verbunden (SSE-Verbindungen verwaist) und keine Hintergrund-Tasks aktiv. Automatischer Shutdown wird eingeleitet...")
                    _force_exit()
            else:
                consecutive_idle_checks = 0
                
    watcher_task = asyncio.create_task(_zombie_watcher())

    yield

    watcher_task.cancel()
    try:
        await watcher_task
    except asyncio.CancelledError:
        pass

    try:
        from .app_state import get_app_state
        from .routers.render_router import _shutdown_active_renders

        render_shutdown = await _shutdown_active_renders(get_app_state())
        if render_shutdown["tasks"]:
            logger.info("  Render-Shutdown: %s", render_shutdown)
    except Exception as e:
        logger.warning(f"  Render-Shutdown fehlgeschlagen: {e}")

    # Review-Fix 2026-07-09: Publisher/Loop-Referenzen zurücksetzen
    try:
        from pb_studio.video.lmstudio_vision_wrapper import set_status_publisher
        set_status_publisher(None)
    except ImportError:
        pass
    set_main_loop(None)

    # BUG-099 FIX: Expliziter Cleanup beim Shutdown
    logger.info("PB Studio AMD Backend wird heruntergefahren...")
    try:
        from pb_studio.ai.smart_director import SmartDirector
        SmartDirector.reset_instance()
        logger.info("  AI Director Ressourcen freigegeben")
    except Exception as e:
        logger.debug(f"Director shutdown cleanup skipped: {e}")


# FastAPI App erstellen
app = FastAPI(
    title="PB Studio AMD Backend",
    description="Lokaler API-Server für PB Studio (AMD DirectML Edition)",
    version="1.0.0",
    lifespan=lifespan,
)


# T7b (S-H1b nswag-compat): downgrade auf OpenAPI 3.0.3 — Pydantic v2 emittiert
# sonst OpenAPI 3.1 mit `anyOf:[string,null]` fuer Optional[str], was NSwag 14
# nicht zu nullable string? collapsen kann (-> opaque placeholder classes).
# Recursive walker konvertiert `anyOf:[X,null]` -> `{...X, nullable:true}`.
def _downgrade_openapi_to_3_0(schema: dict) -> dict:
    """Konvertiert OpenAPI 3.1 anyOf:[X,null] zu 3.0 nullable:true in place."""
    if not isinstance(schema, dict):
        return schema

    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        non_null = [s for s in schema["anyOf"] if not (isinstance(s, dict) and s.get("type") == "null")]
        has_null = any(isinstance(s, dict) and s.get("type") == "null" for s in schema["anyOf"])
        if has_null and len(non_null) == 1 and isinstance(non_null[0], dict):
            collapsed = dict(non_null[0])
            collapsed["nullable"] = True
            for k, v in schema.items():
                if k != "anyOf":
                    collapsed.setdefault(k, v)
            schema.clear()
            schema.update(collapsed)

    for v in schema.values():
        if isinstance(v, dict):
            _downgrade_openapi_to_3_0(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _downgrade_openapi_to_3_0(item)
    return schema


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["openapi"] = "3.0.3"
    _downgrade_openapi_to_3_0(schema)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

# CORS für lokalen C# WPF Client
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
    ],
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["Content-Type", "Accept"],
)

# GPU-Lock Middleware
app.add_middleware(GPULockMiddleware)


# --- Health Router (inline, da minimal) ---


class GpuStatusResponse(BaseModel):
    name: str
    vram_total_mb: int
    vram_used_mb: float
    temperature_c: float
    driver_version: str
    adapter_index: int | None = None
    adapter_luid: str | None = None
    adapter_name: str | None = None
    selection_policy: str | None = None
    dedicated_vram_total_mb: int
    directml_active: bool
    monitoring_status: str
    monitoring_error: str | None = None


class GpuCleanupResponse(BaseModel):
    success: bool
    freed_mb: int
    error: str | None = None

@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Basis Health-Check."""
    return {
        "status": "ok",
        "uptime_seconds": round(get_uptime(), 1),
        "gpu_available": _check_gpu_available(),
    }


@app.get("/health/heartbeat")
async def heartbeat() -> dict[str, Any]:
    """Leichtgewichtiger Herzschlag für UI-Resilienz."""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/gpu/status", response_model=GpuStatusResponse)
async def gpu_status() -> dict[str, Any]:
    """GPU-Status via LibreHardwareMonitor."""
    try:
        from pb_studio.core.directml_adapter import get_directml_adapter
        from pb_studio.core.system_monitor import SystemMonitor
        adapter = get_directml_adapter()
        monitor = SystemMonitor()
        gpu_info = monitor.get_stats()
        directml_active = _check_gpu_available()
        monitoring_status = gpu_info.get("monitoring_status", "degraded")
        return {
            "name": adapter.name,
            "vram_total_mb": adapter.dedicated_vram_mb,
            "vram_used_mb": gpu_info.get("gpu_memory_used", 0),
            "temperature_c": gpu_info.get("gpu_temp", 0),
            "driver_version": gpu_info.get("driver_version", "Unknown"),
            "adapter_index": adapter.device_id,
            "adapter_luid": adapter.luid,
            "adapter_name": adapter.name,
            "selection_policy": adapter.selection_policy,
            "dedicated_vram_total_mb": adapter.dedicated_vram_mb,
            "directml_active": directml_active,
            "monitoring_status": monitoring_status,
            "monitoring_error": (
                None
                if monitoring_status == "ready"
                else (
                    "LibreHardwareMonitor ist eingeschränkt; "
                    "Details stehen im Backend-Log."
                )
            ),
        }
    except Exception as e:
        logger.warning(f"GPU-Status nicht verfügbar: {e}")
        return {
            "name": "Nicht verfügbar",
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "temperature_c": 0,
            "driver_version": "Unknown",
            "adapter_index": None,
            "adapter_luid": None,
            "adapter_name": None,
            "selection_policy": None,
            "dedicated_vram_total_mb": 0,
            "directml_active": False,
            "monitoring_status": "error",
            "monitoring_error": (
                "GPU-Status ist nicht verfügbar; "
                "Details stehen im Backend-Log."
            ),
        }


@app.post("/gpu/cleanup", response_model=GpuCleanupResponse)
async def gpu_cleanup() -> GpuCleanupResponse:
    """Idle GPU models unload and report only confirmed releases."""
    try:
        from pb_studio.core.vram_budget_manager import (
            ModelPriority,
            get_vram_manager,
        )

        manager = get_vram_manager()
        before = manager.get_stats()["models"]
        eligible_ids = {
            model_id
            for model_id, state in before.items()
            if state["is_loaded"]
            and ModelPriority[state["priority"]] >= ModelPriority.LOW
            and manager.get_model_budget(model_id).unload_callback is not None
        }

        freed_mb = await asyncio.to_thread(
            manager.evict_all,
            ModelPriority.LOW,
        )
        remaining = {
            model_id
            for model_id in eligible_ids
            if manager.is_model_loaded(model_id)
        }
        if remaining:
            logger.warning(
                "GPU-Cleanup konnte %d Idle-Modelle nicht bestätigen.",
                len(remaining),
            )
            return GpuCleanupResponse(
                success=False,
                freed_mb=max(0, freed_mb),
                error=(
                    "Nicht alle inaktiven GPU-Modelle konnten sicher "
                    "freigegeben werden."
                ),
            )

        logger.info(
            "GPU-Cleanup bestätigt: %dMB aus %d Idle-Modellen freigegeben.",
            freed_mb,
            len(eligible_ids),
        )
        return GpuCleanupResponse(
            success=True,
            freed_mb=max(0, freed_mb),
        )
    except Exception:
        logger.exception("GPU-Cleanup fehlgeschlagen.")
        return GpuCleanupResponse(
            success=False,
            freed_mb=0,
            error="GPU-Cleanup ist fehlgeschlagen; Details stehen im Backend-Log.",
        )


@app.post(
    "/shutdown",
    responses={
        403: {"description": "Owner-Capability fehlt oder ist ungueltig."},
        503: {"description": "Backend wurde ohne Owner-Capability gestartet."},
    },
    openapi_extra={
        "parameters": [
            {
                "name": OWNER_CAPABILITY_HEADER,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": (
                    "Runtime-required launcher capability for destructive "
                    "loopback operations."
                ),
            }
        ]
    },
)
async def shutdown(
    owner_capability: str | None = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
        include_in_schema=False,
    ),
) -> dict[str, str]:
    """Owner-authorized graceful shutdown called by the WPF launcher."""
    authorize_owner(owner_capability, operation="Backend-Shutdown")
    logger.info("Shutdown-Request erhalten, fahre in 2s herunter...")
    # Windows/Uvicorn: loop.call_later() hat hier im detached Launcher-Pfad
    # nicht zuverlässig ausgelöst, wodurch der alte Prozess Port 8765 belegt hielt.
    # Ein Timer auf separatem Thread ist für den lokalen Shutdown robuster.
    timer = threading.Timer(2.0, _force_exit)
    timer.daemon = True
    timer.start()
    return {"status": "shutting_down"}


def _check_gpu_available() -> bool:
    """Prüft ob DirectML verfügbar ist."""
    try:
        import onnxruntime as ort
        return "DmlExecutionProvider" in ort.get_available_providers()
    except Exception:
        return False


def _force_exit() -> None:
    """Graceful Shutdown: löst uvicorns Signal-Handler in-process aus.

    AP1.4 (Audit 2026-06-10): os.kill(pid, SIGTERM) ist auf Windows
    TerminateProcess (harter Kill) — Lifespan-Teardown/DB-Cleanup liefen NIE.
    Sucht zuerst die uvicorn.Server-Instanz im GC und setzt `should_exit = True`.
    Falls nicht gefunden, ruft signal.raise_signal(signal.SIGINT) auf →
    sorgt für echten Lifespan-Shutdown (SQLite/WAL, SmartDirector.reset_instance).
    Fallback: harter Exit nach 10s, falls der graceful Shutdown hängt.
    """
    import os
    import signal
    import threading as _threading
    import gc

    def _hard_exit() -> None:
        try:
            from pb_studio.rendering.render_service import RenderService
            RenderService.terminate_active_processes(grace_seconds=1.0)
        finally:
            os._exit(0)

    fallback = _threading.Timer(10.0, _hard_exit)
    fallback.daemon = True
    fallback.start()
    
    try:
        import uvicorn
        for obj in gc.get_objects():
            # Verwende string-Vergleich für den Klassennamen, um Import-Probleme zu vermeiden
            if type(obj).__name__ == "Server" and type(obj).__module__ == "uvicorn.server":
                logger.info("Uvicorn-Server-Instanz im GC gefunden. Setze should_exit = True...")
                obj.should_exit = True
                return
    except Exception as gc_err:
        logger.warning(f"Fehler bei der GC-Suche nach dem Uvicorn-Server: {gc_err}")

    try:
        signal.raise_signal(signal.SIGINT)
    except Exception:
        _hard_exit()


# Router importieren
from .routers.project_router import router as project_router
from .routers.audio_router import router as audio_router
from .routers.video_router import router as video_router
from .routers.pacing_router import router as pacing_router
from .routers.render_router import router as render_router
from .routers.events_router import router as events_router
from .routers.brain_router import router as brain_router
from .routers.health_router import router as health_router
from .routers.models_router import router as models_router
from .routers.chat_router import router as chat_router

app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level,
    )
