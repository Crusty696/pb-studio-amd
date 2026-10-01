"""Write/refresh `.completed` + evidence manifest for an SDD feature (Spec 00035).

    PYTHONPATH=src python scripts/dev/write_completed_marker.py specs/00035-full-audit-remediation

Binds the marker to the current HEAD: task digest, manifest digest and one
receipt per task. Run it after the last commit that touches a receipt file and
commit the two outputs; `validate_sdd.py --phase implementation` must then
report SDD VALID. qc-report.md is deliberately no receipt - it keeps growing.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import validate_sdd as v  # noqa: E402

RECEIPTS_00035 = {
    1: "evidence/traceability.md", 2: "evidence/traceability.md",
    3: "evidence/t003-melodic-analyse-20261001.md", 4: "evidence/traceability.md",
    5: "evidence/traceability.md", 6: "evidence/traceability.md", 7: "evidence/traceability.md",
    8: "evidence/finding02-weightsdb-20260930.md", 9: "evidence/traceability.md",
    10: "evidence/traceability.md", 11: "evidence/traceability.md", 12: "clarifications.md",
    13: "evidence/t013-api-workflow-20260930.md", 14: "evidence/t014-caption-review-20261001.md",
    15: "evidence/t016-final-video-log-review-20260929.md",
    16: "evidence/t016-final-video-log-review-20260929.md",
    17: "evidence/t016-final-video-log-review-20260929.md",
}


def main(feature_arg: str, note: str = "") -> None:
    feature = Path(feature_arg).resolve()
    rel = feature.relative_to(Path.cwd().resolve()).as_posix()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    findings: list = []
    tasks = v._parse_tasks(feature / "tasks.md", findings)
    if findings or not all(t.box == "X" for t in tasks):
        raise SystemExit("tasks not parseable or not all done")
    start, end = min(t.identifier for t in tasks), max(t.identifier for t in tasks)
    committed_tasks = subprocess.run(["git", "show", f"{commit}:{rel}/tasks.md"],
                                     capture_output=True, check=True).stdout
    manifest = {
        "schema_version": 1,
        "objective": tasks[0].objective,
        "task_range": f"T{start:03d}-T{end:03d}",
        "commit_sha": commit,
        "review_status": "PASS",
        "open_blockers": [],
        "receipts": [
            {"task_id": f"T{i:03d}", "path": p, "sha256": v.sha256_file(feature / p)}
            for i, p in sorted(RECEIPTS_00035.items())
        ],
        "artifact_hashes": [
            {"path": "tasks.md", "sha256": hashlib.sha256(committed_tasks).hexdigest()},
            {"path": "evidence/traceability.md",
             "sha256": v.sha256_file(feature / "evidence/traceability.md")},
            {"path": "clarifications.md", "sha256": v.sha256_file(feature / "clarifications.md")},
        ],
        "note": note or ("Implementation complete. Not a QC/release claim: GUI/live acceptance "
                         "items in evidence/traceability.md remain separate gates."),
    }
    mpath = feature / "evidence" / "completion-manifest.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")
    marker = {
        "schema_version": 1,
        "objective": tasks[0].objective,
        "phase": "implementation",
        "task_range": f"T{start:03d}-T{end:03d}",
        "task_digest_sha256": v._task_digest(tasks, start, end),
        "evidence_manifest": "evidence/completion-manifest.json",
        "evidence_manifest_sha256": v.sha256_file(mpath),
        "commit_sha": commit,
        "completed": "2026-10-01",
    }
    (feature / ".completed").write_text(json.dumps(marker, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    print(commit)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
