# Tasks: Full-Stack Audit Fixes Phase 2 (2026-06-10)

- [X] T001 [P0] [OBJ4] {TR-008} Fix with_gpu_task VRAM leak and zombie GPU thread in backend/dependencies.py
- [X] T002 [P1] [OBJ4] {TR-009} Implement eviction accounting rollback on callback failure in src/pb_studio/core/vram_budget_manager.py
- [X] T003 [P1] [OBJ4] {TR-010} Add thread lock for LibreHardwareMonitor updates in src/pb_studio/core/system_monitor.py
- [X] T004 [P2] [OBJ4] {TR-011} Rewrite migration runner with single statement transaction atomicity in src/pb_studio/storage/migration_runner.py
- [X] T005 [P2] [OBJ4] {TR-012} Update embedding repository migration atomicity in src/pb_studio/storage/embedding_repository.py
- [X] T006 [P3] [OBJ7] {TR-013} Fix ChatViewModel Take(40) to send latest messages in PBStudio.UI/ViewModels/ChatViewModel.cs
- [X] T007 [P4] [OBJ5] {TR-014} Add JSON string parsing fallback for stems_paths in backend/routers/audio_router.py
- [X] T008 [P0] [OBJ6] {TR-015} Fix POST /pacing/timeline metadata mapping for cut_id and brain_confidence in backend/routers/pacing_router.py
- [X] T009 [P1] [OBJ4] {TR-016} Decouple video analysis: keep CPU/HTTP operations outside the global GPU lock in backend/routers/video_router.py
- [X] T010 [P1] [OBJ5] {TR-017} Add Demucs instrumental synthesis and MDX instrumental fallback in backend/routers/audio_router.py
- [X] T011 [P2] [OBJ7] {TR-018} Wire up pacing_progress and stem_progress SSE events and increase UI HttpClient timeouts in PBStudio.UI
