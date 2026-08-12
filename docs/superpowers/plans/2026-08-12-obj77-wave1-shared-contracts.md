# OBJ77 Wave 1: Shared Contracts, Persistenz und Recovery

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task by task. Apply `consulting-team`, `pb-master` and the zone skill named in each task. Do not begin a later task before the current task's focused gate is green.

**Goal:** Close A-03..A-06, V-01..V-04, P-08, K-17, D-01..D-07 and Wave gates T087..T089 without changing unrelated behavior, while preserving the original dirty worktree and all legacy persisted fields.

**Architecture:** Add a versioned, additive StageReceipt contract shared by audio and video; persist every requested stage before terminal SSE; recover running receipts atomically on project load; reconstruct partial analysis truth after restart; bind sqlite-vec to the existing project-scoped Brain embedding lifecycle while FAISS remains the 1152-D media-search index; enforce one immutable project identity and one SQLite timeout; flush timeline writes before lifecycle transitions; and source every backend endpoint from one checked-in `appsettings.json`. Legacy status/error fields remain readable and writable throughout this remediation.

**Tech Stack:** Python 3.11.x, NumPy 1.26.4, FastAPI/Pydantic, SQLite/sqlite-vec 0.1.9, FAISS-CPU 1.7.4, WPF/net9.0-windows on .NET SDK 9.0.316, System.Text.Json, pytest, the existing C# test project, OpenAPI/NSwag.

---

## Binding scope and non-goals

- Finding mapping: T003-T006, T024-T027, T042, T063, T066-T072, T087-T089.
- Work only in `C:\Users\david\Documents\Pb_studio_AMD_version-remediation` on `codex/obj77-wave1-shared-contracts` until the Wave-1 merge gate.
- Never modify `C:\Users\david\Documents\Pb_studio_AMD_version`.
- Do not change `PBStudio.UI/Services/IApiClient.cs`; the existing methods are sufficient for this wave. If implementation proves otherwise, stop immediately for the required explicit approval.
- Do not add a NuGet or Python dependency. `sqlite-vec==0.1.9` and its hash pin already exist; WPF configuration uses the BCL `System.Text.Json`.
- Do not delete or rename files.
- Do not write migration code before the explicit Task-12 approval, and do not run it against the user's real project data before the separate real-target approval in Task 12. All authorized pre-real migration tests operate on temporary copies only.
- Do not change FAISS into the Brain store or sqlite-vec into the media-search store.
- Do not implement Audio Wave-2, Video Wave-3, Pacing Wave-4, KI Wave-5 or Release Wave-6 features here.
- Keep DirectML-only rules, locked runtimes and locked separator files unchanged.

## Canonical contracts

### StageReceipt V1

Each receipt is persisted under `stage_receipts[stage_id]` and contains exactly these additive top-level fields:

```text
receipt_version, stage_id, requested, status,
input_fingerprint, config_fingerprint,
artifact_ref, artifact_sha256, artifact_valid,
started_at_utc, finished_at_utc,
error_code, error_message,
provider, model_id, attempts, correlation_id
```

- `receipt_version=1` is written by new code; legacy rows are projected in memory as `receipt_version=0`.
- Nullable fields remain nullable during OBJ77. Existing `analysis_status`, `stage_status`, `stage_errors`, `is_analyzed` and domain payloads are not removed.
- `attempts` is a typed list of provider/model-selection attempts matching the existing `ModelSelectionReceipt.to_dict()` fields. Non-model stages use an empty list.
- Timestamps are UTC RFC3339 with `Z`; `finished_at_utc` is null only while status is running.
- `input_fingerprint` is SHA-256 over canonical JSON containing stable `project_uuid`, captured catalog project ID, project epoch, clip ID, media SHA-256 and stage input identity.
- `config_fingerprint` is SHA-256 over canonical JSON containing the stage request flags and effective config/model-asset identity.
- `artifact_ref` identifies the persisted domain payload within `ai_data_json`; `artifact_sha256` hashes that canonical payload. A completed receipt is valid only when the referenced payload exists and its hash matches.
- A single UUID correlation ID is created per analyze request and appears in all its receipts and terminal SSE data.

### Status and retry truth

Only receipts with `requested=true` influence aggregate status:

- all requested stages completed with valid artifacts -> `completed`
- at least one valid completed stage plus failed/interrupted/unavailable -> `partial`
- no requested stage completed and at least one failed/interrupted/unavailable -> `failed`
- a requested unavailable stage must contain `error_code` and `error_message`
- unrequested/skipped stages do not influence aggregate status
- retry selects only missing, failed, interrupted, or newly requested unavailable stages
- legacy rows infer `requested=false` only from explicit `skipped`; all other existing stage statuses are requested

### Store ownership

