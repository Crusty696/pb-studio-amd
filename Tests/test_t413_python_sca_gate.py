from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import security_gate


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "Tests" / "security" / "fixtures"


def _report(vulnerable: bool = False) -> dict[str, object]:
    vulns: list[dict[str, object]] = []
    if vulnerable:
        vulns.append(
            {
                "id": "PYSEC-2021-108",
                "aliases": ["CVE-2021-33503", "CVE-2021-33503"],
                "fix_versions": ["1.26.6"],
            }
        )
    return {
        "dependencies": [
            {"name": "urllib3", "version": "1.26.5", "vulns": vulns}
        ],
        "fixes": [],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(
    report: Path,
    lock: Path,
    receipt: Path,
    *,
    expect_clean: bool,
    exceptions: Path | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        report=report,
        lock=lock,
        provider="osv",
        scanner_version="unverified",
        scanner_version_status="unverified",
        invocation_kind="github-action",
        action_revision="pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266",
        local_source=None,
        local_command=None,
        receipt=receipt,
        expect_clean=expect_clean,
        expect_package="urllib3" if not expect_clean else None,
        expect_version="1.26.5" if not expect_clean else None,
        minimum_dependencies=1,
        exceptions=exceptions,
    )


def test_python_sca_lock_rejects_missing_or_malformed_hashes(tmp_path: Path) -> None:
    missing = tmp_path / "missing-hash.txt"
    missing.write_text("urllib3==1.26.5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 hashes"):
        security_gate._parse_hashed_lock(missing)
    with pytest.raises(ValueError, match="SHA-256 hashes"):
        security_gate._parse_hashed_lock(FIXTURES / "requirements-invalid-hash.txt")
    assert security_gate._parse_hashed_lock(
        FIXTURES / "requirements-wrong-hash.txt"
    ) == [{"name": "urllib3", "version": "1.26.5"}]
    assert (
        security_gate._python_lock(
            SimpleNamespace(
                lock=FIXTURES / "requirements-invalid-hash.txt",
                expect_hash_failure=True,
            )
        )
        == 0
    )


def test_python_sca_hash_fixtures_are_explicit_and_distinct() -> None:
    malformed = (FIXTURES / "requirements-invalid-hash.txt").read_text(
        encoding="utf-8"
    )
    wrong = (FIXTURES / "requirements-wrong-hash.txt").read_text(encoding="utf-8")
    vulnerable = (FIXTURES / "requirements-vulnerable.txt").read_text(
        encoding="utf-8"
    )

    assert "sha256:not-a-valid-sha256" in malformed
    assert "sha256:" + "0" * 64 in wrong
    assert (
        "sha256:753a0374df26658f99d826cfe40394a686d05985786d946fbe4165b5148f5a7c"
        in vulnerable
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BIT-pillow-2026-55379", "BIT-PILLOW-2026-55379"),
        ("X41-2026-002", "X41-2026-002"),
        ("GHSA-65pc-fj4g-8rjx", "GHSA-65PC-FJ4G-8RJX"),
    ],
)
def test_python_sca_accepts_supported_osv_alias_grammars(
    raw: str,
    expected: str,
) -> None:
    assert security_gate._canonical_alias(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "BIT/pillow-2026-55379",
        "BIT-pillow-2026-",
        "BIT--pillow-2026-55379",
        "UNKNOWN-pillow-2026-55379",
        "BIT-pillow_2026-55379",
    ],
)
def test_python_sca_rejects_unsafe_or_malformed_aliases(raw: str) -> None:
    with pytest.raises(ValueError, match="Invalid vulnerability alias"):
        security_gate._canonical_alias(raw)


