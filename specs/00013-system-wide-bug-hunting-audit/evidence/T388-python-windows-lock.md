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

## Verification

- Lock verifier: PASS (`41 direct pins; 124 locked wheels`).
- Vendor wheel/manifest SHA comparison: PASS.
- Python compile, JSON, PowerShell AST and `git diff --check`: PASS.
- `requirements.txt`: `2853d9d0244d16c7131e6dea90b2f0b806cdfd88fdaa798b4734d85db442e60f`.
- `requirements-direct.txt`: `a1da1b70606bc270ff806b637d4d95e03389bcb56aead91812d2a667a934be09`.
- `python-wheel-overrides.json`: `1690d68d0873f4982acf73d5b44a9439666fefd7fa9a20f82c1da0cbf381c1c6`.
- `lock_python_requirements.py`: `32f97726bb3df37d04671dbc0f50263f232f47e7f3fa2866cf7456d0ad54eee1`.
- `setup_pb_studio.ps1`: `d37c6ec1addd09239f741bfd00314505ad6e198d759103074e99e91e59f6b99a`.

The active venv was not mutated. External clean restore remains T407.
