"""Guard: launch.ps1 must not kill a backend that is still in its startup phase.

2026-09-30 live finding (T013 GUI reopen): after a large project was saved, the
recovery bootstrap needed ~80 s before the first log line and the 90-s launcher
deadline force-killed the still-starting backend via Stop-ProcessTree.
"""
from __future__ import annotations

import re
from pathlib import Path

LAUNCH = Path(__file__).resolve().parents[1] / "launch.ps1"


def _source() -> str:
    return LAUNCH.read_text(encoding="utf-8-sig")


def test_default_backend_start_wait_is_generous() -> None:
    match = re.search(r"^\$MaxStartupWaitSeconds\s*=\s*(\d+)\s*$", _source(), re.MULTILINE)
    assert match, "default $MaxStartupWaitSeconds assignment missing"
    assert int(match.group(1)) >= 240


def test_backend_start_wait_is_overridable_and_bounded() -> None:
    src = _source()
    assert "PBSTUDIO_BACKEND_START_TIMEOUT" in src
    assert re.search(r"\[Math\]::Min\(1800,\s*\[Math\]::Max\(30,", src)


def test_backend_stop_waits_for_recovery_snapshot() -> None:
    """2026-10-01 00:42: 10-s stop deadline taskkilled the backend mid-snapshot;
    RUNTIME_DIRTY stayed and the next start rolled back."""
    src = _source()
    match = re.search(r"^\$BackendStopWaitSeconds\s*=\s*(\d+)\s*$", src, re.MULTILINE)
    assert match and int(match.group(1)) >= 120
    assert "PBSTUDIO_BACKEND_STOP_TIMEOUT" in src
    assert "Wait-ForBackendShutdown -TimeoutSeconds 10" not in src
