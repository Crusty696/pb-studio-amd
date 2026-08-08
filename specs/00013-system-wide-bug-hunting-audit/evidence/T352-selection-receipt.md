# T352 — Capability-aware Selection Receipts

Status: CONFIRMED

## Implementation

- Added immutable `ModelSelectionReceipt` with provider, model ID, task, mode,
  required and verified capabilities, source, reason, and UTC timestamp.
- Selection priority is explicit override, persisted task preference,
  capability recommendation, then another suitable live model.
- Candidates must be installed, usable, and carry the required live-verified
  capability; text-only models cannot enter a vision selection.
- Tie-break order is loaded state, configured provider preference, then stable
  provider/model ordering.
- A legacy model-only persisted choice is rejected when it is usable on more
  than one provider and no provider override disambiguates it.
- The shared failover executor performs one inventory refresh after the first
  provider failure and attempts at most three distinct receipt candidates.
- Every attempt is logged as a complete receipt.
- Vision analysis and Brain narration call the exact provider client and exact
  model ID from the receipt.
- Chat selection binds its client to the receipt provider before every model
  call and caps its provider/model retry path at three candidates.
- `/models/recommendations` now returns provider and receipt metadata.

## Static verification

- Python 3.11 `py_compile` passed for registry, inventory, models router, chat,
  video vision wrapper, and Brain narrator.
- Static call scan confirms receipt-bound calls use
  `provider=receipt.provider` and `model=receipt.model_id`.
- `git diff --check` passed.
- Runtime regressions remain deferred until T361.

## Gate

CONFIRMED: capability-safe, provider-bound selection receipts and bounded
failover are implemented for the affected runtime consumers.
