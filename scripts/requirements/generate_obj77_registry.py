"""Generate OBJ-77's qualified requirement registry without mutating legacy SDD files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


OBJECTIVE_RE = re.compile(r"\*\*(OBJ-\d+):\*\*")
REQUIREMENT_DEFINITION_RE = re.compile(
    r"^\s*[-*]\s+(?:"
    r"\*\*(?P<bold_id>(?:FR|TR|OR|RR|SC)-\d{3})"
    r"(?:\s+\[(?P<inner_qualifier>(?:US|OBJ)-?\d+)\])?"
    r"(?::\*\*|\*\*(?:\s+\[(?P<outer_qualifier>(?:US|OBJ)-?\d+)\])?\s*:)"
    r"|(?P<plain_id>(?:FR|TR|OR|RR|SC)-\d{3})\s*:)",
    re.MULTILINE,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_registry(specs_root: Path) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    missing_specs: list[str] = []
    for workspace in sorted(specs_root.iterdir()):
        if not workspace.is_dir() or not re.fullmatch(r"\d{5}-.+", workspace.name):
            continue
        spec = workspace / "spec.md"
        if not spec.is_file():
            missing_specs.append(workspace.name)
            continue
        text = spec.read_text(encoding="utf-8-sig")
        objectives = OBJECTIVE_RE.findall(text)
        objective = objectives[0] if len(objectives) == 1 else "OBJ-UNRESOLVED"
        for match in REQUIREMENT_DEFINITION_RE.finditer(text):
            local_id = match.group("bold_id") or match.group("plain_id")
            definition_qualifier = (
                match.group("inner_qualifier")
                or match.group("outer_qualifier")
            )
            entries.append(
                {
                    "qualified_id": f"{workspace.name}/{objective}/{local_id}",
                    "workspace": workspace.name,
                    "objective": objective,
                    "local_id": local_id,
                    "definition_qualifier": definition_qualifier,
                    "spec_path": spec.as_posix(),
                    "spec_sha256": _sha256(spec),
                }
            )

    by_local: dict[str, list[str]] = {}
    for entry in entries:
        by_local.setdefault(str(entry["local_id"]), []).append(
            str(entry["qualified_id"])
        )
    collisions = {
        local_id: qualified
        for local_id, qualified in sorted(by_local.items())
        if len(qualified) > 1
    }
    by_workspace_local: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        key = (str(entry["workspace"]), str(entry["local_id"]))
        by_workspace_local.setdefault(key, []).append(str(entry["qualified_id"]))
    same_workspace_duplicates = {
        f"{workspace}/{local_id}": qualified
        for (workspace, local_id), qualified in sorted(by_workspace_local.items())
        if len(qualified) > 1
    }
    return {
        "schema_version": 1,
        "qualification_format": "workspace/objective/requirement",
        "naked_cross_workspace_references_allowed": False,
        "entry_count": len(entries),
        "unique_local_id_count": len(by_local),
        "collision_group_count": len(collisions),
        "same_workspace_duplicate_group_count": len(same_workspace_duplicates),
        "missing_spec_workspaces": missing_specs,
        "collisions": collisions,
        "same_workspace_duplicates": same_workspace_duplicates,
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--specs-root", type=Path, default=Path("specs"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_registry(args.specs_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
