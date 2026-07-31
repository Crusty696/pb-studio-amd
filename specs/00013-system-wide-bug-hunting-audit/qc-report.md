# QC Report: System-wide Bug Hunting & AI Optimizations (Epic 00013)

## Authoritative OBJ-72 Gate — 2026-07-31

- **Overall result:** **REOPENED / NOT RELEASE-READY**.
- **Reason:** OBJ-72/T370–T415 supersedes the historical OBJ-71 release gate.
- **Current progress:** 14/46 OBJ-72 tasks PASS. Gate A (T370–T373), central
  project context, Audio/Video/Pacing/Brain isolation, bounded SSE, NSwag
  integration, Timeline lifecycle, atomic creation and CachedTab reapply are
  PASS. T380/T385/T386 implementation is active. Historical OBJ-71 evidence is
  preserved under `history/` and remains valid only for that completed scope.
- **Release rule:** `.completed` and `.qc-passed` remain absent until their
  OBJ-72 implementation and QC digest gates are satisfied.

## Authoritative OBJ-71 End-QC Gate — 2026-07-30

- **Overall result:** **PASSED / RELEASE-READY**.
- **Hardware gate:** PASS. RAFT, SigLIP, Moondream Vision, CLAP and Audio MDX
  produced active DirectML PID/LUID/engine/VRAM receipts on RX 7800 XT index
  `1`, LUID `0x00000000_0x0001185b`; iGPU process load was 0%.
- **Implementation gate:** PASS. Final T360 revalidation covered 348 Python,
  74 JSON and 22 XML/XAML/project files; every changed file was non-empty.
- **Targeted/full regression:** focused model/lock clusters PASS; full suite
  1,090 passed/11 justified skips/0 failed.
- **Release build:** WPF Release 0 warnings, 0 errors.
- **Provider/model E2E:** PASS. Live LM Studio/Ollama inventory, bounded
  failover, provider-bound receipts, persistence and offline/empty states
  were verified.
- **GUI/nullable E2E:** PASS. Release GUI showed the RX 7800 XT and truthful
  provider/model states; real `ApiClient` deserialized `confidence=null`
  with exactly one request and no retry storm.
- **H.264/HEVC:** PASS. Each fresh AMF export contains 190,051 frames,
  `progress=end`, full video/audio decode over 6,335.027 s, 106/106 visual
  segments and no black/freeze intervals.
- **Markers:** `.completed` is valid after the final T360 gate; `.qc-passed`
  is authorized by this 100-percent PASS gate.
- **Publication:** the earlier blocked-state publication passed its own gate;
  the final T363/T368 follow-up is published and Remote-SHA verified in the
  closing T369 receipt.
- **Canonical evidence:** `evidence/T368-final-truth-gate.md`.

### OBJ-71 Requirement Matrix

| Requirement | Status | Canonical evidence |
|---|---|---|
| OR-332 | PASS / CONFIRMED | T340–T341 |
| TR-336 | PASS / CONFIRMED | T342 |
| TR-337 | PASS / CONFIRMED | T343 |
| FR-326–FR-336 | PASS / CONFIRMED | T344–T356 |
| TR-338 | PASS / CONFIRMED | T357, T361–T362 |
| TR-339 | PASS / CONFIRMED | T358 |
| TR-340 | PASS / CONFIRMED | T359 |
| TR-341 | PASS / CONFIRMED | T360 post-fix revalidation |
| TR-342 | PASS / CONFIRMED | T361 |
| TR-343 | PASS / CONFIRMED | T362 |
| TR-344 | PASS / CONFIRMED | T363 |
| TR-345 | PASS / CONFIRMED | T364–T367 |
| OR-333 | PASS / CONFIRMED | T368; `.qc-passed` authorized |
| OR-334 | PASS / CONFIRMED | T369 |
| SC-073 | PASS / CONFIRMED | T363 |
| SC-074 | PASS / CONFIRMED | T364–T365 |
| SC-075 | PASS / CONFIRMED | T368–T369 |

