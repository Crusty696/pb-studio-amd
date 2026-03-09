# PB Studio - Vollständige Technische Abhängigkeitsliste

**Version:** 0.9.x (Pre-Smart-Director)  
**Erstellt:** 2026-01-20  
**Zielsystem:** NVIDIA GTX 1060 (6GB VRAM), 16GB RAM, Windows

---

## 1. SYSTEM-ANFORDERUNGEN

### Hardware (Minimum)
| Komponente | Anforderung | Empfohlen |
|------------|-------------|-----------|
| GPU | NVIDIA GTX 1060 6GB | RTX 2070+ |
| VRAM | 6 GB | 8+ GB |
| RAM | 16 GB | 32 GB |
| CPU | 4 Cores | 8+ Cores |
| Storage | SSD 50 GB frei | NVMe 100+ GB |

### Software-Basis
| Komponente | Version | Status |
|------------|---------|--------|
| **Python** | 3.11.0 | ✅ Erforderlich |
| **CUDA Toolkit** | 12.1 | ✅ Erforderlich |
| **cuDNN** | 8.9+ | ✅ Erforderlich |
| **FFmpeg** | 6.0+ (mit NVENC) | ✅ Erforderlich |
| **Windows** | 10/11 | ✅ Getestet |

---

## 2. CORE PYTHON DEPENDENCIES

### Deep Learning Framework
| Paket | Version | Funktion | VRAM-Impact |
|-------|---------|----------|-------------|
| `torch` | 2.4.1+cu121 | GPU-Berechnungen, Tensoren | Basis |
| `torchvision` | 0.19.1+cu121 | Vision-Modelle (RAFT) | ~300 MB |
| `torchaudio` | 2.4.1+cu121 | Audio-Processing (Alternative) | ~100 MB |
| `transformers` | ≥4.46.3 | HuggingFace Model-Loader | ~200 MB |

### Numerische Bibliotheken
| Paket | Version | Funktion | Kritisch |
|-------|---------|----------|----------|
| `numpy` | <2.0 | Array-Operationen | ⚠️ MUSS <2.0 sein |
| `scipy` | <1.16 | Wissenschaftliche Berechnungen | ⚠️ MUSS <1.16 sein |
| `numba` | ~0.58 | JIT-Kompilierung | Optional |

---

## 3. AUDIO ML PIPELINE

### 3.1 Beat-Detection & Analyse

| Paket | Version | Funktion | VRAM/RAM |
|-------|---------|----------|----------|
| `beatnet` | ^1.1.1 | Beat-Detection (offline DBN) | ~200 MB VRAM |
| `madmom` | (via beatnet) | Audio-Features (mit Python 3.11 Patches) | CPU only |
| `librosa` | ^0.10.1 | Audio-Analyse, Spektrogramme | CPU only |
| `soundfile` | ^0.12.1 | Audio I/O, Streaming | CPU only |

**Funktionen:**
- Beat-Detection (Beats, Downbeats, BPM)
- Onset-Strength-Analyse
- RMS Energy-Extraktion
- Spectral Centroid
- Mel-Spektrogramme
- 3-Band Waveform-Extraktion (Rekordbox-Stil)
- Streaming für Dateien >60 Min

**Kritische Patches (Python 3.11+):**
```python
# madmom collections.abc Kompatibilität
import collections
import collections.abc
collections.Iterable = collections.abc.Iterable
collections.Mapping = collections.abc.Mapping
collections.MutableMapping = collections.abc.MutableMapping
collections.MutableSequence = collections.abc.MutableSequence
collections.Callable = collections.abc.Callable
```

### 3.2 Stem-Separation

| Paket | Version | Funktion | VRAM/RAM |
|-------|---------|----------|----------|
| `demucs` | ~4.0 | 4-Stem Separation (drums, bass, vocals, other) | 4-5 GB VRAM, 8 GB RAM |

**LOCKED Konstanten (NICHT ÄNDERN):**
```python
_CUDA_FALLBACK_ENABLED = False    # KEIN CPU-Fallback
_CUDA_STABLE_SEGMENT_SIZE = 5     # 5s Chunks
_CUDA_STABLE_OVERLAP = 0.1        # 10% Overlap
_CUDA_MIN_FREE_VRAM_GB = 1.5      # Safety-Margin
_MAX_DURATION_BEFORE_CHUNKING = 180  # 3 Min → Auto-Chunking
```

**Funktionen:**
- 4-Stem Separation (Drums, Bass, Vocals, Other)
- Chunked Processing für lange Dateien
- CUDA-only (kein CPU-Fallback)
- Progress-Callbacks für GUI

---

## 4. VIDEO AI ANALYSIS