- FAISS remains the productive 1152-D media-search index.
- `<project>/embeddings.db` is the project-scoped sqlite-vec Brain KNN store.
- Every FAISS/sqlite-vec row is bound to captured stable `project_uuid`, catalog project ID/epoch, owner, media ID, media hash and recovery generation.
- Raw audio/video dimensions and the projected Brain dimension come from the checked model-asset manifest; no first-vector dimension adoption is allowed. Current video is 1152-D and the existing cross-modal Brain projector emits 256-D vectors.
- Input dtype must already be float32; wrong dtype, wrong dimension, NaN, Inf and zero-norm vectors fail before any write.
- Insert, KNN, delete, backup, restore, corruption and restart are mandatory tests.

---

### Task 1: Freeze Wave-1 baseline and write red contract tests

**Findings:** T087, T089 foundation for all Wave-1 findings.

**Files:**
- Create: `Tests/test_stage_receipt_contract.py`
- Create: `Tests/test_wave1_status_derivation.py`
- Create: `Tests/test_wave1_endpoint_configuration_contract.py`
- Create: `Tests/test_wave1_sqlite_connection_contract.py`
- Create: `specs/00022-complete-requirements-remediation/evidence/wave-1-baseline.json`
- Append: `.superpowers/sdd/2026-08-12-obj77-blocker-remediation/progress.md`

**Steps:**

1. Record clean branch/HEAD, Python, NumPy, ORT, sqlite-vec, FAISS, dotnet and config hashes without changing product code.
2. Add failing tests that assert all 17 StageReceipt fields, V0 projection, requested-only status derivation and retry selection.
3. Add failing static tests that detect endpoint literals outside root `appsettings.json`, `ConfigureAwait(false)` in UI-bound namespaces and non-5000 SQLite connection factories. The endpoint guard covers WPF, backend config, chat loopback, `launch.ps1`, runtime contract and launcher wrappers.
4. Run the red suite and save the exact failures in the baseline receipt.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_stage_receipt_contract.py Tests\test_wave1_status_derivation.py Tests\test_wave1_endpoint_configuration_contract.py Tests\test_wave1_sqlite_connection_contract.py -q
git diff --check
```

Expected: failures only for the deliberately missing Wave-1 contracts; no unrelated import or collection failure.

**Commit:** `test(wave1): define shared contract red gates`

---

### Task 2: Implement the shared StageReceipt engine

**Findings:** A-03/T003, V-01/T024, T087.

**Files:**
- Create: `src/pb_studio/core/stage_receipts.py`
- Create: `backend/schemas/stage_receipt.py`
- Modify: `backend/schemas/audio_schemas.py`
- Modify: `backend/schemas/video_schemas.py`
- Modify: `src/pb_studio/data/schemas/media_json_schema.py`
- Test: `Tests/test_stage_receipt_contract.py`
- Test: `Tests/test_wave1_status_derivation.py`

**Steps:**

1. Implement canonical JSON hashing, UTC timestamps, receipt creation/transitions, typed attempt normalization, artifact validation, V0 projection, aggregate status and retry selection in one pure module.
2. Reject illegal transitions such as completed-without-valid-artifact, unavailable-without-reason, finished-running, or mismatched stage dictionary key.
3. Add Pydantic `StageAttemptReceipt` and `StageReceipt`; add `stage_receipts: dict[str, StageReceipt]` to audio/video clip and analysis responses.
4. Extend JSON readers additively: preserve existing fields; synthesize V0 receipts only in returned data; do not rewrite a legacy row just by reading it.
5. Make the Task-1 receipt/status tests green.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_stage_receipt_contract.py Tests\test_wave1_status_derivation.py Tests\test_media_json_schema.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\core\stage_receipts.py backend\schemas\stage_receipt.py backend\schemas\audio_schemas.py backend\schemas\video_schemas.py src\pb_studio\data\schemas\media_json_schema.py
git diff --check
```

**Commit:** `feat(core): add additive stage receipt contract`

---

### Task 3: Persist Audio receipts and early failures before SSE

**Findings:** A-03/T003, A-05/T005.

**Zone:** Z-AUDIO only; do not edit `backend/app_state.py` in this task.

**Files:**
- Modify: `backend/routers/audio_router.py`
- Modify: `backend/schemas/audio_schemas.py`
- Create: `Tests/test_audio_stage_receipts.py`
- Modify: `Tests/test_audio_analysis_resume.py`

**Steps:**

