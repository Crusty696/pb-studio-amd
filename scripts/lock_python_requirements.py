"""Generate and validate PB Studio's CPython 3.11 Windows wheel lock.

Generation uses pip's resolver in dry-run mode. It never installs packages.
The selected wheel URL and SHA-256 come directly from pip's JSON report.
Existing lock versions remain constraints unless explicitly refreshed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Iterable


TARGET_PYTHON = (3, 11)
TARGET_PLATFORM = "win_amd64"
TARGET_ABI = "cp311"
LOCK_PIP_VERSION = "26.1.1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECT = PROJECT_ROOT / "requirements-direct.txt"
DEFAULT_LOCK = PROJECT_ROOT / "requirements.txt"
LOCAL_WHEEL_DIR = PROJECT_ROOT / "vendor" / "wheels"
LOCAL_WHEEL_MANIFEST = PROJECT_ROOT / "config" / "python-wheel-overrides.json"
PYTORCH_CPU_FIND_LINKS = (
    "https://download.pytorch.org/whl/cpu/torch/",
    "https://download.pytorch.org/whl/cpu/torchvision/",
    "https://download.pytorch.org/whl/cpu/torchaudio/",
)
CPU_TORCH_CONTRACT = {
    "torch": "2.4.1+cpu",
    "torchvision": "0.19.1+cpu",
    "torchaudio": "2.4.1+cpu",
}
FORBIDDEN_ACCELERATOR_PREFIXES = ("cuda-", "nvidia-")

_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)=="
    r"(?P<version>[^\s;]+)"
    r"(?:\s+--hash=sha256:(?P<hash>[0-9a-f]{64}))?$"
)


class LockError(RuntimeError):
    """Raised when the lock contract is incomplete or inconsistent."""


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _assert_cpu_torch_contract(
    entries: dict[str, tuple[str, str, str | None]],
) -> None:
    errors: list[str] = []
    for canonical, expected in CPU_TORCH_CONTRACT.items():
        entry = entries.get(canonical)
        if entry is None:
            errors.append(f"{canonical} missing")
        elif entry[1] != expected:
            errors.append(f"{canonical} must be {expected}, got {entry[1]}")
    forbidden = sorted(
        name
        for name in entries
        if name.startswith(FORBIDDEN_ACCELERATOR_PREFIXES)
        or name in {"pytorch-cuda", "triton"}
    )
    if forbidden:
        errors.append("forbidden accelerator packages: " + ", ".join(forbidden))
    if errors:
        raise LockError("CPU-only PyTorch contract violated: " + "; ".join(errors))


def _read_pins(path: Path, *, hashes_required: bool) -> dict[str, tuple[str, str, str | None]]:
    pins: dict[str, tuple[str, str, str | None]] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        match = _PIN_RE.fullmatch(line)
        if match is None:
            raise LockError(f"{path}:{line_number}: expected exact name==version pin")
        digest = match.group("hash")
        if hashes_required and digest is None:
            raise LockError(f"{path}:{line_number}: missing sha256 wheel hash")
        canonical = _canonical_name(match.group("name"))
        if canonical in pins:
            raise LockError(f"{path}:{line_number}: duplicate package {canonical}")
        pins[canonical] = (match.group("name"), match.group("version"), digest)
    if not pins:
        raise LockError(f"{path}: contains no package pins")
    return pins


def _assert_runtime() -> None:
    if sys.version_info[:2] != TARGET_PYTHON:
        raise LockError(
            f"lock generation requires CPython {TARGET_PYTHON[0]}.{TARGET_PYTHON[1]}, "
            f"got {sys.version_info.major}.{sys.version_info.minor}"
        )
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"\bpip\s+([^\s]+)", completed.stdout)
    installed = match.group(1) if match else "unknown"
    if installed != LOCK_PIP_VERSION:
        raise LockError(
            f"lock generation requires pip {LOCK_PIP_VERSION}, got {installed}"
        )


def _verify_local_wheels() -> dict[str, tuple[str, str]]:
    manifest = json.loads(LOCAL_WHEEL_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise LockError(f"{LOCAL_WHEEL_MANIFEST}: unsupported schema")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        raise LockError(f"{LOCAL_WHEEL_MANIFEST}: packages must be non-empty")
    verified: dict[str, tuple[str, str]] = {}
    declared_paths: set[Path] = set()
    for package in packages:
        if not isinstance(package, dict):
            raise LockError(f"{LOCAL_WHEEL_MANIFEST}: invalid package entry")
        relative = package.get("wheel_path")
        expected = package.get("wheel_sha256")
        if not isinstance(relative, str) or not relative.startswith("vendor/wheels/"):
            raise LockError(f"{LOCAL_WHEEL_MANIFEST}: unsafe wheel path")
        path = (PROJECT_ROOT / relative).resolve()
        try:
            path.relative_to(LOCAL_WHEEL_DIR.resolve())
        except ValueError as exc:
            raise LockError(f"{LOCAL_WHEEL_MANIFEST}: wheel path escapes vendor") from exc
        if (
            not path.is_file()
            or not isinstance(expected, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise LockError(f"{relative}: wheel or SHA-256 missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise LockError(f"{relative}: SHA-256 mismatch")
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise LockError(f"{relative}: package name/version missing")
        canonical = _canonical_name(name)
        if canonical in verified or path in declared_paths:
            raise LockError(f"{relative}: duplicate manifest package/path")
        verified[canonical] = (version, expected)
        declared_paths.add(path)
    actual_paths = {path.resolve() for path in LOCAL_WHEEL_DIR.glob("*.whl")}
    if actual_paths != declared_paths:
        unexpected = sorted(os.fspath(path) for path in actual_paths - declared_paths)
        missing = sorted(os.fspath(path) for path in declared_paths - actual_paths)
        raise LockError(
            f"{LOCAL_WHEEL_MANIFEST}: wheel allowlist mismatch; "
            f"unexpected={unexpected}, missing={missing}"
        )
    return verified


def _freeze_installed() -> dict[str, tuple[str, str, None]]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
    )
    pins: dict[str, tuple[str, str, None]] = {}
    for raw_line in completed.stdout.splitlines():
        match = _PIN_RE.fullmatch(raw_line.strip())
        if match is None:
            continue
        name = match.group("name")
        pins[_canonical_name(name)] = (name, match.group("version"), None)
    return pins


def _constraint_lines(
    pins: dict[str, tuple[str, str, str | None]],
    direct: dict[str, tuple[str, str, str | None]],
    upgrades: set[str],
) -> Iterable[str]:
    excluded = set(direct) | upgrades
    for canonical in sorted(pins):
        if canonical in excluded or canonical in {"pip", "setuptools", "wheel"}:
            continue
        name, version, _ = pins[canonical]
        yield f"{name}=={version}"


def _run_resolver(
    direct_path: Path,
    constraints: Iterable[str],
) -> dict:
    with tempfile.TemporaryDirectory(prefix="pb-python-lock-") as temp_dir:
        temp_root = Path(temp_dir)
        constraints_path = temp_root / "constraints.txt"
        report_path = temp_root / "pip-report.json"
        constraints_path.write_text(
            "\n".join(constraints) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--only-binary=:all:",
            "--find-links",
            os.fspath(LOCAL_WHEEL_DIR),
            "--platform",
            TARGET_PLATFORM,
            "--python-version",
            f"{TARGET_PYTHON[0]}.{TARGET_PYTHON[1]}",
            "--implementation",
            "cp",
            "--abi",
            TARGET_ABI,
            "--report",
            os.fspath(report_path),
            "--requirement",
            os.fspath(direct_path),
            "--constraint",
            os.fspath(constraints_path),
        ]
        for find_links_url in PYTORCH_CPU_FIND_LINKS:
            command.extend(["--find-links", find_links_url])
        subprocess.run(command, check=True)
        return json.loads(report_path.read_text(encoding="utf-8"))


def _render_lock(report: dict) -> str:
    entries: dict[str, tuple[str, str, str]] = {}
    for item in report.get("install", []):
        metadata = item.get("metadata") or {}
        download = item.get("download_info") or {}
        archive = download.get("archive_info") or {}
        name = metadata.get("name")
        version = metadata.get("version")
        digest = archive.get("hash")
        url = download.get("url", "")
        if not isinstance(name, str) or not isinstance(version, str):
            raise LockError("pip report entry lacks package name/version")
        if not isinstance(digest, str) or not digest.startswith("sha256="):
            raise LockError(f"{name}=={version}: pip report lacks SHA-256")
        sha256 = digest.removeprefix("sha256=")
        if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise LockError(f"{name}=={version}: invalid SHA-256")
        if not isinstance(url, str) or not url.lower().endswith(".whl"):
            raise LockError(f"{name}=={version}: resolver selected non-wheel artifact")
        canonical = _canonical_name(name)
        if canonical in entries:
            raise LockError(f"pip report contains duplicate package {canonical}")
        entries[canonical] = (name, version, sha256)

    if not entries:
        raise LockError("pip report contains no install entries")
    _assert_cpu_torch_contract(entries)

    lines = [
        "# PB Studio AMD Edition - complete Python lock",
        "# Target: CPython 3.11, Windows x64 (win_amd64), binary wheels only",
        f"# Generated by: scripts/lock_python_requirements.py with pip {LOCK_PIP_VERSION}",
        "# Input: requirements-direct.txt",
        "# Update: edit direct pins, then run:",
        "#   .\\.venv\\Scripts\\python.exe scripts\\lock_python_requirements.py generate --output requirements.txt",
        "# Install:",
        "#   .\\.venv\\Scripts\\python.exe -m pip install --require-hashes -r requirements.txt",
        "",
        "--only-binary=:all:",
        "--find-links=vendor/wheels",
        *(f"--find-links={url}" for url in PYTORCH_CPU_FIND_LINKS),
        "--require-hashes",
        "",
    ]
    for canonical in sorted(entries):
        name, version, digest = entries[canonical]
        lines.append(f"{name}=={version} --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"


def generate(args: argparse.Namespace) -> None:
    _assert_runtime()
    _verify_local_wheels()
    direct = _read_pins(args.direct, hashes_required=False)
    if args.refresh_all:
        baseline: dict[str, tuple[str, str, str | None]] = {}
    elif args.bootstrap_installed:
        baseline = _freeze_installed()
    elif args.lock.exists():
        baseline = _read_pins(args.lock, hashes_required=True)
    else:
        raise LockError(
            "existing lock missing; use --bootstrap-installed only from a proven runtime"
        )
    upgrades = {_canonical_name(name) for name in args.upgrade_package}
    report = _run_resolver(
        args.direct,
        _constraint_lines(baseline, direct, upgrades),
    )
    rendered = _render_lock(report)
    if args.output is None:
        sys.stdout.write(rendered)
        return
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(rendered)
        temp_path = Path(handle.name)
    os.replace(temp_path, output)


def verify(args: argparse.Namespace) -> None:
    local_wheels = _verify_local_wheels()
    direct = _read_pins(args.direct, hashes_required=False)
    locked = _read_pins(args.lock, hashes_required=True)
    text = args.lock.read_text(encoding="utf-8")
    required_options = {
        "--only-binary=:all:",
        "--find-links=vendor/wheels",
        *(f"--find-links={url}" for url in PYTORCH_CPU_FIND_LINKS),
        "--require-hashes",
    }
    present_options = {
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("--")
    }
    if present_options != required_options:
        raise LockError(
            f"{args.lock}: options must be exactly {sorted(required_options)}"
        )
    mismatches = []
    for canonical, (name, version, _) in direct.items():
        locked_entry = locked.get(canonical)
        if locked_entry is None:
            mismatches.append(f"{name}=={version}: missing")
        elif locked_entry[1] != version:
            mismatches.append(
                f"{name}: direct {version}, lock {locked_entry[1]}"
            )
    if mismatches:
        raise LockError("direct/lock mismatch: " + "; ".join(mismatches))
    _assert_cpu_torch_contract(locked)
    local_mismatches = []
    for canonical, (version, digest) in local_wheels.items():
        entry = locked.get(canonical)
        if entry is None:
            local_mismatches.append(f"{canonical}: missing")
        elif entry[1:] != (version, digest):
            local_mismatches.append(
                f"{canonical}: manifest {version}/{digest}, "
                f"lock {entry[1]}/{entry[2]}"
            )
    if local_mismatches:
        raise LockError("local-wheel/lock mismatch: " + "; ".join(local_mismatches))
    print(
        f"PASS: {len(direct)} direct pins; {len(locked)} locked wheels; "
        "all exact and SHA-256-bound"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--direct", type=Path, default=DEFAULT_DIRECT)
    generate_parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    generate_parser.add_argument("--output", type=Path)
    generate_parser.add_argument("--bootstrap-installed", action="store_true")
    generate_parser.add_argument("--refresh-all", action="store_true")
    generate_parser.add_argument("--upgrade-package", action="append", default=[])
    generate_parser.set_defaults(handler=generate)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--direct", type=Path, default=DEFAULT_DIRECT)
    verify_parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    verify_parser.set_defaults(handler=verify)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        args.handler(args)
    except (LockError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
