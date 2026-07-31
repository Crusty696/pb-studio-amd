# System Design: PB Studio AMD – C# WPF + Python FastAPI Hybrid

**Datum:** 2026-03-04
**Status:** SUPERSEDED – historischer Migrationsentwurf vom 2026-03-04.
FastAPI-Backend und C#-WPF-Frontend sind inzwischen implementiert; WPF ist der
aktive Produktpfad. Aktuelle Verträge stehen in ADR-002/ADR-003, den
projektspezifischen Agent-Referenzen und den T311-T329-Reparaturbelegen.
**Verantwortlich:** Claude (Opus 4.6)

---

## Aktueller Architekturvertrag

- WPF (.NET 9) kommuniziert über REST/SSE ausschließlich mit
  `127.0.0.1:8765`.
- Python 3.11.x und NumPy 1.26.4 sind fest.
- ONNX-ML nutzt nur `DmlExecutionProvider`; `enable_mem_pattern=False` und
  `enable_cpu_mem_arena=False` sind gemeinsam Pflicht. Kein CPU-Fallback.
- Rendering nutzt ausschließlich `h264_amf`, `hevc_amf` oder `av1_amf` und
  schlägt ohne AMF geschlossen fehl.
- SigLIP liefert 1152-dimensionale ONNX-Embeddings. CLAP-Semantik ist nur mit
  registriertem CLAP-ONNX-Modell verfügbar und sonst explizit `unavailable`.
- Modellquelle, Transformation, Lizenzkette und Release-Hash sind ausschließlich
  in [`config/directml-model-assets.json`](../config/directml-model-assets.json)
  und [`config/directml-asset-bundle.json`](../config/directml-asset-bundle.json)
  autoritativ.
- Medien werden als lokale Projektkatalog-Einträge importiert und über
  registrierte Clip-IDs an Timeline/Preview/Render gebunden.

Alle folgenden Plan-, Bestands- und Implementierungsangaben sind historische
Migrationsdokumentation und dürfen nicht als aktuelle Betriebsanleitung
verwendet werden.

---

## 1. Problemstellung

PB Studio AMD ist eine PyQt6/Python-Desktop-App für musiksynchrone Video-Produktion.
Die App soll in eine **C# WPF + Python FastAPI Hybrid-Architektur** migriert werden.

### IST-Zustand (AMD Version)

| Kennzahl | Wert |
|----------|------|
| Python-Module | 139 Dateien |
| Code-Zeilen | ~32.460 |
| UI-Widgets (PyQt6) | 40 Dateien |
| GPU-Stack | AMD DirectML via `onnxruntime-directml` |
| Hardware-Encoder | FFmpeg AMF (h264_amf, hevc_amf) |
| Datenbanken | SQLite (SQLAlchemy) + FAISS-CPU |
| Python-Version | 3.11.x (BeatNet/madmom Kompatibilität) |
| NumPy | 1.26.4 (< 2.0, fest) |

### Unterschiede zur NVIDIA-Version

| Aspekt | NVIDIA | AMD |
|--------|--------|-----|
| GPU-Inference | CUDA + torch.cuda | DirectML + ONNX Runtime |
| Video-Encoder | NVENC (hevc_nvenc) | AMF (hevc_amf) |
| Embeddings | CLIP 512-dim + CLAP | SigLIP 1152-dim + registriertes CLAP-ONNX |
| Vector Store | ChromaDB | FAISS-CPU |
| Vision LLM | Moondream (PyTorch) | Moondream ONNX (FP16 DirectML) |
| Motion | RAFT (PyTorch CUDA) | RAFT ONNX (Opset 17 DirectML) |
| GPU-Monitoring | pynvml | LibreHardwareMonitorLib (pythonnet) |
| Beat Detection | BeatNet CPU + beat_this CUDA | BeatNet CPU only |

---

## 2. Ziel-Architektur

