# Full-Stack Audit Report — PB Studio (AMD Edition) — 2026-05-19

> Dr.-Level systematic audit nach `full-stack-system-audit` SKILL 7-Phasen-Discipline.
> Read-only audit. Keine Source-Modifikationen.
> Auditor: Claude Opus 4.7 (1M context). HEAD = `aacad04` (clean working tree).

---

## 1. Scope (Phase 0 — Plan-Lock)

```
PROJECT ROOT:  C:\Users\david\Documents\Pb_studio_AMD_version
HEAD:          aacad04 ("fix(ui): 4 WPF Compiler-Warnings auf 0 (B5)")
WORKING TREE:  clean (git status --porcelain = 0 lines)

LAYERS IN SCOPE:
  - Backend Python (FastAPI, 9 Router, 10 Schema-Modules, ~14 Service-Module)
  - C# WPF Frontend (PBStudio.UI: 16 ViewModels, 16 Views, 11 Services, 17 Models)
  - SQLite (DatabaseCore, 2 Migrationen, MediaRepository, ProjectRepository)
  - FAISS Vector Store (1152-d SigLIP SO400M), sqlite-vec (Brain-Modul)
  - IPC: REST (port 8765) + SSE event-stream
  - External: Ollama / LM-Studio Hybrid (OpenAI-compat)

DOMAINS (all 6 mandated):
  1. Wiring          — caller<>callee parity, router-registration, signal/observer
  2. Pipelines       — multi-step type/shape conformance, error/cancel paths
  3. Data-Flow       — field write↔read parity across layers
  4. Persistence     — transactional integrity, FK, migrations, recovery
  5. Intermediate-Storage — caches, singletons, temp-files, thread-safety
  6. Schemas         — DB ↔ Pydantic ↔ C# DTO parity, defaults, nullability

OUT OF SCOPE:
  - Performance profiling (no benchmark runs)
  - Security pentest (local-only desktop app per CLAUDE.md §main.py L8)
  - UX/visual design
  - LiveAudio of running app (no Windows GUI session reachable from this audit env)
  - GPU-runtime verification (no DirectML access from Bash env)

PRIOR AUDITS USED AS BASELINE (not as substitute):
  - AUDIT_MASTER_2026-05-11.md (consolidates 7 domain audits, ~130 findings)
  - AUDIT_TIMELINE_INTEGRITY_2026-05-11.md, AUDIT_AUDIO_PIPELINE_2026-05-11.md,
    AUDIT_VIDEO_PIPELINE_2026-05-11.md, AUDIT_STATE_DB_CACHE_2026-05-11.md,
    AUDIT_FRONTEND_WIRING_2026-05-11.md, AUDIT_GPU_THREADING_2026-05-11.md,
    AUDIT_RENDERING_PIPELINE_2026-05-11.md

KNOWN OPEN ISSUES INPUT (from C:\Users\david\Brain\10_Projects\PB_studio\open-tasks\
                          2026-05-19-post-timeline-merge.md):
  - #1 Live-Verify Timeline-UI (skipped per user directive)
  - #6 VRAM-Stubs (LM-Studio /health/vram) — deferred
  - #7 LM-Studio Phase B — hybrid factory shipped, caller-migration incremental
  - #16 E010 Resilience — substantial done, 4h-stress runtime-test deferred

TIME-AWARENESS: "Audit takes as long as needed." — no domain may be silent-cut.

DELIVERABLE: This file + cited research per CRITICAL/HIGH finding.
```

LOCKED. No scope drift mid-audit. If new domains surface, they go into Phase-8 follow-up, not into Phase 3-7.

---

## 2. Project-Comprehension Summary (Phase 1)

