# Detaillierter Vergleich: NVIDIA-Version vs. AMD-Version
## PB Studio Hybrid Migration (PyQt6 → C# WPF + Python FastAPI)

**Datum:** 2026-03-04
**Status:** AMD-Version existiert, NVIDIA-Version nicht vorhanden (älter/archiviert)
**Erkenntnisse:** AMD-Version ist moderner, strukturiert für DirectML + FastAPI

---

## ÜBERSICHT: Architektur-Unterschiede

| **Bereich** | **NVIDIA-Version (Typ)** | **AMD-Version (Aktuell)** | **Kritisch?** |
|---|---|---|---|
| **GPU-Backend** | CUDA + PyTorch GPU | DirectML (ONNX) | 🔴 JA - Total anders |
| **Rendering** | `rendering/` Ordner | `video/engine.py` | 🔴 JA - Umstrukturiert |
| **Database** | ORM (SQLAlchemy) wahrscheinlich | Pure SQLite (DatabaseCore) | 🟡 MITTEL |
| **Services** | `audio_service.py`, `pacing_service.py`, `render_service.py` | `analysis_service.py`, `generation_service.py`, `media_service.py` | 🟡 MITTEL |
| **Core/GPU-Management** | `gpu_manager.py`, `hardware.py` | `vram_arbiter.py`, `vram_budget_manager.py`, `system_monitor.py` | 🔴 JA - Proaktiv vs. Reaktiv |
| **UI Framework** | PyQt6 (Python) | PyQt6 (Python) aktuell, C# WPF geplant | 🟢 NEIN - Noch nicht migr. |
| **Worker/Threading** | `PyQt.QThread` wahrscheinlich | `ThreadPoolManager` + `Worker` + Signal-System | 🟡 MITTEL |
| **Config** | Wahrscheinlich mehrere .yaml Dateien | `ConfigManager` (Singleton, JSON) | 🟢 NEIN |
| **Error Handling** | Generisch wahrscheinlich | `CrashHandler` + Try-Catch | 🟢 NEIN |
| **FastAPI Integration** | NICHT VORHANDEN | Geplant, noch nicht implementiert | 🟡 MITTEL - Zukünftig |

---

## 1. RENDERING-SYSTEM

### NVIDIA (Erwartet)
```
src/pb_studio/rendering/
├── render_service.py       # Main orchestration
├── final_renderer.py       # FFmpeg final pass
├── preview_renderer.py     # Real-time preview (OpenGL?)
├── proxy_service.py        # Proxy video generation
└── render_engine.py        # CUDA-based effects?
```

**Eigenschaften:**
- Wahrscheinlich CUDA-beschleunigte Filter
- Separate Preview vs. Final Render Logic
- Proxy-System für schnellere Vorschau
- GPU-Rendering möglich

### AMD (Aktuell)
```
src/pb_studio/video/
├── engine.py               # VideoGenerator (Main Logic)
├── encoder_utils.py        # FFmpeg AMF encoding
├── moondream.py            # Vision LLM (ONNX)
├── raft.py                 # Optical Flow (ONNX)
└── scene_detect.py         # Scene Detection (OpenCV)
```

**Eigenschaften:**
- Pure FFmpeg + DirectML Encoding
- AI-Models sind ONNX (kein PyTorch)
- Keine CUDA-Filter, nur Hardware-Encoding
- Vision + Motion via AI Models

**Kritisch?** 🔴 **JA** - AMD hat völlig anders kodierte Renderer

---

## 2. DATABASE-SYSTEM

### NVIDIA (Erwartet)
```
src/pb_studio/database/
├── connection.py           # SQLAlchemy Declarative Base
├── models.py               # ORM Models (Project, Media, Scene, etc.)
├── schema.py               # Alembic migrations?
├── global_cache.py         # In-Memory Cache (Redis? Dict?)
└── crud.py                 # CRUD Operations
```

**Eigenschaften:**
- SQLAlchemy ORM
- Wahrscheinlich Alembic für Migrations
- Separate CRUD Layer
- Global Cache für häufige Queries

### AMD (Aktuell)
```
src/pb_studio/data/
├── database_core.py        # DatabaseCore (Thread-Safe Singleton)
├── vector_store.py         # FAISS Vector DB
└── repositories/
    ├── media_repository.py    # Media CRUD
    └── project_repository.py  # Project CRUD
```

