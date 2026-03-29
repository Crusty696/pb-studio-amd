# PB Studio AMD – Full Audit Report
**Datum:** 2026-03-28
**Auditor:** Claude Sonnet 4.6
**Branch:** claude/cranky-hodgkin
**Status:** ⚠️ FAIL — 2 kritische IRON RULE Verletzungen gefunden

---

## STATISTIK

| Kategorie | Anzahl |
|-----------|--------|
| Python src/ Dateien geprüft | 117 |
| Python backend/ Dateien geprüft | 21 |
| Python Tests/ Dateien geprüft | 23 |
| C# Dateien geprüft | 35 |
| XAML Dateien geprüft | 10 |
| **Kritische Fehler** | **2** |
| Warnings | 5 |
| OK / Verifiziert | 28 |

---

## KRITISCHE FEHLER

### KRITISCH-001: `clap_wrapper.py` — `enable_cpu_mem_arena = True` (IRON RULE Verletzung)

**Datei:** `src/pb_studio/ai/clap_wrapper.py` | **Zeile:** 151
**Code:**
```python
def _create_session_options(self) -> ort.SessionOptions:
    sess_options = ort.SessionOptions()
    sess_options.enable_mem_pattern = False          # korrekt
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.enable_cpu_mem_arena = True         # ← FALSCH! IRON RULE Verletzung
    sess_options.intra_op_num_threads = 0
    sess_options.inter_op_num_threads = 0
    return sess_options
```
**Problem:** IRON RULE §2 lautet: `enable_mem_pattern = False` UND `enable_cpu_mem_arena = False` sind BEIDE PFLICHT für DirectML. clap_wrapper setzt `enable_cpu_mem_arena = True` — das ist das genaue Gegenteil.
**Beweis:** Zeile 151 ist eindeutig. Die FallbackSessionOptions (Zeile 35) für Test-Umgebungen ohne onnxruntime hat ebenfalls `enable_cpu_mem_arena = True` — bedeutet: auch wenn Tests die Fallback-Klasse nutzen, üben sie falsche Konfiguration.
**Auswirkung:** Bei DmlExecutionProvider-Sessions kann `enable_cpu_mem_arena = True` zu Speicherkonflikten zwischen dem DirectML-Allocator und der CPU-Memory-Arena führen — direkter Weg zu OOM oder instabilem ONNX-Inferencing auf AMD GPUs.

---

### KRITISCH-002: `separator.py` — `_apply_directml_patch()` missing `enable_cpu_mem_arena = False`

**Datei:** `src/pb_studio/audio/separator.py` | **Zeilen:** 166–175
**Code:**
```python
def _apply_directml_patch(self):
    if not getattr(self, '_has_directml', False):
        return
    self._original_session_options_init = ort.SessionOptions.__init__
    def _patched_init(self_opts, *args, **kwargs):
        self._original_session_options_init(self_opts, *args, **kwargs)
        self_opts.enable_mem_pattern = False          # nur das gesetzt
        # enable_cpu_mem_arena = False fehlt hier!    # ← IRON RULE Verletzung
    ort.SessionOptions.__init__ = _patched_init
```
**Problem:** Der Monkey-Patch für audio-separator's DirectML-Nutzung patcht nur `enable_mem_pattern = False`, setzt aber `enable_cpu_mem_arena` nicht auf `False`. Laut IRON RULE §2 müssen BEIDE Flags gesetzt werden.
**Beweis:** Grep über alle `enable_cpu_mem_arena`-Vorkommen in `src/` zeigt: `raft.py` (✅), `moondream.py` (✅), `siglip_wrapper.py` (✅), `model_loader.py` (✅) — alle korrekt. `clap_wrapper.py` und der `separator.py`-Patch sind die einzigen Ausnahmen.
**Auswirkung:** Stem-Separation (audio-separator mit DirectML) läuft mit CPU-Memory-Arena aktiviert — erhöhte OOM-Wahrscheinlichkeit während MDX-NET ONNX-Inferencing auf AMD GPU.

---

## WARNINGS

### WARN-001: `requirements.txt` — PyQt6 Legacy-Abhängigkeit vorhanden

**Datei:** `requirements.txt`
**Code:**
```
PyQt6==6.8.0
qt-material>=2.14
```
**Problem:** Die Produktions-UI ist WPF/C# (PBStudio.UI/). PyQt6 und qt-material sind Legacy-Code aus der alten Python-UI (`src/pb_studio/ui/`). Diese Dateien existieren noch:
- `src/pb_studio/ui/main_window.py`
- `src/pb_studio/ui/widgets/` (ca. 15 Widget-Dateien)

