# T349 — LM Studio JIT configuration

Status: CONFIRMED

## Baseline and backup

- Supported setting: `justInTimeModelLoading` in LM Studio's local HTTP server configuration.
- Active config: `C:\Users\david\.lmstudio\.internal\http-server-config.json`
- Original SHA-256: `528FB131F3FCE5984BC8AF372A5B2857123845F1C9B0098AF14C593AB2EEA4B1`
- Backup: `C:\Users\david\.lmstudio\.internal\http-server-config.json.backup-20260730T0538+0200`
- Backup SHA-256: `528FB131F3FCE5984BC8AF372A5B2857123845F1C9B0098AF14C593AB2EEA4B1`
- Baseline `/v1/models`: 1 served model.
- Baseline loaded state: 1 model.

## Activation and restart

- Changed only `justInTimeModelLoading` from `false` to `true`.
- Restarted the local server with `lms server stop` followed by
  `lms server start --port 1234 --bind 127.0.0.1`.
- Restart status: server running on port 1234.
- Active config after LM Studio normalization:
  SHA-256 `09D934E220A1ACCB031EDC928D3E46E70916503C2B1AC0E701C415F206E716F7`.
- Active value after restart: `true`.

## Runtime result

- `/v1/models`: 14 truthful available model identifiers.
- `lms ps --json`: 1 model remains loaded.
- JIT therefore exposes downloaded models without eagerly loading all of them.
- Loaded identifier: `hermes-ha-ornith`.

## Restore probe

- Copied the immutable backup to
  `temp\T349-lmstudio-restore-probe.json`.
- Probe parsed successfully with `justInTimeModelLoading=false`.
- Probe SHA-256 equals the original and backup SHA-256:
  `528FB131F3FCE5984BC8AF372A5B2857123845F1C9B0098AF14C593AB2EEA4B1`.
- The active JIT configuration was retained; the tested restore source remains
  byte-identical to the pre-change state.

## Gate

CONFIRMED: backup, hash, supported setting activation, controlled restart,
truthful available-versus-loaded behavior, and exact restore probe all passed.
