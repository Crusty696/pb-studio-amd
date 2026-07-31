# T381 Brain Project Leases

Date: 2026-07-31
Result: PASS

## Change

- Each Brain binding publishes an immutable canonical state path, epoch and
  optional project ID with its SQLite connection.
- Read leases retain retired connections until release; swaps and unbinds
  defer close while a reader is active.
- `run_write()` holds the binding lock across stale validation and the complete
  mutation, so a project swap cannot interleave with a write.
- Feedback registers as an AppState project operation and acquires an exact
  path/epoch/project-ID lease before reading or writing.
- Project activation supplies the invalidated AppState epoch and database
  project ID to the Brain binding; pacing uses the same identity contract.

## Critical Review

- A raw current-connection lease was insufficient for feedback during the
  invalidate-to-rebind window. Team-lead review added AppState registration and
  exact identity matching before accepting T381.
- Retired slots close only after their final lease; stale writes fail closed
  with `StaleBrainProjectLeaseError`.
- Singleton shutdown defers the shared Brain-store close while leased project
  slots remain active.

## Verification

- Full modified Brain/backend `py_compile`: PASS.
- `git diff --check`: PASS.
- `backend/_brain_singleton.py` SHA-256:
  `56d78616a89fcb46d4ba91083837515868a2bcbfec5e6411d2e9dbd880ebd833`.
- `backend/routers/brain_router.py` SHA-256:
  `1fa78651db4b667c0c15316e197742943011eafd60c4b27959c94203caf5431d`.
- `src/pb_studio/brain/brain_service.py` SHA-256:
  `30783aa7be19e0b0ab25063038d29a71b5348d0cb79f71a7c806af8b3c2b06e4`.

Concurrency and injected swap tests remain deferred to T404/T410.