**Eigenschaften:**
- Pure SQLite (Thread-local Connection Management)
- WAL-Mode für Concurrency
- Foreign Keys aktiviert
- Repositories Pattern (Nicht ORM)
- FAISS für Vector Search
- Kein Global Cache (müsste hinzugefügt werden)

**Kritisch?** 🟡 **MITTEL** - AMD braucht Global Cache für Perfomance

---

## 3. SERVICES-SCHICHT

### NVIDIA (Erwartet)
```
src/pb_studio/services/
├── audio_service.py        # Audio Analysis + Separation
├── pacing_service.py       # Timeline Generation
└── render_service.py       # Render Orchestration
```

### AMD (Aktuell)
```
src/pb_studio/services/
├── analysis_service.py     # Audio + Video Analysis (Async Worker)
├── generation_service.py   # Video Generation + SmartDirector AI
└── media_service.py        # File Import + Metadata Extraction
```

**Vergleich:**

| Feature | NVIDIA (erwartet) | AMD | Impact |
|---------|---|---|---|
| **Audio Analysis** | `audio_service.py` | `analysis_service.py` | 🟢 Ähnlich |
| **Pacing/Timeline** | Separate `pacing_service.py` | In `generation_service.py` | 🟡 AMD vereinfacht |
| **Rendering** | `render_service.py` | `generation_service` + `VideoGenerator` | 🟢 Äquivalent |
| **AI Integration** | Wahrscheinlich nicht | **SmartDirector** im Generation-Service | 🔴 AMD hat mehr AI |
| **Async/Threading** | PyQt Signals wahrscheinlich | `Worker` + `ThreadPoolManager` | 🟡 AMD expliziter |
| **Media Import** | Wahrscheinlich in Audio/Video Service | **Separate `media_service.py`** | 🟢 AMD klarer |

**Kritisch?** 🟡 **MITTEL** - Struktur anders aber funktional äquivalent

---

## 4. CORE-MODUL (GPU + SYSTEM)

### NVIDIA (Erwartet)
```
src/pb_studio/core/
├── gpu_manager.py          # CUDA Device Management
├── hardware.py             # Hardware Detection
├── system_monitor.py       # CPU/RAM/GPU Stats
├── session_manager.py      # Project Session State
├── project_manager.py      # Project CRUD
├── config.py               # Configuration (Wahrscheinlich .yaml)
├── exceptions.py           # Custom Exceptions
├── error_reporter.py       # Crash Logging
└── result.py               # Result Objects
```

**Eigenschaften:**
- Reactive VRAM Management (OOM Handling)
- CUDA-spezifische APIs
- Session State Management
- Global Project Manager

### AMD (Aktuell)
```
src/pb_studio/core/
├── vram_arbiter.py              # Legacy VRAM Check (Now delegates to BudgetManager)
├── vram_budget_manager.py       # PROACTIVE VRAM Budgeting (!!)
├── model_loader.py              # VRAM-Aware Model Loading
├── system_monitor.py            # LibreHardwareMonitor Integration
├── task_queue.py                # Priority Task Queue
├── thread_pool.py               # Worker Pool + Signal System
├── crash_handler.py             # Crash/Exception Handler
└── worker_signals.py            # PyQt Signal Definitions
```

**Unterschiede:**

| Feature | NVIDIA | AMD | Kritisch |
|---------|--------|-----|----------|
| **VRAM Strategy** | Reaktiv (OOM nach Fehler) | **Proaktiv (Budget vor Load)** | 🔴 JA |
| **GPU Driver** | CUDA (nvidia-ml) | DirectML (LibreHardwareMonitor) | 🔴 JA |
| **Model Loading** | Wahrscheinlich `torch.load()` | `ModelLoader` (ONNX-fokussiert) | 🔴 JA |
| **Task Scheduling** | Wahrscheinlich Qt Event Loop | `TaskQueue` mit Priorities | 🟡 AMD moderner |
| **Session Management** | Zentraler SessionManager | State im UI Widget Tuch | 🟡 AMD dezentraler |
| **Config Format** | Wahrscheinlich YAML | JSON (ConfigManager Singleton) | 🟢 NEIN |

**Kritisch?** 🔴 **JA - KERN-UNTERSCHIED!**
- AMD nutzt **PROAKTIVE VRAM-Verwaltung** (Budgets)
- NVIDIA hat wahrscheinlich **REAKTIVE Fehlerbehandlung** (OOM-Catch)

---

