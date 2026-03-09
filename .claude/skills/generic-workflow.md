# Generic Development Workflow Skill ("The Finalizer")

## Trigger
Aktiviere diesen Skill automatisch bei:
- Beginn jeder neuen Entwicklungsaufgabe
- "Implementiere", "Erstelle", "Baue", "Entwickle"
- Komplexe Änderungen an mehreren Dateien
- Immer als Meta-Framework für andere Skills

## Cross-References
- → ALLE anderen Skills (dieser Skill ist das Meta-Framework)
- → `verification.md` (Schritt 4: Reflect)
- → `research-docs.md` (Schritt 1: Analyze)
- → `python-backend.md` (Schritt 3: Execute)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **AMD-Only** | Ausschließlich AMD GPU Support via DirectML |
| **Offline-Safe** | Keine versteckten Internet-Abhängigkeiten |
| **Stability** | Finalisierungsphase - Stabilität vor Features |

---

## Der Core Cycle

```
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   ┌──────────┐    ┌──────────┐    ┌──────────┐         │
    │   │          │    │          │    │          │         │
    │   │ ANALYZE  │───▶│   PLAN   │───▶│ EXECUTE  │         │
    │   │          │    │          │    │          │         │
    │   └──────────┘    └──────────┘    └──────────┘         │
    │        ▲                               │               │
    │        │                               ▼               │
    │        │                         ┌──────────┐          │
    │        │                         │          │          │
    │        └─────────────────────────│ REFLECT  │          │
    │              (bei Problemen)     │          │          │
    │                                  └──────────┘          │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

---

## Phase 1: 🔍 ANALYZE (Context Check)

### Vor dem ersten Codezeile MUSS ich:

```python
# Mental Checklist - vor jeder Implementierung durchgehen

ANALYZE_CHECKLIST = {
    "master_plan": "Passt diese Änderung zum MASTER_PLAN_v10.md?",
    "related_files": "Habe ich ALLE betroffenen Dateien gelesen?",
    "dependencies": "Welche Module/Funktionen werden verwendet?",
    "hardware_context": "Ist das AMD/DirectML-safe?",
    "offline_context": "Braucht das Internet-Zugriff?",
    "existing_patterns": "Gibt es ähnlichen Code im Projekt?"
}
```

### Analyse-Schritte:

1. **Master Plan prüfen**
   ```
   Lese: MASTER_PLAN_v10.md
   Frage: Ist meine Aufgabe dort beschrieben?
   ```

2. **Betroffene Dateien lesen**
   ```
   - Zieldatei(en) komplett lesen
   - Direkte Imports/Dependencies identifizieren
   - Tests falls vorhanden
   ```

3. **Hardware-Kontext prüfen**
   ```
   Frage: Verwendet dieser Code GPU-spezifische Features?
   - Wenn ja: DirectML-Kompatibilität sichergestellt?
   - CPU Fallback vorhanden?
   ```

4. **Dependency Check**
   ```
   Lese: pyproject.toml oder requirements.txt
   Frage: Sind alle benötigten Libraries verfügbar?
   ```

---

## Phase 2: 📝 PLAN (Roadmap)

### Für komplexe Änderungen MUSS ein Plan erstellt werden:

```markdown
# Implementation Plan: [Feature Name]

## Ziel
[1-2 Sätze was erreicht werden soll]

## Betroffene Dateien
- `src/pb_studio/module/file.py` - [was wird geändert]
- `src/pb_studio/gui/widget.py` - [was wird geändert]

## Implementierungsschritte
1. [ ] Schritt 1 - [Beschreibung]
2. [ ] Schritt 2 - [Beschreibung]
3. [ ] Schritt 3 - [Beschreibung]

## Erfolgskriterien
- [ ] Kriterium 1
- [ ] Kriterium 2

## Risiken
- Risiko 1: [Beschreibung] → Mitigation: [Lösung]
- Risiko 2: [Beschreibung] → Mitigation: [Lösung]

## AMD/Offline Checks
- [ ] Nur DirectML verwendet
- [ ] Keine Internet-Abhängigkeit zur Runtime
- [ ] AMD GPU getestet
```

### Plan-Entscheidungsbaum:

```
Ist die Änderung...
│
├── Einfach (1 Datei, < 50 Zeilen)?
│   └── Kein formeller Plan nötig, aber mental durchgehen
│
├── Mittel (2-5 Dateien, neue Funktion)?
│   └── Kurzer Plan in Kommentar oder mental
│
└── Komplex (> 5 Dateien, Architektur-Änderung)?
    └── Formeller Implementation Plan ERFORDERLICH
```

---

## Phase 3: 💻 EXECUTE (Implementation)

### Coding-Regeln:

```python
# ✅ RICHTIG: Vollständiger, funktionaler Code
def process_audio(file_path: Path) -> dict:
    """Verarbeitet Audio-Datei und gibt Analyse zurück."""
    if not file_path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")
    
    audio, sr = librosa.load(str(file_path), sr=44100)
    tempo, beats = librosa.beat.beat_track(y=audio, sr=sr)
    
    return {
        "bpm": float(tempo),
        "beats": beats.tolist(),
        "duration": len(audio) / sr
    }

# ❌ FALSCH: Placeholder-Code
def process_audio(file_path: Path) -> dict:
    # TODO: Implement audio processing
    pass
