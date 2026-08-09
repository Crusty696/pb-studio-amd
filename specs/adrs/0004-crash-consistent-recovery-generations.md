# ADR-0004: Crash-konsistente Recovery-Generationen

**Status:** Accepted for implementation

**Date:** 2026-08-09

**Objective:** OBJ-75 / FR-389–FR-391

## Context

PB Studio persists one logical work state across SQLite databases, project JSON,
Chat history, Brain files, embeddings, Projector state, FAISS, Stem markers and
external references. Independent file copies can restore mixed generations.
`config.json` itself locates the main database, so recovery cannot depend on it.

## Decision

1. A stdlib-only bootstrap uses the fixed control root
   `%LOCALAPPDATA%\PB_Studio\recovery-control\v1` before backend Config, file
   logging, database, router, Brain, vector or render initialization.
2. Control files are `CURRENT`, `journal.json` and
   `generations/<generation_id>/manifest.json`. The control root never snapshots
   itself and cannot be overridden by Config, CWD or `.env`.
3. A process-wide Recovery Write Barrier blocks new owner writes. Owner adapters
   drain or return BUSY; open product handles are never bypassed during restore.
4. Every generation covers all registered consistency groups from the OBJ-75
   Truth-Source-Matrix. External media/model/runtime files are receipts, not
   restore targets. Derived caches are invalidated unless explicitly promoted.
5. SQLite sources use the online backup API. File artifacts stage on their target
   volume, flush and fsync, hash-validate, then publish through same-volume
   replacement. `CURRENT` is replaced and its parent directory durably synced.
6. Restore occurs only in bootstrap with no product handles open. It rolls a
   fully staged generation forward; otherwise it restores verified previous
   hashes. Product initialization fails closed if neither path validates.

## Durable journal

`PREPARING -> STAGED -> APPLYING -> VALIDATING -> COMMITTED`

- Each transition and each applied target has a durable receipt.
- Crash in `PREPARING`: discard only unreferenced staging.
- Crash in `STAGED`: validate complete staging, then roll forward or discard.
- Crash in `APPLYING`/`VALIDATING`: resume remaining targets or roll back every
  applied target using recorded previous hashes.
- `COMMITTED`: `CURRENT` must reference the same manifest digest.
- Retention protects `CURRENT`, its parent and every journal-referenced generation.

## Manifest minimum

- generation ID, parent, schema version, timestamp, config/project inventory digests
- per artifact: logical ID, group, owner, class, required flag, absolute target,
  volume ID, generation-relative path, size, SHA-256, adapter, schema/user_version
  and restore policy
- external receipts: canonical path, required flag, size, mtime, content hash and
  degraded-mode policy

## Reversibility

The ADR and new generation store are reversible. UUID/path migrations remain
one-way until T037/T040 prove restoration of the untouched pre-migration
generation. No down-migration is used.

## Consequences

- Startup happens in two gates: stdlib recovery, then post-Config schema/root
  validation before product owners initialize.
- Snapshot may return BUSY rather than cancel non-cancellable Stem/Render work.
- Cross-volume atomicity is logical and journal-driven, never claimed as one
  filesystem operation.
