"""Fail-closed status gate for OBJ-77 external reservations."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_STATUS = {
    "ground_truth": "reserved",
    "intel": "reserved",
    "nvidia": "reserved",
    "lm_window": "authorized",
    "stress_window": "reserved",
}


def validate_reservations(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for key, expected in REQUIRED_STATUS.items():
        actual = payload.get(key, {}).get("status")
        if actual != expected:
            errors.append(f"{key}.status must be {expected}")
    return errors


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: validate_obj77_reservations.py RECEIPT.json", file=sys.stderr)
        return 2

    errors = validate_reservations(Path(arguments[0]))
    if errors:
        print("OBJ-77 external reservations blocked:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