```
PROJECT:        PB Studio AMD Edition
PURPOSE:        Local desktop app (Windows, AMD GPUs only via DirectML) that ingests
                a long audio mix (DJ-set, podcast) + a video library, analyses both
                (BPM, beats, key, structure, motion, scenes, semantic embeddings),
                generates a beat/structure/semantic-matched cut-list ("Director")
                and renders the final cut via FFmpeg AMF hardware encoder.

KEY COMPONENTS:
  Backend:     backend/main.py (FastAPI :8765) + 9 routers + AppState singleton
  Audio:       pb_studio.audio  (analyzer, beat_detector, key_detector, separator,
                                 spectral_analyzer, structure_analyzer,
                                 subtrack_detector, streaming_analyzer, waveform_*)
  Video:       pb_studio.video  (raft MotionAnalyzer, scene_detect, FrameGrabber,
                                 video_embedder, moondream, lmstudio_vision_wrapper,
                                 ollama_vision_wrapper, encoder_utils, visual_curves)
  AI/Brain:    pb_studio.ai     (smart_director, clap_wrapper, siglip_wrapper,
                                 llm_provider, lmstudio_client, ollama_client,
                                 model_registry, video_specialist, chat_agent,
                                 tool_registry)
  Brain-Modul: pb_studio.brain  (brain_service, weight_store, scorer, reranker,
                                 cross_modal_projector, smart_sampler, post_processor,
                                 cold_start, feedback_logger, llm_narrator,
                                 bridge_dimensions, loader_cache, context_resolver)
  Pacing:      pb_studio.pacing (advanced_pacing_engine, clip_selector,
                                 semantic_matcher, anchor_manager, export_handler)
  Rendering:   pb_studio.rendering (render_engine, final_renderer, preview_renderer,
                                    proxy_service, render_queue, render_service)
  Core:        pb_studio.core   (vram_arbiter, vram_budget_manager, model_loader,
                                 task_queue, thread_pool, crash_handler, media_hash,
                                 system_monitor, recovery_handler)
  Data:        pb_studio.data   (database_core, vector_store, media_repository,
                                 project_repository)
  Storage:     pb_studio.storage (sqlite_init, embedding_cache, embedding_repository,
                                  migration_runner, backup, brain_store)
  Frontend:    PBStudio.UI (WPF + CommunityToolkit.Mvvm)
                Services: ApiClient/IApiClient, SSEClient, PythonBridgeService,
                          ProjectService, TimelineStateService, AudioLibraryState*,
                          VideoLibraryState*, SettingsService, DialogService
                ViewModels: 16 (MVVM)
                Views: 16 (XAML)

DATA-LIFECYCLE:
  Import        → User picks files → ApiClient POST /audio/import + /video/import
                → backend.routers.audio_router/video_router register clip in AppState
                → AppState.persist_audio_clip / persist_video_clip → SQLite media
  Analyze       → /audio/analyze, /video/analyze → backend routes asyncio.to_thread
                → pb_studio.audio.analyzer / pb_studio.video.engine analyses on GPU
                → AppState.update_audio_analysis / update_video_analysis →
                  SQLite media.ai_data_json + in-memory analysis_cache
  Embed         → SigLIP video / CLAP audio via DirectML →
                  pb_studio.data.vector_store (FAISS-CPU) + embedding_cache
  Generate Cut  → /pacing/generate → AdvancedPacingEngine + SemanticMatcher +
                  optional BrainService post-processing → CutList in AppState.timeline
  Render        → /render/start → render_service (FFmpeg AMF encoders) → output mp4
                + AppState.render_tasks + SQLite render_jobs (resume on startup)

PERSISTENCE-LAYERS:
  - SQLite (data/pb_studio.db)
      - projects(id, name, created_at, last_modified, json_data)
      - media(id, project_id, file_path, file_hash, duration_sec, status,
              metadata_json [clip_type, clip_id, audio_hash/video_hash,
                              stems_paths, width/height/fps/codec],
              ai_data_json  [bpm, beats_json, key, beat_count, energy_curve,
                             structure_segments, spectral_data, subtrack_segments,
                             tempo_curve, scene_count, avg_motion, has_embedding,
                             scenes, motion, dominant_colors, tags, audio_key,
                             embedding_dim, embedding_samples, is_analyzed])
      - vector_map(faiss_id, media_id, segment_start, segment_end, description)
      - media_import_guard(project_id, normalized_file_path, media_id) [trg]
      - schema_migrations(version, name, applied_at)
  - FAISS index files on disk (per-name index buckets, e.g. "video_index", "main_index")
  - sqlite-vec store (Brain-Modul KNN)
  - logs/  (rotating, 10 MB, gzip, 7-day retention)
  - <project>/ exports/, outputs/, models/, temp/
  - In-memory: AppState singleton (audio_clips, video_clips, analysis caches,
               timeline, render_tasks, cancel_flags)

CURRENT-STATE-MARKERS:
  - Python source files (backend + src/pb_studio):  186
  - C# source files (PBStudio.UI, excl. bin/obj):    74
  - Test files (Tests/test_*.py):                    93
  - Last claimed test result (open-tasks doc):       674 pass / 12 skipped / 0 fail
  - Git commits total:                               247
  - Last 30 commits:  10 fixes (vram, render, stems, ui, encoder), 5 feature
                      (chat, lm-studio, brain restore, llm-provider, timeline),
                      6 docs/chore (gitignore, archive, scripts, handoff, audit)
  - Working tree:    clean
  - DB present:      data/pb_studio.db (present)
```

