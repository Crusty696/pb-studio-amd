# T036/T038-T040 Projector V2 Receipt

**Result:** PASS

**Live migration executed:** no

**Parent basetemp:** `C:\Users\david\AppData\Local\Temp\pb_obj75_parent_projector_d2547620e21e4ac9a7827afcd2f576f6`

## Implemented contract

- Catalog V4 stores immutable `project_uuid`; legacy rows receive deterministic
  UUIDv5 values and new projects receive UUIDv4 values.
- State migration 002 binds the State DB to its catalog identity and backfills
  stable `event_uuid` values idempotently.
- Projector V2 persists generation ancestry, applied event UUIDs, pending events,
  per-project checkpoints and an inventory digest.
- Training uses a copy, validates a same-volume staged artifact, fsyncs it and
  atomically publishes it with `os.replace`; active readers are swapped only
  after validation.
- The first V2 publish archives a hash-addressed immutable V1 artifact. The V1
  restore path validates and atomically republishes that artifact.

## Parent verification

```text
PYTHONPATH=src .venv\Scripts\python.exe -m pytest
  Tests/test_brain_projector_v2.py
  Tests/test_brain_learned_projector.py
  Tests/test_brain_cross_modal.py
  Tests/test_brain_core.py
  Tests/test_brain_router.py
  Tests/test_project_brain_binding.py
  Tests/test_project_persistence.py
  Tests/test_brain_recovery.py
  Tests/test_brain_backup.py
  -q --basetemp <unique-guid-path>
```

Receipt: `89 passed, 4 warnings in 53.57s` on Python 3.11.9.

Covered cases include deterministic backfill, A/B/A inventory ordering,
ID reuse, missing embeddings as pending, retry/exactly-once application,
replace failure, concurrent readers, restart/load and V1 restore.

## Safety boundary

All migration and restore tests used temporary copies. T037's pre-migration
generation remains untouched and hash-valid. No user Catalog, State DB or
Projector artifact was opened for migration by this verification.
