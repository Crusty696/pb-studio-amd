# PB Studio — Modul-Map

**Automatisch erzeugt am 2026-10-01** aus `git ls-files src/pb_studio backend`
(erste Docstring-Zeile je Datei). Die frühere handgeschriebene Karte nannte
gelöschte Module (`clap_pytorch`, `moondream_pytorch`, `stem_runner`,
`video/engine.py`, `workers/`) und ist ersetzt.

Neu erzeugen: Dateiliste per `git ls-files` + `ast.get_docstring` (siehe
Commit-Text). Fakten zu Laufzeitpfaden stehen in `CLAUDE.md` §3/§4:

- GPU-Inferenz nur über `onnxruntime-directml`; LLM/VLM über LM Studio (Vulkan).
- Beats: librosa (BeatNet/madmom zur Laufzeit wirkungslos), Downbeats abgeleitet.
- Stem-Separation htdemucs auf CPU; ONNX-MDX über DirectML.
- Mix-Grenzen: `audio/subtrack_detector.py` (optimale Zerlegung, Stand T003).
### `backend/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `_brain_singleton.py` | BrainService accessor for FastAPI routers (Plan Phase 4). |
| `app_state.py` | Zentraler In-Memory App-State für alle FastAPI Router. |
| `config.py` | Backend-Konfiguration für PB Studio AMD FastAPI Server. |
| `dependencies.py` | Shared Dependencies für FastAPI Dependency Injection. |
| `main.py` | PB Studio AMD – FastAPI Backend |
| `media_path_policy.py` | Fail-closed policy for persisted media paths. |
| `owner_capability.py` | Process-local authorization and backend identity proof for loopback API calls. |
| `recovery_bootstrap.py` | Stdlib-only crash recovery bootstrap for PB Studio product generations. |
| `recovery_runtime.py` | Runtime owner adapter for automatic startup/shutdown recovery snapshots. |

### `backend/middleware/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `gpu_lock.py` | GPU-Timing Middleware für FastAPI. |
| `owner_capability.py` | Default-deny authorization for PB Studio's local HTTP boundary. |

### `backend/routers/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `audio_router.py` | Audio Router – Import, Analyse, Beats, Waveform, Stems. |
| `brain_router.py` | Brain Router (Plan Phase 4 + R-Brain-09) -- 6 Endpoints. |
| `chat_router.py` | Chat Router — KI-Chat-Endpoints fuer PB Studio (LM Studio Tool-Use). |
| `events_router.py` | Events Router – Server-Sent Events (SSE) für Echtzeit-Updates. |
| `health_router.py` | Health Router – Sub-Endpoints fuer System-Telemetrie. |
| `models_router.py` | Providerübergreifendes Modellinventar und Management für PB Studio. |
| `pacing_router.py` | Pacing Router – Cut-List Generierung und Timeline. |
| `project_router.py` | Project Router – CRUD Operationen für PB Studio Projekte. |
| `render_router.py` | Render Router – Video-Rendering starten, Status abrufen, abbrechen. |
| `video_router.py` | Video Router – Import, Analyse, Thumbnails, Scenes, Motion. |

### `backend/schemas/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `audio_schemas.py` | Audio-bezogene Schemas. |
| `brain_schemas.py` | Brain-Endpoint Schemas (Plan Phase 4 + R-Brain-09). |
| `common.py` | Gemeinsame Schemas für alle Router. |
| `health_schemas.py` | Health endpoint schemas (T5b S-H1b: Pydantic-backed /health/vram für NSwag). |
| `pacing_schemas.py` | Pacing-bezogene Schemas. |
| `project_schemas.py` | Projekt-bezogene Schemas. |
| `render_schemas.py` | Render-bezogene Schemas. |
| `video_schemas.py` | Video-bezogene Schemas. |

### `src/pb_studio/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `config_manager.py` | — |
| `runtime_contract.py` | Canonical local runtime paths for PB Studio. |

### `src/pb_studio/ai/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `chat_agent.py` | KI-Chat-Agent fuer PB Studio. |
| `clap_wrapper.py` | CLAP Audio Specialist - ONNX Implementation with DirectML |
| `config_loader.py` | Shared best-effort readers for AI configuration. |
| `llm_provider.py` | LLM-Provider-Factory fuer exklusiv gewähltes Ollama oder LM Studio. |
| `lmstudio_client.py` | LM Studio HTTP-Client fuer PB Studio (AMD Premium). |
| `model_inventory.py` | Truthful, provider-aware inventory for local AI models. |
| `model_registry.py` | Model-Registry und Auto-Selection fuer PB Studio AI-Tasks. |
| `siglip_wrapper.py` | SigLIP Image Encoder - ONNX Implementation with DirectML. |
| `smart_director.py` | Smart Director - AI-Powered Video Generation Orchestrator |
| `tool_registry.py` | Tool-Registry fuer den PB-Studio KI-Chat-Agenten. |
| `video_specialist.py` | Video Specialist - Video Analysis and Clip Matching with SigLIP. |

