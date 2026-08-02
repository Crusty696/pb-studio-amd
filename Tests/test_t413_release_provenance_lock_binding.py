"""T413 release provenance must bind every approved supply-chain lock."""

import json
from pathlib import Path
import sys
import tempfile

from scripts import generate_release_provenance


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_T413_INPUTS = {
    "requirements.txt",
    "requirements-direct.txt",
    "config/pip-audit-2.10.1-win-py311.lock",
    "config/python-sca-exceptions.json",
    ".mcp.json",
    ".codex/config.toml",
    "tools/mcp-node/.npmrc",
    "tools/mcp-node/package.json",
    "tools/mcp-node/package-lock.json",
}


def test_release_provenance_binds_t413_supply_chain_inputs() -> None:
    lock_paths = tuple(generate_release_provenance.LOCK_PATHS)

    assert len(lock_paths) == len(set(lock_paths))
    assert REQUIRED_T413_INPUTS.issubset(lock_paths)
    for relative in REQUIRED_T413_INPUTS:
        path = ROOT / relative
        assert path.is_file(), relative
        assert len(generate_release_provenance._sha256(path)) == 64


def test_release_serial_seed_changes_when_mcp_lock_changes(tmp_path: Path) -> None:
    source = ROOT / "tools" / "mcp-node" / "package-lock.json"
    changed = tmp_path / "package-lock.json"
    changed.write_bytes(source.read_bytes() + b"\n")

    assert generate_release_provenance._sha256(source) != (
        generate_release_provenance._sha256(changed)
    )


def test_release_provenance_displays_internal_and_external_paths() -> None:
    internal = ROOT / "artifacts" / "release-provenance"
    external = Path(tempfile.gettempdir()) / "pb-t413-external-output"

    assert generate_release_provenance._display_path(ROOT, internal) == (
        "artifacts/release-provenance"
    )
    assert not external.resolve().is_relative_to(ROOT)
    assert generate_release_provenance._display_path(ROOT, external) == str(
        external.resolve()
    )


def test_release_provenance_writes_to_external_output_directory(
    monkeypatch,
) -> None:
    expected_dotnet = json.loads((ROOT / "global.json").read_text(encoding="utf-8"))[
        "sdk"
    ]["version"]
    monkeypatch.setattr(
        generate_release_provenance,
        "_git_state",
        lambda root: {
            "commit_sha": "a" * 40,
            "branch": "test",
            "dirty": False,
            "dirty_paths": [],
        },
    )
    monkeypatch.setattr(
        generate_release_provenance,
        "_dotnet_state",
        lambda root: {"selected_sdk": expected_dotnet, "installed_sdks": []},
    )
    with tempfile.TemporaryDirectory(prefix="pb-t413-provenance-") as temp_name:
        output_dir = Path(temp_name).resolve()
        assert not output_dir.is_relative_to(ROOT)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "generate_release_provenance.py",
                "--output-dir",
                str(output_dir),
                "--allow-unmaterialized-runtime",
            ],
        )

        assert generate_release_provenance.main() == 0
        receipt_path = output_dir / "release-provenance.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        assert (output_dir / "sbom.cdx.json").is_file()
        assert receipt_path.is_file()
        assert receipt["sbom"]["path"] == str(
            (output_dir / "sbom.cdx.json").resolve()
        )
