# T405 Python Release Gate

**Status:** PASS

**Run:** 2026-08-01T21:12:21+02:00

**Baseline commit:** `31ef2f1`

**Command:** `scripts/run_python_quality_gate.ps1`

## Environment

- Python `3.11.9`
- NumPy `1.26.4`
- PyTorch `2.4.1+cpu`; CUDA unavailable
- torchvision `0.19.1+cpu`
- torchaudio `2.4.1+cpu`
- `PYTHONPATH=src;.` during the quality gate
- Requirements lock: PASS, 41 direct pins and 124 exact SHA-256-bound Windows wheels

## Results

- Pytest: **1,127 passed-equivalent outcomes, 0 failed, 0 errors, 11 skipped**
  (`pytest.xml`: 1,127 collected tests including skips)
- Skip policy: **0 unapproved skips**; all 11 skips are owned and unexpired.
- Coverage: **61.4%**, above the required 53.0% release threshold.
- Source compile sweep: PASS (`backend`, `src`, `scripts`, `Tests`).
- SDD `qc-progress` validation: PASS.
- Repository temp hygiene: PASS; the quality runner removed its owned system-temp tree and preserved historical pytest evidence.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| `T405-python-quality/pytest.xml` | `348947124393caa704d291151fe2d2b28ec22686f1b79b6088cd6cb6d93c7df9` |
| `T405-python-quality/coverage.json` | `9e3d63068116c25a5e36184e4ebc252e83a089883859f0451c7bb28a7bd043ed` |
| `T405-python-quality/skips.json` | `34dd9065fb4c9958d18f50cec17ea04799cdf8e51cee07e1fee89e9169d1bec3` |

## Corrections validated by the full suite

- Tests now establish the project operation context required by the hardened backend contracts.
- Video fixtures persist media records before analysis and embedding commits.
- Brain fixtures bind leases to the exact project ID and epoch.
- Static WPF contract tests follow generation/project/result correlation semantics.
- The SDD validator validates the historical implementation marker against its bound commit and enforces contiguous QC progress.
