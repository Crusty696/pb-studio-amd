"""Tests fuer pb_studio.ai.tool_registry — Schema-Sanity + Handler-Roundtrip.

Mockt das Backend per httpx.MockTransport — kein echter Server noetig.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from pb_studio.ai.tool_registry import (
    Tool,
    ToolRegistry,
    build_default_registry,
)


def _run(coro):
    return asyncio.run(coro)


# ======================================================================
# Schema-Validation
# ======================================================================
def test_default_registry_has_minimum_tools():
    reg = build_default_registry()
    assert len(reg) >= 20, f"Erwartet >= 20 Tools, bekommen {len(reg)}"


def test_default_registry_covers_all_categories():
    reg = build_default_registry()
    categories = {t.category for t in reg.all()}
    expected = {"project", "audio", "video", "pacing", "brain", "render", "models", "system"}
    assert expected.issubset(categories), f"Fehlende Kategorien: {expected - categories}"


def test_all_tools_have_unique_names():
    reg = build_default_registry()
    names = [t.name for t in reg.all()]
    assert len(names) == len(set(names)), "Doppelte Tool-Namen"


def test_all_tools_have_valid_json_schema():
    reg = build_default_registry()
    for tool in reg.all():
        params = tool.parameters
        assert isinstance(params, dict), f"{tool.name}: parameters muss dict sein"
        assert params.get("type") == "object", f"{tool.name}: type muss 'object' sein"
        assert "properties" in params, f"{tool.name}: properties fehlt"
        assert isinstance(params["properties"], dict)
        # required muss eine Liste sein wenn vorhanden
        if "required" in params:
            assert isinstance(params["required"], list)
            for req_name in params["required"]:
                assert req_name in params["properties"], (
                    f"{tool.name}: required {req_name!r} nicht in properties"
                )


def test_openai_schema_replaces_dots():
    """Ollama erlaubt keine Punkte in Tool-Namen — llm_name muss '_'-Form sein."""
    reg = build_default_registry()
    schema = reg.openai_schema()
    for entry in schema:
        assert entry["type"] == "function"
        fn = entry["function"]
        assert "name" in fn
        assert "." not in fn["name"], f"Tool-Name hat noch Punkt: {fn['name']}"


def test_registry_lookup_dual_naming():
    """Lookup per Punkt-Form UND Unterstrich-Form muss funktionieren."""
    reg = build_default_registry()
    assert reg.get("audio.list_clips") is not None
    assert reg.get("audio_list_clips") is not None
    assert reg.get("audio.list_clips") is reg.get("audio_list_clips")


def test_destructive_flags_set_on_known_ops():
    reg = build_default_registry()
    destructive_names = {t.name for t in reg.all() if t.destructive}
    must_be_destructive = {
        "render.start",
        "render.cancel",
        "audio.separate_stems",
        "audio.import",
        "video.import",
        "project.create",
    }
    assert must_be_destructive.issubset(destructive_names), (
        f"Diese Tools muessen destructive=True haben: {must_be_destructive - destructive_names}"
    )


def test_inventory_shape():
    reg = build_default_registry()
    inv = reg.inventory()
    assert isinstance(inv, list)
    assert len(inv) == len(reg)
    for entry in inv:
        assert {"name", "llm_name", "description", "category", "destructive", "parameters"} <= entry.keys()


# ======================================================================
# Handler-Roundtrip mit Mock-Backend
# ======================================================================
def _make_backend_mock(routes: dict[tuple[str, str], dict[str, Any]]):
    """Baut einen MockTransport, der erwartete Routen zurueckliefert.

    routes = {("GET", "/audio/clips"): {"status": 200, "json": {...}}, ...}
    Default fuer unbekannte Pfade: 404.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        spec = routes.get(key)
        if spec is None:
            return httpx.Response(404, json={"detail": f"Mock: kein Mapping fuer {key}"})
        status = spec.get("status", 200)
        if "json" in spec:
            return httpx.Response(status, json=spec["json"])
        return httpx.Response(status, content=spec.get("body", b""))

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("tool_name,args,expected_route", [
    ("audio.list_clips", {"page": 1, "limit": 10}, ("GET", "/audio/clips")),
    ("audio.get_beats", {"clip_id": 7}, ("GET", "/audio/beats/7")),
    ("video.get_motion", {"clip_id": 3}, ("GET", "/video/motion/3")),
    ("project.info", {}, ("GET", "/project/info")),
    ("brain.stats", {}, ("GET", "/brain/stats")),
    ("models.list", {}, ("GET", "/models/list")),
    ("system.health", {}, ("GET", "/health")),
])
def test_handler_hits_correct_route(tool_name, args, expected_route):
    reg = build_default_registry()
    tool = reg.get(tool_name)
    assert tool is not None, f"Tool {tool_name} nicht in Registry"

    transport = _make_backend_mock({expected_route: {"json": {"ok": True, "tool": tool_name}}})

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            return await tool.handler(args, http_client=http_client)

    result = _run(go())
    assert result.get("ok") is True or "items" in result or "count" in result
    # Bei Listen-Responses wraps der Helper sie in {items, count}; hier ist
    # die Mock-Response aber ein dict, also kommt's direkt durch:
    assert result.get("tool") == tool_name


