# PB Studio AMD - Modulares Worker-System

## Architektur-Design-Dokument

**Version:** 1.0
**Datum:** 2026-02-04
**Status:** Entwurf

---

## 1. Uebersicht

Dieses Dokument beschreibt das Design eines modularen Worker-Systems fuer PB Studio AMD.
Das System trennt die Verarbeitung in spezialisierte Worker mit klaren Verantwortlichkeiten,
definierten Schnittstellen und expliziten Abhaengigkeiten.

### 1.1 Design-Prinzipien

1. **Single Responsibility**: Jeder Worker hat genau eine Aufgabe
2. **Loose Coupling**: Worker kommunizieren ueber definierte Datenstrukturen
3. **Explicit Dependencies**: Abhaengigkeiten sind klar dokumentiert
4. **VRAM-Aware**: Worker registrieren ihren GPU-Speicherbedarf
5. **Cancellable**: Alle Worker unterstuetzen Abbruch
6. **Progress-Reporting**: Einheitliches Fortschritts-Signaling

### 1.2 Basis-Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WorkerOrchestrator                           │
│  - Verwaltet Abhaengigkeiten                                        │
│  - Startet Worker in korrekter Reihenfolge                          │
│  - Sammelt Ergebnisse                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ThreadPoolManager                           │
│  - Bestehende Infrastruktur (thread_pool.py)                        │
│  - QThreadPool-basiert                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│ AUDIO Pipeline│          │ VIDEO Pipeline│          │  GEN Pipeline │
│   4 Worker    │          │   4 Worker    │          │   3 Worker    │
└───────────────┘          └───────────────┘          └───────────────┘
```

---

## 2. Basis-Worker-Klasse

### 2.1 BaseWorker Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from PyQt6.QtCore import QRunnable

class WorkerStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class WorkerResult:
    """Standardisiertes Ergebnis-Format fuer alle Worker."""
    worker_id: str
    status: WorkerStatus
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: int = 0

class BaseWorker(QRunnable, ABC):
    """
    Basis-Klasse fuer alle spezialisierten Worker.

    Erbt von QRunnable fuer ThreadPool-Kompatibilitaet.
    """

    # Klassen-Attribute - muessen von Subklassen ueberschrieben werden
    WORKER_ID: str = "base_worker"
    REQUIRED_VRAM_MB: int = 0  # GPU-Speicherbedarf
    DEPENDENCIES: Set[str] = set()  # Worker-IDs die vorher laufen muessen

    def __init__(self, input_data: Dict[str, Any]):
        super().__init__()
        self.input_data = input_data
        self.signals = WorkerSignals()
        self._cancelled = False
        self._start_time = 0

    @abstractmethod
    def process(self) -> Dict[str, Any]:
        """
        Hauptverarbeitungslogik - muss implementiert werden.

        Returns:
            Dict mit Ergebnisdaten
        """
        pass

    @abstractmethod
    def validate_input(self) -> bool:
        """Validiert die Eingabedaten vor der Verarbeitung."""
        pass

    def run(self):
        """QRunnable.run() - wird vom ThreadPool aufgerufen."""
        import time
        self._start_time = time.time()

        try:
            # 1. Input-Validierung
            if not self.validate_input():
                raise ValueError(f"Invalid input for {self.WORKER_ID}")

            # 2. Status-Update
            self.signals.status.emit(f"{self.WORKER_ID}: Starting...")

            # 3. Verarbeitung
            result_data = self.process()

            # 4. Ergebnis
            duration = int((time.time() - self._start_time) * 1000)
            result = WorkerResult(
                worker_id=self.WORKER_ID,
                status=WorkerStatus.COMPLETED,
                data=result_data,
                duration_ms=duration
            )
            self.signals.result.emit(result)

        except Exception as e:
            duration = int((time.time() - self._start_time) * 1000)
            result = WorkerResult(
                worker_id=self.WORKER_ID,
                status=WorkerStatus.FAILED,
                data={},
                error=str(e),
                duration_ms=duration
            )
            self.signals.error.emit((type(e), e, traceback.format_exc()))
            self.signals.result.emit(result)

        finally:
            self.signals.finished.emit()

    def cancel(self):
        """Setzt Cancel-Flag - Worker muss dies regelmaessig pruefen."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def emit_progress(self, percent: int, message: str = ""):
        """Hilfsmethode fuer Progress-Updates."""
        self.signals.progress.emit({
            "worker_id": self.WORKER_ID,
            "percent": percent,
            "message": message
        })
```

