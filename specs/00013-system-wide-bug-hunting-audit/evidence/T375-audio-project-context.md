# T375 Audio Project Context

Date: 2026-07-31
Result: PASS

## Change

- Import, analysis and stem separation register through
  `state.project_operation()` before their first await.
- Import registration, analysis cache/clip/DB update, stem metadata and
  subtrack updates use `state.project_commit(context)`.
- Stem success markers and synthesized instrumental publication are guarded;
  no stale operation can publish a reusable success marker.
- Local import metadata is detached from the registered state dictionary
  before later asynchronous enrichment.
- Stale context becomes HTTP 409 and `CancelledError` propagates.

## Review and Verification

- Seven synchronous commit scopes contain no `await`.
- Agent and team-lead `py_compile`: PASS.
- `git diff --check`: PASS.
- `backend/routers/audio_router.py` SHA-256:
  `89a33833a9aa9f58b5a12395440fe5fc57829bca7b1096d546944f332bc9cabf`.
- Raw separator outputs may finish in the frozen source project's cache after
  worker cancellation, but remain unpublished without the guarded marker and
  cannot target the new project.
- Truthful persistence failure propagation is intentionally closed by T379.

Functional fault injection remains deferred to T404/T410.