def test_python_sca_workflow_keeps_hash_and_scanner_identity_contracts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )

    assert "PIP_AUDIT_ACTION_REVISION" in workflow
    assert "PIP_AUDIT_SCANNER_VERSION: unverified" in workflow
    assert "TODO(release-blocker): Pin and attest the pip-audit scanner version" in workflow
    assert "--tool-version" not in workflow
    assert workflow.count("--invocation-kind github-action") == 2
    assert "requirements-invalid-hash.txt" not in workflow
    assert "requirements-wrong-hash.txt" in workflow
    assert "python -m pip download --require-hashes --no-deps" in workflow
    assert "id: production_hash_validation" in workflow
    assert "--dest artifacts/security/python-sca-production-hashes" in workflow
    assert "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE" in workflow
    assert "Expected sha256 $expectedHash" in workflow
    assert "Got\\s+$actualHash" in workflow
    assert "steps.wrong_hash_validation.outcome" in workflow
    assert "steps.production_hash_validation.outcome" in workflow
    assert "steps.production_audit.outcome" in workflow
    production_audit = workflow.split("      - name: Audit production lock", 1)[1].split(
        "      - name: Validate production Python report", 1
    )[0]
    production_validation = workflow.split(
        "      - name: Validate production Python report", 1
    )[1].split("      - name: Verify production Python lock hashes", 1)[0]
    assert "continue-on-error: true" in production_audit
    assert "continue-on-error" not in production_validation


def test_python_sca_hashed_vulnerable_fixture_uses_osv_report_path(
    tmp_path: Path,
) -> None:
    report = tmp_path / "osv-report.json"
    receipt = tmp_path / "validated.json"
    _write_json(report, _report(vulnerable=True))

    assert (
        security_gate._pip_audit_report(
            _args(
                report,
                FIXTURES / "requirements-vulnerable.txt",
                receipt,
                expect_clean=False,
            )
        )
        == 0
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["provider"] == "osv"
    assert payload["scanner"] == {
        "name": "pip-audit",
        "version": "unverified",
        "version_status": "unverified",
    }
    assert payload["invocation"] == {
        "kind": "github-action",
        "action": {
            "name": "pypa/gh-action-pip-audit",
            "revision": "pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266",
        },
    }
    assert "action" not in payload
    assert payload["lock"]["sha256"] == hashlib.sha256(
        (FIXTURES / "requirements-vulnerable.txt").read_bytes()
    ).hexdigest()
    assert payload["lock"]["packages"] == [
        {"name": "urllib3", "version": "1.26.5"}
    ]
    assert payload["vulnerabilities"] == [
        {
            "package": "urllib3",
            "version": "1.26.5",
            "aliases": ["CVE-2021-33503", "PYSEC-2021-108"],
        }
    ]


def test_python_sca_local_cli_records_verified_scanner_without_action_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = tmp_path / "local-report.json"
    receipt = tmp_path / "local-receipt.json"
    _write_json(report, _report())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "security_gate.py",
            "pip-audit-report",
            "--report",
            str(report),
            "--lock",
            str(FIXTURES / "requirements-vulnerable.txt"),
            "--provider",
            "osv",
            "--scanner-version",
            "2.10.1",
            "--scanner-version-status",
            "verified",
            "--invocation-kind",
            "local",
            "--local-source",
            "uvx",
            "--local-command",
            "uvx pip-audit==2.10.1 --requirement requirements.txt --format=json",
            "--receipt",
            str(receipt),
            "--expect-clean",
        ],
    )

    assert security_gate.main() == 0

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["scanner"] == {
        "name": "pip-audit",
        "version": "2.10.1",
        "version_status": "verified",
    }
    assert payload["invocation"] == {
        "kind": "local",
        "source": "uvx",
        "command": "uvx pip-audit==2.10.1 --requirement requirements.txt --format=json",
    }
    assert "action" not in payload


@pytest.mark.parametrize(
    "args",
    [
        SimpleNamespace(
            scanner_version="2.10.1",
            scanner_version_status="verified",
            invocation_kind="github-action",
            action_revision=None,
            local_source=None,
            local_command=None,
        ),
        SimpleNamespace(
            scanner_version="2.10.1",
            scanner_version_status="verified",
            invocation_kind="local",
            action_revision="pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266",
            local_source="uvx",
            local_command="uvx pip-audit==2.10.1",
        ),
        SimpleNamespace(
            scanner_version="2.10.1",
            scanner_version_status="verified",
            invocation_kind="local",
            action_revision=None,
            local_source=None,
            local_command="uvx pip-audit==2.10.1",
        ),
    ],
)
def test_python_sca_rejects_mixed_or_missing_provenance(
    args: SimpleNamespace,
) -> None:
    with pytest.raises(ValueError):
        security_gate._scanner_identity(args)