```
┌─────────────────────────────────────────────────────┐
│                  C# WPF (.NET 9.0)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Views/   │  │ViewModels│  │   Services/      │  │
│  │  XAML     │◄─┤  MVVM    │◄─┤   ApiClient.cs   │  │
│  └──────────┘  └──────────┘  │   SSEClient.cs   │  │
│                               │   PythonBridge.cs│  │
│                               └────────┬─────────┘  │
└────────────────────────────────────────┼────────────┘
                                         │ HTTP REST + SSE
                                         │ localhost:8765
┌────────────────────────────────────────┼────────────┐
│              Python FastAPI Backend                   │
│  ┌─────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ Routers │──│  Schemas   │──│ Core Logic       │  │
│  │         │  │ (Pydantic) │  │ (UNVERÄNDERT)    │  │
│  └─────────┘  └────────────┘  │ audio/, video/,  │  │
│                                │ pacing/, data/,  │  │
│                                │ rendering/, ai/  │  │
│                                │ services/, core/ │  │
│                                └──────────────────┘  │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ SQLite   │  │ FAISS-CPU│  │ DirectML/ONNX    │   │
│  │(SQLAlch.)│  │ Vectors  │  │ GPU Sessions     │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### Begründung

- Python-Backend **zu komplex** für C#-Neuschreibung (ML/AI Stack mit ONNX, librosa, BeatNet)
- PyQt6 UI wird **vollständig ersetzt** durch C# WPF (bessere Windows-Integration)
- FastAPI als **lokaler HTTP-Server** (localhost:8765) = saubere Prozess-Trennung
- SSE für **Echtzeit-Progress** (Stem-Separation, Rendering, Analyse)

### Verworfene Alternativen

| Alternative | Grund der Ablehnung |
|-------------|---------------------|
| pythonnet | Instabil mit ONNX Runtime + DirectML Sessions |
| Named Pipes | Mehr Komplexität, schwerer debugbar als HTTP |
| gRPC | Overkill für lokale Kommunikation, proto-Dateien Overhead |
| WebSocket | SSE reicht (nur Server→Client Streams), einfacher |
| Electron/MAUI | Weder native noch performant genug für GPU-Workloads |

---

## 3. Komponentendiagramm (detailliert)

### 3.1 C# WPF Frontend

```
PBStudio.UI/
├── App.xaml(.cs)                    # Startup, DI Container
├── MainWindow.xaml(.cs)             # Shell mit TabControl
├── Views/
│   ├── MediaIngestView.xaml         # Audio/Video Import (getrennt)
│   ├── AudioLibraryView.xaml        # Audio-Bibliothek + Waveform
│   ├── VideoLibraryView.xaml        # Video-Bibliothek + Thumbnails
│   ├── AnchorView.xaml              # Anchor-Punkte Bearbeitung
│   ├── DirectorView.xaml            # Smart Director / Pacing
│   ├── TimelineView.xaml            # Timeline-Vorschau
│   ├── ProductionView.xaml          # Rendering + Export
│   └── SettingsView.xaml            # GPU-Status, Cache, Einstellungen
├── ViewModels/
│   ├── MainViewModel.cs             # Tab-Navigation, App-State
│   ├── MediaIngestViewModel.cs      # Import-Logik
│   ├── AudioLibraryViewModel.cs     # Audio-Liste, Analyse-Trigger
│   ├── VideoLibraryViewModel.cs     # Video-Liste, Thumbnails
│   ├── AnchorViewModel.cs           # Beat-Marker, Anchor-Edit
│   ├── DirectorViewModel.cs         # Pacing-Config, Cut-List
│   ├── TimelineViewModel.cs         # Timeline-Preview
│   ├── ProductionViewModel.cs       # Render-Start, Progress
│   └── SettingsViewModel.cs         # Config Read/Write
├── Services/
│   ├── PythonBridgeService.cs       # Python-Prozess Lifecycle
│   ├── ApiClient.cs                 # HTTP REST Client (typed)
│   ├── SSEClient.cs                 # Server-Sent Events Listener
│   ├── ProjectService.cs            # Projekt CRUD
│   └── NavigationService.cs         # View-Navigation
└── Models/
    ├── AudioClip.cs                 # Spiegelt audio_schemas.py
    ├── VideoClip.cs                 # Spiegelt video_schemas.py
    ├── TimelineEntry.cs             # Spiegelt pacing_schemas.py
    └── RenderConfig.cs              # Spiegelt render_schemas.py
