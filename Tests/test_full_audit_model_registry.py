"""Regressions for truthful model smoke, capability, and tool support claims."""

from __future__ import annotations

import pytest

from pb_studio.ai.lmstudio_client import LMStudioModelInfo
from pb_studio.ai.model_inventory import ModelInventoryService
from pb_studio.ai.model_registry import ModelRegistry

pytestmark = pytest.mark.unauthorized_backend


def test_empty_model_smoke_reply_has_no_synthetic_success_text():
    from backend.routers.models_router import _model_smoke_response_text

    assert _model_smoke_response_text({"response": "  "}, capability="chat") is None
    assert _model_smoke_response_text(
        {"message": {"content": ""}}, capability="vision"
    ) is None


def test_chat_capability_does_not_claim_tool_call_support():
    assert ModelRegistry._required_capability("chat_tool_use") == "tool_calls"


def test_loaded_probe_failure_does_not_claim_model_is_unloaded_and_jit_ready():
    model = ModelInventoryService._installed_entry(
        provider="ollama",
        model=LMStudioModelInfo(name="verified-model"),
        loaded_names=frozenset(),
        capabilities_by_name={"verified-model": frozenset({"chat"})},
        verified_at="2026-09-27T00:00:00+00:00",
        provider_status="degraded",
        capability_error=None,
        loaded_error="Loaded-State Probe fehlgeschlagen (ConnectError).",
    )
    assert model.installed is True
    assert model.usable is True
    assert "unbekannt" in model.status_reason.lower()
    assert "JIT" not in model.status_reason


def test_capability_probe_failure_is_visible_and_does_not_claim_usable():
    model = ModelInventoryService._installed_entry(
        provider="ollama",
        model=LMStudioModelInfo(name="installed-model"),
        loaded_names=frozenset(),
        capabilities_by_name={},
        verified_at="2026-09-27T00:00:00+00:00",
        provider_status="degraded",
        capability_error="Capability-Prüfung fehlgeschlagen (ConnectError).",
        loaded_error=None,
    )

    assert model.installed is True
    assert model.usable is False
    assert model.capabilities == ()
    assert "Capability-Prüfung fehlgeschlagen" in model.status_reason
    assert "ConnectError" in model.status_reason
