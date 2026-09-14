"""Focused contracts for the bounded OBJ-76 LM Studio diagnostic."""

from __future__ import annotations

import importlib.util
import json
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


def test_unload_waits_for_absence_before_engine_settle(monkeypatch):
    module = _load_module()
    calls: list[object] = []
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, timeout: subprocess.CompletedProcess(command, 0, "", ""),
    )
    monkeypatch.setattr(
        module,
        "_wait_loaded",
        lambda _lms, identifier, expected: calls.append((identifier, expected)),
    )
    monkeypatch.setattr(module.time, "sleep", lambda seconds: calls.append(seconds))

    module._unload("lms", "receipt-id")

    assert calls == [("receipt-id", False), module.MODEL_SETTLE_SECONDS]


def test_restore_accepts_exact_preloaded_state_without_loading(monkeypatch):
    module = _load_module()
    current = {
        "identifier": "receipt-id",
        "modelKey": "model-key",
        "status": "idle",
        "contextLength": 65536,
        "sizeBytes": 42,
        "vision": False,
    }
    monkeypatch.setattr(module, "_loaded_models", lambda _lms: [current])
    monkeypatch.setattr(
        module,
        "_load",
        lambda *_args, **_kwargs: pytest.fail("exact state must not be reloaded"),
    )

    restored = module._restore("lms", current)

    assert restored == {
        "identifier": "receipt-id",
        "model_key": "model-key",
        "status": "idle",
        "context_length": 65536,
        "size_bytes": 42,
        "vision": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (("modelKey", "other-model"), ("contextLength", 8192), ("status", "loading")),
)
def test_restore_rejects_preloaded_identifier_state_mismatch(
    monkeypatch,
    field,
    value,
):
    module = _load_module()
    original = {
        "identifier": "receipt-id",
        "modelKey": "model-key",
        "status": "idle",
        "contextLength": 65536,
    }
    current = {**original, field: value}
    monkeypatch.setattr(module, "_loaded_models", lambda _lms: [current])
    monkeypatch.setattr(
        module,
        "_load",
        lambda *_args, **_kwargs: pytest.fail("mismatch must not be reloaded"),
    )

    with pytest.raises(RuntimeError, match="restore state mismatch"):
        module._restore("lms", original)


def test_stream_receipt_distinguishes_content_from_reasoning(monkeypatch):
    module = _load_module()

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            chunks = (
                {
                    "id": "response-id",
                    "choices": [
                        {
                            "delta": {"reasoning_content": "inspect frame"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "response-id",
                    "choices": [
                        {
                            "delta": {"content": "night, city, neon"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
            for chunk in chunks:
                yield f"data: {json.dumps(chunk)}\n".encode()
            yield b"data: [DONE]\n"

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *_a, **_k: Response())

    receipt = module._stream_inference(b"{}")

    assert receipt["content_nonempty"] is True
    assert receipt["content_length"] == len("night, city, neon")
    assert receipt["content_sha256"] == module.hashlib.sha256(
        b"night, city, neon"
    ).hexdigest()
    assert receipt["reasoning_length"] == len("inspect frame")
    assert receipt["finish_reason"] == "stop"
