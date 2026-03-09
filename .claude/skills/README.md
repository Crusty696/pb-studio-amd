# PB Studio Skills - Master Index

## Übersicht

Dieses Skill-System wurde für **PB Studio** entwickelt und optimiert für:
- **AMD GPU Only** (DirectML-First, kein anderer GPU-Hersteller)
- **100% Offline-Betrieb** (keine Runtime-Downloads)
- **PyQt6 GUI** (Thread-Safety, Responsiveness)

---

## 🗂️ Skill-Katalog

### Core Skills (Meta-Framework)

| Skill | Datei | Beschreibung |
|-------|-------|--------------|
| **Generic Workflow** | `generic-workflow.md` | Analyze→Plan→Execute→Reflect Zyklus |
| **Verification** | `verification.md` | Testing, QA, Checklisten |
| **Research & Docs** | `research-docs.md` | Recherche-Protokoll, Dokumentation |

### Domain Skills (Feature-spezifisch)

| Skill | Datei | Beschreibung |
|-------|-------|--------------|
| **AI Inference** | `ai-inference.md` | ONNX + DirectML, FP16/FP32, GPU-Fallback |
| **Audio Engineering** | `audio-engineering.md` | Stem Separation, BPM, librosa |
| **Video Engineering** | `video-engineering.md` | FFmpeg, CLIP, Frame Extraction |
| **GUI Framework** | `gui-framework.md` | PyQt6, Signals/Slots, Threading |
| **Data Persistence** | `data-persistence.md` | SQLite, FAISS Vektoren |

### Infrastructure Skills

| Skill | Datei | Beschreibung |
|-------|-------|--------------|
| **Python Backend** | `python-backend.md` | Type Hints, Error Handling, Patterns |
| **Service Architecture** | `service-architecture.md` | Module, DI, Event Bus |
| **Hardware Control** | `hardware-control.md` | AMD GPU Detection, LibreHardwareMonitor |
| **Offline Engineering** | `offline-engineering.md` | Asset Management, Offline-Safety |
| **Debugging** | `debugging.md` | Log Analysis, Profiling, GPU Debug |

---

## 🔗 Cross-Reference Matrix

```
                     ┌───────────────────────────────────────────────────────────────┐
                     │                    SKILL DEPENDENCIES                          │
                     └───────────────────────────────────────────────────────────────┘

generic-workflow ────────────────────┬───────────────────────────────────────────────┐
        │                            │                                               │
        ▼                            ▼                                               ▼
┌───────────────┐           ┌───────────────┐                              ┌───────────────┐
│   Research    │           │  Verification │                              │   Debugging   │
│    & Docs     │           │     & QA      │                              │  & Profiling  │
└───────────────┘           └───────────────┘                              └───────────────┘
        │                            │                                               │
        └────────────────────────────┼───────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────────────────────────┐
        │                            │                                                │
        ▼                            ▼                                                ▼
┌───────────────┐           ┌───────────────┐                              ┌───────────────┐
│     Audio     │           │     Video     │                              │      GUI      │
│  Engineering  │           │  Engineering  │                              │   Framework   │
└───────────────┘           └───────────────┘                              └───────────────┘
        │                            │                                                │
        └──────────────┬─────────────┴────────────────────────────────────────────────┘
                       │
                       ▼
              ┌───────────────┐
              │  AI Inference │
              │(ONNX/DirectML)│
              └───────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────┐           ┌───────────────┐
│   Hardware    │           │    Offline    │
│   Control     │           │  Engineering  │
└───────────────┘           └───────────────┘
        │                             │
        └──────────────┬──────────────┘
                       │
                       ▼
              ┌───────────────┐
              │     Data      │
              │  Persistence  │
              └───────────────┘
                       │
                       ▼
              ┌───────────────┐
              │    Service    │
              │  Architecture │
              └───────────────┘
                       │
                       ▼
              ┌───────────────┐
              │    Python     │
              │    Backend    │
              └───────────────┘
```

