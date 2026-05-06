"""Drift-Check: TriggerSettings dataclass vs TriggerSettingsSchema (Pydantic).

Plan Phase 0 #4. Exit 1 bei Drift, 0 wenn synchron.
Aufruf: python scripts/check_trigger_settings_drift.py
"""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from pb_studio.pacing.pacing_models import TriggerSettings  # noqa: E402
from backend.schemas.pacing_schemas import TriggerSettingsSchema  # noqa: E402


def main() -> int:
    dc_fields = {f.name for f in fields(TriggerSettings)}
    schema_fields = set(TriggerSettingsSchema.model_fields.keys())

    only_dc = dc_fields - schema_fields
    only_schema = schema_fields - dc_fields

    if only_dc or only_schema:
        print("DRIFT detected between TriggerSettings <-> TriggerSettingsSchema")
        if only_dc:
            print(f"  Only in dataclass: {sorted(only_dc)}")
        if only_schema:
            print(f"  Only in schema:    {sorted(only_schema)}")
        return 1

    print(f"OK: {len(dc_fields)} fields in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
