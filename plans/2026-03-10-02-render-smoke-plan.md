# Work Plan – Render / Export End-to-End Smoke Test

Date: 2026-03-10
Status: planned

## Goal
Verify whether PB Studio can complete a minimal real render/export cycle end-to-end.

## Why this comes next
- Core import/analyze/pacing/video backend flows are now live-verified.
- Render/export is one of the highest remaining unknowns and a strong release-readiness gate.

## Preparation
### Files / areas to inspect first
- `backend/routers/render_router.py`
- render-related response schemas / request expectations
- `PBStudio.UI/ViewModels/ProductionViewModel.cs` if needed

### Tools needed
- `read` for route/client inspection
- `exec` for live API script and output validation
- `write` / `edit` for result compression

### Research questions
- What exact preconditions does `/render/start` need? timeline already generated? current audio path? output path constraints?
- Is rendering background-task based, and how should status be polled safely?
- What minimal output file is sufficient to validate success?

## Execution steps
1. Inspect render router and confirm required inputs / state dependencies.
2. Reuse or create a minimal timeline if required.
3. Start a real render with a temporary output path.
4. Poll render status at safe intervals until completion/failure.
5. If output exists, inspect file presence/size/basic media metadata.
6. Update `STATUS_MATRIX.md` and `WORKLOG.md`.

## Success criteria
- render start accepted
- status progression observable or final state returned
- output file produced and non-empty

## Stop / ask conditions
- destructive overwrite risk outside temp/test output area
- unexpectedly long/high-risk job behavior
- signs of data corruption or runaway resource use