1. Extend request-local checkpoint state with one correlation ID and one V1 receipt per known audio stage.
2. Before a stage starts, persist `running`; after its payload is committed, persist completed/failed/partial/interrupted plus artifact hash and terminal time.
3. Bind fingerprints to captured project context, clip/media hash and effective per-stage request/config; never read a later active project during the write.
4. Persist missing-file, global worker and cancellation failures to the affected requested stage(s) before terminal error SSE. SSE carries correlation ID, aggregate status, stage status/errors and receipts.
5. Replace ad-hoc aggregate/retry decisions with the shared receipt engine while retaining flat fields for legacy clients.
6. Prove that retry preserves valid completed artifacts and schedules only eligible receipts.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_audio_stage_receipts.py Tests\test_audio_analysis_resume.py Tests\test_audio_long_mix_truth.py -q
.\.venv\Scripts\python.exe -m py_compile backend\routers\audio_router.py backend\schemas\audio_schemas.py
git diff --check
```

**Commit:** `feat(audio): persist stage receipt lifecycle`

---

### Task 4: Persist Video receipts, provider attempts and requested truth

**Findings:** V-01/T024, V-03/T026.

**Zone:** Z-VIDEO only; do not edit `backend/app_state.py` in this task.

**Files:**
- Modify: `src/pb_studio/video/lmstudio_vision_wrapper.py`
- Modify: `backend/routers/video_router.py`
- Modify: `backend/schemas/video_schemas.py`
- Create: `Tests/test_video_stage_receipts.py`
- Modify: `Tests/test_video_analysis_resume.py`
- Modify: `Tests/test_lmstudio_vision_wrapper.py`

**Steps:**

1. Return tags plus the successful `ModelSelectionReceipt` and all bounded attempt receipts from the wrapper; do not collapse the result to model ID.
2. Persist provider, model ID and typed attempts on the caption receipt with the request correlation ID.
3. Generate requested=false/skipped receipts for disabled stages and requested=true receipts for enabled stages.
4. Give every requested unavailable stage a capability/error code and message; derive aggregate status with the shared engine.
5. Persist running and terminal receipt checkpoints before corresponding SSE events; preserve valid completed stages on retry/cancellation.
6. Prove the exact rules: requested unavailable plus one valid stage is partial; all requested unavailable with no valid completion is aggregate failed with per-stage unavailable truth; unrequested stages do not affect status.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_video_stage_receipts.py Tests\test_video_analysis_resume.py Tests\test_lmstudio_vision_wrapper.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\video\lmstudio_vision_wrapper.py backend\routers\video_router.py backend\schemas\video_schemas.py
git diff --check
```

**Commit:** `feat(video): preserve requested stage and provider receipts`

---

### Task 5: Add atomic startup interruption and full partial reload

**Findings:** A-04/T004, V-02/T025, V-04/T027, D-04/T069, D-05/T070.

**Shared-zone owner:** Parent only for `backend/app_state.py`.

**Files:**
- Modify: `src/pb_studio/data/repositories/media_repository.py`
- Modify: `backend/app_state.py`
- Modify: `src/pb_studio/data/schemas/media_json_schema.py`
- Create: `Tests/test_analysis_startup_recovery.py`
- Create: `Tests/test_video_partial_reload.py`
- Modify: `Tests/test_app_state_truth_source.py`

**Steps:**

1. Add one `BEGIN IMMEDIATE` repository operation scoped by explicit project ID that changes every V1 running receipt to interrupted, sets terminal time/error and recomputes legacy status fields in the same transaction.
2. Invoke it before `load_from_db` publishes any RAM state. Do not touch other projects or completed/unrequested receipts.
3. Reconstruct audio and video clips/caches from all nonempty analysis JSON, not only `is_analyzed=true` rows.
4. Restore tags, tag source, aggregate status, stage status/errors/receipts, scenes, motion, embeddings, colors and valid partial artifacts into both clip dictionaries and analysis caches.
5. Validate completed receipt artifact hashes during reload; demote an invalid completed artifact to `failed` with `error_code=artifact_invalid` and atomically persist receipt, `artifact_valid=false` and legacy aggregate/stage truth before RAM publication.
6. Publish the rebuilt dictionaries atomically only after every row validates.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_analysis_startup_recovery.py Tests\test_video_partial_reload.py Tests\test_app_state_truth_source.py Tests\test_media_json_schema.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\data\repositories\media_repository.py backend\app_state.py src\pb_studio\data\schemas\media_json_schema.py
git diff --check
```

**Commit:** `fix(state): recover and reload partial analysis truth`

---

### Task 6: Restore tags in API/WPF and give Pacing a persisted fallback

**Findings:** V-02/T025, V-04/T027.

**Files:**
- Modify: `backend/routers/video_router.py`
- Modify: `backend/routers/pacing_router.py`
- Modify: `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`
- Modify: `Tests/test_video_list_clips_post_analyze.py`
- Create: `Tests/test_pacing_persisted_analysis_fallback.py`
- Modify: `Tests/test_video_partial_reload.py`

**Steps:**

1. Make `/video/clips` use the single rebuilt truth for tags, tag source and receipt/status fields after reload.
2. Update `ApplyAnalysisResult` to apply tags, tag source, aggregate status and legacy stage errors immediately. Typed C# receipts remain a raw transport payload until Task 7 defines their shared records; no receipt property is consumed here.
3. In Pacing, first use the project-bound RAM snapshot; if absent, load the same explicit project/media row from SQLite and validate the required stage receipt/artifact before consuming it.
4. Never synthesize motion/tags/embeddings after a failed fallback; return explicit degradation.
5. Test project isolation, restart parity and corrupted persisted artifact rejection.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_video_list_clips_post_analyze.py Tests\test_video_partial_reload.py Tests\test_pacing_persisted_analysis_fallback.py -q
.\.venv\Scripts\python.exe -m py_compile backend\routers\video_router.py backend\routers\pacing_router.py
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore
git diff --check
```

