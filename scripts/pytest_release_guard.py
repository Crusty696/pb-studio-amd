"""Pytest plugin enforcing owned, expiring skip exceptions."""

from __future__ import annotations

import fnmatch
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest


_CONFIG: pytest.Config | None = None


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_policy() -> list[dict[str, Any]]:
    configured = os.environ.get("PBSTUDIO_SKIP_ALLOWLIST", "")
    path = (
        Path(configured)
        if configured
        else _repository_root() / "config/pytest-skip-allowlist.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise pytest.UsageError("Unsupported skip allowlist schema")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise pytest.UsageError("Skip allowlist is empty")
    today = date.today()
    nodeids: set[str] = set()
    for entry in entries:
        required = {"nodeid", "owner", "expires_on", "reason"}
        if not required.issubset(entry):
            raise pytest.UsageError(f"Incomplete skip allowlist entry: {entry!r}")
        for field in required:
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise pytest.UsageError(
                    f"Skip allowlist field must be non-empty text: {field}"
                )
        nodeid = entry["nodeid"]
        wildcard_base = nodeid[:-3] if nodeid.endswith("::*") else nodeid
        if (
            not nodeid.startswith("Tests/test_")
            or "**" in nodeid
            or any(character in wildcard_base for character in "*?[")
            or (
                any(character in nodeid for character in "*?[")
                and not nodeid.endswith("::*")
            )
        ):
            raise pytest.UsageError(f"Overbroad or invalid skip nodeid: {nodeid}")
        if nodeid in nodeids:
            raise pytest.UsageError(f"Duplicate skip nodeid: {nodeid}")
        nodeids.add(nodeid)
        try:
            expires = date.fromisoformat(entry["expires_on"])
        except ValueError as exc:
            raise pytest.UsageError(
                f"Invalid skip expiry for {nodeid}: {entry['expires_on']}"
            ) from exc
        if expires < today:
            raise pytest.UsageError(
                f"Expired skip exception: {entry['nodeid']} ({entry['expires_on']})"
            )
    return entries


def pytest_configure(config: pytest.Config) -> None:
    global _CONFIG
    _CONFIG = config
    config._pb_skip_policy = _load_policy()  # type: ignore[attr-defined]
    config._pb_skip_records = []  # type: ignore[attr-defined]
    config._pb_skip_violations = []  # type: ignore[attr-defined]
    try:
        limit = int(os.environ.get("PBSTUDIO_UNAPPROVED_SKIP_LIMIT", "0"))
    except ValueError as exc:
        raise pytest.UsageError("Unapproved skip limit must be an integer") from exc
    if limit < 0:
        raise pytest.UsageError("Unapproved skip limit cannot be negative")
    config._pb_skip_violation_limit = limit  # type: ignore[attr-defined]


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if not report.skipped:
        return
    if _CONFIG is None:
        raise pytest.UsageError("PB Studio skip policy was not configured")
    _record_skip(_CONFIG, report.nodeid, str(report.longrepr))


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not report.skipped:
        return
    if _CONFIG is None:
        raise pytest.UsageError("PB Studio skip policy was not configured")
    _record_skip(_CONFIG, report.nodeid, str(report.longrepr))


def _record_skip(config: pytest.Config, nodeid: str, detail: str) -> None:
    records = config._pb_skip_records  # type: ignore[attr-defined]
    if any(record["nodeid"] == nodeid for record in records):
        return
    policy = config._pb_skip_policy  # type: ignore[attr-defined]
    match = next(
        (entry for entry in policy if fnmatch.fnmatchcase(nodeid, entry["nodeid"])),
        None,
    )
    record = {
        "nodeid": nodeid,
        "allowed": match is not None,
        "owner": match["owner"] if match else None,
        "expires_on": match["expires_on"] if match else None,
        "detail": detail,
    }
    records.append(record)
    if match is None:
        config._pb_skip_violations.append(nodeid)  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    records = config._pb_skip_records  # type: ignore[attr-defined]
    violations = config._pb_skip_violations  # type: ignore[attr-defined]
    report_value = os.environ.get("PBSTUDIO_SKIP_REPORT", "")
    if report_value:
        report_path = Path(report_value)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skips": records,
                    "unapproved": sorted(violations),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    limit = config._pb_skip_violation_limit  # type: ignore[attr-defined]
    if len(violations) > limit and exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: pytest.ExitCode,
    config: pytest.Config,
) -> None:
    violations = config._pb_skip_violations  # type: ignore[attr-defined]
    if violations:
        terminalreporter.write_sep("=", "UNAPPROVED SKIPS")
        for nodeid in sorted(violations):
            terminalreporter.write_line(nodeid, red=True)
