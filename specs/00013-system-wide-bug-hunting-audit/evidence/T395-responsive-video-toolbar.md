# T395 Responsive Video Toolbar

Date: 2026-07-31
Result: PASS

## Change

- Video actions use a width-driven `WrapPanel`.
- Analysis counters and thumbnail progress occupy a second wrapping row, so
  narrow windows neither clip nor overlay the status groups.
- Commands and behavior are unchanged.

## Verification

- XAML parse and `git diff --check`: PASS.
- WPF Release build: PASS, 0 warnings, 0 errors.
- `PBStudio.UI/Views/VideoLibraryView.xaml` SHA-256:
  `cfcb2b3958b689a746fd37d614f149fd5fed2425d724f89d6b4bd9926484ef5e`.

Resolution and DPI runtime evidence remains T408.