### `src/pb_studio/audio/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `analyzer.py` | — |
| `audio_embedder.py` | Legacy Brain cache identity for the registered CLAP ONNX encoder. |
| `band_params.py` | Gemeinsame Bandgrenzen und STFT-Parameter fuer die Drum-Trigger. |
| `beat_detector.py` | BeatDetector mit BeatNet für präzise KI-basierte Beat- & Downbeat-Erkennung. |
| `beat_grid.py` | Beatgrid-Schaetzung: Tempo, Anker und eine belastbare Guete. |
| `beat_grid_segments.py` | Segmentiertes Beatgrid fuer DJ-Mixe: mehrere Grid-Abschnitte statt eines Tempos. |
| `beat_this_tracker.py` | Hash-bound Beat This! inference; callers must hold the shared GPU lock. |
| `dj_mix_analyzer.py` | DJ-Mix-Analyzer - Erkennung von Übergängen und Energie-Phasen in DJ-Mixes. |
| `downbeat_alignment.py` | Neural event validation and diagnostic comparison with legacy beat grids. |
| `key_detector.py` | Key Detector — Krumhansl-Kessler Algorithmus für Tonarten-Erkennung. |
| `separator.py` | Stem Separator for AMD GPUs (DirectML Patched) |
| `spectral_analyzer.py` | Spectral Analyzer - 8-Band Frequenzanalyse für Audio. |
| `streaming_analyzer.py` | Streaming-Audio-Analyzer fuer lange Mixe (>60min). |
| `structure_analyzer.py` | Structure-Analyzer - Erkennung von Song-Abschnitten. |
| `subtrack_detector.py` | Sub-Track-Detection für DJ-Mixes (Plan Phase 1 #4). |
| `waveform_analyzer.py` | 3-Band Waveform Analyzer (Rekordbox-Style) |
| `waveform_cache.py` | Waveform Cache with LRU Eviction |

### `src/pb_studio/brain/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `brain_service.py` | BrainService — Singleton der Brain-Pipeline (Plan Phase 3+4). |
| `bridge_dimensions.py` | 17 Bridge-Achsen Berechnungen (Plan Decision #10 + Section 5). |
| `cold_start.py` | Cold-start defaults für 17 Brücken-Achsen (Plan Decision #9 + Section 5). |
| `context_resolver.py` | 6 Kontext-Slots + 5 Backoff-Keys (Plan Section 5). |
| `cross_modal_projector.py` | Cross-Modal Projector CLAP <-> SigLIP (R-Brain-04 + R-Brain-05 + R-Brain-08). |
| `feature_adapter.py` | Canonical real-data adapter shared by Brain scoring entry points. |
| `feedback_logger.py` | Durable Brain feedback logging across project state and global weights. |
| `llm_narrator.py` | LLM-Narrator fuer das Brain-Modul. |
| `loader_cache.py` | R-Brain-08: Process-level LRU cache for loaded raw embeddings. |
| `post_processor.py` | Brain post-processor for cut lists (Plan Phase 4 + R-Brain-01..09). |
| `projector_trainer.py` | R-Brain-05: Sammelt Audio-Video-Embedding-Paare aus Brain-Feedback und |
| `reranker.py` | BrainReranker — Eingriffspunkt in clip_selector.select_clip (Plan Phase 4). |
| `scorer.py` | BrainScorer — kombiniert verfügbare Brücken-Werte × Posterior-Gewichte. |
| `smart_sampler.py` | Smart-Sampler — Top-N Cuts fuer aktives Lernen (Plan Phase 4 + R-Brain-06). |
| `weight_store.py` | Beta-Bernoulli WeightStore mit Hierarchical Backoff |

### `src/pb_studio/core/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `crash_handler.py` | — |
| `directml_adapter.py` | Central DXGI adapter selection for every DirectML consumer. |
| `gpu_lock.py` | Global GPU inference lock for PB Studio AMD. |
| `media_hash.py` | Streaming sha256 hash for media files. |
| `model_loader.py` | VRAM-Aware Model Loader for AMD DirectML |
| `system_monitor.py` | — |
| `task_queue.py` | — |
| `thread_pool.py` | — |
| `vram_budget_manager.py` | VRAM Budget Manager - Central Authority for GPU Memory Management |
| `worker_signals.py` | — |

### `src/pb_studio/data/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `database_core.py` | — |
| `vector_operation_outbox.py` | Crash-consistent SQLite/FAISS delete operations. |
| `vector_store.py` | — |

### `src/pb_studio/data/repositories/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `media_repository.py` | — |
| `project_repository.py` | — |

### `src/pb_studio/data/schemas/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `media_json_schema.py` | C4-Fix (S-C1, 2026-05-19): Versioned schema for SQLite JSON-blob columns. |

### `src/pb_studio/models/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `audio.py` | Audio-related data models for PB Studio AMD. |
| `timeline.py` | Timeline-related data models for PB Studio AMD. |
| `video.py` | Video-related data models for PB Studio AMD. |

### `src/pb_studio/pacing/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `advanced_pacing_engine.py` | Advanced Pacing Engine - Musical Intelligence for Video Editing |
| `clip_selector.py` | Clip Selector - Intelligent Video Segment Selection (AMD Edition) |
| `constants.py` | Pacing Constants |
| `pacing_models.py` | Pacing Models |
| `timeline_models.py` | Timeline Models |

### `src/pb_studio/rendering/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `preview_renderer.py` | PreviewGenerator - Schnelle Vorschau ab beliebigem Zeitpunkt (AMD Version). |
| `render_queue.py` | Render-Queue mit SQLite-Persistenz. |
| `render_service.py` | Render Service (AMD Version) |

### `src/pb_studio/services/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `audio_service.py` | Audio Service für PB_studio AMD |
| `pacing_service.py` | Pacing Service für PB_studio AMD |

### `src/pb_studio/storage/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `backup.py` | Atomare VACUUM INTO Backups für den Hirn-Store (Plan Phase 6). |
| `brain_store.py` | 3-DB Hirn-Store unter %APPDATA%\PB_Studio\brain\ (Plan Phase 3). |
| `embedding_cache.py` | Hash-keyed embedding cache (Plan Phase 2/3, Hirn-Store). |
| `embedding_repository.py` | sqlite-vec embedding repository (Plan Phase 2). |
| `migration_runner.py` | Lightweight SQLite migrations via PRAGMA user_version (Plan Phase 3). |
| `recovery_adapters.py` | Owner inventory and semantic validation for product recovery generations. |
| `recovery_barrier.py` | Process-wide write barrier used by crash-consistent recovery snapshots. |
| `recovery_generation.py` | Immutable product-generation snapshots for PB Studio recovery. |
| `sqlite_init.py` | Standard PRAGMA setup for every SQLite connection (Plan Phase 2/3). |

### `src/pb_studio/utils/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `cache_manager.py` | Cache Manager für PB_studio AMD |
| `log_rotation.py` | Log-Rotation + Retention für PB Studio AMD. |
| `path_helpers.py` | Path Helpers |
| `profiling.py` | Einfacher Profiler und Context-Manager für Performance-Messung. |

### `src/pb_studio/video/`

| Datei | Zweck (erste Docstring-Zeile) |
|---|---|
| `audio_key_detector.py` | Extrahiert Audio-Track aus Video + detektiert Tonart via Krumhansl-Kessler (L-K4). |
| `auto_tagger.py` | Auto-Tagger für Video-Szenen basierend auf Moondream-Captions. |
| `clip_audio_peaks.py` | Extract a downsampled mono peak array from a video/audio file via ffmpeg. |
| `encoder_utils.py` | AMD AMF Encoder Utilities for PB Studio. |
| `frame_extractor.py` | Frame Extractor - Extrahiert Frames aus Videos mittels OpenCV. |
| `lmstudio_vision_wrapper.py` | LM-Studio-Vision-Wrapper fuer Video-Frame Tag-Extraktion. |
| `moondream.py` | Moondream Vision-Language Model - ONNX Implementation with DirectML. |
| `moondream_wrapper.py` | Moondream-Wrapper fuer Video-Frame Captioning + dominante Farb-Extraktion. |
| `raft.py` | RAFT Optical Flow - ONNX Implementation with DirectML. |
| `scene_detect.py` | — |
| `thumbnail_generator.py` | Thumbnail Generator - Erstellt Thumbnails für Video-Clips. |
| `video_embedder.py` | Legacy Brain cache identity for the registered SigLIP ONNX encoder. |
| `visual_curves.py` | Brightness / Saturation / Color-Temperature pro Frame. |
