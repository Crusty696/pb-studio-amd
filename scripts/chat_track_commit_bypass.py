"""Retired Git-plumbing bypass from the historical chat track."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "BLOCKED: legacy ref/index mutation bypasses normal Git locking and "
        "the D07 remote-divergence gate.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
