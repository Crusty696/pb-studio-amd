"""T413-S1A regression checks for global local-backend authorization."""

from __future__ import annotations

import hashlib
import hmac
import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend import owner_capability
from backend.app_state import get_app_state
from backend.main import app
from backend.middleware.owner_capability import _call_next_or_shutdown


CAPABILITY = "test-owner-capability"
HEADER = owner_capability.OWNER_CAPABILITY_HEADER
pytestmark = pytest.mark.unauthorized_backend


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(owner_capability, "_OWNER_CAPABILITY", CAPABILITY)
    state = get_app_state()
    state.start_accepting_requests()
    try:
        yield TestClient(app)
    finally:
        state.start_accepting_requests()


def test_health_is_public_but_all_other_global_routes_require_capability(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health/heartbeat").status_code == 403
    assert client.get("/health/vram").status_code == 403
    assert client.get("/events/progress").status_code == 403
    assert client.get("/openapi.json").status_code == 403

    assert client.get("/openapi.json", headers={HEADER: CAPABILITY}).status_code == 200
    assert client.get("/project/info", headers={HEADER: "wrong"}).status_code == 403


def test_global_gate_reports_unprovisioned_backend(monkeypatch):
    monkeypatch.setattr(owner_capability, "_OWNER_CAPABILITY", None)
    response = TestClient(app).get("/project/info", headers={HEADER: CAPABILITY})

    assert response.status_code == 503


def test_health_proof_is_nonce_bound_without_exposing_capability(client):
    nonce = "A" * 43
    response = client.get("/health/proof", params={"nonce": nonce})

    expected = hmac.new(
        CAPABILITY.encode("utf-8"),
        owner_capability.HEALTH_PROOF_DOMAIN + nonce.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "proof": expected}
    assert CAPABILITY not in response.text
    assert client.get("/health/proof", params={"nonce": "bad"}).status_code == 400


def test_options_bypasses_gate_and_allows_capability_header(client):
    response = client.options(
        "/project/info",
        headers={
            "Origin": "http://127.0.0.1",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": HEADER,
        },
    )

    assert response.status_code == 200
    assert HEADER.lower() in response.headers["access-control-allow-headers"].lower()


def test_shutdown_gate_authenticates_before_rejecting_new_intake(client):
    get_app_state().begin_shutdown()

    assert client.get("/openapi.json", headers={HEADER: "wrong"}).status_code == 403
    response = client.get("/openapi.json", headers={HEADER: CAPABILITY})

    assert response.status_code == 503
    assert response.json()["code"] == "backend_shutting_down"
    assert client.get("/health").status_code == 200


def test_no_response_is_normalized_only_during_shutdown():
    state = get_app_state()
    request = Request({"type": "http", "method": "POST", "path": "/video/analyze"})

    async def no_response(_request):
        raise RuntimeError("No response returned.")

    state.start_accepting_requests()
    with pytest.raises(RuntimeError, match="No response returned"):
        asyncio.run(_call_next_or_shutdown(request, no_response))

    state.begin_shutdown()
    response = asyncio.run(_call_next_or_shutdown(request, no_response))
    state.start_accepting_requests()

    assert response.status_code == 503
    assert response.body == (
        b'{"detail":"Backend wird heruntergefahren",'
        b'"code":"backend_shutting_down"}'
    )
