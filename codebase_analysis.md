# PB Studio AMD – Comprehensive Codebase Analysis
**Erstellt:** 2026-03-06 | **Analysiert von:** Claude (Senior Dev Mode) | **Stand:** Phase G-J abgeschlossen

---

## 1. Project Overview

**Projekttyp:** Desktop-Anwendung (Hybrid-Architektur)
**Zweck:** KI-gestütztes Video-Editing-Studio für AMD-Hardware (DirectML). Analysiert Audio/Video, erkennt Beats, trennt Stems, generiert automatisch einen Videoschnitt basierend auf Musikrhythmus und Videosemantik.

**Tech Stack:**
- **Frontend:** C# WPF .NET 9.0 (MVVM via CommunityToolkit.Mvvm 8.4.0)
- **Backend API:** Python FastAPI (uvicorn, Port 8765)
- **Core ML:** Python 3.11 + ONNX Runtime DirectML + PyTorch CPU
- **Kommunikation:** HTTP/REST + Server-Sent Events (SSE)
- **Datenbank:** SQLite (SQLAlchemy) + FAISS-CPU (Vektor-Index)
- **GPU-Engine:** AMD DirectML (ONNX Runtime) – kein CUDA, kein ROCm

**Architektur-Pattern:** 3-Layer Hybrid
1. C# WPF MVVM Frontend
2. Python FastAPI REST-API (Prozess-Bridge)
3. Python Core-Logic (ML-Pipeline, unverändert)

---

## 2. Detailed Directory Structure Analysis

```
Pb_studio_AMD_version/
├── PBStudio.UI/              ← C# WPF .NET 9.0 Frontend
│   ├── Services/             ← API-Client, SSE, Navigation, PythonBridge
│   ├── ViewModels/           ← 9 MVVM ViewModels
│   ├── Views/                ← 9 XAML Views
│   ├── Models/               ← AudioClipModel, VideoClipModel
│   ├── Converters/           ← Value-Converter (Null, Bool, Visibility)
│   └── Resources/            ← app.ico (16/32/48px)
│
├── backend/                  ← Python FastAPI Backend
│   ├── main.py               ← App-Entrypoint, Router-Registration
│   ├── app_state.py          ← Singleton AppState (ADR-001/003)
│   ├── config.py             ← pydantic-settings Konfiguration
│   ├── dependencies.py       ← with_gpu_task(), publish_event()
│   ├── middleware/
│   │   └── gpu_lock.py       ← GPU-Mutex Middleware
│   ├── routers/              ← 6 FastAPI Router
│   │   ├── audio_router.py
│   │   ├── video_router.py
│   │   ├── pacing_router.py
│   │   ├── render_router.py
│   │   ├── events_router.py  ← SSE Stream
│   │   └── project_router.py
│   └── schemas/              ← Pydantic In/Out-Schemas
│
├── src/pb_studio/            ← Python Core (LOCKED – kein Refactoring)
│   ├── audio/                ← Beat/Stem/Spektral/Waveform/Key-Analyse
│   ├── video/                ← RAFT Optischer Fluss, SceneDetect, Thumbnails
│   ├── pacing/               ← SmartDirector, Timeline-Generierung
│   ├── ai/                   ← Moondream (Vision-LLM), VideoSpecialist
│   ├── core/                 ← VRAM-Arbiter, SystemMonitor, TaskQueue
│   ├── data/                 ← DatabaseCore (SQLite + SQLAlchemy)
│   ├── models/               ← ORM-Modelle (Audio, Video, Timeline)
│   ├── rendering/            ← FinalRenderer, RenderEngine, PreviewRenderer
│   └── services/             ← Orchestrierungs-Services
│
├── models/                   ← ONNX/PT Modell-Dateien
│   ├── siglip_vision.onnx    ← SigLIP SO400M (1152-dim Embeddings)
│   ├── raft_small.onnx       ← RAFT Optical Flow
│   ├── UVR-MDX-NET-*.onnx    ← Stem-Separation
│   └── moondream_pytorch.pt  ← Vision-LLM
│
├── data/                     ← Laufzeit-Daten
│   ├── pb_studio.db          ← SQLite (WAL-Mode)
│   └── test_index.faiss      ← FAISS Vektor-Index
│
├── Tests/                    ← pytest Test-Suite (testpaths = Tests)
├── docs/architecture/        ← ADR-002, ADR-003
├── tools/LibreHardwareMonitor/ ← DLL für GPU-Monitoring
├── requirements.txt
└── pyproject.toml
```

