# QA-Loop Gesamt-Report — 2026-03-15

**Datum:** 2026-03-15 | **Tester:** Auto-QA-Loop Agent
**Backend:** Python 3.11.9 (venv) + FastAPI | **GPU:** AMD Radeon RX 7800 XT (DirectML)

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| API-Endpoints getestet | 31 |
| API-Tests bestanden | 28 PASS / 2 PARTIAL / 0 FAIL |
| Pytest-Tests | 186 passed / 9 skipped / 0 failed |
| WPF-Build | ✅ 0 Fehler, 0 Warnungen |
| Bugs gefunden | 5 |
| Bugs behoben | 5 |

---

## API-Test-Ergebnisse (Überblick)

| Bereich | Ergebnis |
|---------|---------|
| Health & GPU | 3x PASS — `gpu_available=True` mit korrektem Python |
| Projekt-Management | 5x PASS — Create/Open/Save/Close/Info |
| Audio-Import & Bibliothek | 2x PASS — Import + List |
| Audio-Analyse | 5x PASS — BPM=136, 8972 Beats, 6 Struktursegmente |
| Video-Import & Bibliothek | 3x PASS — Import, List, Thumbnail |
| Video-Analyse | scenes=0 (korrekt: 8s Clip ohne Schnitte), motion=370.3 ✅ |
| Pacing & Director | 3x PASS — 2247 Cuts, Timeline, Preview |
| Rendering | 3x PASS — Start, Status, Cancel |
| SSE Events | 1x PASS + 2x PARTIAL (idle — korrekt) |

---

## Gefundene und behobene Bugs

### BUG-QA-001 — Backend mit falschem Python gestartet (INFRASTRUKTUR)
| Feld | Wert |
|------|------|
| **Schwere** | KRITISCH (Betrieb) |
| **Symptom** | `gpu_available=false`, Video-Analyse gibt `motion=0.0` |
| **Root Cause** | `python` (System, 3.12.10) statt `.venv/Scripts/python.exe` (3.11.9) beim Backend-Start |
| **Fix** | Korrekter Start: `PYTHONPATH=src .venv/Scripts/python.exe -m uvicorn backend.main:app --port 8765` |
| **Notiz** | `launch.ps1` priorisiert korrekt `.venv` — nur beim manuellen Start aufgetreten |

### BUG-QA-002 — pacing_router.py: peak_motion nutzte avg_motion (LOGIC ERROR)
| Feld | Wert |
|------|------|
| **Datei** | `backend/routers/pacing_router.py:233` |
| **Schwere** | MITTEL |
| **Root Cause** | `motion.get("avg_motion")` statt `motion.get("peak_motion")` für peak_motion-Feld |
| **Fix** | `clip_data["peak_motion"] = motion.get("peak_motion", 0.0) if motion else 0.0` |
| **Status** | ✅ Behoben |

### BUG-QA-003 — video_router.py: `state` NameError in `_run_video_analysis` (RUNTIME ERROR)
| Feld | Wert |
|------|------|
| **Datei** | `backend/routers/video_router.py:390` |
| **Schwere** | KRITISCH |
| **Root Cause** | `state.video_clips.get(clip_id, ...)` — `state` ist nicht im Scope der standalone-Funktion |
| **Fix** | `result.get("duration_seconds", 0.0)` — nutzt lokale Ergebnisvariable |
| **Status** | ✅ Behoben |

### BUG-QA-004 — TimelineView.xaml.cs: SeekToClipStart ohne _mediaOpened Guard (LOGIC ERROR)
| Feld | Wert |
|------|------|
| **Datei** | `PBStudio.UI/Views/TimelineView.xaml.cs:117` |
| **Schwere** | MITTEL |
| **Root Cause** | `SeekToClipStart()` wird ohne `_mediaOpened` Guard aufgerufen; wenn `_mediaOpened=false` tut die Methode nichts, aber `_pendingSeek` wird nie gecleared |
| **Fix** | `if (_mediaOpened) { SeekToClipStart(); }` |
| **Status** | ✅ Behoben |

### BUG-QA-005 — App.xaml.cs: async void OnStartup (UNOBSERVED EXCEPTION RISK)
| Feld | Wert |
|------|------|
| **Datei** | `PBStudio.UI/App.xaml.cs:19` |
| **Schwere** | MITTEL |
| **Root Cause** | `async void` Event-Handler kann unbeobachtete Exceptions werfen und die App zum Absturz bringen |
| **Fix** | Synchroner `OnStartup` + `bridge.StartAsync().GetAwaiter().GetResult()` |
| **Status** | ✅ Behoben |

### BUG-QA-006 — moondream.py: Fallback-Check `ort.InferenceSession is object` (LOGIC ERROR)
| Feld | Wert |
|------|------|
| **Datei** | `src/pb_studio/video/moondream.py:231` |
| **Schwere** | NIEDRIG |
| **Root Cause** | `ort.InferenceSession is object` — Bedingung zur Erkennung des `_FallbackOrt` unzuverlässig |
| **Fix** | `not hasattr(ort, "InferenceSession") or ort.__class__.__name__ == "_FallbackOrt"` |
| **Status** | ✅ Behoben |

---

## pytest-Infrastruktur Fix

| Problem | Ursache | Fix |
|---------|---------|-----|
| 158 PermissionErrors beim pytest-Start | `.pytest_tmp` durch Windows-Prozess gesperrt | `--basetemp=.pytest_tmp2` in `pytest.ini` |
| **Ergebnis vorher** | 0 Tests liefen durch | **Ergebnis nachher**: 186 passed / 9 skipped |

---

## Offene Punkte

- **Moondream ONNX-Modell fehlt** — Embeddings werden übersprungen (nicht kritisch — Pacing nutzt Round-Robin Fallback)
- **CLAP-Modell fehlt** — 2 Tests korrekt geskippt
- **SigLIP text-Tests** — 4 Tests korrekt geskippt (Modell fehlt)
- **Waveform-Tests** — 3 Tests korrekt geskippt
- **SSE Progress/Log im Idle** — PARTIAL ist korrekt; Streams funktionieren während aktiver Operationen

---

## Verifizierung nach allen Fixes

```
WPF-Build:  0 Fehler, 0 Warnungen ✅
pytest:     186 passed, 9 skipped, 0 failures ✅
API:        28 PASS, 2 PARTIAL (akzeptabel), 0 FAIL ✅
GPU:        gpu_available=True (AMD DirectML) ✅
Motion:     avg_motion=370.29 (korrekt) ✅
```
