# T348 Truthful GPU Status API and WPF — 2026-07-30

## Status

- Task: T348
- Result: CONFIRMED
- Tests executed: none
- Verification: direct endpoint diagnostic, Python syntax, XAML XML, static DTO/binding checks

## Additive API contract

The existing `/gpu/status` fields remain:

- `name`
- `vram_total_mb`
- `vram_used_mb`
- `temperature_c`
- `driver_version`

Added:

- `adapter_index`
- `adapter_luid`
- `adapter_name`
- `selection_policy`
- `dedicated_vram_total_mb`
- `directml_active`
- `monitoring_status`
- `monitoring_error`

The old total field now reports the central DXGI physical capacity rather than an independent sensor/name heuristic. Used VRAM and temperature are populated only by trusted matching monitoring.

## Ready-state diagnostic

| Field | Value |
|---|---|
| name/adapter | AMD Radeon RX 7800 XT |
| adapter index | `1` |
| adapter LUID | `0x00000000_0x0001185b` |
| policy | `highest_vram_amd` |
| dedicated/legacy total | `16177 MB` |
| used | `10453 MB` |
| temperature | `48 °C` |
| DirectML active | `true` |
| monitoring status | `ready` |
| monitoring error | `null` |

## Degraded-state diagnostic

With trust hashes intentionally absent in a separate diagnostic process:

- adapter identity remained RX 7800 XT index 1/LUID `0x00000000_0x0001185b`;
- DirectML remained available;
- monitoring became `degraded`;
- the exact manifest error was returned;
- used VRAM and temperature were both zero;
- no iGPU or aggregate value was substituted.

## WPF surface

- Handwritten `GpuStatus` record was extended additively with optional/defaulted fields.
- Existing five-argument construction remains source-compatible.
- Settings view now displays adapter index, LUID, policy, DirectML status, monitoring status, physical VRAM, used VRAM, temperature, and driver.
- `monitoring_error` is shown as a visible red diagnostic only when non-null.
- The view model uses `dedicated_vram_total_mb` for the physical ceiling and retains the legacy total fallback for old backend compatibility.

## Static verification

- `backend/main.py` compile: CONFIRMED
- Direct endpoint response shape: CONFIRMED
- `SettingsView.xaml` XML parse: CONFIRMED
- DTO snake-case mapping: existing `JsonNamingPolicy.SnakeCaseLower`
- `git diff --check`: CONFIRMED
- WPF build and GUI verification remain deferred to T362/T365.