The 2026-07-29 gate below is a historical OBJ-70 result. It is superseded for
current release readiness by the OBJ-71 gate above.

## Historical OBJ-70 End-QC Gate — 2026-07-29

- **Overall result:** **PASSED / RELEASE-READY** for the local product and
  End-QC gate.
- **Publication status:** **PASS / CONFIRMED**. T339 completed the Secret-Scan,
  Remote-Diff/Fast-forward proof, zoned commits, scoped pushes and Remote-SHA
  verification.
- **Final regression:** 1036 passed, 11 justified skips, 0 failed,
  45 warnings in 402.48 s; stderr empty.
- **Release build:** WPF Release 0 warnings, 0 errors.
- **Static/contracts:** XAML 19/19, PowerShell 12/12,
  OpenAPI/DTO regression PASS, `git diff --check` PASS, 33/33 progress
  evidence references present.
- **Security/data/fault:** T329 Security Review and T334 copy-only security,
  restore, migration and atomic-publication gates PASS.
- **H.264/HEVC:** each 190,051 frames, `progress=end`, full video/audio
  decode over 6,335.027 s, 106/106 visual segments and no black/freeze
  intervals after the productive router fix.
- **GUI/models/project switch:** 14/14 areas, live capability recommendation,
  visible partial/failure state and project switch during an active render
  PASS.
- **Markers:** `.completed` passed T331; `.qc-passed` is authorized only by
  this 100-percent PASS gate.
- **Canonical evidence:** `evidence/T338-final-truth-gate.md`,
  `evidence/T338-final-full-suite.stdout.log`,
  `evidence/T338-final-wpf-release-build.log` and
  `evidence/T339-commit-push-verification.md`.

### OBJ-70 Requirement Matrix

| Requirement | Status | Canonical evidence |
|---|---|---|
| OR-325 | PASS / CONFIRMED | T305 |
| OR-326 | PASS / CONFIRMED | T306 |
| OR-327 | PASS / DECIDED | T307 |
| TR-324 | PASS / CONFIRMED | T308 |
| TR-325 | PASS / CONFIRMED | T309 |
| TR-326 | PASS / DECIDED | T310 |
| FR-311 | PASS / CONFIRMED | T311 |
| FR-312 | PASS / CONFIRMED | T312 |
| FR-313 | PASS / CONFIRMED | T313 |
| FR-314 | PASS / CONFIRMED | T314 |
| FR-315 | PASS / CONFIRMED | T315 |
| FR-316 | PASS / CONFIRMED | T316 |
| FR-317 | PASS / CONFIRMED | T317 |
| FR-318 | PASS / CONFIRMED | T318 |
| FR-319 | PASS / CONFIRMED | T319 |
| FR-320 | PASS / CONFIRMED | T320 |
| FR-321 | PASS / CONFIRMED | T321 |
| FR-322 | PASS / CONFIRMED | T322 |
| FR-323 | PASS / CONFIRMED | T323 |
| RR-236 | PASS / CONFIRMED | T324 |
| OR-328 | PASS / DECIDED | T325 |
| FR-324 | PASS / CONFIRMED | T326 |
| FR-325 | PASS / CONFIRMED | T327 |
| TR-327 | PASS / CONFIRMED | T328 |
| TR-328 | PASS / CONFIRMED | T329 |
| OR-329 | PASS / CONFIRMED | T330 |
| TR-329 | PASS / CONFIRMED | T331 |
| TR-330 | PASS / CONFIRMED | T332 |
| TR-331 | PASS / CONFIRMED | T333 and T338 final rerun |
| TR-332 | PASS / CONFIRMED | T334 |
| TR-333 | PASS / CONFIRMED | T335 and T337 postfix |
| TR-334 | PASS / CONFIRMED | T336 and T337 postfix |
| TR-335 | PASS / CONFIRMED | T337 |
| OR-330 | PASS / CONFIRMED | T338 |
| OR-331 | PASS / CONFIRMED | T339 |
| SC-070 | PASS / CONFIRMED | T339 completion ledger |
| SC-071 | PASS / CONFIRMED | T337 postfix codec gates |
| SC-072 | PASS / CONFIRMED | T339 marker/remote receipts |

