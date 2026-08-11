"""Focused contracts for the bounded OBJ-76 LM Studio diagnostic."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnostics" / "verify_lmstudio_vlm.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_lmstudio_vlm", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_load_waits_for_cli_success_before_accepting_loaded_state(monkeypatch):
    module = _load_module()
    calls: list[str] = []

    def run(command, timeout):
        calls.append("cli_terminal")
        return subprocess.CompletedProcess(command, 0, "", "")

    def wait_loaded(_lms, _identifier, expected):
        assert expected is True
        assert calls == ["cli_terminal"]
        calls.append("state_ready")
        return {
            "identifier": "receipt-id",
            "modelKey": "model-key",
            "status": "idle",
            "contextLength": 8192,
            "sizeBytes": 1,
            "vision": True,
        }

    monkeypatch.setattr(module, "_run", run)
    monkeypatch.setattr(module, "_wait_loaded", wait_loaded)

    receipt = module._load("lms", "model-key", "receipt-id", 8192)

    assert calls == ["cli_terminal", "state_ready"]
    assert receipt["cli_exit_code"] == 0
    assert receipt["state"]["status"] == "idle"


def test_model_load_failure_never_becomes_a_ready_receipt(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, timeout: subprocess.CompletedProcess(
            command,
            1,
            "",
            "Error: Engine protocol startup was aborted.",
        ),
    )
    monkeypatch.setattr(
        module,
        "_wait_loaded",
        lambda *_args, **_kwargs: pytest.fail("failed CLI load must not be polled"),
    )

    with pytest.raises(RuntimeError, match="Engine protocol startup was aborted"):
        module._load("lms", "model-key", "receipt-id", 8192)
