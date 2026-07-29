"""Retired RAFT ONNX export entry point.

PB Studio accepts only approved, hash-bound ONNX assets. Local exports are
intentionally unavailable.
"""

from __future__ import annotations

import logging


def main() -> int:
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    logging.error(
        "Retired: provision RAFT only through the approved, hash-bound "
        "ONNX asset-manifest workflow."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
