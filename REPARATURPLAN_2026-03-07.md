# PB Studio — Reparaturplan
**Datum:** 2026-03-07
**Grundlage:** Vollstaendiger Pruefbericht vom 2026-03-07
**Ziel:** Lokale Entwicklungsumgebung vollstaendig funktionsfaehig machen, alle Tests gruen

---

## Zusammenfassung der Probleme

| # | Problem | Schwere | Phase |
|---|---------|---------|-------|
| P-01 | Falsche Python-Version (3.12 statt 3.11) | KRITISCH | 1 |
| P-02 | NumPy 2.x statt 1.26.4 | KRITISCH | 2 |
| P-03 | onnxruntime-directml fehlt | KRITISCH | 2 |
| P-04 | BeatNet 1.1.1 fehlt | KRITISCH | 2 |
| P-05 | FAISS-CPU fehlt | HOCH | 2 |
| P-06 | colorlog fehlt | MITTEL | 2 |
| P-07 | pydub fehlt | MITTEL | 2 |
| P-08 | demucs fehlt | HOCH | 2 |
| P-09 | scenedetect fehlt | HOCH | 2 |
| P-10 | pythonnet fehlt | HOCH | 2 |
| P-11 | OpenCV falsche Version (4.13 statt 4.9) | NIEDRIG | 2 |
| P-12 | 10/12 Core-Module importieren nicht | KRITISCH | 3 |
| P-13 | 4/12 Tests crashen bei Collection | KRITISCH | 4 |
| P-14 | Restliche 8 Tests nicht verifiziert | HOCH | 4 |

**Hinweis:** P-12 bis P-14 sind Folgefehler von P-01 bis P-10.
Zwei im Pruefbericht gemeldete "FAIL"-Module waren Testfehler (falsche Modulpfade):
- `rendering.encoder_utils` → korrekt: `video.encoder_utils`
- `data.database` → korrekt: `data.database_core`
Diese sind KEINE echten Code-Fehler.

---

## Phase 1: Python 3.11 Virtual Environment erstellen

**Ziel:** Isolierte Python 3.11 Umgebung im Projektverzeichnis
**Loest:** P-01

### Schritte

```powershell
# 1.1 — Pruefen ob Python 3.11 verfuegbar ist
py -3.11 --version
# Erwartet: Python 3.11.9 (bereits bestaetigt)

# 1.2 — venv erstellen
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
py -3.11 -m venv .venv

# 1.3 — Aktivieren
.\.venv\Scripts\Activate.ps1

# 1.4 — pip aktualisieren
python -m pip install --upgrade pip setuptools wheel
```

### Verifizierung Phase 1

```powershell
python --version
# MUSS ausgeben: Python 3.11.9
pip --version
# MUSS enthalten: python 3.11
```

**Abbruchkriterium:** Wenn `py -3.11` nicht verfuegbar ist → Python 3.11 zuerst installieren.

---

## Phase 2: Alle Dependencies installieren

**Ziel:** Alle Packages aus requirements.txt + Spezial-Packages korrekt installiert
**Loest:** P-02 bis P-11

### Reihenfolge ist wichtig!

Einige Packages haben spezielle Installationsanforderungen.
Die Reihenfolge vermeidet Konflikte.

### Schritt 2.1 — NumPy pinnen (VOR allem anderen)

```powershell
pip install "numpy==1.26.4"
```

**Verifizierung:**
```powershell
python -c "import numpy; print(numpy.__version__)"
# MUSS ausgeben: 1.26.4
```

### Schritt 2.2 — PyTorch CPU installieren (eigener Index)

```powershell
pip install torch==2.4.1+cpu torchaudio==2.4.0+cpu --index-url https://download.pytorch.org/whl/cpu
```

**Verifizierung:**
```powershell
python -c "import torch; print(torch.__version__)"
# MUSS ausgeben: 2.4.1+cpu
```

### Schritt 2.3 — onnxruntime-directml installieren

```powershell
pip install "onnxruntime-directml>=1.16.0,<1.20.0"
```

**Verifizierung:**
```powershell
python -c "import onnxruntime; print(onnxruntime.__version__); print([p.get_available_providers() for p in [onnxruntime.InferenceSession.__init__]][:0] or onnxruntime.get_available_providers())"
# MUSS 'DmlExecutionProvider' enthalten
```

### Schritt 2.4 — Restliche requirements.txt installieren

```powershell
pip install -r requirements.txt
```

**Achtung:** Falls NumPy dabei auf 2.x hochgezogen wird:
```powershell
pip install "numpy==1.26.4" --force-reinstall
```

### Schritt 2.5 — Spezial-Packages pruefen

Diese Packages brauchen ggf. besondere Behandlung:

**FAISS-CPU (P-05):**
```powershell
pip install faiss-cpu==1.7.4
# Falls das fehlschlaegt (kein cp311-win_amd64 Wheel):
pip install faiss-cpu
```

