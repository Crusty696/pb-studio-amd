# Tech-Debt Audit — PB Studio (AMD Premium Edition)
**Datum:** 2026-03-04
**Analysiert:** `src/` (33.518 Zeilen Python) + `backend/` (1.778 Zeilen) + `PBStudio.UI/` (1.490 Zeilen C# / 764 Zeilen XAML)
**Framework:** Priority = (Impact + Risk) × (6 − Effort) | Skala 1–5

---

## Zusammenfassung: Top-Prioritäten

| # | Item | Kategorie | Priority-Score | Aufwand |
|---|------|-----------|---------------|---------|
| 1 | `pytest.ini` Case-Bug — Tests laufen NIE | Infrastruktur | **50** | 5 Min |
| 2 | `torch>=2.0.0` unpinned | Dependency | **45** | 15 Min |
| 3 | `onnxruntime-directml` unpinned | Dependency | **40** | 15 Min |
| 4 | `from src.pb_studio` falsche Imports in ai/ | Code | **40** | 30 Min |
| 5 | `ConfigureAwait(false)` fehlt (45 C# awaits) | Code | **35** | 1h |
| 6 | In-Memory State in 4 FastAPI-Routern | Architektur | **30** | 2–3d |
| 7 | `IApiClient` Interface fehlt | Code | **20** | 2h |
| 8 | 3 TODOs in Produktionscode | Code | **16** | 1–2h |
| 9 | Kein CI/CD | Infrastruktur | **14** | 1–2d |
| 10 | Keine OpenAPI-Beschreibungen | Dokumentation | **12** | 3h |
| 11 | Test-Coverage: 90+ Module ohne Tests | Test | **8** | Mehrere Wochen |

---

## Details pro Item

---

### 🔴 P0 — Sofort beheben (vor nächstem Commit)

---

#### #1 — `pytest.ini` Case-Bug
**Kategorie:** Infrastruktur-Debt
**Impact:** 5 | **Risk:** 5 | **Effort:** 1 | **Score: 50**

**Problem:** `pytest.ini` enthält `testpaths = Tests` (Großbuchstabe T). Der tatsächliche Ordner heißt `tests/` (Kleinbuchstabe). Auf case-sensitiven Systemen (Linux CI, WSL) findet pytest **keine Tests** — es gibt 0 Fehler, weil gar nichts ausgeführt wird. Entwickler glauben die Tests seien grün.

**Fundstelle:** `pytest.ini` Zeile mit `testpaths`

**Fix:**
```ini
# pytest.ini
[pytest]
testpaths = tests
```

**Risiko wenn ignoriert:** Alle Regressionen aus der Pacing-Migration werden unbemerkt eingecheckt. False Sense of Security.

---

#### #2 — `torch>=2.0.0` unpinned
**Kategorie:** Dependency-Debt
**Impact:** 4 | **Risk:** 5 | **Effort:** 1 | **Score: 45**

**Problem:** `pyproject.toml` / `requirements.txt` erlauben jede PyTorch-Version ≥ 2.0.0. PyTorch 2.5+ ändert intern die DirectML-Kompatibilität (TorchScript-API). Ein unbeabsichtigtes `pip install --upgrade` bricht sofort die Stem-Separation (Demucs/DirectML).

**Locked Version laut CLAUDE.md:** `2.4.1+cpu`

**Fix:**
```toml
# pyproject.toml
torch = "==2.4.1+cpu"
```

**Risiko wenn ignoriert:** Nach nächstem `pip install -r requirements.txt` in frischer Umgebung lädt pip `torch 2.6+` — Demucs-Patch schlägt fehl, GPU-Inference bricht.

---

#### #3 — `onnxruntime-directml` unpinned
**Kategorie:** Dependency-Debt
**Impact:** 4 | **Risk:** 4 | **Effort:** 1 | **Score: 40**

**Problem:** `onnxruntime-directml>=1.16.0` erlaubt automatische Upgrades. ONNX Runtime 1.18+ ändert das Session-Options-API; `enable_mem_pattern = False` könnte deprecated werden oder anders funktionieren. Alle 3 ONNX-Wrapper (Moondream, RAFT, SigLIP) würden brechen.

**Fix:**
```toml
# pyproject.toml
onnxruntime-directml = ">=1.16.0,<1.20.0"
```

**Risiko wenn ignoriert:** Nach Upgrade in Produktionsumgebung brechen alle AI-Inferenz-Module gleichzeitig. Debugging ist aufwendig da der Fehler nicht sofort offensichtlich ist.

---

#### #4 — `from src.pb_studio` falsche Imports in `ai/`
**Kategorie:** Code-Debt
**Impact:** 4 | **Risk:** 4 | **Effort:** 1 | **Score: 40**

**Problem:** Mehrere Dateien in `src/pb_studio/ai/` importieren mit absolutem Pfad `from src.pb_studio.xxx import ...`. Das funktioniert nur wenn man direkt aus dem Repo-Root ausführt (`python run_ui.py`). Bei korrekter Package-Installation via `pip install -e .` schlägt der Import mit `ModuleNotFoundError: No module named 'src'` fehl.

**Betroffene Dateien:**
- `src/pb_studio/ai/clap_wrapper.py`
- `src/pb_studio/ai/siglip_wrapper.py`
- `src/pb_studio/ai/smart_director.py` (mehrere Imports)

**Fix:** Alle `from src.pb_studio.` ersetzen durch `from pb_studio.`:
```python
# Falsch:
from src.pb_studio.core.vram_arbiter import VRAMArbiter
# Richtig:
from pb_studio.core.vram_arbiter import VRAMArbiter
```

**Risiko wenn ignoriert:** Sobald das Backend als installiertes Package läuft (Docker, CI, `pip install -e .`), crasht der Import-Stack beim Start.

---

### 🟠 P1 — Diese Sprint beheben

---

#### #5 — `ConfigureAwait(false)` fehlt in 45 C# `await`-Calls
**Kategorie:** Code-Debt
**Impact:** 3 | **Risk:** 4 | **Effort:** 1 | **Score: 35**

**Problem:** Alle 45 `await`-Aufrufe in ViewModels und Services haben kein `.ConfigureAwait(false)`. In WPF mit `SynchronizationContext` führt das zu Deadlocks wenn async-Methoden aus nicht-UI-Threads aufgerufen werden. Besonders kritisch in SSE-Event-Handlern die vom ThreadPool kommen.

**Fundstelle:** `PBStudio.UI/Services/ApiClient.cs` (15 async Methoden), ViewModels

**Fix:** Automatisierbar via Find & Replace:
```csharp
// Vorher:
var result = await _httpClient.GetAsync(url);
// Nachher:
var result = await _httpClient.GetAsync(url).ConfigureAwait(false);
```

**PowerShell (Automatisierung):**
```powershell
Get-ChildItem -Path "PBStudio.UI" -Recurse -Filter "*.cs" | ForEach-Object {
    (Get-Content $_.FullName) -replace '(\bawait\b.*?);', '$1.ConfigureAwait(false);' | Set-Content $_.FullName
}
```
⚠️ Nach Automatisierung: Manuell prüfen, dass UI-Updates (die den Dispatcher brauchen) `ConfigureAwait(true)` oder keinen `await` im UI-Thread bekommen.

**Risiko wenn ignoriert:** Sporadische, schwer reproduzierbare Deadlocks bei schnellen Click-Events oder SSE-Bursts. Äußert sich als "App friert ein" ohne Exception.

---

#### #6 — In-Memory State in 4 FastAPI-Routern
**Kategorie:** Architektur-Debt
**Impact:** 5 | **Risk:** 5 | **Effort:** 3 | **Score: 30**

**Problem:** Vier Router verwenden module-level Dictionaries als Zustandsspeicher:

| Router | Variable | Risiko |
|--------|----------|--------|
| `audio_router.py` | `_audio_clips: dict` | Datenverlust bei Neustart |
| `video_router.py` | `_video_clips: dict` | Datenverlust bei Neustart |
| `pacing_router.py` | `_current_timeline: list`, `_current_audio_path: str` | Race-Condition bei parallelen Requests |
| `render_router.py` | `_render_tasks: dict` | Laufende Renders werden "vergessen" |

**Konsequenz:** Jeder Python-Prozess-Neustart löscht alle importierten Clips und Timelines. Die SQLite-Datenbank (bereits vorhanden!) wird nicht genutzt.

**Fix (Phasenweise):**
- **Phase 1 (Quick):** Session-basierter In-Memory Store mit UUID-Key (verhindert State-Konfusion)
- **Phase 2 (Proper):** Router nutzen bestehenden `DatabaseManager` aus `pb_studio.database` für Clip-Persistenz

**Risiko wenn ignoriert:** In der aktuellen Entwicklungsphase akzeptabel (Single-User, lokaler Server). In Produktionsszenarien (Docker-Restart, Crash) gehen alle Nutzerdaten verloren.

---

#### #7 — `IApiClient` Interface fehlt in C#
**Kategorie:** Code-Debt
**Impact:** 3 | **Risk:** 2 | **Effort:** 2 | **Score: 20**

**Problem:** `ApiClient.cs` ist eine konkrete Klasse ohne Interface. Alle ViewModels haben eine harte Abhängigkeit auf `ApiClient`. Das macht Unit-Tests unmöglich (kein Mocking), und den Dependency-Injection-Container schwächer.

**Fix:** Interface `IApiClient` extrahieren mit allen 15 Methoden:
```csharp
// IApiClient.cs
public interface IApiClient : IDisposable
{
    Task<HealthResponse?> GetHealthAsync(CancellationToken ct = default);
    Task<List<AudioClipInfo>> ImportAudioAsync(List<string> paths, CancellationToken ct = default);
    // ... alle 15 Methoden
}
```

Dann in `App.xaml.cs`:
```csharp
services.AddSingleton<IApiClient, ApiClient>();
```

**Risiko wenn ignoriert:** Kein direktes Produktionsrisiko. Aber ohne Interface kann kein einziger ViewModel-Unit-Test geschrieben werden.

---

### 🟡 P2 — Nächste Sprint einplanen

---

#### #8 — 3 TODOs in Produktionscode
**Kategorie:** Code-Debt
**Impact:** 2 | **Risk:** 2 | **Effort:** 2 | **Score: 16**

**Fundstellen:**
```
src/pb_studio/core/crash_handler.py:17    # TODO: ...
src/pb_studio/ui/waveform_container.py:189 # TODO: ...
src/pb_studio/services/engine.py:218       # TODO: ...
```

**Aktion:** TODOs lesen, als GitHub-Issues erfassen oder sofort beheben. Kein Code-TODO darf in Produktionsrelease bleiben.

---

#### #9 — Kein CI/CD
**Kategorie:** Infrastruktur-Debt
**Impact:** 4 | **Risk:** 3 | **Effort:** 4 | **Score: 14**

**Problem:** Es gibt keine automatisierte Pipeline (GitHub Actions, GitLab CI o.ä.). Fehler werden nur durch manuelle Tests entdeckt. Besonders kritisch da:
- `pytest.ini` Case-Bug bisher unbemerkt blieb (kein CI lief die Tests)
- C# Build-Fehler werden erst beim manuellen `dotnet build` erkannt
- Dependency-Konflikte werden nicht automatisch geprüft

**Minimaler Fix (GitHub Actions):**
```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  python-tests:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
  csharp-build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - run: dotnet build PBStudio.UI/PBStudio.UI.csproj --no-restore
```

**Risiko wenn ignoriert:** Regressionen werden erst nach manuellem Testen entdeckt. Bei der laufenden WPF-Migration ist das ein signifikantes Qualitätsrisiko.

---

#### #10 — Keine OpenAPI-Beschreibungen in FastAPI-Routern
**Kategorie:** Dokumentations-Debt
**Impact:** 2 | **Risk:** 1 | **Effort:** 2 | **Score: 12**

**Problem:** Alle 4 Router haben keine `summary`, `description` oder `response_description` in den Endpoint-Dekoratoren. Die generierte Swagger-Dokumentation (`/docs`) ist damit nutzlos für API-Client-Entwicklung.

**Fix (Beispiel):**
```python
@router.post("/import", response_model=list[AudioClipInfo],
             summary="Audio-Dateien importieren",
             description="Importiert MP3/WAV/FLAC/OGG Dateien und gibt Clip-Metadaten zurück.")
async def import_audio(request: AudioImportRequest):
    ...
```

**Aufwand:** ~3 Stunden für alle 4 Router vollständig.

---

### 🟢 P3 — Langfristig / Backlog

---

#### #11 — Test-Coverage: 90+ Python-Module ohne Tests
**Kategorie:** Test-Debt
**Impact:** 4 | **Risk:** 4 | **Effort:** 5 | **Score: 8**

**Problem:** Von ca. 95 Python-Modulen hat nahezu keines einen direkten Unit-Test. Die Pacing-Migration (7 Dateien) wurde nie automatisiert getestet. Core-Module (`vram_arbiter.py`, `beat_detector.py`, `advanced_pacing_engine.py`) haben 0% Coverage.

**Strategie:** Nicht versuchen 100% zu erreichen. Stattdessen:
1. **Tier 1 (sofort):** Tests für die 4 in dieser Session geänderten Dateien
2. **Tier 2 (nächste 2 Sprints):** Tests für alle `services/` und `pacing/` Module
3. **Tier 3 (langfristig):** Coverage-Badge-Ziel: 40% bis Q2 2026

**Minimales Testgerüst (Pacing):**
```python
# tests/test_advanced_pacing_engine.py
def test_init_with_trigger_settings_dict():
    engine = AdvancedPacingEngine(trigger_settings={"use_beats": True})
    assert engine._trigger_settings is not None

def test_clip_selector_lazy_init():
    engine = AdvancedPacingEngine()
    assert engine._clip_selector is None
    _ = engine.clip_selector
    assert engine._clip_selector is not None
```

---

## Phasen-Plan (neben Feature-Work durchführbar)

### Phase 0 — Sofort (< 1 Stunde, kein Review nötig)
1. ✅ `pytest.ini`: `Tests` → `tests` (1 Zeile)
2. ✅ `pyproject.toml`: torch pinnen auf `==2.4.1+cpu`
3. ✅ `pyproject.toml`: onnxruntime-directml auf `>=1.16.0,<1.20.0`
4. ✅ `ai/*.py`: `from src.pb_studio` → `from pb_studio` (3 Dateien, ~10 Stellen)

### Phase 1 — Diese Woche (Review empfohlen)
5. `ConfigureAwait(false)` in allen C# awaits (45 Stellen, automatisierbar)
6. `IApiClient` Interface erstellen und in DI registrieren
7. 3 TODOs als Issues erfassen oder beheben

### Phase 2 — Nächste 2 Wochen (parallel zu WPF-Migration)
8. In-Memory Router State: Phase 1 (UUID-Session-Store)
9. OpenAPI-Beschreibungen für alle 4 Router
10. Minimale CI/CD Pipeline (GitHub Actions)

### Phase 3 — Nach WPF-Migration (Backlog)
11. Test-Coverage: Tier 1 + Tier 2 (Pacing + Services)
12. In-Memory Router State: Phase 2 (SQLite-Persistenz via DatabaseManager)
13. Coverage-Ziel: 40% bis Q2 2026

---

## Risiko-Matrix

```
         RISIKO
          HIGH  |  #2(torch)  #3(onnx)  #6(state)
                |  #4(import) #7(IApiClient)
        MEDIUM  |  #5(await)  #1(pytest) #9(CI)
                |  #8(TODO)
           LOW  |  #10(OpenAPI) #11(Coverage)
                +----------------------------------
                   LOW       MEDIUM     HIGH
                              IMPACT
```

**Kritischer Pfad:** Items #1 → #2 → #3 → #4 müssen vor dem nächsten Production-Build erledigt sein. Zusammen: ca. 1 Stunde Aufwand, maximal 50 Priority-Punkte gespart.

---

*Bericht generiert: 2026-03-04 | Nächste Review: nach Abschluss WPF-Migration Phase 1*
