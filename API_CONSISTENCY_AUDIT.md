# API KONSISTENZ AUDIT: Backend ↔ Frontend
## Datum: 2026-03-05 | Codebase: Pb_studio_AMD_version

---

## AUFGABE 1: BACKEND ENDPOINTS (Python FastAPI)

### Audio Router (/audio)
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| POST | /import | AudioImportRequest {path} | AudioClipInfo |
| POST | /analyze | AudioAnalyzeRequest {clip_id, detect_beats, detect_structure, spectral_analysis} | AudioAnalysisResult |
| GET | /beats/{clip_id} | Path Param | List[BeatData] |
| GET | /waveform/{clip_id} | Path Param + Query(bands=3) | WaveformData |
| POST | /stems/separate | StemSeparateRequest {clip_id, model} | StemResult |
| GET | /structure/{clip_id} | Path Param | List[StructureSegment] |
| GET | /spectral/{clip_id} | Path Param | SpectralData |

### Video Router (/video)
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| POST | /import | VideoImportRequest {paths: List[str]} | List[VideoClipInfo] |
| GET | /clips | Query(page, limit) | List[VideoClipInfo] |
| GET | /thumbnails/{clip_id} | Path Param | Binary JPEG |
| POST | /analyze | VideoAnalyzeRequest {clip_id, detect_scenes, analyze_motion, generate_embeddings, generate_captions} | VideoAnalysisResult |
| GET | /scenes/{clip_id} | Path Param | List[SceneInfo] |
| GET | /motion/{clip_id} | Path Param | MotionData |

### Pacing Router (/pacing)
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| POST | /generate | PacingConfigSchema | CutListResponse |
| GET | /timeline | - | TimelineResponse |
| POST | /preview | PreviewRequest | PreviewResponse |

### Render Router (/render)
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| POST | /start | RenderRequest | RenderProgress |
| GET | /status/{task_id} | Path Param | RenderProgress |
| POST | /cancel/{task_id} | Path Param | {cancelled: bool, task_id: str} |

### Project Router (/project)
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| POST | /create | ProjectCreate {name, path} | ProjectInfo |
| POST | /open | ProjectOpen {path} | ProjectInfo |
| POST | /save | - | StatusResponse |
| POST | /close | - | StatusResponse |
| GET | /info | - | ProjectInfo |

### Events Router (/events) — SSE Streams
| Methode | Pfad | Beschreibung |
|---------|------|------|
| GET | /progress | SSE Stream: Analyse, Render, Import Progress |
| GET | /log | SSE Stream: Log-Nachrichten |
| GET | /gpu | SSE Stream: GPU-Status (5s Intervall) |

### Health & GPU Router
| Methode | Pfad | Request | Response |
|---------|------|---------|----------|
| GET | /health | - | {status, uptimeSeconds, gpuAvailable} |
| GET | /gpu/status | - | GpuStatus |
| POST | /gpu/cleanup | - | {} |

---

## AUFGABE 2: C# API AUFRUFE (ApiClient.cs + IApiClient.cs)

### Implementierte Aufrufe in ApiClient.cs
- GetHealthAsync() → GET /health
- GetGpuStatusAsync() → GET /gpu/status
- CleanupGpuAsync() → POST /gpu/cleanup
- ImportAudioAsync(path) → POST /audio/import
- GetAudioClipsAsync(page, limit) → GET /audio/clips
- AnalyzeAudioAsync(clipId) → POST /audio/analyze
- GetBeatsAsync(clipId) → GET /audio/beats/{clipId}
- SeparateStemsAsync(clipId, model) → POST /audio/stems/separate
- ImportVideosAsync(paths) → POST /video/import
- GetVideoClipsAsync(page, limit) → GET /video/clips
- GetThumbnailAsync(clipId) → GET /video/thumbnails/{clipId}
- AnalyzeVideoAsync(clipId) → POST /video/analyze
- GenerateCutListAsync(config) → POST /pacing/generate
- GetTimelineAsync() → GET /pacing/timeline
- StartRenderAsync(request) → POST /render/start
- GetRenderStatusAsync(taskId) → GET /render/status/{taskId}
- CancelRenderAsync(taskId) → POST /render/cancel/{taskId}

