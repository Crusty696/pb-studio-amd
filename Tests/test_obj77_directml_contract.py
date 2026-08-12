"""Fail-closed OBJ-77 DirectML session contract tests."""
from __future__ import annotations

import sys
from pathlib import Path

import onnxruntime as ort
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pb_studio.core.directml_adapter import (  # noqa: E402
    DirectMLAdapterError,
    configure_directml_session_options,
    enforce_directml_session,
)


PRODUCTIVE_SESSION_CONSTRUCTORS = (
    ROOT / "src/pb_studio/core/model_loader.py",
    ROOT / "src/pb_studio/video/moondream.py",
    ROOT / "src/pb_studio/video/raft.py",
    ROOT / "src/pb_studio/audio/separator.py",
)


class _SessionOptions:
    def __init__(
        self,
        *,
        execution_mode: ort.ExecutionMode = ort.ExecutionMode.ORT_SEQUENTIAL,
    ) -> None:
        self.enable_mem_pattern = False
        self.enable_cpu_mem_arena = False
        self.execution_mode = execution_mode

    @staticmethod
    def get_session_config_entry(key: str) -> str:
        assert key == "session.disable_cpu_ep_fallback"
        return "1"


class _Session:
    def __init__(self, providers: list[str], options: _SessionOptions) -> None:
        self._providers = providers
        self._options = options
        self.fallback_disabled = False

    def get_session_options(self) -> _SessionOptions:
        return self._options

    def disable_fallback(self) -> None:
        self.fallback_disabled = True

    def get_providers(self) -> list[str]:
        return self._providers


def test_central_directml_options_require_sequential_execution() -> None:
    options = configure_directml_session_options(ort.SessionOptions())
    central_source = (
        ROOT / "src/pb_studio/core/directml_adapter.py"
    ).read_text(encoding="utf-8")

    assert options.enable_mem_pattern is False
    assert options.enable_cpu_mem_arena is False
    assert options.execution_mode == ort.ExecutionMode.ORT_SEQUENTIAL
    assert "execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL" in central_source


def test_enforcer_rejects_parallel_execution_mode() -> None:
    session = _Session(
        ["DmlExecutionProvider"],
        _SessionOptions(execution_mode=ort.ExecutionMode.ORT_PARALLEL),
    )

    with pytest.raises(DirectMLAdapterError, match="ORT_SEQUENTIAL"):
        enforce_directml_session(session)


def test_enforcer_rejects_registered_cpu_execution_provider() -> None:
    session = _Session(
        ["DmlExecutionProvider", "CPUExecutionProvider"],
        _SessionOptions(),
    )

    with pytest.raises(DirectMLAdapterError, match="exclusively DirectML"):
        enforce_directml_session(session)


def test_enforcer_accepts_exact_directml_provider() -> None:
    session = _Session(["DmlExecutionProvider"], _SessionOptions())

    assert enforce_directml_session(session) is session
    assert session.fallback_disabled is True


@pytest.mark.parametrize(
    "path",
    PRODUCTIVE_SESSION_CONSTRUCTORS,
    ids=lambda path: path.name,
)
def test_productive_session_constructors_use_central_options_contract(
    path: Path,
) -> None:
    source = path.read_text(encoding="utf-8")

    assert "configure_directml_session_options" in source
