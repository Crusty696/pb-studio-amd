# Full-Stack Audit: PB Studio AMD Edition
**Datum:** 2026-03-04
**Auditor:** Claude (Lead Senior Developer Role)
**Methode:** Statische Code-Analyse aller Dateien + Verkabelungs-Analyse + Schema-Vergleich
**Scope:** 233 Python-Dateien, 30 C#-Dateien, 10 XAML-Views, Datenbank-Schema, Services

---

## Executive Summary

Die App ist architekturell solide konzipiert (Hybrid WPF + FastAPI, MVVM Toolkit, DI korrekt konfiguriert). Die Python Core-Logik ist syntax-sauber (233/233 Dateien fehlerfrei). **Jedoch blockieren 3 kritische Bugs den erfolgreichen Start der Anwendung.** Zusätzlich gibt es 4 hohe und mehrere mittlere Mängel, die Kernfunktionen unbrauchbar machen.

**Gesamtbewertung: NICHT PRODUKTIONSREIF** — Phase E (dotnet build + E2E Test) wird ohne Fixes fehlschlagen.

---

## Schweregrade

| Symbol | Schweregrad | Bedeutung |
|--------|-------------|-----------|
| 🔴 | KRITISCH | Verhindert Build oder Start, Crash, Datenverlust |
| 🟠 | HOCH | Kernfunktion defekt, falsches Verhalten |
| 🟡 | MITTEL | Bug in Nebenfunktion, schlechte UX |
| 🟢 | NIEDRIG | Style, Best-Practice, Sicherheitsoptimierung |

---

## 🔴 KRITISCHE BUGS (3)

### BUG-001: `StartupUri` + DI-Konflikt → NullReferenceException beim Start

**Datei:** `PBStudio.UI/App.xaml` (Zeile 7) + `PBStudio.UI/App.xaml.cs` (Zeile 36-37)

**Problem:** `App.xaml` hat `StartupUri="MainWindow.xaml"` gesetzt. Gleichzeitig instanziiert `App.xaml.cs` via `OnStartup()` das `MainWindow` manuell über den DI-Container.

WPF-Verhalten: `StartupUri` veranlasst WPF, `MainWindow` **sofort beim App-Start** zu instanziieren — **bevor** `OnStartup()` aufgerufen wird. In `OnStartup()` wird erst `Ioc.Default.ConfigureServices(...)` ausgeführt. **Alle 8 Views** rufen in ihrem Konstruktor `Ioc.Default.GetRequiredService<T>()` auf. Da Ioc.Default noch nicht konfiguriert ist, wirft jeder View-Konstruktor eine `InvalidOperationException` (oder `NullReferenceException`).

**Nachweis:**
```xml
<!-- App.xaml, Zeile 7 - PROBLEM -->
StartupUri="MainWindow.xaml"
```
```csharp
// App.xaml.cs - OnStartup() wird NACH StartupUri aufgerufen
Ioc.Default.ConfigureServices(_serviceProvider);  // Zeile 29 - ZU SPÄT
var mainWindow = _serviceProvider.GetRequiredService<MainWindow>(); // Zeile 36
mainWindow.Show(); // Zeile 37 - Zweite Instanz!
```

**Konsequenz:** App startet nicht. Doppel-Instanziierung von MainWindow als Nebeneffekt.

**Fix (einzeilig):** `StartupUri="MainWindow.xaml"` aus `App.xaml` entfernen.

---

### BUG-002: `Resources/app.ico` fehlt → `dotnet build` Fehler

**Datei:** `PBStudio.UI/PBStudio.UI.csproj` (Zeile 9) + `PBStudio.UI/Resources/` (Ordner leer)

**Problem:** Die `.csproj`-Datei referenziert `<ApplicationIcon>Resources\app.ico</ApplicationIcon>`. Der `Resources/`-Ordner existiert, ist aber **vollständig leer** — `app.ico` fehlt.

**Nachweis:**
```
$ ls PBStudio.UI/Resources/
(leer)
```
```xml
<ApplicationIcon>Resources\app.ico</ApplicationIcon>
```

**Konsequenz:** `dotnet build` schlägt mit `MSB3030: Could not copy the file "Resources\app.ico"` oder äquivalentem Fehler fehl. Phase E scheitert beim ersten Build.

**Fix:** Entweder `app.ico` in `Resources/` ablegen oder `<ApplicationIcon>` aus `.csproj` entfernen.

---

### BUG-003: `requirements.txt` fehlt Backend-Abhängigkeiten → Backend startet nicht

**Datei:** `requirements.txt` (Root-Verzeichnis)

