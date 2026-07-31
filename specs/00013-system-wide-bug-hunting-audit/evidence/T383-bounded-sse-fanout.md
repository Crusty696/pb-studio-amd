# T383 Bounded SSE Fanout

Date: 2026-07-31
Result: PASS

## Change

- Every progress/log subscriber owns one queue bounded to 500 events.
- All async and worker-thread publishers converge on `_fanout_event()` and
  `_enqueue_event()`.
- Queue saturation deterministically removes the oldest event before adding
  the newest; `QueueFull` and the defensive empty/full race never escape.
- Global and per-client drop counters are available through
  `get_event_queue_drop_metrics()`.
- Disconnect uses `unregister_event_queue()` and reports the client's drop
  count while removing queue and per-client metric state.

## Verification

- Agent and team-lead `py_compile`: PASS.
- `git diff --check`: PASS.
- `backend/dependencies.py` SHA-256:
  `ffb6470cccc7d584f496287e67a5d83a5a3fc4aee55cb9f3aa454affafa37d0d`.
- `backend/routers/events_router.py` SHA-256:
  `362f58957ad489a2f1a0fd3583407f10f8f4776b0068763e91fa44524c948d5d`.

Queue saturation fault injection remains deferred to T404.