@pytest.mark.parametrize(
    ("offset_days", "accepted"),
    [(0, True), (30, True), (-1, False), (31, False)],
)
def test_python_sca_exception_expiry_is_limited_to_thirty_days(
    tmp_path: Path,
    offset_days: int,
    accepted: bool,
) -> None:
    exceptions = tmp_path / "exceptions.json"
    _write_json(
        exceptions,
        {
            "schema_version": 1,
            "entries": [
                {
                    "id": "SCA-EXPIRY-TEST",
                    "package": "urllib3",
                    "version": "1.26.5",
                    "alias": "CVE-2021-33503",
                    "owner": "security@example.test",
                    "expires_on": (date.today() + timedelta(days=offset_days)).isoformat(),
                    "reason": "Unit-test-only expiry validation",
                }
            ],
        },
    )

    if accepted:
        assert len(security_gate._load_python_sca_exceptions(exceptions)) == 1
    else:
        with pytest.raises(ValueError, match="within 30 days"):
            security_gate._load_python_sca_exceptions(exceptions)


def test_python_sca_rejects_report_package_set_mismatch(tmp_path: Path) -> None:
    report = _report()
    report["dependencies"].append(
        {"name": "extra-package", "version": "1.0", "vulns": []}
    )
    report_path = tmp_path / "report.json"
    _write_json(report_path, report)

    with pytest.raises(ValueError, match="does not exactly match the lock"):
        security_gate._pip_audit_report(
            _args(
                report_path,
                FIXTURES / "requirements-vulnerable.txt",
                tmp_path / "receipt.json",
                expect_clean=True,
            )
        )


def test_python_sca_exception_requires_exact_alias_binding(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    exceptions = tmp_path / "exceptions.json"
    _write_json(report, _report(vulnerable=True))
    _write_json(
        exceptions,
        {
            "schema_version": 1,
            "entries": [
                {
                    "id": "SCA-TEST-001",
                    "package": "urllib3",
                    "version": "1.26.5",
                    "alias": "CVE-2021-33503",
                    "owner": "security@example.test",
                    "expires_on": (date.today() + timedelta(days=30)).isoformat(),
                    "reason": "Unit-test-only exception binding proof",
                }
            ],
        },
    )

    assert (
        security_gate._pip_audit_report(
            _args(
                report,
                FIXTURES / "requirements-vulnerable.txt",
                tmp_path / "receipt.json",
                expect_clean=True,
                exceptions=exceptions,
            )
        )
        == 0
    )


def test_python_sca_merges_transitive_alias_overlap_into_one_component(
    tmp_path: Path,
) -> None:
    report = _report()
    report["dependencies"][0]["vulns"] = [
        {
            "id": "CVE-2021-0001",
            "aliases": ["GHSA-aaaa-bbbb-cccc"],
            "fix_versions": [],
        },
        {
            "id": "PYSEC-2021-1",
            "aliases": ["GHSA-aaaa-bbbb-cccc"],
            "fix_versions": [],
        },
    ]
    report_path = tmp_path / "report.json"
    receipt = tmp_path / "receipt.json"
    _write_json(report_path, report)

    assert (
        security_gate._pip_audit_report(
            _args(
                report_path,
                FIXTURES / "requirements-vulnerable.txt",
                receipt,
                expect_clean=False,
            )
        )
        == 0
    )

    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["vulnerabilities"] == [
        {
            "package": "urllib3",
            "version": "1.26.5",
            "aliases": [
                "CVE-2021-0001",
                "GHSA-AAAA-BBBB-CCCC",
                "PYSEC-2021-1",
            ],
        }
    ]


def test_python_sca_rejects_unused_exception(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    exceptions = tmp_path / "exceptions.json"
    _write_json(report, _report())
    _write_json(
        exceptions,
        {
            "schema_version": 1,
            "entries": [
                {
                    "id": "SCA-TEST-UNUSED",
                    "package": "urllib3",
                    "version": "1.26.5",
                    "alias": "CVE-2021-33503",
                    "owner": "security@example.test",
                    "expires_on": (date.today() + timedelta(days=30)).isoformat(),
                    "reason": "Unit-test-only stale exception proof",
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="Unused Python SCA exceptions"):
        security_gate._pip_audit_report(
            _args(
                report,
                FIXTURES / "requirements-vulnerable.txt",
                tmp_path / "receipt.json",
                expect_clean=True,
                exceptions=exceptions,
            )
        )
