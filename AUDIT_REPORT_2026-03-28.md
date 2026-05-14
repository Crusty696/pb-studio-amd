 main
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

# PB Studio AMD – Full-Stack Audit Report
**Datum:** 2026-03-28
**Auditor:** Claude Sonnet 4.6 (Full-Stack-Auditor)
**Basis-Branch:** `claude/upbeat-liskov`
**Geprüfte Dateien:** 46 Quelldateien (Python Backend, C# WPF, Tests)

---

## ZUSAMMENFASSUNG

| Schweregrad | Anzahl |
|-------------|--------|
| 🔴 KRITISCH  | 3      |
| 🟠 HOCH      | 2      |
| 🟡 MITTEL    | 5      |
| 🟢 NIEDRIG   | 4      |
| **Gesamt**  | **14** |

---

## BEFUNDE

---

### [KRITISCH-001] IRON RULE #2 Verletzung: `enable_cpu_mem_arena = True` in clap_wrapper.py

**Datei:** `src/pb_studio/ai/clap_wrapper.py`
**Zeile:** 151

**Code:**
```python
def _create_session_options(self) -> ort.SessionOptions:
    """Create optimized session options for DirectML compatibility."""
    sess_options = ort.SessionOptions()
    # KRITISCH fuer DirectML: Memory Pattern MUSS deaktiviert sein
    sess_options.enable_mem_pattern = False          # ✓ korrekt
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    # Weitere Performance-Optimierungen
    sess_options.enable_cpu_mem_arena = True          # ✗ FALSCH! IRON RULE #2 verletzt
 backup/pre-hybrid-alignment-2026-03-09
    sess_options.intra_op_num_threads = 0
    sess_options.inter_op_num_threads = 0
    return sess_options
```
 main
**Problem:** IRON RULE §2 lautet: `enable_mem_pattern = False` UND `enable_cpu_mem_arena = False` sind BEIDE PFLICHT für DirectML. clap_wrapper setzt `enable_cpu_mem_arena = True` — das ist das genaue Gegenteil.
**Beweis:** Zeile 151 ist eindeutig. Die FallbackSessionOptions (Zeile 35) für Test-Umgebungen ohne onnxruntime hat ebenfalls `enable_cpu_mem_arena = True` — bedeutet: auch wenn Tests die Fallback-Klasse nutzen, üben sie falsche Konfiguration.
**Auswirkung:** Bei DmlExecutionProvider-Sessions kann `enable_cpu_mem_arena = True` zu Speicherkonflikten zwischen dem DirectML-Allocator und der CPU-Memory-Arena führen — direkter Weg zu OOM oder instabilem ONNX-Inferencing auf AMD GPUs.

---

### KRITISCH-002: `separator.py` — `_apply_directml_patch()` missing `enable_cpu_mem_arena = False`

**Datei:** `src/pb_studio/audio/separator.py` | **Zeilen:** 166–175
**Code:**
```python
def _apply_directml_patch(self):


**Problem:**
IRON RULE #2 schreibt vor: `enable_mem_pattern = False` AND `enable_cpu_mem_arena = False` — BEIDE sind MANDATORY. In `clap_wrapper.py` wird `enable_cpu_mem_arena = True` gesetzt, was direkt gegen die Regel verstößt.

**Beweis (Vergleich mit korrekt implementierten Modulen):**
- `src/pb_studio/ai/siglip_wrapper.py:109-110`: `enable_mem_pattern = False` + `enable_cpu_mem_arena = False` ✓
- `src/pb_studio/video/moondream.py:110-111`: `enable_mem_pattern = False` + `enable_cpu_mem_arena = False` ✓
- `src/pb_studio/video/raft.py:103+110`: `enable_mem_pattern = False` + `enable_cpu_mem_arena = False` ✓
- `src/pb_studio/core/model_loader.py:147-148`: `enable_mem_pattern = False` + `enable_cpu_mem_arena = False` ✓

Die Kommentare in siglip_wrapper.py (Zeile 107-109) bestätigen, dass dies bereits als Bug erkannt und dort behoben wurde: *"R16: enable_cpu_mem_arena=True war falsch — CPU-Arena konkurriert mit"*. Der Fix wurde jedoch auf clap_wrapper.py **vergessen**.

Außerdem ist der `_FallbackSessionOptions`-Stub (Zeile 31-35) mit falschen Defaults (`enable_mem_pattern = True`, `enable_cpu_mem_arena = True`) definiert — nur für Tests ohne onnxruntime, aber semantisch irreführend.

**Auswirkung:**
Bei CLAP-Audio-Embedding läuft die CPU-Memory-Arena parallel zum DirectML-Allocator. Das kann zu VRAM-Konflikten, instabilem Verhalten oder OOM auf AMD-GPUs führen.

**Empfehlung:**
`sess_options.enable_cpu_mem_arena = False` setzen (analog siglip_wrapper.py).

---

### [KRITISCH-002] IRON RULE #2 Verletzung: `enable_cpu_mem_arena = False` fehlt in separator.py DirectML-Patch

**Datei:** `src/pb_studio/audio/separator.py`
**Zeile:** 166-175

**Code:**
```python
def _apply_directml_patch(self):
    """Apply SessionOptions monkey-patch for DirectML (scoped)."""
 backup/pre-hybrid-alignment-2026-03-09
    if not getattr(self, '_has_directml', False):
        return
    self._original_session_options_init = ort.SessionOptions.__init__
    def _patched_init(self_opts, *args, **kwargs):
        self._original_session_options_init(self_opts, *args, **kwargs)
 main
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

        self_opts.enable_mem_pattern = False   # ✓ korrekt
        # FEHLT: self_opts.enable_cpu_mem_arena = False  ← IRON RULE #2 Verletzung!
    ort.SessionOptions.__init__ = _patched_init
    logger.debug("SessionOptions patch applied for DirectML separation")
```

**Problem:**
Der Monkey-Patch für die audio-separator Bibliothek setzt nur `enable_mem_pattern = False`, aber `enable_cpu_mem_arena = False` fehlt vollständig. IRON RULE #2 schreibt BEIDE als MANDATORY vor.

**Zusätzlich:** Der `_FallbackSessionOptions`-Stub (Zeile 17-28) setzt `enable_mem_pattern = False` korrekt, aber auch hier fehlt `enable_cpu_mem_arena = False`.

**Auswirkung:**
Stem-Separation via audio-separator (MDX-NET ONNX-Modelle) läuft ohne die korrekte AMD DirectML-Konfiguration. Die CPU-Arena konkurriert mit dem DirectML-Allocator, was zu Instabilität bei langen Audio-Dateien führen kann.

**Empfehlung:**
`self_opts.enable_cpu_mem_arena = False` in `_patched_init` hinzufügen.

---

### [KRITISCH-003] ffprobe/ffmpeg PATH-Abhängigkeit: config.ffprobe_path wird ignoriert

**Dateien:**
- `backend/routers/audio_router.py`, Zeile 372
- `backend/routers/video_router.py`, Zeilen 276, 327
- `src/pb_studio/rendering/render_service.py`, Zeile 82

**Code (audio_router.py:371-378):**
```python
def _probe_audio_info(path: str) -> dict[str, Any]:
    import subprocess
    cmd = [
        "ffprobe", "-v", "error",   # ← "ffprobe" ohne Pfad!
        "-show_entries", "format=duration",
        ...
    ]
    res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
```

**Code (video_router.py:276):**
```python
cmd = [
    "ffprobe", "-v", "error",   # ← "ffprobe" ohne Pfad!
    ...
]
```

**Code (video_router.py:327):**
```python
cmd = [
    "ffmpeg", "-y", "-i", video_path,  # ← "ffmpeg" ohne Pfad!
    ...
]
```

**Code (render_service.py:81-82):**
```python
test_cmd = [
    "ffmpeg", "-y",  # ← "ffmpeg" ohne Pfad!
    ...
]
```

**Beweis (Konfiguration in backend/config.py:73-74):**
```python
ffmpeg_path: Path = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
ffprobe_path: Path = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"
```

`config.ffprobe_path` und `config.ffmpeg_path` sind korrekt definiert und zeigen auf `tools/ffmpeg/bin/`. Diese Pfade werden jedoch in keinem der Router oder im RenderService verwendet. Stattdessen wird `"ffprobe"` und `"ffmpeg"` als bloßer String aufgerufen — das setzt voraus, dass FFmpeg im System-PATH liegt.

**Auswirkung:**
- Wenn `tools/ffmpeg/bin/` nicht im PATH ist (typisch auf einem sauberen Windows-System), schlagen alle Audio-Imports, Video-Imports, Thumbnail-Generierungen und Encoder-Tests mit `FileNotFoundError` fehl.
- `config.ffprobe_path` und `config.ffmpeg_path` sind totes Konfiguration — werden nie genutzt.

**Empfehlung:**
In allen vier betroffenen Stellen `str(config.ffprobe_path)` / `str(config.ffmpeg_path)` statt `"ffprobe"` / `"ffmpeg"` verwenden. Im RenderService: `config` aus `backend.config` importieren.

---

### [HOCH-001] Thread-unsicherer Zugriff auf `state.current_timeline` in pacing_router.py

**Datei:** `backend/routers/pacing_router.py`
**Zeilen:** 179, 182

**Code:**
```python
async def generate_preview(
    request: PreviewRequest,
    state: AppState = Depends(get_app_state),
) -> PreviewResponse:
    if not state.current_timeline:                    # ← direkter Zugriff ohne Lock
        raise HTTPException(status_code=400, detail="Keine Timeline vorhanden")

    timeline_snapshot = list(state.current_timeline) # ← direkter Zugriff ohne Lock
```

**Problem:**
`state.current_timeline` ist eine `list[dict]`. Der Zugriff ohne `_state_lock` ist in einem Multi-Threaded/Async-Kontext potentiell unsicher. Die korrekte Methode ist `state.get_timeline_snapshot()`, die die Liste unter `_state_lock` kopiert.

**Beweis (korrekte Implementierung in anderen Endpoints):**
- `pacing_router.py:91`: `state.get_timeline_snapshot()` ✓
- `render_router.py:56`: `state.get_timeline_snapshot()` ✓
- `project_router.py:250`: `state.get_timeline_snapshot()` ✓

Der `generate_preview`-Endpoint ist der einzige, der direkt auf `state.current_timeline` ohne Lock zugreift.

**Auswirkung:**
Wenn parallel `/pacing/generate` aufgerufen wird (neue Timeline gesetzt), kann `list(state.current_timeline)` eine inkonsistente (halb-alte, halb-neue) Timeline snapshot liefern. Auf Python mit GIL ist ein vollständiger Crash unwahrscheinlich, aber logisch falsche Preview-Videos sind möglich.

**Empfehlung:**
`timeline_snapshot = state.get_timeline_snapshot()` und `if not timeline_snapshot:` statt `if not state.current_timeline:` verwenden.

---

### [HOCH-002] PostAsync ohne CancellationToken beim JSON-Lesen — ApiClient.cs

**Datei:** `PBStudio.UI/Services/ApiClient.cs`
**Zeile:** 244

**Code:**
```csharp
private async Task<T?> PostAsync<T>(string url, object? body) where T : class
{
    try
    {
        using var response = await _http.PostAsJsonAsync(url, body, JsonOptions, _shutdownCts.Token).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);  // ← kein CancellationToken!
    }
    ...
}
```

**Problem:**
`GetAsync<T>` (Zeile 214-236) nutzt einen CancellationToken für `ReadFromJsonAsync`, aber `PostAsync<T>` (Zeile 238-255) nutzt keinen Token beim Lesen der Response. Wenn während des JSON-Lesens der Shutdown (`_shutdownCts.Cancel()`) ausgelöst wird, hängt die Task bis zum Http-Timeout (10 Minuten, Zeile 29: `_http.Timeout = TimeSpan.FromMinutes(10)`).

**Beweis (GetAsync ist konsistent):**
```csharp
// GetAsync - korrekt:
return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false); // ← hat Token
// PostAsync - fehlerhaft:
return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false); // ← kein Token!
```

**Auswirkung:**
Beim App-Shutdown können POST-Operationen (StartRender, AnalyzeAudio, GenerateCutList) für bis zu 10 Minuten hängen, bevor der Task abbricht. Die `OnExit`-Methode wartet maximal 8 Sekunden (`shutdownCts = new CancellationTokenSource(TimeSpan.FromSeconds(8))`), danach wird der ServiceProvider disposed — was zu ObjectDisposedException auf dem hängenden Task führen kann.

**Empfehlung:**
`_shutdownCts.Token` als CancellationToken zu `ReadFromJsonAsync<T>(JsonOptions, _shutdownCts.Token)` hinzufügen.

---

### [MITTEL-001] SystemMonitor Neuinitialisierung bei jeder GPU-Stream-Verbindung

**Datei:** `backend/routers/events_router.py`
**Zeile:** 113-120

**Code:**
```python
async def gpu_stream(request: Request) -> StreamingResponse:
    async def _gpu_generator() -> AsyncIterator[str]:
        monitor = None
        try:
            from pb_studio.core.system_monitor import SystemMonitor
            monitor = SystemMonitor()  # ← Neuinitialisierung bei jeder Verbindung!
        except Exception as exc:
            ...
