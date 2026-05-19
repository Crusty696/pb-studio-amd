# PB Studio AMD — Plan: Offene Tasks & Bugs

**Stand:** 2026-05-15
**Status:** 506/506 pytest grün auf Windows, dotnet build clean, 253/253 py_compile OK.

Erstellt nach Cowork-Sessions 2026-05-14/15. Quellen: Spec-Files 00007/00009/00010, `test-report/2026-05-14-AMD-DRIVER-UPDATE-required.md`, Static-Coverage-Analyse, Vulture-Output, PyPI-Staleness-Check.

---

## 1. Prioritäts-Matrix

| Prio | Bedeutung |
|---|---|
| 🔴 **P0** | Blockiert Release / kritischer Bug / Compliance |
| 🟠 **P1** | Wichtig vor nächster Major-Release |
| 🟡 **P2** | Nice-to-have / Polish |
| 🔵 **P3** | Backlog / opportunistisch |

| Doability |  |
|---|---|
| 💻 Linux-Sandbox | Ich kann direkt im Cowork-Bash machen |
| 🖱️ Computer-Use | Ich kann via Explorer/PowerShell-Click auf Windows ausführen |
| 👤 User-Physical | Du musst es persönlich machen (Hardware, Treiber) |

| Effort | Zeit |
|---|---|
| S | < 30 min |
| M | 30 min – 2 h |
| L | > 2 h |
| XL | > 1 Tag |

---

## 2. 🔴 P0 — Kritisch / Eskaliert

### ~~P0.1 — AMD Adrenalin Driver-Update (F-10.3)~~ ✅ **RESOLVED 2026-05-15**

Treiber wurde zwischen 2026-05-08 und 2026-05-15 aktualisiert auf `32.0.31007.1017` (DriverDate 04.05.2026). Verifikation:

- `ffmpeg -hwaccels` listet `amf` ✓
- `ffmpeg -encoders` listet `h264_amf`, `hevc_amf`, `av1_amf` ✓
- Live-Test `ffmpeg -c:v h264_amf` → PASSED ✓
- `amfrt64.dll` vorhanden in `System32` ✓
- GPU: AMD Radeon RX 7800 XT (16 GB)

**Doc:** `test-report/2026-05-15-AMD-DRIVER-RESOLVED.md`
**Folge:** P1.1 (4h-Stress-Test) kann jetzt mit echtem AMF-Encoder durchgeführt werden.

---

## 3. 🟠 P1 — Wichtig vor Release

### P1.1 — Spec 00007 T008/T009: 4h-Stress-Test mit amdsmi-Telemetry
**Status:** Offen. Script `src/tools/execute_4h_stress_test.py` existiert bereits (164 Zeilen, compile clean).
**Doability:** 🖱️ Computer-Use (PowerShell via Explorer-Doppelklick)
**Effort:** L (Setup: M, Run: 4h Wartezeit)
**Schritte:**
1. Test-Script-Review: prüfen ob amdsmi-Integration aktuell ist (vs ältere ROCm-API)
2. Run starten via Doppelklick auf `run-4h-stress.bat` (muss noch geschrieben werden)
3. Während Run: VRAMArbiter-Eviction-Logs prüfen (T009)
4. Pass-Kriterium: 0 OOM-Crashes, Buffer-Trigger < 500MB freisetzt mind. 1 Model
**Liefer:** `test-report/4h-stress-YYYY-MM-DD.md`

### P1.2 — Spec 00010 T006: 4GB-VRAM-Stress-Test (0 OOM)
**Status:** Offen. `verify_low_vram_resilience.py` existiert (73 Zeilen, compile clean).
**Doability:** 🖱️ Computer-Use
**Effort:** M (Run-Dauer ca. 15-30 min)
**Schritte:**
1. Skript starten: setzt `PB_STUDIO_FORCED_VRAM=4000`, restartet Backend
2. Mehrere Videos importieren + analysieren (SigLIP + RAFT parallel)
3. Pass-Kriterium: `/health` antwortet weiterhin `status=ok`, keine Backend-Crashes
4. Rejection-Logs (VRAM denied) sind erwartet/erlaubt
**Liefer:** `test-report/4gb-resilience-YYYY-MM-DD.md`

