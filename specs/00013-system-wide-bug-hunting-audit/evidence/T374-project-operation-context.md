# T374 ProjectOperationContext

Date: 2026-07-31
Result: PASS

## Contract

- `ProjectOperationContext` is frozen and carries project DB ID, resolved
  project root and monotonic epoch.
- `project_operation()` captures and registers the current asyncio task while
  holding the lifecycle lock; nested scopes use a reference count.
- `require_project_context_current()` rejects stale identity with
  `ProjectContextChangedError`.
- `project_commit()` holds the project-state lock across guard and synchronous
  mutation, closing the check-then-write race against epoch invalidation.
- Project transitions invalidate the old epoch before bounded cancellation and
  drain. Tasks that ignore cancellation cannot pass the commit guard.
- Candidate catalogs, analysis caches, timeline, audio path and ID counters are
  installed under the established `state_lock -> lock` order.
- Create, open and close serialize through one lifecycle lock. Open loads media
  and timeline into an isolated candidate before the live swap.

## Critical Review

- Cancellation finalization does not return from the async-context-manager
  `finally` block and therefore cannot suppress the original exception.
- Existing state container identities are preserved with clear/update.
- Brain rebind occurs only after stale epochs are invalidated and registered
  tasks are drained; the new Brain binding receives the exact epoch and
  project ID before runtime-state publication.
- The bounded 5-second drain prevents an uncooperative task from hanging a
  project transition; its stale commit remains blocked.
- A project-specialist review that produced no evidence inside its bounded
  window was interrupted once under `LOOP_GUARD`; no blind rerun occurred.

## Static Verification

- `.venv\Scripts\python.exe -m py_compile backend\app_state.py
  backend\routers\project_router.py`: PASS.
- `git diff --check -- backend\app_state.py
  backend\routers\project_router.py`: PASS.
- Active SDD validator: `valid=true`, `phase=open`, no findings.
- `backend/app_state.py` SHA-256:
  `e727ac577c29401698b95e5c14113a10a44112db4b3f4b6a6b359f21f114ba8e`.
- `backend/routers/project_router.py` SHA-256:
  `fd872261ccf042a3fd34737d676667c7c57a102f92296fda69ff947fee8dc5a8`.

Functional fault injection remains intentionally deferred to T404/T410 under
the approved test-bundling rule.
