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
    tasks = (FEATURE / "tasks.md").read_text(encoding="utf-8-sig")
    if (FEATURE / ".qc-passed").exists():
        phase = "release" if "- [X] T415 " in tasks else "qc"
    elif (FEATURE / ".completed").exists():
        phase = "qc-progress"
    else:
        phase = "open"
    report = validate_feature(FEATURE, phase)

    assert report.valid, report.findings


def test_ci_selects_qc_progress_after_qc_execution_starts():
    workflow = (WORKSPACE / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    phase_selection = workflow.split(
        "      - name: Select and validate the active SDD phase", 1
    )[1].split("      - name: Validate lock and security configuration syntax", 1)[0]

    assert "'(?m)^- \\[X\\] T404 '" in phase_selection
    assert '"qc-progress"' in phase_selection
    assert "T415" in phase_selection
    assert '"release"' in phase_selection
    assert phase_selection.index("T404") < phase_selection.index('"qc-progress"')
