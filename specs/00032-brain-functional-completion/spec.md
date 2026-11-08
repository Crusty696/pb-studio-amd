# Spec 00032: Brain/HIRN Functional Completion

## Objective

Complete the productive Brain/HIRN source paths before any verification run. Preserve the accepted Beta-Bernoulli/backoff architecture and DirectML-only inference contract while repairing concrete lifecycle, learning, semantic, API, and WPF defects.

## User Stories

### US1 — Trustworthy Brain scoring

As a user, I need Brain confidence and axis contributions to use only available, normalized evidence so that scores are explainable and not distorted by unavailable or stale data.

### US2 — Durable, project-safe learning

As a user, I need feedback, learning sessions, reset, and projector training to affect only the intended project/cut evidence and to survive normal project transitions safely.

### US3 — Complete HIRN interface

As a user, I need every visible HIRN action, status, statistic, suggestion, feedback, explanation, and reset path to publish truthful state and recover from cancellation or failure.

## Functional Requirements

- FR-408: Score only available finite axes with normalized priors, explicit availability, and deterministic contribution reporting.
- FR-409: Preserve sparse evidence-aware Beta-Bernoulli credit assignment and hierarchical context backoff.
- FR-410: Bind feedback, suggestions, statistics, explanations, reset, and projector work to the current project lease without cross-project publication.
- FR-411: Validate semantic embedding dimensions, norms, finiteness, availability, and trained-projector state; never fabricate semantic success.
- FR-412: Make all six Brain endpoints truthful, bounded, cancellable where applicable, and consistent with their schemas.
- FR-413: Make HIRN WPF loading, learning-session selection, feedback, explanation, refresh, reset, error, and project-transition states functional.
- FR-414: Catalog every productive Brain/HIRN function and preserve implementation-only evidence while verification is prohibited.

## Technical Requirements

- TR-381: Runtime ONNX inference remains DirectML-only with both required session flags and shared GPU lifecycle.
- TR-382: Existing persisted learning data must not be migrated, reset, or destructively rewritten during this fix phase.
- TR-383: No tests, builds, GUI runs, provider probes, or completion/QC markers without explicit user authorization.

## Out of Scope

- Replacing Beta-Bernoulli with another learning algorithm.
- Adding dependencies or changing locked runtime versions.
- Database/schema migrations or automatic reset of learned state.
- Verification and release claims during the fix phase.

## Acceptance Criteria

- AC-1: Productive Brain/HIRN controls and runtime paths are cataloged.
- AC-2: Concrete source defects across learning, semantic scoring, API lifecycle, and WPF state are repaired.
- AC-3: No unavailable/non-finite evidence contributes to a final score or feedback credit.
- AC-4: Project transitions cannot publish stale Brain data or mutate the wrong project.
- AC-5: Implementation evidence and Brain log identify all edits and explicitly mark runtime verification unknown.
