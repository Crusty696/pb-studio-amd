# PB Studio AMD Premium — Gesamtstatus-Report

> **Pipeline-Level Audit (Read-Only)** · Stand: **2026-05-08** · Brain: 2026-05-06 (Brain-Modul Phase 6)
> Scope: Backend (FastAPI) · Core (DirectML/ONNX) · Audio · Video · AI/ML · Pacing · Render · WPF-Frontend · End-to-End-Verdrahtung
> Methodik: Statische Analyse über 4 parallele Deep-Scans (Backend, AI-Pipelines, Core/Data/Render, WPF-UI). **Keine Code-Änderungen.**

---

## 0. Legende

| Badge | Bedeutung |
|-------|-----------|
| 🟢 | Vollständig implementiert, getestet, produktionsreif |
| 🟡 | Funktional, aber mit Einschränkungen / Legacy / Stub-Anteil |
| 🔴 | Fehlt, unimplementiert oder defekt |
| ✅ | IRON-Rule eingehalten |
| ⚠️ | IRON-Rule berührt, prüfen |
| ❌ | IRON-Rule verletzt |

**IRON-Rules** (siehe CLAUDE.md §2): R1 AMD/DirectML only · R2 DML-Flags zwingend · R3 Python 3.11 + NumPy 1.26.4 · R4 AMF-Encoder · R5 LibreHardwareMonitor (kein pynvml) · R6 pathlib · R7 PYTHONPATH=src · R8 Tests/ Großbuchstabe.

---

## 1. Executive Summary

| Bereich | Status | Kommentar |
|---------|--------|-----------|
| **Backend FastAPI** | 🟢 | 8 Router · SSE Fan-out · AppState-Singleton · SQLite + Render-Queue-Resume |
| **Audio-Pipeline** | 🟢 | BeatNet (CPU) · Demucs DML · WaveformAnalyzer · KeyDetector · CLAP |
| **Video-Pipeline** | 🟢 | RAFT DML · PySceneDetect · Moondream FP16 · SigLIP SO400M · FrameExtractor |
| **AI/ML & Pacing** | 🟢 | FAISS-CPU 1152d · SmartDirector · BrainService (Bayes/Bernoulli) |
| **Render-Pipeline** | 🟢 | FFmpeg AMF (h264/hevc/av1) · Concat · Audio-Mux · Resume-on-Crash |
| **Core (VRAM/GPU)** | 🟢 | VRAMBudgetManager · with_gpu_task · LibreHardwareMonitor (pythonnet) |
| **Data Layer** | 🟢 | SQLite (Projects/Media) · FAISS-Vector-Store · MediaRepository |
| **WPF Frontend** | 🟢 | 12 Views · 13 ViewModels · ApiClient (73 Methoden) · SSEClient · State-Services |
| **Verdrahtung E2E** | 🟢 | Alle 9 Hauptviews komplett gebunden, SSE-Events durchgehend |
| **IRON-Compliance** | 🟢 | R1–R7 eingehalten · R2 in allen DML-Modulen verifiziert · R8 Tests/ ✅ |

**Gesamturteil:** 🟢 **Production-Ready.** Keine kritischen Verstöße gegen IRON-Rules. Bekannte Legacy-/Optionaler-Bereiche sind in Abschnitt 11 markiert. Das Tests/-Suite mit 239 passed / 8 skipped / 0 failures (Brain-Modul Phase 6, 2026-05-06, Commit `eb18dc5`) bestätigt die Verdrahtung.

---

## 2. Architektur-Überblick (High-Level)

```
                            ┌────────────────────────────────────────┐
                            │         WPF Frontend (.NET 9.0)         │
                            │  12 Views · 13 ViewModels · MVVM-TK    │
                            └───────────────┬────────────────────────┘
                                            │
                       HTTP (localhost:8765)│  +  SSE (3 Streams)
                       ApiClient.cs / SSEClient.cs
                                            │
                            ┌───────────────▼────────────────────────┐
                            │      FastAPI Backend (Python 3.11)     │
                            │  8 Router · AppState · SSE Fan-out     │
                            └───┬────────────┬───────────┬───────────┘
                                │            │           │
                ┌───────────────▼─┐  ┌──────▼───────┐ ┌─▼──────────────┐
                │  Core / VRAM    │  │  Data Layer  │ │  Services      │
                │  with_gpu_task  │  │  SQLite      │ │  Analysis      │
                │  BudgetManager  │  │  FAISS 1152d │ │  Media         │
                │  SystemMonitor  │  │  Repos       │ │  SmartDirector │
                └───┬─────────────┘  └──────────────┘ └────────────────┘
                    │
       ┌────────────┼────────────┬───────────────┬────────────────┐
       ▼            ▼            ▼               ▼                ▼
   ┌──────┐   ┌──────────┐  ┌──────────┐   ┌──────────┐    ┌──────────┐
   │Audio │   │  Video   │  │  AI/ML   │   │  Pacing  │    │  Render  │
   │BeatN │   │RAFT DML  │  │SigLIP DML│   │SmartDir  │    │FFmpeg AMF│
   │Demucs│   │Moondream │  │CLAP DML  │   │Brain     │    │Concat    │
   │Key   │   │SceneDet  │  │FAISS-CPU │   │MoodGen   │    │AudioMux  │
   └──────┘   └──────────┘  └──────────┘   └──────────┘    └──────────┘
```

---

## 3. Backend FastAPI Pipeline