**Problem:** Die `requirements.txt` enthält ausschließlich Abhängigkeiten der alten PyQt6-Oberfläche und der Core-Bibliotheken. Die **FastAPI Backend-Abhängigkeiten fehlen vollständig**.

**Fehlende Pakete (verifiziert durch Import-Analyse aller Backend-Dateien):**

| Paket | Genutzt in | Kritikalität |
|-------|------------|--------------|
| `fastapi` | `backend/main.py`, alle Router | Ohne App kein Backend |
| `uvicorn` | `backend/main.py` (Startup) | Ohne Server kein Start |
| `pydantic-settings` | `backend/config.py` (BaseSettings) | Config-Klasse nicht importierbar |

**Nachweis:**
```python
# backend/config.py, Zeile 1
from pydantic_settings import BaseSettings  # ← pydantic-settings NICHT in requirements.txt
```

**Konsequenz:** `pip install -r requirements.txt` installiert ein nicht startfähiges Backend. Jeder Neuaufbau der Umgebung schlägt fehl.

**Fix:** `fastapi>=0.110.0`, `uvicorn[standard]>=0.28.0`, `pydantic-settings>=2.0.0` zu `requirements.txt` hinzufügen.

---

## 🟠 HOHE BUGS (4)

### BUG-004: Type-Mismatch `AudioAnalysisResult.energy_curve` → Deserialisierungsfehler

**Datei:** `backend/schemas/audio_schemas.py` (Zeile 48) + `PBStudio.UI/Services/ApiClient.cs` (Zeile 167)

**Problem:** Python sendet `energy_curve: list[float]` (ein Array von Float-Werten). C# erwartet `string? EnergyProfile` (ein optionaler String).

```python
# Python (AudioAnalysisResult)
energy_curve: list[float] = []   # z.B. [0.1, 0.3, 0.85, ...]
```
```csharp
// C# Record
public record AudioAnalysisResult(..., string? EnergyProfile = null);
// System.Text.Json versucht list<float> als string zu deserialisieren → Exception oder null
```

**Konsequenz:** Die JSON-Deserialisierung schlägt fehl oder ignoriert `energy_curve` komplett. Der `AudioAnalysisViewModel` kann die Energy-Kurve nicht darstellen.

**Fix:** C# Record anpassen: `List<float>? EnergyCurve = null` statt `string? EnergyProfile`.

---

### BUG-005: `/events/log` SSE-Stream ist tot (Queue nie befüllt)

**Datei:** `backend/routers/events_router.py` + `backend/dependencies.py`

**Problem:** Der `/events/log` SSE-Endpoint ruft `get_event_queue("logs")` auf. Die Funktion `publish_event()` in `dependencies.py` publiziert jedoch ausschließlich in die `"default"` Queue. Kein Router oder Service ruft je `publish_event(event, queue_name="logs")` auf.

```python
# events_router.py - wartet auf Queue "logs"
async def _log_generator():
    queue = get_event_queue("logs")   # ← Queue "logs" = immer leer

# dependencies.py - publiziert nur in "default"
async def publish_event(event: dict, queue_name: str = "default"):
    ...
```

**Konsequenz:** Der `/events/log` Endpoint wartet ewig und liefert nie Events. Implementiert aber auch nicht genutzt in C# (SSEClient verbindet sich nur mit `/events/progress`). Totes Feature.

---

### BUG-006: `RenderRequest` C# sendet `fps`, Python erwartet es nicht

**Datei:** `PBStudio.UI/Services/ApiClient.cs` (Zeile 177) + `backend/schemas/render_schemas.py` (Zeile 24-33)

**Problem:** Das C# `RenderRequest` Record enthält ein `Fps` Feld. Das Python `RenderRequest` Pydantic-Schema hat **kein `fps` Feld**. Der Client sendet FPS-Informationen, das Backend ignoriert sie vollständig und nutzt immer den Default (30 FPS via `target_fps=30` in `_execute_render()`).

```csharp
// C# - sendet fps
public record RenderRequest(string OutputPath, string AudioPath, string Quality,
    int ResolutionWidth, int ResolutionHeight, double Fps);  // Fps wird gesendet
```
```python
# Python RenderRequest - kein fps Feld
class RenderRequest(BaseModel):
    output_path: str
    audio_path: str
    quality: RenderQuality = RenderQuality.HIGH
    resolution_width: int = 1920
    resolution_height: int = 1080
    bitrate_mbps: float = 12.0
    # fps fehlt komplett
```

**Konsequenz:** Die FPS-Einstellung im WPF-Frontend hat keinen Effekt auf das Rendering. Ausgewählte FPS werden ignoriert.

---