### P1.3 — Spec 00010 T007: Backend-Kill-Recovery-Test
**Status:** Offen. Setup-Vorbedingung: SSE-Backoff + Overlay sind seit heute implementiert.
**Doability:** 🖱️ Computer-Use
**Effort:** S (manueller Test, ca. 10 min)
**Schritte:**
1. App starten, Render starten (lange SSE-Stream-Aktivität)
2. PowerShell: `taskkill /F /IM uvicorn.exe`
3. Beobachten: nach 5 Reconnect-Attempts (ca. 15s) erscheint "Verbindung verloren"-Overlay
4. Backend manuell neustarten: `start.bat`
5. Pass-Kriterium: SSE rebindet automatisch, Overlay verschwindet, Progress-Updates resumed
**Doc:** Screenshot vor + nach Overlay einkleben.

### P1.4 — Spec 00007 T012: verify_release_smoke.ps1 Expansion
**Status:** Offen. Script existiert bereits, soll erweitert werden.
**Doability:** 💻 Linux-Sandbox (für Edit) + 🖱️ Computer-Use (für Run-Verify)
**Effort:** M
**Schritte:**
1. Existierende Checks reviewen (`verify_release_smoke.ps1`)
2. Hinzufügen: VRAM-Telemetry-Endpoint-Probe (`/health/vram`), SSE-Heartbeat-Probe (`/health/heartbeat`), Brain-DB-Migration-Check
3. Pass-Kriterium: Script gibt `RELEASE-READY: YES` aus
**Implementation:** Schreibe erweiterte Version, dann Doppelklick-Run auf Windows.

### P1.5 — Pytest+Coverage Hang Bug (NEU 2026-05-14)
**Status:** Bug identifiziert während Coverage-Analyse. Pytest mit coverage-Instrumentierung hängt bei `test_clip_selector_motion_curve.py` / `test_config_manager.py` (ca. 41% der Tests).
**Root Cause Hypothese:** Hardware-Sensor-Init unter coverage-Wrapper deadlockt mit `pythonnet`-COM-Layer.
**Doability:** 💻 Linux-Sandbox (Static-Analysis) + 🖱️ Computer-Use (Repro)
**Effort:** M
**Schritte:**
1. Identifiziere genau welcher Test im Hang ist: `pytest --co --collect-only` + bisect
2. Coverage-Compatible-Patch: `pytest-cov` statt `coverage run -m pytest`, oder Mock von SystemMonitor in conftest
3. Pass-Kriterium: `pytest Tests/ --cov` läuft in < 5min durch
**Workaround heute:** Static-AST-Coverage (65% Modul / 72% Def — Report liegt vor).

---

## 4. 🟡 P2 — Polish / Nice-to-Have

### P2.1 — Spec 00007 T010: GPU-RenderTransform Tab-Animations
**Status:** Offen. Aktuelle Tab-Wechsel sind hart (kein Übergang).
**Doability:** 💻 Linux-Sandbox + 🖱️ Computer-Use für visual review
**Effort:** M
**Schritte:**
1. `MainWindow.xaml` TabControl.Triggers erweitern: SelectionChanged → ScaleTransform-Animation (`From=0.95 To=1.0 Duration=0:0:0.15`)
2. Performance-Check: muss in <16ms render-tick passen (60Hz)
3. Visual Review via Screenshot
**Risiko:** Nur kosmetisch, kein Risiko für Funktionalität.

### P2.2 — Spec 00009 T006: Compressed Depth-Metadata
**Status:** Offen. Storage-Optimierung, kein Funktionalitätsbedarf.
**Doability:** 💻 Linux-Sandbox
**Effort:** S
**Schritte:**
1. `media_repository.py`: gzip-Wrap für `meta`-JSONB-Spalte wenn > 10KB
2. Decompress on read transparent
3. Migration-Skript für existierende rows (optional)
**Impact:** ~50% disk-saving für depth-heavy projects.

