# OBJ-75 Recovery Design Receipt

## Inputs

- ADR: `specs/adrs/0004-crash-consistent-recovery-generations.md`
- Baseline: `evidence/baseline-manifest.md`
- Truth sources: `evidence/truth-source-matrix.md`

## Startup gates

1. `backend/recovery_bootstrap.py` remains stdlib-only and runs before
   `backend.main` imports product Config or creates file logs.
2. It resolves the fixed control root, validates `CURRENT`/journal/manifests and
   completes roll-forward or rollback without opening product data.
3. After Config import, a second gate compares configured roots and schema
   fingerprints to the selected manifest before routers, AppState, Brain,
   VectorStore or RenderQueue initialize.

## Owner adapters

| Adapter | Mandatory behavior |
|---|---|
| Catalog | global write lease, SQLite backup, quick/integrity check |
| Vector | stop/flush writer, terminalize journal, validate FAISS triplet against DB |
| Project | enumerate every catalog root, epoch barrier, snapshot JSON/state/chat |
| Brain | drain leases, terminalize Feedback outbox, snapshot DB/files/projector together |
| Config | lock and hash Config; never locate control root from Config |
| WPF Settings | require WPF closed/locked or record separate non-atomic scope |
| Stem | wait for registered worker/file handles or return BUSY; marker+WAV together |
| Render | drain active FFmpeg, mark queue interrupted, couple final/evidence receipts |

## Publish protocol

1. Acquire global barrier; block new writes.
2. Drain adapters in stable order: Render/Stem, Chat/Project, Brain, Vector, DB,
   Config/Settings.
3. Create SQLite backups and immutable per-volume staging.
4. Flush/fsync every artifact; write and validate hashes/schema/inventory.
5. Persist `STAGED`; apply targets with per-target journal receipt.
6. Reopen staged copies for validation; persist `VALIDATING`.
7. Replace `CURRENT`, sync its parent, persist `COMMITTED`, release barrier.

## Restore protocol

- Only bootstrap may restore.
- Complete staging rolls forward; incomplete staging rolls back applied targets.
- Main DB/FAISS, Brain feedback stores and each project group validate as units.
- Missing optional external media yields explicit degraded/unavailable state;
  missing required owned state fails closed.

## Required fault injection

- crash after every journal transition and target replacement
- half-applied Brain feedback operation
- Main-DB/FAISS generation mismatch
- corrupt/missing Config and WPF Settings
- open SQLite/vector/Stem/Render handles
- missing `.npy`, Stem WAV, project JSON or external source medium
- same-volume replace failure and multi-volume partial publish
- restart twice to prove recovery idempotency

## Gate result

Design is registered. Product implementation remains blocked until T037 proves
backup, restore dry-run and rollback for the current real local inventory.