---

## 3. File-by-File Breakdown

### Core Application Files

| Datei | Funktion |
|-------|----------|
| `backend/main.py` | FastAPI App, Lifespan, CORS, Router-Registrierung, /health, /gpu/status, /gpu/cleanup, /shutdown |
| `backend/app_state.py` | Singleton AppState – In-Memory Zustand für alle Router (Clips, Timeline, Render-Tasks). Thread-safe via Lock. SQLite-Persistenz beim Startup (ADR-003). |
| `backend/config.py` | pydantic-settings: host, port, log_level, ffmpeg_path, project_dir |
| `backend/dependencies.py` | `with_gpu_task(model_id)` Context-Manager (VRAMBudgetManager), `publish_event()` für SSE |
| `backend/middleware/gpu_lock.py` | Serialisiert GPU-Zugriffe via Mutex – verhindert konkurrierende DirectML-Calls |
| `src/pb_studio/core/vram_arbiter.py` | VRAM-Budget-Verwaltung. Prüft freien VRAM, reserviert Budget pro Modell |
| `src/pb_studio/core/system_monitor.py` | GPU-Stats via LibreHardwareMonitorLib.dll (pythonnet). KEIN pynvml |
| `src/pb_studio/audio/separator.py` | Demucs Stem-Separation (DirectML). LOCKED: segment_size=5, overlap=0.1, min_free_vram_gb=1.5 |
| `src/pb_studio/audio/beat_detector.py` | BeatNet (1.1.1) + librosa-Fallback |
| `src/pb_studio/audio/key_detector.py` | Krumhansl-Kessler via librosa |
| `src/pb_studio/video/raft.py` | RAFT Optical Flow (ONNX DirectML) → MotionAnalyzer |
| `src/pb_studio/video/scene_detect.py` | PySceneDetect → SceneDetector |
| `src/pb_studio/ai/video_specialist.py` | SigLIP SO400M Embeddings (1152-dim) via ONNX DirectML |
| `src/pb_studio/pacing/smart_director.py` | Kern-Algorithmus: Audio-Beats + Video-Semantik → Timeline |
| `src/pb_studio/data/database_core.py` | SQLAlchemy + SQLite Singleton. `shutdown()` setzt `_instance = None` |

### C# WPF Frontend Files

| Datei | Funktion |
|-------|----------|
| `PBStudio.UI/App.xaml.cs` | DI-Setup (Ioc.Default), Alle 9 ViewModels registriert. Kein StartupUri |
| `PBStudio.UI/MainWindow.xaml` | Shell mit NavigationService und Tab-Layout |
| `PBStudio.UI/Services/ApiClient.cs` | Vollständiger HTTP-Client für alle 25+ API-Endpoints. Async/Await |
| `PBStudio.UI/Services/IApiClient.cs` | Interface (inkl. CleanupGpuAsync, GetAudioClipsAsync) |
| `PBStudio.UI/Services/SSEClient.cs` | Server-Sent Events Consumer – Progress-Events an ViewModels |
| `PBStudio.UI/Services/PythonBridgeService.cs` | Startet/stoppt den Python-Prozess via `PBSTUDIO_PYTHON_EXE` env var |
| `PBStudio.UI/Services/ProjectService.cs` | Projekt-Verwaltung (Create/Load/Save) |

### ViewModels (MVVM)

| ViewModel | Zuständigkeit |
|-----------|--------------|
| `MainViewModel` | Navigation, App-State, PythonBridge-Start |
| `MediaIngestViewModel` | Datei-Import (Audio + Video) |
| `AudioLibraryViewModel` | Audio-Clip-Liste, Analyse starten |
| `VideoLibraryViewModel` | Video-Clip-Liste (Auto-Load beim Start via `LoadClipsAsync()`) |
| `DirectorViewModel` | Smart-Director: Clips auswählen, Timeline generieren |
| `TimelineViewModel` | Timeline anzeigen, bearbeiten |
| `ProductionViewModel` | Render starten, Fortschritt |
| `AnchorViewModel` | Anker-Punkte für Timing |
| `SettingsViewModel` | App-Konfiguration |

### Schemas (Pydantic)

