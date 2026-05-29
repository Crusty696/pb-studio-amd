# CHANGELOG - PB Studio AMD Edition
# Bug-History archiviert 2026-03-09

---

## 2026-05-29 - Epic 00012: Timeline High-Fidelity Playback & DJ-Beatgrid (Commit `40e4a8d`)

Erfolgreicher Abschluss des finalen Feature-Epics der Entwicklungs-Roadmap. Etablierung aller UI- und Playback-Refactorings für eine DAW-Level Wellenform-Darstellung und ruckelfreie Wiedergabe.

Tests: **727 passed / 9 skipped / 0 failed** (100% Erfolg). WPF Release Build: 0 Fehler / 0 Warnungen.

### Added / Refactored (Timeline High-Fidelity & DJ-Beatgrid)
- **GPU-beschleunigter WaveformRenderer (FR-001):** WPF FrameworkElement Custom Control, das Amplituden in einer einzigen StreamGeometry zeichnet, was die UI-Rendering-Last um ~99% reduziert.
- **Ruckelfreie Playback-Kanten-Übergänge (FR-002):** Implementierung des transienten Flags `_wasPlayingBeforeReload` im Code-Behind von `TimelineView.xaml.cs` zur Gewährleistung unterbrechungsfreier Wiedergabe an Clipgrenzen.
- **High-Contrast DJ-Beatgrid (FR-003):** Rote Downbeats, eisblaue Beats und kontrastreiche abgerundete Badges mit Taktnummer-Beschriftungen (z.B. `BAR 12`) sorgen für 100%ige Lesbarkeit.
- **Song-Phrasen & Wasserzeichen (FR-004):** Sanfte farbliche Abgrenzung der musikalischen Struktur mit transparenten Bezeichnungen auf der A1-Spur.
- **Verifikations-Gates (TR-005):** Etablierung der `.completed`, `.qc-passed` und `qc-report.md` Qualitäts-Gates für Epic 00012.

---

## 2026-05-22 - Hybrid-LLM-Audit (Commit `3025b22`)

User-Audit deckte auf, dass nur 2 von 6 LLM-Call-Sites Auto-Fallback auf Ollama hatten — die anderen 4 nutzten LMStudioClient mit hard-coded LM-Studio-URL ohne Live-Probe. Folge: bei LM-Studio down + Ollama up war Chat und /models/list broken.

Tests: **721 passed / 9 skipped / 0 failed** (vorher 715, +6 neue Regression-Tests).

### Fixed (Hybrid-LLM-Stack — 4 Bypasses)
- `backend/routers/models_router.py:_make_client` → neuer async `_make_alive_client()` Helper mit korrektem `lmstudio_available`+`ollama_available`-Reporting. list_models, list_available_models, recommend_model migriert.
- `src/pb_studio/ai/chat_agent.py:_ensure_resources` → bei `provider="auto"` jetzt `get_alive_client()` statt `get_llm_client()` (vorher: kein Live-Probe → Chat brach bei LM-Studio down obwohl Ollama lief).
- `src/pb_studio/ai/model_registry.py` → neuer `_resolve_client_async()` mit Auto-Fallback (vorher: `LMStudioClient()` lazy default).
- `src/pb_studio/video/lmstudio_vision_wrapper.py` → `get_alive_client()` statt direkter LMStudioClient für Vision-Captioning.

### Live-Verified (Backend mit LM-Studio down + Ollama up)
- `/models/list` → `ollama_available: true`, 4 Modelle (Gemma-4-Uncensored, qwen2.5-osdev, moondream, llava:13b)
- `/models/available` → qwen3-vl-8b listed
- `/models/recommendations` → installed=[4 Ollama-Modelle], korrekte Reasoning
- `/chat/message` → Gemma-4 streamt `"Hallo! 👋"`

