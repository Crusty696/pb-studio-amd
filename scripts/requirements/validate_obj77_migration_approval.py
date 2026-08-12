"""Validate one OBJ77 migration approval receipt without mutating its target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pb_studio.storage.migration_authorization import (
    MigrationApprovalError,
    read_approval,
    validate_migration_approval,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--scope", choices=("fixture", "real"), default="fixture")
    args = parser.parse_args(argv)
    try:
        value, file_sha256 = read_approval(Path(args.receipt))
        authorization = validate_migration_approval(
            value,
            allowed_scope=args.scope,
        )
    except MigrationApprovalError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "receipt_file_sha256": file_sha256,
                "receipt_payload_sha256": authorization.receipt_sha256,
                "operation_id": authorization.operation_id,
                "bundle_id": authorization.bundle_id,
                "target_kind": authorization.target_kind,
                "target_path": str(authorization.target_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