```

**Technologie-Stack (C#):**

| Paket | Version | Zweck |
|-------|---------|-------|
| .NET | 9.0 | Target Framework |
| CommunityToolkit.Mvvm | ≥8.3 | MVVM ([ObservableProperty], [RelayCommand]) |
| MaterialDesignThemes.Wpf | ≥5.0 | Material Design UI |
| MahApps.Metro.IconPacks.Material | ≥5.0 | Material Icons |
| Microsoft.Xaml.Behaviors.Wpf | ≥1.1 | Event-To-Command |
| System.Net.Http | built-in | HTTP Client |
| Microsoft.Extensions.DI | ≥9.0 | Dependency Injection |

### 3.2 Python FastAPI Backend (historischer Plan)

```
backend/    # historischer Zielbaum; inzwischen implementiert
├── main.py                          # FastAPI App, Startup/Shutdown
├── config.py                        # Server-Konfiguration (Port, Paths)
├── dependencies.py                  # Shared Dependencies (DB, GPU Lock)
├── routers/
│   ├── health_router.py             # GET /health, GET /gpu/status
│   ├── project_router.py            # CRUD /project/*
│   ├── audio_router.py              # /audio/analyze, /audio/beats, /audio/stems
│   ├── video_router.py              # /video/import, /video/analyze, /video/clips
│   ├── pacing_router.py             # /pacing/generate, /pacing/timeline
│   ├── render_router.py             # /render/start, /render/status, /render/cancel
│   └── events_router.py             # SSE /events/progress, /events/log
├── schemas/
│   ├── common.py                    # StatusResponse, ErrorResponse
│   ├── project_schemas.py           # ProjectCreate, ProjectInfo
│   ├── audio_schemas.py             # AudioAnalysisRequest/Response
│   ├── video_schemas.py             # VideoImportRequest, ClipInfo
│   ├── pacing_schemas.py            # PacingConfig, CutListResponse
│   └── render_schemas.py            # RenderRequest, RenderProgress
└── middleware/
    └── gpu_lock.py                  # GPU-Zugriff serialisieren (1 ONNX Session)
```

**Wichtig:** Der `backend/` Ordner importiert direkt aus `src/pb_studio/`.
Kein Code wird kopiert — nur gewrappt.

### 3.3 Python Core (UNVERÄNDERT)

```
src/pb_studio/
├── config_manager.py        # Singleton Config
├── core/                    # VRAM Arbiter, Task Queue, System Monitor (9 Module)
│   ├── vram_arbiter.py      # GPU Memory Management (DirectML)
│   ├── vram_budget_manager.py # VRAM Budget Tracking
│   ├── task_queue.py        # Async Task Queue
│   ├── thread_pool.py       # Thread Pool Management
│   ├── system_monitor.py    # LibreHardwareMonitor Integration
│   ├── model_loader.py      # ONNX Model Loading/Caching
│   ├── worker_signals.py    # Worker Signal Definitions
│   └── crash_handler.py     # Exception Handling
├── workers/                 # Worker Orchestrierung (5 Module)
│   ├── base_worker.py       # Basis-Worker Klasse
│   ├── orchestrator.py      # Task-Orchestrierung
│   ├── registry_setup.py    # Worker-Registry Init
│   └── worker_registry.py   # Worker-Verwaltung
├── audio/                   # 12 Module: BeatNet, Demucs, Spectral, etc.
├── video/                   # 11 Module: Moondream, RAFT, SceneDetect, etc.
├── pacing/                  # 12 Module: AdvancedPacingEngine, ClipSelector, etc.
├── rendering/               # 6 Module: RenderEngine, BatchRenderer, ProxyService
├── ai/                      # 6 Module: SigLIP, Moondream, SmartDirector
├── data/                    # 4 Module: SQLite, FAISS, Repositories
├── services/                # 5 Module: AudioService, PacingService, etc.
├── utils/                   # 4 Module: PathHelpers, CacheManager, Profiling
└── models/                  # 3 Module: Audio, Video, Timeline Dataclasses
```

---

## 4. Datenfluss

### 4.1 Audio-Import + Analyse

```
User klickt "Audio importieren" in C# WPF
    │
    ▼
AudioLibraryViewModel.ImportAudioCommand()
    │
    ▼ POST /audio/analyze { path: "C:/Users/.../song.mp3" }
    │
    ▼
audio_router.py → AudioAnalyzer.analyze()
    │ (async, via asyncio.to_thread)
    │
    ├── BeatNet → Beat-Detection (CPU)
    ├── librosa → Spectral Analysis
    ├── SpectralAnalyzer → 8-Band Analyse
    ├── StructureAnalyzer → Verse/Chorus/Drop
    └── WaveformAnalyzer → Waveform Data
    │
    ▼ SSE /events/progress { step: "beats", percent: 45 }
    │
    ▼
