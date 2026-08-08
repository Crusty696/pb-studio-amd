"""T357 contracts for provider-aware model routing and persistence.

All provider state is frozen in memory. Configuration writes target only the
pytest ``tmp_path`` copy; no test touches the repository ``config.json``.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import models_router
from backend import owner_capability
from pb_studio import config_manager as config_manager_module
from pb_studio.ai.model_inventory import (
    ModelInventoryEntry,
    ModelInventorySnapshot,
    ProviderInventory,
)


VERIFIED_AT = "2026-07-30T06:00:00+00:00"


class _FrozenInventoryService:
    def __init__(self, snapshot: ModelInventorySnapshot) -> None:
        self.snapshot = snapshot
        self.invalidate_calls = 0
        self.refresh_calls = 0

    def invalidate(self) -> None:
        self.invalidate_calls += 1

    async def refresh(self) -> ModelInventorySnapshot:
        self.refresh_calls += 1
        return self.snapshot


class _TempConfigManager:
    def __init__(self, config_file: Path, payload: dict[str, Any]) -> None:
        self.config_file = config_file
        self._config = payload
        self.set_calls = 0
        self._write()

    def _write(self) -> None:
        self.config_file.write_text(
            json.dumps(self._config, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.set_calls += 1
        self._config[key] = value
        self._write()


class _GenerationClient:
    def __init__(self, provider: str, calls: list[dict[str, Any]]) -> None:
        self.provider = provider
        self.calls = calls

    async def __aenter__(self) -> "_GenerationClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        options: dict[str, Any],
    ) -> dict[str, str]:
        self.calls.append(
            {
                "provider": self.provider,
                "model": model,
                "prompt": prompt,
                "options": options,
            }
        )
        return {"response": "ok"}


def _provider(
    provider: str,
    status: str = "ready",
    *,
    discover_url: str | None = None,
) -> ProviderInventory:
    port = 1234 if provider == "lmstudio" else 11434
    return ProviderInventory(
        provider=provider,
        status=status,
        base_url=f"http://127.0.0.1:{port}/v1",
        verified_at=VERIFIED_AT,
        status_reason=f"{provider} {status}",
        catalog_status="discover_only" if provider == "lmstudio" else "verified",
        discover_url=discover_url,
    )


def _model(
    provider: str,
    name: str,
    *,
    capabilities: tuple[str, ...] = ("chat",),
    installed: bool = True,
    loaded: bool = False,
    downloadable: bool = False,
    usable: bool = True,
) -> ModelInventoryEntry:
    return ModelInventoryEntry(
        provider=provider,
        name=name,
        installed=installed,
        loaded=loaded,
        downloadable=downloadable,
        usable=usable,
        capabilities=capabilities,
        inventory_sources=(f"{provider}:frozen",),
        verified_at=VERIFIED_AT,
        status_reason=f"{provider}/{name}",
        size_bytes=4 * 1024**3,
    )


def _snapshot(
    *models: ModelInventoryEntry,
    providers: tuple[ProviderInventory, ...] | None = None,
) -> ModelInventorySnapshot:
    return ModelInventorySnapshot(
        providers=providers
        or (
            _provider("lmstudio"),
            _provider("ollama"),
        ),
        models=models,
        verified_at=VERIFIED_AT,
        generation=17,
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    capability = "T357-owner-capability"
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


@pytest.mark.parametrize(
    ("method", "url", "payload"),
    (
        ("post", "/models/pull", {"name": "library/model:latest"}),
        ("delete", "/models/library/model:latest", None),
        (
            "post",
            "/models/activate",
            {"name": "model", "provider": "ollama"},
        ),
        ("post", "/models/mode", {"mode": "balance"}),
        ("post", "/models/test", {"name": "model", "provider": "ollama"}),
    ),
)
def test_model_mutations_require_owner_capability(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
) -> None:
    monkeypatch.setattr(
        owner_capability,
        "_OWNER_CAPABILITY",
        "expected-owner-capability",
    )
    app = FastAPI()
    app.include_router(models_router.router)
    with TestClient(app) as unauthorized:
        response = unauthorized.request(method, url, json=payload)
    assert response.status_code == 403


def test_config_save_is_atomic_and_propagates_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = object.__new__(config_manager_module.ConfigManager)
    manager.config_file = tmp_path / "config.json"
    manager._config = {"ai": {"provider": "lmstudio"}}
    manager.save_config()
    original = manager.config_file.read_bytes()

    manager._config = {"ai": {"provider": "ollama"}}

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(config_manager_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        manager.save_config()

    assert manager.config_file.read_bytes() == original
    assert list(tmp_path.glob(".config.json.*.tmp")) == []


def _install_inventory(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: ModelInventorySnapshot,
) -> _FrozenInventoryService:
    service = _FrozenInventoryService(snapshot)
    monkeypatch.setattr(
        "pb_studio.ai.model_inventory.get_model_inventory_service",
        lambda: service,
    )
    return service


def _disable_descriptive_enrichment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        models_router,
        "_enrich_model_entry",
        lambda entry: entry,
    )


def test_models_list_preserves_provider_identity_and_refresh_invalidation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat", loaded=True),
            _model("ollama", "shared-chat"),
        ),
    )
    _disable_descriptive_enrichment(monkeypatch)
    monkeypatch.setattr(
        models_router,
        "_load_ai_config",
        lambda: {
            "task_overrides": {"chat_general": "shared-chat"},
            "task_provider_overrides": {"chat_general": "ollama"},
        },
    )

    response = client.get("/models/list", params={"refresh": "true"})

    assert response.status_code == 200
    body = response.json()
    assert body["inventory_generation"] == 17
    assert {(item["provider"], item["name"]) for item in body["models"]} == {
        ("lmstudio", "shared-chat"),
        ("ollama", "shared-chat"),
    }
    active = {
        item["provider"]: item["active_tasks"]
        for item in body["models"]
    }
    assert active == {"lmstudio": [], "ollama": ["Chat"]}
    assert {item["provider"]: item["status"] for item in body["providers"]} == {
        "lmstudio": "ready",
        "ollama": "ready",
    }
    assert service.invalidate_calls == 1
    assert service.refresh_calls == 1


def test_models_list_accepts_unique_legacy_model_only_override(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(_model("lmstudio", "legacy-chat")),
    )
    _disable_descriptive_enrichment(monkeypatch)
    monkeypatch.setattr(
        models_router,
        "_load_ai_config",
        lambda: {"task_overrides": {"chat_general": "legacy-chat"}},
    )

    response = client.get("/models/list")

    assert response.status_code == 200
    assert response.json()["models"][0]["active_tasks"] == ["Chat"]


def test_models_list_marks_no_card_active_for_ambiguous_legacy_override(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat"),
        ),
    )
    _disable_descriptive_enrichment(monkeypatch)
    monkeypatch.setattr(
        models_router,
        "_load_ai_config",
        lambda: {"task_overrides": {"chat_general": "shared-chat"}},
    )

    response = client.get("/models/list")

    assert response.status_code == 200
    assert all(
        item["active_tasks"] == []
        for item in response.json()["models"]
    )


def test_models_available_exposes_only_live_verified_downloadable_entries(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "installed-chat"),
            _model(
                "ollama",
                "verified-download:latest",
                installed=False,
                downloadable=True,
                usable=False,
                capabilities=(),
            ),
            providers=(
                _provider(
                    "lmstudio",
                    discover_url="https://lmstudio.ai/models",
                ),
                _provider(
                    "ollama",
                    discover_url="https://ollama.com/library",
                ),
            ),
        ),
    )

    response = client.get("/models/available")

    assert response.status_code == 200
    body = response.json()
    assert [(item["provider"], item["name"]) for item in body["available"]] == [
        ("ollama", "verified-download:latest")
    ]
    assert body["available"][0]["installed"] is False
    assert body["available"][0]["downloadable"] is True
    assert {item["provider"] for item in body["discover_actions"]} == {
        "lmstudio",
        "ollama",
    }


def test_recommendation_receipt_binds_persisted_provider_and_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat", loaded=True),
        ),
    )
    monkeypatch.setattr(
        models_router,
        "_load_ai_config",
        lambda: {
            "provider": "auto",
            "task_overrides": {"chat_general": "shared-chat"},
            "task_provider_overrides": {"chat_general": "ollama"},
        },
    )

    response = client.get(
        "/models/recommendations",
        params={"task": "chat_general", "mode": "balance"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "shared-chat"
    assert body["required_capabilities"] == ["chat"]
    assert body["verified_capabilities"] == ["chat"]
    assert body["selection_source"] == "user_task_override"
    assert body["selected_at"]


def test_recommendation_rejects_ambiguous_legacy_model_only_override(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat"),
        ),
    )
    monkeypatch.setattr(
        models_router,
        "_load_ai_config",
        lambda: {"task_overrides": {"chat_general": "shared-chat"}},
    )

    response = client.get(
        "/models/recommendations",
        params={"task": "chat_general", "mode": "balance"},
    )

    assert response.status_code == 400
    assert "task_provider_overrides" in response.json()["detail"]


def test_activate_persists_model_and_provider_then_invalidates_inventory(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _install_inventory(
        monkeypatch,
        _snapshot(_model("ollama", "ollama-chat", loaded=True)),
    )
    config_copy = tmp_path / "config.json"
    manager = _TempConfigManager(
        config_copy,
        {
            "ai": {
                "task_overrides": {"video_captioning": "legacy-vision"},
                "task_provider_overrides": {},
            }
        },
    )
    monkeypatch.setattr(
        "pb_studio.config_manager.ConfigManager",
        lambda: manager,
    )

    response = client.post(
        "/models/activate",
        json={
            "name": "ollama-chat",
            "provider": "ollama",
            "task": "chat_general",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    persisted = json.loads(config_copy.read_text(encoding="utf-8"))["ai"]
    assert persisted["task_overrides"] == {
        "video_captioning": "legacy-vision",
        "chat_general": "ollama-chat",
    }
    assert persisted["task_provider_overrides"] == {
        "chat_general": "ollama"
    }
    assert manager.set_calls == 1
    assert service.invalidate_calls == 1
    assert service.refresh_calls == 2


def test_activate_requires_provider_when_model_name_is_ambiguous(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat"),
        ),
    )
    manager = _TempConfigManager(
        tmp_path / "config.json",
        {"ai": {"task_overrides": {}, "task_provider_overrides": {}}},
    )
    monkeypatch.setattr(
        "pb_studio.config_manager.ConfigManager",
        lambda: manager,
    )

    response = client.post(
        "/models/activate",
        json={"name": "shared-chat", "task": "chat_general"},
    )

    assert response.status_code == 409
    assert manager.set_calls == 0
    assert service.invalidate_calls == 0
    assert service.refresh_calls == 1


def test_model_smoke_request_uses_selected_provider_and_exact_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat", loaded=True),
        ),
    )
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "pb_studio.ai.llm_provider.get_llm_client",
        lambda *, provider: _GenerationClient(provider, calls),
    )

    response = client.post(
        "/models/test",
        json={"name": "shared-chat", "provider": "ollama"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert calls == [
        {
            "provider": "ollama",
            "model": "shared-chat",
            "prompt": "Say 'ok'",
            "options": {"max_tokens": 1, "temperature": 0.0},
        }
    ]


def test_model_smoke_request_does_not_guess_ambiguous_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_inventory(
        monkeypatch,
        _snapshot(
            _model("lmstudio", "shared-chat"),
            _model("ollama", "shared-chat"),
        ),
    )
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "pb_studio.ai.llm_provider.get_llm_client",
        lambda *, provider: _GenerationClient(provider, calls),
    )

    response = client.post(
        "/models/test",
        json={"name": "shared-chat"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "nicht eindeutig" in response.json()["error"]
    assert calls == []
