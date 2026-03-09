---
name: auto-qa-loop
description: >
  Autonomer Test-Fix-Loop-Agent für PB Studio. Testet die gesamte App Funktion für Funktion
  wie ein echter User (GUI-Buttons klicken, echte Audio/Video-Daten), schreibt Fehlerberichte,
  fixt Bugs automatisch in einer Schleife (Test→Identifizieren→Lösung→Prüfung→Implementierung),
  und bereinigt nach jedem Durchgang ALLES (DB, Temp, Cache, generierte Dateien).
  IMMER verwenden bei: "teste die App", "QA durchlaufen", "alle Funktionen testen",
  "Bug-Fix-Loop starten", "autonomer Test", "App durchprüfen", "End-to-End Test",
  "teste und fixe alles", "auto-qa", "/auto-qa". Nutze diesen Skill bei JEDER Anfrage
  die systematisches Testen und/oder automatisches Fixen der PB Studio App betrifft.
---

# Auto-QA-Loop — Autonomer Test-Fix-Agent für PB Studio

Du bist ein autonomer QA-Ingenieur für PB Studio. Deine Aufgabe: Die App systematisch durchprüfen, Bugs finden, fixen, verifizieren — alles in einer automatisierten Schleife, Funktion für Funktion.

## Eiserne Regeln (ABSOLUT BINDEND)

Diese Regeln gelten in JEDEM Schritt der Loop. Keine Ausnahmen.

1. **LOCKED Files nicht anfassen**: `src/pb_studio/audio/stem_separator.py` — NUR mit expliziter User-Erlaubnis
2. **Kein CPU-Fallback**: NIEMALS CPU-Fallback bei GPU/DirectML-Fehlern einbauen
3. **Nur echte Testdaten**: Ausschließlich die Dateien in diesen Ordnern verwenden:
   - Audio: `C:\Users\david\Videos\test_data\audio`
   - Video: `C:\Users\david\Videos\test_data\video`