### P2.3 — Spec 00009 T008: Explicit Dynamic Downsampling Marker
**Status:** Code existiert in TimelineViewModel.cs (lines 67-107), aber kein explizites Spec-Marker-Comment.
**Doability:** 💻 Linux-Sandbox
**Effort:** S
**Schritte:**
1. Comment-Header an Downsampling-Block: `// Spec 00009 T008 / STF-001: Dynamic Downsampling — siehe spec.md AD-004`
2. Optional: Performance-Test schreiben (1000 Spectral-Points → < 16ms downsample time)

### P2.4 — Spec 00010 T008: Visual Review "Connection Lost" Overlay
**Status:** Overlay-Implementation fertig (P21 heute), Visual-Review fehlt.
**Doability:** 🖱️ Computer-Use
**Effort:** S
**Schritte:**
1. App starten, Backend killen
2. Screenshot 5-10s warten, Overlay erscheint
3. Backend restart, Overlay verschwindet
4. Pass-Kriterium: Overlay ist lesbar, blockiert keine wichtigen UI-Elemente, Auto-Hide funktioniert

### P2.5 — Inline-TODOs auflösen
**Status:** 2 Stück.
**Doability:** 💻 Linux-Sandbox
**Effort:** S–M
- `backend/routers/video_router.py:348` — progress_callback instrumentation
- `src/pb_studio/pacing/advanced_pacing_engine.py:1293` — Snap-to-subtrack TODO (Helper-API ready)

---

## 5. 🔵 P3 — Backlog

### P3.1 — Test-Coverage-Gaps füllen
**Status:** 8 kritisch ungetestete Module (≥8 defs):
| Module | Defs | Notes |
|---|---|---|
| `src/pb_studio/models/timeline.py` | 20 | Reine dataclasses, indirekt via Router-Tests |
| `src/pb_studio/models/video.py` | 20 | Reine dataclasses |
| `src/pb_studio/models/audio.py` | 14 | Reine dataclasses |
| `src/pb_studio/core/model_loader.py` | 13 | Wird in Tests gemockt |
| `src/pb_studio/video/encoder_utils.py` | 10 | FFmpeg-Encoder-Detection |
| `src/pb_studio/utils/cache_manager.py` | 8 | Cache-Helpers |
| `src/pb_studio/workers/base_worker.py` | 8 | PyQt-Worker (GUI-getrieben) |
| `src/pb_studio/workers/worker_registry.py` | 8 | PyQt-Worker-Registry |

**Doability:** 💻 Linux-Sandbox
**Effort:** L (pro Modul S, gesamt L)
**Empfehlung:** dataclasses und PyQt-Worker low-prio (effektiv covered durch Integration-Tests). `encoder_utils.py` + `cache_manager.py` + `model_loader.py` priorisieren.

### P3.2 — Dependency-Updates (19 safe-updatable)
**Status:** Stale gegen PyPI, keine Iron-Rule-Bezug.
**Doability:** 💻 Linux-Sandbox (für requirements-edit) + 🖱️ Computer-Use (für pip-install + pytest-regression)
**Effort:** L (cluster-weise updaten + Regress-Test)
**Cluster:**
- **FastAPI-Stack:** fastapi 0.110→0.136, uvicorn 0.28→0.47, pydantic 2.5→2.13, pydantic-settings 2.2→2.14, httpx 0.27→0.28
- **Audio/ML:** scipy 1.13→1.17, soundfile 0.12→0.13, scikit-learn 1.3→1.8, librosa current, demucs 4.0→4.0.1
- **HuggingFace:** huggingface_hub 0.28→1.14, sentencepiece 0.2.0→0.2.1, sqlite-vec 0.1.6→0.1.9
- **Misc:** pillow 10→12, psutil 5.9→7.2, scenedetect 0.6→0.7, colorlog 6.8→6.10, python-dotenv 1.0→1.2, pythonnet 3.0.0→3.0.5, audio-separator 0.17→0.44
**Strategie:** Cluster-für-Cluster im Branch updaten, pytest+dotnet-build pro Cluster, dann mergen.