---

## 3. AUDIO Pipeline Worker

### 3.1 AudioImportWorker

**Verantwortung:** Importiert Audio-Dateien und extrahiert Basis-Metadaten.

```python
class AudioImportWorker(BaseWorker):
    """
    Importiert Audio-Dateien und extrahiert Metadaten via FFprobe.

    VRAM: 0 MB (CPU-only)
    Dependencies: Keine
    """

    WORKER_ID = "audio_import"
    REQUIRED_VRAM_MB = 0
    DEPENDENCIES = set()
```

| Aspekt | Details |
|--------|---------|
| **Input** | `file_path: str` - Pfad zur Audio-Datei |
| | `project_id: int` - Projekt-ID fuer DB-Speicherung |
| **Output** | `media_id: int` - Datenbank-ID |
| | `file_hash: str` - MD5-Hash fuer Duplikat-Erkennung |
| | `duration: float` - Dauer in Sekunden |
| | `sample_rate: int` - Sample-Rate in Hz |
| | `channels: int` - Anzahl Audio-Kanaele |
| | `codec: str` - Audio-Codec (z.B. "aac", "mp3") |
| | `bitrate: int` - Bitrate in kbps |
| | `temp_wav_path: str` - Pfad zur konvertierten WAV (fuer BeatNet) |
| **Signals** | `progress(int)` - 0-100% |
| | `status(str)` - "Importing...", "Extracting metadata...", etc. |
| | `result(WorkerResult)` - Finale Daten |
| | `error(tuple)` - Bei Fehlern |
| **Dependencies** | Keine |

**Verarbeitungsschritte:**
1. Datei-Existenz pruefen
2. MD5-Hash berechnen (fuer Duplikat-Check)
3. FFprobe fuer Metadaten ausfuehren
4. WAV-Konversion fuer BeatNet (22050 Hz, Mono, 16-bit)
5. In Datenbank speichern

---

### 3.2 AudioAnalyzeWorker

**Verantwortung:** BPM- und Beat-Erkennung mit BeatNet.

