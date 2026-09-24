# Spec 00033 — Implementation-only Evidence (2026-09-19)

## Scope

- Productive Video/Vision paths were source-audited and repaired.
- User explicitly prohibited tests, builds, GUI checks, and live provider probes.
- Runtime, compilation, DirectML, provider, and GUI behavior remain `[unknown: verification deferred]`.
- No `.completed` or `.qc-passed` marker was created.

## Implemented fixes

### Project and media lifecycle

- Thumbstrip, clip-wave, scene, motion, single-delete, and batch-delete routes now use current-project operation leases; stale work returns conflict instead of publishing across projects.
- Scene and motion retrieval require a completed matching stage. An unrun/failed motion stage no longer returns fabricated zero/static data.
- Import input duplicates are canonicalized and skipped with progress; duration-bounded thumbstrip sampling uses persisted ffprobe duration.
- Video Pydantic collection fields use per-instance factories instead of shared mutable defaults.

### Analysis and model lifecycle

- RAFT and SigLIP owners remain resident across the model-centric multi-clip pass and are discarded only after a real inference/provider failure or VRAM-manager eviction.
- RAFT curves/averages and SigLIP vectors reject NaN/Inf; SigLIP additionally enforces 1152 dimensions and non-zero normalization before persistence.
- Missing DirectML model/provider initialization is recorded as `unavailable`; inference/data faults remain `failed`.
- Existing stage-resume, pending-vector compensation, FAISS/Brain dual-write, and bounded VLM pin/failover behavior remains intact.

### WPF Video Library

- Manual/path/folder import is sequence- and project-bound; a completed old-project request cannot refresh or announce success in the new project.
- Project close/switch invalidates import publication and clears import, scene, analysis-step, and progress state.
- Existing staged batch order remains scenes-all → RAFT-all → SigLIP-all → VLM-all.

## Deferred verification

- T008: focused/full automated verification — blocked until explicit user authorization.
- T009: live API/DirectML/provider/GUI verification — blocked until explicit user authorization.
- T010: completion and QC markers — blocked until T008 and T009 pass.