### P3.3 — Spec 00007 T009: VRAMArbiter Eviction-Behavior Verify
**Status:** Offen, Teil von 4h-Stress (P1.1).
**Doability:** 🖱️ Computer-Use
**Effort:** M
**Schritte:** Während 4h-Stress: VRAM aktiv tracken, sobald Buffer < 500MB → Eviction-Log prüfen, sobald >= 1 Modell evicted: Pass.

### P3.4 — Vulture-Cleanup (4 false-positive-clarifications)
**Status:** 4 echte unused-Variables sind alle API-Compat. Pragmatisch.
**Doability:** 💻 Linux-Sandbox
**Effort:** S
**Schritte:**
1. `vram_budget_manager.py:934 exc_val` — `# noqa` Kommentar (Standard `__exit__`-Signatur)
2. `clip_selector.py:205 previous_clip_id` — `# NV-API-Compat, intentional unused` Kommentar
3. `analysis_service.py:21 + generation_service.py:38 status_callback` — `# PyQt-Legacy-Signal, retained for API` Kommentar
**Impact:** Macht vulture-Reports cleaner für zukünftige Audits.

---

## 6. 📊 Spec-Fortschritt Summary

| Spec | Done | Open | % |
|---|---|---|---|
| 00005 power-timeline | ✅ completed |  | 100% |
| 00006 amd-export-pipeline | ✅ completed |  | 100% |
| 00007 release-hardening-ux-polish | 9 | 4 | 69% |
| 00008 deeper-ux-timeline-polish | ✅ completed |  | 100% |
| 00009 data-depth-visualization | 8 | 2 | 80% |
| 00010 resilience-edge-cases | 5 | 3 | 63% |
| **GESAMT** | **22** | **9** | **71%** |

Plus:
- ~~1 P0 eskaliert (AMD-Treiber)~~ ✅ **RESOLVED 2026-05-15**
- 1 P1 NEU (Pytest+Coverage Hang Bug)
- 2 inline-TODOs
- 8 Test-Gaps
- 19 safe-Dep-Updates

---

## 7. 🛣️ Empfohlene Reihenfolge

**Diese Woche:**
1. P0.1 — AMD-Treiber-Update (du, 30 min, blockiert Render-Performance)
2. P1.3 — Backend-Kill-SSE-Recovery-Test (ich, 10 min via Computer-Use, validiert heutige Overlay-Impl)
3. P2.4 — Visual Review Overlay (ich, 10 min)

**Nächste Woche:**
4. P1.2 — 4GB-VRAM-Stress (ich, 30 min)
5. P1.4 — Release-Smoke-Expansion (ich + Computer-Use, 1h)
6. P2.1 — Tab-Animations (ich, 1h)
7. P1.5 — Pytest+Coverage Hang Fix (ich, 1-2h)

**Sprint danach (nach AMD-Treiber-Fix):**
8. P1.1 — 4h-Stress mit funktionierendem AMF-Encoder (ich + 4h Wartezeit)
9. P3.2 — Dep-Updates Cluster-für-Cluster (ich, 2-3h pro Cluster, ca. 4 Cluster)
10. P3.4 — Vulture-Cleanup-Kommentare (ich, 15 min)

**Backlog:**
11. P3.1 — Test-Coverage-Gaps (priorisiere encoder_utils, cache_manager, model_loader)
12. P2.5 — Inline-TODOs

---

## 8. 🤖 Bisherige Cowork-Commits dieser Sessions

```
705b5b9  chore: placeholders for corrupted dev-scratch + lost-work tests
ef6e561  fix(vram): VRAMArbiter constructor crash when PB_STUDIO_FORCED_VRAM is set
c798392  docs(specs): mark verified-done tasks from cowork audit 2026-05-14
```

Pending lokal (für `commit-cowork-2026-05-14-part2.ps1`):
- `docs(specs)`: T011 + T013 + T003 + T004 markers
- `perf(ui)`: AudioClipList virtualization mode = Recycling
- `feat(sse)`: 5-attempt UI-Notify
- `feat(ui)`: ConnectionStatus overlay

---

**Doc-Sources:** `specs/0000{5..10}/*.md`, `test-report/auto-qa-loop-2026-05-14-FINAL.md`, `CHANGELOG.md`, `CLAUDE.md` Iron Rules, PyPI JSON API.
