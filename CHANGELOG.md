# CHANGELOG - PB Studio AMD Edition
# Bug-History archiviert 2026-03-09

---

## Grand Audit Bugfixes 2026-03-29 (52 Funde)
### KRITISCH (1)
- **BUG-051:** `VideoLibraryViewModel.cs` – Semaphore Double-Release durch `acquired`-Flag Fix behoben.

### HOCH (9)
- **BUG-052:** `smart_director.py` – CLAP Loading Fix (AttributeError `active_provider` entfernt).
- **BUG-053:** `ProductionViewModel.cs` – ETA-Flicker während Render durch `IsRendering`-Guard unterbunden.
- **BUG-054:** `PythonBridgeService.cs` – Watchdog-Restart während Shutdown durch `_isStopping`-Check verhindert.
- **BUG-066:** `advanced_pacing_engine.py` – Energy-Modulation bei pacing=5 korrigiert (Clamp-Fix).
- **BUG-067:** `advanced_pacing_engine.py` – `audio_duration` Präzision in `generate_cut_list_with_stems`.
- **BUG-083:** `orchestrator.py` – `worker.run()` Aufruf fixiert (Signale werden nun korrekt emittiert).
- **BUG-084:** `video_renderer.py` – Invertierter `isinstance`-Check bei Preview-Filter korrigiert.
- **BUG-085:** `thread_pool.py` – Kwargs-Injektion Guard via `inspect.signature` hinzugefügt.
- **BUG-086:** `concat_worker.py` – Windows-spezifisches Pfad-Escaping für FFmpeg concat implementiert.

### MITTEL (22)
- **BUG-055:** `engine.py` – Absolute Pfade in Concat-Dateien (Fix für Dateiname-only Bug).
- **BUG-056:** `SSEClient.cs` – Thread-Safety für Start/Stop via `_stateLock` implementiert.
- **BUG-057:** `routers/` – Hardcodierte `ffmpeg`/`ffprobe` Aufrufe durch `config.ffmpeg_path` ersetzt.
- **BUG-058:** `dj_mix_analyzer.py` – Windowing-Mapping und ID-Generierung in `app_state.py` korrigiert.
- **BUG-059:** `vram_budget_manager.py` – Lock-Schutz für VRAM-Stats Properties hinzugefügt.
- **BUG-060:** `audio_service.py` – Ungültiges Keyword-Argument im `StemSeparator` entfernt.
- **BUG-061:** `pacing_router.py` – Atomares Update von Timeline und Audio-Pfad im `AppState`.
- **BUG-068:** `config_manager.py` – `deepcopy` für `DEFAULTS` gegen Mutation-Leech.
- **BUG-069:** `render_engine.py` – Single-Quote Escaping für FFmpeg Concat (Standard-Konformität).
- **BUG-070:** `render_service.py` – `Path(None)` TypeError durch Null-Check behoben.
- **BUG-071:** `render_engine.py` – Thread-Safe Zugriff auf `_active_processes`.
- **BUG-072:** `vector_store.py` – In-place Normalisierung mutiert Caller-Array nicht mehr (Copy-Fix).
- **BUG-073:** `video_specialist.py` – Vektor-Normalisierung vor Dot-Product (Score-Klammerung 0-1).
- **BUG-074:** `generation_service.py` – Import-Guards für PyQt6/VideoGenerator hinzugefügt.
- **BUG-087:** `audio_import_worker.py` – Temp-WAV-Cleanup im Fehlerfall/Abbruch.
- **BUG-088:** `streaming_analyzer.py` – Blockweises Hashing mit Progress-Logging für große Dateien.
- **BUG-089:** `waveform_cache.py` – Disk-I/O aus Lock-Bereich extrahiert, Mutation atomarisiert.
- **BUG-090:** `worker_registry.py` – Globaler Lock für Worker-Registrierung und -Abfrage.
- **BUG-091:** `logging_setup.py` – Handler-Duplizierung verhindert und absolute Pfade fixiert.
- **BUG-092:** `audio_embedding_worker.py` – Exakter CLAP-Shape-Match durch Padding/Crop-Fix.
- **BUG-093:** `pacing_worker.py` – O(1) Set-Lookup für Downbeat-Matching (Performance).
- **BUG-094:** `stem_runner.py` – Sicherer `sys.path`-Append statt `insert(0)`.

### NIEDRIG (17)
- **BUG-062 bis BUG-065:** Pydantic-Validierungen verschärft (clip_id, start_sec, output_path).
- **BUG-075:** `MainViewModel.cs` – Try/Catch für `InitializeAsync`.
- **BUG-076:** `moondream.py` – Expliziter Check für `temperature=0` (Greedy Decoding).
- **BUG-077:** `siglip_wrapper.py` – Normalisierungskonstanten auf CLIP-Standard aktualisiert.
- **BUG-078:** `vector_store.py` – `nprobe`-Unterstützung für IVF-Indizes ergänzt.
- **BUG-079:** `crash_handler.py` – Windows Event Log Integration.
- **BUG-080:** `system_monitor.py` – `driver_version` Extraktion via WMI.
- **BUG-081:** `video_specialist.py` – `np.linspace` Guard gegen leere Clips.
- **BUG-082:** `vram_arbiter.py` – Korrektur der Puffer-Berechnung (available_real).
- **BUG-095:** `render_worker.py` – Deterministische Seeds für reproduzierbare Renders.
- **BUG-096:** `anchor_features.py` – Vermeidung von doppeltem Audio-Laden.
- **BUG-097:** `thumbnail_generator.py` – `clip_id=0` Handling fixiert.
- **BUG-098:** `encoder_utils.py` – AMF-Status Cache-Invalidierung implementiert.
- **BUG-099:** `thread_pool.py` – Thread-Safe Singleton Pattern für Manager.

### DEAD CODE (3)
- **CLEANUP:** `RenderConfigModel`, `NavigationRequested` Event und ungenutzte Wrapper-Methoden auskommentiert.

---

## Audit-Bugfixes 2026-03-28
- **FIX KRITISCH-001:** `src/pb_studio/ai/clap_wrapper.py:151` – `enable_cpu_mem_arena = True` → `False` (IRON RULE §2 Verstoß behoben)
- **FIX KRITISCH-002:** `src/pb_studio/audio/separator.py:174` – `_apply_directml_patch()` ergänzt um `enable_cpu_mem_arena = False` (nur `enable_mem_pattern` war gesetzt)
- **FIX WARN-002:** `requirements.txt:37` – `faiss-cpu>=1.7.0` → `faiss-cpu==1.7.4` (locked version laut CLAUDE.md §5)

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