### Invalidated repair-start gate — 2026-07-29

- **Historical result:** **FAILED / REOPENED / NOT RELEASE-READY**.
- **Reason:** The published reference container reported 6,335.027 s, but
  its H.264 stream ended at 1,962.100 s. Existing full-frame evidence decoded
  58,848 of 58,863 declared frames and stopped at 1,961.600 s.
- **Evidence:** `evidence/T305-evidence-freeze-2026-07-29.md`.
- **Disposition:** Superseded by the authoritative End-QC gate above after
  T308–T337 root-cause repair and complete revalidation.

Sections below are historical snapshots. None supersedes the authoritative
End-QC gate above.

## Invalidated Release Gate — 2026-07-28

- **Historical claim:** **PASSED / RELEASE-READY — INVALIDATED BY T305**.
- **Finding matrix:** 60/60 PASS — 2 Critical, 26 High, 25 Medium, 7 Low.
- **Final regression:** 966 passed, 11 justified skips, 0 failed, 45 warnings in 265.87 s.
- **Coverage:** 62% — 20,191 statements, 7,662 missed.
- **Static/build:** Python compile PASS; XAML 19/19; OpenAPI 59 paths/63 operations; WPF Release 0 warnings/0 errors; `git diff --check` PASS.
- **Security:** destructive Chat confirmation 6/6 tests; approve, reject, timeout, replay, argument tampering, parallel decision and disconnect all PASS.
- **Data:** 294 valid SQLite test/project databases inspected; 0 integrity failures, 0 FK violations. FAISS/SQLite active mapping remained 785/785 with 0 orphans.
- **Hardware/E2E:** 6,335.027 s audio imported and analyzed; 12,646 beats; real MDX stems; six videos analyzed through RAFT/SigLIP/Vision; 4,816 Brain cuts cover full duration; resumed H.264 AMF render completed with AAC at 640×360/30 fps, 1,332,887,476 bytes.
- **Models/GUI:** `moondream:latest` and `ornith:9b` active; Models tab completed loading; 12/12 views rendered, screenshot variance 300–734.
- **Export:** H.264 and HEVC live PASS; AV1 correctly rejected as unavailable before render.

### Evidence keys

| Key | Evidence |
|---|---|
| E0 | Final full suite 966/11/0; compile/XAML/OpenAPI/WPF/static gates |
| E1 | W1 P0/security/project/render micro-gate; C-01 7/7; Chat security 6/6 |
| E2 | W2 audio gate 54 passed/4 skipped; late cache/timeout gate 20/20; real 105.6-min analysis/stems |
| E3 | W3 GPU/Core gate 31/31; live AMD RX 7800 XT health/VRAM/timeout paths |
| E4 | W4 Video gate 69/69; parser 23/23; six live RAFT/SigLIP/Vision analyses |
| E5 | W5 Pacing/Brain gate 89/89; live 4,816-cut full-duration Brain pacing |
| E6 | W6 Chat/Models/Terminal gate 41/41; model/GUI/security live checks |
| E7 | W7 Project/Data gate 74/74; fault injection on copies; SQLite/FAISS integrity |
| E8 | W8 Render gate 35/35 plus shutdown/restart gate 41/41; live H.264/HEVC/AV1 and 105.6-min resume render |
| E9 | W9 WPF gate 6/6; live external-backend lifecycle; 12-view GUI; Release 0/0 |

### Per-finding result

