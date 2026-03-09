"""
PB Studio AMD – FastAPI Backend

Lokaler HTTP-Server (localhost:8765) als Wrapper um die bestehende
Python Core-Logik. Kommuniziert mit dem C# WPF Frontend via REST + SSE.

WICHTIG: Dieser Server ist NUR für lokale Desktop-Nutzung gedacht.
Kein Auth, kein HTTPS, kein Multi-User.
"""

import logging
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .middleware.gpu_lock import GPULockMiddleware

# Logging Setup
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
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

    # Prüfe ob src/ importierbar ist
    try:
        import pb_studio
        logger.info(f"  pb_studio Modul gefunden: {pb_studio.__file__}")
    except ImportError as e:
        logger.error(f"  pb_studio NICHT importierbar: {e}")
        logger.error(f"  sys.path enthält: {[p for p in sys.path if 'pb_studio' in p.lower() or 'src' in p.lower()]}")

    # ADR-003 Phase 2: Clips aus SQLite wiederherstellen
    from .app_state import get_app_state
    get_app_state().load_from_db()

    yield

    logger.info("PB Studio AMD Backend wird heruntergefahren...")


# FastAPI App erstellen
app = FastAPI(
    title="PB Studio AMD Backend",
    description="Lokaler API-Server für PB Studio (AMD DirectML Edition)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS für lokalen C# WPF Client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lokal — kein Risiko
    allow_methods=["*"],
    allow_headers=["*"],
)

# GPU-Lock Middleware
app.add_middleware(GPULockMiddleware)


# --- Health Router (inline, da minimal) ---

@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Basis Health-Check."""
    return {
        "status": "ok",
        "uptime_seconds": round(get_uptime(), 1),
        "gpu_available": _check_gpu_available(),
    }


@app.get("/gpu/status")
async def gpu_status() -> dict[str, Any]:
    """GPU-Status via LibreHardwareMonitor."""
    try:
        from pb_studio.core.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        # BUG-013 Fix: Methode heißt get_stats(), nicht get_gpu_info()
        gpu_info = monitor.get_stats()
        return {
            "name": gpu_info.get("gpu_name", "Unknown"),
            "vram_total_mb": gpu_info.get("gpu_memory_total", 0),
            "vram_used_mb": gpu_info.get("gpu_memory_used", 0),
            "temperature_c": gpu_info.get("gpu_temp", 0),
            "driver_version": gpu_info.get("driver_version", "Unknown"),
        }
    except Exception as e:
        logger.warning(f"GPU-Status nicht verfügbar: {e}")
        return {
            "name": "Nicht verfügbar",
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "temperature_c": 0,
            "driver_version": str(e),
        }


@app.post("/gpu/cleanup")
async def gpu_cleanup() -> dict[str, int]:
    """VRAM aufräumen."""
    freed_mb = 0
    try:
        # BUG-014 Fix: VRAMArbiter braucht monitor-Argument; cleanup() → get_stats()
        from pb_studio.core.system_monitor import SystemMonitor
        from pb_studio.core.vram_arbiter import VRAMArbiter
        monitor = SystemMonitor()
        arbiter = VRAMArbiter(monitor=monitor)
        stats = arbiter.get_stats()
        freed_mb = max(0, stats.get("budget_reserved_mb", 0))
        logger.info(f"GPU-Cleanup: {freed_mb}MB reserviert (Budget-Reset)")
    except Exception as e:
        logger.warning(f"GPU-Cleanup fehlgeschlagen: {e}")
    return {"freed_mb": freed_mb}


@app.post("/shutdown")
async def shutdown() -> dict[str, str]:
    """Graceful Shutdown (aufgerufen von C# beim App-Close)."""
    import asyncio
    logger.info("Shutdown-Request erhalten, fahre in 2s herunter...")
    asyncio.get_event_loop().call_later(2, _force_exit)
    return {"status": "shutting_down"}


def _check_gpu_available() -> bool:
    """Prüft ob DirectML verfügbar ist."""
    try:
        import onnxruntime as ort
        return "DmlExecutionProvider" in ort.get_available_providers()
    except Exception:
        return False


def _force_exit() -> None:
    """Graceful Shutdown via SIGTERM (schließt SQLite WAL sauber)."""
    import os
    import signal
    # SEC-003 Fix: os._exit(0) → SIGTERM (uvicorn Lifespan-Shutdown, DB-Cleanup)
    os.kill(os.getpid(), signal.SIGTERM)


# Router importieren
from .routers.project_router import router as project_router
from .routers.audio_router import router as audio_router
from .routers.video_router import router as video_router
from .routers.pacing_router import router as pacing_router
from .routers.render_router import router as render_router
from .routers.events_router import router as events_router

app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level,
    )
