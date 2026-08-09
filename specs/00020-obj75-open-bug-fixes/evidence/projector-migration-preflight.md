# T037 Projector Migration Preflight

**Result:** PASS

**Generation:** `20260809T053249Z-de05435e`

**Migration executed:** no

## Backup location

`C:\Users\david\AppData\Local\PB_Studio\recovery-control\v1\preflight\20260809T053249Z-de05435e`

- Manifest SHA-256:
  `27DE4096259C9E8C997A412F1081C05F82CC3502DDC4A87F76AD9D6072F74245`
- 70 artifacts/SQLite sources backed up and restore-verified.
- 15 optional artifacts recorded as absent instead of silently invented.
- Backend/PB Studio process was confirmed stopped before capture.
- Source files and databases were never replaced or migrated.

## SQLite receipts

| Logical source | quick_check | user_version | Total rows | Logical SHA-256 |
|---|---:|---:|---:|---|
| Catalog `pb_studio.db` | ok | 0 | 537 | `355aa42558b3898f0ffd16a9d79180a95301a9df1a9c8f4f0ce703a5511dff99` |
| Project 2 `state.db` | ok | 1 | 0 | `cbc1d8cf4ad4c45e8a138eb1e3b632e9b11b9fc816e47ed8c850fb632ee1ec02` |
| Project 3 `state.db` | ok | 1 | 0 | `cbc1d8cf4ad4c45e8a138eb1e3b632e9b11b9fc816e47ed8c850fb632ee1ec02` |
| Project 4 `state.db` | ok | 1 | 0 | `cbc1d8cf4ad4c45e8a138eb1e3b632e9b11b9fc816e47ed8c850fb632ee1ec02` |
| Brain `weights.db` | ok | 2 | 109 | `b35507c551b6b692867056886bb03eb5052839cfe6d2e1c51946d6dbbb3fc340` |
| Brain `patterns.db` | ok | 1 | 0 | `6a54d66f880b59294f7a4eb574e4bef94203af4ff8f43b252b941b3ae78582ab` |
| Brain `embedding_cache.db` | ok | 2 | 58 | `b6724f59423e4c3c61d55cce1e86e2ad08d6cda9b84bb0f82c41efca7b67944b` |

Each source was copied through `sqlite3.Connection.backup()`, opened with
`quick_check`, then restored through the backup API into a separate dry-run DB.
Schema, user version, table counts and canonical `iterdump` digest matched across
source, backup and restored copy.

## Expected absent state

- No V1 `cross_modal_projector.npz` exists; rollback state is explicitly
  `absent/cold-seed-42`, not an assumed file.
- No pending global Brain outbox or feedback receipts exist.
- Registered project State DBs contain zero feedback events.
- Optional timeline, anchors, chat and State-sidecar outbox files absent in the
  three registered project roots were recorded individually in the manifest.

## Rollback point

Rollback restores the complete untouched pre-migration generation from the path
above using bootstrap/same-volume staging. No SQL down-migration is authorized.
T038 may create and test migration code against copies; applying it to live State
or Catalog DBs requires this generation to remain present and hash-valid.
