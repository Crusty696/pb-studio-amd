# T347 LibreHardwareMonitor 0.9.6 Trust Chain — 2026-07-30

## Status

- Task: T347
- Result: CONFIRMED
- Tests executed: none
- Allowed verification: release/hash diagnostics, Python 3.11 load probe, static C#/JSON checks, copy-only restore rehearsal

## Official source

| Field | Value |
|---|---|
| Release | `v0.9.6` |
| Release URL | <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6> |
| Asset | `LibreHardwareMonitor.zip` |
| Asset URL | <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip> |
| GitHub API size | `6,632,626` bytes |
| GitHub API digest | `sha256:086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001` |
| Downloaded size | `6,632,626` bytes |
| Downloaded SHA-256 | `086D9F1B5A99E643EDC2CFAAAC16051685B551E4C5AC0B32A57C58C0E529C001` |

Downloaded bytes match the publisher-provided GitHub release digest.

## Backup and activation

- Original 43-file bundle moved intact to:
  `tools/LibreHardwareMonitor.backup-20260730T0515+0200`
- Per-file SHA-256 inventory:
  `evidence/T347-lhm-backup-sha256.json`
- Inventory count: `43`
- Inventory mismatches: `0`
- Active official release file count: `43`
- Active-vs-extracted file/hash differences: `0`
- Active assembly identity:
  `LibreHardwareMonitorLib, Version=0.9.6.0`

The active main library changed from:

- 0.9.5 SHA-256 `21673A431323CD350F31F7598D3E1A161BF9D0A4C030B76EF475441FBD30AC33`

to:

- 0.9.6 SHA-256 `6EBC194316536BA61AF5BE24508AD9FCBB2ECC685E716C12E787C79530F66BF0`

## Trust anchors

- Bundle manifest:
  `tools/LibreHardwareMonitor/pb-studio-lhm-manifest.json`
- Manifest SHA-256:
  `AF9C9CF981F92A0BD6EA5CC80FDDF0822DAAE76E60F42636AA5B65757CC5B001`
- Manifest transitive assembly closure: 9 hash-bound DLLs.
- Versioned launcher trust anchor:
  `config/lhm-runtime.json`
- WPF launcher validates both files against the versioned expected hashes before setting:
  - `PBSTUDIO_LHM_MANIFEST_SHA256`
  - `PBSTUDIO_LHM_SHA256`
- Bundle/manifest paths are constrained to the project and flat filenames.
- Hash mismatch aborts backend startup rather than trusting computed attacker-controlled hashes.

The ignored main DLL and bundle manifest must be force-added during the T369 scoped publication.

## Python 3.11/pythonnet activation probe

With the exact trust-anchor hashes supplied to the process:

| Result | Value |
|---|---|
| LHM Computer opened | yes |
| LHM GPU identity | AMD Radeon RX 7800 XT |
| DirectML adapter index | `1` |
| DirectML adapter LUID | `0x00000000_0x0001185b` |
| Monitoring status | `ready` |
| Monitoring error | `null` |
| Total VRAM after physical clamp | `16177 MB` |

The raw LHM sensor reported 16,368 MB and was clamped to the selected DXGI adapter's 16,177 MB physical ceiling.

## Restore rehearsal

The backup was restored into a copy-only probe directory:

- source files: `43`
- restored files: `43`
- path/hash differences: `0`

The active 0.9.6 directory was not changed during the rehearsal. Exact rollback remains possible from the retained backup.

## Static verification

- Manifest JSON parse and per-assembly hash validation: CONFIRMED
- Runtime trust-anchor JSON parse: CONFIRMED
- Python system-monitor syntax: CONFIRMED
- WPF launcher path/hash logic inspected; build deferred to T362
- `git diff --check`: CONFIRMED
- New dependencies/lockfiles: none
