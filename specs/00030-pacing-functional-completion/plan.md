# Plan: Pacing Functional Completion

## Instructions Check

- AMD DirectML-only inference, Python 3.11, NumPy 1.26.4, Windows paths, `PYTHONPATH=src`, `Tests/`, WPF MVVM, local/offline execution: preserved.
- No dependency, migration, public contract break, destructive cleanup, production operation, or protected audio-file change planned.
- Work remains sequential because the productive Pacing path crosses UI, router, service, engine, persistence, and timeline state.

## Implementation

1. Catalog every reachable Director/Pacing function and map UI bindings, DTOs, endpoints, runtime consumers, outputs, and existing tests.
2. Run the existing focused Pacing/Timeline/Anchor baseline and record failures plus coverage gaps.
3. Add focused regression tests for each proven contract, lifecycle, or creative-control defect before changing production code.
4. Apply minimal fixes along the active `trigger_settings` request path; keep legacy `SyncMode` untouched.
5. Re-run focused tests, Python compile sweep, C# Director tests, and WPF Release build.
6. Start the real app safely, create a disposable test project, exercise API and GUI with approved real media, and capture function-level evidence.
7. Shut down cleanly, wait for recovery completion, remove only run-owned artifacts, verify cleanup, update Brain log/learnings, and run final QC.

## Verification

- Python: focused Pacing/router/service/timeline tests with `PYTHONPATH=src`, followed by the relevant regression cluster and compile sweep.
- C#: focused `PBStudio.UI.Tests` Director/Pacing tests plus Release build with zero errors and warnings.
- Live API: generation, validation, progress, cancellation/retry, timeline reload/update, preview, degradations, and project/request isolation.
- Live GUI: every visible KI-Regie control, generate command, progress/error state, results, suggestions, and timeline handoff.
- QC: requirement-to-evidence matrix, run-owned cleanup receipt, `.completed`, then `.qc-passed` only after all P1 gates pass.
