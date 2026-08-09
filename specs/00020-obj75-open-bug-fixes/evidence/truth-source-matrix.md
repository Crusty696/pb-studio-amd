# OBJ-75 Truth-Source-Matrix

**Control root:** `%LOCALAPPDATA%\PB_Studio\recovery-control\v1`

This path is resolved without reading product `config.json`, WPF `settings.json`
or a product database. The Recovery Coordinator owns it and runs first.

| Source | Owner | Class | Consistency group | Quiesce / snapshot | Restore / validation |
|---|---|---|---|---|---|
| `data/pb_studio.db` including projects, media, render queue, `vector_map`, vector outbox | Database/AppState | owned | global-index | drain AppState, render and vector writers; SQLite backup API | integrity/schema; vector-map reconciliation |
| `video_index.faiss`, `_meta.json`, `_tombstones.json` and vector journal | VectorStore | owned | global-index | stop background writer; converge `.txn`/`.bak`; immutable copy | index count/dim, metadata IDs, tombstones and DB map agree |
| project `state.db` | Project lifecycle / Brain feedback | owned | project | hold project epoch; drain feedback writes; SQLite backup | integrity/schema/project UUID |
| `project.json`, `timeline.json`, `anchors.json` | Project router | owned | project | project operation + commit guard; atomic staged copy | schema, IDs and media references agree |
| `chat_history.json` | Chat history store | owned | project | hold history lock for captured project key | JSON schema, bounded entries, same project UUID |
| `weights.db`, `patterns.db`, `embedding_cache.db` | BrainStore | owned | brain | stop Brain operations; SQLite backup | integrity/schema and cache-file closure |
| global `feedback_outbox.json`, `feedback_receipts.json` and discovered `<state.db>.brain-feedback-outbox.json` | FeedbackLogger | owned | brain+project | hold `_OUTBOX_LOCK`; recover or snapshot one complete stage | idempotent replay/compensation; receipt fingerprint |
| `embeddings/*.npy` and projector NPZ | EmbeddingCache / Projector | owned | brain | private immutable generation; flush/fsync/hash | dimensions/model identity/hash; DB paths resolve relatively |
| repository `config.json` | ConfigManager | owned | global-config | ConfigManager lock; staged copy | schema/default merge; must not locate control root |
| `%APPDATA%\PBStudio\settings.json` | WPF SettingsService | owned | global-config | settings service serialization gate | JSON contract; fallback defaults remain available |
| stem complete/partial markers and app-owned stem files | Audio router / Separator | owned | project-media | stop stem task; accept only validated published artifacts | marker identity, source/model hash, audio validation |
| original imported media outside project ownership | Media repository | external-reference | project-media | never mutate; record canonical path, size, mtime and content hash | verify identity; mark unavailable on mismatch, never fake success |
| user-selected render outputs | Render service | external-reference | render | do not overwrite during restore; record output hash/status | validate existing committed output or mark job retryable |
| thumbnails, waveform caches, temp transcodes and progress logs | respective cache/render owner | derived | none | no backup required after writer stop | invalidate/rebuild; never become authoritative |

## Mandatory invariants

1. A stdlib-only bootstrap runs before backend Config/Log imports. Product data
   is not opened before it resolves the journal and validates the generation.
2. `pb_studio.db` and FAISS publish as one logical generation.
3. Brain DBs, embedding files, projector, outbox and receipts publish as one
   logical generation.
4. Project JSON, `state.db` and chat history publish under the same project UUID.
5. External references are never silently converted into owned backups or
   restored as valid when their hash is missing or different.
6. Every source added later requires a matrix row and fault-injection case.
7. WPF Settings are only part of a generation when the WPF writer is closed or
   explicitly locked; otherwise the manifest records a separate settings scope.