| Finding | Result | Evidence |
|---|---|---|
| C-01 | PASS | E1, E2 |
| C-02 | PASS | E1, E6 |
| H-01 | PASS | E2 |
| H-02 | PASS | E2 |
| H-03 | PASS | E2 |
| H-04 | PASS | E2 |
| H-05 | PASS | E2, E3 |
| H-06 | PASS | E2 |
| H-07 | PASS | E3 |
| H-08 | PASS | E3 |
| H-09 | PASS | E3 |
| H-10 | PASS | E4 |
| H-11 | PASS | E4 |
| H-12 | PASS | E5 |
| H-13 | PASS | E5 |
| H-14 | PASS | E5, E7 |
| H-15 | PASS | E5 |
| H-16 | PASS | E5 |
| H-17 | PASS | E6 |
| H-18 | PASS | E9 |
| H-19 | PASS | E9 |
| H-20 | PASS | E1 |
| H-21 | PASS | E7 |
| H-22 | PASS | E8 |
| H-23 | PASS | E1, E8 |
| H-24 | PASS | E8 |
| H-25 | PASS | E8 |
| H-26 | PASS | E6 |
| M-01 | PASS | E2 |
| M-02 | PASS | E2 |
| M-03 | PASS | E2 |
| M-04 | PASS | E3 |
| M-05 | PASS | E3 |
| M-06 | PASS | E4 |
| M-07 | PASS | E4 |
| M-08 | PASS | E4 |
| M-09 | PASS | E4 |
| M-10 | PASS | E5 |
| M-11 | PASS | E5 |
| M-12 | PASS | E6 |
| M-13 | PASS | E6 |
| M-14 | PASS | E9 |
| M-15 | PASS | E9 |
| M-16 | PASS | E9 |
| M-17 | PASS | E7 |
| M-18 | PASS | E7 |
| M-19 | PASS | E7 |
| M-20 | PASS | E7 |
| M-21 | PASS | E7 |
| M-22 | PASS | E7 |
| M-23 | PASS | E8 |
| M-24 | PASS | E8 |
| M-25 | PASS | E8 |
| L-01 | PASS | E2 |
| L-02 | PASS | E2 |
| L-03 | PASS | E4 |
| L-04 | PASS | E4 |
| L-05 | PASS | E9 |
| L-06 | PASS | E6 |
| L-07 | PASS | E7 |

### End-QC discoveries closed

- Stem cache now requires exact source/model identity, unique roles, atomic success marker and validated size/mtime/frame metadata.
- Vision parser rejects refusals/errors, extracts useful English/German prose and never caches empty results.
- WPF exit respects `PBSTUDIO_BACKEND_MANAGED_EXTERNALLY`; live close left backend and render running.
- Backend shutdown tracks render tasks/FFmpeg, persists `interrupted`, terminates children boundedly and resumes without duplicate target publication.
- Skip audit converted hidden Pacing `audio_analysis=None` exception into a passing regression.

This gate is superseded by the authoritative 2026-07-29 repair gate.

## Current Gate Override — 2026-07-28