def test_audio_analyze_handler_validates_clip_id():
    reg = build_default_registry()
    tool = reg.get("audio.analyze")
    assert tool is not None

    transport = _make_backend_mock({})  # Mock soll nicht angesprochen werden

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler({}, http_client=http)

    result = _run(go())
    assert "error" in result, f"Erwartete Fehler-Antwort, bekommen: {result}"


def test_pacing_generate_handler_sends_correct_body():
    reg = build_default_registry()
    tool = reg.get("pacing.generate")
    assert tool is not None

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content) if request.content else {}
        return httpx.Response(200, json={"cuts": [], "total_duration": 0.0, "cut_count": 0, "average_cut_duration": 0.0})

    transport = httpx.MockTransport(handler)

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler(
                {
                    "audio_clip_id": 5,
                    "video_clip_ids": [1, 2, 3],
                    "expected_bpm": 128.0,
                    "use_motion_matching": True,
                    "use_brain": True,
                },
                http_client=http,
            )

    _run(go())
    assert captured["method"] == "POST"
    assert captured["path"] == "/pacing/generate"
    assert captured["body"]["audio_clip_id"] == 5
    assert captured["body"]["video_clip_ids"] == [1, 2, 3]
    assert captured["body"]["expected_bpm"] == 128.0
    assert captured["body"]["use_motion_matching"] is True
    assert captured["body"]["use_brain"] is True


def test_pacing_generate_requires_clip_ids_and_is_long_running():
    reg = build_default_registry()
    tool = reg.get("pacing.generate")
    assert tool is not None
    assert tool.long_running is True

    clip_schema = tool.parameters["properties"]["video_clip_ids"]
    assert clip_schema["minItems"] == 1
    assert "video_clip_ids" in tool.parameters["required"]
    assert "alle" not in clip_schema["description"].lower()

    backend_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal backend_called
        backend_called = True
        return httpx.Response(200, json={"cuts": []})

    async def go():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler(
                {"audio_clip_id": 5, "video_clip_ids": []},
                http_client=http,
            )

    result = _run(go())
    assert "error" in result
    assert "mindestens eine" in result["error"]
    assert backend_called is False


def test_handler_handles_backend_error_gracefully():
    reg = build_default_registry()
    tool = reg.get("audio.list_clips")
    assert tool is not None

    transport = _make_backend_mock({
        ("GET", "/audio/clips"): {"status": 500, "json": {"detail": "Backend kaputt"}},
    })

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler({}, http_client=http)

    result = _run(go())
    assert "error" in result
    assert result.get("status_code") == 500


def test_handler_handles_connection_error():
    reg = build_default_registry()
    tool = reg.get("project.info")
    assert tool is not None

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler({}, http_client=http)

    result = _run(go())
    assert "error" in result
    assert "Connection" in result["error"] or "Backend" in result["error"]


def test_brain_feedback_validates_rating():
    reg = build_default_registry()
    tool = reg.get("brain.feedback")
    assert tool is not None

    transport = _make_backend_mock({})

    async def go():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            return await tool.handler(
                {"cut_id": 1, "rating": "invalid_rating"},
                http_client=http,
            )

    result = _run(go())
    assert "error" in result
    assert "rating" in result["error"]


def test_int_list_coercion_from_string():
    """LLM gibt manchmal Strings statt Listen — der Coerce muss "1,2,3" akzeptieren."""
    from pb_studio.ai.tool_registry import _coerce_int_list

    assert _coerce_int_list([1, 2, 3]) == [1, 2, 3]
    assert _coerce_int_list("1,2,3") == [1, 2, 3]
    assert _coerce_int_list("[1, 2, 3]") == [1, 2, 3]
    assert _coerce_int_list(5) == [5]
    assert _coerce_int_list(None) == []
    assert _coerce_int_list("a,b,c") == []


def test_bool_coercion():
    from pb_studio.ai.tool_registry import _coerce_bool

    assert _coerce_bool(True) is True
    assert _coerce_bool("true") is True
    assert _coerce_bool("ja") is True
    assert _coerce_bool("False") is False
    assert _coerce_bool("nein") is False
    assert _coerce_bool(1) is True
    assert _coerce_bool(0) is False
    assert _coerce_bool(None) is False
    assert _coerce_bool(None, default=True) is True
