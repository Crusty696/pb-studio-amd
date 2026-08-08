from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import security_gate


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "Tests" / "security" / "fixtures"
INVALID_HASH_FIXTURE = FIXTURES / "python-invalid-hash.fixture"
WRONG_HASH_FIXTURE = FIXTURES / "python-wrong-hash.fixture"
VULNERABLE_FIXTURE = FIXTURES / "python-vulnerable.fixture"
SCANNER_LOCK = ROOT / "config" / "pip-audit-2.10.1-win-py311.lock"
SCA_EXCEPTIONS = ROOT / "config" / "python-sca-exceptions.json"
SCANNER_LOCK_SHA256 = (
    "116cff7875527870582ee9c2e182752ae504c3f0887934978ee6e58141518ffe"
)
SCANNER_SOURCE = (
    "config/pip-audit-2.10.1-win-py311.lock@sha256:" + SCANNER_LOCK_SHA256
)


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
        scanner_version="2.10.1",
        scanner_version_status="verified",
        invocation_kind="local",
        action_revision=None,
        local_source=SCANNER_SOURCE,
        local_command="$env:SCANNER_PYTHON -m pip_audit --requirement requirements.txt",
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
        security_gate._parse_hashed_lock(INVALID_HASH_FIXTURE)
    assert security_gate._parse_hashed_lock(
        WRONG_HASH_FIXTURE
    ) == [{"name": "urllib3", "version": "1.26.5"}]
    assert (
        security_gate._python_lock(
            SimpleNamespace(
                lock=INVALID_HASH_FIXTURE,
                expect_hash_failure=True,
            )
        )
        == 0
    )


def test_python_sca_hash_fixtures_are_explicit_and_distinct() -> None:
    malformed = INVALID_HASH_FIXTURE.read_text(encoding="utf-8")
    wrong = WRONG_HASH_FIXTURE.read_text(encoding="utf-8")
    vulnerable = VULNERABLE_FIXTURE.read_text(encoding="utf-8")

    assert "sha256:not-a-valid-sha256" in malformed
    assert "sha256:" + "0" * 64 in wrong
    assert (
        "sha256:753a0374df26658f99d826cfe40394a686d05985786d946fbe4165b5148f5a7c"
        in vulnerable
    )


def test_python_sca_scanner_lock_has_exact_inventory_and_hash() -> None:
    expected = [
        ("boolean-py", "5.0"),
        ("cachecontrol", "0.14.4"),
        ("certifi", "2026.7.22"),
        ("charset-normalizer", "3.4.9"),
        ("cyclonedx-python-lib", "11.11.0"),
        ("defusedxml", "0.7.1"),
        ("filelock", "3.32.2"),
        ("idna", "3.18"),
        ("license-expression", "30.4.4"),
        ("markdown-it-py", "4.2.0"),
        ("mdurl", "0.1.2"),
        ("msgpack", "1.2.1"),
        ("packageurl-python", "0.17.6"),
        ("packaging", "26.2"),
        ("pip", "26.2"),
        ("pip-api", "0.0.34"),
        ("pip-audit", "2.10.1"),
        ("pip-requirements-parser", "32.0.1"),
        ("platformdirs", "4.11.0"),
        ("py-serializable", "2.1.0"),
        ("pygments", "2.20.0"),
        ("pyparsing", "3.3.2"),
        ("requests", "2.34.2"),
        ("rich", "15.0.0"),
        ("sortedcontainers", "2.4.0"),
        ("tomli", "2.4.1"),
        ("tomli-w", "1.2.0"),
        ("typing-extensions", "4.16.0"),
        ("urllib3", "2.7.0"),
    ]
    lock_bytes = SCANNER_LOCK.read_bytes()
    lock_text = lock_bytes.decode("utf-8")
    inventory = security_gate._parse_hashed_lock(SCANNER_LOCK)

    assert hashlib.sha256(lock_bytes).hexdigest() == SCANNER_LOCK_SHA256
    assert [(entry["name"], entry["version"]) for entry in inventory] == expected
    assert len(inventory) == 29
    assert lock_text.count("--hash=sha256:") == 29
    assert "--only-binary=:all:" in lock_text
    assert "--require-hashes" in lock_text
    assert "pip-audit==2.10.1" in lock_text