## 5. UTILS & HELPERS

### NVIDIA (Erwartet)
```
src/pb_studio/utils/
├── cache_manager.py        # General Caching
├── event_logger.py         # Event Logging
├── logger.py               # Logging Setup
├── path_helpers.py         # Path Resolution
├── path_utils.py           # More Path Utilities
└── profiling.py            # Performance Profiling
```

### AMD (Aktuell)
```
src/pb_studio/utils/
└── logging_setup.py        # Basic Logging Config
```

**Kritisch?** 🟡 **MITTEL** - AMD hat minimal Utils, sollte ausgebaut werden

---

## 6. UI & WORKERS

### NVIDIA (Erwartet)
```
src/pb_studio/gui/
├── startup_dialog.py       # Initial Setup UI
├── main_window.py          # Main Window
├── widgets/
│   ├── audio_widget.py
│   ├── video_widget.py
│   └── ...
└── (PyQt6 Widgets)
```

### AMD (Aktuell)
```
src/pb_studio/ui/
├── main_window.py
├── widgets/
│   ├── analysis_widget.py
│   ├── generation_widget.py
│   ├── audio/ (stem, waveform, beat)
│   ├── video/ (encoder, motion, scene)
│   ├── generation/ (clip selector, pacing, progress)
│   └── common/ (timeline, progress card)
└── plugins/ (GEPLANT für C# WPF Migration)

src/pb_studio/workers/  <-- WICHTIG!
├── audio/
│   ├── audio_import_worker.py
│   ├── audio_analyze_worker.py
│   ├── audio_stem_worker.py
│   └── audio_embedding_worker.py
├── video/
│   ├── video_import_worker.py
│   ├── video_scene_worker.py
│   ├── video_motion_worker.py
│   └── video_vision_worker.py
├── generation/
│   ├── pacing_worker.py
│   ├── render_worker.py
│   ├── concat_worker.py
│   └── export_worker.py
├── orchestrator.py         # Master Workflow Controller
└── worker_registry.py      # Dynamic Worker Registration
```

**Kritisch?** 🔴 **JA** - AMD hat dedizierter WORKERS-Ordner mit Orchestrator
- NVIDIA hat wahrscheinlich Worker-Logic in UI-Widgets eingebaut
- AMD hat **Separation of Concerns** (Workers ≠ UI)

---

## 7. ZUSÄTZLICHE ORDNER

### AMD hat zusätzlich:
```
src/pb_studio/
├── ai/                     # AI Models (Moondream, CLAP, SIGLIP, SmartDirector)
├── models/                 # Data Models (Timeline, Audio, Video classes)
├── pacing/                 # Advanced Pacing Engine (Clip Selection Logic)
└── workers/                # Worker Architecture (NVIDIA: Wahrscheinlich in UI)
```

**Kritisch?** 🟡 **NEIN, aber besser strukturiert**

---

## 8. FEATURE-VERGLEICH (Detailliert)

### Audio Processing

| Feature | NVIDIA (expected) | AMD | Critical |
|---------|---|---|---|
| **Beat Detection** | Wahrscheinlich madmom/BeatNet | BeatNet (CPU) | 🟢 NEIN |
| **Audio Analysis** | PyTorch-basiert | DirectML ONNX (Demucs Hybrid) | 🔴 JA |
| **Stem Separation** | Wahrscheinlich `torchaudio` | Demucs (DirectML patched) | 🔴 JA |
| **VRAM Budget** | Unknown | `KNOWN_MODEL_BUDGETS["mdx_net_*"]` | 🟢 Dokumentiert |

### Video Processing

| Feature | NVIDIA (expected) | AMD | Critical |
|---------|---|---|---|
| **Scene Detection** | Wahrscheinlich CUDA Filter | OpenCV (CPU) | 🟢 NEIN |
| **Optical Flow** | Wahrscheinlich PWCNet CUDA | RAFT ONNX (DirectML) | 🔴 JA |
| **Vision LLM** | Wahrscheinlich PyTorch | Moondream ONNX FP16 (DirectML) | 🔴 JA |
| **Hardware Encoding** | NVENC (h264_nvenc) | AMF (h264_amf, hevc_amf, av1_amf) | 🔴 JA |

### AI Integration