SSEClient.cs → AudioLibraryViewModel.OnProgressUpdate()
    │
    ▼ UI Update (ProgressBar, Status Text)
```

### 4.2 Video-Rendering

```
User klickt "Rendering starten" in C# WPF
    │
    ▼
ProductionViewModel.StartRenderCommand()
    │
    ▼ POST /render/start { timeline: [...], audio: "...", quality: "high" }
    │
    ▼
render_router.py → Background Task gestartet
    │
    ├── RenderService.render_timeline()
    │   ├── Normalisierung (AMF Transcoding)
    │   ├── Concat-File erstellen
    │   └── FFmpeg AMF Rendering (hevc_amf)
    │
    ▼ SSE /events/progress { phase: "rendering", percent: 72, time: "02:15/03:00" }
    │
    ▼
SSEClient.cs → ProductionViewModel.OnRenderProgress()
    │
    ▼ UI Update (Render-Progress, ETA)
```

---

## 5. API-Vertrag (REST Endpoints)

### 5.1 Health & System

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/health` | GET | - | `{ status, uptime, gpu_available }` |
| `/gpu/status` | GET | - | `{ name, vram_total, vram_used, temperature, driver }` |
| `/gpu/cleanup` | POST | - | `{ freed_mb }` |

### 5.2 Project

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/project/create` | POST | `{ name, path }` | `ProjectInfo` |
| `/project/open` | POST | `{ path }` | `ProjectInfo` |
| `/project/save` | POST | - | `{ success }` |
| `/project/close` | POST | - | `{ success }` |
| `/project/info` | GET | - | `ProjectInfo` |

### 5.3 Audio

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/audio/import` | POST | `{ path }` | `AudioClipInfo` |
| `/audio/analyze` | POST | `{ clip_id }` | `AudioAnalysisResult` |
| `/audio/beats/{id}` | GET | - | `BeatData[]` |
| `/audio/waveform/{id}` | GET | `?bands=3` | `WaveformData` |
| `/audio/stems/separate` | POST | `{ clip_id, model }` | `StemResult` |
| `/audio/structure/{id}` | GET | - | `StructureSegment[]` |
| `/audio/spectral/{id}` | GET | - | `SpectralData` |

### 5.4 Video

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/video/import` | POST | `{ paths[] }` | `VideoClipInfo[]` |
| `/video/clips` | GET | `?page&limit` | `VideoClipInfo[]` |
| `/video/thumbnails/{id}` | GET | - | `base64 JPEG` |
| `/video/analyze` | POST | `{ clip_id }` | `VideoAnalysisResult` |
| `/video/scenes/{id}` | GET | - | `SceneInfo[]` |
| `/video/motion/{id}` | GET | - | `MotionData` |

### 5.5 Pacing

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/pacing/generate` | POST | `PacingConfig` | `CutListEntry[]` |
| `/pacing/timeline` | GET | - | `TimelineEntry[]` |
| `/pacing/preview` | POST | `{ start_sec, duration }` | `{ preview_path }` |

### 5.6 Render

| Endpoint | Methode | Request | Response |
|----------|---------|---------|----------|
| `/render/start` | POST | `RenderRequest` | `{ task_id }` |
| `/render/status/{id}` | GET | - | `RenderProgress` |
| `/render/cancel/{id}` | POST | - | `{ cancelled }` |

### 5.7 Events (SSE)

| Endpoint | Event-Typen |
|----------|-------------|
| `/events/progress` | `analysis_progress, render_progress, stem_progress, import_progress` |
| `/events/log` | `info, warning, error` |
| `/events/gpu` | `vram_update, temperature_update` |

---

## 6. GPU-Management (AMD DirectML)

### Constraint: Nur 1 ONNX Session gleichzeitig

AMD DirectML erlaubt **keine parallelen ONNX Runtime Sessions** ohne Memory-Konflikte.
Das erfordert einen strikten GPU-Lock:

```python
# backend/middleware/gpu_lock.py
import asyncio

gpu_lock = asyncio.Lock()

async def with_gpu_lock(func, *args):
    async with gpu_lock:
        return await asyncio.to_thread(func, *args)
```

### GPU-Nutzung nach Modul