**BeatNet (P-04):**
```powershell
pip install BeatNet==1.1.1
# BeatNet haengt von madmom ab, das Python 3.11 braucht (deshalb P-01 kritisch)
```

**pythonnet (P-10):**
```powershell
pip install "pythonnet>=3.0.0"
# Braucht .NET Runtime — sollte auf diesem System vorhanden sein (dotnet build geht)
```

**OpenCV (P-11):**
```powershell
pip install opencv-python==4.9.0.80
# Falls 4.9.0.80 nicht mehr verfuegbar:
pip install "opencv-python>=4.9.0,<4.10.0"
```

### Verifizierung Phase 2

```powershell
python -c "
import sys
print(f'Python: {sys.version}')

checks = {
    'numpy': '1.26.4',
    'onnxruntime': None,
    'torch': '2.4.1+cpu',
    'BeatNet': None,
    'faiss': None,
    'colorlog': None,
    'pydub': None,
    'demucs': None,
    'scenedetect': None,
    'clr': None,
    'cv2': None,
    'scipy': None,
    'librosa': None,
    'soundfile': None,
    'fastapi': None,
    'uvicorn': None,
    'pydantic': None,
    'httpx': None,
    'transformers': None,
    'PIL': None,
    'sklearn': None,
    'sentencepiece': None,
}

ok = fail = 0
for mod, expected_ver in checks.items():
    try:
        m = __import__(mod)
        ver = getattr(m, '__version__', 'OK')
        status = 'OK'
        if expected_ver and ver != expected_ver:
            status = f'WARNUNG: {ver} (erwartet {expected_ver})'
        print(f'  OK   {mod} == {ver} {\"\" if status == \"OK\" else status}')
        ok += 1
    except Exception as e:
        print(f'  FAIL {mod}: {e}')
        fail += 1
print(f'Ergebnis: {ok} OK, {fail} FAIL')
"
```

**Erwartung:** 0 FAIL, alle Module importierbar.

**Abbruchkriterium:** Wenn mehr als 2 Packages nicht installierbar sind → Ursache einzeln debuggen.

---

## Phase 3: Core-Module Import-Verifizierung

**Ziel:** Alle pb_studio Module importieren fehlerfrei
**Loest:** P-12

### Schritt 3.1 — Alle Core-Module testen

```powershell
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
$env:PYTHONPATH = "src;."

python -c "
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

modules = [
    # Core
    'pb_studio.core.vram_arbiter',
    'pb_studio.core.task_queue',
    'pb_studio.core.system_monitor',
    'pb_studio.core.crash_handler',
    'pb_studio.core.model_loader',
    'pb_studio.core.thread_pool',
    'pb_studio.core.vram_budget_manager',
    # Audio
    'pb_studio.audio.beat_detector',
    'pb_studio.audio.key_detector',
    'pb_studio.audio.spectral_analyzer',
    'pb_studio.audio.structure_analyzer',
    'pb_studio.audio.streaming_analyzer',
    'pb_studio.audio.separator',
    # Video
    'pb_studio.video.scene_detect',
    'pb_studio.video.encoder_utils',
    'pb_studio.video.engine',
    'pb_studio.video.raft',
    'pb_studio.video.moondream',
    # Data
    'pb_studio.data.database_core',
    'pb_studio.data.vector_store',
    # Rendering
    'pb_studio.rendering.render_service',
    'pb_studio.rendering.render_engine',
    # Services
    'pb_studio.services.analysis_service',
    'pb_studio.services.generation_service',
    'pb_studio.services.media_service',
    # Pacing
    'pb_studio.pacing.advanced_pacing_engine',
    'pb_studio.pacing.clip_selector',
]

ok = fail = 0
for m in modules:
    try:
        __import__(m)
        print(f'  OK   {m}')
        ok += 1
    except Exception as e:
        short = str(e).split(chr(10))[0][:100]
        print(f'  FAIL {m}: {short}')
        fail += 1
print(f'Core-Module: {ok} OK, {fail} FAIL')
"
```

**Erwartung:** 0 FAIL (alle Module importieren).

### Schritt 3.2 — Falls Fehler auftreten

Fuer jedes fehlgeschlagene Modul:
1. Fehlermeldung lesen
2. Fehlende Abhaengigkeit identifizieren
3. Installieren und erneut testen

Typische Ursachen:
- `ModuleNotFoundError` → Package nachinstallieren
- `ImportError: DLL load failed` → Inkompatible Binary-Version
- `AttributeError` → API-Aenderung zwischen Versionen

---

## Phase 4: Tests ausfuehren

**Ziel:** Alle pytest-Tests gruen
**Loest:** P-13, P-14

### Schritt 4.1 — pytest ausfuehren

```powershell
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
python -m pytest Tests/ -v --tb=short
```

**Erwartung (laut CLAUDE.md):** 36/36 PASSED

### Schritt 4.2 — Falls Tests fehlschlagen

