from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI

from pb_studio.ai.chat_agent import (
    ChatAgent,
    ToolConfirmationBroker,
    tool_confirmation_broker,
)
from pb_studio.ai.tool_registry import Tool, ToolRegistry


def _run(coro):
    return asyncio.run(coro)


def _registry(calls: list[dict]) -> ToolRegistry:
    async def mutate(args, *, http_client):
        calls.append(args)
        return {"status": "ok"}

    registry = ToolRegistry()
    registry.register(Tool(
        name="test.mutate",
        description="mutates",
        parameters={"type": "object"},
        handler=mutate,
        destructive=True,
    ))
    return registry


def _call(args: dict) -> dict:
    return {"function": {"name": "test_mutate", "arguments": args}}


def test_mutating_sink_rejects_unconfirmed_call():
    calls: list[dict] = []

    async def go():
        http = httpx.AsyncClient()
        agent = ChatAgent(registry=_registry(calls), http_client=http)
        try:
            result = await agent._dispatch_tool(_call({"path": "a"}))
        finally:
            await http.aclose()
        return result

    result = _run(go())
    assert "Bestaetigung erforderlich" in result["error"]
    assert calls == []


def test_approve_consumes_canonical_args_exactly_once():
    calls: list[dict] = []

    async def go():
        http = httpx.AsyncClient()
        agent = ChatAgent(registry=_registry(calls), http_client=http)
        original = {"path": "approved", "nested": {"value": 1}}
        entry = await tool_confirmation_broker.request(
            stream_id=agent._confirmation_stream_id,
            tool_name="test.mutate",
            args=original,
            timeout_seconds=5,
        )
        original["path"] = "tampered"
        assert await tool_confirmation_broker.decide(
            entry.confirmation_id, approve=True
        )
        first = await agent._dispatch_tool(confirmation_id=entry.confirmation_id)
        replay = await agent._dispatch_tool(confirmation_id=entry.confirmation_id)
        await http.aclose()
        return first, replay

    first, replay = _run(go())
    assert first == {"status": "ok"}
    assert "bereits verwendet" in replay["error"]
    assert calls == [{"nested": {"value": 1}, "path": "approved"}]


def test_reject_timeout_and_disconnect_never_become_consumable():
    async def go():
        broker = ToolConfirmationBroker()
        rejected = await broker.request(
            stream_id="reject", tool_name="test.mutate", args={}, timeout_seconds=5
        )
        assert await broker.decide(rejected.confirmation_id, approve=False)
        assert not await broker.wait(rejected)
        assert await broker.consume(rejected.confirmation_id, stream_id="reject") is None

        expired = await broker.request(
            stream_id="timeout", tool_name="test.mutate", args={}, timeout_seconds=0.01
        )
        assert not await broker.wait(expired)
        assert not await broker.decide(expired.confirmation_id, approve=True)

        disconnected = await broker.request(
            stream_id="disconnect", tool_name="test.mutate", args={}, timeout_seconds=5
        )
        await broker.cancel_stream("disconnect")
        assert not await broker.wait(disconnected)
        assert not await broker.decide(disconnected.confirmation_id, approve=True)

        approved_then_disconnected = await broker.request(
            stream_id="approved-disconnect",
            tool_name="test.mutate",
            args={},
            timeout_seconds=5,
        )
        assert await broker.decide(
            approved_then_disconnected.confirmation_id, approve=True
        )
        await broker.cancel_stream("approved-disconnect")
        assert await broker.consume(
            approved_then_disconnected.confirmation_id,
            stream_id="approved-disconnect",
        ) is None

    _run(go())


def test_parallel_approval_has_single_winner():
    async def go():
        broker = ToolConfirmationBroker()
        entry = await broker.request(
            stream_id="parallel", tool_name="test.mutate", args={}, timeout_seconds=5
        )
        results = await asyncio.gather(
            broker.decide(entry.confirmation_id, approve=True),
            broker.decide(entry.confirmation_id, approve=True),
        )
        assert sorted(results) == [False, True]
        assert await broker.consume(entry.confirmation_id, stream_id="parallel") is not None
        assert await broker.consume(entry.confirmation_id, stream_id="parallel") is None

    _run(go())


def test_confirmation_endpoints_accept_id_only_and_reject_replay():
    async def go():
        from backend.routers.chat_router import router

        app = FastAPI()
        app.include_router(router)
        entry = await tool_confirmation_broker.request(
            stream_id="endpoint", tool_name="test.mutate",
            args={"canonical": True}, timeout_seconds=5,
        )
        assert len(entry.confirmation_id) >= 40
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            approved = await client.post(
                f"/chat/confirm/{entry.confirmation_id}/approve"
            )
            replay = await client.post(
                f"/chat/confirm/{entry.confirmation_id}/approve"
            )
        assert approved.status_code == 200
        assert replay.status_code == 409
        assert await tool_confirmation_broker.wait(entry)

    _run(go())


def test_registry_rejects_unclassified_tool():
    async def read_only(args, *, http_client):
        return {}

    registry = ToolRegistry()
    try:
        registry.register(Tool(
            name="test.unclassified",
            description="missing effect classification",
            parameters={"type": "object"},
            handler=read_only,
        ))
    except ValueError as exc:
        assert "explizit klassifizieren" in str(exc)
    else:
        raise AssertionError("unclassified tool was accepted")