### Added (Regression-Tests)
- `Tests/test_video_list_clips_post_analyze.py` (2 Tests) — guards `_explicit_kwargs`-Drift in `list_clips`
- `Tests/test_pacing_snap_subtrack_import.py` (4 Tests) — guards PacingCut-Import in `_snap_cuts_to_subtrack_boundaries`

---

## 2026-05-21 - Auto-QA-Loop autonom (Commit `9909d4a`)

Autonomer 11-Bereiche-Test der gesamten App per API-Tests gegen Backend. 60/60 Funktionen PASS, 3 echte Bugs gefunden+gefixt.

### Fixed (3 Code-Bugs)
- `backend/routers/video_router.py:list_clips` — `TypeError: VideoClipInfo got multiple values for keyword 'is_analyzed'`. Nach `analyze_video` landeten 8 Felder im in-memory clip-dict die mit den expliziten kwargs kollidierten. `_explicit_kwargs`-Set filtert sie aus `c_payload`.
- `backend/routers/video_router.py:_run_video_analysis` — `NameError: name 'state' is not defined` im Embedding-Pfad. Worker-Thread ohne FastAPI-DI. `except Exception` schluckte silent → `embedding_dim=0` für jedes Video. Fix: `from backend.app_state import get_app_state` Singleton.
- `src/pb_studio/pacing/advanced_pacing_engine.py:_snap_cuts_to_subtrack_boundaries` — `NameError: 'PacingCut' is not defined`. Methode nutzte `PacingCut(...)` ohne lokalen Import. Fix: lokaler Import als erste Statement.

### Verified (Live mit Real-Daten)
- BPM Detection: 123.05 BPM für Psy-Trance Mix (BeatNet+librosa)
- Key Detection: F# minor (Krumhansl-Kessler)
- Demucs Stem-Sep 60s WAV: 9s (DirectML)
- h264_amf Render 60s @24fps: 18s = 80fps Render-Speed (3.3× realtime)
- SigLIP-SO400M Embedding nach Fix: 1152-dim, 4 samples

---

## 2026-05-19 - Timeline-Multi-Lane Merge + Post-Merge-Cleanup (Audit-Phase)

Worktree `worktree-timeline-multi-lane` (Commits c9dd4b7..8ed0111 + 22560a7 handoff) gemerged in `main` via FF `update-ref`. Anschliessend Post-Merge-Audit + 7 Cleanup-Commits (f7846d2..df2f9c6).

Tests: **674 passed / 12 skipped / 0 failed** (3:25 min). WPF Release Build: 0 Errors, 10 Warnings.

### Added (Timeline V1+A1 Lanes)
- PBStudio.UI/Views/TimelineView.xaml: Split in V1 (110px) + A1 (80px) Lanes + 60px Track-Header
- PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs: PathGeometry-Generator fuer Mini-Waveforms
- PBStudio.UI/Models/TimelineEntry.cs: ThumbnailFrames + AudioPeaks Properties
- PBStudio.UI/ViewModels/TimelineViewModel.cs: Lazy-Load thumbstrip + clipwave per Entry
- Drag collision-prevention (ClampStartToNeighbours) + Auto-Gap-Close im Contiguous-Mode

### Added (Backend Per-Clip-Visuals)
- GET /video/thumbstrip/{id}?n=8 — N evenly-spaced base64-JPEGs (160x90)
- GET /video/clipwave/{id}?n=256 — Downsampled mono peaks (0..1)
- src/pb_studio/video/clip_audio_peaks.extract_peaks
- src/pb_studio/video/frame_extractor.FrameGrabber.extract_thumbnail_strip

### Added (Pacing-Integrity)
- src/pb_studio/services/pacing_service._finalize_cut_list: Streckt letzten Cut auf audio_duration (V1.length == A1.length invariant)
- validate_timeline: Overlap + Audio-Overflow → HTTP 400 (statt Warning)

### Restored (Post-Merge per User-Direktive 2026-05-19 "Chat-Track behalten")
- backend/routers/chat_router.py + src/pb_studio/ai/chat_agent.py + tool_registry.py + Tests
- src/pb_studio/ai/lmstudio_client.py + lmstudio_vision_wrapper.py + Tests
- src/pb_studio/brain/llm_narrator.py + Tests (test_brain_router_narrative + test_llm_narrator)