- **Overall result:** **PRODUCT REGRESSION PASSED / CONTINUOUS AUDIT OPEN**. Alle derzeit registrierten Tasks sind umgesetzt und verifiziert; Erfolgsmarker bleiben während der fortgesetzten systemweiten Suche entfernt.
- **C-03 DirectML-only contract:** **PASSED**. ONNX-Stems nutzen ausschließlich `DmlExecutionProvider`; ohne DML endet der Pfad vor Model-Load/Inference. Demucs bleibt der dokumentierte PyTorch-CPU-Pfad. Der globale `SessionOptions`-Patch ist instanzübergreifend serialisiert; Zielcluster `37 passed`.
- **M-03 live FAISS repair:** **PASSED**. Der mehrdeutige Orphan 897 wurde ohne erfundenen Medienlink tombstoniert. Live-Stand: 898 Indexeinträge, 898 Metadaten, 113 Tombstones, Dimension 1152.
- **M-05 live JSON migration:** **PASSED**. Nach verifiziertem Backup wurden 1775/1775 Metadata- und 802/802 AI-Dicts mit zentralen Migratoren auf Schema v1 persistiert. SQLite `integrity_check=ok`, 0 FK-Verstöße.
- **M-31 separator patch lifecycle:** **PASSED**. Parallele Separator-Instanzen können den prozessglobalen ORT-Konstruktor nicht mehr verschachtelt überschreiben; Originalidentität wird wiederhergestellt.
- **M-32 atomic project open:** **PASSED**. Der neue Medienkatalog wird isoliert vorgeladen; DB-Fehler liefern HTTP 500 und lassen aktives Projekt, Medien, Analyse-Caches und Brain-Bindung unverändert. Projekt-/DB-Cluster `44 passed`.
- **M-33 BeatNet import hygiene:** **PASSED**. Der temporäre PyAudio-Stub wird nach dem BeatNet-Importversuch aus `sys.modules` entfernt; Audio-Cluster `26 passed, 1 skipped`.
- **M-34 Python 3.11 launcher gate:** **PASSED**. WPF akzeptiert nur per `--version` bestätigtes Python 3.11; Python312 und unversionierte Launcher-Fallbacks sind entfernt. Verträge `7 passed`, Release `0 warnings, 0 errors`.
- **Dead code / SDD gate:** **PASSED**. Freigegebene unreferenzierte Dateien und Worker-Backup entfernt; falsche `.completed`-/`.qc-passed`-Marker fehlen; Audit-Gate `3 passed`.
- **Full suite:** **853 passed, 11 skipped, 0 failed**, 45 Warnungen. Python-Compile und `git diff --check` bestanden.
- **Build:** WPF Release `0 warnings, 0 errors`.

## Previous Gate Override — 2026-07-27

