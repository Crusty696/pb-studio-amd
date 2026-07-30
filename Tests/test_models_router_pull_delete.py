"""Provider-bound pull/delete regressions for the central live inventory."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import owner_capability
from backend.routers import models_router
from pb_studio.ai import model_inventory
from pb_studio.ai.model_inventory import (
    ModelInventoryEntry,
    ModelInventorySnapshot,
    ProviderInventory,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    capability = "T362-owner-capability"
    monkeypatch.setattr(
        owner_capability,
        "_OWNER_CAPABILITY",
        capability,
    )
    app = FastAPI()
    app.include_router(models_router.router)
    with TestClient(app) as test_client:
        test_client.headers.update(
            {owner_capability.OWNER_CAPABILITY_HEADER: capability}
        )
        yield test_client


class FrozenInventoryService:
    def __init__(
        self,
        snapshot: ModelInventorySnapshot,
        *,
        downloadable: ModelInventoryEntry | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.downloadable = downloadable
        self.invalidate_calls = 0

    async def refresh(self) -> ModelInventorySnapshot:
        return self.snapshot

    async def verify_downloadable_candidate(
        self,
        provider: str,
        model_name: str,
    ) -> ModelInventoryEntry | None:
        candidate = self.downloadable
        if (
            candidate is not None
            and candidate.provider == provider
            and candidate.name == model_name
        ):
            return candidate
        return None

    def invalidate(self) -> None:
        self.invalidate_calls += 1


def _provider(provider: str, status: str = "ready") -> ProviderInventory:
    return ProviderInventory(
        provider=provider,
        status=status,
        base_url=f"http://{provider}/v1",
        verified_at="2026-07-30T06:00:00+00:00",
        status_reason=f"frozen {status}",
    )


def _model(
    provider: str,
    name: str,
    *,
    installed: bool,
    downloadable: bool = False,
) -> ModelInventoryEntry:
    return ModelInventoryEntry(
        provider=provider,
        name=name,
        installed=installed,
        loaded=False,
        downloadable=downloadable,
        usable=installed,
        capabilities=("chat",) if installed else (),
        inventory_sources=("frozen",),
        verified_at="2026-07-30T06:00:00+00:00",
        status_reason="frozen model",
    )


def _snapshot(
    *models: ModelInventoryEntry,
    providers: tuple[ProviderInventory, ...],
) -> ModelInventorySnapshot:
    return ModelInventorySnapshot(
        providers=providers,
        models=models,
        verified_at="2026-07-30T06:00:00+00:00",
        generation=1,
    )


def _install_service(
    monkeypatch: pytest.MonkeyPatch,
    service: FrozenInventoryService,
) -> None:
    monkeypatch.setattr(
        model_inventory,
        "get_model_inventory_service",
        lambda: service,
    )


def test_pull_model_lmstudio_fallback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LM-Studio-only state cannot prove an Ollama download candidate."""
    service = FrozenInventoryService(
        _snapshot(
            _model("lmstudio", "some-model", installed=True),
            providers=(_provider("lmstudio"),),
        )
    )
    _install_service(monkeypatch, service)

    response = client.post("/models/pull", json={"name": "some-model"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "not_verified"
    assert "LM Studio" in body["hint"]


def test_delete_model_lmstudio_fallback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LM-Studio entries are never forwarded to Ollama delete."""
    service = FrozenInventoryService(
        _snapshot(
            _model("lmstudio", "some-model", installed=True),
            providers=(_provider("lmstudio"),),
        )
    )
    _install_service(monkeypatch, service)

    response = client.delete("/models/some-model")

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert "LM Studio" in body["hint"]


def test_delete_model_ollama_forwarding(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an exact installed Ollama identity reaches its native API."""
    service = FrozenInventoryService(
        _snapshot(
            _model("ollama", "my-ollama-model", installed=True),
            providers=(_provider("ollama"),),
        )
    )
    _install_service(monkeypatch, service)
    mock_response = MagicMock(status_code=200, text="OK")

    with (
        patch(
            "pb_studio.ai.llm_provider.get_base_url",
            return_value="http://localhost:11434/v1",
        ),
        patch(
            "httpx.AsyncClient.request",
            AsyncMock(return_value=mock_response),
        ) as mock_request,
    ):
        response = client.delete("/models/my-ollama-model")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert service.invalidate_calls == 1
    mock_request.assert_awaited_once_with(
        "DELETE",
        "http://localhost:11434/api/delete",
        json={"name": "my-ollama-model"},
    )


def test_pull_model_ollama_forwarding(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live-verified Ollama candidate is streamed from its native API."""
    candidate = _model(
        "ollama",
        "my-ollama-model",
        installed=False,
        downloadable=True,
    )
    service = FrozenInventoryService(
        _snapshot(providers=(_provider("ollama"),)),
        downloadable=candidate,
    )
    _install_service(monkeypatch, service)

    stream_context = MagicMock()
    stream_response = MagicMock(status_code=200)

    async def fake_aiter_lines():
        yield '{"status": "pulling layer 1", "completed": 50, "total": 100}'
        yield '{"status": "success"}'

    stream_response.aiter_lines = fake_aiter_lines
    stream_context.__aenter__ = AsyncMock(return_value=stream_response)
    stream_context.__aexit__ = AsyncMock()

    with (
        patch(
            "pb_studio.ai.llm_provider.get_base_url",
            return_value="http://localhost:11434/v1",
        ),
        patch(
            "httpx.AsyncClient.stream",
            return_value=stream_context,
        ) as mock_stream,
    ):
        response = client.post(
            "/models/pull",
            json={"name": "my-ollama-model"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = [
        line if isinstance(line, str) else line.decode("utf-8")
        for line in response.iter_lines()
    ]
    non_empty_lines = [line for line in lines if line.strip()]
    assert len(non_empty_lines) == 4
    assert "event: pull_progress" in non_empty_lines[0]
    assert "pulling layer 1" in non_empty_lines[1]
    assert "event: pull_progress" in non_empty_lines[2]
    assert "success" in non_empty_lines[3]
    mock_stream.assert_called_once_with(
        "POST",
        "http://localhost:11434/api/pull",
        json={"name": "my-ollama-model", "stream": True},
    )
