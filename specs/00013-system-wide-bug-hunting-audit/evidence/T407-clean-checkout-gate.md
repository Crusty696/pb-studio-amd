# T407 External Clean Windows Checkout Gate

**Status:** PASS

**Run:** 2026-08-01T21:28:58+02:00

**Release candidate commit:** `71300b9c2c5a768f1cfa44d8dd09b2835b292d27`

## Isolation

- Cloned the tracked branch with `git clone --no-local --no-hardlinks` into a new system-temp root outside the repository.
- Checkout started clean with no tracked `bin`, `obj` or generated API source; only `PBStudio.UI/Generated/.gitkeep` was tracked.
- NuGet used a new empty `NUGET_PACKAGES` directory (1,896 files after restore).
- Python used a new CPython 3.11 virtual environment and `--no-cache-dir` (124 installed distributions).
- DirectML provisioning targeted the clean checkout, not the developer repository's installed `models/` tree.

## Results

- Locked NuGet restore: PASS for UI and native test project.
- NSwag: generated `obj/Generated/ApiTypes.g.cs` during `CoreCompile` (170,703 bytes).
- WPF Release build with warnings as errors: **0 warnings, 0 errors**.
- Clean-checkout native tests: **28 passed, 0 failed, 0 skipped**.
- Python `--require-hashes` restore: PASS; lock verifier reports 41 direct pins and 124 exact SHA-256-bound wheels.
- Python dependency consistency: `pip check` PASS; NumPy `1.26.4`, torch family `2.4.1+cpu`/`0.19.1+cpu`/`2.4.1+cpu`, ONNX Runtime `1.19.2`.
- DirectML bundle archive SHA-256: `397f4b332a265b71ac555f7209fdb4a140bb2efc5168f51297cff5ea93e4b96d`, exact manifest match.
- Fresh DirectML install: PASS; 29 files / 3,225,560,126 bytes. Immediate second verification: PASS without reinstall.
- Final tracked checkout state: clean.

## Primary evidence hashes

| Artifact | SHA-256 |
|---|---|
| `clean-checkout.log` | `5edf6e62dbf9e659e8997ca01823877fcad2e3c8de82743fc4c3b1becdf2887a` |
| `clean-wpf-release.binlog` | `e08df9c4d691bd2208f3d32bc09c0be943f0ddee869b12223e2ac6d4034ec441` |
| `T407-clean-native-tests.trx` | `fbf1de10fd104f9def265f79c716c4304a3ee6eafa117f90d19f594ef93c534d` |
| `python-lock-verify.log` | `3bac62033aae0745acb1a1dc4864e54d18b836fa81a9200f0ad626f8d641fa77` |
| `python-pip-check.log` | `6326999b2d47daff6338070efad9139a62dd802f33019eab621859ade33fc907` |
| `python-smoke.log` | `74799b5897ee2e25f8efb9979a9a35096b3404d7aeff977d325555cdd02b85bc` |
| `directml-asset-provision.log` | `6667e54c608dd183c27cf2ace2a1547e6ded9f7dfaec2d1697cc6dd303fd58ff` |
| `directml-asset-reverify.log` | `5ad6b98a6e047b8c77314ac1e3e11ce31bc7f7db4ca5cc5b3c6ae0fae824cc28` |
| `asset-source-hashes.log` | `301e25a258dc52bf2c39717426a1822bfb0e3d9dfc886399816a9ff97ecd436c` |
