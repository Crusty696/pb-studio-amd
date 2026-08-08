"""Contracts for the release-gate failures observed on PR #22."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_sdd_archive_text_preserves_manifest_bytes_on_windows() -> None:
    attributes = _read(".gitattributes")

    assert "*.md   text eol=lf" in attributes
    assert "specs/**/history/*.md -text !eol -diff" in attributes
    assert "specs/**/history/*.txt text eol=lf" in attributes


def test_python_quality_gate_disables_repository_pytest_cache() -> None:
    gate = _read("scripts/run_python_quality_gate.ps1")

    assert '"-p", "no:cacheprovider"' in gate


def test_expected_wrong_hash_failure_returns_success_to_github() -> None:
    workflow = _read(".github/workflows/security.yml")
    tracked_requirements = _read(
        "Tests/security/fixtures/requirements-wrong-hash.txt"
    )
    fixture_template = _read(
        "Tests/security/fixtures/python-wrong-hash.fixture"
    )
    block = workflow.split(
        "      - name: Verify wrong Python package hash is rejected", 1
    )[1].split("      - name: Bind Python SCA receipt to commit", 1)[0]

    assert "urllib3" not in tracked_requirements
    assert "urllib3==1.26.5" in fixture_template
    assert 'Join-Path $env:RUNNER_TEMP "requirements-wrong-hash.txt"' in block
    assert "python-wrong-hash.fixture" in block
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


def test_vulnerable_python_fixture_is_materialized_only_in_runner_temp() -> None:
    tracked_requirements = _read(
        "Tests/security/fixtures/requirements-vulnerable.txt"
    )
    fixture_template = _read(
        "Tests/security/fixtures/python-vulnerable.fixture"
    )
    workflow = _read(".github/workflows/security.yml")

    assert "urllib3" not in tracked_requirements
    assert "urllib3==1.26.5" in fixture_template
    assert 'Join-Path $env:RUNNER_TEMP "requirements-vulnerable.txt"' in workflow
    assert "python-vulnerable.fixture" in workflow
    assert "--lock ${{ runner.temp }}\\requirements-vulnerable.txt" in workflow


def test_malformed_python_hash_fixture_is_not_a_dependency_manifest() -> None:
    tracked_requirements = _read(
        "Tests/security/fixtures/requirements-invalid-hash.txt"
    )
    fixture_template = _read(
        "Tests/security/fixtures/python-invalid-hash.fixture"
    )

    assert "urllib3" not in tracked_requirements
    assert "sha256:not-a-valid-sha256" in fixture_template
