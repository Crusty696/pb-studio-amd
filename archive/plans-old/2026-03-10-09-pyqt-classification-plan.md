# Work Plan – Removed PyQt Area Classification

Date: 2026-03-10
Status: planned

## Goal
Classify the removed legacy PyQt UI areas into:
- Keep
- Replace
- Restore
- Rebuild

## Why this comes next
- Core backend and key WPF glue paths are now largely green.
- The remaining migration risk is architecture drift and accidental feature loss from removed PyQt files.

## Preparation
### Files / areas to inspect first
- git diff / deleted file list under `src/pb_studio/ui/...`
- corresponding WPF views/viewmodels now present
- reference expectations from migration docs if needed

### Tools needed
- `exec` for deleted file inventory / diff stat
- `read` for representative removed and replacement files
- `write` / `edit` for classification results

### Research questions
- Which removed files were pure legacy UI shell vs feature-bearing UX?
- Which capabilities are already replaced in WPF?
- Which areas still need rebuild rather than assuming parity?

## Execution steps
1. Inventory removed PyQt UI files by functional area.
2. Map each area against existing WPF coverage.
3. Classify into Keep / Replace / Restore / Rebuild.
4. Update status/worklog with concise migration guidance.

## Success criteria
- migration risk is reduced through explicit classification
- next missing parity areas become concrete instead of vague
