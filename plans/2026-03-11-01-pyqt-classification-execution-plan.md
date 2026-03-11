# Work Plan – PyQt Removal Classification Execution

Date: 2026-03-11
Status: in-progress

## Goal
Turn the previously planned PyQt-removal review into a concrete migration classification with decisions that reduce parity risk.

## Scope
- Inspect deleted legacy PyQt widgets under `src/pb_studio/ui/...`
- Map them against current WPF views/viewmodels
- Classify each removed area into:
  - Keep (concept survives as-is elsewhere)
  - Replace (covered by current WPF flow)
  - Restore (should come back substantially unchanged)
  - Rebuild (feature still needed, but should be rebuilt natively in WPF)
- Update durable project status artifacts

## Files / evidence
- `git diff --name-only --diff-filter=D -- src/pb_studio/ui`
- `PBStudio.UI/Views/*.xaml`
- `PBStudio.UI/ViewModels/*.cs`
- `WORKLOG.md`
- `STATUS_MATRIX.md`

## Tools
- `exec` for deleted-file inventory and repo inspection
- `read` for WPF views and current status files
- `write` / `edit` for plan + classification + status updates

## Decision rules
- Replace: current WPF flow already covers the user-facing job well enough
- Rebuild: current WPF lacks important behavior or only has placeholder/basic coverage
- Restore: legacy implementation is still the least-wrong path and should be revived (expected to be rare)
- Keep: mostly for concepts retained without needing a standalone legacy widget

## Success criteria
- Every deleted PyQt functional area has an explicit migration decision
- WPF parity risk becomes concrete instead of vague
- Current priority list can move past this block