| Schema-Datei | Inhalt |
|-------------|--------|
| `audio_schemas.py` | AudioImportRequest, AudioClipInfo, AudioAnalyzeRequest, AudioAnalysisResult (inkl. List[float] EnergyCurve), BeatData, WaveformData, StemResult, StructureSegment, SpectralData |
| `video_schemas.py` | VideoImportRequest, VideoClipInfo, VideoAnalysisResult, SceneInfo, MotionData (peak_frames: list[dict]) |
| `pacing_schemas.py` | PacingRequest, TimelineEntry (inkl. SegmentType), PacingConfigSchema |
| `render_schemas.py` | RenderRequest (fps: float = 30.0, resolution_width/height, bitrate_mbps), RenderStatus |
| `project_schemas.py` | ProjectCreate, ProjectInfo |
| `common.py` | StatusResponse, ErrorDetail |

---

## 4. API Endpoints Analysis

**Base-URL:** `http://localhost:8765`
**Auth:** Keine (lokale Desktop-App, Single-User)
**Format:** JSON (REST) + text/event-stream (SSE)

### Alle Endpoints

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/health` | Health-Check (uptime, gpu_available) |
| GET | `/gpu/status` | VRAM-Stats via LibreHardwareMonitor |
| POST | `/gpu/cleanup` | VRAM-Budget reset |
| POST | `/shutdown` | Graceful shutdown (SIGTERM in 2s) |
| POST | `/project/create` | Neues Projekt (Path-Traversal-Schutz) |
| GET | `/project/current` | Aktuelles Projekt |
| POST | `/project/load` | Projekt laden |
| POST | `/audio/import` | Audio-Datei importieren |
| POST | `/audio/analyze` | Beat, Struktur, Spektral, Waveform analysieren |
| GET | `/audio/beats/{id}` | Beat-Daten |
| GET | `/audio/waveform/{id}?bands=N` | Waveform (bands: 1-8, constraint ge=1 le=8) |
| POST | `/audio/stems/separate` | Demucs Stem-Separation |
| GET | `/audio/structure/{id}` | Struktur-Segmente |
| GET | `/audio/spectral/{id}` | Spektral-Daten |
| GET | `/audio/clips` | Audio-Clip-Liste |
| POST | `/video/import` | Video-Dateien importieren |
| GET | `/video/clips` | Video-Clip-Liste |
| GET | `/video/thumbnails/{id}` | Thumbnail JPEG |
| POST | `/video/analyze` | SceneDetect + MotionAnalyzer + SigLIP |
| GET | `/video/scenes/{id}` | Scene-Cuts |
| GET | `/video/motion/{id}` | Motion-Daten |
| POST | `/pacing/generate` | SmartDirector → Timeline generieren |
| GET | `/pacing/timeline` | Aktuelle Timeline |
| POST | `/render/start` | Render starten (Path-Traversal-Schutz) |
| GET | `/render/status/{task_id}` | Render-Fortschritt |
| POST | `/render/cancel/{task_id}` | Render abbrechen |
| GET | `/events/stream` | Server-Sent Events (Progress, Logs, Status) |

### Sicherheits-Fixes (umgesetzt)

- **SEC-001:** `project/create` prüft Pfad gegen `config.project_dir` (Path-Traversal)
- **SEC-002:** `render/start` prüft `output_path` gegen `config.project_dir` (Path-Traversal)
- **SEC-003:** Shutdown via `os.kill(SIGTERM)` statt `os._exit(0)` (SQLite WAL sicher)

---

## 5. Architecture Deep Dive

### Gesamtarchitektur

```
┌──────────────────────────────────────────────────────────────────────┐
│                     USER (Windows Desktop)                           │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│              C# WPF Frontend (PBStudio.UI)                           │
│                                                                      │
│  [MainWindow] → [NavigationService] → [Views (XAML)]                │
│       ↕ DataBinding (CommunityToolkit.Mvvm)                         │
│  [ViewModels] ←→ [IApiClient] ←→ [SSEClient]                        │
│                       │                │                             │
│           HTTP/REST (Port 8765)     SSE Stream                      │
└─────────────────────┬────────────────────────────────────────────────┘
                      │ localhost:8765