---

## AUFGABE 3 & 4: KONSISTENZ VERGLEICH

### ✅ FEHLENDE BACKEND ENDPOINTS (von C# nicht aufgerufen)
1. **GET /audio/waveform/{clip_id}** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: WaveformData
   - C# braucht das für Waveform-Visualisierung?

2. **GET /audio/structure/{clip_id}** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: List[StructureSegment]
   - Sollte von AnalysisViewModel verwendet werden?

3. **GET /audio/spectral/{clip_id}** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: SpectralData
   - Sollte für Spektral-Visualisierung verwendet werden?

4. **GET /video/scenes/{clip_id}** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: List[SceneInfo]
   - Sollte von VideoAnalysisViewModel verwendet werden?

5. **GET /video/motion/{clip_id}** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: MotionData
   - Sollte von VideoAnalysisViewModel verwendet werden?

6. **POST /pacing/preview** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: PreviewRequest → PreviewResponse
   - Sollte von TimelineViewModel verwendet werden?

7. **GET /project/info** — Existiert, wird aber NICHT von C# aufgerufen!
   - Schema: ProjectInfo
   - Sollte nach Project-Operationen abgerufen werden?

---

### ❌ FEHLENDE ENDPOINTS: C# versucht Aufrufe, die nicht existieren

#### KRITISCH:
- **GET /audio/clips** — Backend hat KEINEN solchen Endpoint!
  - C# versucht: `GET /audio/clips?page={page}&limit={limit}`
  - Backend hat nur einzelne GET-Operationen für Beats, Waveform, Structure, Spectral
  - **FIX NÖTIG**: Endpoint in audio_router.py hinzufügen ODER C# ändert Logic

- **GET /video/clips** — Backend hat KEINEN solchen Endpoint!
  - C# versucht: `GET /video/clips?page={page}&limit={limit}`
  - Backend hat `/video/import` und `/video/analyze`, aber kein List-Endpoint
  - **FIX NÖTIG**: Endpoint in video_router.py hinzufügen ODER aus AppState-Query

---

## KRITISCHE SCHEMA MISMATCHES

### 🔴 BUG-001: RenderRequest — Doppeltes fps Feld in Python

**Python Backend** (backend/schemas/render_schemas.py Zeilen 32-33):
```python
class RenderRequest(BaseModel):
    output_path: str = Field(..., description="Ziel-Dateipfad")
    audio_path: str = Field(..., description="Audio-Quell-Pfad")
    quality: RenderQuality = RenderQuality.HIGH
    encoder: Optional[RenderEncoder] = None
    resolution_width: int = 1920
    resolution_height: int = 1080
    fps: float = 30.0        # ZEILE 32 — float
    fps: int = 30            # ZEILE 33 — DOPPELT! int (überschreibt)
    bitrate_mbps: float = 12.0
    include_audio: bool = True
```

**C# ApiClient.cs Zeile 186:**
```csharp
public record RenderRequest(string OutputPath, string AudioPath, string Quality,
                           int ResolutionWidth, int ResolutionHeight, double Fps);
```

**PROBLEM**:
- Python deklariert `fps` zweimal (Zeile 32 und 33)
- Pydantic interpretiert dies als: `fps: int = 30` (zweite Deklaration gewinnt)
- C# sendet `double Fps` (PascalCase) → wird zu `fps: float` (snake_case)
- **Typenmismatch**: C# float vs. Python int
- **Fehlende Felder in C#**: bitrate_mbps, include_audio werden nicht gesendet!

---

### 🔴 BUG-002: RenderRequest — Fehlende Felder in C#

**Python erwartet (render_schemas.py):**
```python
output_path: str
audio_path: str
quality: RenderQuality
encoder: Optional[RenderEncoder] = None
resolution_width: int
resolution_height: int
fps: int  # Nach Doppel-Deklaration
bitrate_mbps: float = 12.0        # ← C# SENDET NICHT
include_audio: bool = True        # ← C# SENDET NICHT
```