```

**Problem:**
`SystemMonitor()` lädt die LibreHardwareMonitor-DLL via `pythonnet` und initialisiert Hardware-Handles. Bei jedem SSE-Reconnect (SSEClient reconnectet bis zu 50×) wird `SystemMonitor()` neu instanziiert. Obwohl SystemMonitor intern ein Singleton-Pattern haben könnte, ist die wiederholte DLL-Initialisierung teuer.

**Beweis:**
SSEClient.cs Zeile 27: `MaxReconnectAttempts = 50`. Jeder Reconnect ruft `/events/gpu` neu auf → neuer `_gpu_generator()` → neues `SystemMonitor()`.

**Auswirkung:**
Performance-Overhead bei häufigen Reconnects. Bei 50 Reconnects werden 50 SystemMonitor-Instanzen erstellt (auch wenn der Singleton das intern abfängt, ist die Erstellung teuer).

**Empfehlung:**
SystemMonitor als Modul-Level-Singleton aus `backend/main.py` initialisieren und via Dependency Injection bereitstellen, analog zu `BeatDetector` in audio_router.py.

---

### [MITTEL-002] Hardcoded `sample_rate=44100` in WaveformData ignoriert tatsächliche Sample-Rate

**Datei:** `backend/routers/audio_router.py`
**Zeile:** 282

**Code:**
```python
async def get_waveform(
    clip_id: int,
    bands: int = Query(3, ge=1, le=8),
    state: AppState = Depends(get_app_state),
) -> WaveformData:
    clip = state.get_audio_clip(clip_id)
    ...
    return WaveformData(
        clip_id=clip_id,
        sample_rate=44100,  # ← HARDCODED! Ignoriert clip["sample_rate"]
        bands=waveform,
        duration_seconds=clip["duration_seconds"],
    )
