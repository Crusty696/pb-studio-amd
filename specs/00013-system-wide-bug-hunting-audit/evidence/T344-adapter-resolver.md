# T344 Central DirectML Adapter Resolver — 2026-07-30

## Status

- Task: T344
- Result: CONFIRMED
- Tests executed: none
- Allowed verification: Python syntax, JSON parse, read-only DXGI diagnostic, diff/truncation checks

## Implementation

- Added `src/pb_studio/core/directml_adapter.py`.
- Added `hardware.directml_adapter_policy="highest_vram_amd"` to defaults and `config.json`.
- Implemented configuration precedence:
  `hardware.directml_device_id` → deprecated `ai.dml_device_id` → policy.
- Implemented normal DXGI enumeration, software exclusion, AMD vendor filtering, LUID normalization, dedicated/shared memory capture, high-performance LUID mapping, and process-wide immutable selection.
- Implemented fail-closed errors for missing AMD hardware, invalid/non-AMD/software overrides, unsupported policies, and iGPU override while an AMD dGPU exists.
- Exposed the central adapter descriptor and DirectML provider tuple through `pb_studio.core`.
- Added no dependency and no provider fallback.

## Target-machine diagnostic

| Index | LUID | Adapter | Vendor | Dedicated MB | Software | dGPU |
|---:|---|---|---:|---:|---|---|
| 0 | `0x00000000_0x0000ffbc` | AMD Radeon(TM) Graphics | `0x1002` | 485 | no | no |
| 1 | `0x00000000_0x0001185b` | AMD Radeon RX 7800 XT | `0x1002` | 16,177 | no | yes |
| 2 | `0x00000000_0x000117f8` | Microsoft Basic Render Driver | `0x1414` | 0 | yes | no |

Selected descriptor:

- `device_id=1`
- `luid=0x00000000_0x0001185b`
- `name=AMD Radeon RX 7800 XT`
- `dedicated_vram_mb=16177`
- `selection_policy=highest_vram_amd`
- reason: AMD hardware adapter with highest dedicated VRAM

The current Windows high-performance preference order reported the iGPU first. This is retained as diagnostic metadata but does not override the approved deterministic `highest_vram_amd` policy.

## Static verification

- `py_compile`: CONFIRMED
- `config.json` parse: CONFIRMED
- `git diff --check`: CONFIRMED
- NUL/truncation indicators: none
- IRON R1: AMD DirectML only
- IRON R2: session flags are not changed by T344; central provider contract carries only DML plus selected `device_id`
- IRON R3: no runtime/dependency changes
- IRON R4/R5/R6/R7/R8: unchanged and not violated

Official DXGI contracts:

- <https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgifactory1-enumadapters1>
- <https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1>