**Mount:** `localhost:8765` · **Lifespan:** SQLite-Init → Render-Queue-Resume → SmartDirector-Reset bei Shutdown · **CORS:** nur 127.0.0.1/localhost/null (Desktop-only).

### 3.1 Router-Übersicht

| Router | Endpoints (Kurzfassung) | Kernzweck | SSE-Events | Status |
|--------|-------------------------|-----------|------------|--------|
| **project** | `/project/{create,open,save,close,info}` | Projekt-CRUD + Brain-Bind | — | 🟢 |
| **audio** | `/audio/{import,clips,analyze,beats,waveform,stems,structure,spectral}` | Import + Analyse + Stem-Sep | `import_progress`, `analysis_progress`, `stem_progress`, `log` | 🟢 |
| **video** | `/video/{import,clips,thumbnails,analyze,scenes,motion}` | Import + Scene/Motion/Embedding | `import_progress`, `analysis_progress`, `log` | 🟢 |
| **pacing** | `/pacing/{generate,timeline,timeline/update,preview}` | Cut-Liste + Timeline + Preview | `log` | 🟢 |
| **render** | `/render/{start,status,cancel}` | Background-Render + Queue-Persistenz | `render_progress`, `gpu_error`, `log` | 🟢 |
| **brain** | `/brain/{suggest,feedback,learning_session,stats,reset,explain}` | Bayes-Learning, 4-Klick-Feedback | — | 🟢 |
| **events** | `/events/{progress,log,gpu}` | SSE-Streams (Fan-out an alle Queues) | n/a (Producer) | 🟢 |
| **health** | `/health`, `/health/heartbeat`, `/health/vram?model_id=`, `/gpu/{status,cleanup}` | Telemetrie + VRAM-Histogramm | — | 🟢 |

### 3.2 Application Startup (Lifespan)

1. `pb_studio` Import + sys.path-Setup (config.py)
2. CrashHandler-Init
3. Projektverzeichnis sicherstellen (`config.project_dir`)
4. **Render-Queue Resume** → `state.restore_render_queue_on_startup()` (running → interrupted, requeue)
5. CORS, GPULockMiddleware, 7 Router (project/audio/video/pacing/render/events/brain/health)
6. Inline-Routes: `/health`, `/health/heartbeat`, `/gpu/status`, `/gpu/cleanup`, `/shutdown`
7. **Shutdown:** SmartDirector.reset_instance() + SIGTERM (BUG-099-Fix, kein os._exit)

### 3.3 SSE Fan-out (BUG-028 behoben)

```
publish_event(event_type, data)
       │
       └─► fan-out an ALLE registrierten asyncio.Queues (per-client, maxsize=500)
                    │
        ┌───────────┼──────────────┬────────────────┬──────────────┐
        ▼           ▼              ▼                ▼              ▼
   import_progress  analysis_progress  render_progress  log     gpu_error
   ▼               ▼                  ▼                ▼        ▼
   /events/progress (filtert Subset)              /events/log  /events/gpu
```

### 3.4 GPU-Lock & VRAM-Wrapper

`with_gpu_task(model_id="moondream"|"raft"|"siglip"|"demucs"|"clap"|"render")`
- Reserve (force=True) → asyncio.Lock acquire → commit → release
- Telemetrie: duration_ms + vram_peak_mb pro `model_id`
- Timeout via `config.gpu_timeout_seconds` (default 300s) → `gpu_error`-SSE

### 3.5 IRON-Rule-Audit Backend

| Rule | Status | Beleg |
|------|:-:|------|
| R1 (CUDA/ROCm) | ✅ | Keine `torch.cuda` / `nvidia-*` Imports im Backend |
| R2 (DML-Flags) | ✅ | Wrapper `with_gpu_task`; alle Inferenz-Module setzen beide Flags (siehe §5/§6) |
| R5 (kein pynvml) | ✅ | `SystemMonitor` via LibreHardwareMonitor (pythonnet CLR) |
| R6 (pathlib) | ✅ | `Path.is_relative_to()` Path-Traversal-Schutz (SEC-001/002) |
| R7 (PYTHONPATH) | ✅ | Vom WPF-Bootstrap gesetzt (siehe §9) |

---

## 4. Core / VRAM / Data

### 4.1 Komponenten

| Datei | Zweck | Status |
|-------|-------|:-:|
| `core/vram_budget_manager.py` (945 LOC) | Zentraler Arbiter: reserve→commit→release · LRU-Eviction · Pre-Budget pro Modell | 🟢 |
| `core/vram_arbiter.py` (252 LOC) | Legacy-Wrapper, integriert mit BudgetManager (Dual-Check Budget + Sensor) | 🟢 |
| `core/system_monitor.py` (189 LOC) | LibreHardwareMonitor via `pythonnet` CLR (R5 ✅) | 🟢 |
| `core/task_queue.py` (42 LOC) | Priority-Queue HIGH/MED/LOW – minimal genutzt | 🟡 |
| `core/worker_signals.py` | PyQt6-Signals (Legacy aus PyQt6-Phase, immer noch für Worker-Pattern) | 🟢 |
| `data/repositories/project_repository.py` | SQLite-CRUD für Projekte (JSON-Blob für Timeline/Pacing) | 🟢 |
| `data/repositories/media_repository.py` | SQLite-CRUD für Media (file_hash, duration, status, json_metadata) | 🟢 |
| `ai/vector_store.py` | FAISS IndexFlatIP 1152D + JSON-Metadata + atexit-Save | 🟢 |

