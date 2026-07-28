"""Regressionen fuer capability-aware und deadline-bound Models-Routing."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from backend.routers import models_router
from pb_studio.ai.lmstudio_client import LMStudioModelInfo


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
        return [LMStudioModelInfo(name=f"{self.provider}-chat")]

    async def get_model_capabilities(self):
        return {f"{self.provider}-chat": frozenset({"chat"})}


def test_models_list_offline_provider_has_hard_deadline():
    def factory(*, provider=None, **_kwargs):
        if provider == "ollama":
            return _ProbeClient("ollama", delay=1.0, alive=False)
        return _ProbeClient("lmstudio", delay=0.0, alive=True)

    async def go():
        with patch(
            "pb_studio.ai.llm_provider.get_llm_client",
            side_effect=factory,
        ), patch.object(models_router, "PROVIDER_PROBE_DEADLINE_SECONDS", 0.02):
            return await asyncio.wait_for(models_router.list_models(), timeout=0.2)

    response = asyncio.run(go())
    assert response.lmstudio_available is True
    assert response.ollama_available is False
    assert [model.name for model in response.models] == ["lmstudio-chat"]
