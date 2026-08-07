"""T357 contracts for truthful model inventory and bounded selection receipts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from pb_studio.ai import llm_provider, model_inventory
from pb_studio.ai.lmstudio_client import LMStudioModelInfo
from pb_studio.ai.model_inventory import (
    ModelInventoryEntry,
    ModelInventoryService,
    ModelInventorySnapshot,
    ProviderInventory,
)
from pb_studio.ai.model_registry import (
    ModelFailoverExhaustedError,
    ModelRegistry,
    ModelRegistryError,
    NoSuitableModelError,
    execute_with_model_failover,
)


def _run(coro):
    return asyncio.run(coro)


def _entry(
    provider: str,
    name: str,
    *,
    loaded: bool = False,
    capabilities: tuple[str, ...] = ("chat",),
    installed: bool = True,
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
        inventory_sources=("test",),
        verified_at="2026-07-30T00:00:00+00:00",
        status_reason="test fixture",
    )


def _snapshot(*models: ModelInventoryEntry) -> ModelInventorySnapshot:
    return ModelInventorySnapshot(
        models=tuple(models),
        verified_at="2026-07-30T00:00:00+00:00",
        generation=7,
    )


class _ProviderClient:
    def __init__(
        self,
        models: list[LMStudioModelInfo],
        capabilities: dict[str, frozenset[str]],
        *,
        list_error: Exception | None = None,
        capability_error: Exception | None = None,
    ) -> None:
        self.models = models
        self.capabilities = capabilities
        self.list_error = list_error
        self.capability_error = capability_error
        self.closed = False

    async def list_models(self) -> list[LMStudioModelInfo]:
        if self.list_error is not None:
            raise self.list_error
        return self.models

    async def get_model_capabilities(self) -> dict[str, frozenset[str]]:
        if self.capability_error is not None:
            raise self.capability_error
        return self.capabilities

    async def aclose(self) -> None:
        self.closed = True


def test_inventory_provider_states_and_model_truth_flags(monkeypatch):
    service = ModelInventoryService()
    client_box: list[_ProviderClient] = []
    loaded_box = [model_inventory._LoadedProbe(frozenset())]

    monkeypatch.setattr(
        model_inventory,
        "get_base_url",
        lambda provider: f"http://{provider}.test/v1",
    )
    monkeypatch.setattr(
        model_inventory,
        "get_llm_client",
        lambda **_kwargs: client_box[0],
    )

    async def loaded_lmstudio(_base_url: str):
        return loaded_box[0]

    monkeypatch.setattr(service, "_loaded_lmstudio", loaded_lmstudio)

    async def go():
        ready_client = _ProviderClient(
            [LMStudioModelInfo(name="vision-ready")],
            {"vision-ready": frozenset({"chat", "vision"})},
        )
        client_box[:] = [ready_client]
        loaded_box[:] = [
            model_inventory._LoadedProbe(frozenset({"vision-ready"}))
        ]
        ready = await service._inventory_provider("lmstudio")

        empty_client = _ProviderClient([], {})
        client_box[:] = [empty_client]
        loaded_box[:] = [model_inventory._LoadedProbe(frozenset())]
        empty = await service._inventory_provider("lmstudio")

        degraded_client = _ProviderClient(
            [LMStudioModelInfo(name="unknown-capability")],
            {},
            capability_error=RuntimeError("capability endpoint unavailable"),
        )
        client_box[:] = [degraded_client]
        degraded = await service._inventory_provider("lmstudio")

        offline_client = _ProviderClient(
            [],
            {},
            list_error=ConnectionError("provider offline"),
        )
        client_box[:] = [offline_client]
        offline = await service._inventory_provider("lmstudio")
        return (
            ready,
            empty,
            degraded,
            offline,
            ready_client,
            empty_client,
            degraded_client,
            offline_client,
        )

    (
        (ready_provider, ready_models),
        (empty_provider, empty_models),
        (degraded_provider, degraded_models),
        (offline_provider, offline_models),
        *clients,
    ) = _run(go())

    assert ready_provider.status == "ready"
    assert len(ready_models) == 1
    assert ready_models[0].installed is True
    assert ready_models[0].loaded is True
    assert ready_models[0].downloadable is False
    assert ready_models[0].usable is True
    assert ready_models[0].capabilities == ("chat", "vision")

    assert empty_provider.status == "online_empty"
    assert empty_models == []
    assert degraded_provider.status == "degraded"
    assert degraded_models[0].installed is True
    assert degraded_models[0].usable is False
    assert offline_provider.status == "offline"
    assert offline_models == []
    assert all(client.closed for client in clients)


def test_inventory_refresh_coalesces_concurrent_callers(monkeypatch):
    service = ModelInventoryService(cache_ttl_seconds=60.0)
    calls: list[str] = []

    async def inventory_provider(provider: str):
        calls.append(provider)
        await asyncio.sleep(0)
        status = "ready" if provider == "lmstudio" else "online_empty"
        return (
            ProviderInventory(
                provider=provider,
                status=status,
                base_url=f"http://{provider}.test/v1",
                verified_at="2026-07-30T00:00:00+00:00",
            ),
            [],
        )

    monkeypatch.setattr(service, "_inventory_provider", inventory_provider)

    async def go():
        return await asyncio.gather(service.refresh(), service.refresh())

    first, second = _run(go())

    assert first is second
    assert first.generation == 1
    assert calls.count("lmstudio") == 1
    assert calls.count("ollama") == 1
    assert {provider.status for provider in first.providers} == {
        "online_empty",
        "ready",
    }


def test_downloadable_requires_valid_ollama_id_and_live_manifest(monkeypatch):
    requests: list[tuple[str, bool]] = []

    class _Response:
        status_code = 200

    class _ManifestClient:
        def __init__(self, **kwargs: Any) -> None:
            self.follow_redirects = kwargs["follow_redirects"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def head(self, url: str, **_kwargs):
            requests.append((url, self.follow_redirects))
            return _Response()

    monkeypatch.setattr(model_inventory.httpx, "AsyncClient", _ManifestClient)
    service = ModelInventoryService()

    async def go():
        verified = await service._verify_downloadable(
            "ollama",
            "acme/vision-model:q4",
        )
        invalid = await service._verify_downloadable(
            "ollama",
            "https://evil.example/model",
        )
        unsupported = await service._verify_downloadable(
            "lmstudio",
            "acme/vision-model:q4",
        )
        return verified, invalid, unsupported

    verified, invalid, unsupported = _run(go())

    assert verified is not None
    assert verified.provider == "ollama"
    assert verified.installed is False
    assert verified.loaded is False
    assert verified.downloadable is True
    assert verified.usable is False
    assert invalid is None
    assert unsupported is None
    assert requests == [
        (
            "https://registry.ollama.ai/v2/acme/vision-model/manifests/q4",
            False,
        )
    ]


def test_receipt_priority_is_explicit_persisted_then_recommendation():
    registry = ModelRegistry(
        {
            "task_overrides": {"chat_general": "persisted-chat"},
            "task_provider_overrides": {"chat_general": "lmstudio"},
        }
    )
    snapshot = _snapshot(
        _entry("ollama", "explicit-chat"),
        _entry("lmstudio", "persisted-chat"),
        _entry("lmstudio", "gemma-4-12b-it-uncensored@q4_k_s"),
        _entry("ollama", "unranked-chat"),
    )

    receipts = registry.selection_receipts_for_task(
        snapshot,
        "chat_general",
        explicit_model="explicit-chat",
        explicit_provider="ollama",
        limit=3,
    )

    assert [
        (receipt.provider, receipt.model_id, receipt.source)
        for receipt in receipts
    ] == [
        ("ollama", "explicit-chat", "explicit_override"),
        ("lmstudio", "persisted-chat", "user_task_override"),
        (
            "lmstudio",
            "gemma-4-12b-it-uncensored@q4_k_s",
            "capability_recommendation",
        ),
    ]
    assert all(receipt.required_capabilities == ("chat",) for receipt in receipts)


def test_vision_receipt_never_selects_text_only_model():
    registry = ModelRegistry({"provider": "lmstudio"})
    snapshot = _snapshot(
        _entry("lmstudio", "loaded-text", loaded=True, capabilities=("chat",)),
        _entry(
            "ollama",
            "verified-vision",
            capabilities=("chat", "vision"),
        ),
    )

    receipt = registry.select_receipt_for_task(
        snapshot,
        "video_captioning",
    )

    assert receipt.provider == "ollama"
    assert receipt.model_id == "verified-vision"
    assert receipt.required_capabilities == ("vision",)
    assert "vision" in receipt.verified_capabilities

    with pytest.raises(NoSuitableModelError):
        registry.select_receipt_for_task(
            _snapshot(
                _entry(
                    "lmstudio",
                    "only-text",
                    loaded=True,
                    capabilities=("chat",),
                )
            ),
            "video_captioning",
        )


def test_capability_join_fails_closed_for_colliding_legacy_aliases():
    service = ModelInventoryService()
    entry = service._installed_entry(
        provider="lmstudio",
        model=LMStudioModelInfo(name="model:latest"),
        loaded_names=frozenset(),
        capabilities_by_name={
            "acme/model:latest": frozenset({"chat"}),
            "evil/model:latest": frozenset({"chat", "vision"}),
        },
        verified_at="2026-07-30T00:00:00+00:00",
        provider_status="ready",
        capability_error=None,
    )

    assert entry.capabilities == ()
    assert entry.usable is False


def test_explicit_legacy_alias_requires_one_canonical_identity():
    registry = ModelRegistry({})
    snapshot = _snapshot(
        _entry("lmstudio", "acme/model:latest"),
        _entry("lmstudio", "evil/model:latest"),
    )

    with pytest.raises(ModelRegistryError, match="mehrdeutig"):
        registry.select_receipt_for_task(
            snapshot,
            "chat_general",
            explicit_model="model:latest",
            explicit_provider="lmstudio",
        )


def test_legacy_model_only_preference_requires_provider_when_ambiguous():
    snapshot = _snapshot(
        _entry("lmstudio", "shared-model"),
        _entry("ollama", "shared-model"),
    )
    ambiguous = ModelRegistry(
        {"task_overrides": {"chat_general": "shared-model"}}
    )

    with pytest.raises(ModelRegistryError, match="mehreren Providern"):
        ambiguous.select_receipt_for_task(snapshot, "chat_general")

    disambiguated = ModelRegistry(
        {
            "task_overrides": {"chat_general": "shared-model"},
            "task_provider_overrides": {"chat_general": "ollama"},
        }
    )
    receipt = disambiguated.select_receipt_for_task(snapshot, "chat_general")
    assert (receipt.provider, receipt.model_id) == ("ollama", "shared-model")


def test_receipt_tie_break_prefers_loaded_then_provider_then_stable_name():
    registry = ModelRegistry({"provider": "ollama"})
    snapshot = _snapshot(
        _entry("lmstudio", "zeta-live", loaded=True),
        _entry("lmstudio", "alpha-idle"),
        _entry("ollama", "zulu-idle"),
        _entry("ollama", "beta-idle"),
    )

    receipts = registry.selection_receipts_for_task(
        snapshot,
        "chat_general",
        limit=3,
    )

    assert [
        (receipt.provider, receipt.model_id, receipt.source)
        for receipt in receipts
    ] == [
        ("lmstudio", "zeta-live", "live_fallback"),
        ("ollama", "beta-idle", "live_fallback"),
        ("ollama", "zulu-idle", "live_fallback"),
    ]


def test_receipt_candidate_limit_is_hard_capped_at_three():
    registry = ModelRegistry(
        {
            "task_preferences": {
                "chat_general": {
                    "balance": [f"candidate-{index}" for index in range(6)]
                }
            }
        }
    )
    snapshot = _snapshot(
        *[
            _entry("lmstudio", f"candidate-{index}")
            for index in range(6)
        ]
    )

    receipts = registry.selection_receipts_for_task(
        snapshot,
        "chat_general",
        limit=999,
    )

    assert len(receipts) == 3
    assert [receipt.model_id for receipt in receipts] == [
        "candidate-0",
        "candidate-1",
        "candidate-2",
    ]


@dataclass
class _FailingClient:
    provider: str

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def test_failover_refreshes_once_and_attempts_at_most_three(monkeypatch):
    snapshot = _snapshot(
        *[
            _entry("lmstudio", f"retry-{index}")
            for index in range(4)
        ]
    )

    class _Inventory:
        def __init__(self) -> None:
            self.refresh_calls = 0
            self.invalidate_calls = 0

        async def refresh(self) -> ModelInventorySnapshot:
            self.refresh_calls += 1
            return snapshot

        def invalidate(self) -> None:
            self.invalidate_calls += 1

    inventory = _Inventory()
    attempted: list[tuple[str, str]] = []
    registry = ModelRegistry(
        {
            "task_preferences": {
                "chat_general": {
                    "balance": [f"retry-{index}" for index in range(4)]
                }
            }
        }
    )

    monkeypatch.setattr(
        model_inventory,
        "get_model_inventory_service",
        lambda: inventory,
    )
    monkeypatch.setattr(
        llm_provider,
        "get_llm_client",
        lambda *, provider, **_kwargs: _FailingClient(provider),
    )

    async def operation(client, receipt):
        assert client.provider == receipt.provider
        attempted.append((receipt.provider, receipt.model_id))
        raise RuntimeError("provider request failed")

    async def go():
        return await execute_with_model_failover(
            registry,
            "chat_general",
            "balance",
            operation,
            is_retryable=lambda exc: isinstance(exc, RuntimeError),
            is_provider_failure=lambda _exc: True,
        )

    with pytest.raises(ModelFailoverExhaustedError) as caught:
        _run(go())

    receipts = caught.value.receipts
    assert inventory.invalidate_calls == 1
    assert inventory.refresh_calls == 2
    assert len(receipts) == 3
    assert attempted == [
        (receipt.provider, receipt.model_id)
        for receipt in receipts
    ]
    assert len(set(attempted)) == 3
    assert [receipt.model_id for receipt in receipts] == [
        "retry-0",
        "retry-1",
        "retry-2",
    ]