**Commit:** `fix(video): restore persisted analysis consumers`

---

### Task 7: Show complete Audio stage truth and retry eligibility in WPF

**Findings:** A-06/T006, T087.

**Files:**
- Modify: `PBStudio.UI/Models/AudioClip.cs`
- Modify: `PBStudio.UI/ViewModels/AudioLibraryViewModel.cs`
- Modify: `PBStudio.UI/Views/AudioLibraryView.xaml`
- Modify: `PBStudio.UI/Services/ApiClient.cs`
- Create: `Tests/test_wpf_analysis_receipt_contract.py`

**Steps:**

1. Add typed C# receipt/attempt records and deserialize all additive fields in existing response DTOs; do not change `IApiClient.cs` method signatures.
2. Carry StageStatus, StageErrors and StageReceipts through reload and analyze result mapping.
3. Render every requested stage with status and exact reason; interrupted/unavailable/failed may never show as fully analyzed.
4. Expose one Retry action only when the shared eligibility rule finds at least one stage. The existing analyze request remains the transport; the backend computes the eligible missing set.
5. On terminal SSE, reload the affected clip by existing collection refresh so persisted state, not transient message text, is authoritative.
6. Add XAML parsing/binding tests and native ViewModel tests for completed/partial/failed/interrupted/unavailable.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_wpf_analysis_receipt_contract.py Tests\test_wpf_api_dto_contract.py -q
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release --no-restore
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore
git diff --check
```

**Commit:** `feat(ui): expose audio stage truth and retry`

---

### Task 8: Await timeline writes before every project lifecycle transition

**Findings:** P-08/T042.

**Files:**
- Create: `PBStudio.UI/Services/ITimelineFlushCoordinator.cs`
- Create: `PBStudio.UI/Services/TimelineFlushCoordinator.cs`
- Modify: `PBStudio.UI/ViewModels/TimelineViewModel.cs`
- Modify: `PBStudio.UI/Services/ProjectService.cs`
- Modify: `PBStudio.UI/App.xaml.cs`
- Modify: `PBStudio.UI/MainWindow.xaml.cs`
- Create: `Tests/test_wpf_timeline_flush_contract.py`
- Modify: existing native project/timeline lifecycle tests

**Steps:**

1. Register the active Timeline ViewModel's existing `SyncTimelineAsync` behind one coordinator that serializes flushes and reports failure.
2. Await a successful flush before Save, Close, Open, Create/project switch and shutdown. Do not call `BeginProjectTransition`, cancel tokens, close the project or stop the backend first.
3. If a flush fails or is cancelled, keep the current project open and return an explicit error; never discard confirmed UI edits.
4. Intercept `MainWindow.Closing`; set `e.Cancel=true` while a reentrancy-guarded async flush/save runs. Only after success set the allow-close guard and call `Close()` again; on error keep the window/project open and show the failure. `App.OnExit` performs only the already-authorized backend shutdown after the successful close gate.
5. Test strict call order, failed-flush close cancellation, double-close reentrancy and a real ViewModel dirty-version convergence test.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_wpf_timeline_flush_contract.py Tests\test_wpf_project_command_wiring.py Tests\test_wpf_timeline_reset_lifecycle_contract.py -q
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release --no-restore
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore
git diff --check
```

**Commit:** `fix(timeline): flush writes before lifecycle changes`

---

### Task 9: Centralize backend endpoint configuration and UI await rules

**Findings:** K-17/T063.

**Files:**
- Create: `appsettings.json`
- Create: `PBStudio.UI/Services/BackendEndpointOptions.cs`
- Modify: `PBStudio.UI/PBStudio.UI.csproj`
- Modify: `PBStudio.UI/App.xaml.cs`
- Modify: `PBStudio.UI/Services/PythonBridgeService.cs`
- Modify: `PBStudio.UI/Services/SSEClient.cs`
- Modify: `PBStudio.UI/Services/OwnerCapabilityRequestHandler.cs`
- Modify: `PBStudio.UI/ViewModels/SettingsViewModel.cs`
- Modify: `PBStudio.UI/Views/SettingsView.xaml`
- Modify: `backend/config.py`
- Modify: `src/pb_studio/ai/tool_registry.py`
- Modify: `launch.ps1`
- Modify: `scripts/runtime_contract.ps1`
- Modify: `PBStudio.UI/run.ps1`
- Modify: `verify_release_smoke.ps1`
- Modify: `SSE-RECOVERY-TEST.bat`
- Modify: `setup_pb_studio.ps1`
- Modify: `scripts/owned_runtime_process.ps1`
- Modify: `scripts/diagnostics/verify_video_resume_live.ps1`
- Modify: `LOW-VRAM-STRESS.bat`
- Modify: `scripts/qa/stress_4h.bat`
- Modify: `scripts/qa/check_stress.bat`
- Modify: `scripts/qa/verify_model_manager.bat`
- Modify: `scripts/qa/verify_model_manager_to_file.bat`
- Modify: the six UI-bound `ConfigureAwait(false)` call sites under `PBStudio.UI/ViewModels/`
- Test: `Tests/test_wave1_endpoint_configuration_contract.py`
- Create: `Tests/test_wpf_dispatcher_await_contract.py`