```python
class AudioAnalyzeWorker(BaseWorker):
    """
    Analysiert Audio mit BeatNet fuer BPM und Beat-Positionen.

    VRAM: 0 MB (CPU-only, BeatNet nutzt kein DirectML)
    Dependencies: AudioImportWorker
    """

    WORKER_ID = "audio_analyze"
    REQUIRED_VRAM_MB = 0  # BeatNet laeuft CPU-only
    DEPENDENCIES = {"audio_import"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `wav_path: str` - Pfad zur WAV-Datei (von AudioImportWorker) |
| **Output** | `bpm: float` - Erkanntes Tempo (z.B. 128.5) |
| | `beat_data: List[List[float]]` - [[time, beat_type], ...] |
| | `beat_count: int` - Anzahl erkannter Beats |
| | `downbeats: List[float]` - Positionen der Downbeats (1er) |
| | `confidence: float` - BeatNet-Konfidenz (0.0-1.0) |
| **Signals** | `progress(int)` - 0-100% |
| | `status(str)` - "Loading BeatNet...", "Analyzing...", etc. |
| | `result(WorkerResult)` - Beat-Daten |
| | `error(tuple)` - Bei Fehlern |
| **Dependencies** | `audio_import` - Braucht WAV-Pfad |

**Verarbeitungsschritte:**
1. BeatNet-Modell laden (falls nicht gecached)
2. WAV-Datei verarbeiten
3. Beat-Positionen extrahieren
4. BPM aus Beat-Intervallen berechnen
5. Downbeats identifizieren

---

### 3.3 AudioStemWorker

**Verantwortung:** Stem-Separation mit audio-separator (MDX-Net via DirectML).

```python
class AudioStemWorker(BaseWorker):
    """
    Trennt Audio in Stems (Vocals, Drums, Bass, Other).

    VRAM: ~2000 MB (MDX-Net ONNX-Modell)
    Dependencies: AudioImportWorker
    """

    WORKER_ID = "audio_stem"
    REQUIRED_VRAM_MB = 2000  # MDX-Net braucht ca. 2GB
    DEPENDENCIES = {"audio_import"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `file_path: str` - Original-Audio-Pfad |
| | `model_name: str` - MDX-Modell (default: "UVR-MDX-NET-Inst_HQ_3.onnx") |
| | `stems_requested: List[str]` - z.B. ["vocals", "instrumental"] |
| **Output** | `stems: Dict[str, str]` - {stem_name: file_path} |
| | `model_used: str` - Verwendetes Modell |
| | `processing_time: float` - Sekunden |
| **Signals** | `progress(int)` - 0-100% |
| | `status(str)` - "Loading model...", "Separating...", etc. |
| | `result(WorkerResult)` - Stem-Pfade |
| | `error(tuple)` - Bei Fehlern |
| **Dependencies** | `audio_import` - Braucht validierten Pfad |

**Verarbeitungsschritte:**
1. VRAM reservieren via VRAMArbiter
2. MDX-Modell laden (DirectML)
3. Separation durchfuehren
4. Stems speichern
5. VRAM freigeben

**VRAM-Management:**
```python
def process(self):
    arbiter = VRAMArbiter(SystemMonitor())

    if not arbiter.can_allocate(self.REQUIRED_VRAM_MB, "mdx_stem"):
        # Warten oder evict
        arbiter.evict_if_needed(self.REQUIRED_VRAM_MB)

    arbiter.reserve(self.REQUIRED_VRAM_MB, "mdx_stem")
    try:
        # ... Separation ...
    finally:
        arbiter.release(model_id="mdx_stem")
```

---

### 3.4 AudioEmbeddingWorker

**Verantwortung:** CLAP-Embeddings fuer semantische Audio-Suche.

```python
class AudioEmbeddingWorker(BaseWorker):
    """
    Generiert CLAP-Embeddings fuer Audio-Segmente.

    VRAM: ~800 MB (CLAP ONNX-Modell)
    Dependencies: AudioImportWorker
    """

    WORKER_ID = "audio_embedding"
    REQUIRED_VRAM_MB = 800
    DEPENDENCIES = {"audio_import"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `wav_path: str` - Pfad zur WAV-Datei |
| | `segment_duration: float` - Segmentlaenge in Sekunden (default: 10.0) |
| **Output** | `embeddings: List[Dict]` - [{start, end, vector}, ...] |
| | `embedding_dim: int` - Dimensionalitaet (512 fuer CLAP) |
| | `segment_count: int` - Anzahl Segmente |
| **Signals** | `progress(int)` - 0-100% |
| | `status(str)` - "Loading CLAP...", "Encoding segment X/Y...", etc. |
| | `result(WorkerResult)` - Embedding-Daten |
| | `error(tuple)` - Bei Fehlern |
| **Dependencies** | `audio_import` - Braucht WAV-Pfad |

**Verarbeitungsschritte:**
1. Audio in Segmente teilen
2. CLAP-Modell laden (ONNX + DirectML)
3. Jedes Segment encodieren
4. Embeddings in VectorStore speichern

---

## 4. VIDEO Pipeline Worker

### 4.1 VideoImportWorker

**Verantwortung:** Importiert Video-Dateien und extrahiert Metadaten.

```python
class VideoImportWorker(BaseWorker):
    """
    Importiert Videos und extrahiert technische Metadaten.

    VRAM: 0 MB (CPU-only, FFprobe)
    Dependencies: Keine
    """

    WORKER_ID = "video_import"
    REQUIRED_VRAM_MB = 0
    DEPENDENCIES = set()
```

| Aspekt | Details |
|--------|---------|
| **Input** | `file_path: str` - Pfad zur Video-Datei |
| | `project_id: int` - Projekt-ID |
| | `extract_thumbnail: bool` - Thumbnail generieren? |
| **Output** | `media_id: int` - Datenbank-ID |
| | `file_hash: str` - MD5-Hash |
| | `duration: float` - Dauer in Sekunden |
| | `resolution: Tuple[int, int]` - (width, height) |
| | `fps: float` - Frames per Second |
| | `codec: str` - Video-Codec |
| | `has_audio: bool` - Audio-Track vorhanden? |
| | `thumbnail_path: str` - Pfad zum Thumbnail |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | Keine |

---

### 4.2 VideoSceneWorker

**Verantwortung:** Scene-Detection mit PySceneDetect.

```python
class VideoSceneWorker(BaseWorker):
    """
    Erkennt Szenen-Grenzen im Video.

    VRAM: 0 MB (CPU-only, OpenCV-basiert)
    Dependencies: VideoImportWorker
    """

    WORKER_ID = "video_scene"
    REQUIRED_VRAM_MB = 0
    DEPENDENCIES = {"video_import"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `file_path: str` - Video-Pfad |
| | `threshold: float` - Content-Detector Schwellwert (default: 27.0) |
| | `min_scene_length: float` - Minimum Szenenlaenge in Sekunden |
| **Output** | `scenes: List[Dict]` - [{start, end, duration}, ...] |
| | `scene_count: int` - Anzahl Szenen |
| | `avg_scene_length: float` - Durchschnittliche Szenenlaenge |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | `video_import` |

---

### 4.3 VideoMotionWorker

**Verantwortung:** Optical-Flow-Analyse mit RAFT (DirectML).

```python
class VideoMotionWorker(BaseWorker):
    """
    Analysiert Bewegung im Video via RAFT Optical Flow.

    VRAM: ~1500 MB (RAFT ONNX-Modell)
    Dependencies: VideoImportWorker, VideoSceneWorker
    """

    WORKER_ID = "video_motion"
    REQUIRED_VRAM_MB = 1500
    DEPENDENCIES = {"video_import", "video_scene"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `file_path: str` - Video-Pfad |
| | `scenes: List[Dict]` - Szenen-Liste (von VideoSceneWorker) |
| | `sample_fps: float` - Analyse-Framerate (default: 5.0) |
| **Output** | `motion_data: List[Dict]` - Pro Szene: {scene_idx, avg_motion, peak_motion, motion_curve} |
| | `global_motion_avg: float` - Globaler Durchschnitt |
| | `high_motion_segments: List[Dict]` - Segmente mit hoher Bewegung |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | `video_import`, `video_scene` |

**Verarbeitungsschritte:**
1. VRAM reservieren
2. RAFT-Modell laden
3. Fuer jede Szene: Frames samplen und Flow berechnen
4. Motion-Statistiken aggregieren
5. VRAM freigeben

---

### 4.4 VideoVisionWorker

**Verantwortung:** Frame-Captioning mit Moondream VLM.

```python
class VideoVisionWorker(BaseWorker):
    """
    Generiert Beschreibungen fuer Key-Frames via Moondream.

    VRAM: ~2500 MB (Moondream Encoder + Decoder)
    Dependencies: VideoImportWorker, VideoSceneWorker
    """

    WORKER_ID = "video_vision"
    REQUIRED_VRAM_MB = 2500
    DEPENDENCIES = {"video_import", "video_scene"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `media_id: int` - Datenbank-ID |
| | `file_path: str` - Video-Pfad |
| | `scenes: List[Dict]` - Szenen-Liste |
| | `frames_per_scene: int` - Frames pro Szene (default: 1) |
| | `prompts: List[str]` - Analyse-Prompts |
| **Output** | `captions: List[Dict]` - [{scene_idx, frame_time, caption, objects, mood}, ...] |
| | `dominant_themes: List[str]` - Haeufigste Themen |
| | `object_inventory: Dict[str, int]` - Objekt-Haeufigkeiten |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | `video_import`, `video_scene` |

**Verarbeitungsschritte:**
1. VRAM reservieren (Moondream braucht viel!)
2. Modell laden
3. Pro Szene: Key-Frame extrahieren
4. Moondream-Analyse ausfuehren
5. Ergebnisse aggregieren
6. VRAM freigeben

---

## 5. GENERATION Pipeline Worker

### 5.1 PacingWorker

**Verantwortung:** Plant Cut-Positionen basierend auf Audio-Analyse.

```python
class PacingWorker(BaseWorker):
    """
    Plant Video-Cuts basierend auf Beats, Energy und Pacing-Settings.

    VRAM: 0 MB (CPU-only, algorithmisch)
    Dependencies: AudioAnalyzeWorker
    """

    WORKER_ID = "pacing"
    REQUIRED_VRAM_MB = 0
    DEPENDENCIES = {"audio_analyze"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `beat_data: List[List[float]]` - Von AudioAnalyzeWorker |
| | `bpm: float` - Erkanntes Tempo |
| | `audio_duration: float` - Gesamtdauer |
| | `pacing_level: int` - 1-5 (langsam bis schnell) |
| | `min_clip_duration: float` - Minimum Clip-Laenge |
| | `max_clip_duration: float` - Maximum Clip-Laenge |
| | `beat_precision: float` - Beat-Snap-Staerke (0.0-1.0) |
| | `energy_profile: List[float]` - RMS-Energiekurve |
| **Output** | `cut_plan: List[Dict]` - [{start, end, duration, energy, beat_aligned}, ...] |
| | `total_cuts: int` - Anzahl Cuts |
| | `avg_clip_duration: float` - Durchschnittliche Clip-Laenge |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | `audio_analyze` |

---

### 5.2 RenderWorker

**Verantwortung:** Rendert einzelne Video-Segmente.

```python
class RenderWorker(BaseWorker):
    """
    Rendert Video-Segmente gemaess Cut-Plan.

    VRAM: ~500 MB (AMF Encoder, wenn Hardware-Encoding)
    Dependencies: PacingWorker, VideoImportWorker
    """

    WORKER_ID = "render"
    REQUIRED_VRAM_MB = 500  # Fuer AMF
    DEPENDENCIES = {"pacing", "video_import"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `cut_plan: List[Dict]` - Von PacingWorker |
| | `source_videos: List[str]` - Verfuegbare Videos |
| | `video_metadata: Dict[str, Dict]` - Metadaten pro Video |
| | `output_dir: str` - Temp-Verzeichnis |
| | `resolution: Tuple[int, int]` - Ziel-Aufloesung |
| | `fps: int` - Ziel-FPS |
| | `use_hardware_encoding: bool` - AMF nutzen? |
| **Output** | `segments: List[str]` - Pfade zu gerenderten Segmenten |
| | `segment_count: int` - Anzahl Segmente |
| | `total_render_time: float` - Sekunden |
| **Signals** | `progress(int)` - Per-Segment-Progress |
| | Standard WorkerSignals |
| **Dependencies** | `pacing`, `video_import` |

**Verarbeitungsschritte:**
1. Fuer jeden Cut im Plan:
   a. Passendes Source-Video auswaehlen
   b. In-Point berechnen
   c. FFmpeg-Extraktion mit AMF
2. Progress nach jedem Segment updaten

---

### 5.3 ConcatWorker

**Verantwortung:** Finale Zusammenstellung mit Master-Audio.

```python
class ConcatWorker(BaseWorker):
    """
    Konkateniert Segmente und fuegt Master-Audio hinzu.

    VRAM: ~500 MB (AMF fuer Final-Encode)
    Dependencies: RenderWorker
    """

    WORKER_ID = "concat"
    REQUIRED_VRAM_MB = 500
    DEPENDENCIES = {"render"}
```

| Aspekt | Details |
|--------|---------|
| **Input** | `segments: List[str]` - Von RenderWorker |
| | `master_audio: str` - Pfad zum Master-Audio |
| | `output_path: str` - Finaler Output-Pfad |
| | `codec: str` - Output-Codec (h264, hevc, av1) |
| | `quality: str` - Qualitaetsstufe (speed, balanced, quality) |
| **Output** | `output_path: str` - Pfad zum fertigen Video |
| | `output_duration: float` - Finale Dauer |
| | `file_size_mb: float` - Dateigroesse |
| **Signals** | Standard WorkerSignals |
| **Dependencies** | `render` |

---

## 6. Abhaengigkeits-Graph

```
                    ┌─────────────────┐
                    │  AudioImport    │
                    │  VideoImport    │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌───────────┐    ┌───────────┐    ┌───────────┐
    │AudioAnalyze│    │AudioStem  │    │AudioEmbed │
    └─────┬─────┘    └───────────┘    └───────────┘
          │
          │          ┌───────────┐
          │          │VideoScene │
          │          └─────┬─────┘
          │                │
          │       ┌────────┴────────┐
          │       │                 │
          │       ▼                 ▼
          │ ┌───────────┐    ┌───────────┐
          │ │VideoMotion│    │VideoVision│
          │ └───────────┘    └───────────┘
          │
          ▼
    ┌───────────┐
    │  Pacing   │
    └─────┬─────┘
          │
          ▼
    ┌───────────┐
    │  Render   │
    └─────┬─────┘
          │
          ▼
    ┌───────────┐
    │  Concat   │
    └───────────┘
```

### 6.1 Parallelisierbare Worker

Diese Worker koennen **gleichzeitig** laufen:
- `audio_import` + `video_import`
- `audio_analyze` + `audio_stem` + `audio_embedding` (nach audio_import)
- `video_scene` (nach video_import)
- `video_motion` + `video_vision` (nach video_scene)

### 6.2 Sequentielle Abhaengigkeiten

Diese Worker **muessen warten**:
- `pacing` wartet auf `audio_analyze`
- `render` wartet auf `pacing` + `video_import`
- `concat` wartet auf `render`

---

## 7. VRAM-Budget-Planung

### 7.1 Gesamt-VRAM-Uebersicht

| Worker | VRAM (MB) | GPU-Modell |
|--------|-----------|------------|
| AudioImportWorker | 0 | - |
| AudioAnalyzeWorker | 0 | - |
| AudioStemWorker | 2000 | MDX-Net |
| AudioEmbeddingWorker | 800 | CLAP |
| VideoImportWorker | 0 | - |
| VideoSceneWorker | 0 | - |
| VideoMotionWorker | 1500 | RAFT |
| VideoVisionWorker | 2500 | Moondream |
| PacingWorker | 0 | - |
| RenderWorker | 500 | AMF |
| ConcatWorker | 500 | AMF |

### 7.2 Parallele Ausfuehrung (8GB VRAM Limit)

**Szenario A: Audio-Fokus**
- AudioStemWorker (2000) + AudioEmbeddingWorker (800) = 2800 MB (OK)

**Szenario B: Video-Fokus**
- VideoMotionWorker (1500) + VideoVisionWorker (2500) = 4000 MB (OK)

**Szenario C: Gemischt**
- AudioStemWorker (2000) + VideoMotionWorker (1500) = 3500 MB (OK)

**NICHT erlaubt:**
- AudioStemWorker (2000) + VideoVisionWorker (2500) + VideoMotionWorker (1500) = 6000 MB
  - Funktioniert nur mit Eviction

---

## 8. WorkerOrchestrator

### 8.1 Orchestrierung

```python
class WorkerOrchestrator:
    """
    Verwaltet Worker-Ausfuehrung mit Abhaengigkeits-Tracking.
    """

    def __init__(self):
        self.pool = ThreadPoolManager()
        self.arbiter = VRAMArbiter(SystemMonitor())
        self.results: Dict[str, WorkerResult] = {}
        self.pending: Set[str] = set()
        self.completed: Set[str] = set()

    def submit(self, worker: BaseWorker) -> bool:
        """
        Reicht Worker zur Ausfuehrung ein.
        Prueft Abhaengigkeiten und VRAM.
        """
        # 1. Dependency-Check
        missing_deps = worker.DEPENDENCIES - self.completed
        if missing_deps:
            self.pending.add(worker.WORKER_ID)
            return False

        # 2. VRAM-Check
        if worker.REQUIRED_VRAM_MB > 0:
            if not self.arbiter.can_allocate(worker.REQUIRED_VRAM_MB):
                # Entweder warten oder evict
                if not self.arbiter.evict_if_needed(worker.REQUIRED_VRAM_MB):
                    return False

        # 3. Worker starten
        worker.signals.result.connect(self._on_worker_complete)
        self.pool.start(worker)
        return True

    def _on_worker_complete(self, result: WorkerResult):
        """Callback wenn Worker fertig."""
        self.results[result.worker_id] = result
        self.completed.add(result.worker_id)

        # Pruefen ob wartende Worker jetzt starten koennen
        self._check_pending()
```

---

## 9. Signal-Erweiterungen

### 9.1 Erweiterte WorkerSignals

```python
class WorkerSignals(QObject):
    """
    Erweiterte Signals fuer modulare Worker.
    """
    # Basis-Signals (existieren bereits)
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(object)  # int oder dict
    status = pyqtSignal(str)

    # Neue Signals fuer Orchestrierung
    vram_reserved = pyqtSignal(int)      # VRAM reserviert (MB)
    vram_released = pyqtSignal(int)      # VRAM freigegeben (MB)
    dependency_waiting = pyqtSignal(str) # Wartet auf Worker-ID
    cancellation_requested = pyqtSignal()
```

---

## 10. Datei-Struktur

```
src/pb_studio/
├── workers/
│   ├── __init__.py
│   ├── base_worker.py          # BaseWorker, WorkerResult, WorkerStatus
│   ├── orchestrator.py         # WorkerOrchestrator
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── import_worker.py    # AudioImportWorker
│   │   ├── analyze_worker.py   # AudioAnalyzeWorker
│   │   ├── stem_worker.py      # AudioStemWorker
│   │   └── embedding_worker.py # AudioEmbeddingWorker
│   │
│   ├── video/
│   │   ├── __init__.py
│   │   ├── import_worker.py    # VideoImportWorker
│   │   ├── scene_worker.py     # VideoSceneWorker
│   │   ├── motion_worker.py    # VideoMotionWorker
│   │   └── vision_worker.py    # VideoVisionWorker
│   │
│   └── generation/
│       ├── __init__.py
│       ├── pacing_worker.py    # PacingWorker
│       ├── render_worker.py    # RenderWorker
│       └── concat_worker.py    # ConcatWorker
```

---

## 11. Verwendungsbeispiel

```python
from src.pb_studio.workers import (
    WorkerOrchestrator,
    AudioImportWorker,
    AudioAnalyzeWorker,
    PacingWorker,
    RenderWorker,
    ConcatWorker
)

# Orchestrator erstellen
orchestrator = WorkerOrchestrator()

# Audio-Import
audio_import = AudioImportWorker({
    "file_path": "C:/music/track.mp3",
    "project_id": 1
})
orchestrator.submit(audio_import)

# Audio-Analyse (wartet auf Import)
audio_analyze = AudioAnalyzeWorker({
    "media_id": 1,  # Wird von Import-Ergebnis befuellt
    "wav_path": "..."
})
orchestrator.submit(audio_analyze)

# ... weitere Worker ...

# Auf Completion warten
orchestrator.wait_all()

# Ergebnisse abrufen
final_result = orchestrator.get_result("concat")
print(f"Output: {final_result.data['output_path']}")
```

---

## 12. Migration von bestehendem Code

### 12.1 AnalysisService -> Worker-basiert

**Vorher (analysis_service.py):**
```python
def analyze_media(self, media_id, file_path, on_complete, on_error):
    def run_analysis():
        results = {}
        audio_result = self.audio_analyzer.analyze_file(file_path)
        scenes = self.scene_detector.detect_scenes(file_path)
        # ...
```

**Nachher:**
```python
def analyze_media(self, media_id, file_path, on_complete, on_error):
    orchestrator = WorkerOrchestrator()

    # Parallele Worker
    audio_worker = AudioAnalyzeWorker({"media_id": media_id, "wav_path": file_path})
    scene_worker = VideoSceneWorker({"media_id": media_id, "file_path": file_path})

    orchestrator.submit(audio_worker)
    orchestrator.submit(scene_worker)

    # Callback-Handling
    orchestrator.on_all_complete(on_complete)
    orchestrator.on_any_error(on_error)
```

---

## 13. Zusammenfassung

Dieses Design bietet:

1. **Klare Trennung** - Jeder Worker hat eine spezifische Aufgabe
2. **Explizite Abhaengigkeiten** - Keine versteckten Kopplungen
3. **VRAM-Management** - Proaktive Speicherverwaltung
4. **Parallelisierung** - Unabhaengige Worker laufen gleichzeitig
5. **Erweiterbarkeit** - Neue Worker einfach hinzufuegbar
6. **Testbarkeit** - Worker einzeln testbar

Die naechsten Schritte waeren:
1. `BaseWorker` und `WorkerOrchestrator` implementieren
2. Worker schrittweise migrieren (Audio -> Video -> Generation)
3. UI-Integration mit Progress-Anzeige
