# Spec 00033: Video/Vision Functional Completion

## Objective

Complete the productive Video/Vision source paths before any verification run. Preserve the accepted DirectML-only inference, project isolation, and model-centric batch contracts while repairing concrete import, analysis, persistence, cancellation, and WPF defects.

## User Stories

### US1 — Reliable video library

As a user, I need video import, metadata, thumbnails, selection, deletion, and project refresh to represent the current project accurately without stale or partial state.

### US2 — Truthful staged analysis

As a user, I need scene, motion, embedding, color, caption, and tag stages to run independently, publish exact progress, preserve valid prior results, and expose unavailable capabilities instead of fabricating success.

### US3 — Stable accelerated inference

As a user, I need RAFT, SigLIP, and local vision inference to honor DirectML, VRAM, cancellation, and provider/model pinning contracts without silent CPU fallback or avoidable model churn.

## Functional Requirements

- FR-415: Import and list only current-project video assets with validated paths, stable identities, metadata, thumbnails, and duplicate handling.
- FR-416: Execute scene detection, RAFT motion, SigLIP embedding, color, caption, and tagging as explicit stages with truthful availability and result provenance.
- FR-417: Bind every background job, persisted result, cache mutation, and UI publication to the initiating project lease and clip identity.
- FR-418: Preserve usable completed stage data when another optional stage is unavailable or fails; never report partial analysis as complete.
- FR-419: Enforce DirectML-only ONNX inference, required session flags, shared GPU lifecycle, finite/dimension-valid embeddings, and bounded model failover.
- FR-420: Make all productive Video Library controls, status, selection, progress, cancellation, retry, and project-transition paths functional.
- FR-421: Catalog productive Video/Vision functions and preserve implementation-only evidence while verification is prohibited.

## Technical Requirements

- TR-384: Runtime ONNX inference remains DirectML-only; CPU/CUDA/ROCm neural fallback is forbidden.
- TR-385: Existing project media and analysis data must not be migrated, deleted, or destructively rewritten during this fix phase.
- TR-386: No tests, builds, GUI runs, provider probes, or completion/QC markers without explicit user authorization.

## Out of Scope

- Adding dependencies, downloading models, or changing locked runtime versions.
- Database/schema migrations or destructive media cleanup.
- Replacing RAFT, SigLIP, scene detection, or the selected local vision provider architecture.
- Verification and release claims during the fix phase.

## Acceptance Criteria

- AC-1: Productive Video/Vision controls and runtime paths are cataloged.
- AC-2: Concrete source defects across import, analysis, persistence, inference, and WPF state are repaired.
- AC-3: Missing models, invalid embeddings, cancelled work, and partial results remain explicit.
- AC-4: Project transitions cannot publish stale video data or mutate another project.
- AC-5: Implementation evidence and Brain log identify edits and mark runtime verification unknown.