**C# sendet (ApiClient.cs Zeile 186):**
```csharp
OutputPath, AudioPath, Quality, ResolutionWidth, ResolutionHeight, Fps
```

**PROBLEM**:
- C# weglassen: `bitrate_mbps`, `include_audio`
- Backend erwartet diese Felder
- Pydantic füllt Default-Werte ein (12.0, True), aber das ist semantisch falsch
- **Rendering-Parameter werden ignoriert!**

---

### 🟠 BUG-003: AudioAnalysisResult — energy_curve Typ Mismatch

**Python** (backend/schemas/audio_schemas.py Zeile 48):
```python
class AudioAnalysisResult(BaseModel):
    clip_id: int
    duration_seconds: float
    bpm: float = 0.0
    beat_count: int = 0
    beats: list[BeatData] = []
    key: Optional[str] = None
    energy_curve: list[float] = []              # ← Nie null!
    structure_segments: list[dict] = []
    spectral_data: Optional[dict] = None
```

**C#** (PBStudio.UI/Services/ApiClient.cs Zeile 176):
```csharp
public record AudioAnalysisResult(..., List<float>? EnergyCurve = null);  // ← Nullable!
```

**PROBLEM**:
- Python: `energy_curve` ist immer `list[float]` (leere Liste, nie null)
- C#: `EnergyCurve` ist `List<float>?` (kann null sein)
- **Deserialisierung OK**, aber C# Null-Checks sind unnötig
- **FIX**: C# sollte sein: `List<float> EnergyCurve = []`

---

### 🟠 BUG-004: VideoAnalysisResult — embedding_dim Feld fehlt in C#

**Python** (backend/schemas/video_schemas.py Zeilen 35-43):
```python
class VideoAnalysisResult(BaseModel):
    clip_id: int
    scene_count: int = 0
    avg_motion: float = 0.0
    dominant_colors: list[str] = []
    tags: list[str] = []
    embedding_dim: int = 1152                   # ← SigLIP 1152-dim
    has_embedding: bool = False
```

**C#** (PBStudio.UI/Services/ApiClient.cs Zeile 180):
```csharp
public record VideoAnalysisResult(int ClipId, int SceneCount, double AvgMotion,
                                 List<string> DominantColors, List<string> Tags,
                                 bool HasEmbedding);  // ← embedding_dim FEHLT!
```

**PROBLEM**:
- Python gibt `embedding_dim: int = 1152` in Response zurück
- C# hat kein Feld dafür → wird ignoriert
- **IMPACT**: Embedding-Dimension-Info geht verloren
- **FIX**: C# Record ergänzen: `int EmbeddingDim`

---

### 🟠 BUG-005: TimelineEntry — segment_type Feld fehlt in C#

**Python** (backend/schemas/pacing_schemas.py Zeilen 47-57):
```python
class TimelineEntrySchema(BaseModel):
    clip_id: str
    clip_name: str
    file_path: str
    start_time: float
    end_time: float
    clip_start: float = 0.0
    trigger_type: str = ""
    trigger_strength: float = 0.0
    segment_type: Optional[str] = None          # ← Optional, aber vorhanden
```

**C#** (PBStudio.UI/Services/ApiClient.cs Zeile 184):
```csharp
public record TimelineEntry(string ClipId, string ClipName, string FilePath,
                           double StartTime, double EndTime, double ClipStart,
                           string TriggerType, double TriggerStrength);  // ← segment_type FEHLT!
```

**PROBLEM**:
- Python `TimelineEntrySchema` hat `segment_type: Optional[str] = None`
- C# TimelineEntry-Record hat kein SegmentType-Feld
- **Deserialisierung**: Feld wird ignoriert (Extra-Felder erlaubt per JsonSerializerOptions)
- **IMPACT**: Segment-Type-Info geht verloren (z.B. "verse", "chorus")
- **FIX**: C# Record: `string? SegmentType = null`

---

### 🟠 BUG-006: PacingConfig — nested TriggerSettingsSchema wird flach gesendet