### BUG-007: `PythonBridgeService` hat hardcoded Benutzerpfad

**Datei:** `PBStudio.UI/Services/PythonBridgeService.cs` (Zeile 17)

**Problem:** Der Python-Interpreter-Pfad ist hardcoded auf `C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe`.

```csharp
private const string PythonExe = @"C:\Users\david\AppData\Local\Programs\Python\Python311\python.exe";
```

**Konsequenz:** Die App funktioniert ausschließlich auf David Lochmanns Entwicklungsmaschine. Auf jedem anderen Windows-System (anderer Username, anderer Python-Installationspfad) startet das Backend nicht.

---

## 🟡 MITTLERE BUGS (5)

### BUG-008: `SettingsViewModel.CleanupGpuAsync()` ruft falschen Endpoint auf

**Datei:** `PBStudio.UI/ViewModels/SettingsViewModel.cs` (Zeile 48)

Der "GPU Cleanup"-Button ruft `_api.GetHealthAsync()` auf statt `_api.CleanupGpuAsync()`. Das Backend hat `/gpu/cleanup` (POST) implementiert, der C# ApiClient hat auch `PostAsync` für `/gpu/cleanup` — aber der ViewModel verbindet sich nicht korrekt.

```csharp
private async Task CleanupGpuAsync()
{
    await _api.GetHealthAsync(); // Placeholder — sollte /gpu/cleanup aufrufen
}
```

**Konsequenz:** GPU-VRAM wird nie freigegeben über die UI. Bei VRAM-Mangel ist kein Recovery möglich ohne App-Neustart.

---

### BUG-009: `AudioLibraryViewModel.AudioClips` wird nie aus Backend geladen

**Datei:** `PBStudio.UI/ViewModels/AudioLibraryViewModel.cs`

Die `AudioClips` ObservableCollection startet leer und hat **keine Methode**, um bestehende Clips vom Backend zu laden. Clips erscheinen nur, wenn sie in **derselben Session** über den MediaIngest-Tab importiert wurden. Nach App-Neustart ist die Liste immer leer, obwohl die Clips in der SQLite-Datenbank vorhanden sind.

**Konsequenz:** Der Audio-Library-Tab zeigt nach jedem Neustart eine leere Liste. Persistenz ist gebrochen.

---

### BUG-010: `DirectorViewModel.SelectedVideoClipIds` nicht über UI befüllbar

**Datei:** `PBStudio.UI/ViewModels/DirectorViewModel.cs` (Zeile 26, 48)

`SelectedVideoClipIds: ObservableCollection<int>` existiert und wird beim API-Call verwendet, aber es gibt **keine UI-Interaktion** die IDs zu dieser Collection hinzufügt. Der `GenerateCutListAsync`-Command sendet immer eine leere Video-Clip-ID-Liste.

```csharp
VideoClipIds: SelectedVideoClipIds.ToList(),  // immer []
```

**Konsequenz:** Die Pacing/Cut-List-Generierung vom Director-Tab funktioniert nie korrekt, da keine Clips ausgewählt werden können.

---

### BUG-011: `project_router.py` nutzt module-level State statt AppState Singleton

**Datei:** `backend/routers/project_router.py`

Alle anderen Router nutzen den `AppState` Singleton für Zustandsverwaltung. `project_router.py` nutzt eine module-level Variable `_current_project: dict | None = None`. Dieser State ist nicht thread-safe und wird bei einem Hot-Reload des Servers zurückgesetzt.

**Konsequenz:** Projekt-State ist inkonsistent mit dem Rest der Applikation. Bei Mehrfachzugriffen Race-Condition möglich.

---

### BUG-012: `DatabaseCore.shutdown()` verhindert Neu-Initialisierung

**Datei:** `src/pb_studio/data/database_core.py` (Zeile 184-195)

`shutdown()` setzt `_initialized = False`, aber **nicht** `DatabaseCore._instance = None`. Das Double-Check-Locking in `__new__()` prüft `if cls._instance is None` — nach `shutdown()` ist `_instance` noch gesetzt, aber `_initialized = False`. Die `_init_db()` Methode prueft `if self._initialized: return` und kehrt sofort zurück, OHNE tatsächlich neu zu initialisieren.

**Konsequenz:** Nach einem `shutdown()` kann die Datenbank nicht neu initialisiert werden, ohne die App neu zu starten. Betrifft Szenarien mit DB-Reconnect.

---

## 🟢 NIEDRIGE FINDINGS (4)

### FIND-001: `VectorStore` lädt Legacy-Pickle mit unsicherem `pickle.load()`

**Datei:** `src/pb_studio/data/vector_store.py` (Zeile 57)