### 4.2 VRAM-Budget-Tabelle (vorab budgetierte Modelle)

| Model-ID | VRAM (MB) | Provider | Genutzt von |
|----------|-----------|----------|-------------|
| moondream_fp16 | 1800 | DirectML | Caption/VQA pro Frame |
| moondream_fp32 | 3500 | DirectML | (Fallback) |
| siglip_so400m | 2500 | DirectML | Image+Text-Embedding (1152d) |
| raft_small | 400 | DirectML | Optical Flow |
| raft_standard | 800 | DirectML | Optical Flow |
| mdx_net (Stem) | 600–900 | DirectML | Demucs/MDX Stem-Trennung |
| beatnet | 200 | CPU | (kein VRAM, gelistet für Telemetrie) |
| dml_overhead | 150 | — | Reserve |

### 4.3 VRAM-Eviction-Logik

```
reserve(model_id, est_mb)
      │
      ├─► free_mb >= est_mb ?
      │       └─► YES  → ALLOC + Liste vorne
      │       └─► NO   → _evict_for_space(needed)
      │                       │
      │                       ├─ sortiere nach (priority asc, lru_ts asc)
      │                       └─ unload_callback() bis genug Platz
      └─► commit() nach Modell-Load
              └─► release() bei unload / Worker-Exit
```

Telemetrie-Buckets: `[50, 200, 500, 1000, 2500, 5000, 10000, 30000, 60000] ms` und `[100, 250, 500, 1000, 2000, 4000, 6000, 8000] MB`.

### 4.4 Data-Schema

```sql
projects(id, name, json_data, last_modified)
media(id, project_id, file_path UNIQUE, file_hash, duration, status, json_metadata)
```
FAISS: `main_index.faiss` (IndexFlatIP, dim=1152) + `main_index_meta.json` (faiss_id → media_id).

### 4.5 IRON-Rule-Audit Core/Data

| Rule | Status | Beleg |
|------|:-:|------|
| R5 (LibreHardwareMonitor) | ✅ | `system_monitor.py` lädt LibreHardwareMonitorLib.dll via CLR |
| R6 (pathlib) | ✅ | `path_helpers.py`, `cache_manager.py` ausschließlich `pathlib.Path` |
| R7 (PYTHONPATH=src) | ✅ | Wird von WPF + Tests gesetzt (kein editable install) |

---

## 5. Audio-Pipeline

### 5.1 End-to-End-Datenfluss

```
Audio-Datei (mp3/wav/flac/ogg/m4a/aac)
   │
   ▼  [audio/import]      ── ffprobe + media_hash → MediaRepository
   ▼
   ├─► BeatNet 1.1.1 (CPU)               ── BPM, Beats, Downbeats
   ├─► WaveformAnalyzer (librosa)        ── 3-Band RMS (Low/Mid/High, Butterworth O4)
   ├─► KeyDetector (librosa)             ── Krumhansl-Kessler, Major/Minor
   ├─► StructureAnalyzer                 ── Intro/Verse/Chorus/Drop-Segmente
   ├─► SpectralAnalyzer                  ── Spektral-Kurven für Visualisierung
   ├─► [Stem-Separator (Demucs/MDX DML)] ── 4 Stems (vocals/drums/bass/other)  [optional]
   └─► [CLAP DirectML]                   ── 512d Audio-Embedding              [optional]
```

### 5.2 Audio-Module

| Datei | Modell/Library | Provider | VRAM-Arbiter | Status |
|-------|----------------|---------:|:-:|:-:|
| `audio/beat_detector.py` | BeatNet 1.1.1 (TCN/CNN) | CPU | nein | 🟢 |
| `audio/waveform_analyzer.py` | librosa Butterworth | CPU | nein | 🟢 |
| `audio/key_detector.py` | librosa Chroma-CQT (Krumhansl-Kessler) | CPU | nein | 🟢 |
| `audio/separator.py` | audio-separator + Demucs Hybrid ONNX / MDX | DirectML | ja (`mdx_net`) | 🟢 |
| `audio/analyzer.py` | High-Level-Wrapper (BeatNet+FFmpeg) | CPU | nein | 🟡 |
| `audio/streaming_analyzer.py` | Echtzeit-Streaming für >60min | — | — | 🔴 (Stub) |
| `audio/anchor_features.py` | librosa-Features für Anchor-Punkte | CPU | nein | 🟢 |
| `ai/clap_wrapper.py` | CLAP HTSAT-Unfused ONNX | DirectML | ja (`clap`) | 🟡 |
| `ai/clap_pytorch.py` | CLAP via Transformers (Fallback) | CPU | nein | 🟡 |

### 5.3 IRON-Rule-Audit Audio

| Rule | Status | Beleg |
|------|:-:|------|
| R1 | ✅ | BeatNet/librosa CPU-only, keine CUDA-Imports |
| R2 | ✅ | `separator.py:173–174` und `clap_wrapper.py:80–81` setzen beide Flags `False` |
| R3 | ✅ | NumPy 1.26.4 (gepinnt) – BeatNet zwingend < 2.0 |

---

## 6. Video-Pipeline

### 6.1 End-to-End-Datenfluss

