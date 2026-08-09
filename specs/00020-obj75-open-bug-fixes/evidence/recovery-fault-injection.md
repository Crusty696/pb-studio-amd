# T042/T043 Recovery Fault-Injection Receipt

**Result:** PASS

**Live restore executed:** no

**Basetemp:** `C:\Users\david\AppData\Local\Temp\pb_obj75_fault_a00c03cb847a4d0698703ea10e89feb9`

## Verified state machine

- Snapshot: `PREPARING -> STAGED -> CURRENT -> COMMITTED` with injected aborts
  after PREPARING, STAGED and CURRENT.
- A PREPARING snapshot keeps the previous pointer; a STAGED snapshot publishes
  only the pointer and never replays backup bytes over newer live work.
- Restore: STAGED, partially APPLYING and VALIDATING converge idempotently;
  corrupt/missing next generations roll back or fail closed.
- COMMITTED snapshot and restore journals validate only and never re-apply over
  work produced after recovery.
- Every target is copied to a sibling temporary file on the target volume before
  `os.replace`; simulated Windows open-handle denial remains journaled and fails
  closed without modifying the live target.
- Multi-artifact partial restore resumes from the durable `applied` receipt and
  converges both targets before CURRENT commit.

## Recovery cluster

```text
pytest Tests/test_recovery_generation.py Tests/test_recovery_bootstrap.py
       Tests/test_recovery_owner_adapters.py Tests/test_recovery_barrier.py
       -q --basetemp <unique-guid-path>
```

Receipt: `44 passed, 4 warnings in 19.73s` on Python 3.11.9.

The four warnings are unchanged third-party madmom/SciPy deprecations. All
faults and restores used temporary generations. `request_restore_generation()`
only writes a durable request; target replacement remains bootstrap-only.

## Retention safety

CURRENT, its parent and every journal-referenced generation are protected.
Deletion requires an exact caller-confirmed candidate tuple; any changed plan
fails before deletion. No user recovery generation was deleted in this task.
