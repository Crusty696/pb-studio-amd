# T319 — Snap provenance

Status: CONFIRMED

## Root cause

`_snap_cuts_to_subtrack_boundaries()` changed only the cut timestamp. A source
`downbeat`, `snare`, or other trigger retained its old type and strength after
being moved to a different semantic event.

## Contract

- A snapped cut is reclassified as `subtrack` with boundary strength `1.0`.
- Provenance retains source time, source type, source strength, target time,
  snap distance, operation, and classification.
- Quality distinguishes exact coordinate alignment from the underlying
  `detected_subtrack_boundary`; it does not claim a measured musical downbeat.
- Newly inserted boundaries use `boundary_insert` provenance.
- `PacingCut` owns structured provenance and both advanced and round-robin
  cut-list conversion persist it as `metadata.trigger_provenance`.

## Static verification

- Python syntax and `git diff --check` — PASS
- Assignment scan found one production endpoint-time mutation; it now updates
  type, strength, and provenance together.
- Runtime snap regressions remain deferred to T332.
