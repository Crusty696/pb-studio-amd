# Spec 00032 — Implementation-only Evidence (2026-09-19)

## Scope

- Productive Brain/HIRN scoring, learning, semantic, API, persistence, pacing-boundary, and WPF paths were source-audited and repaired.
- The user explicitly prohibited tests, builds, GUI checks, and live API/provider runs.
- Runtime, compilation, generated OpenAPI compatibility, and GUI behavior remain `[unknown: verification deferred]`.
- No `.completed` or `.qc-passed` marker was created.

## Implemented fixes

### Scoring and learning

- Explicit axis availability now controls bridge calculation and the final-score denominator.
- A cut contributes only its matching trigger family axis; unrelated hard-zero trigger axes no longer dilute confidence.
- `brain_min_confidence` now filters the Brain reranker by final Brain score. The post-processor records threshold status without deleting finished timeline intervals.
- Smart sampling uses only axes available on each persisted cut.
- Beta variance now includes the Laplace prior, preventing one-sided early feedback from becoming falsely certain.
- Posterior diagnostics expose the exact confident backoff bucket and authoritative cold-start state; explanations use the same current calculation for contributions and final score.

### Semantic projector

- Fresh random projector matrices are explicitly untrained and cannot produce semantic evidence.
- V1 learned artifacts and V2 artifacts with applied feedback events are recognized as trained.
- Missing audio/video embeddings remain distinguishable from an unavailable or untrained projector.
- A projector generation is not published when no trainable feedback pair exists.

### Persistence, API, and project isolation

- Failed Brain annotation persistence no longer returns transient scores that cannot receive feedback; the pacing boundary retains its existing base-timeline degradation path.
- Brain feedback carries the initiating desktop project identity. The backend rejects the mutation if the active project changed before acceptance.
- Learning-session uncertainty is derived from persisted available-axis evidence.
- Pydantic collection defaults use factories; schema descriptions match normalized current behavior.
- Narrative model/cache identity includes provider/model selection; an empty narrative falls back without switching models.

### HIRN WPF

- Project transitions clear learning cuts, selection, pending feedback/reset generations, and close an open walkthrough.
- Learning loads and rating publication are generation guarded.
- Archived weight-semantics history is visible instead of silently dropped by the C# DTO.
- Reset commands are serialized against load/feedback/reset work and stale reset responses are rejected.
- Reset wording now states the real scope: global Beta weights only; semantic projector and feedback history remain.

## Deferred verification

- T008: focused/full automated verification — blocked until explicit user authorization.
- T009: live API/GUI/learning verification — blocked until explicit user authorization.
- T010: completion and QC markers — blocked until T008 and T009 pass.
