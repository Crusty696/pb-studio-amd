"""
GPU-Timing Middleware für FastAPI.

Diese Middleware ist ein Logger/Timer für GPU-intensive Requests.
Der eigentliche GPU-Lock (Serialisierung von DirectML ONNX Sessions) befindet sich
in ``backend/dependencies.py`` als ``gpu_lock = asyncio.Lock()``,
welches über ``with_gpu_task()`` erworben wird.
"""

import logging
import time
from collections.abc import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app_state import get_app_state

logger = logging.getLogger(__name__)

# Pfade die GPU-Lock benötigen
GPU_PATHS = {
    "/audio/stems/separate",
    "/audio/analyze",
    "/video/analyze",
    "/render/start",
    "/gpu/cleanup",
}


class GPULockMiddleware(BaseHTTPMiddleware):
    """Middleware die GPU-intensive Requests loggt und zeitlich erfasst."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path

        if path in GPU_PATHS:
            start = time.monotonic()
            logger.info(f"GPU-Request: {request.method} {path}")

            try:
                response = await call_next(request)
            except Exception as e:
                if (
                    isinstance(e, RuntimeError)
                    and str(e) == "No response returned."
                    and get_app_state().is_shutdown_started()
                ):
                    logger.info("GPU-Request durch Backend-Shutdown beendet: %s", path)
                    return JSONResponse(
                        status_code=503,
                        content={
                            "detail": "Backend wird heruntergefahren",
                            "code": "backend_shutting_down",
                        },
                    )
                logger.error(f"GPU-Request fehlgeschlagen: {path}: {e}")
                return JSONResponse(
                    status_code=503,
                    content={"error": str(e), "detail": "GPU-Operation fehlgeschlagen"},
                )

            elapsed = time.monotonic() - start
            logger.info(f"GPU-Request fertig: {path} ({elapsed:.2f}s)")
            return response

        return await call_next(request)
