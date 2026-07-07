# Tasks - Block B Audit Fixes (Production Readiness)

- [X] T101 [OBJ1] except HTTPException: raise in backend/routers/pacing_router.py
- [X] T102 [OBJ1] ffprobe in asyncio.to_thread in backend/routers/pacing_router.py
- [X] T103 [OBJ1] state_conn writes behind db_write_lock in backend/routers/pacing_router.py
- [X] T104 [OBJ1] Windows graceful shutdown CTRL_BREAK in backend/main.py
- [X] T105 [OBJ1] SSE registration in generator in backend/routers/events_router.py

- [X] T201 [OBJ2] Replace bare ffmpeg paths in src/pb_studio/rendering/render_service.py
- [X] T202 [OBJ2] Enforce SAR/audio normalization in src/pb_studio/rendering/render_service.py
- [X] T203 [OBJ2] AMF software fallback SSE event in src/pb_studio/rendering/render_service.py
- [X] T204 [OBJ2] Preview-Renderer speed (get_preview_encoder) in src/pb_studio/rendering/preview_renderer.py

- [X] T301 [OBJ3] App-Exit-Race in PBStudio.UI/App.xaml.cs
- [X] T302 [OBJ3] Windows Job Object in PBStudio.UI/Services/PythonBridgeService.cs
- [X] T303 [OBJ3] BackendReadyMessage in PBStudio.UI/Services/PythonBridgeService.cs
- [X] T304 [OBJ3] Clean dead bindings in PBStudio.UI/Views/VideoLibraryView.xaml
- [X] T305 [OBJ3] CollectionChanged in Controls/WaveformRenderer.cs and DepthRenderer.cs
- [X] T306 [OBJ3] TimelineViewModel to IApiClient in PBStudio.UI/ViewModels/TimelineViewModel.cs
- [X] T307 [OBJ3] Remove 50-reconnect limit in PBStudio.UI/Services/SSEClient.cs

- [X] T401 [OBJ4] Fallback energy curve to original mix in backend/routers/audio_router.py
- [X] T402 [OBJ4] Neutral beat strength for >600s in backend/routers/audio_router.py
- [X] T403 [OBJ4] Song duration structure analysis in backend/routers/audio_router.py
- [X] T404 [OBJ4] librosa.get_duration exception catch in src/pb_studio/audio/beat_detector.py
- [X] T405 [OBJ4] WaveformAnalyzer large file OOM guard in src/pb_studio/audio/waveform_analyzer.py

- [X] T501 [OBJ5] Remove torch.cuda from src/pb_studio/core/recovery_handler.py
- [X] T502 [OBJ5] enable_cpu_mem_arena=False in scripts download and export scripts
- [X] T503 [OBJ5] Fix global exit code in verify_release_smoke.ps1
- [X] T504 [OBJ5] embedding_cache media_hash[:16] collisions in src/pb_studio/storage/embedding_cache.py
- [X] T505 [OBJ5] patterns_conn lock synchronization in src/pb_studio/storage/brain_store.py
