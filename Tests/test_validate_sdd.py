"""Negative governance fixtures for the fail-closed SDD validator."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts.validate_sdd import (
    ARCHIVE_SOURCE_MAP,
    _expected_requirement_registry,
    _parse_tasks,
    _task_digest,
    main,
    sha256_file,
    validate_feature,
)


def _git(feature: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(feature), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write_manifest(feature: Path) -> None:
    history = feature / "history"
    source_commit = _git(feature, "rev-parse", "HEAD")
    repo_root = Path(_git(feature, "rev-parse", "--show-toplevel"))
    feature_relative = feature.relative_to(repo_root)
    files = []
    for name, source_path in ARCHIVE_SOURCE_MAP.items():
        path = history / name
        git_blob = (
            _git(
                feature,
                "rev-parse",
                f"{source_commit}:{(feature_relative / source_path).as_posix()}",
            )
            if name != "requirement-registry-through-obj71.md"
            else None
        )
        files.append(
            {
                "path": name,
                "source_path": source_path,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "git_blob": git_blob,
            }
        )
    (history / "archive-manifest-obj71.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "objective": "OBJ-71",
                "source_commit": source_commit,
                "files": files,
            }
        ),
        encoding="utf-8",
    )


def _tasks(feature: Path):
    findings = []
    result = _parse_tasks(feature / "tasks.md", findings)
    assert not findings
    return result


def _refresh_archive_anchor(feature: Path) -> None:
    spec_path = feature / "spec.md"
    manifest = feature / "history" / "archive-manifest-obj71.json"
    text = spec_path.read_text(encoding="utf-8")
    updated = re.sub(
        r"(`history/archive-manifest-obj71\.json`\n"
        r"  - SHA-256: `)[0-9a-f]{64}(`)",
        rf"\g<1>{sha256_file(manifest)}\g<2>",
        text,
    )
    assert updated != text
    spec_path.write_text(updated, encoding="utf-8")


def _write_completed_marker(feature: Path) -> None:
    evidence = feature / "evidence" / "implementation.json"
    evidence.parent.mkdir()
    receipt = feature / "evidence" / "T403.md"
    receipt.write_text("T403 review PASS\n", encoding="utf-8")
    _git(feature, "add", "tasks.md", "evidence/T403.md")
    _git(feature, "commit", "-m", "implementation gate source")
    commit_sha = _git(feature, "rev-parse", "HEAD")
    evidence_payload = {
        "schema_version": 1,
        "objective": "OBJ-72",
        "task_range": "T370-T403",
        "receipts": [
            {
                "task_id": f"T{identifier:03d}",
                "path": "evidence/T403.md",
                "sha256": sha256_file(receipt),
            }
            for identifier in range(370, 404)
        ],
        "artifact_hashes": [
            {"path": "tasks.md", "sha256": sha256_file(feature / "tasks.md")}
        ],
        "review_status": "PASS",
        "open_blockers": [],
        "commit_sha": commit_sha,
    }
    evidence.write_text(json.dumps(evidence_payload), encoding="utf-8")
    tasks = _tasks(feature)
    marker = {
        "schema_version": 1,
        "objective": "OBJ-72",
        "phase": "implementation",
        "task_range": "T370-T403",
        "task_digest_sha256": _task_digest(tasks, 370, 403),
        "evidence_manifest": "evidence/implementation.json",
        "evidence_manifest_sha256": sha256_file(evidence),
        "commit_sha": commit_sha,
    }
    (feature / ".completed").write_text(json.dumps(marker), encoding="utf-8")


def _write_qc_marker(feature: Path) -> None:
    evidence = feature / "evidence" / "qc.json"
    evidence.parent.mkdir(exist_ok=True)
    receipt = feature / "evidence" / "T414.md"
    receipt.write_text("T414 QC PASS\n", encoding="utf-8")
    report = feature / "qc-report.md"
    report.write_text(
        "# QC\n\n"
        "## Authoritative OBJ-72 Gate — 2026-07-31\n\n"
        "- **Overall result:** **PASSED / RELEASE-READY**.\n",
        encoding="utf-8",
    )
    gate_sources = ["tasks.md", "qc-report.md", "evidence/T414.md"]
    if (feature / ".completed").is_file():
        gate_sources.append(".completed")
    _git(feature, "add", *gate_sources)
    _git(feature, "commit", "-m", "qc gate source")
    commit_sha = _git(feature, "rev-parse", "HEAD")
    evidence_payload = {
        "schema_version": 1,
        "objective": "OBJ-72",
        "task_range": "T370-T414",
        "receipts": [
            {
                "task_id": f"T{identifier:03d}",
                "path": "evidence/T414.md",
                "sha256": sha256_file(receipt),
            }
            for identifier in range(370, 415)
        ],
        "artifact_hashes": [
            {"path": "tasks.md", "sha256": sha256_file(feature / "tasks.md")},
            {
                "path": "qc-report.md",
                "sha256": sha256_file(feature / "qc-report.md"),
            },
            {
                "path": ".completed",
                "sha256": (
                    sha256_file(feature / ".completed")
                    if (feature / ".completed").is_file()
                    else "0" * 64
                ),
            },
        ],
        "review_status": "PASS",
        "open_blockers": [],
        "commit_sha": commit_sha,
    }
    evidence.write_text(json.dumps(evidence_payload), encoding="utf-8")
    tasks = _tasks(feature)
    marker = {
        "schema_version": 1,
        "objective": "OBJ-72",
        "phase": "qc",
        "task_range": "T370-T414",
        "task_digest_sha256": _task_digest(tasks, 370, 414),
        "completed_marker_sha256": (
            sha256_file(feature / ".completed")
            if (feature / ".completed").exists()
            else "0" * 64
        ),
        "qc_report_sha256": sha256_file(feature / "qc-report.md"),
        "evidence_manifest": "evidence/qc.json",
        "evidence_manifest_sha256": sha256_file(evidence),
        "commit_sha": commit_sha,
    }
    (feature / ".qc-passed").write_text(json.dumps(marker), encoding="utf-8")


@pytest.fixture
def valid_feature(tmp_path: Path) -> Path:
    feature = tmp_path / "specs" / "00001-example"
    history = feature / "history"
    checklist = feature / "checklists"
    history.mkdir(parents=True)
    checklist.mkdir()
    (feature / "spec.md").write_text(
        "\n".join(
            [
                "# Spec",
                "**OBJ-72:** Example objective.",
                "**OR-335:** Governance.",
                "**FR-337:** Runtime behavior.",
                "**RR-237:** Recovery.",
                "**TR-346:** Validation.",
                "**SC-076 [OBJ-72]:** T370–T415 pass.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (feature / "plan.md").write_text("# Plan\n", encoding="utf-8")
    task_lines = [
        f"- [ ] T{identifier:03d} [OBJ-72] {{(OR-335)}} "
        f"Validate `file-{identifier}.txt` [Z-DOCS]"
        for identifier in range(370, 416)
    ]
    (feature / "tasks.md").write_text(
        "# Tasks\n\n" + "\n".join(task_lines) + "\n",
        encoding="utf-8",
    )
    (checklist / "requirements.md").write_text(
        "# Checklist\n\n- [X] Requirements are testable.\n",
        encoding="utf-8",
    )
    (feature / "qc-report.md").write_text(
        "# QC\n\n"
        "## Authoritative OBJ-72 Gate — 2026-07-31\n\n"
        "- **Overall result:** **REOPENED / NOT RELEASE-READY**.\n",
        encoding="utf-8",
    )
    (feature / ".completed").write_text("historical completed\n", encoding="utf-8")
    (feature / ".qc-passed").write_text("historical qc\n", encoding="utf-8")
    (history / "spec-through-obj71-2026-07-30.md").write_bytes(
        (feature / "spec.md").read_bytes()
    )
    (history / "plan-through-obj71-2026-07-30.md").write_bytes(
        (feature / "plan.md").read_bytes()
    )
    (history / "tasks-through-t369.md").write_bytes(
        (feature / "tasks.md").read_bytes()
    )
    (history / "qc-report-through-obj71-2026-07-30.md").write_bytes(
        (feature / "qc-report.md").read_bytes()
    )
    (history / "completed-through-obj71.txt").write_bytes(
        (feature / ".completed").read_bytes()
    )
    (history / "qc-passed-through-obj71.txt").write_bytes(
        (feature / ".qc-passed").read_bytes()
    )
    _git(feature, "init")
    _git(feature, "config", "user.email", "sdd-test@example.invalid")
    _git(feature, "config", "user.name", "SDD Test")
    _git(feature, "config", "core.autocrlf", "false")
    _git(feature, "add", ".")
    _git(feature, "commit", "-m", "fixture baseline")
    (feature / ".completed").unlink()
    (feature / ".qc-passed").unlink()
    source_commit = _git(feature, "rev-parse", "HEAD")
    (history / "requirement-registry-through-obj71.md").write_text(
        _expected_requirement_registry(
            source_commit,
            sha256_file(history / "spec-through-obj71-2026-07-30.md"),
            sha256_file(history / "tasks-through-t369.md"),
        ),
        encoding="utf-8",
    )
    _write_manifest(feature)
    spec_path = feature / "spec.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + "- `history/archive-manifest-obj71.json`\n"
        + f"  - SHA-256: `{sha256_file(history / 'archive-manifest-obj71.json')}`\n",
        encoding="utf-8",
    )
    return feature


def _codes(feature: Path, phase: str = "open") -> set[str]:
    return {finding.code for finding in validate_feature(feature, phase).findings}


def test_valid_open_workspace_passes(valid_feature: Path):
    report = validate_feature(valid_feature, "open")

    assert report.valid, report.findings


def test_cli_json_and_exitcodes(valid_feature: Path, capsys):
    assert main(["--feature", str(valid_feature), "--phase", "open", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["findings"] == []


def test_rejects_spec_over_10240_bytes(valid_feature: Path):
    (valid_feature / "spec.md").write_text("x" * 10_241, encoding="utf-8")

    assert "SPEC_SIZE" in _codes(valid_feature)


def test_rejects_noncanonical_task_box(valid_feature: Path):
    path = valid_feature / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("- [ ] T370", "- [x] T370"),
        encoding="utf-8",
    )

    assert "TASK_FORMAT" in _codes(valid_feature)


def test_rejects_short_task_candidate(valid_feature: Path):
    path = valid_feature / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "- [ ] T41 malformed\n",
        encoding="utf-8",
    )

    assert "TASK_FORMAT" in _codes(valid_feature)


def test_rejects_missing_task_id(valid_feature: Path):
    path = valid_feature / "tasks.md"
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith("- [ ] T400 ")
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert "TASK_ID_SET" in _codes(valid_feature)


def test_rejects_duplicate_task_id(valid_feature: Path):
    path = valid_feature / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "- [ ] T401 ",
            "- [ ] T400 ",
        ),
        encoding="utf-8",
    )

    assert "TASK_ID_DUPLICATE" in _codes(valid_feature)


def test_rejects_unknown_requirement(valid_feature: Path):
    path = valid_feature / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "{(OR-335)} Validate `file-370.txt`",
            "{(OR-999)} Validate `file-370.txt`",
        ),
        encoding="utf-8",
    )

    assert "TASK_REQUIREMENT_UNKNOWN" in _codes(valid_feature)


def test_rejects_task_without_repository_path(valid_feature: Path):
    path = valid_feature / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Validate `file-370.txt`",
            "Validate file-370.txt",
        ),
        encoding="utf-8",
    )

    assert "TASK_PATH_MISSING" in _codes(valid_feature)


def test_rejects_open_checklist(valid_feature: Path):
    path = valid_feature / "checklists" / "requirements.md"
    path.write_text("# Checklist\n\n- [ ] Still open.\n", encoding="utf-8")

    assert "CHECKLIST_OPEN" in _codes(valid_feature)


def test_rejects_nested_open_checklist(valid_feature: Path):
    nested = valid_feature / "checklists" / "nested"
    nested.mkdir()
    (nested / "open.md").write_text("- [ ] Nested open.\n", encoding="utf-8")

    assert "CHECKLIST_OPEN" in _codes(valid_feature)


def test_rejects_bad_archive_hash(valid_feature: Path):
    path = valid_feature / "history" / "spec-through-obj71-2026-07-30.md"
    path.write_text("changed\n", encoding="utf-8")

    assert "ARCHIVE_HASH" in _codes(valid_feature)


def test_rejects_self_signed_archive_change(valid_feature: Path):
    history = valid_feature / "history"
    archived = history / "spec-through-obj71-2026-07-30.md"
    archived.write_text("changed\n", encoding="utf-8")
    _write_manifest(valid_feature)

    assert "ARCHIVE_ANCHOR" in _codes(valid_feature)


def test_rejects_archive_path_escape(valid_feature: Path):
    manifest_path = valid_feature / "history" / "archive-manifest-obj71.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "../outside.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_archive_anchor(valid_feature)

    assert "ARCHIVE_PATH_ESCAPE" in _codes(valid_feature)


def test_rejects_archive_source_path_substitution(valid_feature: Path):
    manifest_path = valid_feature / "history" / "archive-manifest-obj71.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["source_path"] = "tasks.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_archive_anchor(valid_feature)

    assert "ARCHIVE_SOURCE_PATH" in _codes(valid_feature)


def test_rejects_premature_completed_marker(valid_feature: Path):
    _write_completed_marker(valid_feature)

    assert "COMPLETED_TOO_EARLY" in _codes(valid_feature)


def test_rejects_short_completed_range(valid_feature: Path):
    _write_completed_marker(valid_feature)
    marker_path = valid_feature / ".completed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["task_range"] = "T370-T370"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "COMPLETED_RANGE" in _codes(valid_feature)


def test_rejects_bad_completed_task_digest(valid_feature: Path):
    _write_completed_marker(valid_feature)
    marker_path = valid_feature / ".completed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["task_digest_sha256"] = "0" * 64
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "COMPLETED_TASK_DIGEST" in _codes(valid_feature)


def test_rejects_incomplete_evidence_schema(valid_feature: Path):
    _write_completed_marker(valid_feature)
    evidence = valid_feature / "evidence" / "implementation.json"
    evidence.write_text('{"valid": true}\n', encoding="utf-8")
    marker_path = valid_feature / ".completed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["evidence_manifest_sha256"] = sha256_file(evidence)
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "COMPLETED_EVIDENCE_FIELDS" in _codes(valid_feature)


def test_rejects_incomplete_receipt_coverage(valid_feature: Path):
    _write_completed_marker(valid_feature)
    evidence = valid_feature / "evidence" / "implementation.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["receipts"] = payload["receipts"][:1]
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    marker_path = valid_feature / ".completed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["evidence_manifest_sha256"] = sha256_file(evidence)
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "COMPLETED_RECEIPT_COVERAGE" in _codes(valid_feature)


def test_rejects_receipt_not_bound_to_marker_commit(valid_feature: Path):
    _write_completed_marker(valid_feature)
    receipt = valid_feature / "evidence" / "T403.md"
    receipt.write_text("mutated after gate commit\n", encoding="utf-8")
    evidence = valid_feature / "evidence" / "implementation.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    for entry in payload["receipts"]:
        entry["sha256"] = sha256_file(receipt)
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    marker_path = valid_feature / ".completed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["evidence_manifest_sha256"] = sha256_file(evidence)
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "COMPLETED_RECEIPT_COMMIT" in _codes(valid_feature)


def test_rejects_qc_without_completed(valid_feature: Path):
    _write_qc_marker(valid_feature)

    assert "QC_BEFORE_IMPLEMENTATION" in _codes(valid_feature)


def test_rejects_bad_qc_report_digest(valid_feature: Path):
    _write_completed_marker(valid_feature)
    _write_qc_marker(valid_feature)
    marker_path = valid_feature / ".qc-passed"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["qc_report_sha256"] = "0" * 64
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert "QC_REPORT_DIGEST" in _codes(valid_feature)


def test_accepts_qc_commit_through_direct_pr_merge_after_main_advances(
    valid_feature: Path,
):
    tasks_path = valid_feature / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [X]"),
        encoding="utf-8",
    )
    _write_completed_marker(valid_feature)
    _write_qc_marker(valid_feature)
    _git(valid_feature, "add", "evidence/qc.json", ".qc-passed")
    _git(valid_feature, "commit", "-m", "publish qc marker")
    pr_head = _git(valid_feature, "rev-parse", "HEAD")
    qc_commit = _git(valid_feature, "rev-parse", "HEAD^")
    base = _git(valid_feature, "rev-parse", f"{qc_commit}^")
    _git(valid_feature, "branch", "pr-head", pr_head)
    _git(valid_feature, "switch", "-c", "protected-main", base)
    (valid_feature / "main-advanced.txt").write_text("advanced\n", encoding="utf-8")
    _git(valid_feature, "add", "main-advanced.txt")
    _git(valid_feature, "commit", "-m", "advance protected main")
    _git(valid_feature, "merge", "--no-ff", "pr-head", "-m", "merge release PR")

    report = validate_feature(valid_feature, "release")

    assert report.valid, report.findings


def test_rejects_qc_commit_two_non_merge_commits_behind(valid_feature: Path):
    tasks_path = valid_feature / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [X]"),
        encoding="utf-8",
    )
    _write_completed_marker(valid_feature)
    _write_qc_marker(valid_feature)
    _git(valid_feature, "add", "evidence/qc.json", ".qc-passed")
    _git(valid_feature, "commit", "-m", "publish qc marker")
    (valid_feature / "after-marker.txt").write_text("later\n", encoding="utf-8")
    _git(valid_feature, "add", "after-marker.txt")
    _git(valid_feature, "commit", "-m", "unrelated later commit")

    assert "QC_GATE_COMMIT" in _codes(valid_feature, "release")


def test_rejects_historical_qc_status_before_current(valid_feature: Path):
    (valid_feature / "qc-report.md").write_text(
        "# QC\n\n"
        "## Authoritative OBJ-71 Gate — 2026-07-30\n\n"
        "- **Overall result:** **PASSED / RELEASE-READY**.\n\n"
        "## Authoritative OBJ-72 Gate — 2026-07-31\n\n"
        "- **Overall result:** **REOPENED / NOT RELEASE-READY**.\n",
        encoding="utf-8",
    )

    assert "QC_STATUS_ORDER" in _codes(valid_feature)


def test_rejects_unknown_direct_api_phase(valid_feature: Path):
    assert "PHASE_UNKNOWN" in _codes(valid_feature, "unknown")
