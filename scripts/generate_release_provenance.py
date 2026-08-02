"""Generate a lock-derived CycloneDX SBOM and a release provenance receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)(?:\s+|$)(.*)$"
)
SHA256_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")
LOCK_PATHS = (
    "requirements.txt",
    "requirements-direct.txt",
    "global.json",
    "PBStudio.UI/packages.lock.json",
    "PBStudio.UI/PBStudio.UI.csproj",
    "PBStudio.UI.Tests/packages.lock.json",
    "PBStudio.UI.Tests/PBStudio.UI.Tests.csproj",
    "config/python-wheel-overrides.json",
    "config/pip-audit-2.10.1-win-py311.lock",
    "config/python-sca-exceptions.json",
    "config/directml-asset-bundle.json",
    "config/directml-model-assets.json",
    ".mcp.json",
    ".codex/config.toml",
    "tools/mcp-node/.npmrc",
    "tools/mcp-node/package.json",
    "tools/mcp-node/package-lock.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(root: Path, path: Path) -> str:
    root = root.resolve()
    path = path.resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        args,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    return result.stdout.strip()


def _git_state(root: Path) -> dict[str, object]:
    status = _run(root, "git", "status", "--porcelain=v1", "--untracked-files=all")
    paths = sorted(line[3:] for line in status.splitlines() if len(line) >= 4)
    return {
        "commit_sha": _run(root, "git", "rev-parse", "HEAD"),
        "branch": _run(root, "git", "branch", "--show-current"),
        "dirty": bool(paths),
        "dirty_paths": paths,
    }


def _python_components(lock_path: Path) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT_RE.match(line.strip())
        if not match:
            continue
        name, version, suffix = match.groups()
        normalized = name.lower().replace("_", "-")
        hashes = [
            {"alg": "SHA-256", "content": value}
            for value in SHA256_RE.findall(suffix)
        ]
        if not hashes:
            raise ValueError(f"Python lock entry has no SHA-256: {name}=={version}")
        component: dict[str, object] = {
            "type": "library",
            "bom-ref": f"pkg:pypi/{quote(normalized)}@{quote(version)}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{quote(normalized)}@{quote(version)}",
            "hashes": hashes,
            "properties": [{"name": "pb-studio:ecosystem", "value": "python"}],
        }
        components.append(component)
    if not components:
        raise ValueError("Python lock produced no components")
    return components


def _nuget_components(
    lock_path: Path,
    lock_source: str,
) -> list[dict[str, object]]:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    resolved: dict[tuple[str, str], dict[str, object]] = {}
    for framework, packages in payload.get("dependencies", {}).items():
        for name, record in packages.items():
            if str(record.get("type", "")).lower() == "project":
                continue
            version = str(record.get("resolved", "")).strip()
            content_hash = str(record.get("contentHash", "")).strip()
            if not version or not content_hash:
                raise ValueError(f"Incomplete NuGet lock entry: {framework}/{name}")
            key = (name, version)
            item = resolved.setdefault(
                key,
                {
                    "type": "library",
                    "bom-ref": f"pkg:nuget/{quote(name)}@{quote(version)}",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:nuget/{quote(name)}@{quote(version)}",
                    "properties": [
                        {"name": "pb-studio:ecosystem", "value": "nuget"},
                        {"name": "nuget:contentHash", "value": content_hash},
                        {"name": "pb-studio:lock-source", "value": lock_source},
                    ],
                },
            )
            frameworks = next(
                (
                    prop
                    for prop in item["properties"]
                    if prop["name"] == "pb-studio:frameworks"
                ),
                None,
            )
            if frameworks is None:
                item["properties"].append(
                    {"name": "pb-studio:frameworks", "value": framework}
                )
            elif framework not in frameworks["value"].split(","):
                frameworks["value"] += f",{framework}"
    if not resolved:
        raise ValueError("NuGet lock produced no components")
    return [resolved[key] for key in sorted(resolved)]


def _deduplicate_nuget_components(
    components: list[dict[str, object]],
) -> list[dict[str, object]]:
    deduplicated: dict[str, dict[str, object]] = {}
    for component in components:
        bom_ref = str(component["bom-ref"])
        existing = deduplicated.get(bom_ref)
        if existing is None:
            deduplicated[bom_ref] = component
            continue
        for field in ("type", "name", "version", "purl"):
            if existing[field] != component[field]:
                raise ValueError(f"Conflicting NuGet component {bom_ref}: {field}")
        existing_properties = {
            str(item["name"]): str(item["value"])
            for item in existing["properties"]
        }
        new_properties = {
            str(item["name"]): str(item["value"])
            for item in component["properties"]
        }
        if (
            existing_properties["nuget:contentHash"]
            != new_properties["nuget:contentHash"]
        ):
            raise ValueError(f"Conflicting NuGet content hash: {bom_ref}")
        for property_name in ("pb-studio:frameworks", "pb-studio:lock-source"):
            merged = sorted(
                set(existing_properties[property_name].split(","))
                | set(new_properties[property_name].split(","))
            )
            for item in existing["properties"]:
                if item["name"] == property_name:
                    item["value"] = ",".join(merged)
                    break
    return [deduplicated[key] for key in sorted(deduplicated)]


def _asset_components(manifest_path: Path) -> list[dict[str, object]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("approval_status") != "approved":
        raise ValueError("DirectML asset manifest is not approved")
    components: list[dict[str, object]] = []
    for record in manifest.get("files", []):
        if record.get("kind") not in {"model", "runtime"}:
            continue
        source = record.get("source", {})
        license_record = record.get("license", {})
        target = str(record["target"])
        components.append(
            {
                "type": (
                    "machine-learning-model"
                    if record["kind"] == "model"
                    else "file"
                ),
                "bom-ref": f"asset:{target}",
                "name": Path(target).name,
                "version": str(manifest["bundle_version"]),
                "hashes": [{"alg": "SHA-256", "content": record["sha256"]}],
                "licenses": [{"expression": license_record["spdx"]}],
                "properties": [
                    {"name": "pb-studio:target", "value": target},
                    {
                        "name": "pb-studio:source-repository",
                        "value": source["repository"],
                    },
                    {
                        "name": "pb-studio:source-revision",
                        "value": source["revision"],
                    },
                    {"name": "pb-studio:source-file", "value": source["file"]},
                    {
                        "name": "pb-studio:source-sha256",
                        "value": source["sha256"],
                    },
                ],
            }
        )
    if not components:
        raise ValueError("DirectML manifest produced no model/runtime components")
    return components


def _dotnet_state(root: Path) -> dict[str, object]:
    return {
        "selected_sdk": _run(root, "dotnet", "--version"),
        "installed_sdks": _run(root, "dotnet", "--list-sdks").splitlines(),
    }


def _artifact_records(
    root: Path,
    artifacts: list[tuple[str, str]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: dict[Path, str] = {}
    for value, kind in artifacts:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if path in seen:
            if seen[path] != kind:
                raise ValueError(
                    f"Release artifact has conflicting types: {path} "
                    f"({seen[path]} and {kind})"
                )
            continue
        seen[path] = kind
        if not path.is_file():
            raise FileNotFoundError(f"Release artifact not found: {path}")
        if kind == "application":
            _validate_application_artifact(path)
        records.append(
            {
                "path": _display_path(root, path),
                "kind": kind,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return records


def _validate_application_artifact(path: Path) -> None:
    required_package_names = {
        "pbstudio.ui.exe",
        "pbstudio.ui.dll",
        "pbstudio.ui.deps.json",
        "pbstudio.ui.runtimeconfig.json",
    }
    if path.suffix.lower() == ".exe":
        if path.name.lower() != "pbstudio.ui.exe":
            raise ValueError(
                f"Application executable must be named PBStudio.UI.exe: {path}"
            )
        with path.open("rb") as executable:
            magic = executable.read(2)
        if magic != b"MZ":
            raise ValueError(f"Application executable is not a PE image: {path}")
        return
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                normalized = {
                    Path(name.replace("\\", "/")).name.lower(): name
                    for name in archive.namelist()
                    if not name.endswith("/")
                }
                missing = required_package_names - normalized.keys()
                if missing:
                    raise ValueError(
                        "Application ZIP is incomplete; missing: "
                        + ", ".join(sorted(missing))
                    )
                with archive.open(normalized["pbstudio.ui.exe"]) as executable:
                    if executable.read(2) != b"MZ":
                        raise ValueError(
                            "PBStudio.UI.exe in application ZIP is not a PE image"
                        )
        except zipfile.BadZipFile as error:
            raise ValueError(f"Application artifact is not a valid ZIP: {path}") from error
        return
    raise ValueError(
        "Application artifact must be PBStudio.UI.exe or a complete WPF publish ZIP"
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-provenance",
        help="Output directory below the repository unless absolute.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help=(
            "Built WPF application, installer or release package to bind; "
            "repeat as needed."
        ),
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail unless the repository has no tracked or untracked changes.",
    )
    parser.add_argument(
        "--allow-unmaterialized-runtime",
        action="store_true",
        help="Generate metadata/SBOM without requiring installed NumPy; never release-eligible.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir = output_dir.resolve()

    git_state = _git_state(root)
    if args.require_clean and git_state["dirty"]:
        print("Release provenance refused: repository is dirty.", file=sys.stderr)
        return 2

    lock_records = []
    for relative in LOCK_PATHS:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required lock/provenance input missing: {relative}")
        lock_records.append(
            {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)}
        )

    directml_manifest_path = root / "config/directml-asset-bundle.json"
    directml_manifest = json.loads(
        directml_manifest_path.read_text(encoding="utf-8")
    )
    default_bundle = root / "release-assets" / directml_manifest["archive"]["file_name"]
    artifact_inputs = [(value, "application") for value in args.artifact]
    if default_bundle.is_file():
        artifact_inputs.append((str(default_bundle), "directml-assets"))
    artifacts = _artifact_records(root, artifact_inputs)
    if default_bundle.is_file():
        archive_record = next(
            record
            for record in artifacts
            if record["path"] == default_bundle.relative_to(root).as_posix()
        )
        expected_archive = directml_manifest["archive"]
        if (
            archive_record["size"] != expected_archive["size"]
            or archive_record["sha256"] != expected_archive["sha256"]
        ):
            raise ValueError("DirectML release archive does not match its manifest")

    dotnet_state = _dotnet_state(root)
    expected_dotnet = json.loads(
        (root / "global.json").read_text(encoding="utf-8")
    )["sdk"]["version"]
    if dotnet_state["selected_sdk"] != expected_dotnet:
        raise ValueError(
            "Selected .NET SDK does not match global.json: "
            f"{dotnet_state['selected_sdk']} != {expected_dotnet}"
        )
    if sys.version_info[:2] != (3, 11):
        raise ValueError(f"Release provenance requires Python 3.11, got {sys.version}")
    try:
        numpy_version = importlib.metadata.version("numpy")
    except importlib.metadata.PackageNotFoundError:
        numpy_version = None
    if not args.allow_unmaterialized_runtime and numpy_version != "1.26.4":
        raise ValueError(
            f"Release provenance requires NumPy 1.26.4, got {numpy_version}"
        )
    numpy_contract = numpy_version == "1.26.4"

    nuget_components = _deduplicate_nuget_components(
        _nuget_components(
            root / "PBStudio.UI/packages.lock.json",
            "PBStudio.UI/packages.lock.json",
        )
        + _nuget_components(
            root / "PBStudio.UI.Tests/packages.lock.json",
            "PBStudio.UI.Tests/packages.lock.json",
        )
    )
    components = (
        _python_components(root / "requirements.txt")
        + nuget_components
        + _asset_components(directml_manifest_path)
    )
    refs = [str(component["bom-ref"]) for component in components]
    if len(refs) != len(set(refs)):
        raise ValueError("SBOM contains duplicate bom-ref values")

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    serial_seed = "|".join(
        [str(git_state["commit_sha"])]
        + [str(record["sha256"]) for record in lock_records]
    )
    app_ref = f"application:pb-studio@{git_state['commit_sha']}"
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, serial_seed)}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "PB Studio release provenance generator",
                        "version": "1",
                    }
                ]
            },
            "component": {
                "type": "application",
                "bom-ref": app_ref,
                "name": "PB Studio AMD Edition",
                "version": str(git_state["commit_sha"]),
            },
        },
        "components": components,
        "dependencies": [{"ref": app_ref, "dependsOn": refs}],
    }
    sbom_path = output_dir / "sbom.cdx.json"
    _write_json(sbom_path, sbom)

    receipt = {
        "schema_version": 1,
        "generated_at": timestamp,
        "release_eligible": (
            not args.allow_unmaterialized_runtime
            and not git_state["dirty"]
            and any(record["kind"] == "application" for record in artifacts)
            and default_bundle.is_file()
            and numpy_contract
        ),
        "source": git_state,
        "contracts": {
            "python_3_11": True,
            "numpy_1_26_4": numpy_contract,
            "dotnet_matches_global_json": True,
            "directml_manifest_approved": True,
            "directml_archive_verified": default_bundle.is_file(),
            "application_artifact_verified": any(
                record["kind"] == "application" for record in artifacts
            ),
        },
        "environment": {
            "os": platform.platform(),
            "python": {
                "executable": str(Path(sys.executable).resolve()),
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "numpy": numpy_version,
            },
            "dotnet": dotnet_state,
        },
        "locks": lock_records,
        "sbom": {
            "path": _display_path(root, sbom_path),
            "size": sbom_path.stat().st_size,
            "sha256": _sha256(sbom_path),
            "components": len(components),
        },
        "artifacts": artifacts,
    }
    if not args.allow_unmaterialized_runtime and not receipt["release_eligible"]:
        raise ValueError(
            "Release provenance is not eligible: require a clean repository, "
            "verified DirectML archive and verified PBStudio.UI application artifact"
        )
    receipt_path = output_dir / "release-provenance.json"
    _write_json(receipt_path, receipt)
    print(
        "PROVENANCE_PASS "
        f"commit={git_state['commit_sha']} dirty={git_state['dirty']} "
        f"components={len(components)} artifacts={len(artifacts)} "
        f"receipt={receipt_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
