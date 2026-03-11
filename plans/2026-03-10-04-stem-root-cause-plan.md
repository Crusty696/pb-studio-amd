# Work Plan – Stem Separation Root-Cause Review

Date: 2026-03-10
Status: planned

## Goal
Determine why `/audio/stems/separate` returns HTTP 200 but no stem output paths.

## Why this comes next
- Basic smoke test is complete.
- The issue is now narrowed to implementation/runtime behavior, not endpoint availability.

## Preparation
### Files / areas to inspect first
- `src/pb_studio/audio/separator.py`
- any model path / output-dir logic used by `StemSeparator`
- backend logs or direct local invocation behavior if needed

### Tools needed
- `read` for source inspection
- `exec` for direct local reproduction / debug script
- `edit` / `write` for result compression

### Research questions
- Does `StemSeparator.separate()` silently succeed with empty `stems`?
- Are model files missing or misresolved?
- Are outputs written to a temp/output directory that is not being mapped back?
- Is the chosen model only expected to return specific stems that the current mapper misses?

## Execution steps
1. Inspect `src/pb_studio/audio/separator.py` and related config.
2. Identify expected return shape and output location.
3. If safe, reproduce separator directly via local debug script.
4. Determine whether the issue is model availability, output mapping, or runtime behavior.
5. Update `STATUS_MATRIX.md` and `WORKLOG.md`.

## Success criteria
- root cause narrowed to a concrete class of problem
- next action becomes implementable (fix mapping, fix model path, fix runtime, etc.)

## Stop / ask conditions
- destructive filesystem cleanup outside project scope
- risky environment-level changes
