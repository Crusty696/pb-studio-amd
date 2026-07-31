# T397 CachedTab Template Reapplication

Date: 2026-07-31
Result: PASS

## Change

- `OnApplyTemplate()` retains the previous content-holder reference.
- Existing cached presenters are detached from the previous holder and added
  exactly once to the replacement holder.
- Presenter content is not reassigned, preserving active views and their
  in-memory state across template reapplication.

## Verification

- Agent review: no duplicate-parent or duplicate-child insertion path remains.
- `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore`:
  PASS, 0 warnings, 0 errors.
- `git diff --check`: PASS.
- `PBStudio.UI/Controls/CachedTabControl.cs` SHA-256:
  `edcd3992461dd3d2fe6743dc9380a2df66ab32a285df9525bc89b75d20eb01c1`.

Interactive template/theme switching remains part of T408 GUI QC.