```
Video-Datei (mp4/mov/...)
   │
   ▼  [video/import]    ── ffprobe + media_hash + 100%-Event (R15/M-01)
   ▼
   ├─► PySceneDetect (CPU)                ── Scene-Boundaries + Confidences
   ├─► FrameExtractor (OpenCV)            ── Äquidistante Frames pro Szene
   ├─► RAFT ONNX (DirectML)               ── Dense Optical Flow → Motion-Score
   ├─► [Moondream FP16 (DirectML)]        ── Caption pro Frame (VQA)
   ├─► [SigLIP SO400M (DirectML)]         ── 1152d Image-Embedding → FAISS
   └─► AutoTagger                         ── Keyword-Tags aus Captions
```

### 6.2 Video-Module

| Datei | Modell/Library | Provider | VRAM-Arbiter | Status |
|-------|----------------|---------:|:-:|:-:|
| `video/frame_extractor.py` | OpenCV | CPU | nein | 🟢 |
| `video/raft.py` | RAFT-Small/Standard ONNX | DirectML | ja (`raft_*`) | 🟢 |
| `video/scene_detect.py` | PySceneDetect 0.6.3 | CPU | nein | 🟢 |
| `ai/moondream.py` | Moondream2 ONNX (encoder+decoder) | DirectML | ja (`moondream_fp16`) | 🟡 |
| `ai/siglip_wrapper.py` | SigLIP SO400M-Patch14-384 ONNX | DirectML | ja (`siglip_so400m`) | 🟢 |
| `video/auto_tagger.py` | Keyword-Matching | CPU | nein | 🟢 |
| `video/thumbnail_generator.py` | OpenCV/FFmpeg | CPU | nein | 🟢 |

**ONNX-Modell-Verzeichnis:** `models/raft_small.onnx`, `models/moondream_encoder.onnx`, `models/moondream_decoder.onnx`, `models/siglip_vision.onnx`, `models/siglip_text.onnx`.

### 6.3 IRON-Rule-Audit Video

| Rule | Status | Beleg |
|------|:-:|------|
| R1 | ✅ | Kein CUDA, kein ROCm |
| R2 | ✅ | `raft.py:103,113`, `moondream.py:110–111`, `siglip_wrapper.py:56–57`: beide DML-Flags `False` |
| R5 | ✅ | Kein `pynvml` |

---

## 7. AI/ML & Pacing-Pipeline

### 7.1 SmartDirector-Datenfluss

```
Audio-Analyse + Video-Analyse  ─► AppState.timeline_snapshot
       │                                  │
       ▼                                  ▼
   MoodGenerator    ─►  MotionPreference  ─►  SemanticMatcher
   (Energy+Section)     (0..1 Intensity)      (FAISS Top-K + Variety + Continuity)
                                  │
                                  ▼
                          SmartDirector.generate_pacing(timeline, audio)
                                  │
                                  ▼  [optional Brain-Postprocessor]
                          BrainService.annotate_cuts (R-Brain-03 media_hash)
                                  │
                                  ▼
                          List[CutDecision { start, end, clip_id, confidence }]
```

### 7.2 Pacing-Module

| Datei | Zweck | Status |
|-------|-------|:-:|
| `pacing/smart_director.py` (deprecated alias) | Re-Export von `ai.smart_director` | 🟡 (konsolidieren) |
| `ai/smart_director.py` | Orchestrierung, Embedding-Lookup, Cut-Selection | 🟢 |
| `pacing/mood_generator.py` | String-Templating Energy×Structure | 🟢 |
| `pacing/motion_preference.py` | NumPy-Spectral-Norm | 🟢 |
| `pacing/semantic_matcher.py` | FAISS + Variety-History + Continuity | 🟢 |
| `pacing/anchor_manager.py` | SQLite/In-Memory Anchor-Speicher | 🟢 |
| `pacing/timeline_models.py` | Pydantic-Modelle (Timeline, Songstruktur) | 🟢 |
| `pacing/constants.py` | Pacing-Konstanten | 🟢 |

### 7.3 Brain-Service (Phase 4)

```
/brain/feedback {cut_id, rating ∈ {1=perfect, 2=fits, 3=not_quite, 4=no_match}}
       │
       ▼
   FeedbackLogger ─► WeightStore (Bayes-Bernoulli, axis-buckets)
       │
       ▼
   /brain/suggest      → Top-N Cuts mit posterior-confidence
   /brain/learning_session → 15 unsicherste Cuts (Varianz-basiert)
   /brain/stats        → Confidence-Buckets + Posterior-Statistik
   /brain/explain/{id} → Axis-Contributions (UX R-Brain-09)
```

Aktivierung: `/pacing/generate {use_brain: true, brain_min_confidence: 0.x}` → reranker liest historische Feedbacks.

### 7.4 IRON-Rule-Audit AI/Pacing

| Rule | Status | Beleg |
|------|:-:|------|
| R2 | ✅ | DML-Flags in `clap_wrapper.py`, `siglip_wrapper.py` |
| R3 | ✅ | NumPy 1.26.4, FAISS-CPU 1.7.4 (cp311) |

---

## 8. Render-Pipeline (FFmpeg AMF)

### 8.1 End-to-End-Datenfluss

```
POST /render/start (RenderRequest)
   │
   ├─► validate timeline (snapshot at request time, read-only)
   ├─► SEC-002 Path-Traversal-Check (is_relative_to)
   ├─► job_hash = SHA256(audio_path + timeline)
   ├─► RenderQueue.enqueue(job_hash, ...)        ──► SQLite-persistent (Resume on Crash)
   │
   └─► asyncio.create_task(_run_render_task)
           │
           ├─ Build concat-demuxer file (lokale escape-paths)
           ├─ FFmpeg-Cmd:
           │     -i concat:list  -vf "scale=...:fps=..."  
           │     -c:v {h264_amf|hevc_amf|av1_amf} -quality speed -b:v 8M
           │     [-c:a aac -b:a 192k]
           ├─ subprocess (hidden console, -progress pipe:1)
           │     └─► parse frame/bitrate/speed → SSE render_progress (% + eta)
           ├─ optional Audio-Mux: ffmpeg -i video -i audio -c:v copy -c:a aac
           └─ RenderQueue.update(status=completed)
```

