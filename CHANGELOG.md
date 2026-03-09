# CHANGELOG - PB Studio AMD Edition
# Bug-History archiviert 2026-03-09

---

## Deep-Audit 2026-03-09 (5 CRITICAL + 4 HIGH + 1 Test)
- **BUG-037 (CRITICAL):** `video_renderer.py`: `get_encoder_config().get("ffmpeg_path")` AttributeError → `_get_ffmpeg_path()`.
- **BUG-038 (CRITICAL):** `streaming_analyzer.py`: tempo=0 ZeroDivisionError → guard.
- **BUG-039 (CRITICAL):** `streaming_analyzer.py`: StemSeparator result parsing → filename mapping.
- **BUG-040 (CRITICAL):** `pacing_schemas.py`: TriggerSettingsSchema field mismatch → 10 fields aligned + C#.
- **BUG-041 (CRITICAL):** `engine.py`: parallel render temp_dir collision → UUID temp_dir.
- **BUG-042 (HIGH):** `spectral_analyzer.py`: missing offset param → added.
- **BUG-043 (HIGH):** `audio_router.py`: bands param ignored → band_keys filtering.
- **BUG-044 (HIGH):** `video_renderer.py`: thread-unsafe preview → new instance.
- **BUG-045 (HIGH/SEC):** Path-Traversal `str().startswith()` → `Path.is_relative_to()`.
- **BUG-046:** `test_vector_store.py`: missing `_lock` in `__new__` → `threading.Lock()`.

## Bug-Detective-Run 2026-03-09
- **BUG-028:** SSE Fan-out: `publish_event` broadcastet an ALLE registrierten Queues.
- **BUG-029:** `ai/audio/video/core/__init__.py`: module-level Imports in try/except — CI ohne Windows-.venv.
- **BUG-030:** `generation_service.py`: ThreadPoolManager/Worker/VideoGenerator Imports in try/except.
- **BUG-031:** `audio_router.py`: `logger.info(... {duration:.1f}s ...)` NameError → `probe_info['duration']`.
- **BUG-032:** Tests `test_backend_routers.py`: `_get_audio_duration` → `_probe_audio_info`.
- **BUG-033:** Tests: `fake_run` Signatur: 5. Parameter `video_analysis_cache=None` ergänzt.
- **BUG-034:** Tests: `@patch(Worker)` — Worker=None auf Linux.
- **BUG-035:** Tests: `skipif` für NTFS rmdir auf Linux.
- **BUG-036:** `test_vector_store.py`: `pytest.importorskip("faiss")`.

## Phase G-J (2026-03-05)
- **BUG-025:** render_router nutzt `request.resolution_width/height/bitrate_mbps` statt hardcodierter quality_map.
- **BUG-026:** render_service `target_fps: int` → `float`, `fps={fps:.3f}` (23.976 korrekt).
- **BUG-027:** pacing_router Validierung VOR `asyncio.to_thread()` → HTTP 404/400 statt Exception.
- **SEC-001:** project_router `create_project()` prüft Pfad gegen `config.project_dir`.
- **SEC-002:** render_router `start_render()` prüft `output_path` gegen `config.project_dir`.
- **SEC-003:** main.py `_force_exit()`: `os._exit(0)` → `os.kill(os.getpid(), signal.SIGTERM)`.
- **WPF-001:** `VideoLibraryViewModel` Constructor ruft `_ = LoadClipsAsync()` auf.
- **WPF-002:** `/audio/waveform/{id}?bands=N` Query-Constraint `ge=1, le=8`.
- **CLEANUP-001:** `AudioAnalyzeRequest.waveform: bool` entfernt.
- **render_router:** `from pathlib import Path` ergänzt (SEC-002 via Smoke-Test entdeckt).
- **ProjectService.cs CS1998:** `await Task.CompletedTask` in 3 async Stubs.

## Phase F Konsistenz-Audit (2026-03-05)
- **BUG-015:** `scipy>=1.10.0` in requirements.txt ergänzt.
- **BUG-016:** audio_router nutzt BeatDetector mit librosa-Fallback statt AudioAnalyzer.
- **BUG-017:** `MotionData.peak_frames`: `list[int]` → `list[dict]` (Pydantic-Crash).
- **BUG-018:** render_schemas.py doppeltes fps entfernt → nur `fps: float = 30.0`.
- **BUG-019:** `GET /audio/clips` Endpoint in audio_router.py ergänzt.
- **BUG-020:** C# RenderRequest: `BitrateMbps` + `IncludeAudio` ergänzt.
- **BUG-021:** C# AudioAnalysisResult: `StructureSegments` + `SpectralData` ergänzt.
- **BUG-022:** C# IApiClient + ApiClient: 5 Methoden + 3 Records (WaveformData, SceneInfo, MotionData).
- **BUG-023:** C# TimelineEntry: `SegmentType` ergänzt.
- **BUG-024:** events_router GPU-Stream: `get_gpu_info()` → `get_stats()` + Key-Mapping.

## AMD Migration / Initiale Fixes (2026-03-05)
- **BUG-001:** C# DI: Alle 8 Views via `Ioc.Default.GetRequiredService<T>()`. StartupUri entfernt.
- **BUG-002:** app.ico: 3-size ICO (16/32/48px, DeepPurple #673AB7) erstellt.
- **BUG-003:** requirements.txt: fastapi/uvicorn/pydantic-settings ergänzt.
- **BUG-004:** C# AudioAnalysisResult: `List<float>? EnergyCurve` (war `string? EnergyProfile`).
- **BUG-005:** SSE Log-Queue: `get_event_queue()` statt toter "logs"-Queue.
- **BUG-006:** RenderRequest fps: `fps: int = 30` in Schema + Router.
- **BUG-007:** PythonBridgeService: `PBSTUDIO_PYTHON_EXE` env var + Fallback-Kandidaten.
- **BUG-008+009:** IApiClient: `CleanupGpuAsync()` + `GetAudioClipsAsync()` ergänzt.
- **BUG-010:** DirectorViewModel: `LoadVideoClipsAsync()` + Add/Remove SelectedVideoClip.
- **BUG-011:** project_router: `AppState.current_project` statt Modul-Variable.
- **BUG-012:** DatabaseCore: `shutdown()` setzt `_instance = None`.
- **BUG-013:** gpu/status: `monitor.get_stats()` statt `get_gpu_info()`.
- **BUG-014:** gpu/cleanup: `VRAMArbiter(monitor=SystemMonitor())` + `get_stats()`.
