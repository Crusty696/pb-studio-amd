# T376 Video Project Context

Date: 2026-07-31
Result: PASS

## Change

- Import and analysis register with `state.project_operation()` before their
  first asynchronous boundary.
- Media/vector lookup uses frozen `context.project_id`; no late active-project
  fallback remains in the SigLIP path.
- Import registration, analysis DB/cache update and vector outbox/index writes
  run inside `state.project_commit(context)`, making guard plus synchronous
  commit atomic against epoch invalidation.
- Cancelled tasks propagate `CancelledError`; stale contexts become HTTP 409.
- A GPU worker that outlives its cancelled await can compute but cannot enter a
  stale commit scope.

## Review and Verification

- Agent static verification: `py_compile` and `git diff --check` PASS.
- Team-lead cross-zone review replaced check-then-write guards with atomic
  commit scopes and grouped vector dedupe plus add under one epoch boundary.
- Final `py_compile` for AppState, project, video and pacing routers: PASS.
- Final `git diff --check` for those files: PASS.
- `backend/routers/video_router.py` SHA-256:
  `6bccf3565a11655018aeca91ea88f3a887e87150da1f67a17560823bf2971757`.

Functional GPU/project-switch fault injection remains deferred to T404/T410.
