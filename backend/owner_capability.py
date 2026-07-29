"""Process-local authorization for destructive loopback operations."""

from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import HTTPException

OWNER_CAPABILITY_ENV = "PBSTUDIO_OWNER_CAPABILITY"
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
    if not owner_capability or not hmac.compare_digest(owner_capability, expected):
        raise HTTPException(status_code=403, detail="Owner-Capability ungueltig")
    return hashlib.sha256(expected.encode("utf-8")).hexdigest()
