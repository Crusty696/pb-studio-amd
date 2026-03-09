# Research & Documentation Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Research", "Dokumentation", "README", "Analyse", "Investigate"
- Fragen zu unbekannten Technologien, Best Practices
- Arbeit an `*.md` Dateien, Kommentaren, Docstrings
- Vor komplexen Implementierungen (Research Phase)

## Cross-References
- → `generic-workflow.md` (Analyze Phase)
- → `python-backend.md` (Docstrings)
- → `debugging.md` (Problem Analysis)
- → Alle Skills (Dokumentation der Patterns)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Living Docs** | Dokumentation ist die Karte zum Code |
| **Deep Analysis** | Verstehen WARUM, nicht nur WIE |
| **AMD/DirectML Focus** | Edge Cases für diese Plattform dokumentieren |

---

## 1. Research Protocol

```
┌─────────────────────────────────────────────────────────┐
│              RESEARCH WORKFLOW                          │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  1. DEFINE - Was genau ist die Frage?                   │
│     • Präzise Formulierung                              │
│     • Kontext: AMD/DirectML/Offline relevant?           │
│     • Scope begrenzen                                   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  2. SEARCH - Informationen sammeln                      │
│     • Offizielle Docs (Microsoft, ONNX, PyQt)           │
│     • GitHub Issues/Discussions                         │
│     • Stack Overflow (mit Vorsicht)                     │
│     • Bestehender Code im Projekt                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  3. VERIFY - Quellen prüfen                             │
│     • Ist die Info aktuell?                             │
│     • Passt sie zu unserer Python/PyQt Version?         │
│     • Funktioniert sie mit DirectML (AMD)?              │
│     • Cross-Reference mit anderen Quellen               │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  4. SYNTHESIZE - Erkenntnisse zusammenfassen            │
│     • Kernaussagen extrahieren                          │
│     • Relevanz für PB Studio bewerten                   │
│     • In eigene Worte fassen                            │
│     • Code-Beispiele erstellen                          │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  5. DOCUMENT - Ergebnisse festhalten                    │
│     • In Implementation Plan aufnehmen                  │
│     • Lessons Learned dokumentieren                     │
│     • Für Team zugänglich machen                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Search Strategies

```python
# Effektive Suchbegriffe für PB Studio

SEARCH_TEMPLATES = {
    "directml_issues": [
        "onnxruntime directml {problem}",
        "DmlExecutionProvider {error}",
        "AMD GPU onnx {topic}",
        "site:github.com/microsoft/onnxruntime {issue}"
    ],
    
    "pyqt6_issues": [
        "PyQt6 {widget} {problem}",
        "Qt6 {signal} thread",
        "site:riverbankcomputing.com {topic}"
    ],
    
    "audio_processing": [
        "librosa {function} {issue}",
        "soundfile python {format}",
        "audio stem separation offline"
    ],
    
    "python_patterns": [
        "python 3.10+ {pattern}",
        "asyncio {topic} best practice",
        "pathlib {operation}"
    ]
}

# Vertrauenswürdige Quellen (Priorität)
TRUSTED_SOURCES = {
    "tier1_official": [
        "docs.python.org",
        "doc.qt.io",
        "onnxruntime.ai",
        "docs.microsoft.com"
    ],
    
    "tier2_community": [
        "github.com/microsoft/onnxruntime",
        "stackoverflow.com (mit >10 upvotes)"
    ],
    
    "tier3_blogs": [
        "realpython.com",
        "medium.com (verifizierte Autoren)"
    ]
}
```

---

## 3. Documentation Templates

### Implementation Plan Template

```markdown
# Implementation Plan: [Feature Name]

## Datum: YYYY-MM-DD
## Status: Draft | In Review | Approved | In Progress | Done

## 1. Übersicht
[1-2 Absätze die das Feature beschreiben]

## 2. Motivation
- Warum brauchen wir das?
- Welches Problem wird gelöst?
- Wie passt es in den Master Plan?

## 3. Research Ergebnisse
### 3.1 Technologie-Analyse
[Ergebnisse der Research Phase]

### 3.2 Bestehende Lösungen
| Lösung | Vorteile | Nachteile | AMD-kompatibel |
|--------|----------|-----------|----------------|
| A      | ...      | ...       | Ja/Nein        |
| B      | ...      | ...       | Ja/Nein        |

### 3.3 Gewählter Ansatz
[Begründung der Entscheidung]

## 4. Technische Spezifikation
### 4.1 Architektur
[Diagramm oder Beschreibung]

### 4.2 Betroffene Dateien
- `src/...` - [Änderungen]
- `src/...` - [Änderungen]

### 4.3 Neue Dependencies
- `package==version` - [Grund]

## 5. Implementation Steps
- [ ] Step 1: ...
- [ ] Step 2: ...
- [ ] Step 3: ...

## 6. Testing Strategy
- [ ] Unit Tests für ...
- [ ] Integration Test für ...
- [ ] Manual Test: ...

