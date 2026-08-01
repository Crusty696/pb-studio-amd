"""Regression coverage for Epic 00013 SDD/QC truthfulness."""
from __future__ import annotations

from pathlib import Path

from scripts.validate_sdd import validate_feature


WORKSPACE = Path(__file__).resolve().parents[1]
FEATURE = WORKSPACE / "specs" / "00013-system-wide-bug-hunting-audit"


def test_completed_tasks_use_canonical_uppercase_checkbox():
    tasks = (FEATURE / "tasks.md").read_text(encoding="utf-8-sig")

    assert "- [x]" not in tasks


def test_current_feature_workspace_passes_fail_closed_sdd_gate():
    phase = "qc" if (FEATURE / ".qc-passed").exists() else (
        "qc-progress" if (FEATURE / ".completed").exists() else "open"
    )
    report = validate_feature(FEATURE, phase)

    assert report.valid, report.findings