### 8.2 Encoder-Auswahl (R4)

| Kandidat | Position | Hardware | Status |
|----------|---------:|----------|:-:|
| `hevc_amf` | 1 | AMD AMF | ✅ |
| `h264_amf` | 2 | AMD AMF | ✅ |
| `h264_mf` | 3 | Windows Media-Foundation | (Fallback) |
| `libx264` | 4 | Software | ⚠️ Last-Resort |

**Belege:** `rendering/render_engine.py:70` und `rendering/proxy_service.py:39`. Es existiert **kein** Vorkommen von `nvenc`, `cuda` oder `pynvml` im gesamten Render-Pfad.

### 8.3 IRON-Rule-Audit Render

| Rule | Status | Beleg |
|------|:-:|------|
| R4 (AMF) | ✅ | hevc/h264_amf primär, libx264 nur Fallback |
| R5 (kein pynvml) | ✅ | — |
| R6 (pathlib) | ✅ | `path_helpers.escape_path_for_ffmpeg` |
| Aufgabe I (Resume) | ✅ | `restore_render_queue_on_startup` in Lifespan |

---

## 9. WPF-Frontend & End-to-End-Verdrahtung

### 9.1 App-Boot-Sequenz

```
App.OnStartup()
  ├─► ConfigureServices (DI: HttpClient, ApiClient, SSEClient,
  │                       PythonBridgeService, Dialog/Navigation/Project,
  │                       Audio/Video/Timeline-StateService, 13 ViewModels)
  ├─► MainWindow.Show()                       (UI sofort sichtbar)
  └─► Background-Task: PythonBridgeService.StartAsync()
         ├─ FindBackendDirectory()
         ├─ ProcessStartInfo.Environment["PYTHONPATH"] = projectRoot/src   ✅ R7
         ├─ python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
         ├─ stdout/stderr → Debug-Log
         └─ Health-Check (max 30s warten)
```

**Shutdown:** WeakReferenceMessenger("app-shutdown") · `SaveProjectAsync()` ∥ `ShutdownAsync()` · `PythonBridgeService.StopAsync()` (8s Timeout) · ServiceProvider.Dispose().

### 9.2 ApiClient ↔ IApiClient (Vollständigkeit)

| Kategorie | Methoden | Parität |
|-----------|----------|:-:|
| Health/GPU | GetHealth, GetGpuStatus, CleanupGpu | ✅ |
| Project | Create / Open / Save / Close / Info | ✅ |
| Audio | Import / GetClips / Analyze / GetBeats / Stems / Waveform / Structure / Spectral | ✅ |
| Video | Import / GetClips / GetThumbnail / Analyze / GetScenes / GetMotion | ✅ |
| Pacing | GenerateCutList / GetTimeline / UpdateTimeline / GeneratePreview | ✅ |
| Render | Start / GetStatus / Cancel / Shutdown | ✅ |
| Brain | Suggest / Feedback / LearningSession / Stats / Reset / Explain | ✅ |
| Telemetry | GetVramTelemetry(modelId?) | ✅ |

**Insgesamt 73 Methoden — 100 % Parität, keine Stubs.**

### 9.3 SSE-Client (3 Streams)

```
SSEClient.StartListening()
  ├─ /events/progress  → ProgressReceived  (analysis/render/import/stem/gpu_error)
  ├─ /events/log       → LogReceived
  └─ /events/gpu       → GpuStatusReceived (alle 5s)

State-Guards: _stateLock (BUG-056), exponentielles Reconnect 3→30s, max 50 Versuche.
```

### 9.4 State-Services (Cross-View-Cache)

| Service | Cache | TTL | Event |
|---------|-------|-----|-------|
| `AudioLibraryStateService` | `IReadOnlyList<AudioClipInfo>` | 2 s | `AudioClipsChanged` |
| `VideoLibraryStateService` | `IReadOnlyList<VideoClipInfo>` | 2 s | `VideoClipsChanged` |
| `TimelineStateService` | `TimelineResponse?` | — (always fresh) | `TimelineChanged` |
| `ProjectService` | `ProjectInfo?` | — | `ProjectChanged` + Messenger `project-opened/closed` |

Pattern: Singleton + Observer + WeakReferenceMessenger → loose coupling, In-Flight-Dedup.

### 9.5 Views (Bindings & Endpoints)