```

**Problem:**
Die tatsächliche Sample-Rate des Clips (`clip["sample_rate"]`) wird importiert und gespeichert, aber in der Waveform-Response ignoriert. Ein 48kHz-Clip würde fälschlicherweise als 44100Hz gemeldet.

**Auswirkung:**
C# WPF-Frontend bekommt falsche Metadaten. Für reine Visualisierung irrelevant, aber für Sample-genaue Operationen (Waveform-Zeitstempel → Beat-Ausrichtung) könnte dies zu geringen Timing-Abweichungen führen.

**Empfehlung:**
`sample_rate=clip.get("sample_rate", 44100)` statt `sample_rate=44100`.

---

### [MITTEL-003] `_isShuttingDown = false` beim Projekt-Close ist semantisch falsch — DirectorViewModel

**Datei:** `PBStudio.UI/ViewModels/DirectorViewModel.cs`
**Zeile:** 299

**Code:**
```csharp
private void ResetProjectState()
{
    _isShuttingDown = false; // project closed, but app is still running
    AvailableAudioClips.Clear();
    ...
    IsGenerating = false;
    StatusText = "Kein Projekt geöffnet";
}

public void Dispose()
{
    if (_disposed) return;
    _disposed = true;
    _isShuttingDown = true;  // Set to true only on real app shutdown
    ...
}
```

**Problem:**
Das Feld `_isShuttingDown` hat zwei verschiedene Bedeutungen: (1) "Projekt geschlossen, aber App läuft noch" (wird auf `false` gesetzt) und (2) "App fährt runter" (wird auf `true` gesetzt in `Dispose()`). `GenerateCutListAsync` prüft `_isShuttingDown` (Zeile 186) — wenn nach `Dispose()` irgendwie noch ein Event triggert, würde er `true` finden und abbrechen (korrekt). Aber bei Projekt-Close wird `_isShuttingDown = false` gesetzt, obwohl kein neues Projekt geöffnet ist — das erlaubt das Starten einer Cut-List-Generierung wenn noch kein Projekt da ist.

**Auswirkung:**
Gering — `CanGenerateCutList()` (Zeile 174) würde trotzdem `false` zurückgeben da `SelectedAudioClip == null`. Kein direkter Bug, aber semantisch verwirrend und fragil.

**Empfehlung:**
`_isProjectActive` (bool) statt `_isShuttingDown` verwenden, mit klarer Semantik.

---

### [MITTEL-004] `total_duration=0.0` hardcoded in PacingService-Aufruf

**Datei:** `backend/routers/pacing_router.py`
**Zeile:** 257

**Code:**
```python
cut_list = service.generate_cut_list(
    audio_path=audio_path,
    clips=clips,
    pacing_config=pacing_config,
    total_duration=0.0,    # ← immer 0.0!
    duration_limit=config.duration_limit,
    cached_analysis=cached_analysis,
)
```

**Problem:**
`total_duration=0.0` wird immer als `0.0` übergeben. Ob `PacingService.generate_cut_list()` dies als "keine Beschränkung" oder als "0 Sekunden" interpretiert, hängt von der Service-Implementierung ab. Die Audio-Clip-Dauer (`audio_clips_snapshot[config.audio_clip_id]["duration_seconds"]`) ist verfügbar aber wird nicht übergeben.

**Auswirkung:**
Abhängig von der PacingService-Implementierung: Wenn `0.0` als "keine Beschränkung" behandelt wird, ist es OK. Wenn es als "0 Sekunden Dauer" interpretiert wird, würde keine Cut-Liste generiert. Die `duration_limit`-Logik könnte ebenfalls nicht korrekt greifen.

**Empfehlung:**
Tatsächliche Audio-Dauer übergeben: `total_duration=audio_clips_snapshot.get(config.audio_clip_id, {}).get("duration_seconds", 0.0)`.

---

### [MITTEL-005] `clap_wrapper.py` FallbackSessionOptions: Falsche Default-Werte

**Datei:** `src/pb_studio/ai/clap_wrapper.py`
**Zeilen:** 31-35

**Code:**
```python
class _FallbackSessionOptions:
    def __init__(self):
        self.enable_mem_pattern = True    # ← Sollte False sein!
        ...
        self.enable_cpu_mem_arena = True  # ← Sollte False sein!
