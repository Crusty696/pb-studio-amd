"""Fail-closed verifier for PB Studio's approved CPU-only PyTorch stack."""

from __future__ import annotations

from importlib import metadata
import sys


EXPECTED = {
    "torch": "2.11.0+cpu",
    "torchvision": "0.26.0+cpu",
    "torchaudio": "2.11.0+cpu",
}
FORBIDDEN_PREFIXES = ("cuda-", "nvidia-")
FORBIDDEN_EXACT = {"pytorch-cuda", "triton"}


def canonical_name(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def main() -> int:
    errors: list[str] = []
    for distribution, expected in EXPECTED.items():
        try:
            actual = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            errors.append(f"{distribution} is not installed")
            continue
        if actual != expected:
            errors.append(f"{distribution} must be {expected}, got {actual}")

    installed = {
        canonical_name(dist.metadata["Name"] or "")
        for dist in metadata.distributions()
    }
    forbidden = sorted(
        name
        for name in installed
        if name.startswith(FORBIDDEN_PREFIXES) or name in FORBIDDEN_EXACT
    )
    if forbidden:
        errors.append("forbidden accelerator packages: " + ", ".join(forbidden))

    try:
        import torch
        import torchaudio  # noqa: F401 - binary compatibility is the check
        import torchvision  # noqa: F401 - binary compatibility is the check
    except Exception as exc:
        errors.append(f"PyTorch family import failed: {type(exc).__name__}: {exc}")
    else:
        if torch.__version__ != EXPECTED["torch"]:
            errors.append(
                f"torch runtime must be {EXPECTED['torch']}, got {torch.__version__}"
            )
        if torch.version.cuda is not None:
            errors.append(f"torch exposes CUDA runtime {torch.version.cuda}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("PASS: PyTorch 2.11.0 CPU-only stack; CUDA runtime/packages absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
