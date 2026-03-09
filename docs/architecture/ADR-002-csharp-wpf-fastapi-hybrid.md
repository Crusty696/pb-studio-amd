# ADR-002: C# WPF + Python FastAPI Hybrid-Architektur

**Status:** Accepted
**Datum:** 2026-03-01
**Entscheider:** David Lochmann (Owner)
**Umgesetzt seit:** 2026-03-01 (Phase 1 aktiv)
**Ersetzt:** PyQt6 Monolith-Architektur (vor 2026-03-01)

---

## Kontext

PB Studio war eine reine Python/PyQt6-Desktop-Anwendung. Das Frontend (GUI) und das Backend (ML-Pipeline, Audio/Video-Analyse, Rendering) liefen im selben Prozess. Dies führte zu mehreren strukturellen Problemen:

- **GUI-Blocking:** Schwere ML-Operationen (Demucs, RAFT, CLAP) blockierten den UI-Thread trotz QThread-Worker-Pattern
- **Wartbarkeit:** PyQt6 XAML-äquivalent fehlt — UI-Code ist stark mit Business-Logik verwoben
- **Testbarkeit:** Keine klare API-Grenze zwischen GUI und ML-Logic
- **Zukunftsfähigkeit:** PyQt6 ist für komplexe UI-Patterns (MVVM, Dependency Injection, DataBinding) nicht ausgelegt
- **Featuregap:** Die NVIDIA-Referenzversion nutzt bereits eine moderne C#/WPF-Architektur als Prototyp

**Projektziel:** PB Studio soll feature-parität mit der NVIDIA-Version erreichen, dabei aber AMD DirectML verwenden.

---

## Entscheidung

PB Studio wird in eine **C# WPF .NET 9.0 + Python FastAPI Hybrid-Anwendung** migriert.

```
┌─────────────────────────────────────────────────────────────────┐
│                    C# WPF Frontend (.NET 9.0)                   │
│  MVVM (CommunityToolkit.Mvvm) │ MaterialDesignThemes │ MahApps  │
│  ViewModels ←→ Commands ←→ Views (XAML)                        │
│                      ↕ HTTP/REST + SSE                          │
│                  localhost:8765                                  │
└─────────────────────────────────────────────────────────────────┘
                             ↕
┌─────────────────────────────────────────────────────────────────┐
│                   Python FastAPI Backend                         │
│  audio_router │ video_router │ pacing_router │ render_router    │
│  asyncio.to_thread() für blockierende ML-Calls                  │
└─────────────────────────────────────────────────────────────────┘
                             ↕
┌─────────────────────────────────────────────────────────────────┐
│              Python Core (UNVERÄNDERT — kein Refactoring)        │
│  audio/ │ video/ │ pacing/ │ ai/ │ database/ │ rendering/       │
│  DirectML (ONNX) │ FAISS-CPU │ SQLite │ DuckDB                  │
└─────────────────────────────────────────────────────────────────┘
```

### Kommunikationsprotokoll

| Richtung | Protokoll | Verwendung |
|----------|-----------|------------|
| C# → Python | HTTP REST (Port 8765) | Import, Analyse starten, Konfiguration |
| Python → C# | Server-Sent Events (SSE) | Progress, Logs, Status-Updates |
| C# ↔ Python | HTTP Long-Polling (Fallback) | Wenn SSE nicht verfügbar |

---

## Optionen Evaluiert

### Option A: C# WPF + Python FastAPI (Gewählt)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Hoch (2 Prozesse, IPC) |
| GPU-Kompatibilität | ✅ Python behält 100% Kontrolle über DirectML |
| UI-Qualität | ✅ XAML, MVVM, DataBinding, Animationen |
| Testbarkeit | ✅ ViewModel-Tests ohne GPU |
| Portabilität | ⚠️ Windows only (WPF) |
| Aufwand | Hoch (Migration) |

**Pros:**
- Klare Trennung von UI und ML-Logic (keine GUI-Blocking-Risiken mehr)
- XAML + MVVM: deutlich bessere UI-Wartbarkeit
- C# Async/Await: native non-blocking UI-Patterns
- Python-Core bleibt unverändert: kein Rewrite-Risiko für ML-Pipelines
- CommunityToolkit.Mvvm: Source-Generator-basiertes MVVM ohne Boilerplate

**Cons:**
- Zwei separate Prozesse müssen synchronisiert werden
- Startup-Latenz: Python FastAPI muss vor C# gestartet sein
- Debug-Overhead: Fehler können in beiden Schichten liegen
- SSE-Reconnect-Logik erforderlich

---

### Option B: Bleiben bei PyQt6

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Niedrig |
| GPU-Kompatibilität | ✅ |
| UI-Qualität | ⚠️ Kein natives MVVM, schlechtes DataBinding |
| Testbarkeit | ❌ GUI eng mit Logic verknüpft |
| Aufwand | Niedrig |

**Cons:** Keine Feature-Parität mit NVIDIA-Prototyp möglich. GUI-Blocking-Problem ungelöst.

---

### Option C: Electron + Python Backend

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Hoch (Node.js + Python) |
| GPU-Kompatibilität | ✅ |
| UI-Qualität | ✅ Web-Technologien |
| Testbarkeit | ✅ |
| Bundle-Größe | ❌ Electron ~200MB Overhead |