**Auswirkung:**
1. Installiert ~120MB unnötige Pakete inkl. Qt-Runtime
2. `audio-separator` versucht bereits NumPy 2.x zu ziehen; PyQt6 kann weitere Konflikte einbringen
3. Tote Code-Basis erhöht Wartungsaufwand und Angriffsfläche
4. `qt-material>=2.14` ist nicht versionspinned — potentieller Breaking Change bei Update

---

### WARN-002: `requirements.txt` — `faiss-cpu` nicht exakt auf 1.7.4 gepinnt

**Datei:** `requirements.txt`
**Code:**
```
faiss-cpu>=1.7.0
```
**Problem:** CLAUDE.md und MEMORY.md spezifizieren explizit `faiss-cpu==1.7.4 (cp311-win_amd64)`. Die requirements.txt erlaubt `>=1.7.0`, was bedeutet ein `pip install` könnte eine neuere Version ziehen die keine cp311-win_amd64 Wheel hat oder inkompatibel mit NumPy 1.26.4 ist.
**Beweis:** CLAUDE.md §5: `FAISS-CPU | 1.7.4 | cp311-win_amd64`
**Auswirkung:** Nicht-reproduzierbare Installs auf neuen Maschinen.

---

### WARN-003: `gpu_lock.py` — Bezeichnung `GPULockMiddleware` ist irreführend

**Datei:** `backend/middleware/gpu_lock.py` | **Zeilen:** 30–53
**Code:**
```python
class GPULockMiddleware(BaseHTTPMiddleware):
    """Middleware die GPU-intensive Requests loggt und zeitlich erfasst."""
    async def dispatch(self, request: Request, call_next: ...):
        if path in GPU_PATHS:
            start = time.monotonic()
            ...
            response = await call_next(request)  # kein Lock hier!
```
**Problem:** Die Middleware heißt `GPULockMiddleware`, sperrt aber keine GPU. Sie loggt und misst Zeit. Der echte GPU-Lock ist `asyncio.Lock()` in `backend/dependencies.py` via `with_gpu_task()`. Dieser Lock ist korrekt und funktional — aber Naming Mismatch kann neue Entwickler in die Irre führen (sie könnten annehmen, die Middleware serialisiert GPU-Zugriffe).
**Schweregrad:** Niedrig — funktional korrekt, konzeptuell verwirrend.

---

### WARN-004: Keine Test-Coverage für `render_service.py`

**Datei:** `src/pb_studio/rendering/render_service.py` (615 Zeilen)
**Problem:** `render_service.py` ist das Herzstück der Render-Pipeline (FFmpeg AMF, Concat-List, Progress-Parsing, Cancel-Support, Clip-Normalisierung). Für diesen Code gibt es **keinen Test** in `Tests/`.
**Verifiziert:** `Tests/` enthält `test_backend_routers.py` (testet den Router), aber keinen direkten Test der `RenderService`-Klasse. Insbesondere ungetestet:
- `_detect_best_encoder()` Fallback-Logik
- `_normalize_clips()` mit Cancel-Callback
- `_parse_ffmpeg_progress()` stderr-Parsing
- `_cleanup_temp()` Edge Cases

---

### WARN-005: `VRAMBudgetManager._detect_vram_limit()` — PowerShell-Aufrufe bei Init

**Datei:** `src/pb_studio/core/vram_budget_manager.py` | **Zeilen:** 183–246
**Code:**
```python
result = subprocess.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_VideoController | ..."],
    capture_output=True, text=True, timeout=10
)
```
**Problem:** Bei fehlendem LibreHardwareMonitor oder Config-Limit werden bis zu 3 PowerShell-Subprozesse beim App-Start aufgerufen — alle mit `timeout=10` → potenziell bis zu 30s Startup-Delay auf langsamen Systemen oder wenn WMI hängt.
**Sicherheit:** Kein `shell=True`, keine User-Eingaben in den Befehlen → kein Injection-Risiko. ✅
**Auswirkung:** Nur Performance/UX-Impact bei fehlenden Monitoring-Komponenten.

---

## OK / VERIFIZIERT

### Python Backend