Fuer jeden fehlgeschlagenen Test:
1. Fehlermeldung analysieren
2. Unterscheiden: Umgebungsproblem vs. Code-Bug
3. Umgebungsprobleme → zurueck zu Phase 2
4. Code-Bugs → dokumentieren und separat fixen

### Schritt 4.3 — Tests mit Markern ausfuehren

```powershell
# Ohne GPU-Tests (wie CI)
python -m pytest Tests/ -v --tb=short -m "not gpu and not integration"

# Nur GPU-Tests (falls GPU verfuegbar)
python -m pytest Tests/ -v --tb=short -m "gpu"
```

---

## Phase 5: Backend End-to-End Verifizierung

**Ziel:** FastAPI-Backend startet und antwortet korrekt

### Schritt 5.1 — Backend starten

```powershell
python -m uvicorn backend.main:app --port 8765
```

### Schritt 5.2 — Endpoints testen

In einem zweiten Terminal:
```powershell
# Health-Check
curl http://localhost:8765/docs

# Projekt erstellen
curl -X POST http://localhost:8765/project/create -H "Content-Type: application/json" -d "{\"name\": \"test\", \"path\": \"C:/temp/pb_test\"}"

# GPU-Status
curl http://localhost:8765/gpu/status

# Audio-Clips
curl http://localhost:8765/audio/clips
```

### Schritt 5.3 — Verifizierung

Alle Endpoints muessen HTTP 200 zurueckgeben (oder erwartete Fehler wie 404 bei leerem Projekt).

---

## Phase 6: WPF-Build bestaetigen

**Ziel:** C#-Build weiterhin fehlerfrei (Regression pruefen)

### Schritt 6.1 — dotnet build

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj
```

**Erwartung:** 0 Errors, 0 Warnings (bereits bestaetigt, Regressionscheck)

---

## Phase 7: Abschluss-Verifizierung

**Ziel:** Alles zusammen pruefen, Ergebnis dokumentieren

### Checkliste

| # | Pruefpunkt | Kommando | Erwartung |
|---|-----------|----------|-----------|
| V-01 | Python-Version | `python --version` | 3.11.9 |
| V-02 | NumPy-Version | `python -c "import numpy; print(numpy.__version__)"` | 1.26.4 |
| V-03 | onnxruntime DML | `python -c "import onnxruntime"` | Kein Fehler |
| V-04 | BeatNet | `python -c "import BeatNet"` | Kein Fehler |
| V-05 | FAISS | `python -c "import faiss"` | Kein Fehler |
| V-06 | pythonnet | `python -c "import clr"` | Kein Fehler |
| V-07 | scenedetect | `python -c "import scenedetect"` | Kein Fehler |
| V-08 | demucs | `python -c "import demucs"` | Kein Fehler |
| V-09 | Core-Module | Phase-3-Skript | 0 FAIL |
| V-10 | pytest | `pytest Tests/ -v` | Alle PASSED |
| V-11 | dotnet build | `dotnet build PBStudio.UI\...` | 0 Errors |
| V-12 | Backend-Start | `uvicorn backend.main:app` | Startet ohne Fehler |
| V-13 | FFmpeg AMF | `ffmpeg -encoders 2>&1 \| grep amf` | h264_amf, hevc_amf, av1_amf |

### Ergebnis-Dokumentation

Nach erfolgreichem Durchlauf aller 13 Pruefpunkte:
- CLAUDE.md aktualisieren (Current Task, Tests-Ergebnis)
- Diesen Plan als erledigt markieren

---

## Zeitschaetzung

| Phase | Geschaetzter Aufwand |
|-------|---------------------|
| Phase 1 | 2 Minuten |
| Phase 2 | 5-15 Minuten (abhaengig von Download-Geschwindigkeit) |
| Phase 3 | 2 Minuten |
| Phase 4 | 3 Minuten |
| Phase 5 | 5 Minuten |
| Phase 6 | 1 Minute |
| Phase 7 | 3 Minuten |
| **Gesamt** | **ca. 20-30 Minuten** |

---

## Risiken und Fallback-Strategien

| Risiko | Wahrscheinlichkeit | Fallback |
|--------|-------------------|----------|
| BeatNet laesst sich nicht installieren (madmom-Konflikt) | MITTEL | madmom manuell patchen, dann BeatNet |
| FAISS-CPU hat kein cp311-win_amd64 Wheel | NIEDRIG | `pip install faiss-cpu` (neuere Version) |
| NumPy wird durch anderes Package auf 2.x hochgezogen | MITTEL | Nach jedem `pip install` NumPy-Version pruefen |
| pythonnet braucht spezielle .NET-Runtime | NIEDRIG | .NET 9 SDK ist bereits installiert |
| onnxruntime-directml inkompatibel mit Python 3.11.9 | NIEDRIG | Version-Range testen: 1.16, 1.17, 1.18, 1.19 |