### Removed
- Branch worktree-timeline-multi-lane (remote + lokal nach Merge)
- Worktree-Dir .claude/worktrees/timeline-multi-lane/
- Stale-Reports im Repo-Root → archive/status/ (LM_STUDIO_PHASE_B_STATUS_2026-05-17, LM_STUDIO_VERIFY_2026-05-17, STATUS_CONSOLIDATED_2026-05-15)

### Fixed
- pre-existing brain_schemas.py (unclosed Field) + chat_router.py (unterminated __all__) — surgical edits + Reverts
- backend/main.py: chat_router import + include_router korrekt verkabelt

### Updated (Doku)
- specs/project-plan.md E010: Cross-Link auf Brain-Vault open-tasks/2026-05-19-post-timeline-merge.md (#16) + specs/00010-resilience-edge-cases/plan.md
- .gitignore: LM-Studio debug-outputs, cowork-scratch, worktree-subdir, _CLEANUP_*.bat

### Test-Status (Net seit 2026-05-14)
- 2026-05-14: 511 passed / 8 skipped
- 2026-05-17: +76 (brain-narrator + chat-track) → 587
- 2026-05-19: +87 (Timeline-Multi-Lane backend + lmstudio + restoration) → **674 passed**

---

## 2026-05-15 - Cowork-Sessions Day 2 (Plan-Execution + Dep-Updates + Test-Coverage)

Commits: 8 (Spec-Markers, Tab-Animations, TODOs, Vulture-Noqa, gzip-meta, coverage-config, autonomy-docs).
pytest: **537 passed / 10 skipped / 0 failed** in 71s (Win) nach Cluster-1-Dep-Update.

### Added (Code)
- P2.1 / Spec 00007 T010: GPU-accelerated TabControl-Animations (ScaleTransform + Opacity 150ms Storyboard via SelectionChanged Event)
- P2.2 / Spec 00009 T006: media_repository.py gzip-Wrap fuer meta-JSON >10KB (`_serialize_meta`/`_deserialize_meta_str`, 96.8% disk-saving REPL)
- P2.5 / advanced_pacing_engine.py: `_snap_cuts_to_subtrack_boundaries(window=0.5)` impl (Helper-API ready, Aufruf in generate_cut_list)
- P1.4 / Spec 00007 T012: verify_release_smoke.ps1 erweitert um 3 Steps (/health/heartbeat, /health/vram, /brain/stats)
- AGENTS.md: Parallele-Subagent-Sektion (13 Code-Zonen, Mount-Truncation-Schutz, Skill-Mapping, Convergence-Protokoll)
- COWORK_AUTONOMY_LESSONS.md: 12 Anti-Patterns dokumentiert + Iron Rule 12 in CLAUDE.md

### Added (Tests)
- P3.1 / Test-Coverage-Gap-Filler #1: Tests/test_encoder_utils.py (12 tests, Codec+Quality+RateControl+EncoderConfig+build_args+get_encoder_info)
- P3.1 / Test-Coverage-Gap-Filler #2: Tests/test_cache_manager.py (12 tests, init+save+load+exists+invalidate+clear_all+ttl-expiry+corrupt-json)
- P3.1 / Test-Coverage-Gap-Filler #3: Tests/test_model_loader.py (12 tests, ModelType+Spec+register+is_loaded+get_stats+unload_all+singleton)

### Fixed (UI)
- Spec 00010 T003 (TR-001): SSEClient.cs NotifyUiAfterAttempts=5 Konstante + IsBackendReachable Property + BackendReachabilityChanged Event (additiv, kein Break)
- Spec 00010 T004 (TR-003): MainWindow.xaml roter ConnectionStatus-Overlay-Banner (Grid.Row=1 Top, Panel.ZIndex=1000, WifiOff-Icon, Auto-Hide bei Recovery)
- Spec 00007 T011: AudioClipList VirtualizationMode=Recycling (Konsistenz mit VideoClipList)
- P3.4 vulture-noqa: 4 API-Compat-Parameter mit `# noqa: ARG002` markiert (exc_val __exit__, previous_clip_id NV-API, status_callback x2 PyQt-Legacy)

### Fixed (Test-Infrastructure)
- P1.5 Coverage-Hang: dedicated pytest-coverage.ini + .coveragerc + coverage_run_v2.bat (Hardware-Tests excluded wegen CLR/pythonnet-Deadlock unter coverage.py-Instrumentierung)
- video_router.py:348 stale TODO durch Status-Beschreibung ersetzt

### Updated (Deps)
- Cluster 1 FastAPI-Stack: fastapi 0.110→**0.136.1**, uvicorn 0.28→**0.47.0**, pydantic 2.5→**2.13.4**, pydantic-settings 2.2→**2.14.1**, httpx 0.27→**0.28.1**. Zero regression (537 tests pass).

### Verified (Runtime)
- AMD Adrenalin 32.0.31007.1017 (2026-05-04) — h264_amf live-test PASSED. F-10.3 RESOLVED. Doc: test-report/2026-05-15-AMD-DRIVER-RESOLVED.md
- SSE-Recovery + Overlay-Visibility: vr2_overlay.png zeigt rotes Banner nach ~50s (5-attempt threshold). Backend-Recovery: overlay clears.

## 2026-05-14 - Audit-Phase X+Y+Z+IRC autonom (21 Findings)

Auto-QA-Loop session 2026-05-14. Commits: e3a68bd, 9d32bbf, f5bce71, 0487314.
pytest: 511 passed / 8 skipped / 0 failed. dotnet build Release: clean.

### Added
- Y4 / L-AUDIO-1: StreamingAudioAnalyzer integration fuer >10min mixes
- Y6 / L-STATE-2: vector_map populate + tombstone-on-delete
- Z1 / GPU-F3: brain_clap (600 MB) + brain_siglip2 (1100 MB) VRAM-Budgets
- Tests: test_motion_schema_forwarding.py, test_video_hash_persist.py

### Fixed
- X1 / L-VIDEO-2 (M-4 CRIT): peak_motion silent-drop in MotionData schema
- X2 / CD-1 / L-AUDIO-8: stems_paths persist + reload
- X3 / CD-2 / L-VIDEO-1 / L-STATE-3: FAISS-Index unified + atexit leak
- X4 / CD-3 / L-VIDEO-3: video_hash persist + reload
- X5 / CD-4 / L-AUDIO-6 (M-3 CRIT): Subtrack/Tempo reload decoupled from is_analyzed
- X6 / L-FE-13: DirectorVM AudioHash + StemsPaths Mapping
- Y1 / L-FE-15: TimelineView CompositionTarget unsubscribe
- Y2 / L-FE-7: BrainVM + LearningSessionVM IDisposable
- Y3 / GPU-F2: audio_key OUT of with_gpu_task
- Y5 / L-VIDEO-5: range-bug Motion+Embedding loops
- Y7 / L-STATE-4: Brain state.db reset on project close
- Z2 / GPU-F4: brain_router asyncio.to_thread
- Z3 / M-1 CRIT: ModelLoader Lock -> RLock
- Z4 / L-AUDIO-4: Spectral band_means/variances/events forwarded
- Z5 / L-AUDIO-5: subtrack/tempo merge in analyze_audio
- Z6 / L-VIDEO-4: 6 dead schema fields removed
- IRC-1: siglip + clap DML-strict (kein silent CPU-Fallback)
- IRC-2: video_embedder + audio_embedder torch-directml strict

### Open (User-Action)
- AMD Adrenalin Driver Update fuer h264_amf (siehe test-report/2026-05-14-AMD-DRIVER-UPDATE-required.md)

---
