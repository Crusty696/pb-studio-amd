"""Regression coverage for Epic 00013 SDD/QC truthfulness."""
from __future__ import annotations

from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
FEATURE = WORKSPACE / "specs" / "00013-system-wide-bug-hunting-audit"


def test_completed_tasks_use_canonical_uppercase_checkbox():
    tasks = (FEATURE / "tasks.md").read_text(encoding="utf-8-sig")

    assert "- [x]" not in tasks


def test_current_qc_report_matches_release_gate():
    report = (FEATURE / "qc-report.md").read_text(encoding="utf-8-sig")

    if (FEATURE / ".qc-passed").exists():
        assert "**PASSED / RELEASE-READY**" in report
    else:
        assert "**FAILED / NOT RELEASE-READY**" in report


def test_implementation_marker_precedes_qc_marker():
    assert (FEATURE / ".completed").exists()
    if (FEATURE / ".qc-passed").exists():
        assert (FEATURE / ".completed").exists()