def test_byte_bound_security_inputs_keep_lf_on_every_checkout() -> None:
    paths = [
        "config/pip-audit-2.10.1-win-py311.lock",
        "config/secret-scan-allowlist.json",
        "Tests/security/fixtures/seeded-secret.txt",
    ]
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.stdout.splitlines() == [f"{path}: eol: lf" for path in paths]
    allowlist = json.loads(
        (ROOT / "config" / "secret-scan-allowlist.json").read_text(
            encoding="utf-8"
        )
    )
    fixture_hash = hashlib.sha256(
        (FIXTURES / "seeded-secret.txt").read_bytes()
    ).hexdigest()
    assert fixture_hash in {
        entry["content_sha256"] for entry in allowlist["entries"]
    }


def test_python_sca_registered_exceptions_are_exact_and_consumed(
    tmp_path: Path,
) -> None:
    payload = json.loads(SCA_EXCEPTIONS.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "entries": [
            {
                "id": "T413-TORCH-CVE-2025-3000",
                "package": "torch",
                "version": "2.11.0+cpu",
                "alias": "CVE-2025-3000",
                "owner": "PB Studio Release Owner",
                "expires_on": "2026-09-01",
                "reason": (
                    "Affected torch.jit.script is absent in the shipped repository; "
                    "fresh-target compatibility and runtime tests remain required."
                ),
            },
            {
                "id": "T413-SETUPTOOLS-CVE-2026-59890",
                "package": "setuptools",
                "version": "81.0.0",
                "alias": "CVE-2026-59890",
                "owner": "PB Studio Release Owner",
                "expires_on": "2026-09-01",
                "reason": (
                    "The release target is Windows x64 with wheel-only installation, "
                    "which defeats the macOS sdist precondition."
                ),
            },
        ],
    }
    assert date.fromisoformat("2026-09-01") - date(2026, 8, 2) == timedelta(days=30)
    assert len(security_gate._load_python_sca_exceptions(SCA_EXCEPTIONS)) == 2

    lock = tmp_path / "approved-exceptions.lock"
    lock.write_text(
        "setuptools==81.0.0 --hash=sha256:" + "1" * 64 + "\n"
        "torch==2.11.0+cpu --hash=sha256:" + "2" * 64 + "\n",
        encoding="utf-8",
    )
    report = tmp_path / "approved-exceptions-report.json"
    receipt = tmp_path / "approved-exceptions-receipt.json"
    _write_json(
        report,
        {
            "dependencies": [
                {
                    "name": "setuptools",
                    "version": "81.0.0",
                    "vulns": [
                        {
                            "id": "GHSA-h35f-9h28-mq5c",
                            "aliases": ["CVE-2026-59890", "PYSEC-2026-3447"],
                            "fix_versions": ["83.0.0"],
                        }
                    ],
                },
                {
                    "name": "torch",
                    "version": "2.11.0+cpu",
                    "vulns": [
                        {
                            "id": "GHSA-rrmf-rvhw-rf47",
                            "aliases": ["CVE-2025-3000", "PYSEC-2025-194"],
                            "fix_versions": ["2.13.0"],
                        }
                    ],
                },
            ],
            "fixes": [],
        },
    )

    assert security_gate._pip_audit_report(
        _args(
            report,
            lock,
            receipt,
            expect_clean=True,
            exceptions=SCA_EXCEPTIONS,
        )
    ) == 0
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert [
        entry["id"] for entry in receipt_payload["applied_exceptions"]
    ] == [
        "T413-SETUPTOOLS-CVE-2026-59890",
        "T413-TORCH-CVE-2025-3000",
    ]


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