**Rationalization-Guard:** Comprehension obtained from CLAUDE.md, AUDIT_MASTER_2026-05-11.md, open-tasks doc, backend/main.py, app_state.py, database_core.py, App.xaml.cs, IApiClient.cs, directory listings of all major sub-packages. Sufficient for Phase 2.

---

## 3. Data-Flow Map (Phase 2)

Text-level component map. Each `→` carries a payload spec (`type / shape / sync-mode / failure`).

```
[USER] WPF View
  │  binds via MVVM
  ▼
[WPF VM]  (TimelineViewModel, DirectorViewModel, AudioLibraryViewModel, ...)
  │  uses Ioc.Default → DI
  ▼
[ApiClient : IApiClient]  (PBStudio.UI/Services/ApiClient.cs)
  │  HTTP GET/POST/DELETE → http://127.0.0.1:8765/...
  │  sync-mode: async/await, Polly retries (HttpClient)
  │  failure: timeout 10min, exceptions surfaced to VM
  │
  │  ── SSE channel ──
  ▼     │
[SSEClient] ─→ event-stream consumer → MVVM Messenger → multiple VMs
  │
  ▼
─── HTTP boundary ──────────────────────────────────────────────────
  ▼
[FastAPI app] (backend/main.py)
  │  CORSMiddleware (localhost only, allow GET+POST)
  │  GPULockMiddleware (serialises GPU-bound endpoints)
  │
  ├─→ project_router    → AppState.current_project, ProjectRepository
  ├─→ audio_router      → pb_studio.audio.* (analyzer, beat_detector, separator),
  │                       AppState.audio_clips/analysis_cache,
  │                       AppState.persist_audio_clip / update_audio_analysis
  ├─→ video_router      → pb_studio.video.* (raft, scene_detect, FrameGrabber,
  │                       video_embedder, moondream/llm-vision), AppState.video_*
  ├─→ pacing_router     → pb_studio.pacing.advanced_pacing_engine,
  │                       pb_studio.pacing.semantic_matcher (→ VectorStore),
  │                       pb_studio.ai.smart_director, optional BrainService
  ├─→ render_router     → pb_studio.rendering.render_service,
  │                       pb_studio.rendering.render_queue (SQLite-backed),
  │                       FFmpeg subprocess (h264_amf/hevc_amf/av1_amf)
  ├─→ events_router     → SSE fan-out (publish_event → all queues)
  ├─→ brain_router      → pb_studio.brain.brain_service (suggest, feedback,
  │                       learning_session, stats, reset, explain)
  ├─→ health_router     → SystemMonitor, VRAMArbiter (telemetry)
  ├─→ models_router     → pb_studio.ai.model_registry, ollama_client / lmstudio
  └─→ chat_router       → pb_studio.ai.chat_agent + tool_registry → llm_provider

[AppState singleton]
  │  RLock-protected dicts: audio_clips, video_clips, audio_analysis_cache,
  │                          video_analysis_cache, current_timeline, render_tasks
  │
  ▼
[Persistence Edge]
  ├─→ MediaRepository (CRUD media table)
  ├─→ ProjectRepository (CRUD projects table)
  ├─→ DatabaseCore (SQLite WAL, FK ON, busy_timeout 30s, custom function
  │                 normalize_media_path)
  └─→ VectorStore (FAISS index files per index_name)

[Engine Edge — GPU/CPU]
  ├─→ VRAMBudgetManager (model registration, request/release)
  ├─→ VRAMArbiter / SystemMonitor (LibreHardwareMonitor via pythonnet)
  ├─→ ModelLoader (singleton with eviction)
  └─→ ThreadPool / TaskQueue (asyncio.to_thread workers)

[External LLM]
  ├─→ Ollama (HTTP localhost via ollama_client)
  └─→ LM-Studio (HTTP localhost via lmstudio_client)
        ↑ unified via llm_provider.py factory (OpenAI-compat)
```

**Edges noted as candidates for orphan / write-but-never-read** during Phase 3-5:
- `VectorStore("main_index")` vs `VectorStore("video_index")` split (prior CD-2)
- ModelLoader (prior M-1 — dead in hot-path)
- StreamingAudioAnalyzer (prior M-2 — exists but not wired)
- vector_map table — `INSERT` reachable? `SELECT` reachable? (prior L-STATE-2)
- 6 Pydantic video fields (mood_tags, style_tags, object_tags, brightness_curve,
  saturation_curve, color_temp_curve) — producers exist? (prior L-VIDEO-4)
- `GetOnsetsAsync` referenced in prior L-FE-2 — still missing in IApiClient? (verified above: NOT in IApiClient.cs)
- `CompositionTarget.Rendering` subscription unbalanced? (prior L-FE-15)

---

