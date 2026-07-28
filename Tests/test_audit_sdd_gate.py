"""Regression coverage for Epic 00013 SDD/QC truthfulness."""
from __future__ import annotations

from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
FEATURE = WORKSPACE / "specs" / "00013-system-wide-bug-hunting-audit"


def test_completed_tasks_use_canonical_uppercase_checkbox():
    tasks = (FEATURE / "tasks.md").read_text(encoding="utf-8-sig")

    assert "- [x]" not in tasks


def test_current_qc_report_is_not_release_ready():
    report = (FEATURE / "qc-report.md").read_text(encoding="utf-8-sig")

    assert "**FAILED / NOT RELEASE-READY**" in report
    assert "HISTORICAL SNAPSHOT — INVALIDATED" in report


def test_success_markers_are_absent_while_gate_is_failed():
    assert not (FEATURE / ".completed").exists()
    assert not (FEATURE / ".qc-passed").exists()