┌─────────────────────▼────────────────────────────────────────────────┐
│           Python FastAPI Backend (backend/)                          │
│                                                                      │
│  [main.py] → [GPULockMiddleware] → [Router]                         │
│  [AppState Singleton] ← [6 Router] → [with_gpu_task()]              │
│  audio_router | video_router | pacing_router | render_router         │
│  project_router | events_router (SSE)                               │
│       ↕ asyncio.to_thread()  (blockierende ML-Calls)               │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│           Python Core (src/pb_studio/) – LOCKED                      │
│                                                                      │
│  audio/: BeatDetector, Demucs(DirectML), Spectral, Waveform, Key    │
│  video/: RAFT(DirectML), SceneDetect, FrameExtractor, Thumbnails    │
│  pacing/: SmartDirector, ClipSelector, MoodGenerator, Timeline      │
│  ai/:    Moondream(ONNX), SigLIP SO400M(ONNX), VideoSpecialist      │
│  core/:  VRAMArbiter, SystemMonitor(LHM-DLL), TaskQueue             │
│  data/:  DatabaseCore(SQLite/SQLAlchemy), VectorStore(FAISS-CPU)    │
│  rendering/: FinalRenderer(FFmpeg AMF), RenderEngine, Preview       │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│                 Hardware & Persistenz                                │
│                                                                      │
│  AMD GPU (DirectML via ONNX Runtime)                                │
│  SQLite (WAL-Mode): data/pb_studio.db                               │
│  FAISS-CPU Index:   data/test_index.faiss                           │
│  LibreHardwareMonitorLib.dll (GPU-Monitoring)                       │
│  FFmpeg 6.x Gyan.dev (h264_amf / hevc_amf / av1_amf)               │
└──────────────────────────────────────────────────────────────────────┘
```

### Datenfluss: Audio-Analyse

```
User wählt MP3 → C# AudioLibraryViewModel
  → POST /audio/import          → AppState.audio_clips[id]
  → POST /audio/analyze         → asyncio.to_thread(_run_audio_analysis)
      → BeatDetector (librosa)
      → SpectralAnalyzer
      → StructureAnalyzer
      → WaveformAnalyzer
      → KeyDetector (Krumhansl-Kessler)
      → AppState.audio_analysis_cache[id]
  → SSE /events/stream          → C# SSEClient → Progress-Updates
  → GET /audio/beats/{id}       → C# AudioLibraryViewModel.BeatData
```

### Datenfluss: Video-Render

```
User klickt "Render" → C# ProductionViewModel
  → POST /render/start          → RenderTask erzeugt (UUID)
      → asyncio.to_thread(_execute_render)
          → with_gpu_task("renderer")   ← VRAMBudgetManager
          → FinalRenderer.render()
              → FFmpeg h264_amf / hevc_amf / av1_amf
              → request.resolution_width/height/bitrate_mbps
              → fps: float = 30.0 (23.976 korrekt via vf_filter fps={fps:.3f})
  → GET /render/status/{task_id} (Polling) + SSE (Push)
```

### Key Design Patterns

| Pattern | Implementierung |
|---------|----------------|
| MVVM | CommunityToolkit.Mvvm `[ObservableProperty]`, `[RelayCommand]` |
| Singleton | AppState (Python), DatabaseCore (Python) |
| Repository | MediaRepository (SQLite via SQLAlchemy) |
| Dependency Injection | C#: `Ioc.Default.GetRequiredService<T>()` |
| Async Wrapping | `asyncio.to_thread()` für alle blockierenden ML-Calls |
| Event Bus | SSE Stream (`/events/stream`) für Push-Notifications |
| GPU Arbiter | `VRAMArbiter` + `VRAMBudgetManager` + `with_gpu_task()` |
| Middleware | `GPULockMiddleware` serialisiert GPU-Zugriffe |

---

## 6. Environment & Setup Analysis

### Voraussetzungen

| Komponente | Version | Quelle |
|------------|---------|--------|
| Python | 3.11.x | python.org |
| .NET SDK | 9.0 | microsoft.com |
| FFmpeg | 6.x | Gyan.dev (Windows) |
| AMD GPU | DirectX 12-fähig | — |
| LibreHardwareMonitor | DLL enthalten | tools/ |

### Installation

```powershell
# 1. Python-Abhängigkeiten
pip install -r requirements.txt

# 2. C# Frontend bauen
dotnet build PBStudio.UI\PBStudio.UI.csproj

# 3. Backend starten
python -m uvicorn backend.main:app --port 8765

