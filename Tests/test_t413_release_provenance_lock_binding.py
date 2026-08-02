"""T413 release provenance must bind every approved supply-chain lock."""

from pathlib import Path

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