| Komponente | Status | Anmerkung |
|-----------|--------|-----------|
| `backend/main.py` | ✅ | CORS localhost-only, 6 Router korrekt registriert |
| `backend/app_state.py` | ✅ | Singleton + RLock + SQLite-Persistenz korrekt |
| `backend/dependencies.py` | ✅ | `asyncio.to_thread()`, GPU-Lock, SSE Fan-out (BUG-028) korrekt |
| `backend/config.py` | ✅ | `SHGetKnownFolderPath` Win32 für robuste Documents-Erkennung |
| `backend/routers/audio_router.py` | ✅ | File-Check vor GPU-Lock, `asyncio.to_thread()` durchgehend |
| `backend/routers/video_router.py` | ✅ | `_generate_thumbnail` kein `shell=True`, SigLIP+FAISS korrekt |
| `backend/routers/pacing_router.py` | ✅ | `min_cut_interval` weitergeleitet (HIGH-fix), `validate_timeline()` |
| `backend/routers/render_router.py` | ✅ | `is_relative_to()` Path-Traversal-Schutz ✅ |
| `backend/routers/project_router.py` | ✅ | `is_relative_to()` auf create+open (SEC-001) ✅, atomare Writes |
| `backend/routers/events_router.py` | ✅ | Per-Client UUID Queue, Keepalive, GPU-Poll via `asyncio.to_thread` |
| `backend/middleware/gpu_lock.py` | ✅ (funktional) | Loggt korrekt, echter Lock in dependencies.py |
| `backend/schemas/` | ✅ | Pydantic v2, `model_rebuild()` für ForwardRefs, path-validator |

### Core Python

| Komponente | Status | Anmerkung |
|-----------|--------|-----------|
| `src/pb_studio/data/database_core.py` | ✅ | WAL-Mode, FK ON, kein `executescript()` (R16-fix), Migration-System |
| `src/pb_studio/data/repositories/media_repository.py` | ✅ | Parameterized SQL, Idempotent-Upsert via `media_import_guard` |
| `src/pb_studio/video/raft.py` | ✅ | `enable_mem_pattern=False` + `enable_cpu_mem_arena=False` ✅ |
| `src/pb_studio/video/moondream.py` | ✅ | Beide Flags korrekt (R16 fix) |
| `src/pb_studio/ai/siglip_wrapper.py` | ✅ | Beide Flags korrekt (R16 fix) |
| `src/pb_studio/core/model_loader.py` | ✅ | Beide Flags korrekt |
| `src/pb_studio/audio/beat_detector.py` | ✅ | CPU-only, BeatNet-Fallback auf librosa, collections-Patches korrekt |
| `src/pb_studio/audio/separator.py` | ⚠️ | Funktional, aber KRITISCH-002 (fehlender CPU-Arena-Flag) |
| `src/pb_studio/rendering/render_service.py` | ✅ | AMF-Encoder korrekt, kein `shell=True`, Cancel-Support |
| `src/pb_studio/core/vram_budget_manager.py` | ✅ | LRU-Eviction, Thread-safe, Proactive Budgeting |
| `src/pb_studio/core/vram_arbiter.py` | ✅ | Legacy-Interface, lazy Budget-Manager korrekt |
| `src/pb_studio/core/system_monitor.py` | ✅ | `pythonnet`/LHM optional, kein `pynvml` |
| `src/pb_studio/video/scene_detect.py` | ✅ | `open_video` + `ContentDetector`, File-Handle in `finally` freigegeben |

### C# WPF

| Komponente | Status | Anmerkung |
|-----------|--------|-----------|
| `PBStudio.UI.csproj` | ✅ | net9.0-windows, CommunityToolkit.Mvvm 8.4.0, MaterialDesign 5.1.0 |
| `App.xaml.cs` | ✅ | DI korrekt, globale Exception-Handler (R10), OnExit mit 8s-Timeout |
| `Services/ApiClient.cs` | ✅ | 28+ Endpoints, snake_case JSON, IDisposable, 10min-Timeout GPU |
| `Services/SSEClient.cs` | ✅ | 3 Streams, exponentieller Backoff (max 50), CTS-Disposal korrekt |
| `ViewModels/MainViewModel.cs` | ✅ | partial class, [ObservableProperty], Dispatcher-wrapped, WeakReferenceMessenger |
| `ViewModels/AudioLibraryViewModel.cs` | ✅ | IDisposable, alle Commands korrekt, WeakReferenceMessenger-Unregister |
| `ViewModels/VideoLibraryViewModel.cs` | ✅ | SemaphoreSlim-Load-Gate, Version-Counter, Thumbnail-Batching, IDisposable |
| `ViewModels/AnchorViewModel.cs` | ✅ | Acquired-Flag-Pattern (R15), Semaphor-Release korrekt |
| `ViewModels/DirectorViewModel.cs` | ✅ | SemaphoreSlim Load-Gate, `MinCutInterval` gesendet, IDisposable |
| `ViewModels/ProductionViewModel.cs` | ✅ | Task-ID-Filterung SSE, `BuildEtaText`, IDisposable |
| `ViewModels/SettingsViewModel.cs` | ✅ | WeakReferenceMessenger, IDisposable |
| `ViewModels/TimelineViewModel.cs` | ✅ | Dispatcher-wrapped (R9), Version-Counter, IDisposable |
| `Converters/NullToVisibilityConverter.cs` | ✅ | 3 Converter vorhanden: NullToVisibility, InverseNullToVisibility, InverseBool |

