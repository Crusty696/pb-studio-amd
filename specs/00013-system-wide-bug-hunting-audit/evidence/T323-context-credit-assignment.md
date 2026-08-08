# T323 – Context-relevant Credit Assignment

Status: CONFIRMED

## Root cause

- `%APPDATA%\PB_Studio\brain\weights.db` contains exactly 102 rows: 17 axes × 6 context levels.
- Every row has the identical state `positive_count=6.0`, `negative_count=4.0`.
- `FeedbackLogger._snapshot_weights()` formed the full Cartesian product without reading the rated cut's bridge values, axis availability, or axis-specific context.
- The Release-QC state has no feedback events and no pending outbox, so the 102-row state cannot be replay-attributed to the current project.

## Credit formula

- Source evidence: persisted `bridge_values`; legacy fallback: persisted `brain_scores`.
- Axis relevance: finite bridge value clamped to `[0,1]`; values below `0.05`, absent axes, and unavailable semantic axes are excluded.
- Context relevance:
  - Audio trigger/energy axes: levels `0,1,4,5`.
  - Clip-length axes: levels `0,1,5`.
  - Motion/scene/pace axes: levels `0,1,3,5`.
  - Brightness/color/semantic/mood axes: levels `0,2,3,5`.
- Context attenuation: level 0 `0.25`, level 1 `0.50`, level 2 `0.60`, level 3 `0.75`, level 4 `0.85`, level 5 `1.00`.
- Per-bucket delta: rating base delta × bridge relevance × context attenuation.

The first persisted Release-QC cut statically resolves from 102 identical
updates to 38 evidence-weighted assignments. Its zero trigger axes, sub-0.05
scene score, and legacy synthetic semantic score are excluded.

## Data flow and recovery

1. `/brain/feedback` loads the rated cut's scores, bridge values, context keys, and axis availability.
2. `build_credit_assignments()` produces the sparse deterministic assignment list.
3. An empty assignment returns HTTP 409 without mutating weights or event history.
4. The durable outbox stores the assignment list and each bucket's exact weighted deltas.
5. Recovery relation checks, apply, compensation, and restore use per-item deltas; legacy pending outboxes remain readable through top-level delta fallback.
6. `updated_buckets` reports the number of actually changed rows.

## Static verification

- `weights.db`: `PRAGMA quick_check=ok`, schema version 1, 102 identical rows.
- Pending feedback outbox: absent.
- Python syntax: PASS for `feedback_logger.py` and `brain_router.py`.
- Static caller scan: the production endpoint supplies explicit assignments.
- Stale Cartesian-product scan: removed.
- `git diff --check`: PASS.
- Functional/recovery tests: intentionally not run before T332.