**Steps:**

1. Define one loopback-only backend scheme/host/port in root `appsettings.json`; copy the same file to WPF output.
2. Load and validate it with `System.Text.Json`; reject non-loopback hosts, invalid schemes and invalid ports.
3. Inject the same immutable options into HttpClient, PythonBridge, SSE, owner-origin validation and chat loopback capability validation; show the same value in Settings.
4. Make backend configuration and every listed active launcher/diagnostic wrapper read the same root contract while preserving environment override behavior where already supported. Tests, archived scripts and documentation examples are excluded from the runtime-literal guard.
5. Remove `ConfigureAwait(false)` only from ViewModels/Views/MainWindow UI-bound continuations; keep it in services and explicit non-UI shutdown work.
6. Add a namespace guard and dispatcher-thread test instead of a total hit-count assertion.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_wave1_endpoint_configuration_contract.py Tests\test_wpf_dispatcher_await_contract.py Tests\test_backend_config.py -q
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release --no-restore
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore
git diff --check
```

**Commit:** `fix(ui): centralize backend endpoint and dispatcher awaits`

---

### Task 10: Enforce manifest-bound vector validation

**Findings:** D-02/T067, D-03/T068 foundation.

**Files:**
- Modify: `config/directml-model-assets.json`
- Modify: `src/pb_studio/storage/embedding_repository.py`
- Modify: `src/pb_studio/data/vector_store.py`
- Create: `src/pb_studio/storage/embedding_contract.py`
- Create: `Tests/test_embedding_contract.py`
- Modify: `Tests/test_storage_layer.py`
- Modify: `Tests/test_vector_store.py`

**Steps:**

1. Add explicit current output dimensions to the existing asset manifest: raw audio uses its active CLAP dimension, raw video uses the current SigLIP 1152-D contract, and the existing cross-modal Brain projector uses its 256-D contract.
2. Load dimensions through one fail-closed pure contract helper; do not adapt dimension from the first vector.
3. Require `np.float32` input before normalization and reject wrong dtype, wrong size, empty, NaN, Inf and zero norm before opening a transaction.
4. Apply the new validation immediately to FAISS media writes/queries and to sqlite-vec query/input helpers, but do not activate 1152-/256-D sqlite-vec writers in this task.
5. Detect an existing/created legacy `FLOAT[768]` sqlite-vec schema as `migration_required` and fail closed before any incompatible write. Task 12 supplies the tested schema migration; Task 13 activates productive writers only after the migrated schema validates.
6. Keep FAISS search behavior and index dimension 1152 unchanged.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_embedding_contract.py Tests\test_storage_layer.py Tests\test_vector_store.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\storage\embedding_contract.py src\pb_studio\storage\embedding_repository.py src\pb_studio\data\vector_store.py
git diff --check
```

**Commit:** `fix(storage): enforce manifested embedding contracts`

---

### Task 11: Remove project-1 fallback and standardize SQLite busy timeout

**Findings:** D-06/T071, D-07/T072.

**Shared-zone owner:** Parent only for `backend/app_state.py`.

**Files:**
- Modify: `backend/app_state.py`
- Modify: `backend/routers/render_router.py`
- Modify: `src/pb_studio/storage/sqlite_init.py`
- Modify: `src/pb_studio/data/database_core.py`
- Modify: `src/pb_studio/storage/backup.py`
- Modify: `src/pb_studio/storage/recovery_adapters.py`
- Modify: `src/pb_studio/storage/recovery_generation.py`
- Modify: `backend/routers/brain_router.py`
- Create: `Tests/test_project_operation_identity_contract.py`
- Create: `Tests/test_project_context_barrier.py`
- Modify: `Tests/test_database_core_synchronous.py`
- Test: `Tests/test_wave1_sqlite_connection_contract.py`

**Steps:**