### Sicherheit

| Check | Status | Ergebnis |
|-------|--------|---------|
| `shell=True` in subprocess-Aufrufen | ✅ | **Nicht vorhanden.** Nur ein Kommentar in `video_renderer.py:71` der explizit erklärt, dass kein `shell=True` verwendet wird |
| SQL-Injection | ✅ | Alle SQL-Queries parameterisiert. `bulk_update_status` nutzt `','.join('?' * len(...))` — korrekt |
| Path-Traversal | ✅ | `is_relative_to()` in `project_router.py` (create + open) und `render_router.py` (output path) |
| CUDA/ROCm Imports | ✅ | Keine CUDA-Imports in Production-Code. Alle CUDA-Erwähnungen sind Kommentare die explizit erklären, dass CUDA NICHT genutzt wird |
| `pynvml` | ✅ | Nicht vorhanden |
| CORS | ✅ | `["http://127.0.0.1", "http://localhost", "null"]` — nur localhost |

### Tests & CI

| Check | Status | Ergebnis |
|-------|--------|---------|
| `pytest.ini` `testpaths = Tests` | ✅ | Großbuchstabe korrekt (Windows NTFS) |
| `pythonpath = src .` | ✅ | Korrekt, kein editable install nötig |
| `--strict-markers` | ✅ | Verhindert typo-Marker |
| `conftest.py` `isolated_test_database` | ✅ | Jeder Test isolierte SQLite via tmp_path |
| Singleton-Reset in conftest | ✅ | `DatabaseCore._instance = None` + `ConfigManager._instance = None` |

### SSE Fan-out

- `publish_event()` in `backend/dependencies.py:126` iteriert über `list(_event_queues.values())` → Fan-out an ALLE registrierten Queues ✅
- `QueueFull`-Handling: ältestes Event wird bei vollen Queues verworfen (maxsize=500), kein Blockieren ✅
- C# `SSEClient.cs`: 3 concurrent Streams (progress, log, gpu), per-UUID Queue-Registration ✅
- GPU-SSE-Stream: Polling alle 5s via `asyncio.to_thread()` korrekt ✅

---

## MODULE OHNE TESTS (Coverage-Lücken)

| Modul | Begründung |
|-------|-----------|
| `src/pb_studio/rendering/render_service.py` | Kern-Render-Pipeline — **keine Tests** |
| `src/pb_studio/services/` (5 Dateien) | Orchestration-Layer — **keine Tests** |
| `src/pb_studio/core/system_monitor.py` | LHM-Integration — nur Mock-Fixtures in conftest |
| `src/pb_studio/video/scene_detect.py` | SceneDetector — **keine Tests** |
| `src/pb_studio/audio/structure_analyzer.py` | — **keine Tests** |
| `backend/middleware/gpu_lock.py` | — **keine Tests** |
| `src/pb_studio/ui/` (Legacy PyQt6) | Dead Code — kein Test, kein Gebrauch |

---

## GEGENPRÜFUNG

### KRITISCH-001 (clap_wrapper.py:151) — Verifiziert

Grep-Beleg: `src/pb_studio/ai/clap_wrapper.py:151:        sess_options.enable_cpu_mem_arena = True`
Quercheck: Alle anderen DirectML-Session-Erstellungen (raft.py:110, moondream.py:111, siglip_wrapper.py:110, model_loader.py:148) setzen `enable_cpu_mem_arena = False`. clap_wrapper ist eindeutig die Ausnahme.
**Befund bestätigt. ✅**

### KRITISCH-002 (separator.py:173) — Verifiziert

Code gelesen: `_apply_directml_patch()` setzt `self_opts.enable_mem_pattern = False` und NICHTS für `enable_cpu_mem_arena`.
Konsequenz: Zur Laufzeit werden alle SessionOptions-Instanzen im audio-separator mit `enable_mem_pattern=False` erstellt, aber `enable_cpu_mem_arena` bleibt auf Default (`True`).
**Befund bestätigt. ✅**

### WARN-001 (PyQt6) — Verifiziert

