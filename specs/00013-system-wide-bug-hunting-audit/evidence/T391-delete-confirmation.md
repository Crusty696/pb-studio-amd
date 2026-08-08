# T391 Destructive Delete Confirmation

Date: 2026-07-31
Result: PASS

## Change

- Single, selected/batch and all-delete paths for audio and video require an
  explicit Yes/No confirmation whose default is No.
- Single targets show name and ID; batch/all targets show the exact captured
  count.
- Cancellation returns before status, API or state mutation.
- API null/false and exceptions remain visible failures; only a backend
  response triggers refresh/success text.

## Verification

- Static ordering check for all four command paths: PASS.
- `git diff --check`: PASS.
- WPF Release build: PASS, 0 warnings, 0 errors.
- `IDialogService.cs`: `1cedb139815370d88a0263ab395ad16f91ea8bfef3fc90a7d521604ecea42080`.
- `DialogService.cs`: `33ff3e589c9641ef9c4ea6227d404cb3e78cdac3d617c4374a7761f5cee186b6`.
- `AudioLibraryViewModel.cs`: `0e401314ad6a4751c5164cfcca571e1c8a7fc6f57675e8ea8ad4debbade003b4`.
- `VideoLibraryViewModel.cs`: `8c8d4589b0dade38771af4df81d85f0e5fa00ffc8728f9b14f90d7cbc535a3ca`.

Native cancel/confirm call-count proof remains T398/T404.
