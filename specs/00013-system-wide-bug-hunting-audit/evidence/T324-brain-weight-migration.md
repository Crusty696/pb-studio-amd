# T324 – Brain Weight Migration

Status: CONFIRMED
Decision: D04

## Replay gate

- Scanned 24 project `state.db` files under `C:\Users\david\Documents\PBStudio`.
- Total `feedback_events`: `0`.
- Legacy global weights contained 102 uniformly updated rows.
- The event log is therefore incomplete and cannot reproduce the legacy weights.
- D04 selects a versioned archive plus neutral v2 restart; no legacy row was replayed or deleted.

## Backup

- Path: `C:\Users\david\AppData\Roaming\PB_Studio\backups\brain_backup_20260729_035819_955056\weights.db`
- Size: `36,864` bytes
- SHA-256: `1e3183c3204d7af9897e80f60924bf41e5f4f4f0d885b631d6216e02dbdc83fa`
- Backup method: SQLite `VACUUM INTO`
- Backup `PRAGMA quick_check`: `ok`

## Copy rehearsal

- Work directory: `C:\Users\david\AppData\Local\Temp\PBStudio-T324-kp72giz4`
- Rehearsal user version: `2`
- Rehearsal `quick_check`: `ok`
- Archived v1 rows: `102`
- Active v2 rows: `0`
- New `feedback_count`: `0`
- Rehearsal SHA-256: `711769adc442180b840602aff308d0dfb514eba4cb0ece94f8cd53804df5fd2a`

## Restore probe

- Restored copy SHA-256 equals backup SHA-256: `true`
- Restored copy user version: `1`
- Restored copy rows: `102`
- Restored copy `quick_check`: `ok`

## Production migration

- Backend port 8765 had no listener before migration.
- Migration: `002_sparse_credit_v2.sql`, one SQLite transaction.
- Production user version: `2`
- Production `quick_check`: `ok`
- `axis_weights_v1_archive`: `102` rows
- Active `axis_weights`: `0` rows
- `feedback_count`: `0`
- Logical archived-row SHA-256 equals backup-row SHA-256:
  `05d212b7190e370225baa93c225d7c7dc60e64884562c9b340dd53317bd765c2`
- Production file SHA-256 after migration:
  `0aba99ae8d0c9e40363279a4afc5a93a9a344595ac71be2e8f8868a8623b5b81`
- `brain_meta` stores the backup path, backup hash, semantics version, reason,
  migration timestamp, and exact feedback counter.

## Recovery contract

- New feedback increments `feedback_count` atomically with sparse weight deltas.
- Outbox replay compares both per-bucket deltas and the feedback counter.
- Compensation restores both weights and counter.
- Legacy schema-v1 pending outboxes remain readable through operation-wide delta fallback.
- Reset clears only active v2 weights and the v2 counter; the v1 archive remains intact.

## Static verification

- Python syntax: PASS for `feedback_logger.py` and `weight_store.py`.
- Migration parser: 6 statements.
- `git diff --check`: PASS.
- Functional/fault tests: intentionally deferred to T332/T334.