### 4.1 Semantic Analysis (CLIP)

| Paket | Version | Modell | VRAM |
|-------|---------|--------|------|
| `transformers` | ≥4.46.3 | openai/clip-vit-base-patch32 | ~1.5 GB |
| `transformers` | ≥4.46.3 | openai/clip-vit-large-patch14 | ~2.5 GB |

**Funktionen:**
- Embedding-Generierung (512/768 Dimensionen)
- Batch-Processing (32 Frames gleichzeitig)
- Text-zu-Bild Similarity
- Semantische Video-Suche

### 4.2 Motion Analysis (RAFT Optical Flow)

| Paket | Version | Modell | VRAM |
|-------|---------|--------|------|
| `torchvision` | 0.19.1+cu121 | raft_large (Raft_Large_Weights.DEFAULT) | ~300 MB + Frames |

**Funktionen:**
- Optical Flow Berechnung
- Motion-Score pro Clip (mean, max, curve)
- Konfigurierbares FPS-Sampling (Default: 10 fps)
- Frame-Buffer-Management

**Performance-Parameter:**
| Parameter | Default | Funktion |
|-----------|---------|----------|
| `sample_fps` | 10.0 | Frames pro Sekunde für Analyse |
| RAM-Limit | ~2 GB | Für Videos >5 Min |

### 4.3 Video Captioning (Moondream)

| Paket | Version | Modell | VRAM |
|-------|---------|--------|------|
| `moondream` | Latest | vikhyatk/moondream2 | ~4 GB |

**Funktionen:**
- Automatische Clip-Beschreibungen
- Visual Question Answering
- Content-Tags Generierung

### 4.4 Scene Detection

| Paket | Version | Funktion | VRAM |
|-------|---------|----------|------|
| `scenedetect` | ^0.6 | ContentDetector | CPU only |

**Funktionen:**
- Automatische Scene-Splits
- Konfigurierbarer Threshold (20-35)
- Timestamp-Extraktion

### 4.5 Frame Extraction

| Paket | Version | Funktion | VRAM |
|-------|---------|----------|------|
| `opencv-python` | ^4.8 | VideoCapture, Frame-Manipulation | GPU-Decode optional |

**Funktionen:**
- Frame-Extraktion mit konfigurierbarem FPS
- BGR→RGB Konvertierung
- Thumbnail-Generierung
- Video-Metadata-Extraktion

---

## 5. VECTOR DATABASE (ChromaDB)

| Paket | Version | Funktion |
|-------|---------|----------|
| `chromadb` | ^0.4 | Embedding Storage, Similarity Search |

**Konfiguration:**
```python
Settings(
    anonymized_telemetry=False,
    allow_reset=True
)
collection_metadata={"hnsw:space": "cosine"}
```

**Collections:**
| Collection | Dimensionen | Inhalt |
|------------|-------------|--------|
| `video_clips` (Legacy) | 512 | OpenAI CLIP Embeddings |
| `siglip_videos` (Geplant) | 1152 | Google SigLIP Embeddings |

**Funktionen:**
- Clip-Embedding Storage
- Cosine Similarity Search
- Metadata-Filterung (motion_score, duration)
- Blacklist-Support für Clip-Selection

**⚠️ KRITISCH (Windows):**
- IMMER `close()` vor App-Exit aufrufen
- File-Locks verhindern sonst Zugriff

---

## 6. SQL DATABASE (SQLAlchemy)

| Paket | Version | Funktion |
|-------|---------|----------|
| `sqlalchemy` | ^2.0 | ORM, Session-Management |
| `alembic` | ^1.12 | Database-Migrations |

**Tabellen:**
- `projects` - Projekt-Metadaten
- `audio_files` - Audio-Tracks
- `video_files` - Video-Clips
- `timelines` - Generierte Schnitte
- `embeddings` - Embedding-Referenzen

---

## 7. GUI FRAMEWORK (PyQt6)

| Paket | Version | Funktion |
|-------|---------|----------|
| `PyQt6` | ^6.6 | GUI Framework |
| `pyqtgraph` | ^0.13 | Waveform/Timeline Visualisierung |

### Worker-Architektur
| Worker | Funktion | GPU/CPU |
|--------|----------|---------|
| `AudioWorker` | Audio-Analyse | CPU |
| `StemWorker` | Demucs Separation | GPU (4-5 GB) |
| `VideoWorker` | Video-Import | CPU |
| `VideoAnalysisWorker` | RAFT Motion | GPU (300 MB) |
| `EmbeddingWorker` | CLIP Embeddings | GPU (1.5 GB) |
| `PacingWorker` | Timeline-Generierung | CPU |
| `RenderWorker` | FFmpeg Rendering | GPU (NVENC) |
| `ResourceWorker` | System-Monitoring (1 Hz) | CPU |

