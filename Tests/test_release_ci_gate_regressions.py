"""Contracts for the release-gate failures observed on PR #22."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_sdd_archive_text_is_checked_out_with_stable_lf_bytes() -> None:
    attributes = _read(".gitattributes")

    assert "*.md   text eol=lf" in attributes
    assert "specs/**/history/*.txt text eol=lf" in attributes


def test_python_quality_gate_disables_repository_pytest_cache() -> None:
    gate = _read("scripts/run_python_quality_gate.ps1")

    assert '"-p", "no:cacheprovider"' in gate


def test_expected_wrong_hash_failure_returns_success_to_github() -> None:
    workflow = _read(".github/workflows/security.yml")
    block = workflow.split(
        "      - name: Verify wrong Python package hash is rejected", 1
    )[1].split("      - name: Bind Python SCA receipt to commit", 1)[0]

    pass_message = block.index("PYTHON_PACKAGE_HASH_NEGATIVE_FIXTURE_PASS")
    assert block.index("exit 0", pass_message) > pass_message


def test_vulnerable_nuget_fixture_is_materialized_only_in_runner_temp() -> None:
    tracked_project = _read(
        "Tests/security/fixtures/VulnerableNuGet/VulnerableNuGet.csproj"
    )
    fixture_template = _read(
        "Tests/security/fixtures/VulnerableNuGet/VulnerableNuGet.csproj.txt"
    )
    workflow = _read(".github/workflows/security.yml")

    assert "Newtonsoft.Json" not in tracked_project
    assert 'Newtonsoft.Json" Version="12.0.1' in fixture_template
    assert 'Join-Path $env:RUNNER_TEMP "pb-studio-vulnerable-nuget"' in workflow
    assert "Copy-Item `" in workflow
    assert "--expect-project VulnerableNuGet.csproj" in workflow
