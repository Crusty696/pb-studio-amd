# T378 Timeline Project Lifecycle

Date: 2026-07-31
Result: PASS

## Change

- WPF project contexts now bind generation, project path and cancellation.
- Overlapping project transitions use a counter; no context can be captured
  while any create/open/close transition remains active.
- Timeline autosave takes a deep entry snapshot and owns a linked CTS plus
  sequence. Only the current sequence and project path may publish UI status.
- Preview snapshots start/duration, forwards cancellation through
  `IApiClient`, and rejects stale responses before path/status/event updates.
- Project transition cancels both operations and marks the Timeline
  non-mutable until the new project Timeline refresh is applied. A delayed
  View timer therefore cannot post old/empty entries into the new project.

## Critical Review

- Fixed the existing preview cancellation parameter that was accepted but not
  forwarded by `ApiClient`.
- Fixed overlapping-transition truth: a bool was insufficient when two
  transitions complete out of order; the counter keeps the context unstable
  until all have ended.
- Fixed delayed-autosave-after-open by gating mutation on completed Timeline
  refresh, not only on the current ProjectService generation.
- Replaced replaceable-field capture with local CTS ownership; stale finalizers
  cannot clear the state of a newer operation.

## Verification

- `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore`:
  PASS, 0 warnings, 0 errors.
- `git diff --check` for all four changed C# files: PASS.
- SHA-256:
  - `ProjectService.cs`:
    `6ebdd1784d158556819abde55f038e607f82403c9c5b5f7f2c3b74a3d66e9180`
  - `IApiClient.cs`:
    `96f199c7ac515aa67886bf4373560a16f6e5c7462ea0f71a952f08c94b41eff6`
  - `ApiClient.cs`:
    `23bef5723c8daf3e0de766f497157ad6839177c905a7a92fd6eee29f082c6529`
  - `TimelineViewModel.cs`:
    `f90e53634d5e8f9863369dfcb1182ec959d0e9d025f68cd87268b0b1060324a0`

Functional A→B fault injection remains deferred to T404/T410.
