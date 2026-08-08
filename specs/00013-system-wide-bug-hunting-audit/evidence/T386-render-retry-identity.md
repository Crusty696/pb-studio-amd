# T386 Render Retry Identity

Date: 2026-07-31
Result: PASS

## Change

- Render deduplication applies only to active `queued`, `running` or
  `interrupted` attempts.
- Completed, failed and cancelled attempts remain immutable history; a retry
  receives a new job and attempt identity.
- The canonical render identity includes timeline, settings, project identity
  and the stored content hashes of referenced media.
- `BEGIN IMMEDIATE` serializes the active-identity check and insert across
  processes.
- Render start captures an exact `ProjectOperationContext` and rejects a
  project change before publishing the task.

## Verification

- Python compile check: PASS.
- `git diff --check`: PASS.
- AMD Iron Rule scan (`libx264`, NVENC, CUDA, pynvml, nvidia-smi): PASS.
- `backend/routers/render_router.py` SHA-256:
  `5ebca2814ea7b37afb8f38907d8ef1b318ee48110ba9f0b5eeccb247e1667bfd`.
- `src/pb_studio/rendering/render_queue.py` SHA-256:
  `3a20e0f38f593f2bdac33d04cac9d7af93c0fde039736ea9186706be3a5b262a`.

Functional retry/restart validation remains bundled in T412. Persistence
failure truth is a separate T379 acceptance criterion and is not claimed here.
