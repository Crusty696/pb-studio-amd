# T313 — Temp-, Resume- und Prozessisolation

Status: `CONFIRMED`

## Job workspace

Every render now has:

- a sanitized persistent job token derived from `queue_job_id` or task ID;
- a fresh UUID run ID for each execution or restart;
- a private workspace:
  `.temp_render/<job-token>/<run-id>/`;
- a private `concat_list.txt` and deterministic per-run `norm_<index>.mp4`;
- a staging output named with both job token and run ID.

Restart/resume therefore recomputes into a new run workspace and a new staging
file. It cannot reuse or overwrite an interrupted manifest, normalized clip or
partial output. The prior published target remains untouched until T312 passes
and the new staging file is atomically exchanged.

`render_router._execute_render()` passes the persistent queue job ID into
`RenderService`; ad-hoc callers receive an independent generated token.

## Process ownership

Long-running render-adjacent probe and validation subprocesses now use the same
registered, hidden, capture runner as the render job. It:

- polls the task-specific cancel callback;
- kills only the currently owned child on job cancel or timeout;
- unregisters and closes pipes on every terminal path;
- remains visible to the existing global shutdown termination sweep.

Normalization and final FFmpeg loops retain their existing task-specific cancel
polling. A cancel is translated back to the router's `_RenderCancelled` state.

## Cleanup

The job removes only its own normalized files, manifest and empty workspace
ancestors. No recursive or cross-job deletion is used. Shared final output is
only changed by validated atomic replacement.

## Static verification

- `render_service.py`: Python 3.11 syntax/AST `PASS`, 52,684 bytes, 1,311 lines
- `render_router.py`: Python 3.11 syntax/AST `PASS`, 34,118 bytes, 906 lines
- Static path scan: no shared run-level manifest or normalization path
- Stable queue job token plus unique run UUID: `CONFIRMED`
- Validator and probe subprocesses use `_run_capture_process`: `CONFIRMED`
- `git diff --check`: `PASS` except pre-existing SDD markdown EOL notices
- Runtime resume/cancel/fault execution remains deferred to T334/T336