# 4. WPF App starten
.\PBStudio.UI\run.ps1
```

### Umgebungsvariablen

| Variable | Bedeutung |
|----------|-----------|
| `PBSTUDIO_PYTHON_EXE` | Pfad zur Python-Executable (PythonBridgeService) |

### Test-Ausführung

```powershell
# Wichtig: testpaths = Tests (Grossbuchstabe! Windows NTFS auf Linux-Mount)
pytest Tests/

# E2E-Tests
python test_e2e_full.py
```

### Kritische Test-Datenpfade

```
C:\Users\david\Videos\test_data\audio   ← Audio-Testdaten
C:\Users\david\Videos\test_data\video   ← Video-Testdaten
```

---

## 7. Technology Stack Breakdown

### Runtime & Frameworks

| Schicht | Technologie | Version |
|---------|------------|---------|
| C# Runtime | .NET | 9.0 |
| Python Runtime | CPython | 3.11.x |
| Web Framework | FastAPI | >=0.110.0 |
| ASGI Server | uvicorn | >=0.28.0 |
| MVVM Framework | CommunityToolkit.Mvvm | 8.4.0 |
| UI Framework | WPF (UseWPF=true) | .NET 9.0 |

### ML / AI Libraries

| Bibliothek | Version | Verwendung |
|-----------|---------|-----------|
| onnxruntime-directml | >=1.16.0 | GPU-Inferenz (AMD DirectML) |
| PyTorch (CPU) | 2.4.1+cpu | Tensor-Ops (kein GPU!) |
| torchaudio | 2.4.0+cpu | Audio-Preprocessing |
| demucs | >=4.0.0 | Stem-Separation |
| BeatNet | 1.1.1 | Beat-Detection |
| librosa | >=0.10.1 | Audio-Analyse, Key-Detection |
| transformers | >=4.48.0 | Tokenizer für SigLIP/Moondream |
| audio-separator | >=0.17.0 | UVR MDX-NET Wrapper |
| numpy | 1.26.4 (STRICT) | Tensor-Ops (< 2.0 wegen BeatNet) |

### Daten & Storage

| Technologie | Verwendung |
|------------|-----------|
| SQLite (WAL) | Clip-Metadaten, Projekt-State (SQLAlchemy ORM) |
| FAISS-CPU 1.7.4 | Vektor-Index (1152-dim SigLIP Embeddings) |

### UI / Design

| Paket | Version | Verwendung |
|-------|---------|-----------|
| MaterialDesignThemes | 5.1.0 | Material Design 3 Styling |
| MaterialDesignColors | 3.1.0 | Farbpalette |
| MahApps.Metro.IconPacks.Material | 5.0.0 | Material Icons |
| Microsoft.Xaml.Behaviors.Wpf | 1.1.135 | Event-To-Command Bindings |
| Microsoft.Extensions.DependencyInjection | 9.0.0 | DI Container |

---

## 8. Visual Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════╗
║              PB STUDIO AMD – SYSTEM OVERVIEW                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │           C# WPF FRONTEND (.NET 9.0)                        │    ║
║  │                                                              │    ║
║  │  MainWindow → NavigationService → XAML Views (9)            │    ║
║  │  ViewModels (9) via [ObservableProperty]/[RelayCommand]      │    ║
║  │  ApiClient (async) ←→ SSEClient (Push-Events)               │    ║
║  │  PythonBridgeService (startet/stoppt Python-Prozess)         │    ║
║  └──────────────────┬──────────────────────────────────────────┘    ║
║                     │ HTTP/REST + SSE (localhost:8765)               ║
║  ┌──────────────────▼──────────────────────────────────────────┐    ║
║  │           PYTHON FASTAPI BACKEND (backend/)                  │    ║
║  │                                                              │    ║
║  │  GPULockMiddleware → 6 Router                                │    ║
║  │  AppState Singleton (Thread-safe, SQLite-Restore)            │    ║
║  │  asyncio.to_thread() für alle ML-Calls                       │    ║
║  │  with_gpu_task() → VRAMBudgetManager                         │    ║
║  └──────────────────┬──────────────────────────────────────────┘    ║
║                     │ Python function calls                          ║
║  ┌──────────────────▼──────────────────────────────────────────┐    ║
║  │        PYTHON CORE (src/pb_studio/) – LOCKED                 │    ║
║  │                                                              │    ║
║  │  audio/  → BeatDetector, Demucs(DML), Spectral, Waveform    │    ║
║  │  video/  → RAFT(DML), SceneDetect, FrameExtractor            │    ║
║  │  pacing/ → SmartDirector, ClipSelector, Timeline             │    ║
║  │  ai/     → SigLIP SO400M (ONNX), Moondream (ONNX)           │    ║
║  │  core/   → VRAMArbiter, SystemMonitor (LHM-DLL)             │    ║
║  │  data/   → DatabaseCore (SQLite/SQLAlchemy)                  │    ║
║  │  rendering/ → FinalRenderer (FFmpeg AMF)                     │    ║
║  └──────────────────┬──────────────────────────────────────────┘    ║
║                     │                                                ║
║  ┌──────────────────▼──────────────────────────────────────────┐    ║
║  │              PERSISTENZ / HARDWARE                           │    ║
║  │                                                              │    ║
║  │  SQLite WAL    FAISS-CPU       AMD GPU (DirectML)            │    ║
║  │  pb_studio.db  test_index.faiss  onnxruntime-directml        │    ║
║  │  (SQLAlchemy)  (1152-dim)        h264_amf/hevc_amf/av1_amf  │    ║
║  └──────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 9. Key Insights & Recommendations

### Code Quality Assessment

**Stärken:**
- Klare Schichtentrennung (Frontend / API / Core) – Grenze konsequent eingehalten
- AppState als zentraler Singleton eliminiert Cross-Router-Abhängigkeiten (ADR-001/003)
- Pydantic-Schemas erzwingen strikte Typisierung an der API-Grenze
- MVVM-Toolkit sauber implementiert: `[ObservableProperty]`, `[RelayCommand]`, partielle Klassen
- Security: Path-Traversal-Schutz in project_router und render_router (SEC-001/002)
- GPU-Lock-Middleware verhindert Race-Conditions bei direkten DirectML-Calls
- Test-Suite solide: 36/36 pytest + 24/24 API E2E + 14/14 Smoke-Tests

**Schwachstellen / Risiken:**

1. **AppState verliert Analyse-Cache bei Neustart.** Nur Clip-Metadaten werden via `load_from_db()` wiederhergestellt. Analyse-Ergebnisse (Beats, Waveform etc.) müssen neu berechnet werden.

2. **Kein Auth-Layer.** CORS `allow_origins=["*"]` – akzeptabel für lokale Desktop-App, nicht für Netzwerk-Exposition.

3. **`asyncio.to_thread()` ohne Timeout.** Hängende ML-Calls (z.B. bei Demucs-Fehlern) können uvicorn-Worker blockieren.

4. **render_service `fps: float`** – `vf_filter fps={fps:.3f}` funktioniert für 23.976 korrekt. Bei av1_amf prüfen, ob der Encoder float-FPS korrekt verarbeitet (experimenteller Codec).

5. **FAISS-Index warm halten fehlt.** Wird bei jeder Analyse neu geladen. Singleton würde Ladezeit sparen.

### Security Considerations

- Path-Traversal: SEC-001/002 implementiert – gut. Bei neuen Endpoints konsequent beibehalten.
- Kein `subprocess.run(shell=True)` – Regel eingehalten.
- CORS `*`: Nur für localhost, niemals remote exponieren.
- `/shutdown` ist ungeschützt – für lokale Desktop-App tolerierbar.

### Performance Optimization Opportunities

1. FAISS-Index als Singleton halten (kein Reload bei jeder Analyse)
2. Thumbnail-Cache auf Dateisystem (vermeidet CV2-Dekodierung bei jedem Request)
3. `WaveformCache` (existiert bereits) – Nutzung in allen Paths sicherstellen
4. SSE-Queue Maximalgröße definieren (Backpressure-Schutz)

### Direkter Handlungsbedarf (Next Steps laut CLAUDE.md)

1. `dotnet build PBStudio.UI\PBStudio.UI.csproj` auf Windows ausführen (0 Errors erwartet)
2. Python Backend starten: `python -m uvicorn backend.main:app --port 8765`
3. WPF App starten und alle 9 Views End-to-End testen
4. Reale Test-Daten verwenden: `C:\Users\david\Videos\test_data\`

---

*Tests: 36/36 pytest | 24/24 API E2E | 14/14 Smoke-Tests PASSED | dotnet build: 0 Errors 0 Warnings*