def test_python_sca_workflow_uses_isolated_exact_scanner_and_direct_cli() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )
    production_command = (
        "& $env:SCANNER_PYTHON -m pip_audit --vulnerability-service osv "
        "--disable-pip --require-hashes --no-deps --strict --aliases=on "
        "--desc=off --progress-spinner=off --format=json "
        "--output=artifacts/security/python-sca-production.json "
        "--requirement requirements.txt"
    )
    fixture_command = (
        "& $env:SCANNER_PYTHON -m pip_audit --vulnerability-service osv "
        "--disable-pip --require-hashes --no-deps --strict --aliases=on "
        "--desc=off --progress-spinner=off --format=json "
        "--output=artifacts/security/python-sca-fixture.json "
        "--requirement $fixture"
    )
    fixture_receipt_command = (
        "& $env:SCANNER_PYTHON -m pip_audit --vulnerability-service osv "
        "--disable-pip --require-hashes --no-deps --strict --aliases=on "
        "--desc=off --progress-spinner=off --format=json "
        "--output=artifacts/security/python-sca-fixture.json "
        "--requirement $env:RUNNER_TEMP\\requirements-vulnerable.txt"
    )

    def collapse_invocation(block: str) -> str:
        lines: list[str] = []
        capturing = False
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if line.startswith("& $env:SCANNER_PYTHON -m pip_audit"):
                capturing = True
            if not capturing:
                continue
            continued = line.endswith("`")
            lines.append(line.removesuffix("`").rstrip())
            if not continued:
                break
        return " ".join(lines)

    assert "pypa/gh-action-pip-audit" not in workflow
    assert 'PIP_AUDIT_SCANNER_VERSION: "2.10.1"' in workflow
    assert f"PIP_AUDIT_SCANNER_LOCK_SHA256: {SCANNER_LOCK_SHA256}" in workflow
    assert "python -m venv $scannerVenv" in workflow
    assert "SCANNER_PYTHON=$scannerPython" in workflow
    assert "& $scannerPython -m pip install" in workflow
    assert "--require-hashes --only-binary=:all: --no-deps" in workflow
    assert "$scannerVersion -ne \"pip-audit $env:PIP_AUDIT_SCANNER_VERSION\"" in workflow
    assert workflow.count("--local-command '& $env:SCANNER_PYTHON -m pip_audit") == 2
    assert "--local-command '$env:SCANNER_PYTHON -m pip_audit" not in workflow
    assert workflow.count("--invocation-kind local") == 2
    assert workflow.count(f"@sha256:${{{{ env.PIP_AUDIT_SCANNER_LOCK_SHA256 }}}}") == 2
    assert "--exceptions config/python-sca-exceptions.json" in workflow
    assert "--invocation-kind github-action" not in workflow
    assert "PIP_AUDIT_ACTION_REVISION" not in workflow
    assert "--tool-version" not in workflow
    assert "requirements-invalid-hash.txt" not in workflow
    assert "requirements-wrong-hash.txt" in workflow
    assert (
        "python -m pip download --require-hashes --only-binary=:all: --no-deps"
        in workflow
    )
    assert "id: production_hash_validation" in workflow
    assert "--dest artifacts/security/python-sca-production-hashes" in workflow
    assert "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE" in workflow
    assert "Expected sha256 $expectedHash" in workflow
    assert "Got\\s+$actualHash" in workflow
    assert "steps.wrong_hash_validation.outcome" in workflow
    assert "steps.production_hash_validation.outcome" in workflow
    assert "steps.production_audit.outcome" in workflow
    assert "steps.scanner_install.outcome" in workflow
    scanner_install = workflow.split(
        "      - name: Install isolated pip-audit scanner", 1
    )[1].split("      - name: Audit production lock", 1)[0]
    production_audit = workflow.split("      - name: Audit production lock", 1)[1].split(
        "      - name: Validate production Python report", 1
    )[0]
    production_validation = workflow.split(
        "      - name: Validate production Python report", 1
    )[1].split("      - name: Verify production Python lock hashes", 1)[0]
    vulnerable_fixture = workflow.split(
        "      - name: Audit vulnerable fixture", 1
    )[1].split("      - name: Validate vulnerable Python report", 1)[0]
    fixture_validation = workflow.split(
        "      - name: Validate vulnerable Python report", 1
    )[1].split("      - name: Verify wrong Python package hash is rejected", 1)[0]
    assert "requirements.txt" not in scanner_install
    assert collapse_invocation(production_audit) == production_command
    assert f"--local-command '{production_command}'" in production_validation
    assert collapse_invocation(vulnerable_fixture) == fixture_command
    assert f"--local-command '{fixture_receipt_command}'" in fixture_validation
    assert "$auditExit -notin @(0, 1)" in production_audit
    assert "python-sca-production-exit.json" in production_audit
    assert production_audit.rstrip().endswith("exit 0")
    assert vulnerable_fixture.rstrip().endswith("exit 0")
    assert "continue-on-error" not in production_audit
    assert "continue-on-error" not in production_validation