| Modul | GPU (DirectML) | CPU | Anmerkung |
|-------|---------------|-----|-----------|
| Moondream ONNX | Ja | Nein | Vision-Language Model; fail closed |
| RAFT ONNX | Ja | Nein | Optical Flow |
| SigLIP ONNX | Ja | Nein | Video Embeddings; fail closed |
| Demucs/htdemucs (PyTorch) | Nein | Ja | Stem Separation; freigegebene CPU-Ausnahme |
| UVR-MDX-NET (ONNX) | Ja | Nein | Stem Separation via DirectML; fail closed |
| BeatNet | Nein | Ja | Immer CPU (AMD Constraint) |
| FFmpeg AMF | Ja (HW Encoder) | Nein | Video Rendering; AMF-only |
| FAISS | Nein | Ja | Vector Search |
| librosa | Nein | Ja | Audio Features |

### ONNX Session Config (AMD PFLICHT)

```python
import onnxruntime as ort

session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False  # MANDATORY für DirectML
session_options.enable_cpu_mem_arena = False
providers = ["DmlExecutionProvider"]
```

---

## 7. Skalierung & Zuverlässigkeit

### 7.1 Last-Schätzung

| Szenario | Gleichzeitige Requests | Latenz-Budget |
|----------|----------------------|---------------|
| Import 50 Clips | 1 (seriell, DB-Write) | <500ms/Clip |
| Audio-Analyse | 1 (GPU Lock) | 30-120s |
| Video-Analyse | 1 (GPU Lock) | 10-60s/Clip |
| Pacing-Generierung | 1 (CPU-bound) | 5-30s |
| Rendering | 1 (FFmpeg + AMF) | Minuten-Bereich |

Dies ist eine **Single-User Desktop-App** — keine Skalierung auf mehrere User nötig.
Der Engpass ist die GPU (1 Session = 1 Task).

### 7.2 Fehlerbehandlung

```
C# WPF                          Python FastAPI
   │                                  │
   ├─ HTTP Timeout (30s default) ─────┤
   │  → Retry 1x, dann Error-Dialog  │
   │                                  │
   ├─ Server nicht erreichbar ────────┤
   │  → PythonBridge Restart          │
   │  → /health Check (max 3x)       │
   │                                  │
   ├─ GPU OOM ────────────────────────┤
   │  → Python fängt OOM ab           │
   │  → HTTP 503 + { error: "OOM" }  │
   │  → C# zeigt Warnung             │
   │  → KEIN CPU-Fallback (Regel!)   │
   │                                  │
   └─ Python Crash ───────────────────┤
      → crash_handler.py loggt        │
      → PythonBridge erkennt Exit     │
      → Auto-Restart + Recovery       │
```

### 7.3 Prozess-Lifecycle

```
launch.ps1
    │
    ├─ Startet Python: python.exe backend/main.py
    │   └─ Wartet auf /health (max 30s, Polling 500ms)
    │
    ├─ Startet C# WPF: PBStudio.UI.exe
    │   └─ PythonBridgeService prüft /health
    │
    └─ Bei C# App Close:
        ├─ POST /shutdown (Graceful)
        ├─ Warte 5s
        └─ Kill Python-Prozess (Fallback)
```

---

## 8. Trade-Off-Analyse

### Entscheidung 1: HTTP REST vs. Named Pipes

| Kriterium | HTTP REST | Named Pipes |
|-----------|-----------|-------------|
| Debugging | Postman, Browser DevTools | Schwer |
| Latenz | ~1-5ms lokal | ~0.1ms |
| Serialisierung | JSON (Standard) | Custom |
| Streaming | SSE (einfach) | Möglich |
| Komplexität | Niedrig | Mittel |

**Entscheidung:** HTTP REST. Latenz ist für Desktop-App irrelevant (kein ms-kritisches Trading). Debugging-Vorteile überwiegen.

### Entscheidung 2: SSE vs. WebSocket vs. Polling

| Kriterium | SSE | WebSocket | Polling |
|-----------|-----|-----------|---------|
| Richtung | Server→Client | Bidirektional | Client→Server |
| Komplexität | Niedrig | Mittel | Niedrig |
| Reconnect | Automatisch | Manuell | N/A |
| Eignung | Progress Updates | Chat/Realtime | Selten |