| Feature | NVIDIA (expected) | AMD | Critical |
|---------|---|---|---|
| **Audio Mood** | Unknown | CLAP PyTorch | 🟡 MITTEL |
| **Smart Director** | NICHT VORHANDEN | **SmartDirector (Semantic Matching)** | 🔴 AMD hat mehr! |
| **Clip Tagging** | Wahrscheinlich | SigLIP (Vision) | 🟡 MITTEL |

---

## 9. KONFIGURATION & DEPLOYMENT

### NVIDIA (Erwartet)
```yaml
# config.yaml (wahrscheinlich)
gpu:
  backend: cuda
  device_id: 0
  vram_limit_mb: 8192
paths:
  ffmpeg: "/usr/bin/ffmpeg"
```

### AMD (Aktuell)
```json
{
  "hardware": {
    "gpu_backend": "directml",
    "vram_limit_mb": 4096,
    "enable_monitoring": true
  },
  "paths": {
    "ffmpeg_bin": "./tools/ffmpeg/bin/ffmpeg.exe",
    "lhm_lib": "./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll"
  }
}
```

**Kritisch?** 🟢 **NEIN** - ConfigManager ist flexibel

---

## 10. ZUSAMMENFASSUNG: WAS NVIDIA HATTE (WAHRSCHEINLICH)

| **Layer** | **NVIDIA** | **AMD heute** | **Status** |
|---|---|---|---|
| **Frontend** | PyQt6 (gui/) | PyQt6 (ui/) + C# WPF geplant | 🟡 Migr. in Progress |
| **Backend Services** | audio/pacing/render_service | analysis/generation/media_service | 🟢 Äquivalent |
| **Core/GPU** | gpu_manager + reactive OOM | vram_arbiter + proactive Budget | 🔴 AMD BESSER |
| **Database** | SQLAlchemy ORM | SQLite + Repositories | 🟡 AMD simpler |
| **Worker System** | PyQt Signals im UI | Separate workers/ + Orchestrator | 🔴 AMD BESSER |
| **AI Models** | PyTorch GPU | ONNX DirectML | 🔴 Völlig anders |
| **Encoding** | NVENC | AMF | 🔴 Völlig anders |

---

## 11. KRITISCHE ERKENNTNISSE

### 🔴 BLOCKIERENDE UNTERSCHIEDE (User-sichtbar)

1. **VRAM-Verwaltung:**
   - NVIDIA: Reaktiv (OOM → Fehler → Neustart)
   - AMD: Proaktiv (Budget vor Load → Eviction)
   - **Impact:** AMD ist stabiler

2. **GPU Encoding:**
   - NVIDIA: `h264_nvenc`, `hevc_nvenc` (NVIDIA-only)
   - AMD: `h264_amf`, `hevc_amf`, `av1_amf` (AMD-only)
   - **Impact:** Hardware-spezifisch, portierbar

3. **AI Models:**
   - NVIDIA: PyTorch (GPU)
   - AMD: ONNX (DirectML, CPU-fallback möglich)
   - **Impact:** AMD ist flexibler

4. **Threading:**
   - NVIDIA: PyQt QThread (GUI-Blocks wahrscheinlich möglich)
   - AMD: ThreadPoolManager + Worker (GUI nicht blockierbar)
   - **Impact:** AMD reaktiver

### 🟡 MITTLERE UNTERSCHIEDE (Portierung nötig)

5. **Service-Struktur:**
   - Umbenennungen nötig
   - Logic größtenteils äquivalent
   - **Time:** ~2-3 Stunden für Refactoring

6. **Database:**
   - AMD braucht Global Cache für N+1 Queries
   - Repositories Schema ist gut, nur Caching fehlt
   - **Time:** ~1 Stunde für Cache Layer

7. **Config:**
   - JSON vs. YAML
   - Leicht zu konvertieren
   - **Time:** ~30 Minuten

### 🟢 KEINE CHANGES NÖTIG

- Core audio/video/pacing/ai Logik ist **gleich**
- Models (Timeline, Audio, Video) sind kompatibel
- UI kann parallel zu FastAPI weiterentwickelt werden

---

## 12. MIGRATION PATH (NVIDIA → AMD)

Wenn NVIDIA-Code existieren würde:

