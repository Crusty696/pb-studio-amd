# T350 — Central provider and model inventory

Status: CONFIRMED

## Implementation

- Added `src/pb_studio/ai/model_inventory.py`.
- Provider state is one of `offline`, `online_empty`, `ready`, or `degraded`.
- Every model record carries provider, installed, loaded, downloadable, usable,
  capabilities, verification time, and status reason.
- LM Studio installed state uses supported `/v1/models`; loaded state uses
  `lms ps --json`.
- Ollama installed state uses `/api/tags`; loaded state uses `/api/ps`.
- LM Studio private indexes and `lms ls --detailed` are not used.
- Same-name models remain provider-specific rather than becoming an ambiguous
  synthetic `both` model.
- LM Studio exposes only a general Discover URL for unavailable models.
- An absent Ollama model becomes downloadable only after a bounded, allowlisted
  live manifest response from `registry.ollama.ai`.
- Provider probes are bounded, shell-free, and publish one atomic snapshot.

## Static verification

- Python 3.11 `py_compile` passed.
- No private-index, `lms ls`, shell execution, redirect-following, or
  unbounded provider call is present.
- Runtime regression execution remains deferred until T361 by the approved gate.

## Gate

CONFIRMED: the central inventory contract and truthful state sources are
implemented without new dependencies or private runtime indexes.