- **Overall result:** **FAILED / NOT RELEASE-READY**. This section supersedes the historical 2026-06-09 pass below.
- **C-01 Pacing cache contract:** **PASSED**. Regression `4 passed`; Pacing cluster `101 passed, 1 skipped`; real release smoke passed through pacing, timeline, save, and render-cancel.
- **C-02 AMF-only render contract:** **PASSED**. Target cluster `71 passed`; AMF/OpenAPI regressions `30 passed`; live encoder probe selected `hevc_amf`; release smoke passed.
- **C-03 DirectML-only contract:** **PARTIAL / BLOCKED**. `ModelLoader`, RAFT factory/export and SmartDirector motion are DirectML-only; target cluster `26 passed`. `audio/separator.py` remains unchanged because the active `audio-expertise` skill requires explicit user approval.
- **H-01 missing-media restore:** **PASSED**. Missing files are skipped without deleting persisted rows, and their clip IDs remain reserved; persistence cluster `46 passed`.
- **H-02 atomic Brain rebind:** **PASSED**. Connection/path swap is transactional and failed create/open leaves prior runtime state intact; Brain/project cluster `137 passed`.
- **H-03 FAISS/SQLite compaction gate:** **PASSED**. Failed `vector_map` remap preserves active index, metadata and tombstones; VectorStore/data cluster `22 passed`.
- **VectorStore fixture:** **PASSED**. Invalid `__new__` test setup now mocks save notification; complete VectorStore suite `6 passed`.
- **Generation cancel contract:** **PASSED**. Job acceptance resets stale state once, while in-flight cancel survives analysis and stops basic/SmartDirector render; integration cluster `24 passed`, adjacent render clusters `36 passed`.
- **H-04 crash-consistent FAISS snapshot:** **PASSED**. Mid-replace failure and startup journal recovery restore the previous three-file generation; snapshot tests `3 passed`, VectorStore/data cluster `25 passed`.
- **H-05 video VRAM ownership:** **PASSED**. Composite video analysis keeps the global lock and `video_analysis_full` telemetry without reserving the outer 2900 MB budget; VRAM/DirectML/video cluster `36 passed`.
- **H-06 long-mix trigger coverage:** **PASSED**. Onset/Kick/Snare/HiHat candidates are aggregated across all streaming chunks and forwarded into the analysis cache; audio/streaming/pacing cluster `28 passed`.
- **H-07 render restart:** **PASSED**. Versioned request/timeline snapshots are reconstructed and queued/interrupted jobs are scheduled during lifespan startup; render/router/AMF cluster `52 passed`.
- **H-08/H-09 WPF project lifecycle:** **PASSED**. Direct switches invalidate state/thumbnail generations and all lifecycle messages are delivered through the WPF dispatcher; contract tests `5 passed`, Release build `0 warnings, 0 errors`.
- **M-01 media delete honesty:** **PASSED**. SQLite/tombstone failures preserve in-memory clips and analysis caches and propagate to the API error path; AppState/router/persistence cluster `55 passed`.
- **M-02 project-bound import:** **PASSED**. Audio/video imports return HTTP 409 without an active project and strict registration/persistence paths cannot fall back to DB project 1; router/persistence cluster `59 passed`.
- **M-03 linked FAISS writes:** **CODE PASSED / LIVE REPAIR OPEN**. Missing media IDs are rejected before index mutation; failed `vector_map` inserts roll back or tombstone the new ID and propagate. Data/router cluster `72 passed`. Existing live orphan 897 was not modified.
- **M-04 Brain stats locking:** **PASSED**. All direct shared-connection reads execute under `BrainStore._weights_lock`; Brain router/recovery/core/binding cluster `45 passed`.
- **M-05 media JSON schema writes:** **CODE PASSED / LIVE MIGRATION OPEN**. WMV/FLV use video migrations and normal metadata/AI writes persist `__schema_version`; repository/schema/storage/persistence cluster `57 passed`. Existing 2,544 live blobs were not modified.
- **M-06 streaming energy timeline:** **PASSED**. Failed load/RMS chunks reserve zero-valued timeline frames, preserving later peak positions; streaming/audio/pacing/router cluster `44 passed`.
- **M-07 RAFT flow reuse:** **PASSED**. Segment analysis performs exactly one DirectML flow calculation per frame pair and derives motion plus scene-change metrics from it; progress/DirectML/VRAM/video cluster `30 passed`.
- **M-08 learning-session playback:** **PASSED**. PlayPause toggles both events and label state, navigation resets playback; WPF contract `1 passed`, Release build `0 warnings, 0 errors`.
- **M-09 SSE progress correlation:** **PASSED**. Video analysis/import and pacing events carry and enforce active clip/task correlation; router/pacing/contract cluster `36 passed`, WPF Release `0 warnings, 0 errors`.
- **M-10 active API DTO completeness:** **PASSED**. Handwritten analysis records now retain current audio trigger/subtrack and video mood/color/embedding fields; contract `1 passed`, WPF Release `0 warnings, 0 errors`.
- **M-11 non-blocking WPF file logging:** **PASSED**. Production no longer captures every UI click; a bounded queue moves file I/O to one background writer and drains on provider disposal. WPF contracts `10 passed`, Release `0 warnings, 0 errors`.
- **M-12 VectorStore writer lifecycle:** **PASSED**. Index-name switches close, drain and persist the previous singleton; close terminates its writer and permits a fresh instance. VectorStore/data/AppState/router cluster `74 passed`.
- **LOW-02 Canvas pacing flow:** **PASSED**. CanvasPath now crosses backend schema, router, OpenAPI and active WPF request; clip IDs are prefixed once. Pacing cluster `98 passed`, Canvas/OpenAPI contracts `7 passed`, WPF Release `0 warnings, 0 errors`.
- **LOW-07 truthful project timeline status:** **PASSED**. ProjectOverview distinguishes no project, missing timeline and generated timeline; generation action is hidden without a project. Contracts `6 passed`, WPF Release `0 warnings, 0 errors`.
- **LOW-08 Terminal history:** **PASSED**. WPF and backend SSE logs share a thread-safe 100k history buffer, replay on ViewModel subscription, and clear centrally. WPF contracts `13 passed`, Release `0 warnings, 0 errors`.
- **LOW-04 shared AI config fallback:** **PASSED**. Brain narrator and LM-Studio vision share one ConfigManager-first/disk-fallback helper while private and Ollama shim aliases remain compatible. AI/provider/registry cluster `94 passed`.
- **M-24/M-25 async gate lifetime:** **PASSED**. ViewModel- und PythonBridge-Gates remain valid until in-flight `finally` releases complete; lifecycle contracts `5 passed`, WPF Release `0 warnings, 0 errors`.
- **M-26/M-27/M-28 SSE concurrency:** **PASSED**. Listener tokens are generation-bound, reconnect throttling is locked, and connection state is aggregated per stream and generation; SSE contracts `3 passed`, WPF Release `0 warnings, 0 errors`.
- **Full suite after M-28:** **842 passed, 11 skipped, 1 failed**. The sole failure is the SDD gate proving that false `.completed`/`.qc-passed` markers still exist; all product and pipeline tests pass. Python compile sweep and `git diff --check` pass.
- **Build:** WPF Release `0 warnings, 0 errors`; current Python compile sweep for backend, source and tests passed.
- **Status-marker:** **INVALID**. `.completed` and `.qc-passed` are currently present despite open tasks and failed QC; they must be removed before this report is trustworthy.