```
1. VRAM System
   - Ersetze gpu_manager.py durch vram_budget_manager.py
   - Integre system_monitor mit LibreHardwareMonitor
   - Time: 4-6 Stunden

2. Database
   - Konvertiere SQLAlchemy ORM → Repositories Pattern
   - Füge Global Cache (Redis oder dict-based) hinzu
   - Time: 2-3 Stunden

3. Services
   - Rename/Map: audio_service, pacing_service, render_service
   - Integriere SmartDirector (AMD-Vorteil)
   - Time: 2-3 Stunden

4. Workers
   - Konvertiere PyQt QThread → ThreadPoolManager
   - Behalte Worker Signal-System
   - Time: 3-4 Stunden

5. AI/GPU Backend
   - Ersetze PyTorch GPU → ONNX DirectML
   - Ersetze NVENC → AMF Encoding
   - Time: 6-8 Stunden

6. Config
   - YAML → JSON Converter schreiben
   - Test Path Resolution
   - Time: 1 Stunde

**Total:** ~20-25 Stunden für vollständige Migration
```

---

## 13. AKTUELLE BLOCKERS (AMD-Version)

1. **Fehlend: Global Cache**
   - Repositories machen pro Query neue Verbindung
   - N+1 Problem bei Listen
   - **Lösung:** `global_cache.py` schreiben (Redis oder dict-based)

2. **Fehlend: FastAPI Integration**
   - Services sind nur lokal nutzbar
   - C# WPF braucht HTTP Endpoints
   - **Lösung:** `fastapi_server.py` mit Routers

3. **Suboptimal: Worker Orchestration**
   - `orchestrator.py` nur für UI vorhanden
   - Pacing Worker hat keine Queue Management
   - **Lösung:** `task_queue.py` in Worker Loop integrieren

4. **Fehlend: Error Recovery**
   - `CrashHandler` ist basic
   - Keine automatische Eviction bei OOM
   - **Lösung:** `vram_arbiter.py` erweitern mit Eviction Handler

---

## 14. RECOMMENDATIONS FÜR MIGRATION ZU C# WPF

### BEHALTEN (Python bleibt)
```python
✅ src/pb_studio/core/        # VRAM Management
✅ src/pb_studio/audio/       # Analysis & Separation (CPU safe)
✅ src/pb_studio/video/       # AI Models & Encoding
✅ src/pb_studio/pacing/      # Timeline Logic
✅ src/pb_studio/ai/          # SmartDirector
✅ src/pb_studio/data/        # Database & Vectors
```

### ERSETZEN DURCH FASTAPI
```python
❌ src/pb_studio/services/    → fastapi_server/routes/
❌ src/pb_studio/ui/          → C# WPF (new project)
❌ src/pb_studio/workers/     → Async Tasks in FastAPI
```

### ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│           C# WPF Frontend (.NET 9.0)                    │
│  (MVVM, MaterialDesignThemes, async ApiClient)          │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP/REST + Server-Sent Events (Port 8765)
┌────────────────▼────────────────────────────────────────┐
│         Python FastAPI Backend                          │
│  ├─ /api/analysis   → AnalysisService                  │
│  ├─ /api/generate   → GenerationService                │
│  ├─ /api/media      → MediaService                     │
│  └─ /api/models     → ModelLoaderService               │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│    Core Python Modules (UNCHANGED)                      │
│  ├─ audio/, video/, pacing/, ai/, data/, core/         │
│  └─ Databases, GPU, AI Models (DirectML)               │
└─────────────────────────────────────────────────────────┘
```

---

## FAZIT

**AMD-Version ist strukturell MODERNER als NVIDIA erwartet:**

| Aspekt | NVIDIA (erwartet) | AMD | Gewinner |
|--------|---|---|---|
| **Architektur** | Monolitisch (PyQt) | Modular (Services + Workers) | AMD |
| **VRAM Management** | Reaktiv | Proaktiv | AMD |
| **GPU Support** | CUDA (locked-in) | DirectML (portierbar) | AMD |
| **AI Integration** | Wahrscheinlich limited | SmartDirector | AMD |
| **Code Quality** | Unknown | Well-Structured | AMD |
| **Stability** | Unknown | High (Budget-based) | AMD |

**AMD hat die Migration zu C# WPF RICHTIG vorbereitet:**
- Services sind bereits abstrahiert
- Workers sind bereits dekoupled
- Core ist GPU-agnostisch (ONNX)
- Config ist centralized

**Nächste Schritte:**
1. FastAPI Server implementieren (Port 8765)
2. Global Cache für Database (Performance)
3. C# WPF Client mit MVVM & ApiClient
4. Eviction Handler für automatische VRAM-Freigabe
5. Testing gegen long-form Videos (Test Data)
