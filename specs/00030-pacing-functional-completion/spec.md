# Specification: Pacing Functional Completion

## Objective

Verify and harden every productively reachable KI-Regie/Pacing function from WPF input through API, service, engine, persistence, preview, SSE, and timeline handoff. The area is complete only when each catalogued function works with real project media or is explicitly reported unavailable with a truthful reason.

## User Stories

### US1 — Reliable cut-list generation (P1)

As an editor, I can select analyzed audio and video, generate a contiguous source-safe cut list, and receive a usable timeline without manual repair.

### US2 — Effective creative controls (P1)

As an editor, every visible Director setting changes the active generation path as described, including beat mode, weights, interval limits, motion, structure, semantic, key, stem, Brain, anchors, BPM override, and canvas input.

### US3 — Observable operation and recovery (P1)

As an editor, generation reports progress, supports cancellation/retry safely, preserves project isolation, and exposes degradations instead of silently pretending optional AI capabilities succeeded.

### US4 — Preview and timeline handoff (P1)

As an editor, generated cuts can be reloaded, edited, previewed, and passed to the timeline/render boundary without gaps, overlaps, stale state, or source-bound violations.

## Requirements

### FR-396 Productive-path inventory

Create a code-backed catalog of every reachable Pacing/Director control, command, endpoint, response field, generation mode, persistence operation, progress event, and downstream handoff. Historical unreachable APIs must be labelled legacy and excluded from product-completion claims.

### FR-397 End-to-end contract integrity

For every catalogued function, UI bindings, C# DTOs, JSON fields, Pydantic validation, router mapping, service consumption, engine behavior, response mapping, and UI presentation must agree.

### FR-398 Deterministic safety invariants

All successful cut lists must be finite, ordered, contiguous over the requested target, non-overlapping, positive-duration, within configured interval policy, within source duration, and scoped to the active project/request.

### FR-399 Creative-control effectiveness

Every enabled visible control must be consumed by the active runtime path and produce an observable, testable behavior. Unsupported capability states must disable or degrade transparently; silent no-ops are defects.

### FR-400 Runtime lifecycle

Generation, progress, cancellation, concurrent-request rejection, retry, backend restart handling, timeline persistence, preview creation, and error presentation must terminate safely without stuck UI state or ghost results.

### FR-401 Real-media validation

Run API and GUI validation with existing media only from `C:\Users\david\Videos\test_data\audio` and `C:\Users\david\Videos\test_data\video`. Record exact inputs and observable results. Clean only artifacts created by this validation and verify cleanup.

### TR-379 Regression coverage

Each discovered defect requires a failing focused regression before implementation and a passing rerun afterward. Existing passing behavior must remain covered.

### OR-356 Compatibility and hardware policy

No new dependency, migration, public request break, CUDA/ROCm path, CPU inference fallback, destructive data operation, or unrelated refactor is permitted.

## Success Criteria

- SC-107: Catalog contains every productively reachable Pacing/Director function and maps each to evidence.
- SC-108: Every catalog entry is PASS in automated and applicable real-media API/GUI verification, or explicitly unavailable by approved capability policy.
- SC-109: Python Pacing/router/service/timeline regression cluster and C# Director tests pass; Release build has zero errors and warnings.
- SC-110: Real-media generation completes with valid progress, valid cuts, visible degradation semantics, preview/timeline handoff, and no persistent test residue.
- SC-111: `.completed` and `.qc-passed` are created only after all P1 requirements have authoritative evidence.

## Out of Scope

- Historical `SyncMode`/legacy generation APIs with no productive caller.
- New visual redesign, new models, dependency changes, database migrations, or non-Pacing feature work.
- Changing audio/video analysis algorithms except where a proven Pacing contract defect requires a minimal adapter fix.
