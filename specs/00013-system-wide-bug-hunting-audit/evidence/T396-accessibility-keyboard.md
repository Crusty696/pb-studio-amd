# T396 Accessibility and Keyboard

Date: 2026-07-31
Result: PASS

## Change

- Updated all 16 application views: 73/73 buttons have explicit UIA names, 63 have help text, 56 key bindings were added, and all view roots define focus navigation.
- Primary/destructive actions are named and keyboard reachable; Anchor deletion has no unsafe global Delete shortcut.
- Brain ratings use `Ctrl+1` through `Ctrl+4`, leaving numeric Cut-ID input untouched.
- Project close/save access keys are unique (`Alt+C` / `Alt+S`).
- Terminal and Anchor special surfaces use system colors for High Contrast.

## Timeline keyboard contract

- Up/Down and Home/End select previous/next and first/last cuts.
- Left/Right scrubs by 0.1 s; Shift changes the step to 1.0 s.
- Ctrl+Left/Right nudges the selected cut.
- Alt+Left/Right trims the left edge; Ctrl+Alt trims the right edge.
- Enter/Space selects the focused cut.
- Delete performs no mutation because no confirmed timeline-delete contract exists.
- Nudge and trim clamp after rounding to project, source, neighbor and minimum-duration bounds and use the epoch-bound autosave path.

## Verification

- XML parse: 16/16 views PASS.
- Shortcut/modifier and duplicate-binding scan: PASS.
- C# structure and `git diff --check`: PASS.
- Independent review found five focus, CanExecute, rounding, delete and shortcut defects.
- All five were corrected; independent re-review: PASS.
- WPF build and UIA/DPI execution remain intentionally assigned to T406/T409.
