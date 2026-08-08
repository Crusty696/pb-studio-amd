# T346 VRAM and Monitoring Coherence — 2026-07-30

## Status

- Task: T346
- Result: CONFIRMED
- Tests executed: none
- Verification: syntax/static diagnostics only

## Implementation

- `VRAMBudgetManager` now takes physical capacity exclusively from the central DirectML adapter descriptor.
- Removed WMI-first, name-table, monitor-first, and 8 GB fallback capacity selection.
- Config/constructor/environment limits are validated and clamped to physical selected-adapter VRAM.
- Dynamic limit changes are also clamped to the same physical ceiling.
- Budget stats expose adapter index/LUID/name and physical/effective VRAM.
- A monitor is attached to the budget only when its selected LUID equals the DirectML LUID.
- `VRAMArbiter` uses sensor values only when status is `ready` and the sensor LUID equals the central adapter LUID.
- `SystemMonitor` binds LHM by an exact normalized identity match to the central adapter and never selects a fallback GPU.
- Missing, ambiguous, or untrusted monitoring is `degraded`; foreign GPU values remain zero/suppressed.
- Aggregate multi-GPU counter and alternate-GPU temperature fallbacks were removed from the runtime refresh path.

## Diagnostics

Central budget:

| Field | Value |
|---|---|
| adapter index | `1` |
| adapter LUID | `0x00000000_0x0001185b` |
| adapter name | AMD Radeon RX 7800 XT |
| physical VRAM | `16177 MB` |
| effective VRAM | `16177 MB` |
| usable after safety buffer | `15677 MB` |

An explicit diagnostic request for `99999 MB` was clamped to `16177 MB`.

With the pre-T347 missing trust manifest:

- adapter identity remains the RX 7800 XT;
- `monitoring_status=degraded`;
- `monitoring_error=PBSTUDIO_LHM_MANIFEST_SHA256 fehlt oder ist ungueltig`;
- sensor used/total values are both `0`, so no iGPU or aggregate counter value leaks into the arbiter.

## Static verification

- Core `py_compile`: CONFIRMED
- Full `src` + `backend` compile sweep: CONFIRMED
- `git diff --check`: CONFIRMED
- Legacy budget WMI/name/fallback selection: `0`
- Runtime sensor acceptance requires matching LUID and ready status: CONFIRMED