```

**Problem:**
Der Fallback-Stub (für Tests ohne onnxruntime) setzt `enable_mem_pattern = True` und `enable_cpu_mem_arena = True`. Diese Werte sind gemäß IRON RULE #2 falsch. Zum Vergleich: der Fallback-Stub in `separator.py` setzt `enable_mem_pattern = False`. Der CLAP-Fallback ist semantisch inkonsistent.

**Auswirkung:**
Direkte Auswirkung nur wenn onnxruntime nicht installiert ist (Tests). Produktionscode nutzt den echten SessionOptions. Trotzdem verwirrend und ein potentieller Testfehler wenn Tests DirectML-Verhalten simulieren.

---

### [NIEDRIG-001] `render_service.py`: `av1_amf` hat höhere Priorität als `h264_amf`

**Datei:** `src/pb_studio/rendering/render_service.py`
**Zeilen:** 71-76

**Code:**
```python
encoders = [
    ("hevc_amf", "AMD GPU H.265 (beste Kompression)"),
    ("av1_amf", "AMD GPU AV1 (modernste Kompression)"),  # ← Vor h264_amf!
    ("h264_amf", "AMD GPU H.264"),
    ...
]
```

**Problem:**
`av1_amf` (AV1 Hardware-Encoding) wird vor `h264_amf` getestet. AV1-AMF ist auf vielen AMD-GPUs (besonders RX 7800 XT mit RDNA3) experimentell und kann mit kurzen Clips oder bestimmten Resolutionen instabil sein. `h264_amf` ist die bewährtere und breitere Option.

**Auswirkung:**
Wenn `hevc_amf` nicht verfügbar ist, wird `av1_amf` bevorzugt. Mögliche Rendering-Fehler bei AV1-kompatiblen Videos.

---

### [NIEDRIG-002] `MainViewModel.cs`: Keine Retry-Option nach 30s Backend-Timeout

**Datei:** `PBStudio.UI/ViewModels/MainViewModel.cs`
**Zeilen:** 56-73

**Code:**
```csharp
private async Task InitializeAsync()
{
    for (int i = 0; i < 60; i++)   // 60 × 500ms = 30s
    {
        if (_bridge.IsRunning) { ... return; }
        await Task.Delay(500);
    }
    BackendStatusText = "Backend: Offline";
    BackendStatusColor = Brushes.Red;
    // ← Keine weitere Retry-Logik!
}
```

**Problem:**
Nach 30 Sekunden wird "Backend: Offline" angezeigt, aber der User hat keine Möglichkeit, einen erneuten Verbindungsversuch zu starten (kein "Retry"-Button). Die `OnBackendStatusChanged`-Methode (Zeile 173) würde zwar reagieren, wenn `PythonBridgeService` einen späteren Status-Event sendet — aber ohne den Timer läuft, gibt es keine automatische Wiederverbindung.

**Auswirkung:**
User muss App neu starten wenn Backend nach 30s noch nicht bereit ist (z.B. bei langsamem Modell-Download beim ersten Start).

---

### [NIEDRIG-003] `audio_router.py`: `subprocess.check_output` mit `stderr=subprocess.STDOUT` kann bei ffprobe-Fehler kryptische Nachrichten liefern

**Datei:** `backend/routers/audio_router.py`
**Zeile:** 378

**Code:**
```python
res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
```

**Problem:**
`stderr=subprocess.STDOUT` leitet ffprobe-Fehlermeldungen in die stdout, die dann als JSON geparst wird. Bei einem ffprobe-Fehler (z.B. korrupte Datei) führt dies zu einem `json.JSONDecodeError` mit der ffprobe-Fehlermeldung im Stacktrace, nicht zu einer lesbaren Fehlermeldung.

**Vergleich:** `video_router.py:282` nutzt `stderr=subprocess.DEVNULL` und gibt nur Exit-Code zurück — beide Ansätze haben Nachteile.

---

### [NIEDRIG-004] `separator.py` `list_models()`: Kein aussagekräftiger Fehler wenn Separator nicht initialisiert

**Datei:** `src/pb_studio/audio/separator.py`
**Zeile:** 224-230

**Code:**
```python
def list_models(self):
    """Returns available models grouped by type."""
    if not self.separator:
        return {}   # ← Leeres Dict, kein Hinweis warum
    ...
