"""Fail-closed validator for a Spec-Driven Development feature workspace."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


SPEC_LIMIT_BYTES = 10_240
TASK_RE = re.compile(
    r"^- \[(?P<box> |X)\] "
    r"T(?P<id>\d{3}) "
    r"(?P<parallel>\[P\] )?"
    r"\[OBJ-(?P<objective>\d+)\] "
    r"(?P<refs>(?:\{\((?:FR|TR|OR|RR)-\d{3}\)\} )+)"
    r"(?P<description>\S.*)$"
)
TASK_LIKE_RE = re.compile(r"^- \[[^]]*\] T")
REF_RE = re.compile(r"\{\(((?:FR|TR|OR|RR)-\d{3})\)\}")
REQUIREMENT_RE = re.compile(r"\*\*((?:FR|TR|OR|RR)-\d{3}):\*\*")
OBJECTIVE_RE = re.compile(r"\*\*(OBJ-\d+):\*\*")
TASK_RANGE_RE = re.compile(r"\bT(\d{3})[–-]T(\d{3})\b")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
AUTHORITATIVE_RE = re.compile(r"^## Authoritative (OBJ-\d+) Gate\b")
REPO_PATH_RE = re.compile(r"`([^`]+)`")
CHECKBOX_RE = re.compile(r"^- \[([^]]*)\] ")
ARCHIVE_SOURCE_MAP = {
    "spec-through-obj71-2026-07-30.md": "spec.md",
    "plan-through-obj71-2026-07-30.md": "plan.md",
    "tasks-through-t369.md": "tasks.md",
    "qc-report-through-obj71-2026-07-30.md": "qc-report.md",
    "completed-through-obj71.txt": ".completed",
    "qc-passed-through-obj71.txt": ".qc-passed",
    "requirement-registry-through-obj71.md": (
        "generated registry over archived Spec and Tasks"
    ),
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class Task:
    identifier: int
    box: str
    objective: str
    requirements: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    phase: str
    findings: tuple[Finding, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _add(findings: list[Finding], code: str, path: Path, message: str) -> None:
    findings.append(Finding(code=code, path=str(path), message=message))


def _load_json(path: Path, findings: list[Finding], code: str) -> dict | None:
    try:
        value = json.loads(_read_text(path))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _add(findings, code, path, f"invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        _add(findings, code, path, "JSON root must be an object")
        return None
    return value


def _safe_child(feature: Path, relative: object) -> Path | None:
    if not isinstance(relative, str):
        return None
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_feature = feature.resolve()
    resolved_candidate = (feature / candidate).resolve()
    if not resolved_candidate.is_relative_to(resolved_feature):
        return None
    return resolved_candidate


def _parse_tasks(path: Path, findings: list[Finding]) -> list[Task]:
    tasks: list[Task] = []
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        if not TASK_LIKE_RE.match(line):
            continue
        match = TASK_RE.fullmatch(line)
        if match is None:
            _add(
                findings,
                "TASK_FORMAT",
                path,
                f"line {line_number} is not canonical: {line}",
            )
            continue
        repo_paths = REPO_PATH_RE.findall(match.group("description"))
        if not repo_paths:
            _add(
                findings,
                "TASK_PATH_MISSING",
                path,
                f"line {line_number} has no backtick repository path",
            )
        for repo_path in repo_paths:
            normalized = Path(repo_path.replace("\\", "/"))
            if normalized.is_absolute() or ".." in normalized.parts:
                _add(
                    findings,
                    "TASK_PATH_INVALID",
                    path,
                    f"line {line_number} has unsafe path: {repo_path}",
                )
        tasks.append(
            Task(
                identifier=int(match.group("id")),
                box=match.group("box"),
                objective=f"OBJ-{match.group('objective')}",
                requirements=tuple(REF_RE.findall(match.group("refs"))),
                raw=line,
            )
        )
    return tasks


def _task_digest(tasks: list[Task], start: int, end: int) -> str:
    selected = [task.raw for task in tasks if start <= task.identifier <= end]
    payload = ("\n".join(selected) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_marker_range(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"T(\d{3})-T(\d{3})", value)
    if match is None:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    return (start, end) if start <= end else None


def _validate_evidence_reference(
    feature: Path,
    marker: dict,
    marker_path: Path,
    findings: list[Finding],
    prefix: str,
) -> None:
    evidence = _safe_child(feature, marker.get("evidence_manifest"))
    if evidence is None:
        _add(findings, f"{prefix}_EVIDENCE_PATH", marker_path, "unsafe evidence path")
        return
    if not evidence.is_file():
        _add(findings, f"{prefix}_EVIDENCE_MISSING", evidence, "evidence manifest missing")
        return
    expected = marker.get("evidence_manifest_sha256")
    if expected != sha256_file(evidence):
        _add(findings, f"{prefix}_EVIDENCE_DIGEST", evidence, "evidence digest mismatch")
        return
    manifest = _load_json(evidence, findings, f"{prefix}_EVIDENCE_JSON")
    if manifest is None:
        return
    required = {
        "schema_version",
        "objective",
        "task_range",
        "receipts",
        "artifact_hashes",
        "review_status",
        "open_blockers",
        "commit_sha",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        _add(
            findings,
            f"{prefix}_EVIDENCE_FIELDS",
            evidence,
            f"missing fields: {', '.join(missing)}",
        )
        return
    if (
        manifest.get("schema_version") != 1
        or manifest.get("objective") != marker.get("objective")
        or manifest.get("task_range") != marker.get("task_range")
        or manifest.get("commit_sha") != marker.get("commit_sha")
        or manifest.get("review_status") != "PASS"
        or manifest.get("open_blockers") != []
        or not isinstance(manifest.get("receipts"), list)
        or not manifest["receipts"]
        or not isinstance(manifest.get("artifact_hashes"), list)
        or not manifest["artifact_hashes"]
    ):
        _add(findings, f"{prefix}_EVIDENCE_SCHEMA", evidence, "evidence schema invalid")
        return
    task_range = _parse_marker_range(marker.get("task_range"))
    if task_range is None:
        return
    start, end = task_range
    commit_sha = str(marker.get("commit_sha", ""))
    seen_tasks: set[str] = set()
    for receipt in manifest["receipts"]:
        if not isinstance(receipt, dict):
            _add(findings, f"{prefix}_RECEIPT_SCHEMA", evidence, "receipt must be object")
            continue
        task_id = receipt.get("task_id")
        match = re.fullmatch(r"T(\d{3})", str(task_id))
        if (
            match is None
            or not start <= int(match.group(1)) <= end
            or task_id in seen_tasks
        ):
            _add(findings, f"{prefix}_RECEIPT_TASK", evidence, "receipt task invalid")
            continue
        seen_tasks.add(str(task_id))
        _validate_hashed_path(
            feature,
            receipt,
            evidence,
            findings,
            f"{prefix}_RECEIPT",
        )
        _validate_commit_bound_path(
            feature,
            commit_sha,
            receipt,
            evidence,
            findings,
            f"{prefix}_RECEIPT",
        )
    expected_tasks = {f"T{identifier:03d}" for identifier in range(start, end + 1)}
    if seen_tasks != expected_tasks:
        missing = ", ".join(sorted(expected_tasks - seen_tasks))
        _add(
            findings,
            f"{prefix}_RECEIPT_COVERAGE",
            evidence,
            f"receipt coverage incomplete: {missing}",
        )
    seen_artifacts: set[str] = set()
    for artifact in manifest["artifact_hashes"]:
        if not isinstance(artifact, dict) or artifact.get("path") in seen_artifacts:
            _add(findings, f"{prefix}_ARTIFACT_SCHEMA", evidence, "artifact invalid")
            continue
        seen_artifacts.add(str(artifact.get("path")))
        _validate_hashed_path(
            feature,
            artifact,
            evidence,
            findings,
            f"{prefix}_ARTIFACT",
        )
        _validate_commit_bound_path(
            feature,
            commit_sha,
            artifact,
            evidence,
            findings,
            f"{prefix}_ARTIFACT",
        )
    required_artifacts = (
        {"tasks.md"}
        if prefix == "COMPLETED"
        else {"tasks.md", "qc-report.md", ".completed"}
    )
    if not required_artifacts.issubset(seen_artifacts):
        missing = ", ".join(sorted(required_artifacts - seen_artifacts))
        _add(
            findings,
            f"{prefix}_ARTIFACT_COVERAGE",
            evidence,
            f"required artifacts missing: {missing}",
        )
    committed_digest = _task_digest_at_commit(feature, commit_sha, start, end)
    if committed_digest is None or committed_digest != marker.get("task_digest_sha256"):
        _add(
            findings,
            f"{prefix}_TASK_COMMIT",
            evidence,
            "task range is not bound to commit_sha",
        )


def _validate_hashed_path(
    feature: Path,
    entry: dict,
    owner: Path,
    findings: list[Finding],
    code: str,
) -> None:
    path = _safe_child(feature, entry.get("path"))
    expected = entry.get("sha256")
    if path is None:
        _add(findings, f"{code}_PATH", owner, "unsafe or missing path")
    elif not path.is_file():
        _add(findings, f"{code}_MISSING", path, "referenced file missing")
    elif not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        _add(findings, f"{code}_HASH", owner, "sha256 must be 64 lowercase hex")
    elif sha256_file(path) != expected:
        _add(findings, f"{code}_HASH", path, "referenced file digest mismatch")


def _validate_commit_bound_path(
    feature: Path,
    commit_sha: str,
    entry: dict,
    owner: Path,
    findings: list[Finding],
    code: str,
) -> None:
    relative = entry.get("path")
    path = _safe_child(feature, relative)
    if path is None or not COMMIT_RE.fullmatch(commit_sha):
        return
    source = _git_show(feature, commit_sha, str(relative))
    clean_blob = _git_clean_blob_sha(feature, str(relative), path)
    if source is None or clean_blob != _git_blob_sha(source):
        _add(
            findings,
            f"{code}_COMMIT",
            owner,
            f"{relative} is not byte-bound to commit_sha",
        )


def _repository_head(feature: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(feature), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    head = result.stdout.strip().lower()
    return head if COMMIT_RE.fullmatch(head) else None


def _repository_root(feature: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(feature), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    root = Path(result.stdout.strip()).resolve()
    return root if feature.resolve().is_relative_to(root) else None


def _commit_is_ancestor(feature: Path, commit_sha: str, head: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(feature), "merge-base", "--is-ancestor", commit_sha, head],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _commit_distance(feature: Path, commit_sha: str, head: str) -> int | None:
    result = subprocess.run(
        ["git", "-C", str(feature), "rev-list", "--count", f"{commit_sha}..{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def _git_show(feature: Path, commit_sha: str, source_path: str) -> bytes | None:
    root = _repository_root(feature)
    source = Path(source_path.replace("\\", "/"))
    if root is None or source.is_absolute() or ".." in source.parts:
        return None
    repo_relative = (feature.resolve().relative_to(root) / source).as_posix()
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{commit_sha}:{repo_relative}"],
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _task_digest_at_commit(
    feature: Path,
    commit_sha: str,
    start: int,
    end: int,
) -> str | None:
    source = _git_show(feature, commit_sha, "tasks.md")
    if source is None:
        return None
    try:
        lines = source.decode("utf-8-sig").splitlines()
    except UnicodeError:
        return None
    selected: list[str] = []
    identifiers: set[int] = set()
    for line in lines:
        if not TASK_LIKE_RE.match(line):
            continue
        match = TASK_RE.fullmatch(line)
        if match is None:
            return None
        identifier = int(match.group("id"))
        if start <= identifier <= end:
            selected.append(line)
            identifiers.add(identifier)
    if identifiers != set(range(start, end + 1)) or len(selected) != end - start + 1:
        return None
    payload = ("\n".join(selected) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _git_clean_blob_sha(feature: Path, source_path: str, archived: Path) -> str | None:
    root = _repository_root(feature)
    source = Path(source_path.replace("\\", "/"))
    if root is None or source.is_absolute() or ".." in source.parts:
        return None
    repo_relative = (feature.resolve().relative_to(root) / source).as_posix()
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "hash-object",
            f"--path={repo_relative}",
            str(archived),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip().lower()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def _validate_completed_marker(
    feature: Path,
    tasks: list[Task],
    objective: str,
    expected_range: tuple[int, int],
    repository_head: str | None,
    findings: list[Finding],
) -> None:
    path = feature / ".completed"
    marker = _load_json(path, findings, "COMPLETED_JSON")
    if marker is None:
        return
    required = {
        "schema_version",
        "objective",
        "phase",
        "task_range",
        "task_digest_sha256",
        "evidence_manifest",
        "evidence_manifest_sha256",
        "commit_sha",
    }
    missing = sorted(required - marker.keys())
    if missing:
        _add(findings, "COMPLETED_FIELDS", path, f"missing fields: {', '.join(missing)}")
        return
    marker_range = _parse_marker_range(marker.get("task_range"))
    if marker_range is None:
        _add(findings, "COMPLETED_RANGE", path, "invalid task range")
        return
    start, end = marker_range
    if marker_range != expected_range:
        _add(
            findings,
            "COMPLETED_RANGE",
            path,
            f"expected T{expected_range[0]:03d}-T{expected_range[1]:03d}",
        )
    selected = [task for task in tasks if start <= task.identifier <= end]
    expected_count = end - start + 1
    if len(selected) != expected_count or any(task.box != "X" for task in selected):
        _add(findings, "COMPLETED_TOO_EARLY", path, "implementation tasks remain open")
    if marker.get("task_digest_sha256") != _task_digest(tasks, start, end):
        _add(findings, "COMPLETED_TASK_DIGEST", path, "task digest mismatch")
    if marker.get("schema_version") != 1:
        _add(findings, "COMPLETED_SCHEMA", path, "schema_version must be 1")
    if marker.get("objective") != objective or marker.get("phase") != "implementation":
        _add(findings, "COMPLETED_IDENTITY", path, "objective or phase mismatch")
    commit_sha = str(marker.get("commit_sha", ""))
    if not COMMIT_RE.fullmatch(commit_sha):
        _add(findings, "MARKER_COMMIT", path, "commit_sha must be 40 lowercase hex")
    elif repository_head is None:
        _add(findings, "MARKER_GIT", path, "repository HEAD unavailable")
    elif not _commit_is_ancestor(feature, commit_sha, repository_head):
        _add(findings, "MARKER_COMMIT", path, "commit_sha is not an ancestor of HEAD")
    _validate_evidence_reference(feature, marker, path, findings, "COMPLETED")


def _validate_qc_marker(
    feature: Path,
    tasks: list[Task],
    objective: str,
    expected_range: tuple[int, int],
    repository_head: str | None,
    findings: list[Finding],
) -> None:
    path = feature / ".qc-passed"
    marker = _load_json(path, findings, "QC_JSON")
    if marker is None:
        return
    required = {
        "schema_version",
        "objective",
        "phase",
        "task_range",
        "task_digest_sha256",
        "completed_marker_sha256",
        "qc_report_sha256",
        "evidence_manifest",
        "evidence_manifest_sha256",
        "commit_sha",
    }
    missing = sorted(required - marker.keys())
    if missing:
        _add(findings, "QC_FIELDS", path, f"missing fields: {', '.join(missing)}")
        return
    completed = feature / ".completed"
    if not completed.is_file():
        _add(findings, "QC_BEFORE_IMPLEMENTATION", path, ".completed is missing")
    elif marker.get("completed_marker_sha256") != sha256_file(completed):
        _add(findings, "QC_COMPLETED_DIGEST", path, ".completed digest mismatch")
    marker_range = _parse_marker_range(marker.get("task_range"))
    if marker_range is None:
        _add(findings, "QC_RANGE", path, "invalid task range")
    else:
        start, end = marker_range
        if marker_range != expected_range:
            _add(
                findings,
                "QC_RANGE",
                path,
                f"expected T{expected_range[0]:03d}-T{expected_range[1]:03d}",
            )
        selected = [task for task in tasks if start <= task.identifier <= end]
        expected_count = end - start + 1
        if len(selected) != expected_count or any(task.box != "X" for task in selected):
            _add(findings, "QC_TOO_EARLY", path, "QC tasks remain open")
        if marker.get("task_digest_sha256") != _task_digest(tasks, start, end):
            _add(findings, "QC_TASK_DIGEST", path, "task digest mismatch")
    report = feature / "qc-report.md"
    if not report.is_file() or marker.get("qc_report_sha256") != sha256_file(report):
        _add(findings, "QC_REPORT_DIGEST", report, "QC report digest mismatch")
    if marker.get("schema_version") != 1:
        _add(findings, "QC_SCHEMA", path, "schema_version must be 1")
    if marker.get("objective") != objective or marker.get("phase") != "qc":
        _add(findings, "QC_IDENTITY", path, "objective or phase mismatch")
    commit_sha = str(marker.get("commit_sha", ""))
    if not COMMIT_RE.fullmatch(commit_sha):
        _add(findings, "MARKER_COMMIT", path, "commit_sha must be 40 lowercase hex")
    elif repository_head is None:
        _add(findings, "MARKER_GIT", path, "repository HEAD unavailable")
    elif not _commit_is_ancestor(feature, commit_sha, repository_head):
        _add(findings, "MARKER_COMMIT", path, "commit_sha is not an ancestor of HEAD")
    else:
        distance = _commit_distance(feature, commit_sha, repository_head)
        if distance is None or distance > 1:
            _add(findings, "QC_GATE_COMMIT", path, "QC commit is not HEAD or its parent")
    _validate_evidence_reference(feature, marker, path, findings, "QC")


def _archive_anchor(spec: str) -> tuple[str, str] | None:
    lines = spec.splitlines()
    for index, line in enumerate(lines[:-1]):
        match = re.search(r"`history/(archive-manifest-[^`]+\.json)`", line)
        if not match:
            continue
        digest = re.search(r"SHA-256: `([0-9a-f]{64})`", lines[index + 1])
        if digest:
            return match.group(1), digest.group(1)
    return None


def _expected_requirement_registry(
    source_commit: str,
    spec_sha256: str,
    tasks_sha256: str,
) -> str:
    return (
        "# Requirement Registry through OBJ-71\n\n"
        f"- source_commit: `{source_commit}`\n"
        "- spec_path: `spec-through-obj71-2026-07-30.md`\n"
        f"- spec_sha256: `{spec_sha256}`\n"
        "- tasks_path: `tasks-through-t369.md`\n"
        f"- tasks_sha256: `{tasks_sha256}`\n"
        "- resolution: Exact OBJ/OR/FR/RR/TR/SC definitions resolve from the hashed\n"
        "  historical Spec; exact T001–T369 traceability resolves from the hashed\n"
        "  historical Tasks. Sparse historical requirement numbers are not invented.\n"
        "- next_namespace: `OBJ-72`, `OR-335`, `FR-337`, `RR-237`, `TR-346`,\n"
        "  `SC-076`, `T370`\n"
    )


def _validate_archive(feature: Path, spec: str, findings: list[Finding]) -> None:
    anchor = _archive_anchor(spec)
    if anchor is None:
        _add(findings, "ARCHIVE_ANCHOR", feature / "spec.md", "archive anchor missing")
        return
    anchored_name, anchored_digest = anchor
    manifests = sorted((feature / "history").glob("archive-manifest-*.json"))
    if len(manifests) != 1:
        _add(
            findings,
            "ARCHIVE_MANIFEST_COUNT",
            feature / "history",
            f"expected one archive manifest, found {len(manifests)}",
        )
        return
    manifest_path = manifests[0]
    if manifest_path.name != anchored_name or sha256_file(manifest_path) != anchored_digest:
        _add(findings, "ARCHIVE_ANCHOR", manifest_path, "archive manifest anchor mismatch")
        return
    manifest = _load_json(manifest_path, findings, "ARCHIVE_MANIFEST_JSON")
    if manifest is None:
        return
    if manifest.get("schema_version") != 1:
        _add(findings, "ARCHIVE_SCHEMA", manifest_path, "schema_version must be 1")
    if manifest.get("objective") != "OBJ-71" or not COMMIT_RE.fullmatch(
        str(manifest.get("source_commit", ""))
    ):
        _add(findings, "ARCHIVE_IDENTITY", manifest_path, "objective/source_commit invalid")
    source_commit = str(manifest.get("source_commit", ""))
    if _repository_head(feature) is None or not _commit_is_ancestor(
        feature,
        source_commit,
        _repository_head(feature) or "",
    ):
        _add(findings, "ARCHIVE_SOURCE_COMMIT", manifest_path, "source commit unavailable")
    files = manifest.get("files")
    if not isinstance(files, list):
        _add(findings, "ARCHIVE_FILES", manifest_path, "files must be an array")
        return
    required = set(ARCHIVE_SOURCE_MAP)
    seen: set[str] = set()
    entries_by_path: dict[str, dict] = {}
    for entry in files:
        if not isinstance(entry, dict):
            _add(findings, "ARCHIVE_ENTRY", manifest_path, "file entry must be an object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or relative in seen:
            _add(findings, "ARCHIVE_ENTRY", manifest_path, "path missing or duplicated")
            continue
        seen.add(relative)
        entries_by_path[relative] = entry
        archived = _safe_child(feature / "history", relative)
        if archived is None:
            _add(findings, "ARCHIVE_PATH_ESCAPE", manifest_path, f"unsafe path: {relative}")
            continue
        if not archived.is_file():
            _add(findings, "ARCHIVE_MISSING", archived, "archive file missing")
            continue
        if entry.get("bytes") != archived.stat().st_size:
            _add(findings, "ARCHIVE_BYTES", archived, "archive byte count mismatch")
        if entry.get("sha256") != sha256_file(archived):
            _add(findings, "ARCHIVE_HASH", archived, "archive digest mismatch")
        source_path = entry.get("source_path")
        git_blob = entry.get("git_blob")
        expected_source = ARCHIVE_SOURCE_MAP.get(relative)
        if expected_source is None or source_path != expected_source:
            _add(
                findings,
                "ARCHIVE_SOURCE_PATH",
                manifest_path,
                f"{relative} has unexpected source_path",
            )
            continue
        if relative == "requirement-registry-through-obj71.md":
            if git_blob is not None:
                _add(
                    findings,
                    "ARCHIVE_GIT_BLOB",
                    archived,
                    "generated registry must not claim a Git source blob",
                )
        else:
            if not isinstance(git_blob, str) or not re.fullmatch(
                r"[0-9a-f]{40}",
                git_blob,
            ):
                _add(findings, "ARCHIVE_GIT_BLOB", archived, "Git blob missing")
                continue
            source_bytes = _git_show(feature, source_commit, str(source_path))
            if source_bytes is None:
                _add(findings, "ARCHIVE_GIT_SOURCE", archived, "Git source unavailable")
            else:
                if git_blob != _git_blob_sha(source_bytes):
                    _add(findings, "ARCHIVE_GIT_BLOB", archived, "Git blob mismatch")
                clean_blob = _git_clean_blob_sha(feature, str(source_path), archived)
                if clean_blob != git_blob:
                    _add(
                        findings,
                        "ARCHIVE_GIT_CONTENT",
                        archived,
                        "worktree archive does not clean-filter to Git blob",
                    )
    missing = sorted(required - seen)
    unexpected = sorted(seen - required)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        _add(
            findings,
            "ARCHIVE_REQUIRED_FILE",
            manifest_path,
            "; ".join(details),
        )
    registry = feature / "history" / "requirement-registry-through-obj71.md"
    spec_entry = entries_by_path.get("spec-through-obj71-2026-07-30.md", {})
    tasks_entry = entries_by_path.get("tasks-through-t369.md", {})
    spec_digest = spec_entry.get("sha256")
    tasks_digest = tasks_entry.get("sha256")
    if (
        registry.is_file()
        and isinstance(spec_digest, str)
        and isinstance(tasks_digest, str)
        and _read_text(registry)
        != _expected_requirement_registry(source_commit, spec_digest, tasks_digest)
    ):
        _add(
            findings,
            "ARCHIVE_REGISTRY_CONTENT",
            registry,
            "generated registry is not deterministic from anchored archive entries",
        )


def _validate_qc_order(
    feature: Path,
    objective: str,
    qc_exists: bool,
    findings: list[Finding],
) -> None:
    report_path = feature / "qc-report.md"
    if not report_path.is_file():
        _add(findings, "QC_REPORT_MISSING", report_path, "QC report missing")
        return
    lines = _read_text(report_path).splitlines()
    heading_index = None
    heading_objective = None
    for index, line in enumerate(lines):
        match = AUTHORITATIVE_RE.match(line)
        if match:
            heading_index = index
            heading_objective = match.group(1)
            break
    if heading_index is None:
        _add(findings, "QC_STATUS_ORDER", report_path, "authoritative QC heading missing")
        return
    if heading_objective != objective:
        _add(findings, "QC_STATUS_ORDER", report_path, "current objective is not first")
    section: list[str] = []
    for line in lines[heading_index + 1 :]:
        if line.startswith("## "):
            break
        section.append(line)
    result_lines = [line for line in section if line.startswith("- **Overall result:**")]
    if len(result_lines) != 1:
        _add(findings, "QC_STATUS_ORDER", report_path, "exactly one current result required")
        return
    result = result_lines[0]
    if qc_exists:
        if result != "- **Overall result:** **PASSED / RELEASE-READY**.":
            _add(findings, "QC_STATUS_ORDER", report_path, "QC marker requires PASS status")
    elif result not in {
        "- **Overall result:** **REOPENED / NOT RELEASE-READY**.",
        "- **Overall result:** **FAILED / NOT RELEASE-READY**.",
    }:
        _add(findings, "QC_STATUS_ORDER", report_path, "open work requires reopened status")


def validate_feature(feature: Path, phase: str = "open") -> ValidationReport:
    feature = feature.resolve()
    findings: list[Finding] = []
    if phase not in {"open", "implementation", "qc", "release"}:
        _add(findings, "PHASE_UNKNOWN", feature, f"unknown phase: {phase}")
        return ValidationReport(False, phase, tuple(findings))
    spec_path = feature / "spec.md"
    tasks_path = feature / "tasks.md"
    plan_path = feature / "plan.md"
    for required in (spec_path, tasks_path, plan_path):
        if not required.is_file():
            _add(findings, "REQUIRED_FILE", required, "required SDD file missing")
    if findings:
        return ValidationReport(False, phase, tuple(findings))

    spec_bytes = spec_path.stat().st_size
    if spec_bytes > SPEC_LIMIT_BYTES:
        _add(
            findings,
            "SPEC_SIZE",
            spec_path,
            f"{spec_bytes} bytes exceeds {SPEC_LIMIT_BYTES}",
        )
    spec = _read_text(spec_path)
    objectives = OBJECTIVE_RE.findall(spec)
    if len(objectives) != 1:
        _add(findings, "OBJECTIVE_COUNT", spec_path, "exactly one objective is required")
        objective = objectives[0] if objectives else "OBJ-UNKNOWN"
    else:
        objective = objectives[0]
    definitions = REQUIREMENT_RE.findall(spec)
    duplicate_definitions = sorted(
        requirement for requirement in set(definitions) if definitions.count(requirement) > 1
    )
    if duplicate_definitions:
        _add(
            findings,
            "REQUIREMENT_DUPLICATE",
            spec_path,
            f"duplicate definitions: {', '.join(duplicate_definitions)}",
        )
    task_ranges = [(int(a), int(b)) for a, b in TASK_RANGE_RE.findall(spec)]
    if not task_ranges:
        _add(findings, "TASK_RANGE_MISSING", spec_path, "no task range in Spec")

    tasks = _parse_tasks(tasks_path, findings)
    identifiers = [task.identifier for task in tasks]
    if task_ranges:
        expected_start = min(start for start, _ in task_ranges)
        expected_end = max(end for _, end in task_ranges)
        expected = list(range(expected_start, expected_end + 1))
        if identifiers != expected:
            code = "TASK_ID_DUPLICATE" if len(identifiers) != len(set(identifiers)) else "TASK_ID_SET"
            _add(findings, code, tasks_path, f"expected T{expected_start:03d}-T{expected_end:03d}")
    for task in tasks:
        if task.objective != objective:
            _add(findings, "TASK_OBJECTIVE", tasks_path, f"T{task.identifier:03d} objective mismatch")
        for requirement in task.requirements:
            if requirement not in definitions:
                _add(
                    findings,
                    "TASK_REQUIREMENT_UNKNOWN",
                    tasks_path,
                    f"T{task.identifier:03d} references {requirement}",
                )

    checklist_dir = feature / "checklists"
    checklist_files = sorted(checklist_dir.rglob("*.md")) if checklist_dir.is_dir() else []
    if not checklist_files:
        _add(findings, "CHECKLIST_MISSING", checklist_dir, "no checklist found")
    completed_items = 0
    for checklist in checklist_files:
        for line_number, line in enumerate(_read_text(checklist).splitlines(), start=1):
            checkbox = CHECKBOX_RE.match(line)
            if checkbox is None:
                continue
            if checkbox.group(1) == "X":
                completed_items += 1
            elif checkbox.group(1) in {"", " ", "x"}:
                _add(
                    findings,
                    "CHECKLIST_OPEN",
                    checklist,
                    f"line {line_number} is not completed",
                )
            else:
                _add(
                    findings,
                    "CHECKLIST_FORMAT",
                    checklist,
                    f"line {line_number} has invalid checkbox",
                )
    if checklist_files and completed_items == 0:
        _add(findings, "CHECKLIST_EMPTY", checklist_dir, "no completed checklist item")

    _validate_archive(feature, spec, findings)
    completed_exists = (feature / ".completed").is_file()
    qc_exists = (feature / ".qc-passed").is_file()
    repository_head = _repository_head(feature)
    task_start = min(identifiers) if identifiers else 0
    task_end = max(identifiers) if identifiers else 0
    if completed_exists:
        _validate_completed_marker(
            feature,
            tasks,
            objective,
            (task_start, min(403, task_end)),
            repository_head,
            findings,
        )
    if qc_exists:
        _validate_qc_marker(
            feature,
            tasks,
            objective,
            (task_start, min(414, task_end)),
            repository_head,
            findings,
        )
    _validate_qc_order(feature, objective, qc_exists, findings)

    task_by_id = {task.identifier: task for task in tasks}
    if identifiers:
        start, end = min(identifiers), max(identifiers)
        implementation_end = min(403, end)
        qc_end = min(414, end)
        expected_boxes: dict[int, str]
        if phase == "open":
            if completed_exists or qc_exists:
                _add(findings, "OPEN_MARKER", feature, "open phase cannot have markers")
            if all(task.box == "X" for task in tasks):
                _add(findings, "OPEN_TASKS", tasks_path, "open phase requires open tasks")
            expected_boxes = {}
        elif phase == "implementation":
            expected_boxes = {
                identifier: "X" if identifier <= implementation_end else " "
                for identifier in range(start, end + 1)
            }
            if not completed_exists or qc_exists:
                _add(findings, "PHASE_MARKER", feature, "implementation marker state invalid")
        elif phase == "qc":
            expected_boxes = {
                identifier: "X" if identifier <= qc_end else " "
                for identifier in range(start, end + 1)
            }
            if not completed_exists or not qc_exists:
                _add(findings, "PHASE_MARKER", feature, "QC marker state invalid")
        else:
            expected_boxes = {identifier: "X" for identifier in range(start, end + 1)}
            if not completed_exists or not qc_exists:
                _add(findings, "PHASE_MARKER", feature, "release marker state invalid")
        for identifier, expected_box in expected_boxes.items():
            task = task_by_id.get(identifier)
            if task is None or task.box != expected_box:
                _add(
                    findings,
                    "TASK_PHASE_STATE",
                    tasks_path,
                    f"T{identifier:03d} has wrong state for {phase}",
                )

    return ValidationReport(not findings, phase, tuple(findings))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("open", "implementation", "qc", "release"),
        default="open",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = validate_feature(args.feature, args.phase)
    except SystemExit:
        raise
    except Exception as exc:
        if "--json" in (argv if argv is not None else sys.argv[1:]):
            print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"validator error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(
            json.dumps(
                {
                    "valid": report.valid,
                    "phase": report.phase,
                    "findings": [asdict(finding) for finding in report.findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for finding in report.findings:
            print(f"{finding.code}: {finding.path}: {finding.message}")
        print("SDD VALID" if report.valid else "SDD INVALID")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
