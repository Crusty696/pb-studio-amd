"""T413 regression checks for authenticated in-process chat loopback calls."""

from __future__ import annotations

import asyncio

import httpx

from backend import owner_capability
from pb_studio.ai import tool_registry


CAPABILITY = "internal-owner-capability"
HEADER = owner_capability.OWNER_CAPABILITY_HEADER


def test_chat_loopback_request_gets_capability_only_for_canonical_backend(monkeypatch):
    monkeypatch.setattr(owner_capability, "_OWNER_CAPABILITY", CAPABILITY)
    captured: dict[str, str | None] = {}

    def loopback(request: httpx.Request) -> httpx.Response:
        captured["loopback"] = request.headers.get(HEADER)
        return httpx.Response(200, json={"status": "ok"})

    def foreign(request: httpx.Request) -> httpx.Response:
        captured["foreign"] = request.headers.get(HEADER)
        return httpx.Response(200, json={"status": "ok"})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(loopback),
            base_url="http://127.0.0.1:8765",
        ) as loopback_client:
            await tool_registry._call("GET", "/project/info", http_client=loopback_client)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(foreign),
            base_url="http://example.test",
        ) as foreign_client:
            await tool_registry._call("GET", "/project/info", http_client=foreign_client)

    asyncio.run(run())
    assert captured == {"loopback": CAPABILITY, "foreign": None}


def test_chat_loopback_does_not_follow_redirect_with_capability(monkeypatch):
    monkeypatch.setattr(owner_capability, "_OWNER_CAPABILITY", CAPABILITY)
    requests: list[httpx.Request] = []

    def redirector(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"location": "http://evil.test/steal"})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(redirector),
            base_url="http://localhost:8765",
        ) as client:
            await tool_registry._call("GET", "/project/info", http_client=client)

    asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].headers[HEADER] == CAPABILITY
