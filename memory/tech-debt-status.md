# Tech-Debt Status — PB Studio AMD Edition
**Letzte Aktualisierung:** 2026-03-04

## ALLE 11 ITEMS ABGESCHLOSSEN ✅

| # | Item | Status | Session |
|---|------|--------|---------|
| 1 | `pytest.ini` Case-Bug (Tests→tests/Tests) | ✅ Behoben | Phase 0 |
| 2 | `torch>=2.0.0` unpinned | ✅ Gepinnt: `==2.4.1+cpu` | Phase 0 |
| 3 | `onnxruntime-directml` unpinned | ✅ Gepinnt: `>=1.16.0,<1.20.0` | Phase 0 |
| 4 | `from src.pb_studio` falsche Imports | ✅ Alle 139 Dateien, 0 verbleibend | Phase 0 |
| 5 | `ConfigureAwait(false)` fehlt (45 C# awaits) | ✅ ApiClient, PythonBridge, SSEClient | Phase 1 |
| 6 | In-Memory State in 4 Router | ✅ `backend/app_state.py` Singleton | Phase 2a |
| 7 | `IApiClient` Interface fehlt | ✅ 15 Methoden, DI registriert | Phase 1 |
| 8 | 3 TODOs in Produktionscode | ✅ Alle 3 aufgelöst | Phase 1 |
| 9 | Kein CI/CD | ✅ `.github/workflows/ci.yml` | Phase 2c |
| 10 | Keine OpenAPI-Beschreibungen | ✅ Alle 4 Router komplett | Phase 2b |
| 11 | Test-Coverage: 0 Tests für Backend | ✅ 36 Tests, 36 PASSED | Phase 3 |

## Kritische Erkenntnisse

### pytest.ini: Pfad ist `Tests` (Großbuchstabe!)
- Windows NTFS auf Linux-Mount: `Tests/` (capital T) ist der echte Name
- `pytest.ini`: `testpaths = Tests` (korrigiert von `tests`)
- `pythonpath = src .` (Punkt für `backend/` Import)

### backend/routers/__init__.py Shadow-Problem
- `from .audio_router import router as audio_router` → Name-Kollision
- `patch("backend.routers.audio_router.publish_event")` FUNKTIONIERT NICHT
- Korrekte Lösung: `importlib.import_module("backend.routers.audio_router")` via `sys.modules`
- Muster: `_get_module("backend.routers.audio_router")` Helper-Funktion in Tests

### AppState: Thread-Sicherheit bestätigt
- 500 parallele Threads → 0 doppelte IDs (test_thread_sicherheit PASSED)
- `threading.Lock` korrekt implementiert

### Video-Router Semantik (kein 404 bei Import!)
- Video-Import gibt leere Liste bei nicht-existierenden Dateien (skip, kein 404)
- Nur Thumbnail/Analyse-Endpoints geben 404 bei unbekannter clip_id
