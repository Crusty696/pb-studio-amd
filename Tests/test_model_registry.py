"""Tests fuer pb_studio.ai.model_registry."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from pb_studio.ai.model_registry import (
    DEFAULT_TASK_PREFERENCES,
    ModelRegistry,
    ModelRegistryError,
    NoSuitableModelError,
    _name_matches,
)
from pb_studio.ai.ollama_client import OllamaClient


def _run(coro):
    return asyncio.run(coro)


def _client_with_models(model_names: list[str]) -> OllamaClient:
    """Erzeugt einen OllamaClient, der via MockTransport ``model_names`` zurueckgibt."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": n,
                            "size": 1_000_000_000,
                            "modified_at": "2026-05-15",
                        }
                        for n in model_names
                    ]
                },
            )
        return httpx.Response(404)

    return OllamaClient(transport=httpx.MockTransport(handler))


# ======================================================================
# _name_matches helper
# ======================================================================
def test_name_matches_exact():
    assert _name_matches("gemma4:latest", "gemma4:latest")


def test_name_matches_candidate_without_tag():
    assert _name_matches("gemma4", "gemma4:9b")
    assert _name_matches("gemma4", "gemma4:latest")


def test_name_matches_installed_without_tag():
    assert _name_matches("gemma4:latest", "gemma4")


def test_name_matches_different_models():
    assert not _name_matches("gemma4", "llava:13b")


# ======================================================================
# refresh()
# ======================================================================
def test_registry_refresh_populates_installed_models():
    async def go():
        async with _client_with_models(["gemma4:latest", "llava:13b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
        return reg

    reg = _run(go())
    assert reg.is_loaded
    names = [m.name for m in reg.installed_models]
    assert names == ["gemma4:latest", "llava:13b"]


def test_select_before_refresh_raises():
    reg = ModelRegistry()
    with pytest.raises(ModelRegistryError):
        reg.select_best_for_task("video_captioning", "balance")


# ======================================================================
# Preference list resolution
# ======================================================================
def test_get_preference_list_returns_defaults_when_no_config():
    reg = ModelRegistry()
    prefs = reg.get_preference_list("video_captioning", "balance")
    assert prefs == DEFAULT_TASK_PREFERENCES["video_captioning"]["balance"]


def test_get_preference_list_user_overrides_defaults():
    cfg = {
        "task_preferences": {
            "video_captioning": {
                "balance": ["my-custom-model:latest"],
            }
        }
    }
    reg = ModelRegistry(cfg)
    prefs = reg.get_preference_list("video_captioning", "balance")
    assert prefs == ["my-custom-model:latest"]


def test_get_preference_list_invalid_mode_raises():
    reg = ModelRegistry()
    with pytest.raises(ModelRegistryError):
        reg.get_preference_list("video_captioning", "ultra")


# ======================================================================
# Auto-selection happy paths
# ======================================================================
def test_select_first_installed_pref():
    async def go():
        async with _client_with_models(["llava:13b", "gemma4:latest"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            # balance preference: gemma4 first, then llava
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "gemma4:latest"


def test_select_falls_back_to_second_pref_when_first_missing():
    async def go():
        # Only llava installed; balance prefs are [gemma4, llava, minicpm]
        async with _client_with_models(["llava:13b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "llava:13b"


def test_select_speed_mode_picks_speed_pref():
    async def go():
        async with _client_with_models(["moondream:latest"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "speed")

    assert _run(go()) == "moondream:latest"


# ======================================================================
# User override
# ======================================================================
def test_user_override_takes_precedence_if_installed():
    cfg = {"task_overrides": {"video_captioning": "llava:13b"}}

    async def go():
        async with _client_with_models(["llava:13b", "gemma4:latest"]) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "llava:13b"


def test_user_override_ignored_if_not_installed_falls_back():
    cfg = {"task_overrides": {"video_captioning": "not-installed:latest"}}

    async def go():
        async with _client_with_models(["gemma4:latest"]) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "gemma4:latest"


# ======================================================================
# No suitable model
# ======================================================================
def test_no_suitable_model_raises():
    async def go():
        async with _client_with_models(["random-unrelated:latest"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    with pytest.raises(NoSuitableModelError):
        _run(go())


def test_no_suitable_with_allow_any_picks_first_installed():
    async def go():
        async with _client_with_models(["random-unrelated:latest"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task(
                "video_captioning", "balance", allow_any_installed=True
            )

    assert _run(go()) == "random-unrelated:latest"


def test_no_suitable_with_allow_any_but_empty_still_raises():
    async def go():
        async with _client_with_models([]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task(
                "video_captioning", "balance", allow_any_installed=True
            )

    with pytest.raises(NoSuitableModelError):
        _run(go())


# ======================================================================
# recommendation_with_reason
# ======================================================================
def test_recommendation_reports_top_preference():
    async def go():
        async with _client_with_models(["gemma4:latest"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] == "gemma4:latest"
    assert "top preference" in out["reason"]
    assert out["installed"] == ["gemma4:latest"]


def test_recommendation_reports_fallback_index():
    async def go():
        async with _client_with_models(["llava:13b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] == "llava:13b"
    assert "fallback" in out["reason"]


def test_recommendation_reports_override():
    cfg = {"task_overrides": {"video_captioning": "llava:13b"}}

    async def go():
        async with _client_with_models(["llava:13b"]) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] == "llava:13b"
    assert "override" in out["reason"]


def test_recommendation_when_none_installed():
    async def go():
        async with _client_with_models([]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] is None
    assert out["installed"] == []
