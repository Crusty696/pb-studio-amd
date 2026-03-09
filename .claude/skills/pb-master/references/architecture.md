# PB Studio — Architektur-Referenz

## Projektpfad
`C:\Users\david\Dokumente\Pb_studio_AMD_version`

## Schichten-Modell

```
┌─────────────────────────────────────────────────────────┐
│                C# WPF (.NET 9.0)                        │
│  Views (XAML) ←→ ViewModels (MVVM Toolkit) ←→ Services  │
│  PBStudio.UI/Views/    PBStudio.UI/ViewModels/          │
│  PBStudio.UI/Services/ (ApiClient, SSEClient, Bridge)   │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP REST + SSE
                            │ localhost:8765
┌───────────────────────────┴─────────────────────────────┐
│              Python FastAPI Backend                      │
│  backend/routers/    → Endpoints pro Domäne             │
│  backend/schemas/    → Pydantic In/Out                  │
│  backend/middleware/  → GPU-Lock                        │
│  backend/app_state.py → Singleton State                 │
└───────────────────────────┬─────────────────────────────┘
                            │ direkte Python-Imports
┌───────────────────────────┴─────────────────────────────┐
│              Core Logic (UNVERÄNDERT)                    │
│  src/pb_studio/                                         │
│  ├── ai/          (SigLIP, Moondream, SmartDirector)    │
│  ├── audio/       (Separator, BeatDetect, Spectral)     │
│  ├── video/       (RAFT, SceneDetect, FrameExtract)     │
│  ├── core/        (VRAM, TaskQueue, ThreadPool)          │
│  ├── data/        (SQLite, FAISS, Repositories)         │
│  ├── pacing/      (PacingEngine, ClipSelector, Mood)    │
│  ├── rendering/   (FFmpeg AMF, Preview, Final)          │
│  ├── services/    (Audio, Video, Media, Pacing, Gen.)   │
│  ├── workers/     (Orchestrator, Registry)              │
│  ├── models/      (Daten-Modelle)                       │
│  └── utils/       (Cache, Logging, Paths, Profiling)    │
└─────────────────────────────────────────────────────────┘
```

## AMD GPU-Stack

| Komponente | Technologie |
|-----------|-------------|
| ML-Inference | `onnxruntime-directml` |
| Video-Encoder | FFmpeg AMF (`h264_amf`, `hevc_amf`) |
| Embeddings | SigLIP ONNX (1152-dim) |
| Vision LLM | Moondream ONNX FP16 |
| Optical Flow | RAFT ONNX (Opset 17) |
| Vector Store | FAISS-CPU |
| Beat Detection | BeatNet CPU only |
| GPU-Monitoring | LibreHardwareMonitor (pythonnet) |

## Kommunikationspfade

### C# → Python (REST)
```
ApiClient.cs → HTTP POST/GET → FastAPI Router → Service → Core Logic
```

### Python → C# (SSE)
```
Core Logic → Service → SSE Event → SSEClient.cs → ViewModel → UI Update
```

### GPU-Zugriff
```
Router → gpu_lock Middleware → VramArbiter → DirectML Session → ONNX Runtime
```

## C# Frontend (PBStudio.UI/)

### NuGet-Packages
- CommunityToolkit.Mvvm (MVVM-Toolkit)
- MaterialDesignThemes.Wpf (Styling)
- MahApps.Metro.IconPacks.Material (Icons)
- Microsoft.Xaml.Behaviors.Wpf (Behaviors)
- Microsoft.Extensions.DependencyInjection

### Views ↔ ViewModels Mapping
| View | ViewModel | Funktion |
|------|-----------|----------|
| MediaIngestView | MediaIngestViewModel | Audio/Video Import |
| AudioLibraryView | AudioLibraryViewModel | Audio-Bibliothek |
| VideoLibraryView | VideoLibraryViewModel | Video-Bibliothek |
| AnchorView | AnchorViewModel | Beat-Anchor Editing |
| DirectorView | DirectorViewModel | Smart Director / Pacing |
| TimelineView | TimelineViewModel | Timeline-Vorschau |
| ProductionView | ProductionViewModel | Rendering + Export |
| SettingsView | SettingsViewModel | GPU-Status, Einstellungen |

### Services
| Service | Aufgabe |
|---------|---------|
| ApiClient.cs | HTTP-Kommunikation mit Python Backend |
| SSEClient.cs | Server-Sent Events Empfang |
| PythonBridgeService.cs | Python-Prozess starten/stoppen |
| NavigationService.cs | Tab-Navigation |
| ProjectService.cs | Projekt laden/speichern |

## FastAPI Backend (backend/)

### Router → Endpoints
| Router | Prefix | Kern-Endpunkte |
|--------|--------|----------------|
| audio_router | /api/audio | analyze, separate, beats, waveform |
| video_router | /api/video | analyze, scenes, embeddings, thumbnails |
| pacing_router | /api/pacing | generate, preview, export |
| render_router | /api/render | start, status, cancel |
| project_router | /api/project | load, save, list |
| events_router | /api/events | SSE stream |

### Schemas (Pydantic)
Jeder Router hat ein zugehöriges Schema-Modul in `backend/schemas/`.

## Geschützte Bereiche

| Datei | Status | Grund |
|-------|--------|-------|
| `src/pb_studio/audio/separator.py` | LOCKED | Stem-Separation Config ist fein-kalibriert |
| Gesamter `src/pb_studio/` Ordner | READONLY bei Migration | Core-Logik bleibt unverändert |
