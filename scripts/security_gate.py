"""Fail-closed local secret scan and security-exception validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SECRET_RULES = {
    "private-key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "github-fine-grained-token": re.compile(
        r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"
    ),
    "openai-key": re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    "anthropic-key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "pb-test-secret": re.compile(r"\bPB_TEST_SECRET_[A-Z0-9]{20}\b"),
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema in {path}")
    return payload


def _validate_exceptions(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"entries must be a list in {path}")
    today = date.today()
    required = {"id", "owner", "expires_on", "reason", "scope"}
    for entry in entries:
        if not required.issubset(entry):
            raise ValueError(f"Incomplete security exception: {entry!r}")
        if date.fromisoformat(str(entry["expires_on"])) < today:
            raise ValueError(
                f"Expired security exception: {entry['id']} "
                f"({entry['expires_on']})"
            )
    return entries


def _load_allowlist(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _load_json(path)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"entries must be a list in {path}")
    today = date.today()
    required = {
        "path",
        "rule",
        "content_sha256",
        "owner",
        "expires_on",
        "reason",
    }
    for entry in entries:
        if not required.issubset(entry):
            raise ValueError(f"Incomplete secret allowlist entry: {entry!r}")
        if date.fromisoformat(str(entry["expires_on"])) < today:
            raise ValueError(
                f"Expired secret allowlist entry: {entry['path']} "
                f"({entry['expires_on']})"
            )
        if "object_id" in entry and not re.fullmatch(
            r"[0-9a-f]{40}",
            str(entry["object_id"]),
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                f"Invalid historical blob object_id for {entry['path']}"
            )
        if not re.fullmatch(
            r"[0-9a-f]{64}",
            str(entry["content_sha256"]),
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                f"Invalid content_sha256 for {entry['path']}"
            )
    return entries


def _tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [
        root / value.decode("utf-8", errors="strict")
        for value in result.stdout.split(b"\0")
        if value and (root / value.decode("utf-8", errors="strict")).is_file()
    ]


def _is_binary(path: Path) -> bool:
    with path.open("rb") as stream:
        return b"\0" in stream.read(8192)


def _scan_text(
    relative: str,
    text: str,
    source: str,
    object_id: str | None = None,
    content_sha256: str | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule_id, pattern in SECRET_RULES.items():
            if pattern.search(line):
                finding = {
                    "path": relative,
                    "line": line_number,
                    "rule": rule_id,
                    "source": source,
                    "secret": "[REDACTED]",
                }
                if object_id is not None:
                    finding["object_id"] = object_id
                if content_sha256 is not None:
                    finding["content_sha256"] = content_sha256
                findings.append(finding)
    return findings


def _scan_file(root: Path, path: Path) -> list[dict[str, Any]]:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    payload = path.read_bytes()
    return _scan_text(
        relative,
        payload.decode("utf-8", errors="replace"),
        "working-tree",
        content_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _history_text_blobs(
    root: Path,
) -> tuple[list[tuple[str, list[str], str, str]], int]:
    objects = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    ).stdout.splitlines()
    names: dict[str, set[str]] = {}
    for line in objects:
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1]:
            names.setdefault(parts[0], set()).add(parts[1].replace("\\", "/"))
    if not names:
        return [], 0

    check = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=root,
        check=True,
        input="\n".join(names) + "\n",
        capture_output=True,
        text=True,
        encoding="ascii",
        errors="strict",
    ).stdout.splitlines()
    blobs = [
        (parts[0], sorted(names[parts[0]]))
        for line in check
        if len(parts := line.split(" ")) == 2 and parts[1] == "blob"
    ]

    text_blobs: list[tuple[str, list[str], str, str]] = []
    binary_count = 0
    for object_id, relative_paths in blobs:
        payload = subprocess.run(
            ["git", "cat-file", "blob", object_id],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if b"\0" in payload[:8192]:
            binary_count += 1
            continue
        text_blobs.append(
            (
                object_id,
                relative_paths,
                payload.decode("utf-8", errors="replace"),
                hashlib.sha256(payload).hexdigest(),
            )
        )
    return text_blobs, binary_count


def _write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _secrets(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    allowlist = _load_allowlist(args.allowlist)
    if args.path:
        files = [(root / value).resolve() for value in args.path]
    else:
        files = _tracked_files(root)

    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Secret-scan inputs missing: {missing}")

    findings: list[dict[str, Any]] = []
    scanned = 0
    skipped_binary = 0
    for path in files:
        if _is_binary(path):
            skipped_binary += 1
            continue
        scanned += 1
        findings.extend(_scan_file(root, path))
    history_scanned = 0
    history_binary_skipped = 0
    if args.history:
        history_blobs, history_binary_skipped = _history_text_blobs(root)
        history_scanned = sum(len(paths) for _, paths, _, _ in history_blobs)
        for object_id, relative_paths, text, content_sha256 in history_blobs:
            for relative in relative_paths:
                findings.extend(
                    _scan_text(
                        relative,
                        text,
                        f"git-object:{object_id}",
                        object_id=object_id,
                        content_sha256=content_sha256,
                    )
                )

    unique_findings: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (
            finding["path"],
            finding["line"],
            finding["rule"],
            finding["source"],
        )
        unique_findings[key] = finding
    findings = list(unique_findings.values())

    active: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    for finding in findings:
        exception = next(
            (
                entry
                for entry in allowlist
                if entry["path"] == finding["path"]
                and entry["rule"] == finding["rule"]
                and entry["content_sha256"] == finding.get("content_sha256")
                and (
                    finding["source"] == "working-tree"
                    or entry.get("object_id") == finding.get("object_id")
                )
            ),
            None,
        )
        if exception is None:
            active.append(finding)
        else:
            allowed.append(
                {
                    **finding,
                    "owner": exception["owner"],
                    "expires_on": exception["expires_on"],
                }
            )

    report = {
        "schema_version": 1,
        "files_considered": len(files),
        "files_scanned": scanned,
        "binary_files_skipped": skipped_binary,
        "history_text_blobs_scanned": history_scanned,
        "history_binary_blobs_skipped": history_binary_skipped,
        "findings": active,
        "allowlisted": allowed,
    }
    _write_report(args.output, report)

    if args.expect_findings:
        if not active:
            print("SECRET_NEGATIVE_FIXTURE_FAILED no finding", file=sys.stderr)
            return 1
        print(f"SECRET_NEGATIVE_FIXTURE_PASS findings={len(active)}")
        return 0
    if args.expect_all_rules:
        detected_rules = {finding["rule"] for finding in active}
        expected_rules = set(SECRET_RULES)
        if detected_rules != expected_rules:
            missing_rules = sorted(expected_rules - detected_rules)
            unexpected_rules = sorted(detected_rules - expected_rules)
            print(
                "SECRET_RULE_FIXTURE_FAILED "
                f"missing={missing_rules} unexpected={unexpected_rules}",
                file=sys.stderr,
            )
            return 1
        print(
            f"SECRET_RULE_FIXTURE_PASS rules={len(detected_rules)} "
            f"findings={len(active)}"
        )
        return 0
    if active:
        for finding in active:
            print(
                f"SECRET {finding['rule']} {finding['path']}:{finding['line']}",
                file=sys.stderr,
            )
        return 1
    print(
        f"SECRET_SCAN_PASS scanned={scanned} "
        f"binary_skipped={skipped_binary} history_scanned={history_scanned} "
        f"allowlisted={len(allowed)}"
    )
    return 0


def _read_report(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Security report missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _pip_audit_report(args: argparse.Namespace) -> int:
    payload = _read_report(args.report)
    dependencies = payload.get("dependencies") if isinstance(payload, dict) else None
    if not isinstance(dependencies, list):
        raise ValueError("pip-audit report has no dependencies list")
    if not isinstance(payload.get("fixes"), list):
        raise ValueError("pip-audit report has no fixes list")
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, dict):
            raise ValueError(f"pip-audit dependency {index} is not an object")
        if not str(dependency.get("name", "")).strip():
            raise ValueError(f"pip-audit dependency {index} has no name")
        if not str(dependency.get("version", "")).strip():
            raise ValueError(
                f"pip-audit dependency {dependency.get('name')} has no version"
            )
        vulnerabilities = dependency.get("vulns")
        if not isinstance(vulnerabilities, list):
            raise ValueError(
                f"pip-audit dependency {dependency['name']} has no vulns list"
            )
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ValueError("pip-audit vulnerability is not an object")
            if not str(vulnerability.get("id", "")).strip():
                raise ValueError("pip-audit vulnerability has no advisory ID")
            if not isinstance(vulnerability.get("fix_versions"), list):
                raise ValueError(
                    "pip-audit vulnerability has no fix_versions list"
                )
    vulnerable = [
        dependency
        for dependency in dependencies
        if isinstance(dependency, dict) and dependency.get("vulns")
    ]
    if args.expect_clean:
        if len(dependencies) < args.minimum_dependencies:
            raise ValueError(
                "pip-audit production report is incomplete: "
                f"{len(dependencies)} < {args.minimum_dependencies}"
            )
        if vulnerable:
            raise ValueError("pip-audit production report contains vulnerabilities")
    else:
        match = next(
            (
                dependency
                for dependency in vulnerable
                if str(dependency.get("name", "")).lower()
                == args.expect_package.lower()
                and str(dependency.get("version", "")) == args.expect_version
            ),
            None,
        )
        if match is None:
            raise ValueError(
                "Expected vulnerable Python package/version was not reported"
            )
        advisory_ids = [
            str(vulnerability.get("id", ""))
            for vulnerability in match["vulns"]
            if isinstance(vulnerability, dict)
        ]
        if not any(
            re.fullmatch(r"(?:PYSEC|GHSA|CVE)-[A-Za-z0-9-]+", advisory_id)
            for advisory_id in advisory_ids
        ):
            raise ValueError("Expected Python vulnerability has no advisory ID")
    print(
        f"PIP_AUDIT_REPORT_PASS dependencies={len(dependencies)} "
        f"vulnerable={len(vulnerable)}"
    )
    return 0


def _nuget_vulnerable_packages(
    payload: Any,
    expected_project: str,
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("NuGet audit report is not output version 1")
    parameters = payload.get("parameters")
    if not isinstance(parameters, str) or not {
        "--vulnerable",
        "--include-transitive",
    }.issubset(parameters.split()):
        raise ValueError("NuGet report parameters do not describe a full audit")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources or not all(
        isinstance(source, str) and source.strip() for source in sources
    ):
        raise ValueError("NuGet audit report has no vulnerability sources")
    projects = payload.get("projects") if isinstance(payload, dict) else None
    if not isinstance(projects, list) or len(projects) != 1:
        raise ValueError("NuGet audit report must contain exactly one project")
    packages: list[dict[str, Any]] = []
    framework_count = 0
    for project in projects:
        if not isinstance(project, dict):
            raise ValueError("NuGet audit project is not an object")
        actual_path = str(project.get("path", "")).replace("\\", "/").lower()
        normalized_expected = expected_project.replace("\\", "/").lower()
        if not actual_path or not (
            actual_path == normalized_expected
            or actual_path.endswith(f"/{normalized_expected}")
        ):
            raise ValueError(
                "NuGet audit project mismatch: "
                f"{project.get('path')} != {expected_project}"
            )
        frameworks = project.get("frameworks")
        if frameworks is None:
            continue
        if not isinstance(frameworks, list) or not frameworks:
            raise ValueError("NuGet audit project frameworks are malformed")
        framework_count += len(frameworks)
        for framework in frameworks:
            if not isinstance(framework, dict) or not str(
                framework.get("framework", "")
            ).strip():
                raise ValueError("NuGet audit framework record is incomplete")
            for key in ("topLevelPackages", "transitivePackages"):
                records = framework.get(key, [])
                if not isinstance(records, list):
                    raise ValueError(f"NuGet audit field {key} is not a list")
                for record in records:
                    if not isinstance(record, dict):
                        raise ValueError("NuGet audit package is not an object")
                    if not str(record.get("id", "")).strip() or not str(
                        record.get("resolvedVersion", "")
                    ).strip():
                        raise ValueError("NuGet audit package is incomplete")
                    vulnerabilities = record.get("vulnerabilities")
                    if not isinstance(vulnerabilities, list) or not vulnerabilities:
                        raise ValueError(
                            "NuGet vulnerable package has no vulnerabilities"
                        )
                    for vulnerability in vulnerabilities:
                        if not isinstance(vulnerability, dict):
                            raise ValueError(
                                "NuGet vulnerability is not an object"
                            )
                        if not str(vulnerability.get("severity", "")).strip():
                            raise ValueError("NuGet vulnerability has no severity")
                        if not str(vulnerability.get("advisoryurl", "")).strip():
                            raise ValueError(
                                "NuGet vulnerability has no advisory URL"
                            )
                    packages.append(record)
    return packages, framework_count


def _nuget_audit_report(args: argparse.Namespace) -> int:
    reports = [_read_report(path) for path in args.report]
    packages: list[dict[str, Any]] = []
    framework_count = 0
    if len(args.expect_project) != len(reports):
        raise ValueError(
            "Each NuGet audit report requires one matching --expect-project"
        )
    for payload, expected_project in zip(reports, args.expect_project, strict=True):
        report_packages, report_frameworks = _nuget_vulnerable_packages(
            payload,
            expected_project,
        )
        packages.extend(report_packages)
        framework_count += report_frameworks
    if args.expect_clean:
        if packages:
            raise ValueError("NuGet production reports contain vulnerabilities")
    else:
        match = next(
            (
                package
                for package in packages
                if str(package.get("id", "")).lower()
                == args.expect_package.lower()
                and str(package.get("resolvedVersion", ""))
                == args.expect_version
            ),
            None,
        )
        if match is None:
            raise ValueError("Expected vulnerable NuGet package/version was not reported")
        advisories = [
            str(vulnerability.get("advisoryurl", ""))
            for vulnerability in match["vulnerabilities"]
            if isinstance(vulnerability, dict)
        ]
        if not any(
            re.fullmatch(
                r"https://github\.com/advisories/(?:GHSA-[A-Za-z0-9-]+|CVE-[A-Za-z0-9-]+)",
                advisory,
                flags=re.IGNORECASE,
            )
            for advisory in advisories
        ):
            raise ValueError("Expected NuGet vulnerability has no advisory URL")
    print(
        f"NUGET_AUDIT_REPORT_PASS reports={len(reports)} "
        f"frameworks={framework_count} vulnerable={len(packages)}"
    )
    return 0


def _workflow_receipt(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit, flags=re.IGNORECASE):
        raise ValueError("Workflow receipt commit must be a 40-character Git SHA")
    payload = {
        "schema_version": 1,
        "gate": args.gate,
        "status": args.status,
        "commit_sha": args.commit.lower(),
        "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    if args.base or args.head:
        if not args.base or not args.head:
            raise ValueError("Workflow receipt base/head must be supplied together")
        for label, value in (("base", args.base), ("head", args.head)):
            if not re.fullmatch(r"[0-9a-f]{40}", value, flags=re.IGNORECASE):
                raise ValueError(
                    f"Workflow receipt {label} must be a 40-character Git SHA"
                )
        if args.head.lower() != args.commit.lower():
            raise ValueError("Workflow receipt head must equal commit SHA")
        if args.base.lower() == args.head.lower() or set(args.base) == {"0"}:
            raise ValueError("Workflow receipt requires a real non-identical base SHA")
        payload["base_sha"] = args.base.lower()
        payload["head_sha"] = args.head.lower()
    _write_report(args.output, payload)
    print(
        f"WORKFLOW_RECEIPT_PASS gate={args.gate} "
        f"status={args.status} commit={args.commit.lower()}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    secrets = subparsers.add_parser("secrets")
    secrets.add_argument("--root", type=Path, default=Path.cwd())
    secrets.add_argument("--allowlist", type=Path)
    secrets.add_argument("--output", type=Path)
    secrets.add_argument("--path", action="append", default=[])
    secrets.add_argument("--history", action="store_true")
    secrets.add_argument("--expect-findings", action="store_true")
    secrets.add_argument("--expect-all-rules", action="store_true")

    exceptions = subparsers.add_parser("exceptions")
    exceptions.add_argument(
        "--config",
        type=Path,
        default=Path("config/security-exceptions.json"),
    )

    pip_audit = subparsers.add_parser("pip-audit-report")
    pip_audit.add_argument("--report", type=Path, required=True)
    pip_mode = pip_audit.add_mutually_exclusive_group(required=True)
    pip_mode.add_argument("--expect-clean", action="store_true")
    pip_mode.add_argument("--expect-package")
    pip_audit.add_argument("--expect-version")
    pip_audit.add_argument("--minimum-dependencies", type=int, default=1)

    nuget_audit = subparsers.add_parser("nuget-audit-report")
    nuget_audit.add_argument("--report", type=Path, action="append", required=True)
    nuget_audit.add_argument(
        "--expect-project",
        action="append",
        required=True,
    )
    nuget_mode = nuget_audit.add_mutually_exclusive_group(required=True)
    nuget_mode.add_argument("--expect-clean", action="store_true")
    nuget_mode.add_argument("--expect-package")
    nuget_audit.add_argument("--expect-version")

    receipt = subparsers.add_parser("workflow-receipt")
    receipt.add_argument("--gate", required=True)
    receipt.add_argument("--status", required=True)
    receipt.add_argument("--commit", required=True)
    receipt.add_argument("--base")
    receipt.add_argument("--head")
    receipt.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "secrets":
        return _secrets(args)
    if args.command == "exceptions":
        entries = _validate_exceptions(args.config)
        print(f"SECURITY_EXCEPTIONS_PASS active={len(entries)}")
        return 0
    if args.command == "pip-audit-report":
        if not args.expect_clean and not args.expect_version:
            parser.error("--expect-version is required with --expect-package")
        return _pip_audit_report(args)
    if args.command == "nuget-audit-report":
        if not args.expect_clean and not args.expect_version:
            parser.error("--expect-version is required with --expect-package")
        return _nuget_audit_report(args)
    return _workflow_receipt(args)


if __name__ == "__main__":
    raise SystemExit(main())