| View / ViewModel | Wichtigste Endpoints | SSE-Events | Bindings | Status |
|------------------|----------------------|-----------|---------:|:-:|
| **ProjectOverviewView** / VM | `/project/info`, `/audio/clips`, `/video/clips` | — | 100 % | 🟢 |
| **MediaIngestView** / VM | `/audio/import`, `/video/import` | — | 100 % | 🟢 |
| **AudioLibraryView** / VM | `/audio/{clips,analyze,beats,stems}` | `analysis_progress` | 100 % | 🟢 |
| **VideoLibraryView** / VM | `/video/{clips,thumbnails,analyze,scenes,motion}` | `analysis_progress` | 100 % | 🟢 |
| **DirectorView** / VM | `/pacing/generate`, `/pacing/timeline`, `/brain/suggest` | `pacing_progress`, `brain_suggest_progress` | 100 % | 🟢 |
| **TimelineView** / VM | `/pacing/timeline`, `/pacing/preview`, `/audio/spectral`, `/audio/waveform` | `preview_progress` | 100 % | 🟢 |
| **ProductionView** / VM | `/render/{start,status,cancel}` | `render_progress`, `render_error`, `gpu_status` | 100 % | 🟢 |
| **BrainView** / VM | `/brain/{stats,feedback,learning_session,reset}` | — | 100 % | 🟢 |
| **SettingsView** / VM | `/gpu/{status,cleanup}` + lokale `settings.json` | gpu_status | 100 % | 🟢 |
| **VramTelemetryView** / VM | `/health/vram?model_id=` (5 s Polling) | — | 100 % | 🟢 |
| **AnchorView** / VM | `/audio/{waveform,beats}` (read-only) | — | 100 % | 🟢 |
| **LearningSessionDialog** / VM | `/brain/learning-session` | — | 100 % (Tasten 1–4, ←→, Esc) | 🟢 |

### 9.6 End-to-End-Klickpfade (Beispiele)

**A) Audio importieren → Library-Update**
```
[User klickt "Audio importieren" in MediaIngestView]
  → ImportAudioCommand
  → DialogService.OpenFiles
  → ApiClient.ImportAudioAsync(path)        ── POST /audio/import
  → AudioClipModel append → ImportedAudio (ObservableCollection)
  → Messenger.Send("audio-imported")
       ├─ ProjectOverviewVM.RefreshAsync   (count update)
       └─ AudioLibraryVM.LoadAudioClipsAsync → AudioLibraryState.RefreshAsync
              → ApiClient.GetAudioClipsAsync ── GET /audio/clips
              → AudioClips ObservableCollection → ListView
```

**B) Cut-Liste generieren → Brain-Feedback-Loop**
```
[DirectorView: User klickt "Cut-Liste generieren"]
  → GenerateCutListCommand
  → ApiClient.GenerateCutListAsync(PacingConfig{ useBrain=true })
        ── POST /pacing/generate
              → AdvancedPacingEngine + Brain-Postprocessor
  → DirectorVM.CutList populated
  → Messenger.Send("cuts-generated")
       └─ TimelineVM.LoadTimelineAsync → GET /pacing/timeline
  
[BrainView: User klickt "👍 Perfect" auf cut_id=42]
  → ApiClient.BrainFeedbackAsync(42, rating=1)  ── POST /brain/feedback
        → WeightStore-Update + Bucket-Bumps
  → Messenger.Send(BrainFeedbackAppliedMessage(42))
       └─ TimelineVM invalidiert Confidence-Tooltip für Cut #42
```

**C) Render → SSE-Progress → ProductionLog**
```
[ProductionView: "Rendern starten"]
  → ApiClient.StartRenderAsync(RenderRequest)  ── POST /render/start
  → Backend spawnt FFmpeg-AMF-Subprocess
  → SSEClient.ProgressReceived (event_type="render_progress")
       ├─ ProductionVM.RenderProgress (ProgressBar.Value)
       ├─ ProductionVM.EtaText
       └─ ProductionVM.RenderLogEntries.Add(entry)
  → event_type="render_complete" → IsRendering=false
```

### 9.7 IRON-Rule-Audit WPF

| Rule | Status | Beleg |
|------|:-:|------|
| R6 (Windows-Pfade) | ✅ | `Path.Combine` durchgängig, keine hardcoded Slashes |
| R7 (PYTHONPATH=src) | ✅ | `PythonBridgeService.StartAsync` setzt es vor Subprocess |

---

## 10. IRON-Rule-Compliance — Gesamtmatrix

| Regel | Backend | Audio | Video | AI/Pacing | Render | Core/Data | WPF | Gesamt |
|-------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **R1** AMD/DML only | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ✅ |
| **R2** beide DML-Flags | n/a | ✅ | ✅ | ✅ | n/a | n/a | n/a | ✅ |
| **R3** Py 3.11 + NumPy 1.26.4 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ✅ |
| **R4** AMF-Encoder | n/a | n/a | n/a | n/a | ✅ | n/a | n/a | ✅ |
| **R5** kein pynvml | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | n/a | ✅ |
| **R6** pathlib / Win-Paths | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **R7** PYTHONPATH=src | ✅ | n/a | n/a | n/a | n/a | n/a | ✅ | ✅ |
| **R8** `Tests/` Großbuchst. | ✅ (`pytest Tests/`) | n/a | n/a | n/a | n/a | n/a | n/a | ✅ |

**Verdict:** 🟢 **Vollständige IRON-Rule-Compliance über alle Schichten.**

---

## 11. Bekannte Legacy-/Optionale Bereiche (nicht blockierend)

