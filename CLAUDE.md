# CLAUDE.md - PB Studio (AMD Premium Edition)
# SYSTEM PROMPT, RULES & PROJECT BRAIN

Read this file ENTIRELY before executing any tasks. Do not look for other .agent files.

---

## 1. 🚀 BOOT PROTOCOL
1. Read this file completely.
2. Acknowledge the current task.
3. Verify that your proposed solution respects the IRON RULES.
4. Output confirmation: "✅ BOOT OK | Task: [Current Task] | Brain: 2026-03-05"

---

## 2. ⚠️ IRON RULES (NEVER OVERRIDE)
1. **AMD DIRECTML ONLY:** NO CUDA, NO ROCm. Use `onnxruntime-directml`.
2. **DIRECTML PATTERN:** `session_options.enable_mem_pattern = False` (MANDATORY).
3. **PYTHON & NUMPY:** Python 3.11.x | NumPy 1.26.4 (< 2.0 strict — BeatNet).
4. **HARDWARE ENCODING:** NO NVENC. Use `h264_amf`, `hevc_amf`, `av1_amf` via FFmpeg.
5. **GPU MONITORING:** NO `pynvml`. Use `LibreHardwareMonitorLib.dll` via `pythonnet`.
6. **WINDOWS:** `pathlib.Path` oder raw strings. PowerShell für Shell-Befehle.

---

## 3. 🧠 PROJECT BRAIN & CURRENT STATUS
- **Date:** 2026-03-09
- **Phase:** Production / Verified
- **Progress:** AMD Migration 100% + WPF Hybrid + Phase G-J + Deep-Audit 2026-03-09 (10 Bugs gefixt) ✅
- **Current Task:** ABGESCHLOSSEN — Deep-Audit (2026-03-09). 5 CRITICAL + 4 HIGH + 1 Test-Fix. 163 passed, 9 skipped, 0 failures.
- **Next Task:** End-to-End Test (WPF App starten + alle 9 Views testen).
- **⚠️ WINDOWS-ONLY STEPS:**
  - `dotnet build PBStudio.UI\PBStudio.UI.csproj` in PowerShell ausführen
  - Python Backend starten: `python -m uvicorn backend.main:app --port 8765`
  - WPF App starten und alle 9 Views testen