## HISTORICAL SNAPSHOT — INVALIDATED (2026-06-09)

- **Date:** 2026-06-09
- **Branch:** `00013-system-wide-bug-hunting-audit`
- **Result:** **HISTORICAL PASS — INVALIDATED**

### Historical Verification Activities

The statements below record the 2026-06-09 snapshot only. They are not evidence for the current gate and are superseded by the failed override above.

#### 1. Automated Regression Test Suite (Pytest)
- **Command:** `pytest Tests/ -q`
- **Historical result:** 734 passed, 11 skipped, 31 warnings.
- **Stats:** 734 passed, 11 skipped, 31 warnings.
- **Scope:** Unit, integration and OpenAPI snapshot tests that existed on 2026-06-09.

#### 2. Stresstest & Langzeitresilienz (F4)
- **Command:** `.venv\Scripts\python.exe src\tools\execute_4h_stress_test.py`
- **Historical result:** 0 failures in the then-current cycles.
- **Details:** The stress test ran successfully for all cycles, verifying correct import, audio analysis, optical flow (RAFT), embedding extraction (SigLIP), pacing timeline construction, preview rendering, and memory cleanup under continuous loop execution.

#### 3. GPU Inferenz-Sperre & Mutex (F1)
- **Details:** Verified the global synchronous `gpu_inference_lock` in `src/pb_studio/core/gpu_lock.py` which serializes all ONNX/DirectML inference session runs (RAFT, SigLIP, Moondream, AudioSeparator) to guarantee sequential execution on limited GPU profiles (<= 8GB VRAM).

#### 4. Native C++ Crash-Protokollierung (F2)
- **Details:** Configured Python's native `faulthandler` in `backend/main.py`. Any potential native segfault or C++ access violation of the `onnxruntime.dll` will be logged directly into `logs/native_crash.log`.

#### 5. SQLite Lock-Safety & Scope-Entkopplung (F5)
- **Details:** CPU/IO-intensive vector database tombstoning (`VectorStore.mark_tombstoned()`) was successfully moved outside the SQLite transaction block in `backend/routers/video_router.py`, eliminating lock contention and `database is locked` risks.

### Historical Conclusion — Invalidated

The former release-ready conclusion no longer applies. The authoritative current result is **FAILED / NOT RELEASE-READY**.


