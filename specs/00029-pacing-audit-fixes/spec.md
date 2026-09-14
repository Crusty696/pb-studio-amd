# Specification: Pacing Audit Fixes

## Objective

Close the four verified Pacing/Director defects without changing public request compatibility or AMD/DirectML constraints.

## Requirements

### FR-392 Source-safe exact coverage

Generated and render-finalized cuts must cover the requested target interval contiguously while every source out-point remains within the known source duration. Short sources may be reused as multiple segments; they must never be stretched past their media duration.

### FR-393 Expected BPM correction

When `expected_bpm` is supplied and materially differs from detected tempo, the active `trigger_settings` path must use it to construct the rhythmic trigger grid. Real measured beats remain preferred near corrected grid points so musical timing is preserved.

### FR-394 Interval invariants

Contradictory minimum and maximum cut interval settings must be rejected at the API boundary. The engine must defensively enforce one effective minimum and ensure automatic maximum-length splits never create cuts below that minimum.

### FR-395 Observable graceful degradation

Semantic and Brain fallback paths must remain non-fatal, but the response must contain one compact degradation per affected mode. The Director UI must show every degradation with that item's own counts.

### TR-378 Regression coverage

Automated tests must reproduce all four defects before the fix and verify the corrected service, engine, router, render, and UI-binding behavior afterward.

### OR-355 Compatibility

No new dependency, schema migration, public request break, CUDA/ROCm path, or unrelated refactor is permitted. Existing user worktree changes must be preserved.

## Success Criteria

- SC-103: No finalized cut has `clip_start + duration > source_duration`, and coverage ends exactly at the target duration.
- SC-104: A 60 BPM override and a 180 BPM override produce different corrected rhythmic grids from the same measured-beat input.
- SC-105: Invalid interval combinations return validation failure; valid combinations cannot be split below the effective minimum.
- SC-106: Semantic and Brain runtime fallbacks are visible in API output and correctly formatted in the Director UI.

## Out of Scope

- Legacy `SyncMode` behavior.
- New pacing features or visual redesign.
- Dependency, database, or model changes.
