# Work Plan – Timeline / Production UI Workflow Verification

Date: 2026-03-10
Status: planned

## Goal
Verify the next major remaining user-facing gap: whether the WPF-side Timeline / Production workflow is actually coherent beyond backend API success.

## Why this comes next
- Core backend flows are now broadly green: import, analyze, waveform, video analyze, render, stems.
- Remaining uncertainty is increasingly in UI workflow coherence and project-path/config alignment.

## Preparation
### Files / areas to inspect first
- `PBStudio.UI/ViewModels/DirectorViewModel.cs`
- `PBStudio.UI/ViewModels/TimelineViewModel.cs`
- `PBStudio.UI/ViewModels/ProductionViewModel.cs`
- any related views / commands if needed

### Tools needed
- `read` for UI workflow inspection
- `exec` for selective runtime checks or app launch smoke support
- `write` / `edit` for compression

### Research questions
- Does timeline retrieval align cleanly with generated cut-list data?
- Does ProductionViewModel derive the audio path correctly from timeline state?
- Are there obvious UI-state gaps between Director generate -> Timeline -> Production render?

## Execution steps
1. Inspect Director/Timeline/Production viewmodels and command flow.
2. Verify timeline endpoint/state assumptions against current backend behavior.
3. Identify whether the WPF workflow is coherent, partial, or missing glue.
4. If possible, do a lightweight runtime validation of the path.
5. Update status/worklog.

## Success criteria
- clear verdict on UI workflow coherence
- next concrete UI fix/test target identified if gaps exist

## Stop / ask conditions
- need for invasive UI automation or risky external actions