## 7. Risiken & Mitigations
| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| ...    | Hoch/Mittel/Niedrig | Hoch/Mittel/Niedrig | ... |

## 8. Erfolgskriterien
- [ ] Kriterium 1
- [ ] Kriterium 2
- [ ] AMD GPU getestet
- [ ] Offline-Modus verifiziert
```

---

## 4. Code Documentation Standards

### Docstrings (Google Style)

```python
def complex_function(
    audio_data: np.ndarray,
    sample_rate: int,
    options: ProcessingOptions | None = None
) -> ProcessingResult:
    """Verarbeitet Audio-Daten mit konfigurierbaren Optionen.
    
    Führt eine mehrstufige Audio-Analyse durch, einschließlich
    BPM-Erkennung und Transient-Detection. Optimiert für AMD GPUs
    via DirectML.
    
    Args:
        audio_data: Audio-Samples als numpy Array. 
            Shape: (samples,) für Mono oder (2, samples) für Stereo.
        sample_rate: Sample-Rate in Hz (typisch 44100 oder 48000).
        options: Optionale Verarbeitungseinstellungen.
            Wenn None, werden Defaults verwendet.
    
    Returns:
        ProcessingResult mit folgenden Feldern:
            - bpm: Erkannte BPM (float)
            - beats: Liste der Beat-Zeitpunkte in Sekunden
            - transients: Liste der Transient-Positionen
    
    Raises:
        ValueError: Wenn audio_data leer oder ungültiges Format.
        RuntimeError: Wenn GPU-Verarbeitung fehlschlägt.
    
    Example:
        >>> audio, sr = librosa.load("song.mp3", sr=44100)
        >>> result = complex_function(audio, sr)
        >>> print(f"BPM: {result.bpm}")
        BPM: 128.0
    
    Note:
        Diese Funktion ist CPU-intensiv. Für UI-Integration
        sollte sie in einem separaten Thread ausgeführt werden.
        Siehe gui-framework.md für Worker-Pattern.
    """
    pass
```

### Inline Comments

```python
# ✅ GUT - Erklärt WARUM
# DirectML benötigt explizite Float32-Konvertierung,
# da FP16 auf manchen AMD Karten instabil ist
input_data = data.astype(np.float32)

# ✅ GUT - Warnt vor Edge Case
# WICHTIG: iPhone Videos sind oft VFR (Variable Frame Rate),
# was zu Timing-Problemen führen kann
fps = self._detect_fps(video_path)

# ❌ SCHLECHT - Erklärt nur WAS (offensichtlich)
# Konvertiere zu Float32
input_data = data.astype(np.float32)
```

---

## 5. Knowledge Base Integration

```python
# Automatische Extraktion von Learnings aus Code-Kommentaren

import re
from pathlib import Path

def extract_learnings(source_dir: Path) -> list[dict]:
    """Extrahiert dokumentierte Learnings aus Code."""
    
    patterns = {
        "lesson": re.compile(r'# LESSON:\s*(.+)'),
        "gotcha": re.compile(r'# GOTCHA:\s*(.+)'),
        "important": re.compile(r'# IMPORTANT:\s*(.+)'),
        "amd_note": re.compile(r'# AMD:\s*(.+)'),
        "offline_note": re.compile(r'# OFFLINE:\s*(.+)')
    }
    
    learnings = []
    
    for py_file in source_dir.glob("**/*.py"):
        content = py_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            for tag, pattern in patterns.items():
                match = pattern.search(line)
                if match:
                    learnings.append({
                        "type": tag,
                        "message": match.group(1),
                        "file": str(py_file),
                        "line": i + 1
                    })
    
    return learnings

# Verwendung im Code:
# LESSON: DirectML benötigt Opset Version >= 14 für Transformer-Modelle
# GOTCHA: librosa.load() lädt standardmäßig als Mono - für Stereo sr=None setzen
# AMD: h264_amf Encoder benötigt AMD Treiber >= 21.10
# OFFLINE: Dieses Model muss vor Runtime heruntergeladen werden
```

---

## Checkliste: Research & Documentation

### Vor dem Research
- [ ] Frage präzise formuliert?
- [ ] Scope begrenzt?
- [ ] AMD/Offline-Kontext berücksichtigt?

### Während des Research
- [ ] Mehrere Quellen konsultiert?
- [ ] Offizielle Docs priorisiert?
- [ ] Aktualität geprüft?

### Nach dem Research
- [ ] Ergebnisse dokumentiert?
- [ ] Code-Beispiele erstellt?
- [ ] Lessons Learned festgehalten?
- [ ] Für Team zugänglich?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| Veraltete Info | Alte SO-Antwort | Datum prüfen, offizielle Docs |
| Andere GPU-Lösung | Falsche Quellen | Explizit nach DirectML/AMD suchen |
| Unvollständige Docs | Zu wenig Zeit | Templates verwenden |
| Verloren gegangenes Wissen | Nicht dokumentiert | Research Log führen |