**Python PacingConfigSchema** (backend/schemas/pacing_schemas.py Zeilen 7-24):
```python
class TriggerSettingsSchema(BaseModel):
    beat_sensitivity: float = Field(0.7, ge=0.0, le=1.0)
    energy_threshold: float = Field(0.5, ge=0.0, le=1.0)
    onset_weight: float = Field(0.3, ge=0.0, le=1.0)
    spectral_weight: float = Field(0.2, ge=0.0, le=1.0)

class PacingConfigSchema(BaseModel):
    audio_clip_id: int
    video_clip_ids: list[int] = []
    expected_bpm: float = 120.0
    trigger_settings: TriggerSettingsSchema = TriggerSettingsSchema()  # ← Nested!
    use_motion_matching: bool = False
    use_structure_awareness: bool = False
    duration_limit: Optional[float] = None
    min_cut_interval: float = 0.5                                      # ← C# hat das nicht!
```

**C#** (PBStudio.UI/Services/ApiClient.cs Zeile 185):
```csharp
public record PacingConfig(int AudioClipId, List<int> VideoClipIds,
                          double ExpectedBpm, bool UseMotionMatching,
                          bool UseStructureAwareness, double? DurationLimit);
                          // ← TriggerSettingsSchema FEHLT
                          // ← min_cut_interval FEHLT
```

**PROBLEM**:
- Python erwartet: `trigger_settings` als nested Objekt (TriggerSettingsSchema)
- C# sendet: flache Properties (keine TriggerSettings)
- Python erwartet: `min_cut_interval: float = 0.5`
- C# hat: kein min_cut_interval Feld
- **Deserialisierung kann fehlschlagen!** Wenn Pydantic `strict=True` ist
- **FIX**: C# muss TriggerSettings und min_cut_interval hinzufügen

---

## FEHLENDE C# API-AUFRUFE (existieren im Backend)

| # | Endpoint | C# Methode | Zweck |
|----|----------|-----------|-------|
| 1 | GET /audio/waveform/{clip_id} | `GetWaveformAsync(clipId, bands)` | Waveform-Visualisierung |
| 2 | GET /audio/structure/{clip_id} | `GetStructureSegmentsAsync(clipId)` | Timeline-Vorschau (Verse/Chorus) |
| 3 | GET /audio/spectral/{clip_id} | `GetSpectralDataAsync(clipId)` | Spektral-Anzeige |
| 4 | GET /video/scenes/{clip_id} | `GetScenesAsync(clipId)` | Scene-Detection Ergebnisse |
| 5 | GET /video/motion/{clip_id} | `GetMotionDataAsync(clipId)` | Motion-Analyse Ergebnisse |
| 6 | POST /pacing/preview | `GeneratePreviewAsync(startSec, duration)` | Timeline-Preview |
| 7 | GET /project/info | `GetProjectInfoAsync()` | Projekt-Info nach Operationen |

---

## FEHLENDE BACKEND ENDPOINTS (C# versucht sie zu nutzen)

| # | C# Methode | Backend Endpoint | Problem |
|----|-----------|-----------------|---------|
| 1 | `GetAudioClipsAsync(page, limit)` | GET /audio/clips | **EXISTIERT NICHT** |
| 2 | `GetVideoClipsAsync(page, limit)` | GET /video/clips | **EXISTIERT NICHT** |

### Details zu fehlenden Endpoints:

#### GET /audio/clips
- **Wo C# versucht zu nutzen**: AudioLibraryViewModel, wahrscheinlich in `LoadAudioClipsAsync()`
- **Was Backend hat**: Audio-Clips in `AppState.audio_clips` dict, aber kein GET /audio/clips Endpoint
- **FIX Option 1**: Neuer Endpoint in audio_router.py:
  ```python
  @router.get("/clips", response_model=list[AudioClipInfo], ...)
  async def list_audio_clips(page: int = 1, limit: int = 50, state: AppState = Depends(get_app_state)):
      clips = list(state.audio_clips.values())
      start = (page - 1) * limit
      return [AudioClipInfo(**c) for c in clips[start:start+limit]]
  ```
- **FIX Option 2**: C# lädt Clips direkt nach /audio/import, speichert sie lokal

