# T388 Python 3.11 Windows Lock

Date: 2026-07-31
Result: PASS

## Change

- 41 direct pins resolve to 124 exact CPython 3.11 Windows-wheel hashes.
- Lock generation and verification are repository-owned and fail closed on
  version, target, wheel or hash drift.
- Four sdist-only dependencies are vendored as twice-reproduced pure-Python
  wheels with source URL/hash, license, builder versions and output hash.
- Setup validates the wheel manifest, path boundary, allowlist and hashes,
  then installs only with `--require-hashes`.
- Torch, TorchVision and TorchAudio are exact official `+cpu` wheels from
  package-specific PyTorch find-links pages. Generation, verification, setup
  and CI reject CUDA/NVIDIA packages and binary-incompatible imports.

## Verification

- Lock verifier: PASS (`41 direct pins; 124 locked wheels`).
- Vendor wheel/manifest SHA comparison: PASS.
- Python compile, JSON, PowerShell AST and `git diff --check`: PASS.
- `requirements.txt`: `7c40a190f86199a4ee21f8050f8e0d83913dd6601226c32d31809ada3111e903`.
- `requirements-direct.txt`: `b61c7b9909baf8f0bcbc4e5c3fd328251aee85367d587af4d97dda703c2c1557`.
- `python-wheel-overrides.json`: `1690d68d0873f4982acf73d5b44a9439666fefd7fa9a20f82c1da0cbf381c1c6`.
- `lock_python_requirements.py`: `68916c0cadd525a48e075d811c54688ecf35ace3ad8b841cebe9c3bf6ce27906`.
- `verify_cpu_torch_runtime.py`: `dd279f513e817d271346502141a37aaf92166fbd5bac8490ce01985336d199f9`.
- `setup_pb_studio.ps1`: `459de657fd014b569eb186a775baa50fab6469d6756d2e3a56fbe9ebdfcc9827`.

The active venv was not mutated. External clean restore remains T407.