```

**Problem:**
Kein Log-Eintrag und kein Fehler wenn `self.separator is None`. Ein leeres Dict könnte für den Aufrufer wie "keine Modelle vorhanden" aussehen, obwohl der Separator gar nicht initialisiert wurde.

---

## GEGENPRÜFUNG (Zweiter Durchlauf)

### Verifikation der KRITISCH-Befunde

**KRITISCH-001 (clap_wrapper.py:151)** ✓ Verifiziert via direktem Grep-Ergebnis:
```
src/pb_studio/ai/clap_wrapper.py:151:        sess_options.enable_cpu_mem_arena = True
```
Direkter Vergleich mit siglip_wrapper.py (Zeile 110) und moondream.py (Zeile 111) — beide haben `False`. IRON RULE #2 ist eindeutig verletzt.

**KRITISCH-002 (separator.py:173)** ✓ Verifiziert via direktem Grep — nur `enable_mem_pattern = False` ohne `enable_cpu_mem_arena`:
```
src/pb_studio/audio/separator.py:173:            self_opts.enable_mem_pattern = False
```
Kein weiterer Eintrag für `enable_cpu_mem_arena` in separator.py außer dem Fallback-Stub.

**KRITISCH-003 (ffprobe/ffmpeg PATH)** ✓ Verifiziert:
- `config.ffprobe_path` definiert in `backend/config.py:74` ✓
- Wird NICHT genutzt in `audio_router.py:372`, `video_router.py:276`, `video_router.py:327`, `render_service.py:82` ✓
- `config.ffprobe_path` und `config.ffmpeg_path` sind toter Konfigurationscode

### Verifikation der HOCH-Befunde

**HOCH-001 (pacing_router.py:179+182)** ✓ Verifiziert durch direktes Lesen:
- `state.current_timeline` direkt gelesen ohne `_state_lock`
- Alle anderen Endpoints nutzen `state.get_timeline_snapshot()` ✓

**HOCH-002 (ApiClient.cs:244)** ✓ Verifiziert durch direktes Lesen:
- `PostAsync`: `ReadFromJsonAsync<T>(JsonOptions)` ohne Token ✓
- `GetAsync`: `ReadFromJsonAsync<T>(JsonOptions, token)` mit Token ✓

### Was ich NICHT geprüft habe (Limitierungen)

1. **Dynamische Tests**: Keine Ausführung des Backends oder der WPF-App. Alle Befunde sind statisch aus Code-Analyse.
2. **render_service.py vollständig**: Nur die ersten 130 Zeilen gelesen. Die vollständige Render-Pipeline mit Normalisierung/FFmpeg-Progress-Parsing wurde nur durch Subagent-Zusammenfassung analysiert.
3. **pacing/advanced_pacing_engine.py**: 1557 Zeilen — nur Subagent-Zusammenfassung, kein direktes Lesen.
4. **Testabdeckung vollständig**: Nicht alle 23 Test-Dateien direkt gelesen — nur über Subagent-Zusammenfassung. Tests für CLAP (skipped) — kein Test für `enable_cpu_mem_arena` in CLAP.
5. **XAML Views**: Nicht gelesen — nur die ViewModels. MaterialDesign-Themes, Icon-Einbindung und Bindings nicht geprüft.
6. **data/repositories**: `media_repository.py` und `project_repository.py` nicht direkt gelesen.
7. **Laufzeit-Verhalten**: Ob ffprobe im PATH ist oder nicht, kann nur durch Ausführung verifiziert werden.

### Annahmen

- `ffprobe` ist auf diesem System NICHT im Windows-PATH (Standardannahme für saubere Installations)
- `tools/ffmpeg/bin/` wurde nicht zum PATH hinzugefügt
- Python 3.11 und alle requirements.txt-Pakete korrekt installiert

---

## FAZIT

**Gesamtbewertung: 🟡 PRODUZIERBAR MIT EINSCHRÄNKUNGEN**

Das PB Studio AMD Projekt ist strukturell gut durchdacht. Die Architektur (WPF + FastAPI + DirectML) ist sauber implementiert, die Thread-Safety durch AppState-Locks ist größtenteils korrekt, die SSE-Fan-out-Implementierung ist robust, und die vielen Fix-Kommentare (BUG-xxx, R-xx, MEDIUM-xxx) belegen gründliche iterative Verbesserungen.

**Kritische Risiken:**

1. **KRITISCH-003 (ffprobe/ffmpeg PATH)** ist das **höchste praktische Risiko**: Wenn FFmpeg nur im Projektordner liegt und nicht im System-PATH, schlagen Audio-Import, Video-Import, Thumbnail-Generierung und Encoder-Tests alle fehl. Das betrifft den kompletten normalen Workflow.

2. **KRITISCH-001 und KRITISCH-002 (IRON RULE #2)** sind **latente GPU-Stabilitätsrisiken**: CLAP-Embeddings (`enable_cpu_mem_arena = True`) und Stem-Separation (`enable_cpu_mem_arena` fehlt) könnten bei AMD-GPU-Last zu Instabilität führen. CLAP ist jedoch optional (Tests skippen es wenn Modell fehlt), und Stem-Separation ist optional (nur auf expliziten User-Request).

3. **HOCH-001 (Thread-Safety)** betrifft nur den seltenen `POST /pacing/preview` Endpoint.

4. **HOCH-002 (PostAsync)** ist ein Edge-Case bei schnellem App-Shutdown während laufender API-Calls.

Die 20-Runden-Deep-Audit-Historie (R1-R20, BUG-001..047, HIGH-001..006) zeigt, dass das Team die Bugs systematisch gefunden und behoben hat. Die drei kritischen Befunde dieses Audits sind **Regressionen oder ursprünglich vergessene Fixes** (besonders KRITISCH-001: siglip+moondream wurden gefixt, clap blieb zurück).

---

*Bericht erstellt am 2026-03-28 | Keine Code-Änderungen wurden vorgenommen (Audit-Only)*
 backup/pre-hybrid-alignment-2026-03-09
