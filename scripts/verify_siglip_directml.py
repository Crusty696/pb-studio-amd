"""Retired standalone SigLIP DirectML verifier.

The verifier could not establish model provenance. Verification now belongs to
the approved, hash-bound ONNX asset-manifest workflow.
"""

from __future__ import annotations

import logging


def main() -> int:
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    logging.error(
        "Retired: verify SigLIP through the approved ONNX asset-manifest "
        "workflow."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