Migration von `.pkl` zu JSON nutzt `pickle.load()` ohne Validierung. Bei manipulierten Pickle-Dateien ist Code-Execution möglich.

---

### FIND-002: `VideoClipModel` fehlt INotifyPropertyChanged

**Datei:** `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`

`LoadAllThumbnailsAsync()` nutzt `RemoveAt(idx); Insert(idx, clip)` um UI-Updates zu erzwingen, da `VideoClipModel` kein `INotifyPropertyChanged` implementiert. Ineffizient und fehleranfällig.

---

### FIND-003: `md:PackIcon` statt `icon:PackIconMaterial` in VideoLibraryView

**Datei:** `PBStudio.UI/Views/VideoLibraryView.xaml` (Zeile 737)

Inkonsistente Icon-Verwendung. Alle anderen Views nutzen `icon:PackIconMaterial` (MahApps). `md:PackIcon` ist die MaterialDesign-Variante (andere API, anderes Styling).

---

### FIND-004: Python `uuid` ist stdlib, nicht installierbar

**Status:** Kein echtes Problem. `uuid` ist Python-Standardbibliothek (seit Python 2.5). Kein `pip install uuid` notwendig. Nur zur Klarstellung dokumentiert.

---

## Verkabelungs-Analyse: C# ↔ Python API

### Ergebnis: Alle 17 C# Endpoints haben Python-Pendants ✅

| C# Endpoint | Python Route | Status |
|-------------|-------------|--------|
| GET /health | GET /health | ✅ OK |
| GET /gpu/status | GET /gpu/status | ✅ OK |
| POST /audio/import | POST /audio/import | ✅ OK |
| POST /audio/analyze | POST /audio/analyze | ✅ OK |
| GET /audio/beats/{id} | GET /audio/beats/{clip_id} | ✅ OK |
| POST /audio/stems/separate | POST /audio/stems/separate | ✅ OK |
| GET /video/clips | GET /video/clips | ✅ OK |
| POST /video/import | POST /video/import | ✅ OK |
| GET /video/thumbnails/{id} | GET /video/thumbnails/{clip_id} | ✅ OK |
| POST /video/analyze | POST /video/analyze | ✅ OK |
| POST /pacing/generate | POST /pacing/generate | ✅ OK |
| GET /pacing/timeline | GET /pacing/timeline | ✅ OK |
| POST /render/start | POST /render/start | ✅ OK |
| GET /render/status/{id} | GET /render/status/{task_id} | ✅ OK |
| POST /render/cancel/{id} | POST /render/cancel/{task_id} | ✅ OK |
| GET /events/progress | GET /events/progress | ✅ OK |

### Python Routes ohne C# Client (nicht verbunden, aber kein Bug)