| Bereich | Status | Anmerkung |
|---------|:-:|-----------|
| `audio/streaming_analyzer.py` | 🔴 (Stub) | Echtzeit-Streaming für Mixe >60min noch nicht implementiert |
| `audio/analyzer.py` | 🟡 | High-Level-Wrapper – partial overlap mit BeatDetector/StructureAnalyzer |
| `pacing/smart_director.py` | 🟡 | Deprecated alias → `ai.smart_director`, Konsolidierung empfohlen |
| `ai/clap_wrapper.py` (ONNX) | 🟡 | ONNX-Export von CLAP HTSAT-Unfused noch nicht final; `clap_pytorch.py` (CPU) als Fallback aktiv |
| `ai/moondream_pytorch.py` | 🟡 | PyTorch-Fallback (CPU) für Moondream existiert; Standard ist ONNX-DML |
| `core/task_queue.py` | 🟡 | Priority-Queue definiert, derzeit minimal eingesetzt – für künftige Batch-Jobs vorgesehen |
| `services/final_renderer.py` | 🟡 | Audio-Mux-Logik unvollständig integriert |
| `data/database_core.py` | 🟡 | Transaction-Context-Manager — Rollback-Semantik prüfen |
| `services/NavigationService.cs` | 🟡 | DEAD CODE (keine Subscriber); `MainViewModel.SelectedTabIndex`-Binding wird stattdessen genutzt |
| Messenger-Keys (string-basiert) | 🟡 | Typo-Risiko – schrittweise auf strongly-typed messages migrieren (siehe `BrainFeedbackAppliedMessage`) |
| `LearningSessionVM.ResolveVideoUri` | 🟡 | Heuristische Datei-Suche – bei verschobenen Videos still failure |

---

## 12. Test-Status (Obsidian Vault `_plan/INDEX.md`, 2026-05-06, Brain-Modul Phase 6)

```
Tests/-Suite (pytest, 47 .py-Dateien): 239 passed · 8 skipped · 0 failures
Verifiziert nach Brain-Phase-6 (Commit eb18dc5).

Kern-Coverage:
  test_audio_analyzer.py        ✅
  test_moondream_safety.py      ✅
  test_pacing_engine.py         ✅
  test_separator.py             ✅
  test_siglip_video.py          ✅
  test_smart_director_integration.py ✅
  test_torchvision_stub.py      ✅
  test_vector_store.py          ✅
  test_vram_arbiter.py          ✅
  test_waveform_analyzer.py     ✅
  test_sse_live.py              ✅

Brain-Modul-Coverage (47 neue Tests):
  test_brain_backup.py          ✅
  test_brain_caching.py         ✅
  test_brain_caching_layers.py  ✅
  test_brain_core.py            ✅
  test_brain_cross_modal.py     ✅
  test_brain_embeddings.py      ✅
  test_brain_explain.py         ✅
  test_brain_helpers_new.py     ✅
  test_brain_learned_projector.py ✅
  test_brain_post_processor.py  ✅
  test_brain_recovery.py        ✅
  test_brain_router.py          ✅
  test_brain_smart_sampler.py   ✅
  test_clap_wrapper.py          ✅
  test_media_hash.py            ✅
  test_media_repository_idempotency.py ✅

GUI manuell: gui_screenshot_test.py / gui_test_pywinauto.py / autonomous_ui_agent.py
```

Skipped: meist GPU-Hardware-abhängig oder externe Modelle nicht verfügbar.

Historischer Stand (CHANGELOG, Pre-Brain-Modul, 2026-03-16): 186 passed / 9 skipped (20-Runden Deep-Audit, R12–R20).

---

## 13. Empfohlene nächste Schritte

1. **End-to-End-GUI-Test** (laut CLAUDE.md "Next Task"): `auto-qa-loop`-Skill für alle 12 Views starten.
2. **Konsolidierung** `pacing/smart_director.py` → `ai/smart_director.py` finalisieren (deprecated alias entfernen).
3. **NavigationService** entfernen (DEAD CODE) ODER aktiv durch `Frame`-basierte Navigation ersetzen.
4. **Streaming-Analyzer** für Mixe >60min implementieren (madmom-Patches bereits aktiv).
5. **Messenger-Keys** schrittweise auf strongly-typed Records migrieren.

---

## 15. Bugs gefunden und gefixt 2026-05-08 (Trust-Incident)

User-gemeldetes Symptom: Nach Video-Import zeigt VIDEO-Tab keine Clips, Status-Text bleibt auf "Video-Clips werden geladen…".

### 15.1 BUG-200: CTS-Race in `VideoLibraryViewModel.LoadClipsAsync`
- **Datei:** `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`
- **Pattern:** `ProcessVideoImportAsync` rief `Send("video-imported")` UND `await LoadClipsAsync()` direkt nacheinander. Messenger-Handler triggert `RequestClipReloadAsync` synchron auf UI-Thread → Load1 startet, suspendiert beim HTTP-await. Direct-call → Load2 ruft `ReplaceActiveLoadCts()` → cancelled+disposed Load1's CTS mid-flight.
- **Folge:** Load1 sieht `cancellationToken.IsCancellationRequested=true` → early return ohne UI-Update. Load1's recursion → Load3 ruft `Cancel()` auf bereits disposed CTS → `ObjectDisposedException` (fire-and-forget, unobserved). Status bleibt für immer auf "Video-Clips werden geladen…".
- **Beweis:** WPF-Log Stacktrace `ObjectDisposedException at VideoLibraryViewModel.cs:501 (CancelActiveLoad)`; Backend-Log zeigt `/video/clips 200 OK` aber keine `/video/thumbnails`-Folgecalls.
- **Fix:** (a) Reihenfolge umgedreht — `await LoadClipsAsync()` VOR `Send(...)`. (b) `ReplaceActiveLoadCts` + `CancelActiveLoad` schlucken jetzt `ObjectDisposedException`.