---

## 🎯 Skill-Auswahl nach Aufgabe

### "Ich will..."

| Aufgabe | Primary Skill | Supporting Skills |
|---------|---------------|-------------------|
| ...Audio analysieren | `audio-engineering` | `ai-inference`, `offline-engineering` |
| ...Video verarbeiten | `video-engineering` | `hardware-control`, `ai-inference` |
| ...GUI bauen | `gui-framework` | `service-architecture`, `python-backend` |
| ...Daten speichern | `data-persistence` | `python-backend` |
| ...AI Model nutzen | `ai-inference` | `hardware-control`, `offline-engineering` |
| ...Bug fixen | `debugging` | `verification`, `python-backend` |
| ...Feature planen | `generic-workflow` | `research-docs` |
| ...Code testen | `verification` | `debugging` |
| ...Hardware erkennen | `hardware-control` | `ai-inference` |

---

## 🚀 Quick Start

### 1. Workflow starten
Jede Aufgabe beginnt mit dem **Generic Workflow**:
```
1. ANALYZE - Code lesen, Context verstehen
2. PLAN    - Bei komplexen Änderungen
3. EXECUTE - Mit dem passenden Domain-Skill
4. REFLECT - AMD-Check, Offline-Check, UI-Check
```

### 2. Skill aktivieren
Skills werden automatisch aktiviert durch:
- **Keywords** im Prompt (z.B. "ONNX", "PyQt6", "BPM")
- **Datei-Patterns** (z.B. `*_inference.py`, `*_widget.py`)
- **Explizite Anfrage** ("verwende audio-engineering skill")

### 3. AMD-Only Mindset
Jeder Skill verwendet ausschließlich AMD-kompatible Patterns:
- `get_optimal_providers()` → DirectML > CPU
- Kein anderer GPU-Hersteller wird unterstützt
- CPU Fallback immer implementiert

---

## 📋 Globale Checklisten

### Vor jeder Implementation
- [ ] Passenden Skill identifiziert?
- [ ] Generic Workflow gestartet (ANALYZE)?
- [ ] AMD-Kompatibilität berücksichtigt?
- [ ] Offline-Safety geprüft?

### Nach jeder Implementation
- [ ] REFLECT Phase durchgeführt?
- [ ] Tests geschrieben/aktualisiert?
- [ ] Dokumentation aktuell?
- [ ] Keine ERROR in Logs?

---

## 🔧 Skill-Erweiterung

### Neuen Skill erstellen
```markdown
# [Skill Name]

## Trigger
- Keywords: [...]
- Datei-Patterns: [...]
- Kontext: [...]

## Cross-References
- → skill1.md (Grund)
- → skill2.md (Grund)

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| ... | ... |

## [Hauptabschnitte mit Code-Beispielen]

## Checkliste
- [ ] ...

## Häufige Fehler & Lösungen
| Fehler | Ursache | Lösung |
|--------|---------|--------|
| ... | ... | ... |
```

---

## 📊 Skill-Statistiken

| Metrik | Wert |
|--------|------|
| Anzahl Skills | 13 |
| Code-Beispiele | 100+ |
| Checklisten | 13 |
| Cross-References | 50+ |

---

## 🏷️ Tags

Alle Skills verwenden konsistente Tags:
- `#amd` - AMD GPU spezifisch
- `#directml` - DirectML Provider
- `#offline` - Offline-Betrieb
- `#pyqt6` - GUI Framework
- `#onnx` - ONNX Runtime
- `#threading` - Multi-Threading
- `#ffmpeg` - Video Processing (AMD AMF)
- `#librosa` - Audio Processing
- `#sqlite` - Datenbank
- `#faiss` - Vector Store

---

*Letzte Aktualisierung: 2025-01-24*
*Version: 2.0 (AMD-Only Edition für Claude Code)*
