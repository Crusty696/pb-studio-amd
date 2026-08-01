"""T411 fresh-install DirectML probe with runtime session receipts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from pb_studio.core import directml_adapter


ROOT = Path(__file__).resolve().parents[3]
T363_PROBE = Path(__file__).with_name("T363-hardware-probe.py")
SESSION_RECEIPTS: list[dict[str, Any]] = []


def _load_t363() -> Any:
    spec = importlib.util.spec_from_file_location("t411_t363_probe", T363_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load workload driver: {T363_PROBE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MODELS_DIR = ROOT / "models"
    module.PROJECT_DIR = Path(os.environ["PBSTUDIO_T411_PROJECT_DIR"])
    module.PROJECT_DB = Path(os.environ["PBSTUDIO_T411_PROJECT_DB"])
    return module


def _capture_session(session: Any) -> None:
    options = session.get_session_options()
    provider_options = getattr(session, "get_provider_options", lambda: {})()
    receipt = {
        "ordinal": len(SESSION_RECEIPTS) + 1,
        "providers": list(session.get_providers()),
        "provider_options": provider_options,
        "enable_mem_pattern": options.enable_mem_pattern,
        "enable_cpu_mem_arena": options.enable_cpu_mem_arena,
        "disable_cpu_ep_fallback": options.get_session_config_entry(
            "session.disable_cpu_ep_fallback"
        ),
    }
    SESSION_RECEIPTS.append(receipt)


def _install_capture() -> None:
    original = directml_adapter.enforce_directml_session

    def capture(session: Any) -> Any:
        enforced = original(session)
        _capture_session(enforced)
        return enforced

    directml_adapter.enforce_directml_session = capture


def _emit(prefix: str, result: dict[str, Any]) -> None:
    payload = dict(result)
    payload["fresh_install_root"] = str(ROOT)
    payload["session_contracts"] = list(SESSION_RECEIPTS)
    print(
        f"{prefix}=" + json.dumps(payload, sort_keys=True, default=str),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "workload",
        choices=("inventory", "raft", "siglip", "moondream", "clap", "audio"),
    )
    parser.add_argument("--seconds", type=float, default=12.0)
    args = parser.parse_args()

    _install_capture()
    driver = _load_t363()
    if args.workload == "audio":
        from pb_studio.core import model_loader

        model_loader.enforce_directml_session = (
            directml_adapter.enforce_directml_session
        )
    driver._emit_ready = lambda result: _emit("T411_READY", result)
    driver._emit = lambda result: _emit("T411_RESULT", result)
    try:
        return driver.PROBES[args.workload](max(0.1, args.seconds))
    except Exception as exc:
        result = driver._base(args.workload)
        result.update(ready=False, error=f"{type(exc).__name__}: {exc}")
        _emit("T411_RESULT", result)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
