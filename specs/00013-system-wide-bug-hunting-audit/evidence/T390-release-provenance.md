# T390 Release Provenance

Date: 2026-07-31
Result: PASS

## Change

- Added `scripts/generate_release_provenance.py`.
- The generator produces a CycloneDX 1.6 SBOM and a machine-readable provenance receipt.
- The receipt binds commit, branch, exact dirty paths, Python/.NET SDKs, NumPy, ten lock/config inputs, SBOM hash and release artifact hashes.
- Python 3.11, NumPy 1.26.4, the exact `global.json` SDK, approved DirectML manifest and exact bundle hash are fail-closed contracts.
- Both UI and native-test NuGet locks are deduplicated into the SBOM.
- Normal mode also requires a verified `PBStudio.UI.exe` PE image or complete WPF publish ZIP; arbitrary files and `release_eligible=false` fail.
- `--require-clean` rejects a dirty repository with exit code 2.

## Current receipt

- Commit: `044fa13c70f8880d0c64d78d24667b49ea8f3eb4`
- Dirty: `true` with 255 paths; therefore `release_eligible=false` truthfully.
- Python: `3.11.9`; NumPy: `1.26.4`; .NET SDK: `9.0.316`.
- SBOM: 160 components; SHA-256 `555df929c9bb2595feff6a2da5ebf92642808450690bd4a1e23684d86b98e0b1`.
- DirectML artifact: 3,219,585,582 bytes; SHA-256 `397f4b332a265b71ac555f7209fdb4a140bb2efc5168f51297cff5ea93e4b96d`.
- Receipt SHA-256: `ff756a0c5fe78550f144447ff9e73d5da4059bace3de80d8c12ea65ea80a5311`.

## Verification

- Python compile: PASS.
- CycloneDX JSON parse and unique `bom-ref` validation: PASS.
- Dirty-state negative gate: PASS, expected exit code 2.
- DirectML archive size and SHA-256 comparison against the approved manifest: PASS.
- Direct `app.openapi()` export is atomic UTF-8 JSON and byte-stable at
  `8456bf2c1c3e9c36b8a8d781e17026f241c6bfce4bd020b6907e2cfbd870554b`;
  PowerShell object reserialization is no longer used.
- `git diff --check`: PASS.

The current receipt is an implementation receipt, not a release approval. T413 must regenerate it from the single clean release commit and require `release_eligible=true`.
