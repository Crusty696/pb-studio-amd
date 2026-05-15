# CHANGELOG - PB Studio AMD Edition
# Bug-History archiviert 2026-03-09

---

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
