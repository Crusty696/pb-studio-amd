# ADR-0003: Runtime Hardware and Provider Truth

> Date: 2026-07-30 | Status: accepted | Extends ADR-0002

## Context

PB Studio selected DirectML by ordinal index while VRAM accounting and
LibreHardwareMonitor could describe a different adapter. Model cards and
task selection could also outlive provider state, so displayed availability
did not prove which provider and model handled the next request.

## Decision

1. `highest_vram_amd` is the default DirectML adapter policy. The central
   resolver records DXGI index, LUID, adapter name and dedicated VRAM.
2. DirectML sessions, VRAM limits and hardware monitoring use that exact
   identity. On the verified workstation it is RX 7800 XT index `1`, LUID
   `0x00000000_0x0001185b`.
3. LibreHardwareMonitor activates only when the versioned runtime manifest,
   bundle boundary and every declared assembly hash pass. Launchers propagate
   the validated manifest and library hashes; trust failures degrade closed.
4. LM Studio and Ollama are inventoried from live supported APIs at startup
   and bounded refresh points. Installed, loaded, usable and downloadable
   states remain distinct.
5. Every task selection produces a provider/model receipt. The following HTTP
   request must use that exact pair. A provider failure permits one inventory
   refresh and at most three distinct compatible candidates.
6. Missing or DirectML-incompatible model assets make the capability
   explicitly unavailable. No CPU, CUDA, ROCm or capability-mismatched
   fallback is allowed.

## Consequences

- GPU status, budgets and monitoring can no longer combine different devices.
- Stale configuration IDs cannot become live model cards.
- Provider failover is bounded and auditable.
- Release readiness requires physical DirectML evidence for every required
  inference workload; unavailable assets block the gate rather than weakening
  the runtime contract.