1. Make `resolve_project_db_id` fail closed; remove fallback 1 from operational paths.
2. Extend `ProjectOperationContext` with the existing stable `project_uuid`; require explicit captured UUID, catalog project ID, root and epoch at the beginning of analyze, delete, update, load, render-resume and recovery operations.
3. Revalidate epoch before each mutation and surface stale context as 409/typed failure.
4. Route every SQLite connection factory through the common initializer or set exactly `PRAGMA busy_timeout=5000` immediately after open.
5. Update the old 30000-ms regression expectation and add a parameterized inventory test for every productive connection factory.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_project_operation_identity_contract.py Tests\test_database_core_synchronous.py Tests\test_wave1_sqlite_connection_contract.py Tests\test_project_context_barrier.py -q
.\.venv\Scripts\python.exe -m py_compile backend\app_state.py src\pb_studio\storage\sqlite_init.py src\pb_studio\data\database_core.py src\pb_studio\storage\backup.py src\pb_studio\storage\recovery_adapters.py src\pb_studio\storage\recovery_generation.py backend\routers\brain_router.py
git diff --check
```

**Commit:** `fix(storage): require project identity and uniform timeout`

---

### Task 12: Implement and prove reversible sqlite-vec migration on copies

**Findings:** D-01/T066, D-02/T067, D-03/T068, T088.

**Approval gate:** Stop before the first migration-code edit and request the required explicit schema-migration approval. The request must name the exact migration file, temporary-copy test path, backup strategy and rollback command. A later second confirmation is required before any real project `embeddings.db` is migrated.

**Files:**
- Create: next numbered migration under `src/pb_studio/storage/migrations/embeddings/`
- Create: `scripts/requirements/migrate_obj77_embeddings.py`
- Create: `specs/00022-complete-requirements-remediation/contracts/migration-approval.schema.json`
- Create: `scripts/requirements/validate_obj77_migration_approval.py`
- Create: `Tests/test_obj77_migration_approval.py`
- Create: `src/pb_studio/storage/migration_authorization.py`
- Modify: `src/pb_studio/storage/embedding_repository.py`
- Modify: `src/pb_studio/data/database_core.py` with the next append-only `SCHEMA_MIGRATIONS` entry
- Modify: `src/pb_studio/storage/recovery_adapters.py`
- Modify: `src/pb_studio/storage/recovery_generation.py`
- Create: `Tests/test_embedding_migration_recovery.py`
- Modify: `Tests/test_recovery_owner_adapters.py`
- Modify: `Tests/test_recovery_generation.py`

**Steps:**

1. Before product startup after these migration definitions exist, inventory every real main DB and `embeddings.db` read-only by canonical path, file SHA-256, schema version, row counts and project UUID. A target with pending destructive migration blocks startup until the explicit script succeeds.
2. Define a machine-readable approval receipt bound to exact canonical target path, pre-migration SHA-256, approved target versions, backup path/hash, operator approval timestamp and rollback command. Temporary-fixture approval and real-target approval are distinct receipts.
3. Change both automatic runners fail-closed: `EmbeddingRepository.__init__` and `DatabaseCore._apply_migrations` may initialize a genuinely new/empty DB, but must raise typed `migration_required` before applying OBJ77 destructive migrations to an existing nonempty DB. A generic environment flag cannot bypass this.
4. The explicit migration script validates the approval receipt, rechecks the live source hash, creates and verifies the backup, then invokes the otherwise inaccessible approved migration path. Constructors merely accept the already migrated target afterward; they never consume approval to mutate it.
5. Build a committed legacy-768 fixture during the test, hash it and copy it to a temporary backup location.
6. Implement an idempotent migration that creates the 256-D projected Brain table with `distance_metric=cosine` and moves the active raw-video schema to the manifested 1152-D contract without fabricating 1152 values from 768 vectors: preserve legacy data in a versioned archive table and require regeneration before it enters the active vec table.
7. Add append-only main-DB migration fields that bind every `vector_map` row to catalog project ID, stable `project_uuid`/owner UUID, media hash, recovery generation and write receipt; backfill only values provable from the joined `media`/`projects` rows and mark anything else explicitly legacy/unverified.
8. Add dry-run reporting with schema version, row counts, hashes, required regeneration and no source mutation.
9. Fault-inject between backup, schema creation, unit copy, vec write, relational receipt and CURRENT/recovery commit.
10. Prove rollback restores byte-identical original data; prove successful restart KNN and corruption detection.
11. Add `embeddings.db` to owner-scoped project backup/restore inventory; never delete the backup or legacy archive in OBJ77.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_migration_approval.py Tests\test_embedding_migration_recovery.py Tests\test_recovery_owner_adapters.py Tests\test_recovery_generation.py Tests\test_vector_operation_outbox.py -q
.\.venv\Scripts\python.exe -m py_compile scripts\requirements\validate_obj77_migration_approval.py scripts\requirements\migrate_obj77_embeddings.py src\pb_studio\storage\migration_authorization.py src\pb_studio\storage\embedding_repository.py src\pb_studio\data\database_core.py src\pb_studio\storage\recovery_adapters.py src\pb_studio\storage\recovery_generation.py
git diff --check
```

Expected before real-data approval: all fixture/copy tests green; no user project file changed.

**Commit:** `feat(storage): add reversible embedding migration`