| Route | Anmerkung |
|-------|-----------|
| GET /audio/waveform/{id} | Noch kein WaveformView im C# |
| GET /audio/structure/{id} | Noch kein StructureView im C# |
| GET /audio/spectral/{id} | Noch kein SpectralView im C# |
| GET /video/motion/{id} | Noch kein MotionView im C# |
| GET /video/scenes/{id} | Noch kein ScenesView im C# |
| GET /events/log | Dead feature (BUG-005) |
| GET /events/gpu | Nicht in SSEClient verdrahtet |
| POST /shutdown | Nicht in C# genutzt |
| POST /pacing/preview | Nicht in C# genutzt |
| POST /project/* | Kein ProjectViewModel in C# |

---

## Statische Code-Analyse

### Python Backend (233 Dateien)
- **Syntax-Fehler:** 0 (alle 233 Dateien fehlerfrei via `python -m py_compile`)
- **Routers:** 6 Router vorhanden, alle korrekt in `main.py` registriert
- **Pydantic Schemas:** Alle Schemas korrekt typisiert (bis auf BUG-004)
- **AppState Singleton:** Thread-safe implementiert, SQLite-Persistenz vorhanden
- **FAISS VectorStore:** Korrekte 1152-dim SigLIP Konfiguration, JSON-Metadata (sicherer als Pickle)
- **DatabaseCore:** WAL-Mode, Foreign Keys, Thread-local Connections — solid
- **RenderService:** AMD AMF Encoder-Detection korrekt, FFmpeg Progress-Parsing solide
- **PacingService:** Round-Robin und Motion-Matching beide implementiert

### C# WPF Frontend (30 Dateien)
- **Build-Fehler:** 1 (BUG-002: app.ico fehlt)
- **MVVM Toolkit:** Korrekt verwendet (`[ObservableProperty]`, `[RelayCommand]`, partielle Klassen)
- **DI/Ioc:** Korrekt konfiguriert — ABER durch StartupUri (BUG-001) nutzlos beim Start
- **Alle 8 Views:** DataContext-XAML-Instantiierung entfernt (Ioc.Default korrekt)
- **ApiClient:** SnakeCaseLower Policy korrekt, alle Endpoints async, ConfigureAwait korrekt
- **SSEClient:** Nur `/events/progress` verbunden (kein `/events/gpu`, kein `/events/log`)
- **Converters:** NullToVisibility, InverseBool, InverseNullToVisibility alle vorhanden

---

## Datenbank-Analyse

### SQLite (via DatabaseCore + MediaRepository)
- **Schema:** `projects`, `media`, `vector_map` Tabellen mit korrekten Foreign Keys
- **Indexes:** Auf `file_hash`, `project_id`, `status`, `media_id` — performant
- **WAL-Mode:** Aktiviert für bessere Concurrency ✅
- **Transaktionen:** Korrekt via `@contextmanager transaction()` ✅
- **Thread-Safety:** Thread-local Connections korrekt implementiert ✅
- **Shutdown-Bug:** Siehe BUG-012

### FAISS VectorStore
- **Dimension:** 1152 (SigLIP SO400M) korrekt konfiguriert ✅
- **Index-Typ:** `IndexFlatIP` (Inner Product = Cosine Similarity nach L2-Normierung) ✅
- **Metadata:** JSON statt Pickle (sicher) ✅
- **Auto-Save:** alle 10 Embeddings ✅
- **Sicherheit:** Legacy-Pickle-Migration via unsicherem `pickle.load()` (FIND-001)

---

## Selbst-Kritik (Pflicht)

### Was NICHT geprüft wurde:
1. **Dynamische Tests:** Keine echte App-Ausführung möglich (kein Windows-Environment in diesem Sandbox). Alle Findings basieren auf statischer Analyse.
2. **`AdvancedPacingEngine` internals:** Die Pacing-Engine wurde nicht vollständig analysiert (> 500 Zeilen, komplexe Logik).
3. **`BeatNet` / `Demucs` Konfiguration:** Die ML-Model-Konfiguration und tatsächliche DirectML-Kompatibilität wurde nicht getestet.
4. **XAML-Binding-Fehler:** WPF XAML Binding-Fehler zur Laufzeit sind ohne Ausführung nicht detektierbar.
5. **SSE-Reconnect-Logik:** Fehlerverhalten bei Backend-Ausfall nicht analysiert.
6. **`ConfigManager`:** Die Config-Auflösung für `db_path` und `ffmpeg_path` wurde nur oberflächlich geprüft.

### Unsicherheiten:
- BUG-001 (StartupUri): **Hochkonfident** — WPF-Dokumentation eindeutig. StartupUri vs OnStartup ist ein bekanntes Problem.
- BUG-002 (app.ico): **100% sicher** — Ordner leer, Datei fehlt nachweislich.
- BUG-003 (requirements.txt): **100% sicher** — Import-Analyse eindeutig.
- BUG-004 (Type-Mismatch): **Hochkonfident** — `list[float]` ist nicht als `string` deserialisierbar.
- BUG-006 (fps-Feld): **Sicher** — Schema-Vergleich eindeutig. FastAPI ignoriert unbekannte Felder standardmäßig.

---

## Priorisierte Fix-Reihenfolge für Phase E

| Priorität | Bug | Aufwand | Impact |
|-----------|-----|---------|--------|
| 1 | BUG-002: app.ico hinzufügen | 2 Min | Build möglich |
| 2 | BUG-001: StartupUri entfernen | 1 Min | App startet |
| 3 | BUG-003: requirements.txt ergänzen | 5 Min | Backend installierbar |
| 4 | BUG-004: EnergyProfile → List<float> | 10 Min | Audio-Analyse korrekt |
| 5 | BUG-007: Python-Pfad konfigurierbar | 30 Min | Portabilität |
| 6 | BUG-006: fps-Feld in Python-Schema | 10 Min | FPS-Setting wirksam |
| 7 | BUG-008: CleanupGpu Endpoint fix | 5 Min | GPU Cleanup funktioniert |
| 8 | BUG-009: AudioClips laden | 30 Min | Library persistiert |
| 9 | BUG-010: Video-Selection UI | 60 Min | Director-Tab nutzbar |

**Geschätzter Fix-Aufwand für Kritische + Hohe Bugs:** 2-3 Stunden Entwicklungszeit.

---

*Audit erstellt: 2026-03-04 | Keine Code-Änderungen durch diesen Audit vorgenommen.*
