"""
GPU-Lock Middleware für FastAPI.

Stellt sicher, dass nur 1 ONNX DirectML Session gleichzeitig läuft.
AMD DirectML hat Memory-Konflikte bei parallelen Sessions.
"""

import logging
import time
from collections.abc import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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
    """Middleware die GPU-intensive Requests serialisiert."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path

        if path in GPU_PATHS:
            start = time.monotonic()
            logger.info(f"GPU-Request: {request.method} {path}")

            try:
                response = await call_next(request)
            except Exception as e:
                logger.error(f"GPU-Request fehlgeschlagen: {path}: {e}")
                return JSONResponse(
                    status_code=503,
                    content={"error": str(e), "detail": "GPU-Operation fehlgeschlagen"},
                )

            elapsed = time.monotonic() - start
            logger.info(f"GPU-Request fertig: {path} ({elapsed:.2f}s)")
            return response

        return await call_next(request)
