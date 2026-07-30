"""Live LM Studio -> Ollama receipt-bound failover proof for T364."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pb_studio.ai.lmstudio_client import is_provider_failure
from pb_studio.ai.model_inventory import get_model_inventory_service
from pb_studio.ai.model_registry import (
    ModelRegistry,
    execute_with_model_failover,
)


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).with_suffix(".json")
LMS = Path(r"C:\Users\david\.lmstudio\bin\lms.exe")
OLLAMA = Path(r"C:\Users\david\AppData\Local\Programs\Ollama\ollama.exe")


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_port(port: int, expected: bool, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(port) is expected:
            return
        time.sleep(0.25)
    raise RuntimeError(
        f"Port {port} did not become {'open' if expected else 'closed'}"
    )


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )


async def main() -> dict[str, Any]:
    if not LMS.is_file() or not OLLAMA.is_file():
        raise RuntimeError("LM Studio or Ollama CLI is missing")
    if not _port_open(1234) or not _port_open(11434):
        raise RuntimeError("Both live providers must be ready before T364 failover")

    inventory = get_model_inventory_service()
    baseline = await inventory.refresh(force=True)
    baseline_states = {
        provider.provider: provider.status for provider in baseline.providers
    }
    if baseline_states != {"lmstudio": "ready", "ollama": "ready"}:
        raise RuntimeError(f"Unexpected provider baseline: {baseline_states}")

    counters = {"refresh": 0, "invalidate": 0, "operation": 0}
    original_refresh = inventory.refresh
    original_invalidate = inventory.invalidate

    async def counted_refresh(*args: Any, **kwargs: Any):
        counters["refresh"] += 1
        return await original_refresh(*args, **kwargs)

    def counted_invalidate() -> None:
        counters["invalidate"] += 1
        original_invalidate()

    inventory.refresh = counted_refresh  # type: ignore[method-assign]
    inventory.invalidate = counted_invalidate  # type: ignore[method-assign]
    original_invalidate()

    lmstudio_stopped = False
    try:
        registry = ModelRegistry(
            {
                "task_overrides": {"chat_general": "moondream:latest"},
                "task_provider_overrides": {"chat_general": "ollama"},
            }
        )

        async def operation(client, receipt):
            nonlocal lmstudio_stopped
            counters["operation"] += 1
            if counters["operation"] == 1:
                if receipt.provider != "lmstudio":
                    raise AssertionError("First receipt was not LM Studio")
                _run([str(LMS), "server", "stop"])
                lmstudio_stopped = True
                _wait_for_port(1234, False)
            response = await client.chat(
                model=receipt.model_id,
                messages=[{"role": "user", "content": "Reply with OK."}],
                options={"num_predict": 1, "temperature": 0},
            )
            return {
                "provider": receipt.provider,
                "model": receipt.model_id,
                "response_model": response.get("model"),
                "done": response.get("done"),
                "content": str(
                    (response.get("message") or {}).get("content") or ""
                )[:80],
            }

        result, selected, attempts = await execute_with_model_failover(
            registry,
            "chat_general",
            "balance",
            operation,
            is_retryable=is_provider_failure,
            is_provider_failure=is_provider_failure,
            explicit_model="hermes-ha-qwen35",
            explicit_provider="lmstudio",
        )
        receipts = [receipt.to_dict() for receipt in attempts]
        if len(receipts) != 2:
            raise AssertionError(f"Expected two receipts, got {len(receipts)}")
        if receipts[0]["provider"] != "lmstudio":
            raise AssertionError("First receipt provider mismatch")
        if receipts[1]["provider"] != "ollama":
            raise AssertionError("Failover did not switch to Ollama")
        if receipts[1]["model_id"] != "moondream:latest":
            raise AssertionError("Failover did not bind the configured Ollama model")
        if selected.provider != result["provider"]:
            raise AssertionError("Selected receipt and HTTP provider diverged")
        if selected.model_id != result["model"]:
            raise AssertionError("Selected receipt and HTTP model diverged")
        if counters != {"refresh": 2, "invalidate": 1, "operation": 2}:
            raise AssertionError(f"Unexpected failover counters: {counters}")

        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
            "baseline_states": baseline_states,
            "counters": counters,
            "attempts": receipts,
            "selected": selected.to_dict(),
            "http_result": result,
        }
    finally:
        inventory.refresh = original_refresh  # type: ignore[method-assign]
        inventory.invalidate = original_invalidate  # type: ignore[method-assign]
        if lmstudio_stopped or not _port_open(1234):
            _run(
                [
                    str(LMS),
                    "server",
                    "start",
                    "--port",
                    "1234",
                    "--bind",
                    "127.0.0.1",
                ]
            )
            _wait_for_port(1234, True)
        _run([str(OLLAMA), "stop", "moondream:latest"])


if __name__ == "__main__":
    try:
        receipt = asyncio.run(main())
    except Exception as exc:
        failure = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        OUTPUT.write_text(
            json.dumps(failure, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
