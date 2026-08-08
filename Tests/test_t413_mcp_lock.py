import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = REPO_ROOT / "tools" / "mcp-node"
CONTEXT7_SRI = "sha512-m+GIwQKBx2yCnLN7Et3wqkuTk1iPkMySQH2i6KiUf4B9wVI0tgtjeXRcDfFZPf5rnRA3gjYhr1FqQqMb9aSRnw=="
CAVEMAN_SRI = "sha512-AH81oXnhBTRrqbolhq3vTMrJxP+Zgk5cTxMYatMVNGNALqqdviY+3sTkSxynCfZQfxNXUwAwi5mWSlrXxM4TkA=="
LOCK_SHA256 = "2D542EE2E1F30793777E23959842325D032D75FB7E521314D4AA1EE23AFE5152"
MCP_SOURCE_FILES = {
    ".npmrc",
    "package-lock.json",
    "package.json",
    "run-caveman-shrink.cmd",
    "run-context7.cmd",
    "verify-lock.mjs",
}


def _load_lock(path: Path | None = None) -> dict:
    return json.loads((path or TOOL_DIR / "package-lock.json").read_text(encoding="utf-8"))


def test_mcp_direct_dependencies_and_integrities_are_exact() -> None:
    manifest = json.loads((TOOL_DIR / "package.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((TOOL_DIR / "package-lock.json").read_bytes()).hexdigest().upper() == LOCK_SHA256
    assert manifest["private"] is True
    assert manifest["engines"] == {"node": ">=20.18.1"}
    assert manifest["dependencies"] == {
        "@upstash/context7-mcp": "3.2.5",
        "caveman-shrink": "0.1.0",
    }

    lock = _load_lock()
    package_nodes = {
        path: entry
        for path, entry in lock["packages"].items()
        if path.startswith("node_modules/")
    }
    assert lock["lockfileVersion"] == 3
    assert len(package_nodes) == 110
    assert lock["packages"][""]["dependencies"] == manifest["dependencies"]
    assert lock["packages"][""]["engines"] == manifest["engines"]
    assert lock["packages"]["node_modules/@upstash/context7-mcp"]["version"] == "3.2.5"
    assert lock["packages"]["node_modules/@upstash/context7-mcp"]["integrity"] == CONTEXT7_SRI
    assert lock["packages"]["node_modules/caveman-shrink"]["version"] == "0.1.0"
    assert lock["packages"]["node_modules/caveman-shrink"]["integrity"] == CAVEMAN_SRI
    assert all(entry.get("integrity") for entry in package_nodes.values() if entry.get("resolved"))


def test_mcp_configs_are_project_portable_and_never_install_dynamically() -> None:
    claude = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    codex_text = (REPO_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    codex = tomllib.loads(codex_text)
    context7 = claude["mcpServers"]["context7"]

    assert context7["command"] == "${CLAUDE_PROJECT_DIR:-.}\\tools\\mcp-node\\run-context7.cmd"
    assert context7["args"] == []
    assert codex["mcp_servers"]["context7"] == {
        "command": "tools/mcp-node/run-context7.cmd",
        "cwd": ".",
    }
    assert codex["mcp_servers"]["caveman-shrink"] == {
        "command": "tools/mcp-node/run-caveman-shrink.cmd",
        "cwd": ".",
    }

    owned_text = "\n".join(
        [
            json.dumps(claude),
            codex_text,
            (TOOL_DIR / "run-context7.cmd").read_text(encoding="utf-8"),
            (TOOL_DIR / "run-caveman-shrink.cmd").read_text(encoding="utf-8"),
            (TOOL_DIR / "verify-lock.mjs").read_text(encoding="utf-8"),
        ]
    ).lower()
    assert "@" + "latest" not in owned_text
    assert '"' + "-y" + '"' not in owned_text
    for dynamic_runner in ("np" + "x", "npm " + "exec", "pnpm " + "dlx", "bun" + "x"):
        assert dynamic_runner not in owned_text


def test_runtime_wrappers_are_offline_local_and_fail_closed() -> None:
    for wrapper_name, binary_name in (
        ("run-context7.cmd", "context7-mcp.cmd"),
        ("run-caveman-shrink.cmd", "caveman-shrink.cmd"),
    ):
        text = (TOOL_DIR / wrapper_name).read_text(encoding="utf-8").lower()
        assert "npm_config_offline=true" in text
        assert "npm_config_ignore_scripts=true" in text
        assert "node_modules\\.bin" in text
        assert binary_name in text
        assert "process.versions.node" in text
        assert 'node "%mcp_verify%" --runtime' in text
        assert "if not exist" in text
        assert "exit /b 69" in text

    caveman_text = (TOOL_DIR / "run-caveman-shrink.cmd").read_text(encoding="utf-8").lower()
    assert "node_modules\\@upstash\\context7-mcp\\dist\\index.js" in caveman_text
    assert 'call "%mcp_caveman_bin%" node "%mcp_context7_entry%"' in caveman_text

    npmrc = (TOOL_DIR / ".npmrc").read_text(encoding="utf-8").splitlines()
    assert npmrc == [
        "ignore-scripts=true",
        "engine-strict=true",
        "audit=false",
        "fund=false",
        "update-notifier=false",
    ]


def test_clean_checkout_tracking_and_ignore_contract() -> None:
    assert {path.name for path in TOOL_DIR.iterdir() if path.is_file()} == MCP_SOURCE_FILES
    unignored_paths = [REPO_ROOT / ".codex" / "config.toml"] + [TOOL_DIR / name for name in MCP_SOURCE_FILES]
    for path in unignored_paths:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 1, f"source path remains ignored: {path}"

    for ignored_path in (
        TOOL_DIR / "node_modules" / "@upstash" / "context7-mcp" / "package.json",
        TOOL_DIR / "unexpected-runtime-file.txt",
        REPO_ROOT / ".codex" / "unrelated.toml",
        REPO_ROOT / "src" / "tools" / "unexpected-runtime-file.txt",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", str(ignored_path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 0, f"runtime path became trackable: {ignored_path}"


@pytest.mark.skipif(os.name != "nt", reason="PB Studio MCP wrappers target Windows")
@pytest.mark.parametrize("wrapper_name", ["run-context7.cmd", "run-caveman-shrink.cmd"])
def test_runtime_wrapper_does_not_install_when_dependencies_are_missing(
    tmp_path: Path,
    wrapper_name: str,
) -> None:
    wrapper = tmp_path / wrapper_name
    shutil.copy2(TOOL_DIR / wrapper_name, wrapper)
    shutil.copy2(TOOL_DIR / "verify-lock.mjs", tmp_path / "verify-lock.mjs")

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(wrapper)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 69
    assert "npm ci --ignore-scripts" in result.stderr
    assert not (tmp_path / "node_modules").exists()


def test_lock_verifier_rejects_tampered_direct_sri(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to verify the MCP lock"
    lock = _load_lock()
    lock["packages"]["node_modules/@upstash/context7-mcp"]["integrity"] = "sha512-AAAAAAAA"
    tampered_lock = tmp_path / "package-lock.json"
    tampered_lock.write_text(json.dumps(lock), encoding="utf-8")

    result = subprocess.run(
        [node, str(TOOL_DIR / "verify-lock.mjs"), str(tampered_lock)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={**os.environ, "npm_config_offline": "true"},
    )

    assert result.returncode == 1
    assert "Context7 integrity: expected" in result.stderr


def test_lock_verifier_rejects_transitive_lock_tamper(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to verify the MCP lock"
    lock = _load_lock()
    lock["packages"]["node_modules/@modelcontextprotocol/sdk"]["version"] = "1.30.1"
    tampered_lock = tmp_path / "package-lock.json"
    tampered_lock.write_text(json.dumps(lock), encoding="utf-8")

    result = subprocess.run(
        [node, str(TOOL_DIR / "verify-lock.mjs"), str(tampered_lock)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 1
    assert "lock SHA-256: expected" in result.stderr


@pytest.mark.integration
def test_runtime_verifier_rejects_range_compatible_installed_drift(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to verify the MCP runtime"
    runtime_dir = tmp_path / "mcp-node"
    shutil.copytree(TOOL_DIR, runtime_dir)
    sdk_manifest_path = runtime_dir / "node_modules" / "@modelcontextprotocol" / "sdk" / "package.json"
    sdk_manifest = json.loads(sdk_manifest_path.read_text(encoding="utf-8"))
    assert sdk_manifest["version"] == "1.30.0"
    sdk_manifest["version"] = "1.30.1"
    sdk_manifest_path.write_text(json.dumps(sdk_manifest), encoding="utf-8")

    result = subprocess.run(
        [node, str(runtime_dir / "verify-lock.mjs"), "--runtime"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 1
    assert "node_modules/@modelcontextprotocol/sdk installed version: expected 1.30.0, got 1.30.1" in result.stderr