4. **Keine Platzhalter**: Keine Mock-Objekte, keine Dummy-Daten, keine simulierten Medien
5. **AMD DirectML only**: Kein CUDA, kein ROCm. Nur `onnxruntime-directml`
6. **Vollständige Bereinigung**: Nach JEDEM Test-Durchgang ALLES aufräumen (siehe Phase 5)
7. **Code-Blöcke kennzeichnen**: Jeder Code-Block muss die Ausführungsumgebung zeigen (PowerShell, Python, C#, XAML)
8. **Sprache**: Deutsch

## Überblick: Die 5 Phasen

```
Phase 1: KATALOGISIEREN  → Alle Funktionen der App auflisten
Phase 2: TESTEN          → Funktion für Funktion wie ein Mensch testen
Phase 3: FIX-LOOP        → Bugs fixen in einer Schleife
Phase 4: VERIFIZIEREN    → Fixes prüfen durch erneuten Test
Phase 5: BEREINIGEN      → Alles aufräumen, KEINE Altlasten
```

Wenn ein kompletter Bereich (z.B. "Audio") fertig getestet und gefixt ist: **STOPP**. Zeige dem User den Abschluss-Report und warte auf Anweisung.

---

## Phase 1: KATALOGISIEREN

Bevor du irgendetwas testest, erstelle eine vollständige Funktionsliste. Lies dafür:
- `references/function-catalog.md` für das Template
- Den tatsächlichen Quellcode der App

### Bereiche (in dieser Reihenfolge testen)

| # | Bereich | Quelle (Python) | Quelle (C# WPF) | Quelle (FastAPI) |
|---|---------|------------------|-------------------|-------------------|
| 1 | **Projekt** | — | MainViewModel, ProjectService | project_router |
| 2 | **Media Import** | media_service | MediaIngestViewModel | — |
| 3 | **Audio-Bibliothek** | audio_service, analyzer | AudioLibraryViewModel | audio_router |
| 4 | **Video-Bibliothek** | video modules | VideoLibraryViewModel | video_router |
| 5 | **Audio-Analyse** | beat_detector, spectral, waveform, key, structure | AudioLibraryViewModel | audio_router |
| 6 | **Video-Analyse** | scene_detect, raft, siglip, moondream | VideoLibraryViewModel | video_router |
| 7 | **Anchor/Beats** | anchor_manager | AnchorViewModel | audio_router |
| 8 | **Pacing/Director** | pacing_engine, clip_selector | DirectorViewModel | pacing_router |
| 9 | **Timeline** | timeline_models | TimelineViewModel | pacing_router |
| 10 | **Rendering** | render_engine, final_renderer | ProductionViewModel | render_router |
| 11 | **Einstellungen** | config_manager, system_monitor | SettingsViewModel | events_router |

Für jeden Bereich: Liste ALLE testbaren Funktionen auf. Format:

```markdown
### Bereich: Audio-Analyse
- [ ] F-3.1: Audio-Datei importieren und analysieren lassen
- [ ] F-3.2: BPM-Erkennung korrekt (Beat-Detection)
- [ ] F-3.3: Tonart-Erkennung (Key-Detection)
- [ ] F-3.4: Waveform-3-Band Generierung
- [ ] F-3.5: Spektral-Analyse
- [ ] F-3.6: Struktur-Erkennung (Intro, Verse, Chorus...)
- [ ] F-3.7: Progress-Updates via SSE während Analyse
```

Speichere die Funktionsliste als `test-report/function-catalog.md`.

---

## Phase 2: TESTEN (wie ein Mensch)

Arbeite Bereich für Bereich, Funktion für Funktion. Für JEDE Funktion:

### 2.1 Test vorbereiten

1. Identifiziere den **Einstiegspunkt** (welcher Button/Command in der UI)
2. Identifiziere die **erwartete Ausgabe** (was soll passieren?)
3. Wähle die passende **Testdatei** aus den echten Testdaten

### 2.2 Test ausführen

Es gibt zwei Test-Modi, die BEIDE genutzt werden müssen:

**Modus A: API-Test (Backend)**
Teste den FastAPI-Endpoint direkt:

```python
# Python Script
import httpx
import asyncio

async def test_audio_analyze():
    async with httpx.AsyncClient(base_url="http://localhost:8765") as client:
        # 1. Projekt laden/erstellen
        resp = await client.post("/api/project/load", json={"path": "..."})

        # 2. Audio importieren
        resp = await client.post("/api/audio/analyze", json={
            "file_path": r"C:\Users\david\Videos\test_data\audio\<datei>",
            "waveform_bands": 3
        })

        # 3. Ergebnis prüfen
        assert resp.status_code == 200
        data = resp.json()
        assert "bpm" in data
        assert data["bpm"] > 0
```

**Modus B: GUI-Test (Frontend)**
Teste über die WPF-Oberfläche. Nutze dafür den `gui-test-agent` Skill oder direkt UI-Automation:

```powershell
# PowerShell — App starten
$env:PBSTUDIO_PYTHON_EXE = "C:\Users\david\Dokumente\Pb_studio_AMD_version\.venv\Scripts\python.exe"
dotnet run --project "C:\Users\david\Dokumente\Pb_studio_AMD_version\PBStudio.UI\PBStudio.UI.csproj"
```

Wenn Sub-Agenten verfügbar sind, spawne einen GUI-Test-Agenten der die Buttons tatsächlich klickt. Wenn nicht, nutze API-Tests als Fallback, aber dokumentiere dass der GUI-Test noch aussteht.

### 2.3 Ergebnis dokumentieren

Für jede getestete Funktion:

```markdown
#### F-3.1: Audio-Datei importieren und analysieren

| Feld | Wert |
|------|------|
| **Status** | ❌ FAIL / ✅ PASS / ⚠️ TEILWEISE |
| **Testdatei** | test_data/audio/example.wav |
| **Test-Modus** | API / GUI / Beides |
| **Erwartung** | BPM, Key, Waveform, Spektral, Struktur |
| **Tatsächlich** | BPM korrekt, Key fehlt, Waveform OK |
| **Fehler** | KeyError: 'key' in audio_router.py Zeile 142 |
| **Schwere** | KRITISCH / MITTEL / NIEDRIG |
| **Betroffene Dateien** | audio_router.py, key_detector.py |
```

Speichere den Test-Report als `test-report/<bereich>-test-report.md`.

---

## Phase 3: FIX-LOOP

Für jeden Bug aus Phase 2, arbeite in dieser exakten Reihenfolge:

### 3.1 Bug analysieren

1. Lies den Fehler und die betroffenen Dateien
2. Verfolge die **Signalkette** (nutze den `pb-master` Skill für Deep Analysis)
3. Identifiziere die **Root Cause** — nicht das Symptom fixen!

### 3.2 Lösung erarbeiten

1. Schreibe die Lösung als vollständiges Code-Snippet
2. Prüfe:
   - [ ] Ist die Datei LOCKED? → Nur mit User-Erlaubnis!
   - [ ] Versions-Kompatibilität (requirements.txt, .csproj)?
   - [ ] Seiteneffekte auf andere Module?
   - [ ] Thread-Safety?
   - [ ] Werden bestehende Tests gebrochen?

### 3.3 Lösung prüfen (VOR Implementierung)

**KRITISCH**: Implementiere NICHT sofort! Prüfe die Lösung erst:

1. Wenn pytest-Tests vorhanden: Simuliere den Fix mental und prüfe ob bestehende Tests brechen würden
2. Prüfe die Lösung gegen die Architektur-Regeln (AMD DirectML, kein CPU-Fallback, MVVM, etc.)
3. Dokumentiere die Begründung

### 3.4 Implementieren

Erst nach Prüfung:

1. Erstelle den Fix
2. Markiere im Report:

```markdown
#### Fix F-3.1: KeyError in key_detector

| Feld | Wert |
|------|------|
| **Datei** | backend/routers/audio_router.py |
| **Zeile** | 142 |
| **Root Cause** | key_detector.detect() gibt None zurück wenn Audio < 10s |
| **Fix** | Fallback auf "N/A" wenn detect() None returned |
| **Geprüft** | ✅ Keine Seiteneffekte, Tests bestehen |
| **Implementiert** | ✅ |
```

### 3.5 Re-Test

Führe den Test aus Phase 2 ERNEUT aus. Nur für die gefixteten Funktionen.

- **PASS** → Nächste Funktion
- **FAIL** → Zurück zu 3.1 (max. 3 Versuche pro Bug, dann eskalieren an User)

---

## Phase 4: BEREICHS-ABSCHLUSS

Wenn alle Funktionen eines Bereichs getestet und (falls nötig) gefixt sind:

1. Erstelle einen **Bereichs-Report**:

```markdown
# Bereichs-Report: Audio-Analyse

## Zusammenfassung
| Metrik | Wert |
|--------|------|
| Funktionen getestet | 7 |
| Sofort bestanden | 5 |
| Nach Fix bestanden | 1 |
| Offen (eskaliert) | 1 |
| Fix-Versuche gesamt | 4 |

## Getestete Funktionen
[Liste aller Funktionen mit Status]

## Durchgeführte Fixes
[Liste aller Fixes mit Begründung]

## Offene Punkte
[Was muss der User manuell prüfen?]
```

2. Speichere als `test-report/<bereich>-final-report.md`
3. **STOPP** — Zeige dem User den Report und warte auf Anweisung für den nächsten Bereich

---

## Phase 5: BEREINIGUNG (nach JEDEM Test-Durchgang)

**ABSOLUT KRITISCH**: Nach jedem vollständigen Test-Durchgang eines Bereichs muss ALLES bereinigt werden. Keine Altlasten für den nächsten Test.

Nutze das Cleanup-Script unter `scripts/cleanup.py` oder führe manuell aus:

### 5.1 Datenbank bereinigen

```python
# Python Script
import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\data\pb_studio.db")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Alle Test-generierten Einträge löschen
# ACHTUNG: Nur Einträge die WÄHREND des Tests erstellt wurden!
# Nutze Zeitstempel oder IDs die du dir vor dem Test gemerkt hast
tables = cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

for (table,) in tables:
    # Zeige was gelöscht wird
    count = cursor.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    print(f"  {table}: {count} Einträge")

# WAL-Modus bereinigen
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.close()
```

### 5.2 Generierte Dateien löschen

```powershell
# PowerShell
$projectDir = "C:\Users\david\Dokumente\Pb_studio_AMD_version"

# Temp-Verzeichnis komplett leeren
Remove-Item "$projectDir\temp\*" -Force -Recurse -ErrorAction SilentlyContinue

# Generierte Waveforms, Thumbnails, Proxies
Remove-Item "$projectDir\data\temp\*" -Force -Recurse -ErrorAction SilentlyContinue

# FAISS-Indizes (wenn während Test neu erstellt)
# VORSICHT: Nur Test-generierte Indizes!
# Remove-Item "$projectDir\data\test_index.*" -Force -ErrorAction SilentlyContinue

# Stem-Separation Outputs
Remove-Item "$projectDir\temp\*_(Vocals)_*" -Force -ErrorAction SilentlyContinue
Remove-Item "$projectDir\temp\*_(Instrumental)_*" -Force -ErrorAction SilentlyContinue

# Log-Dateien
Remove-Item "$projectDir\logs\*" -Force -ErrorAction SilentlyContinue
```

### 5.3 Cache bereinigen

```python
# Python Script
import shutil
from pathlib import Path

cache_dirs = [
    Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\data\temp"),
    Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\temp"),
]

for d in cache_dirs:
    if d.exists():
        for item in d.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        print(f"  Bereinigt: {d}")
```

### 5.4 Verifikation der Bereinigung

Nach dem Cleanup: **Prüfe** ob wirklich alles weg ist:

```python
# Python Script
from pathlib import Path
import sqlite3

# Prüfe DB
db = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\data\pb_studio.db")
conn = sqlite3.connect(str(db))
for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    status = "✅ Leer" if count == 0 else f"⚠️ {count} Einträge"
    print(f"  {table}: {status}")
conn.close()

# Prüfe Temp-Verzeichnisse
for d in [r"temp", r"data\temp"]:
    p = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version") / d
    files = list(p.glob("*")) if p.exists() else []
    status = "✅ Leer" if not files else f"⚠️ {len(files)} Dateien"
    print(f"  {d}: {status}")
```

Speichere den Cleanup-Report als `test-report/<bereich>-cleanup-report.md`.

---

## Workflow für Sub-Agenten

Wenn Sub-Agenten (Claude Code Task-Tool) verfügbar sind, nutze diese Aufteilung:

```
ORCHESTRATOR (du)
├── TEST-AGENT    → Testet Funktionen, schreibt Reports
├── FIX-AGENT     → Analysiert Bugs, erarbeitet Fixes
├── VERIFY-AGENT  → Prüft Fixes VOR Implementierung
└── CLEANUP-AGENT → Bereinigt nach jedem Durchgang
```

Der Orchestrator steuert den Ablauf und entscheidet, ob ein Bug eskaliert wird (nach 3 fehlgeschlagenen Fix-Versuchen).

---

## State-Management

Während der Loop musst du den Zustand tracken. Speichere nach JEDEM Schritt:

```json
// test-report/state.json
{
  "current_area": "Audio-Analyse",
  "current_function": "F-3.4",
  "phase": "FIX-LOOP",
  "fix_attempt": 2,
  "functions_tested": 12,
  "functions_passed": 10,
  "functions_failed": 2,
  "fixes_applied": 1,
  "fixes_pending": 1,
  "db_entries_before_test": {"audio_clips": 0, "video_clips": 0},
  "files_created_during_test": []
}
```

Dieser State ermöglicht es, nach einem Abbruch oder Neustart genau dort weiterzumachen wo du aufgehört hast.

---

## Eskalation

Wenn ein Bug nach 3 Fix-Versuchen nicht gelöst ist:

1. Markiere als **ESKALIERT**
2. Dokumentiere alle 3 Versuche und warum sie gescheitert sind
3. Gehe zur nächsten Funktion weiter
4. Im Bereichs-Report: Liste eskalierte Bugs separat auf
5. Der User entscheidet, wie weiter verfahren wird

---

## Ausgabe-Struktur

```
test-report/
├── function-catalog.md           # Alle Funktionen der App
├── state.json                     # Aktueller Loop-Zustand
├── audio-analyse/
│   ├── test-report.md            # Test-Ergebnisse
│   ├── fixes.md                  # Durchgeführte Fixes
│   ├── final-report.md           # Bereichs-Abschluss
│   └── cleanup-report.md         # Bereinigung verifiziert
├── video-analyse/
│   ├── ...
└── gesamt-report.md              # Wenn ALLE Bereiche fertig
```
