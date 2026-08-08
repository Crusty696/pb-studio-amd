# T351 — Startup refresh and request coalescing

Status: CONFIRMED

## Implementation

- Backend lifespan performs one forced central inventory refresh per start.
- Inventory snapshots have a short freshness window and explicit invalidation.
- A shared async lock plus a second freshness check coalesces concurrent callers.
- `/models/list` and `/models/available` consume the same central snapshot.
- `GET /models/list?refresh=true` invalidates once before refreshing.
- LM Studio and Ollama probes remain parallel inside one bounded refresh.
- The published snapshot is atomic and carries a monotonic generation number.

## Static verification

- Python 3.11 `py_compile` passed for the inventory service, backend startup,
  and models router.
- Static call enumeration confirms provider listing and capability calls occur
  only inside the central service for these API paths.
- Runtime regression execution remains deferred until T361.

## Gate

CONFIRMED: startup refresh, bounded provider bundling, invalidation, and
concurrent request coalescing are implemented without a request fan-out.
