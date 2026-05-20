"""S-H1b (Audit V2): fails when backend openapi.json drifts from
checked-in PBStudio.UI/openapi.snapshot.json. Forces dev to refresh
the snapshot before WPF build (else generated DTOs go stale)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


SNAPSHOT_PATH = Path(__file__).parent.parent / "PBStudio.UI" / "openapi.snapshot.json"


def _normalize(spec: dict) -> dict:
    """Strip non-deterministic fields (version stamps, server URLs)
    so the diff focuses on schema-relevant differences."""
    out = dict(spec)
    out.pop("servers", None)
    info = dict(out.get("info", {}))
    info.pop("version", None)
    out["info"] = info
    return out


def test_snapshot_exists():
    assert SNAPSHOT_PATH.exists(), (
        f"Snapshot missing: {SNAPSHOT_PATH}. "
        "Run scripts/dev/refresh-openapi-snapshot.ps1 to create it."
    )


def test_snapshot_matches_live_backend():
    client = TestClient(app)
    live = client.get("/openapi.json").json()

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    live_paths = sorted(_normalize(live).get("paths", {}).keys())
    snap_paths = sorted(_normalize(snapshot).get("paths", {}).keys())

    missing_in_snapshot = set(live_paths) - set(snap_paths)
    missing_in_live = set(snap_paths) - set(live_paths)

    assert not missing_in_snapshot, (
        f"Backend has paths NOT in snapshot (run refresh script): "
        f"{sorted(missing_in_snapshot)}"
    )
    assert not missing_in_live, (
        f"Snapshot has paths NOT in live backend (delete from snapshot): "
        f"{sorted(missing_in_live)}"
    )


def test_snapshot_schemas_consistent():
    """Per-component schemas must match key-set. Catches added/removed fields
    without requiring full deep-diff (tests aren't a regression suite for
    OpenAPI itself — they're a drift-alarm)."""
    client = TestClient(app)
    live = client.get("/openapi.json").json()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    live_schemas = (live.get("components") or {}).get("schemas") or {}
    snap_schemas = (snapshot.get("components") or {}).get("schemas") or {}

    diffs = []
    for name in set(live_schemas) | set(snap_schemas):
        if name not in live_schemas:
            diffs.append(f"snapshot has schema '{name}' not in live")
            continue
        if name not in snap_schemas:
            diffs.append(f"live has schema '{name}' not in snapshot")
            continue
        live_props = set((live_schemas[name].get("properties") or {}).keys())
        snap_props = set((snap_schemas[name].get("properties") or {}).keys())
        if live_props != snap_props:
            diffs.append(
                f"{name}: properties diverge "
                f"live={sorted(live_props)} snap={sorted(snap_props)}"
            )

    assert not diffs, "Schema drift:\n  " + "\n  ".join(diffs)
