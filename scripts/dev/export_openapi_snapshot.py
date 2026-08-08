"""Export the canonical FastAPI OpenAPI document atomically and deterministically."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
for import_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


def _serialize_openapi() -> bytes:
    from backend.main import app

    return (
        json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise OSError("OpenAPI snapshot read-back verification failed")
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("PBStudio.UI/openapi.snapshot.json"),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    payload = _serialize_openapi()
    changed = not output.is_file() or output.read_bytes() != payload
    if changed:
        _atomic_write(output, payload)
    print(
        f"OPENAPI_SNAPSHOT_PASS changed={str(changed).lower()} "
        f"bytes={len(payload)} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