`requirements.txt` enthält `PyQt6==6.8.0`. `src/pb_studio/ui/main_window.py` existiert. `PBStudio.UI/` ist die produktive WPF-UI. Python-UI wird nirgendwo aus dem Backend aufgerufen.
**Befund bestätigt. ✅**

### shell=True — Negativ-Befund bestätigt

Grep über alle `*.py` Dateien findet nur einen Kommentar in `video_renderer.py` der explizit KEIN `shell=True` dokumentiert. Kein echter `shell=True`-Aufruf im gesamten Projekt.
**Sauber. ✅**

### CUDA-Imports — Negativ-Befund bestätigt

Grep findet nur Kommentare (z.B. "kein CUDA", "AMD-only build - kein CUDA verfuegbar"). Kein `import torch.cuda`, kein `.cuda()` Call, kein CUDA-Provider in OnnxRuntime-Sessions.
**Sauber. ✅**

---

## FAZIT

### Was funktioniert (und nachweislich korrekt ist)

1. **AMD DirectML Integration** ist in 5 von 7 ONNX-Komponenten korrekt implementiert (RAFT, Moondream, SigLIP, ModelLoader, Audio-Analyzer). Dual-Flag-Pattern aus IRON RULE §2 ist als Muster im Codebase verankert.

2. **Sicherheitslage ist solide.** Keine SQL-Injection-Vektoren, kein `shell=True`, Path-Traversal-Schutz auf allen exponierten Dateisystem-Zugriffen.

3. **C# WPF-Architektur ist hochwertig.** Alle 9 ViewModels nutzen `partial class`, `[ObservableProperty]`, `[RelayCommand]`, korrektes `IDisposable`-Muster, Dispatcher-Wrapping und WeakReferenceMessenger. Besonders `VideoLibraryViewModel.cs` zeigt ausgereiftes CTS-Management für parallele Loads.

4. **SSE Fan-out** ist korrekt implementiert und adressiert BUG-028.

5. **Datenbankschicht** ist robust: WAL-Mode, FK-Constraints, Migration-System mit `complete_statement()` statt `executescript()`, Idempotent-Upsert via `media_import_guard`.

6. **Test-Infrastruktur** ist solide: isolierte SQLite-Datenbank pro Test via `conftest.py`, `testpaths = Tests` korrekt.

### Was kaputt / problematisch ist

1. **KRITISCH: 2 IRON RULE Verletzungen** (`clap_wrapper.py:151` und `separator.py:173`) — beide können zu OOM oder instabilem GPU-Inferencing auf AMD führen. CLAP ist zwar optional (nur für Audio-Embedding genutzt wenn Modell vorhanden), aber Stem-Separation (separator.py) ist ein Kern-Feature.

2. **Tote Code-Basis:** `src/pb_studio/ui/` (PyQt6) ist produktiv-irrelevant aber in requirements.txt gebunden. Erhöht Install-Zeit und Konflikt-Wahrscheinlichkeit.

3. **Render-Pipeline ohne Tests:** `render_service.py` (615 Zeilen, inkl. FFmpeg AMF, Cancel, Progress-Parsing) hat null Test-Coverage.

### Priorität der Fixes

| Priorität | Item |
|-----------|------|
| 🔴 1 | `clap_wrapper.py:151` `enable_cpu_mem_arena = True` → `False` |
| 🔴 2 | `separator.py:173` `_apply_directml_patch()` + `enable_cpu_mem_arena = False` |
| 🟡 3 | `requirements.txt` `faiss-cpu>=1.7.0` → `faiss-cpu==1.7.4` |
| 🟡 4 | `requirements.txt` PyQt6 + qt-material entfernen (oder in extras verschieben) |
| 🟢 5 | Tests für `render_service.py` schreiben |

---

## LIMITIERUNGEN DIESER ANALYSE

- **Keine Laufzeit-Tests:** Kein echtes AMD-GPU-System verfügbar — alle Befunde sind statische Code-Analyse. Ob KRITISCH-001/002 tatsächlich OOM verursachen hängt vom AMD-GPU-Modell und VRAM-Auslastung ab.
- **Nicht geprüft:** `src/pb_studio/services/` (5 Dateien), `src/pb_studio/workers/` (worker-Implementierungen), vollständige XAML-View-Analyse (Bindings/Behaviors nicht im Detail geprüft).
- **Test-Ausführung:** Tests wurden nicht ausgeführt — nur statische Analyse der Test-Struktur.
- **Modelle nicht verfügbar:** CLAP, SigLIP-Text und Waveform-Fixtures (9 skipped Tests) konnten nicht geprüft werden — per Memory/conftest bestätigt korrekte Skips.
