# T383 Bounded SSE Fanout

Date: 2026-07-31
Result: PASS

## Change

- Every progress/log subscriber owns one queue bounded to 500 events.
- Subscriber filters are registered with the queue and applied before enqueue,
  so log traffic cannot evict progress traffic (or vice versa).
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
  `7a1cdccc03ab16065dc448b8b709951ae7307ee6f547c60bf8581549b40548c4`.
- `backend/routers/events_router.py` SHA-256:
  `ea242b9f39a7e4bbb8f5313197404b33eaa7f6d3a1888c3a140e3ab981646d46`.

Queue saturation fault injection remains deferred to T404.