@pytest.mark.parametrize(
    ("step_name", "next_step_name", "seed_fixture_report"),
    [
        (
            "Audit production lock",
            "Validate production Python report",
            False,
        ),
        (
            "Audit vulnerable fixture",
            "Validate vulnerable Python report",
            True,
        ),
    ],
)
def test_python_sca_accepted_exit_one_normalizes_github_runner_status(
    tmp_path: Path,
    step_name: str,
    next_step_name: str,
    seed_fixture_report: bool,
) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    assert powershell is not None, "Windows PowerShell is required by this gate"

    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )
    step = workflow.split(f"      - name: {step_name}", 1)[1].split(
        f"      - name: {next_step_name}", 1
    )[0]
    script = textwrap.dedent(step.split("        run: |", 1)[1]).strip()
    assert script.endswith("exit 0")

    security_dir = tmp_path / "artifacts" / "security"
    security_dir.mkdir(parents=True)
    if seed_fixture_report:
        (security_dir / "python-sca-fixture.json").write_text("{}", encoding="utf-8")

    fake_scanner = tmp_path / "fake-scanner.cmd"
    fake_scanner.write_text("@exit /b 1\n", encoding="utf-8")
    environment = {**os.environ, "SCANNER_PYTHON": str(fake_scanner)}
    runner_epilogue = (
        "\nif ((Test-Path -LiteralPath variable:\\LASTEXITCODE)) "
        "{ exit $LASTEXITCODE }\n"
    )

    vulnerable_script = tmp_path / "without-normalization.ps1"
    vulnerable_script.write_text(
        script.removesuffix("exit 0").rstrip() + runner_epilogue,
        encoding="utf-8",
    )
    fixed_script = tmp_path / "with-normalization.ps1"
    fixed_script.write_text(script + runner_epilogue, encoding="utf-8")

    vulnerable = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(vulnerable_script),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    fixed = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(fixed_script),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert vulnerable.returncode == 1, vulnerable.stdout + vulnerable.stderr
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr


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
                VULNERABLE_FIXTURE,
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
        "version": "2.10.1",
        "version_status": "verified",
    }
    assert payload["invocation"] == {
        "kind": "local",
        "source": SCANNER_SOURCE,
        "command": "$env:SCANNER_PYTHON -m pip_audit --requirement requirements.txt",
    }
    assert "action" not in payload
    assert payload["lock"]["sha256"] == hashlib.sha256(
        VULNERABLE_FIXTURE.read_bytes()
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
            str(VULNERABLE_FIXTURE),
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
                VULNERABLE_FIXTURE,
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
                VULNERABLE_FIXTURE,
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
                VULNERABLE_FIXTURE,
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
                VULNERABLE_FIXTURE,
                tmp_path / "receipt.json",
                expect_clean=True,
                exceptions=exceptions,
            )
        )