---

### Task 13: Bind sqlite-vec productively to project-scoped Brain KNN

**Findings:** D-01/T066, D-03/T068.

**Files:**
- Modify: `src/pb_studio/brain/brain_service.py`
- Modify: `src/pb_studio/storage/embedding_repository.py`
- Modify: `src/pb_studio/brain/post_processor.py`
- Modify: `src/pb_studio/data/vector_store.py`
- Modify: `src/pb_studio/data/vector_operation_outbox.py`
- Modify: `src/pb_studio/ai/video_specialist.py`
- Modify: `src/pb_studio/pacing/clip_selector.py`
- Modify: `backend/routers/video_router.py`
- Modify: `backend/routers/pacing_router.py`
- Modify: `backend/_brain_singleton.py`
- Create: `Tests/test_brain_embedding_repository_binding.py`
- Create: `Tests/test_brain_knn_product_path.py`
- Modify: `Tests/test_project_brain_binding.py`

**Steps:**

1. Bind an `EmbeddingRepository` to the same immutable project identity/epoch as Brain `state.db`; retire it on project switch only after active leases release.
2. Add one immutable vector-write context containing stable `project_uuid`, catalog project ID/epoch, owner UUID, media ID, media hash, model/asset identity and recovery generation. Require it for every FAISS and sqlite-vec write.
3. Make the public FAISS `add_embedding` path delegate to the media-linked, outbox-protected path and remove first-vector dimension adoption. Update the two dormant direct callers and the productive video writer to supply the same explicit context; a missing or stale context fails before an index mutation.
4. In the existing `annotate_cuts_with_brain` live path, reuse the already projected audio query and projected eligible video candidates from `post_processor.py`; upsert the eligible candidates and query with `k = eligible_candidate_count`. For sqlite-vec cosine distance `d` in `[0,2]`, compute the existing bridge value exactly as `clip(1 - d / 2, 0, 1)`, which equals `(cosine + 1) / 2`. Do not add an endpoint or route this through `/brain/suggest`.
5. Prove semantic-score and final-order parity with the current direct cosine calculation; sqlite-vec changes persistence/indexing, not the user-visible scoring meaning. FAISS remains the only media-search index.
6. Add delete-by-media and delete-by-owner operations that remove unit and vec rows atomically through the recovery outbox.
7. Reject stale project leases before writes; prove project A cannot query/write project B after a switch.
8. Prove productive Pacing `use_brain=true` -> post-processor -> sqlite-vec KNN -> existing semantic axis, then delete and restart parity through the real bound service, not direct repository-only tests.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_brain_embedding_repository_binding.py Tests\test_brain_knn_product_path.py Tests\test_project_brain_binding.py Tests\test_storage_layer.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\brain\brain_service.py src\pb_studio\brain\post_processor.py src\pb_studio\storage\embedding_repository.py src\pb_studio\data\vector_store.py src\pb_studio\data\vector_operation_outbox.py src\pb_studio\ai\video_specialist.py src\pb_studio\pacing\clip_selector.py backend\routers\video_router.py backend\routers\pacing_router.py
git diff --check
```

**Commit:** `feat(brain): bind project sqlite vec knn store`

---

### Task 14: Prove OpenAPI, Pydantic, C# and persistence parity

**Findings:** T087.

**Files:**
- Modify: `PBStudio.UI/openapi.snapshot.json`
- Generate for verification only: `PBStudio.UI/obj/Generated/ApiTypes.g.cs`
- Modify: `PBStudio.UI/Services/ApiClient.cs` adapters as needed without changing `IApiClient.cs`
- Modify: `Tests/test_openapi_snapshot_drift.py`
- Modify: `Tests/test_wpf_api_dto_contract.py`
- Create: `Tests/test_stage_receipt_transport_parity.py`

**Steps:**

1. Refresh OpenAPI only after all Python response schemas are final.
2. Regenerate C# transport types with the existing NSwag target.
3. Add a structural test for names, types, nullability, required flags, dictionaries and attempt collections across Pydantic, OpenAPI, generated C# and hand-written adapters.
4. Roundtrip a V0 legacy row and a V1 audio/video receipt through persistence -> Pydantic -> JSON -> C# fixture -> adapter.
5. Confirm no method signature in `IApiClient.cs` changed.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
powershell -ExecutionPolicy Bypass -File scripts\dev\refresh-openapi-snapshot.ps1
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
.\.venv\Scripts\python.exe -m pytest Tests\test_openapi_snapshot_drift.py Tests\test_wpf_api_dto_contract.py Tests\test_stage_receipt_transport_parity.py -q
git diff --check
```

**Commit:** `test(api): prove stage receipt transport parity`

---

### Task 15: Execute Wave-1 restart, recovery and local AMD gate

**Findings:** T088, T089 and closure evidence for every Wave-1 primary finding.