**Abgelehnt:** Team hat keine Electron-Erfahrung. Chromium-Overhead. Nicht kompatibel mit der NVIDIA-Vorlage.

---

### Option D: Vollmigration zu .NET MAUI (C# everywhere)

**Abgelehnt:** DirectML, FAISS, Demucs, BeatNet — alle haben ausschließlich Python-Bindings. Ein Python-Rewrite in C# würde Monate dauern und alle ML-Modelle gefährden.

---

## Trade-off Analyse

**Hauptspannung:** Komplexität (2-Prozess-Architektur) vs. Qualität (MVVM, Testbarkeit, keine GUI-Blocks)

Die 2-Prozess-Architektur ist akzeptabel weil:
1. Die ML-Operationen sind ohnehin langläufig (Sekunden bis Minuten) — Prozessgrenzen fügen keine merkliche Latenz hinzu
2. FastAPI mit asyncio.to_thread() löst das GUI-Blocking-Problem fundamental, nicht nur symptomatisch
3. Der Python-Core bleibt zu 100% unverändert — das eliminiert das größte Migrations-Risiko

---

## Architektur-Regeln (Bindend)

### Was C# WPF ersetzt (Frontend-Only):
- Alle `.py`-Dateien in `pb_studio/gui/` (Widgets, Tabs, Windows, Workers)
- PyQt6-Worker werden zu C# `async Task`-Methoden

### Was Python bleibt (Core — UNBERÜHRBAR):
```
pb_studio/core/      → VRAM-Arbiter, Task-Queue
pb_studio/audio/     → BeatNet, Demucs
pb_studio/video/     → Moondream, RAFT
pb_studio/pacing/    → AdvancedPacingEngine, SmartDirector
pb_studio/database/  → SQLite (SQLAlchemy), FAISS
pb_studio/rendering/ → FFmpeg AMF
pb_studio/ai/        → CLAP, SigLIP
```

### C# Pflichtbibliotheken:
| Zweck | Bibliothek |
|-------|-----------|
| MVVM | CommunityToolkit.Mvvm (Source Generators) |
| UI-Design | MaterialDesignThemes.Wpf |
| Icons | MahApps.Metro.IconPacks.Material |
| Behaviors | Microsoft.Xaml.Behaviors.Wpf |
| HTTP | System.Net.Http.HttpClient |
| JSON | System.Text.Json |

### Python FastAPI Pflichtregeln:
- Vollständig `async def` — kein `def` in Endpunkten
- Blockierende ML-Calls via `asyncio.to_thread()` wrappen
- Pydantic-Schemas für alle Request/Response-Bodies
- Port: **8765** (fest)

---

## Konsequenzen

### Was einfacher wird:
- UI-Tests: ViewModels testbar ohne GPU/Python
- UI-Entwicklung: XAML DataBinding ersetzt manuelles `connect()`/`emit()`
- Parallelentwicklung: Frontend und Backend unabhängig entwickelbar
- Fehlerdiagnose: ML-Fehler bleiben in Python-Logs, UI-Fehler in C#-Logs

### Was schwieriger wird:
- **Startup-Sequenz:** C# muss warten bis FastAPI bereit ist (Health-Check auf `/health`)
- **Fehlerbehandlung:** Netzwerk-Fehler zwischen C# und Python müssen in `ApiClient.cs` behandelt werden
- **State-Synchronisation:** Python-State (geladene Clips, aktive Analyse) muss über API abrufbar sein
- **Deployment:** Zwei separate Prozesse müssen gestartet/gestoppt werden

### Was wir neu brauchen:
- `ApiClient.cs`: Zentraler HTTP-Client (implementiert, braucht noch `IApiClient`-Interface)
- SSE-Subscription-Logik in C# (noch nicht implementiert)
- Python-Process-Launcher in C# (noch nicht implementiert)
- `IApiClient`-Interface für Testbarkeit (noch ausstehend — Tech-Debt #7)

---

## Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| SSE-Verbindungsabbruch | Mittel | Auto-Reconnect mit Exponential-Backoff |
| Python-Prozess-Crash | Niedrig | C# überwacht Prozess-PID, zeigt Fehler-Dialog |
| Port-Konflikt (8765) | Niedrig | Konfigurierbarer Port via `appsettings.json` |
| Latenz bei ML-Progress | Niedrig | SSE-Updates alle 100ms — wahrnehmbar flüssig |

---

## Offene Punkte (Action Items)

- [ ] **`IApiClient`-Interface extrahieren** (Tech-Debt #7) — für ViewModel-Tests
- [ ] **`ConfigureAwait(false)`** in allen 45 C# `await`-Calls (Tech-Debt #5)
- [ ] **SSE-Integration** in C# ViewModels (noch nicht implementiert)
- [ ] **Python-Prozess-Launcher:** C# soll `uvicorn backend.main:app` starten und überwachen
- [ ] **`appsettings.json`:** Port (8765) konfigurierbar machen

---

*ADR erstellt: 2026-03-04 | Nächste Review: nach WPF-Migration Phase 1 abgeschlossen*
