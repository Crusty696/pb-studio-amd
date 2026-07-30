"""Fresh static implementation gate after the T365 launcher trust fix."""

from __future__ import annotations

import hashlib
import json
import os
import py_compile
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "specs/00013-system-wide-bug-hunting-audit/evidence"
RESULT_PATH = EVIDENCE / "T360-post-T365-revalidation.json"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "bin",
    "obj",
    "node_modules",
    "__pycache__",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def active(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        not any(part in EXCLUDED_PARTS or part.startswith(".pytest_") for part in relative.parts)
        and path.is_file()
    )


def decode_json(path: Path) -> object:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return json.loads(raw.decode("utf-16"))
    return json.loads(raw.decode("utf-8-sig"))


errors: list[str] = []
counts: dict[str, int] = {}

try:
    python_files = [
        path
        for parent in ("src", "backend", "Tests", "scripts")
        for path in (ROOT / parent).rglob("*.py")
        if active(path)
    ]
    for path in python_files:
        py_compile.compile(str(path), doraise=True)
    counts["python"] = len(python_files)

    json_paths = {
        ROOT / path
        for path in (
            git("ls-files", "*.json").splitlines()
            + git("ls-files", "--others", "--exclude-standard", "*.json").splitlines()
        )
        if path
    }
    json_paths = {path for path in json_paths if active(path)}
    for path in json_paths:
        decode_json(path)
    counts["json"] = len(json_paths)

    xml_paths = {
        path
        for pattern in ("*.xaml", "*.csproj", "*.props", "*.targets")
        for path in ROOT.rglob(pattern)
        if active(path)
    }
    xml_paths.update(
        path
        for path in (ROOT / "tools/LibreHardwareMonitor").glob("*.config")
        if active(path)
    )
    for path in xml_paths:
        ET.parse(path)
    counts["xml"] = len(xml_paths)

    changed = {
        ROOT / path
        for path in (
            git("diff", "--name-only", "--diff-filter=ACMRTUXB").splitlines()
            + git("ls-files", "--others", "--exclude-standard").splitlines()
        )
        if path
    }
    changed = {path for path in changed if active(path)}
    empty = [str(path.relative_to(ROOT)) for path in changed if path.stat().st_size == 0]
    if empty:
        fail(f"Changed files are empty: {empty}")
    counts["changed_nonempty"] = len(changed)

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    os.environ["PYTHONPATH"] = str(ROOT / "src")
    from backend.main import app

    snapshot_path = ROOT / "PBStudio.UI/openapi.snapshot.json"
    generated_path = ROOT / "PBStudio.UI/Generated/ApiTypes.g.cs"
    snapshot = decode_json(snapshot_path)
    if snapshot != app.openapi():
        fail("OpenAPI runtime schema differs from openapi.snapshot.json")
    if generated_path.stat().st_size == 0:
        fail("Generated NSwag client is empty")
    if generated_path.stat().st_mtime_ns < snapshot_path.stat().st_mtime_ns:
        fail("Generated NSwag client is older than OpenAPI snapshot")

    lhm_runtime = decode_json(ROOT / "config/lhm-runtime.json")
    lhm_active = lhm_runtime["active"]
    bundle = (ROOT / lhm_active["bundle_dir"]).resolve(strict=True)
    if not bundle.is_relative_to(ROOT.resolve()):
        fail("LHM bundle escaped project root")
    manifest = bundle / lhm_active["manifest"]
    library = bundle / lhm_active["library"]
    if sha256(manifest) != lhm_active["manifest_sha256"].upper():
        fail("LHM manifest hash mismatch")
    if sha256(library) != lhm_active["library_sha256"].upper():
        fail("LHM library hash mismatch")
    bundle_manifest = decode_json(manifest)
    if bundle_manifest["version"] != lhm_active["version"]:
        fail("LHM bundle version mismatch")
    for assembly in bundle_manifest["assemblies"]:
        assembly_path = bundle / assembly["file"]
        if sha256(assembly_path) != assembly["sha256"].upper():
            fail(f"LHM assembly hash mismatch: {assembly['file']}")

    directml = (ROOT / "src/pb_studio/core/directml_adapter.py").read_text(encoding="utf-8")
    for contract in (
        "session.disable_cpu_ep_fallback",
        "enable_mem_pattern = False",
        "enable_cpu_mem_arena = False",
        "disable_fallback",
        'providers[0] != "DmlExecutionProvider"',
    ):
        if contract not in directml:
            fail(f"DirectML contract missing: {contract}")

    consumers = (
        "src/pb_studio/core/model_loader.py",
        "src/pb_studio/video/raft.py",
        "src/pb_studio/video/moondream.py",
        "src/pb_studio/ai/siglip_wrapper.py",
        "src/pb_studio/ai/clap_wrapper.py",
        "src/pb_studio/audio/separator.py",
    )
    for relative in consumers:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if "enforce_directml_session" not in text:
            fail(f"Central DirectML enforcement missing: {relative}")

    runtime_contract = (ROOT / "scripts/runtime_contract.ps1").read_text(encoding="utf-8-sig")
    launcher = (ROOT / "launch.ps1").read_text(encoding="utf-8-sig")
    for contract in (
        "config\\lhm-runtime.json",
        "PBSTUDIO_LHM_MANIFEST_SHA256",
        "PBSTUDIO_LHM_SHA256",
        "Get-FileHash",
        "ReparsePoint",
    ):
        if contract not in runtime_contract:
            fail(f"Launcher LHM trust contract missing: {contract}")
    if "Get-PBStudioRuntimeContract -ProjectRoot $ProjectRoot -RequirePython -RequireFFmpeg -ApplyEnvironment" not in launcher:
        fail("Production launcher does not apply runtime environment contract")

    diff_check = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if diff_check.returncode:
        fail(f"git diff --check failed:\n{diff_check.stdout}{diff_check.stderr}")

    result = {
        "status": "PASS",
        "counts": counts,
        "openapi_sha256": sha256(snapshot_path),
        "generated_sha256": sha256(generated_path),
        "lhm_manifest_sha256": sha256(manifest),
        "lhm_library_sha256": sha256(library),
        "errors": errors,
    }
except Exception as exc:
    errors.append(f"{type(exc).__name__}: {exc}")
    result = {
        "status": "FAIL",
        "counts": counts,
        "errors": errors,
    }

RESULT_PATH.write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["status"] == "PASS" else 1)
