"""Default-deny authorization for PB Studio's local HTTP boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.owner_capability import OWNER_CAPABILITY_HEADER, authorize_owner


class OwnerCapabilityMiddleware(BaseHTTPMiddleware):
    """Require launcher capability for every route except liveness and identity proof."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "OPTIONS" or (
            request.method == "GET"
            and request.url.path in {"/health", "/health/proof"}
        ):
            return await call_next(request)

        try:
            authorize_owner(
                request.headers.get(OWNER_CAPABILITY_HEADER),
                operation="Backend-API",
            )
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        return await call_next(request)
