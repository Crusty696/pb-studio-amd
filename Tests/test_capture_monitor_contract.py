"""Session-bound capture and sanitization contracts for OBJ-76 T006-T008."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONITOR = ROOT / "scripts" / "diagnostics" / "capture_monitor.ps1"
EXPORT = ROOT / "scripts" / "diagnostics" / "export_capture.ps1"
POWERSHELL = "powershell.exe"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _dummy_process(milliseconds: int, exit_code: int = 0) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Start-Sleep -Milliseconds {milliseconds}; exit {exit_code}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )


def _start_monitor(
    workspace: Path,
    source_config: Path,
    output: Path,
    supervisor: subprocess.Popen[str],
    backend: subprocess.Popen[str],
    wpf: subprocess.Popen[str],
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(MONITOR),
            "-RepoRoot",
            str(workspace),
            "-OutputPath",
            str(output),
            "-SessionId",
            "obj76-test",
            "-CommitSha",
            "abcdef0",
            "-SupervisorPid",
            str(supervisor.pid),
            "-BackendPid",
            str(backend.pid),
            "-WpfPid",
            str(wpf.pid),
            "-SourceConfigPath",
            str(source_config),
            "-PollMilliseconds",
            "50",
            "-ExitGracePolls",
            "2",
        ],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _source_config(workspace: Path, source: Path, start_offset: int) -> Path:
    config = workspace / "sources.json"
    config.write_text(
        json.dumps(
            [
                {
                    "tag": "TEST_SOURCE",
                    "path": str(source),
                    "session_owned": False,
                    "start_offset": start_offset,
                }
            ]
        ),
        encoding="utf-8",
    )
    return config


def _wait_for_event(path: Path, event: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and f'"event":"{event}"' in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return
        time.sleep(0.05)
    raise AssertionError(f"capture event did not appear: {event}")


def _finish_processes(*processes: subprocess.Popen[str]) -> None:
    for process in processes:
        if process.poll() is None:
            process.kill()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def test_capture_rejects_zero_supervisor_pid(tmp_path: Path):
    output = tmp_path / "raw.jsonl"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(MONITOR),
            "-RepoRoot",
            str(tmp_path),
            "-OutputPath",
            str(output),
            "-SessionId",
            "obj76-test",
            "-CommitSha",
            "abcdef0",
            "-SupervisorPid",
            "0",
            "-BackendPid",
            "1",
            "-WpfPid",
            "2",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        creationflags=CREATE_NO_WINDOW,
    )

    assert result.returncode != 0
    assert not output.exists()


def test_capture_is_session_bounded_and_export_is_sanitized(tmp_path: Path):
    source = tmp_path / "application.log"
    source.write_text("stale previous session\n", encoding="utf-8")
    start_offset = source.stat().st_size
    config = _source_config(tmp_path, source, start_offset)
    raw = tmp_path / "raw.jsonl"
    exported = tmp_path / "export.jsonl"
    supervisor = _dummy_process(1600, 0)
    backend = _dummy_process(1400, 7)
    wpf = _dummy_process(1200, 0)
    monitor = _start_monitor(tmp_path, config, raw, supervisor, backend, wpf)
    secret = "Q" * 44
    try:
        _wait_for_event(raw, "monitor_started")
        with source.open("a", encoding="utf-8") as handle:
            handle.write(
                "fresh C:\\Users\\david\\private.mov "
                f"owner_capability={secret} nonce=health-proof-123 "
                "api_key=top-secret\n"
            )
        stdout, stderr = monitor.communicate(timeout=8)
        assert monitor.returncode == 0, f"{stdout}\n{stderr}"
    finally:
        _finish_processes(monitor, supervisor, backend, wpf)

    records = _records(raw)
    assert {record["session_id"] for record in records} == {"obj76-test"}
    assert [record["sequence"] for record in records] == list(
        range(1, len(records) + 1)
    )
    assert "stale previous session" not in raw.read_text(encoding="utf-8")
    assert sum(record["event"] == "monitor_stopped" for record in records) == 1
    exits = {
        record["data"]["role"]: record["data"]["exit_code"]
        for record in records
        if record["event"] == "process_exited"
    }
    assert exits == {"supervisor": 0, "backend": 7, "wpf": 0}

    env = os.environ.copy()
    env["PBSTUDIO_OWNER_CAPABILITY"] = secret
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(EXPORT),
            "-InputPath",
            str(raw),
            "-OutputPath",
            str(exported),
            "-PrivateRoots",
            str(tmp_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
    text = exported.read_text(encoding="utf-8")
    assert secret not in text
    assert "health-proof-123" not in text
    assert "top-secret" not in text
    assert not re.search(r"(?i)[A-Z]:\\\\Users\\\\", text)
    assert {record["session_id"] for record in _records(exported)} == {"obj76-test"}


def test_capture_detects_source_rotation_without_replaying_old_content(tmp_path: Path):
    source = tmp_path / "rotating.log"
    stale = "old-generation-stale\n"
    source.write_text(stale, encoding="utf-8")
    config = _source_config(tmp_path, source, source.stat().st_size)
    raw = tmp_path / "rotation.jsonl"
    supervisor = _dummy_process(2400)
    backend = _dummy_process(2200)
    wpf = _dummy_process(2000)
    monitor = _start_monitor(tmp_path, config, raw, supervisor, backend, wpf)
    try:
        _wait_for_event(raw, "monitor_started")
        with source.open("a", encoding="utf-8") as handle:
            handle.write("first-generation-new-content-that-is-long\n")
        time.sleep(0.3)
        source.write_text("rotated-new\n", encoding="utf-8")
        stdout, stderr = monitor.communicate(timeout=8)
        assert monitor.returncode == 0, f"{stdout}\n{stderr}"
    finally:
        _finish_processes(monitor, supervisor, backend, wpf)

    records = _records(raw)
    assert any(record["event"] == "source_rotated" for record in records)
    text = raw.read_text(encoding="utf-8")
    assert "old-generation-stale" not in text
    assert "rotated-new" in text
    assert records[-1]["event"] == "monitor_stopped"
    assert records[-1]["data"]["final_drop_count"] >= 1


def test_capture_survives_an_abrupt_owned_process_exit(tmp_path: Path):
    source = tmp_path / "abrupt.log"
    source.write_text("", encoding="utf-8")
    config = _source_config(tmp_path, source, 0)
    raw = tmp_path / "abrupt.jsonl"
    supervisor = _dummy_process(1800)
    backend = _dummy_process(5000)
    wpf = _dummy_process(1600)
    monitor = _start_monitor(tmp_path, config, raw, supervisor, backend, wpf)
    try:
        _wait_for_event(raw, "monitor_started")
        backend.kill()
        backend.wait(timeout=5)
        stdout, stderr = monitor.communicate(timeout=8)
        assert monitor.returncode == 0, f"{stdout}\n{stderr}"
    finally:
        _finish_processes(monitor, supervisor, backend, wpf)

    records = _records(raw)
    backend_exit = next(
        record
        for record in records
        if record["event"] == "process_exited"
        and record["data"]["role"] == "backend"
    )
    assert backend_exit["data"]["exit_code"] != 0
    assert records[-1]["event"] == "monitor_stopped"
    assert sum(record["event"] == "monitor_stopped" for record in records) == 1


def test_export_fails_closed_for_mixed_or_unfinished_sessions(tmp_path: Path):
    raw = tmp_path / "invalid.jsonl"
    exported = tmp_path / "export.jsonl"
    raw.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "session_id": "session-a",
                        "sequence": 1,
                        "event": "monitor_started",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "session_id": "session-b",
                        "sequence": 2,
                        "event": "monitor_stopped",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(EXPORT),
            "-InputPath",
            str(raw),
            "-OutputPath",
            str(exported),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )

    assert result.returncode != 0
    assert not exported.exists()
