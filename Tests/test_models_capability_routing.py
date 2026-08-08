"""Regressionen fuer capability-aware und deadline-bound Models-Routing."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

from backend.routers import models_router
from pb_studio.ai import model_inventory
from pb_studio.ai.lmstudio_client import (
    LMStudioConnectionError,
    LMStudioModelInfo,
)
from pb_studio.ai.model_inventory import (
    ModelInventoryEntry,
    ModelInventoryService,
    ModelInventorySnapshot,
    ProviderInventory,
    _LoadedProbe,
)


class _ProbeClient:
    def __init__(self, provider: str, *, delay: float, alive: bool) -> None:
        self.provider = provider
        self.base_url = f"http://{provider}/v1"
        self._delay = delay
        self._alive = alive

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self.aclose()

    async def aclose(self) -> None:
        return None

    async def is_alive(self) -> bool:
        await asyncio.sleep(self._delay)
        return self._alive

    async def list_models(self):
        await asyncio.sleep(self._delay)
        if not self._alive:
            raise LMStudioConnectionError(f"{self.provider} offline")
        return [LMStudioModelInfo(name=f"{self.provider}-chat")]

    async def get_model_capabilities(self):
        return {f"{self.provider}-chat": frozenset({"chat"})}

    async def supports_capability(self, capability: str) -> bool:
        capabilities = await self.get_model_capabilities()
        return any(
            capability in model_capabilities
            for model_capabilities in capabilities.values()
        )


def test_models_list_offline_provider_has_hard_deadline():
    def factory(*, provider=None, **_kwargs):
        if provider == "ollama":
            return _ProbeClient("ollama", delay=1.0, alive=False)
        return _ProbeClient("lmstudio", delay=0.0, alive=True)

    service = ModelInventoryService(
        probe_timeout_seconds=0.5,
        cache_ttl_seconds=5.0,
    )

    async def go():
        with (
            patch.object(model_inventory, "get_llm_client", side_effect=factory),
            patch.object(
                model_inventory,
                "get_base_url",
                side_effect=lambda provider: f"http://{provider}/v1",
            ),
            patch.object(
                service,
                "_loaded_lmstudio",
                AsyncMock(return_value=_LoadedProbe(frozenset())),
            ),
            patch.object(
                service,
                "_loaded_ollama",
                AsyncMock(return_value=_LoadedProbe(frozenset())),
            ),
        ):
            started = time.perf_counter()
            snapshot = await service.refresh(force=True)
            elapsed = time.perf_counter() - started
            with (
                patch.object(
                    model_inventory,
                    "get_model_inventory_service",
                    return_value=service,
                ),
                patch.object(models_router, "_enrich_model_entry", lambda entry: entry),
            ):
                response = await models_router.list_models()
        return response, snapshot, elapsed

    response, snapshot, elapsed = asyncio.run(go())
    assert elapsed < 0.8
    assert response.lmstudio_available is True
    assert response.ollama_available is False
    assert [model.name for model in response.models] == ["lmstudio-chat"]
    assert {
        provider.provider: provider.status
        for provider in snapshot.providers
    } == {"lmstudio": "ready", "ollama": "offline"}


def test_recommendation_distinguishes_live_provider_from_missing_capability():
    snapshot = ModelInventorySnapshot(
        providers=(
            ProviderInventory(
                provider="lmstudio",
                status="ready",
                base_url="http://lmstudio/v1",
                verified_at="2026-07-30T06:00:00+00:00",
                status_reason="frozen ready",
            ),
            ProviderInventory(
                provider="ollama",
                status="offline",
                base_url="http://ollama/v1",
                verified_at="2026-07-30T06:00:00+00:00",
                status_reason="frozen offline",
            ),
        ),
        models=(
            ModelInventoryEntry(
                provider="lmstudio",
                name="lmstudio-chat",
                installed=True,
                loaded=True,
                downloadable=False,
                usable=True,
                capabilities=("chat",),
                inventory_sources=("frozen",),
                verified_at="2026-07-30T06:00:00+00:00",
                status_reason="chat only",
            ),
        ),
        verified_at="2026-07-30T06:00:00+00:00",
        generation=1,
    )

    class FrozenService:
        async def refresh(self):
            return snapshot

    service = FrozenService()

    async def go():
        with (
            patch.object(
                model_inventory,
                "get_model_inventory_service",
                return_value=service,
            ),
            patch.object(models_router, "_load_ai_config", return_value={}),
        ):
            return await models_router.recommend_model(
                task="video_captioning",
                mode="balance",
            )

    response = asyncio.run(go())

    assert response.model is None
    assert response.installed == ["lmstudio-chat"]
    assert "vision" in response.reason
