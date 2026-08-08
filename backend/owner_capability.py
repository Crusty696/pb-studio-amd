"""Process-local authorization and backend identity proof for loopback API calls."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

from fastapi import HTTPException

OWNER_CAPABILITY_ENV = "PBSTUDIO_OWNER_CAPABILITY"
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
HEALTH_PROOF_DOMAIN = b"PBStudio-health-proof-v1\0"
_HEALTH_PROOF_NONCE_RE = re.compile(r"[A-Za-z0-9_-]{22,128}\Z")
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def get_owner_capability() -> str | None:
    """Return capability for trusted in-process loopback clients only."""
    return _OWNER_CAPABILITY


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


def create_health_proof(nonce: str) -> str:
    """Return a domain-separated proof that this process owns ``nonce``'s capability."""
    if not _HEALTH_PROOF_NONCE_RE.fullmatch(nonce):
        raise HTTPException(status_code=400, detail="Health-Proof-Nonce ungueltig")

    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Health-Proof ist ohne Owner-Capability deaktiviert",
        )

    return hmac.new(
        expected.encode("utf-8"),
        HEALTH_PROOF_DOMAIN + nonce.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
