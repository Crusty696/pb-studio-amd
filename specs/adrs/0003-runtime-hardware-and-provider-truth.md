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
7. Locally installed inference assets are bound to pinned source revisions,
   source/derived SHA-256 values and deterministic transformations in
   `config/directml-model-assets.json`. Fixed-shape exports are permitted when
   they remove unsupported dynamic-shape control nodes without changing neural
   weights.
8. Partial model readiness is explicit. Moondream Vision may be ready while
   caption generation remains unavailable; vision load must never set the
   full caption-pipeline readiness flag.

## Consequences

- GPU status, budgets and monitoring can no longer combine different devices.
- Stale configuration IDs cannot become live model cards.
- Provider failover is bounded and auditable.
- Release readiness requires physical DirectML evidence for every required
  inference workload; unavailable assets block the gate rather than weakening
  the runtime contract.
- Deterministic CPU input preprocessing is allowed, but neural inference stays
  under the strict DirectML session contract.
- Wrapper-level DirectML calls own the shared GPU lock; orchestration layers
  must not reacquire the same non-reentrant lock around wrapper calls.