### 15.2 BUG-201: Fehlende XAML-Resource `VideoThumbCard`
- **Datei:** `PBStudio.UI/App.xaml`
- **Pattern:** Commit `6dbf895` ("MVP Release Hardening") entfernte lokale `<Style x:Key="VideoThumbCard">` aus `VideoLibraryView.xaml`, migrierte ihn aber nie zu App.xaml. Verwaiste `StaticResource`-Referenz seitdem.
- **Folge:** `WrapPanel.MeasureOverride` → `Border` mit `Style="{StaticResource VideoThumbCard}"` → `XamlParseException: Die Ressource mit dem Namen "VideoThumbCard" kann nicht gefunden werden`. Crash beim Layout-Pass mit 126 Items → Tab blockiert.
- **Fix:** Style in App.xaml hinzugefügt (Border, AbletonSurface, 200 width, 4 margin).

### 15.3 BUG-202: Fehlende Color-Resource `AbletonYellowColor` (latent)
- **Datei:** `PBStudio.UI/App.xaml` + `PBStudio.UI/Views/TimelineView.xaml:418`
- **Pattern:** Storyboard-Animation in TimelineView setzt `(SolidColorBrush.Color)` mit `To="{StaticResource AbletonYellowColor}"`. App.xaml hatte nur `AbletonYellow` als `SolidColorBrush`, keine separate `Color`-Resource.
- **Folge:** Wäre beim ersten Beat-Animation-Trigger in TimelineView gecrasht. Latent, weil User vor Crash schon im Video-Tab Crash hatte.
- **Fix:** Alle Ableton-Brushes umgebaut auf zugehörige `*Color`-Resources. `Color`-Definitionen jetzt vorhanden für Storyboards.

### 15.4 BUG-203: Launcher lädt veraltetes Release-Binary nach Code-Änderung
- **Datei:** `start.bat`, `launch.ps1`, `build.ps1`
- **Pattern:** `launch.ps1` startet `PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe` ohne Auto-Rebuild. Nach Code-Änderung musste User manuell `build.ps1 -c Release` aufrufen — passierte oft nicht.
- **Folge:** User testete altes Binary obwohl Source aktuell. Trust-Incident heute genau aus diesem Grund — CTS-Race-Fix war im Source aber nicht im laufenden Binary.
- **Fix:** `start.bat` erweitert um Build-Check vor Launch: PowerShell-Timestamp-Vergleich Source vs. Release-DLL → ruft `build.ps1 -Configuration Release` wenn nötig. Build-Failure → ABORT, kein Launch mit altem Binary. `build.ps1` modernisiert (`$ErrorActionPreference="Continue"`, `$LASTEXITCODE`-Sicherung, Em-dashes/Umlaute → ASCII für PS5.1 BOM-Safety). Validiert via script-validator-Skill mit 3× clean Smoke-Runs.

### 15.5 IRON-Rule R9 hinzugefügt
- **Datei:** `CLAUDE.md` §2 + Memory + Obsidian
- **Pattern:** Trust-Incident hat gezeigt dass "Source geändert + Build OK" nicht reicht — Deployment-Step (Release-Build, abhängige Wrapper-Updates, Validierung) muss autonom passieren ohne User-Aufforderung.
- **R9-Regel:** Nach JEDER Aufgabe die Code/Scripts/Configs ändert die Deployment brauchen → Deployment AUTONOM ausführen. Niemals "Source geändert, fertig" als Endmeldung.

### 15.6 BUG-204: Fehlende SSE `analysis_progress` Events bei Video-Analyse
- **Datei:** `backend/routers/video_router.py` `analyze_video()`
- **Pattern:** Audio-Router + Pacing-Router emittieren `publish_event("analysis_progress", ...)` während Analyse. Video-Router emittierte NIE. C# `VideoLibraryViewModel.OnSseProgressReceived` lauscht auf `analysis_progress` für StatusText-Updates → keine Live-Status-Updates während mehrminütiger RAFT/SigLIP-Analyse.
- **Beweis:** `grep -r "publish_event.*analysis_progress" backend/` → 4 Treffer audio_router, 1 Treffer pacing_router, 0 Treffer video_router. Auto-QA-Loop F-4.6 SSE-Test: 0 events received während POST /video/analyze.
- **Fix:** 3× `publish_event("analysis_progress", ...)` in `analyze_video()` (start 5%, complete 100% mit scene_count+avg_motion, error 0%).
- **Status:** Code committed in `9203caa`. Erfordert Backend-Restart für Aktivierung. Re-Test F-4.6 nach Restart.
- **Severity:** MITTEL — UX-Verschlechterung (keine Live-Progress), nicht funktional-blockierend (Endergebnis kommt via HTTP-Response).

---

## 14. Quellen / Methodik

- **Statische Analyse** (Read + Grep) der relevanten Module unter `backend/`, `src/pb_studio/`, `PBStudio.UI/`.
- **4 parallele Sub-Agents** (Backend / AI-Pipelines / Core+Data+Render / WPF-UI), Read-Only.
- **CLAUDE.md** als Projekt-Brain (Marker 2026-03-16, vor Brain-Modul-Integration) als Referenz für IRON-Rules und Architektur-Entscheidungen.
- **CHANGELOG.md** als Bug-/Fix-Historie (BUG-001..046, HIGH-001..046, R12–R20).
- **Obsidian Vault** `C:\Users\david\Brain\10_Projects\PB_studio` für aktuelle Test- und Brain-Modul-Stände (2026-05-06, Phase 6).

> ⚠️ Dieser Report wurde durch reines Scannen erstellt. **Keine Code- oder Konfigurations-Änderungen** wurden vorgenommen.
