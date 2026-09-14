"""Default-deny authorization for PB Studio's local HTTP boundary."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.owner_capability import OWNER_CAPABILITY_HEADER, authorize_owner
from backend.app_state import (
    PROJECT_CAPABILITY_HEADER,
    ProjectContextChangedError,
    ProjectContextUnavailableError,
    get_app_state,
)


_PROJECT_CONTEXT_MUTATION_PATHS = {
    "/project/create",
    "/project/open",
    "/project/close",
}


def _project_conflict(message: str, *, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": message, "code": code},
    )


def _shutdown_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Backend wird heruntergefahren",
            "code": "backend_shutting_down",
        },
    )


async def _call_next_or_shutdown(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        return await call_next(request)
    except RuntimeError as exc:
        if (
            str(exc) == "No response returned."
            and get_app_state().is_shutdown_started()
        ):
            return _shutdown_response()
        raise


class OwnerCapabilityMiddleware(BaseHTTPMiddleware):
    """Require launcher capability for every route except liveness and identity proof."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        is_public_probe = (
            request.method == "GET"
            and request.url.path in {"/health", "/health/proof"}
        )

        if not is_public_probe:
            try:
                authorize_owner(
                    request.headers.get(OWNER_CAPABILITY_HEADER),
                    operation="Backend-API",
                )
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        state = get_app_state()
        if (
            not is_public_probe
            and request.url.path != "/shutdown"
            and state.is_shutdown_started()
        ):
            return _shutdown_response()

        project_capability = request.headers.get(PROJECT_CAPABILITY_HEADER)
        if not project_capability:
            return await _call_next_or_shutdown(request, call_next)
        if request.url.path in _PROJECT_CONTEXT_MUTATION_PATHS:
            return _project_conflict(
                "Projektwechsel ist innerhalb eines gebundenen Chat-Turns nicht erlaubt",
                code="project_context_change_forbidden",
            )

        bound_context = None
        try:
            async with state.project_capability_operation(
                project_capability
            ) as bound_context:
                return await _call_next_or_shutdown(request, call_next)
        except (ProjectContextChangedError, ProjectContextUnavailableError) as exc:
            return _project_conflict(str(exc), code="project_context_changed")
        except asyncio.CancelledError:
            if state.is_shutdown_started():
                return _shutdown_response()
            if (
                bound_context is not None
                and not state.is_project_context_current(bound_context)
            ):
                return _project_conflict(
                    "Projekt wurde während des Tool-Aufrufs gewechselt",
                    code="project_context_changed",
                )
            raise