#### GET /video/clips
- **Wo C# versucht zu nutzen**: DirectorViewModel, wahrscheinlich in `LoadVideoClipsAsync()`
- **Was Backend hat**: Video-Clips in `AppState.video_clips` dict, aber kein GET /video/clips Endpoint (video_router.py Zeile 93 zeigt falschen Endpoint!)
- **FIX Option 1**: Neuer Endpoint in video_router.py (BEREITS VORHANDEN — Zeile 93!):
  ```python
  @router.get("/clips", response_model=list[VideoClipInfo], ...)
  async def list_clips(page: int = Query(1), limit: int = Query(50), ...):
      # existiert bereits!
  ```
  **ABER**: Nicht in Router registriert? Oder Router nicht in main.py included?
- **FIX Option 2**: Prüfen, ob Endpoint wirklich nicht erreichbar ist

---

## ZUSAMMENFASSUNG KRITISCHER FEHLER

| # | Typ | Komponente | Problem | Datei | Zeile | Schweregrad |
|----|------|-----------|---------|-------|-------|------------|
| 1 | Schema | RenderRequest | Doppeltes `fps` Feld (float + int) | render_schemas.py | 32-33 | 🔴 KRITISCH |
| 2 | Schema | RenderRequest | Fehlende `bitrate_mbps`, `include_audio` in C# | ApiClient.cs | 186 | 🔴 KRITISCH |
| 3 | Endpoint | Audio | `/audio/clips` existiert nicht in Backend | audio_router.py | - | 🔴 KRITISCH |
| 4 | Endpoint | Video | `/video/clips` nicht erreichbar oder nicht registriert | video_router.py | 93 | 🔴 KRITISCH |
| 5 | Schema | VideoAnalysisResult | Fehlende `embedding_dim` in C# Record | ApiClient.cs | 180 | 🟠 WICHTIG |
| 6 | Schema | AudioAnalysisResult | `energy_curve` sollte nicht nullable sein | ApiClient.cs | 176 | 🟠 WICHTIG |
| 7 | Schema | TimelineEntry | Fehlende `segment_type` in C# Record | ApiClient.cs | 184 | 🟠 WICHTIG |
| 8 | Schema | PacingConfig | Nested `trigger_settings` fehlt in C# | ApiClient.cs | 185 | 🟠 WICHTIG |
| 9 | Schema | PacingConfig | `min_cut_interval` fehlt in C# | ApiClient.cs | 185 | 🟠 WICHTIG |
| 10 | API-Aufruf | Audio | `GetWaveformAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 11 | API-Aufruf | Audio | `GetStructureSegmentsAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 12 | API-Aufruf | Audio | `GetSpectralDataAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 13 | API-Aufruf | Video | `GetScenesAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 14 | API-Aufruf | Video | `GetMotionDataAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 15 | API-Aufruf | Pacing | `GeneratePreviewAsync()` Missing | IApiClient.cs | - | 🟠 WICHTIG |
| 16 | API-Aufruf | Project | `GetProjectInfoAsync()` Missing | IApiClient.cs | - | 🟡 MINOR |

---

## EMPFEHLUNGEN NÄCHSTE SCHRITTE

### SOFORT BEHEBEN (vor E2E-Test):
1. **render_schemas.py**: Doppeltes fps Feld entfernen (Zeile 33 löschen)
2. **ApiClient.cs RenderRequest**: bitrate_mbps und include_audio hinzufügen
3. **video_router.py**: GET /video/clips Endpoint überprüfen (registriert?)
4. **audio_router.py**: GET /audio/clips Endpoint hinzufügen
5. **ApiClient.cs**: VideoAnalysisResult, TimelineEntry, PacingConfig ergänzen

### NACHLAGERN (funktional):
1. Waveform, Structure, Spectral, Scenes, Motion Aufrufe in C# hinzufügen
2. Preview-Generation in C# implementieren
3. Project-Info in Workflows integrieren

---

## KONSISTENZ-PRÜFUNG ABGELESEN: NICHT BESTANDEN ✗

**Status**: 15 Fehler gefunden
- 4 Kritisch (keine E2E Tests möglich)
- 9 Wichtig (Test läuft, aber Features nicht vollständig)
- 2 Minor (Optimierungen)