**Files:**
- Create: `specs/00022-complete-requirements-remediation/evidence/wave-1-gate-receipt.json`
- Update: `specs/00022-complete-requirements-remediation/evidence/findings-ledger.json`
- Update only evidence-backed checkboxes: `specs/00022-complete-requirements-remediation/tasks.md`
- Append: `.superpowers/sdd/2026-08-12-obj77-blocker-remediation/progress.md`
- Append after merge: `C:\Users\david\Brain\10_Projects\PB_studio\log.md`

**Steps:**

1. Before importing/starting the product, repeat the Task-12 read-only real-DB inventory. Stop if any existing target reports `migration_required`; obtain the separate approval and complete backup/migration/restore proof first.
2. Run a full Python compile sweep over every changed Python file and XML/XAML parse over every changed project/UI file.
3. Run all Wave-1 focused tests, then affected domain E2E clusters, then native C# tests and WPF Release build.
4. On the local AMD machine, execute real Audio and Video analysis, hard-kill during a running stage, restart, verify interrupted receipts, retry only missing stages, preserve completed hashes and show the result in WPF.
5. Save a pending timeline edit, then test Save, Close, project switch and Exit/reopen with zero lost edits.
6. Verify sqlite-vec insert/KNN/delete/restart on a temporary project and FAISS media-search parity. Wave 1 can close only if no real legacy target exists, or every discovered target has passed the separately approved Task-12 backup/dry-run/migration/rollback procedure.
7. Run independent spec-compliance and code-quality reviews; resolve every Critical/Important finding and rerun affected tests.
8. Record one ledger row per finding with commit SHA, command, result and evidence path. Mark no unchecked item that lacks current evidence.
9. Merge only the green Wave-1 branch into `codex/complete-requirements-remediation`; record merge SHA and verify the original dirty worktree is byte/status unchanged.

**Verify:**

```powershell
$env:PYTHONPATH = 'src;.'
.\.venv\Scripts\python.exe -m pytest Tests\test_stage_receipt_contract.py Tests\test_audio_stage_receipts.py Tests\test_video_stage_receipts.py Tests\test_analysis_startup_recovery.py Tests\test_video_partial_reload.py Tests\test_pacing_persisted_analysis_fallback.py Tests\test_project_operation_identity_contract.py Tests\test_embedding_contract.py Tests\test_brain_knn_product_path.py Tests\test_embedding_migration_recovery.py Tests\test_stage_receipt_transport_parity.py -q
.\.venv\Scripts\python.exe -m pytest Tests\test_audio_analysis_resume.py Tests\test_video_analysis_resume.py Tests\test_recovery_owner_adapters.py Tests\test_recovery_generation.py Tests\test_vector_operation_outbox.py -q
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
.\.venv\Scripts\python.exe scripts\validate_sdd.py --feature specs\00022-complete-requirements-remediation --phase open
git diff --check
git status --short --branch
```

**Wave-1 gate:**

- A-03..A-06, V-01..V-04, P-08, K-17 and D-01..D-07 each have individual green evidence.
- Legacy receipt read, V1 write, restart/resume, terminal error ordering, tag/status reload and Pacing fallback are green.
- FAISS and sqlite-vec roles remain separate; vector validation and project isolation are green.
- Fixture migration dry-run/rollback/restore and corruption tests are green; every discovered real target is either absent or separately approved, migrated, verified and rollback-proven.
- OpenAPI/Pydantic/C# parity, native tests and WPF Release are green.
- Intel, NVIDIA, LM-Studio maintenance and 14,400-second stress remain deferred final gates and do not block this merge.

**Commit:** zone-separated evidence commits, then merge commit `merge: complete obj77 wave1 shared contracts`.

---

## Consulting decision record

- **Engagement Manager:** Scope is exactly 17 primary findings plus T087-T089; no Wave-2+ feature is pulled forward.
- **Senior Partner:** StageReceipt and immutable project identity are the two shared foundations; all downstream work consumes them instead of adding parallel status stores.
- **Analyst:** WPF UI state must return through the Dispatcher context, SQLite busy timeout is connection-scoped, and sqlite-vec 0.1.9 remains pre-1.0; therefore the plan uses dispatcher guards, a connection inventory test and the existing exact dependency/hash pin.
- **Domain Expert:** Legacy flat fields and FAISS behavior stay intact; new receipts and sqlite-vec Brain binding are additive.
- **Risk Officer:** Highest risks are real-data migration, stale project writes, duplicate status truth and timeline loss. Test copies, epoch barriers, one receipt engine and fail-closed flush ordering control them.
- **Devil's Advocate:** A repository with only unit callers is not productive; Task 13 requires a real Brain consumer test. A receipt written only at the end is not resumable; Tasks 3-5 require DB-first running checkpoints and hard-kill evidence.
- **Synthesizer:** Execute Tasks 1-15 in order; allow code-zone parallelism only after the shared contract task and never overlap `backend/app_state.py`, central API contracts or lifecycle service edits.