**Entscheidung:** SSE. Wir brauchen nur Server→Client (Progress, Logs). Kein bidirektionaler Stream nötig.

### Entscheidung 3: MaterialDesign vs. Fluent UI vs. Custom

| Kriterium | MaterialDesign | Fluent UI | Custom |
|-----------|---------------|-----------|--------|
| WPF Support | Exzellent | Begrenzt | Aufwändig |
| Dark Mode | Built-in | Built-in | Manuell |
| Icons | MahApps.Metro.IconPacks | Segoe MDL2 | Manuell |
| Community | Groß | Klein (WPF) | Keine |

**Entscheidung:** MaterialDesignThemes.Wpf. Beste WPF-Integration, großes Icon-Set, bewährtes Dark/Light Theme.

---

## 9. Implementierungsreihenfolge (AMD-spezifisch)

### Phase 1: FastAPI Fundament (Backend)
- `backend/main.py` mit Uvicorn (Port 8765)
- `/health`, `/gpu/status` Endpoints
- Pydantic Schemas (`common.py`)
- GPU-Lock Middleware

### Phase 2: Project + Audio Router
- `/project/*` CRUD Endpoints
- `/audio/import`, `/audio/analyze`, `/audio/beats`
- SSE Progress für Audio-Analyse

### Phase 3: Video + Pacing Router
- `/video/import`, `/video/analyze`, `/video/clips`
- `/pacing/generate`, `/pacing/timeline`
- Thumbnail-Streaming (Base64 JPEG)

### Phase 4: Render Router
- `/render/start`, `/render/status`, `/render/cancel`
- AMF Hardware-Encoding Integration
- SSE Render-Progress (Echtzeit)

### Phase 5: C# WPF Shell
- .NET 9.0 Projekt mit MVVM Toolkit
- PythonBridgeService (Prozess-Management)
- ApiClient (typed HTTP Client)
- SSEClient (EventSource Pattern)
- MainWindow mit TabControl

### Phase 6: C# Views
- MediaIngestView (Audio/Video getrennt)
- AudioLibraryView + VideoLibraryView
- AnchorView (Beat-Marker Editor)
- DirectorView (Pacing Config)
- TimelineView (Preview Player)
- ProductionView (Render Export)
- SettingsView (GPU, Cache)

### Phase 7: Launcher + Installer
- PowerShell Launch-Script
- Python venv Auto-Setup
- Optional: Inno Setup Installer

---

## 10. Bekannte Probleme im IST-Zustand

1. **smart_director.py Duplikation:** Existiert in `pacing/smart_director.py` (542 Zeilen)
   UND `ai/smart_director.py` (1354 Zeilen) mit unterschiedlichen Implementierungen.
   → Muss vor Migration konsolidiert werden (ai/ Version ist kanonisch).

2. **workers/ Modul:** 5 Dateien mit Orchestrierung-Logik, die bei der
   FastAPI-Migration in Background Tasks überführt werden müssen.

3. **PyQt6 UI (40 Dateien):** Wird komplett durch C# WPF ersetzt.
   Die bestehenden PyQt6-Widgets dienen als Spezifikation für die C#-Views.

---

## 11. Offene Punkte / Risiken

| Risiko | Schwere | Mitigation |
|--------|---------|------------|
| DirectML Session-Konflikte bei Parallel-Requests | Hoch | GPU Lock (asyncio.Lock) |
| Python-Prozess Crash bei langem Rendering | Mittel | Auto-Restart + State Recovery |
| VRAM-Engpass bei großen ONNX-Modellen | Mittel | VRAM Arbiter + Session Cleanup |
| C# WPF Lernkurve (Team kennt PyQt6) | Niedrig | MVVM Toolkit vereinfacht vieles |
| FFmpeg AMF nicht auf allen AMD-GPUs verfügbar | Hoch | Vor Renderstart explizit `unavailable`; kein Software-Fallback |

---

## 12. Was bei Wachstum überarbeitet werden sollte

- **Multi-GPU:** Aktuell nur 1 GPU angenommen. Bei 2+ GPUs: DML Device Index Routing.
- **Batch-Processing:** Queue mit Priority (Render > Analyse > Import).
- **Plugin-System:** FastAPI Router als Plugins für 3rd-Party-Erweiterungen.
- **Remote Backend:** Falls Python auf anderem Rechner läuft: API-Key Auth + HTTPS.