- **Architecture Decisions:**
  - *Vision LLM:* Moondream ONNX (FP16) via DirectML.
  - *Motion Analysis:* RAFT ONNX via DirectML (`raft.py -> MotionAnalyzer`).
  - *Stem Separation:* Demucs Hybrid patched for DirectML.
  - *Vector DB:* FAISS-CPU (1152-dim SigLIP SO400M embeddings).
  - *AppState:* `backend/app_state.py` Singleton + SQLite-Persistenz + `current_project` attr (ADR-001+003).
  - *VRAM Arbiter:* `with_gpu_task(model_id=...)` prueft VRAMBudgetManager (2026-03-04).
  - *Key Detection:* `src/pb_studio/audio/key_detector.py` Krumhansl-Kessler via librosa (2026-03-04).
  - *Audio Glue-Code:* `audio_router._run_audio_analysis` 7 Bugs gefixt, alle 4 Analyzer aktiv (2026-03-04).
  - *Video Glue-Code:* `video_router._run_video_analysis` SceneDetector + MotionAnalyzer + SigLIP Embedding (2026-03-04).
  - *SigLIP Embedding:* Echte Implementierung via VectorStore (Stub ersetzt, 2026-03-04).
  - *render_router:* `_execute_render()` 4+1 Bugs gefixt: output_dir, encoder-Param, callback-Signatur, Quality-Params, fps (2026-03-05).
  - *C# DI-Fix:* Alle 8 Views via `Ioc.Default.GetRequiredService<T>()`. StartupUri entfernt (BUG-001, 2026-03-05).
  - *app.ico:* 3-size ICO (16/32/48px, DeepPurple #673AB7) erstellt (BUG-002, 2026-03-05).
  - *requirements.txt:* fastapi/uvicorn/pydantic-settings hinzugefügt (BUG-003, 2026-03-05).
  - *AudioAnalysisResult C#:* `List<float>? EnergyCurve` (war `string? EnergyProfile`, BUG-004, 2026-03-05).
  - *SSE Log-Queue:* `get_event_queue()` statt toter "logs"-Queue (BUG-005, 2026-03-05).
  - *RenderRequest fps:* `fps: int = 30` Feld in Schema + Router (BUG-006, 2026-03-05).
  - *PythonBridgeService:* `PBSTUDIO_PYTHON_EXE` env var + Fallback-Kandidaten (BUG-007, 2026-03-05).
  - *IApiClient:* `CleanupGpuAsync()` + `GetAudioClipsAsync()` ergänzt (BUG-008+009, 2026-03-05).
  - *DirectorViewModel:* `LoadVideoClipsAsync()` + `AddSelectedVideoClip`/`RemoveSelectedVideoClip` (BUG-010, 2026-03-05).
  - *project_router:* `AppState.current_project` statt Modul-Variable (BUG-011, 2026-03-05).
  - *DatabaseCore:* `shutdown()` setzt `_instance = None` (BUG-012, 2026-03-05).
  - *gpu/status Fix:* `monitor.get_stats()` statt `get_gpu_info()` (BUG-013, 2026-03-05).
  - *gpu/cleanup Fix:* `VRAMArbiter(monitor=SystemMonitor())` + `get_stats()` statt `cleanup()` (BUG-014, 2026-03-05).
  - *Phase F Konsistenz-Audit (2026-03-05):*
  - *scipy missing:* `scipy>=1.10.0` in requirements.txt ergänzt (BUG-015).
  - *AudioAnalyzer → BeatDetector:* audio_router nutzt jetzt BeatDetector mit librosa-Fallback statt AudioAnalyzer ohne Fallback (BUG-016).
  - *MotionData peak_frames:* `list[int]` → `list[dict]` in video_schemas.py (Pydantic-Crash, BUG-017).
  - *render_schemas.py doppeltes fps:* Duplikat `fps: int = 30` entfernt, nur `fps: float = 30.0` (BUG-018).
  - *GET /audio/clips:* Fehlender Endpoint in audio_router.py ergänzt (BUG-019).
  - *C# RenderRequest:* `BitrateMbps` + `IncludeAudio` Felder ergänzt (BUG-020).
  - *C# AudioAnalysisResult:* `StructureSegments` + `SpectralData` Felder ergänzt (BUG-021).
  - *C# IApiClient + ApiClient:* 5 fehlende Methoden + 3 Records (WaveformData, SceneInfo, MotionData) ergänzt (BUG-022).
  - *C# TimelineEntry:* `SegmentType` Feld ergänzt (BUG-023).
  - *events_router GPU-Stream:* `get_gpu_info()` → `get_stats()` + Key-Mapping korrigiert (BUG-024, 2026-03-05).
  - *Phase G-J Fixes (2026-03-05):*
  - *BUG-025:* render_router `_execute_render()` nutzt jetzt `request.resolution_width/height/bitrate_mbps` statt hardcodierter quality_map.
  - *BUG-026:* render_service `target_fps: int` → `float`, vf_filter `fps={fps:.3f}` (23.976 korrekt).
  - *BUG-027:* pacing_router audio_clip_id/video_clip_ids Validierung VOR `asyncio.to_thread()` → HTTP 404/400 statt Exception aus Thread.
  - *SEC-001:* project_router `create_project()` prüft Pfad gegen `config.project_dir` (Path-Traversal-Schutz).
  - *SEC-002:* render_router `start_render()` prüft `output_path` gegen `config.project_dir` (Path-Traversal-Schutz).
  - *SEC-003:* main.py `_force_exit()`: `os._exit(0)` → `os.kill(os.getpid(), signal.SIGTERM)` (Graceful Shutdown, SQLite WAL sicher).
  - *WPF-001:* `VideoLibraryViewModel` Constructor ruft `_ = LoadClipsAsync()` auf (Auto-Load beim Start).
  - *WPF-002:* `/audio/waveform/{id}?bands=N` hat Query-Constraint `ge=1, le=8` (kein 500er bei bands=-1).
  - *CLEANUP-001:* `AudioAnalyzeRequest.waveform: bool` entfernt (war nie gelesen, Waveform nur via GET /audio/waveform/{id}).
  - *CLEANUP-002 SKIP:* False Positive — `min_cut_interval` ist NUR in `PacingConfigSchema`, nicht in `TriggerSettingsSchema`. Kein Duplikat vorhanden.
  - *render_router Path-Import:* `from pathlib import Path` ergänzt (SEC-002 nutzte Path ohne Import — via Smoke-Test entdeckt).
  - *ProjectService.cs CS1998:* `await Task.CompletedTask` in 3 async Stubs ergänzt (0 Warnings bei dotnet build).
  - *Bug-Detective-Run 2026-03-09:*
  - *BUG-028:* SSE Fan-out: `publish_event` broadcastet an ALLE registrierten Queues (events_router "log" + "default" teilen sich keine Events mehr).
  - *BUG-029:* `ai/__init__.py`, `audio/__init__.py`, `video/__init__.py`, `core/__init__.py`: Alle module-level Imports in try/except — CI ohne Windows-.venv (PyQt6, scenedetect, faiss) bricht nicht mehr ab.
  - *BUG-030:* `generation_service.py`: ThreadPoolManager/Worker/VideoGenerator Imports in try/except mit None-Fallback.
  - *BUG-031:* `audio_router.py`: `logger.info(... {duration:.1f}s ...)` → NameError — gefixt auf `probe_info['duration']`.
  - *BUG-032:* Tests `test_backend_routers.py`: `_get_audio_duration` existiert nicht → korrekt auf `_probe_audio_info` umgestellt (2 Tests).
  - *BUG-033:* Tests: `fake_run` Signatur: 5. Parameter `video_analysis_cache=None` ergänzt (pacing_router übergab 5 Args).
  - *BUG-034:* Tests: `TestGenerationServiceRouting`: `@patch(Worker)` ergänzt — Worker=None auf Linux, sonst TypeError.
  - *BUG-035:* Tests: `test_generate_from_timeline_renders_all_clips` + `test_generate_from_timeline_cancel`: skipif für NTFS rmdir auf Linux.
  - *BUG-036:* `test_vector_store.py`: `pytest.importorskip("faiss")` — faiss nur in Windows-.venv.
  - *Deep-Audit 2026-03-09:*
  - *BUG-037 (CRITICAL):* `video_renderer.py`: `get_encoder_config().get("ffmpeg_path")` AttributeError. Fix: `_get_ffmpeg_path()`.
  - *BUG-038 (CRITICAL):* `streaming_analyzer.py`: tempo=0 ZeroDivisionError. Fix: guard.
  - *BUG-039 (CRITICAL):* `streaming_analyzer.py`: StemSeparator result parsing. Fix: filename mapping.
  - *BUG-040 (CRITICAL):* `pacing_schemas.py`: TriggerSettingsSchema field mismatch. Fix: 10 fields aligned + C#.
  - *BUG-041 (CRITICAL):* `engine.py`: parallel render temp_dir collision. Fix: UUID temp_dir.
  - *BUG-042 (HIGH):* `spectral_analyzer.py`: missing offset param. Fix: added.
  - *BUG-043 (HIGH):* `audio_router.py`: bands param ignored. Fix: band_keys filtering.
  - *BUG-044 (HIGH):* `video_renderer.py`: thread-unsafe preview. Fix: new instance.
  - *BUG-045 (HIGH/SEC):* Path-Traversal str().startswith() -> Path.is_relative_to().
  - *BUG-046:* `test_vector_store.py`: missing _lock in __new__. Fix: threading.Lock().
- **Tests:** 163 passed, 9 skipped, 0 failures (2026-03-09, Deep-Audit).
- **Reparaturplan 2026-03-07:** 7 Phasen komplett. 6 Test-Fixes (ffmpeg_path, fake_run sig, clip-ID validation, patch paths, cancel_flag). torchaudio 2.4.1+cpu. madmom skip (librosa fallback).
- **ACHTUNG pytest:** `testpaths = Tests` (Grossbuchstabe! Windows NTFS auf Linux-Mount).

---

## 4. 🏗️ ARCHITECTURE MAP
```
src/pb_studio/
├── audio/      # BeatNet(CPU), Demucs(DirectML), SpectralAnalyzer, StructureAnalyzer,
│               # WaveformAnalyzer, KeyDetector (alle VOLLSTÄNDIG implementiert)
├── video/      # raft.py→MotionAnalyzer, scene_detect.py→SceneDetector, FrameGrabber
├── core/       # VRAM Arbiter, Task Queue, LibreHardwareMonitor
├── data/       # SQLite (SQLAlchemy), FAISS-CPU
└── services/   # Orchestration
backend/
├── routers/    # audio, video, pacing, render, events, project (alle vorhanden)
├── app_state.py # Singleton + SQLite-Persistenz + current_project
└── dependencies.py # with_gpu_task(model_id=...)
PBStudio.UI/
├── Services/   # ApiClient.cs (VOLLSTÄNDIG), IApiClient.cs, SSEClient.cs,
│               # PythonBridgeService.cs (PBSTUDIO_PYTHON_EXE env var)
├── ViewModels/ # 9 VMs (alle implementiert, MVVM Toolkit)
├── Views/      # 9 XAML Views (alle vorhanden, kein StartupUri)
├── Converters/ # NullToVisibility, InverseBool, InverseNullToVisibility
├── Resources/  # app.ico (3-size, 16/32/48px)
└── Models/     # AudioClipModel (Key+BeatCount), VideoClipModel (Thumbnail)
```

## 5. 🛠️ LOCKED VERSIONS
| Tool | Version | Constraint |
|------|---------|-----------|
| Python | 3.11.x | madmom/BeatNet |
| NumPy | 1.26.4 | < 2.0 strict |
| onnxruntime-directml | >=1.16.0 | GPU engine |
| PyTorch (CPU) | 2.4.1+cpu | ML tensors |
| BeatNet | 1.1.1 | Beat detection |
| FFmpeg | 6.x Gyan.dev | AMF encoders |
| FAISS-CPU | 1.7.4 | cp311-win_amd64 |

## 6. 📝 BRAIN UPDATE PROTOCOL
After every major task: update Current/Next Task + Architecture Decisions. Keep < 120 lines.
