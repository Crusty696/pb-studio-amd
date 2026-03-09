# PB Studio — Modul-Map

Vollständige Übersicht aller Module mit Dateien, Abhängigkeiten und Verbindungen.

## Inhaltsverzeichnis
1. [AI-Module](#ai-module)
2. [Audio-Module](#audio-module)
3. [Video-Module](#video-module)
4. [Core-Module](#core-module)
5. [Data-Module](#data-module)
6. [Pacing-Module](#pacing-module)
7. [Rendering-Module](#rendering-module)
8. [Services](#services)
9. [Workers](#workers)
10. [Models (Daten-Modelle)](#models)
11. [Utils](#utils)
12. [Backend (FastAPI)](#backend)
13. [Frontend (C# WPF)](#frontend)

---

## AI-Module
**Pfad:** `src/pb_studio/ai/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `siglip_wrapper.py` | SigLIP ONNX Embeddings (1152-dim) | onnxruntime-directml, PIL |
| `clap_wrapper.py` | CLAP Audio-Embeddings (nur NVIDIA) | — (deaktiviert auf AMD) |
| `clap_pytorch.py` | CLAP PyTorch Backend | — (deaktiviert auf AMD) |
| `moondream_pytorch.py` | Moondream ONNX FP16 Vision LLM | onnxruntime-directml |
| `smart_director.py` | KI-gesteuerte Schnitt-Entscheidungen | siglip_wrapper, vector_store |
| `video_specialist.py` | Video-spezifische AI-Analyse | moondream, siglip_wrapper |

**Wichtig:** Auf AMD kein CLAP verfügbar. SigLIP ersetzt CLIP (1152-dim statt 512-dim).

---

## Audio-Module
**Pfad:** `src/pb_studio/audio/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `analyzer.py` | Haupt-Audio-Analyse (BPM, Key, Energy) | librosa, numpy |
| `anchor_features.py` | Feature-Extraktion für Anchor-Punkte | librosa |
| `beat_detector.py` | BeatNet CPU Beat-Detection | BeatNet, madmom |
| `dj_mix_analyzer.py` | DJ-Mix spezifische Analyse | analyzer, beat_detector |
| `key_detector.py` | Tonart-Erkennung | librosa |
| `separator.py` | **LOCKED** Stem-Separation (ONNX DirectML) | onnxruntime-directml, UVR-MDX-NET |
| `spectral_analyzer.py` | Spektral-Analyse | librosa, scipy |
| `stem_runner.py` | Stem-Separation Ausführung | separator |
| `streaming_analyzer.py` | Streaming für lange Dateien (>60min) | librosa, soundfile |
| `structure_analyzer.py` | Song-Struktur-Erkennung (Intro, Verse, etc.) | librosa |
| `waveform_analyzer.py` | 3-Band Waveform-Extraktion | librosa, numpy |
| `waveform_cache.py` | Cache für berechnete Waveforms | cache_manager |

**Signalkette Audio-Analyse:**
```
AudioRouter.analyze → AudioService.analyze_audio → analyzer.py
  → beat_detector (BPM, Beats)
  → key_detector (Tonart)
  → spectral_analyzer (Spektrum)
  → waveform_analyzer (3-Band Waveform)
  → Ergebnis → DB speichern → SSE Event
```

---

## Video-Module
**Pfad:** `src/pb_studio/video/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `moondream.py` | Moondream ONNX Captioning | onnxruntime-directml |
| `raft.py` | RAFT ONNX Optical Flow | onnxruntime-directml |
| `scene_detect.py` | PySceneDetect Scene Detection | scenedetect, opencv |
| `frame_extractor.py` | Frame-Extraktion aus Video | opencv |
| `auto_tagger.py` | Automatisches Video-Tagging | siglip, moondream |
| `encoder_utils.py` | FFmpeg Encoding Utilities | ffmpeg |
| `engine.py` | Video-Processing Engine | alle video-Module |
| `thumbnail_generator.py` | Thumbnail-Erzeugung | opencv, PIL |
| `video_renderer.py` | Video-Rendering Pipeline | ffmpeg, encoder_utils |

**Signalkette Video-Analyse:**
```
VideoRouter.analyze → VideoService → engine.py
  → frame_extractor (Keyframes)
  → scene_detect (Szenen-Grenzen)
  → siglip_wrapper (Embeddings pro Frame)
  → moondream (Captions pro Szene)
  → raft (Motion-Scores)
  → auto_tagger (Tags)
  → Ergebnis → FAISS + DB → SSE Event
```

---

## Core-Module
**Pfad:** `src/pb_studio/core/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `vram_arbiter.py` | VRAM-Budgetierung & Zuweisung | system_monitor |
| `vram_budget_manager.py` | Detailliertes VRAM-Budget-Management | vram_arbiter |
| `task_queue.py` | Aufgaben-Queue mit Prioritäten | threading |
| `thread_pool.py` | Thread-Pool Management | concurrent.futures |
| `crash_handler.py` | Crash-Recovery & Logging | logging |
| `model_loader.py` | ONNX-Modell-Laden mit DirectML | onnxruntime-directml |
| `system_monitor.py` | GPU/System-Monitoring | LibreHardwareMonitor (pythonnet) |
| `worker_signals.py` | Signal-Definitionen für Worker | — |

**GPU-Zugriff-Kette:**
```
Request → gpu_lock Middleware → VramArbiter.request_vram()
  → model_loader.load_model() → ONNX DirectML Session
  → Inference → VramArbiter.release_vram()
```

---

## Data-Module
**Pfad:** `src/pb_studio/data/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `database_core.py` | SQLite via SQLAlchemy | sqlalchemy |
| `vector_store.py` | FAISS-CPU Vector Store | faiss-cpu |
| `repositories/` | Repository-Pattern für DB-Zugriff | database_core |

---

## Pacing-Module
**Pfad:** `src/pb_studio/pacing/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `advanced_pacing_engine.py` | Haupt-Pacing-Engine | clip_selector, semantic_matcher |
| `anchor_manager.py` | Anchor-Punkt-Verwaltung | — |
| `clip_selector.py` | Video-Clip-Auswahl basierend auf Beats | vector_store, siglip |
| `constants.py` | Pacing-Konstanten | — |
| `export_handler.py` | Export der Cut-List | — |
| `mood_generator.py` | Stimmungs-Generierung aus Audio | audio analyzer |
| `motion_preference.py` | Motion-Präferenz pro Beat-Phase | raft scores |
| `pacing_models.py` | Daten-Modelle für Pacing | pydantic |
| `semantic_matcher.py` | Semantisches Matching Audio↔Video | siglip, vector_store |
| `smart_director.py` | Regie-Entscheidungen | advanced_pacing_engine |
| `timeline_models.py` | Timeline-Datenstrukturen | — |

**Signalkette Pacing:**
```
PacingRouter.generate → PacingService → advanced_pacing_engine
  → anchor_manager (Beat-Anchors laden)
  → mood_generator (Stimmung aus Audio)
  → clip_selector (Video-Clips wählen via FAISS)
  → semantic_matcher (Audio↔Video Matching)
  → motion_preference (Motion-Score pro Segment)
  → export_handler (Cut-List generieren)
  → SSE Events (Progress)
```

---

## Rendering-Module
**Pfad:** `src/pb_studio/rendering/`

| Datei | Funktion | Abhängigkeiten |
|-------|----------|----------------|
| `final_renderer.py` | Finales Video-Rendering | ffmpeg, render_engine |
| `preview_renderer.py` | Schnelle Vorschau-Generierung | ffmpeg |
| `proxy_service.py` | Proxy-Dateien für leichte Vorschau | ffmpeg |
| `render_engine.py` | Rendering-Orchestrator | final_renderer, video_renderer |
| `render_service.py` | Service-Schicht für Rendering | render_engine |

---

## Services
**Pfad:** `src/pb_studio/services/`

| Datei | Funktion | Verbindet |
|-------|----------|-----------|
| `analysis_service.py` | Koordiniert Audio+Video Analyse | audio/, video/, ai/ |
| `audio_service.py` | Audio-Operationen | audio/ Module |
| `generation_service.py` | Video-Generierung aus Pacing | pacing/, rendering/ |
| `media_service.py` | Medien-Import/-Verwaltung | data/, audio/, video/ |
| `pacing_service.py` | Pacing-Operationen | pacing/ Module |

---

## Workers
**Pfad:** `src/pb_studio/workers/`

| Datei | Funktion |
|-------|----------|
| `orchestrator.py` | Koordiniert Worker-Ausführung |
| `worker_registry.py` | Registry aller verfügbaren Worker |
| `registry_setup.py` | Worker-Registrierung beim Start |
| `base_worker.py` | Basis-Klasse für alle Worker |
| `audio/` | Audio-spezifische Worker |
| `video/` | Video-spezifische Worker |
| `generation/` | Generierungs-Worker |

---

## Models
**Pfad:** `src/pb_studio/models/`

| Datei | Inhalt |
|-------|--------|
| `audio.py` | AudioClip, AudioAnalysisResult, StemResult |
| `video.py` | VideoClip, VideoAnalysisResult, SceneInfo |
| `timeline.py` | TimelineEntry, CutList, PacingResult |

---

## Utils
**Pfad:** `src/pb_studio/utils/`

| Datei | Funktion |
|-------|----------|
| `cache_manager.py` | Allgemeiner Cache (Waveforms, Thumbnails, etc.) |
| `logging_setup.py` | Logging-Konfiguration |
| `path_helpers.py` | Pfad-Utilities |
| `profiling.py` | Performance-Profiling |

---

## Backend
**Pfad:** `backend/`

### Router
| Router | Prefix | Kern-Funktionen |
|--------|--------|-----------------|
| `audio_router.py` | `/api/audio` | analyze, separate, beats, waveform |
| `video_router.py` | `/api/video` | analyze, scenes, embeddings, thumbnails |
| `pacing_router.py` | `/api/pacing` | generate, preview, export |
| `render_router.py` | `/api/render` | start, status, cancel |
| `project_router.py` | `/api/project` | load, save, list |
| `events_router.py` | `/api/events` | SSE stream |

### Middleware
- `gpu_lock.py` — Stellt sicher, dass nur ein GPU-Job gleichzeitig läuft

### Schemas (Pydantic)
Ein Schema-Modul pro Router in `backend/schemas/`.

---

## Frontend
**Pfad:** `PBStudio.UI/`

### Technologie-Stack
- .NET 9.0, WPF
- CommunityToolkit.Mvvm
- MaterialDesignThemes.Wpf
- MahApps.Metro.IconPacks.Material
- Microsoft.Xaml.Behaviors.Wpf

### Architektur
MVVM-Pattern: View (XAML) ↔ ViewModel (C#) ↔ Service (HTTP/SSE)

Kein Code-Behind wo MVVM möglich.
