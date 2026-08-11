"""OBJ-77 qualified requirement registry regression tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/requirements/generate_obj77_registry.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("obj77_registry", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_covers_all_definition_syntax_and_collision_groups() -> None:
    payload = _load_generator().build_registry(ROOT / "specs")

    assert payload["entry_count"] == 283
    assert payload["unique_local_id_count"] == 215
    assert payload["collision_group_count"] == 33
    assert payload["same_workspace_duplicate_group_count"] == 0
    assert payload["missing_spec_workspaces"] == ["00017-fix-audit-block-c"]


def test_every_registry_entry_is_fully_qualified() -> None:
    payload = _load_generator().build_registry(ROOT / "specs")

    for entry in payload["entries"]:
        assert entry["qualified_id"] == (
            f"{entry['workspace']}/{entry['objective']}/{entry['local_id']}"
        )
        assert entry["spec_sha256"]


def test_naked_cross_workspace_references_are_forbidden() -> None:
    payload = _load_generator().build_registry(ROOT / "specs")

    assert payload["naked_cross_workspace_references_allowed"] is False
    assert len(payload["collisions"]["FR-354"]) == 2
    assert len(payload["collisions"]["SC-084"]) == 2