```

### Skill-Delegation:

| Aufgabe | Verwende Skill |
|---------|----------------|
| ONNX/DirectML Code | `ai-inference.md` |
| Audio-Verarbeitung | `audio-engineering.md` |
| Video/FFmpeg | `video-engineering.md` |
| PyQt6 GUI | `gui-framework.md` |
| Datenbank/Vektoren | `data-persistence.md` |
| Error Handling | `python-backend.md` |
| Performance Issues | `debugging.md` |

### Code-Preservation:

```python
# Wenn alter Code ersetzt wird:

# DEPRECATED: Alte Implementierung (Grund: Performance)
# def old_function():
#     ...

# Neue Implementierung
def new_function():
    ...
```

### Logging:

```python
import logging
logger = logging.getLogger(__name__)

def critical_operation():
    logger.info("Starting critical operation")
    try:
        result = do_something()
        logger.debug(f"Operation result: {result}")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise
```

---

## Phase 4: 🧠 REFLECT (Self-Correction)

### Die 4 Pflicht-Checks:

```python
REFLECT_CHECKS = {
    "amd_check": """
        Frage: Wird dieser Code auf einer AMD-Karte crashen?
        - Nur DirectML verwendet
        - CPU Fallback vorhanden
    """,
    
    "offline_check": """
        Frage: Funktioniert das ohne Internet?
        - Keine huggingface_hub Downloads zur Runtime
        - Alle Models lokal in models/
        - Keine API-Calls
    """,
    
    "ui_check": """
        Frage: Blockiert das den Main Thread?
        - Schwere Operationen in QThread
        - Keine Schleifen > 100ms im Main Thread
        - Progress-Feedback für lange Operationen
    """,
    
    "verification": """
        Frage: Wie weiß ich dass es funktioniert?
        - Code ausgeführt oder Test geschrieben
        - Logs geprüft
        - Edge Cases berücksichtigt
    """
}
```

### Reflection-Workflow:

```
┌─────────────────────────────────────────────────────────┐
│  Nach jeder Implementation:                              │
│                                                          │
│  1. AMD Check bestanden?                                │
│     └── Nein → Zurück zu EXECUTE, DirectML verwenden   │
│                                                          │
│  2. Offline Check bestanden?                            │
│     └── Nein → Zurück zu EXECUTE, lokale Assets nutzen │
│                                                          │
│  3. UI Check bestanden?                                 │
│     └── Nein → Zurück zu EXECUTE, QThread verwenden    │
│                                                          │
│  4. Verification bestanden?                             │
│     └── Nein → Test schreiben/ausführen                │
│                                                          │
│  Alle Ja? → DONE ✅                                     │
└─────────────────────────────────────────────────────────┘
```

---

## Anti-Patterns (NIEMALS tun)

### 1. Hardcoded Provider
```python
# ❌ FALSCH
providers = ['CPUExecutionProvider']  # Verschenkt GPU Power

# ✅ RICHTIG
providers = get_optimal_providers()  # DML > CPU
```

### 2. Silent Failures
```python
# ❌ FALSCH
try:
    dangerous_operation()
except:
    pass

# ✅ RICHTIG
try:
    dangerous_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise  # oder sinnvolle Fehlerbehandlung
```

### 3. UI Blocking
```python
# ❌ FALSCH (in Widget.__init__)
def __init__(self):
    self.model = load_heavy_model()  # Blockiert UI

# ✅ RICHTIG
def __init__(self):
    QTimer.singleShot(0, self._load_model_async)

def _load_model_async(self):
    self.loader_thread = ModelLoaderThread()
    self.loader_thread.finished.connect(self._on_model_loaded)
    self.loader_thread.start()
```

### 4. Internet-Abhängigkeit
```python
# ❌ FALSCH
model = AutoModel.from_pretrained("openai/clip")  # Downloads!

# ✅ RICHTIG
model_path = Path("models/clip.onnx")
if not model_path.exists():
    raise FileNotFoundError("Model nicht gefunden. Bitte Setup ausführen.")
session = ort.InferenceSession(str(model_path))
```

---

## Checkliste: Workflow Completion

### Vor dem Commit
- [ ] ANALYZE: Alle betroffenen Dateien gelesen?
- [ ] PLAN: Bei komplexen Änderungen Plan erstellt?
- [ ] EXECUTE: Code vollständig (keine TODOs)?
- [ ] REFLECT: Alle 4 Checks bestanden?

### Qualitäts-Gates
- [ ] Nur DirectML für GPU?
- [ ] Kein bare `except: pass`?
- [ ] Keine UI-blockierenden Operationen?
- [ ] Logging für wichtige Operationen?
- [ ] Type Hints vorhanden?

---

## Quick Reference: Skill-Auswahl

```
Was mache ich gerade?
│
├── AI/ML Inference → ai-inference.md
├── Audio verarbeiten → audio-engineering.md
├── Video verarbeiten → video-engineering.md
├── GUI entwickeln → gui-framework.md
├── Datenbank/Vektoren → data-persistence.md
├── Bug fixen → debugging.md
├── Architektur planen → service-architecture.md
├── Hardware-Integration → hardware-control.md
├── Offline-Funktionalität → offline-engineering.md
├── Research/Docs → research-docs.md
├── Testing/QA → verification.md
└── Allgemein Python → python-backend.md
```
