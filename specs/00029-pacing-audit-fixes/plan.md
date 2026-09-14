# Plan: Pacing Audit Fixes

## Implementation

1. Add focused regression tests for source bounds, BPM correction, interval validation/enforcement, and degradation aggregation/UI formatting.
2. Make cut finalization source-aware and preserve appended segments in render serialization.
3. Apply `expected_bpm` to the active measured-beat trigger grid with adaptive measured-beat snapping.
4. Validate and defensively normalize effective interval constraints.
5. Aggregate semantic/Brain fallback provenance into the existing response contract and fix UI formatting.
6. Run focused Python tests, compile sweep, full relevant Pacing tests, and WPF Release build.
7. Record QA artifacts, completion markers, and Brain progress.

## Risk Controls

- Preserve existing request/response fields.
- Keep source-duration probing behind existing cache/probe helpers.
- Bound corrected BPM grids to media duration.
- Emit user-safe degradation reasons, never raw exception text.
- Do not touch unrelated dirty files.

## Verification

- `PYTHONPATH=src pytest` on new and affected regression modules.
- `PYTHONPATH=src python -m compileall` on changed Python modules.
- Relevant Pacing/router/render test cluster.
- `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release`.