**Signals:**
```python
progress = pyqtSignal(int, str)    # (0-100, message)
finished = pyqtSignal(object)      # Ergebnis
error = pyqtSignal(str)            # Fehlermeldung
```

**⚠️ KRITISCHE REGELN:**
1. NIE GUI-Widgets aus Worker-Thread manipulieren
2. IMMER Signals für Cross-Thread-Kommunikation
3. IMMER Worker bei closeEvent stoppen
4. IMMER try/finally für Batch-Mode

---

## 8. RENDERING PIPELINE (FFmpeg)

| Tool | Version | Funktion |
|------|---------|----------|
| `ffmpeg` | 6.0+ | Video-Encoding, Muxing |
| `ffmpeg-python` | ^0.2 | Python-Bindings (optional) |

### NVENC Encoder
| Encoder | Codec | GPU-Generation |
|---------|-------|----------------|
| `h264_nvenc` | H.264 | GTX 600+ (Kepler) |
| `hevc_nvenc` | H.265 | GTX 900+ (Maxwell) |
| `av1_nvenc` | AV1 | RTX 4000+ (Ada) |

### Presets
| Preset | Speed | Qualität | Use-Case |
|--------|-------|----------|----------|
| `p1` | Fastest | Niedrig | Preview |
| `p4` | Medium | Gut | Standard |
| `p7` | Slowest | Beste | Final Export |

**Funktionen:**
- Concat-Demuxer (schnittlose Verbindung)
- CUDA-beschleunigtes Decoding
- NVENC Hardware-Encoding
- Audio-Muxing (AAC 320k)
- Stream Copy (wenn möglich)
- Progress-Tracking via pipe

---

## 9. GEPLANTE AI-MODELLE (Smart Director)

### Audio Specialist (CLAP)
| Modell | Dimensionen | VRAM | Status |
|--------|-------------|------|--------|
| `laion/clap-htsat-unfused` | 512 | ~1 GB | Geplant |

**Funktionen:**
- Zero-Shot Audio Classification
- Mood-Tags Generierung (~50 Konzepte)
- Audio-zu-Text Embedding Bridge

### Video Specialist (SigLIP)
| Modell | Dimensionen | VRAM | Status |
|--------|-------------|------|--------|
| `google/siglip-so400m-patch14-384` | 1152 | ~2-3 GB | Geplant |

**Funktionen:**
- Verbesserte Bild-Embeddings (vs. CLIP)
- Text-zu-Bild Matching
- "Text-Bridge" für Audio↔Video

### Aesthetic Scorer
| Modell | VRAM | Status |
|--------|------|--------|
| LAION-Aesthetics MLP | <100 MB | Geplant |

**Funktionen:**
- Qualitäts-Score (1-10)
- Filterung verwackelter/dunkler Clips

### Training (Optional)
| Paket | Version | Funktion |
|-------|---------|----------|
| `peft` | Latest | LoRA-Adapter Training |
| `bitsandbytes` | Latest | 4-Bit Quantisierung (QLoRA) |

---

## 10. UTILITY PACKAGES

| Paket | Version | Funktion |
|-------|---------|----------|
| `psutil` | ^5.9 | System-Monitoring (CPU, RAM) |
| `pynvml` | ^11.5 | GPU-Monitoring (VRAM) |
| `Pillow` | ^10.0 | Bild-Manipulation |
| `tqdm` | ^4.66 | Progress-Bars |
| `pathlib` | (built-in) | Pfad-Handling |
| `hashlib` | (built-in) | Clip-ID Generation |
| `configparser` | (built-in) | Config-Files |
| `gc` | (built-in) | Garbage Collection |
| `threading` | (built-in) | Thread-Locks |
| `tempfile` | (built-in) | Temp-Dateien |

---

## 11. VRAM-BUDGET ÜBERSICHT

### Sequenzielles Laden (Staffellauf-Architektur)
| Phase | Modell | VRAM | Danach |
|-------|--------|------|--------|
| Ingest Video | SigLIP + Aesthetics | 3 GB | ENTLADEN |
| Ingest Audio | BeatNet + CLAP | 1.5 GB | ENTLADEN |
| Stem-Sep | Demucs | 4-5 GB | ENTLADEN |
| Analysis | RAFT Optical Flow | 0.3 GB | ENTLADEN |
| Matching | CPU-only (Vektor-Math) | 0 GB | - |
| Rendering | NVENC | ~0.5 GB | - |

### ⚠️ NIE GLEICHZEITIG LADEN:
- Demucs + Moondream (>8 GB!)
- Demucs + SigLIP (>7 GB!)
- CLIP + RAFT bei vielen Frames (RAM-Exhaustion)

---

## 12. BEKANNTE KOMPATIBILITÄTSPROBLEME

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `numpy` AttributeError | numpy ≥2.0 | numpy <2.0 installieren |
| `collections.Iterable` | Python 3.11+ | madmom Patches anwenden |
| ChromaDB File-Locks | Windows | close() vor App-Exit |
| CUDA OOM | Modell-Wechsel | gc.collect() + empty_cache() |
| librosa Warnung | scipy ≥1.16 | scipy <1.16 installieren |

---

## 13. REQUIREMENTS.TXT (Minimal)

```
# Core
torch==2.4.1+cu121
torchvision==0.19.1+cu121
torchaudio==2.4.1+cu121
transformers>=4.46.3

# Numeric (KRITISCHE VERSIONEN)
numpy<2.0
scipy<1.16

# Audio
librosa>=0.10.1
soundfile>=0.12.1
beatnet>=1.1.1
demucs>=4.0

# Video
opencv-python>=4.8
scenedetect>=0.6

# Database
chromadb>=0.4
sqlalchemy>=2.0
alembic>=1.12

# GUI
PyQt6>=6.6
pyqtgraph>=0.13

# Utilities
psutil>=5.9
pynvml>=11.5
Pillow>=10.0
tqdm>=4.66

# Optional (Smart Director)
# peft
# bitsandbytes
```

---

## 14. INSTALLATIONS-HINWEISE

### PyTorch mit CUDA
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### FFmpeg mit NVENC
- Windows: Download von https://ffmpeg.org/download.html (Full Build mit NVENC)
- Oder via chocolatey: `choco install ffmpeg-full`

### Kritische Reihenfolge
1. Python 3.11.x installieren
2. CUDA 12.1 Toolkit installieren
3. cuDNN 8.9+ installieren
4. FFmpeg mit NVENC installieren
5. `pip install numpy<2.0 scipy<1.16` ZUERST
6. Dann restliche Pakete

---

## 15. MODUL-STRUKTUR (ÜBERSICHT)

```
pb_studio/
├── audio/
│   ├── audio_analyzer.py          # BPM, Struktur, Energy
│   ├── beat_detector.py           # BeatNet + madmom
│   ├── stem_separator.py          # Demucs [LOCKED]
│   ├── streaming_analyzer.py      # Für >60 Min
│   ├── waveform_analyzer.py       # 3-Band Waveform
│   └── waveform_cache.py          # LRU-Cache
│
├── video/
│   ├── processing_pipeline.py     # Orchestrierung
│   ├── semantic_engine.py         # CLIP + Moondream [LOCKED]
│   ├── motion_analyzer.py         # RAFT Optical Flow
│   ├── scene_splitter.py          # PySceneDetect
│   ├── frame_extractor.py         # OpenCV
│   ├── vector_store.py            # ChromaDB
│   └── vector_store_manager.py    # Manager-Pattern
│
├── pacing/
│   ├── advanced_pacing_engine.py  # Rhythm-basiert
│   ├── clip_selector.py           # Vektor-Matching
│   └── semantic_pacing_engine.py  # (Geplant)
│
├── rendering/
│   ├── final_renderer.py          # NVENC Export
│   ├── preview_renderer.py        # Schnelle Vorschau
│   └── render_engine.py           # FFmpeg Low-Level
│
├── database/
│   ├── session_manager.py         # SQLAlchemy Session
│   ├── models.py                  # ORM-Modelle
│   └── embedding_crud.py          # Embedding CRUD
│
├── gui/
│   ├── main_window.py             # Haupt-Fenster
│   ├── tabs/                      # GUI-Tabs
│   └── workers/
│       ├── base_worker.py         # Basis-Klasse
│       ├── audio_worker.py
│       ├── stem_worker.py
│       ├── video_worker.py
│       ├── video_analysis_worker.py
│       ├── embedding_worker.py
│       ├── pacing_worker.py
│       ├── render_worker.py
│       └── resource_worker.py
│
├── ai/  # (Geplant - Smart Director)
│   ├── models/
│   │   ├── clap_wrapper.py
│   │   ├── siglip_wrapper.py
│   │   └── aesthetic.py
│   ├── audio_specialist.py
│   ├── video_specialist.py
│   └── smart_director.py
│
└── utils/
    ├── gpu_manager.py             # VRAM-Singleton
    └── config.py                  # Konfiguration
```

---

**Dokument erstellt:** 2026-01-20  
**Basierend auf:** PB Studio Skills v1.0, Projektdokumentation, Code-Analyse
