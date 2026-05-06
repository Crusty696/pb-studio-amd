# PB Studio AMD

PB Studio AMD ist die Windows-/AMD-orientierte Hybrid-Version von PB Studio mit:
- **WPF-Frontend** (`PBStudio.UI`)
- **FastAPI-Backend** (`backend/`)
- **Python-Core** für Audio-, Video- und Render-Pipelines (`src/pb_studio/`)
- **Brain-Modul** lernfähiger Audio-zu-Video-Reranker (`src/pb_studio/brain/`)

Der aktuelle Produktpfad ist **nicht mehr die alte PyQt-UI**. Die aktive Desktop-Oberfläche ist die WPF-Anwendung.

---

## Aktueller Stand

Die App deckt heute bereits zentrale Kernpfade ab:
- Audio import / list / analyze / waveform / beats
- Video import / list / thumbnails / analyze
- Pacing / Timeline-Erzeugung
- Render start / status / cancel
- Projekt save / open / close / reopen
- **Brain-Modul** (online-Lernen via Beta-Bernoulli, 17 Bridge-Achsen,
  CLAP+SigLIP-2 via torch-directml, sqlite-vec KNN, 5 REST-Endpoints,
  WPF HIRN-Tab + Lern-Session-Walkthrough + Confidence-Balken)

Wichtiger Hinweis:
- Die Architektur befindet sich in einer laufenden Hybrid-Migration.
- WPF ist die aktive UI.
- Einige reichere Interaktionsflächen (z. B. echter Timeline-/Player-Editor) sind noch im Ausbau.

---

## Voraussetzungen

### Betriebssystem
- Windows 10/11

### Hardware
- AMD-GPU mit aktuellem Treiber empfohlen
- ausreichend VRAM für Analyse-/ML-Pfade

### Software
- Python **3.10 oder 3.11**
- FFmpeg mit AMF-Support bzw. das projektinterne FFmpeg-Setup
- funktionierende `.venv`

---

## Projektstruktur

```text
PBStudio.UI/          WPF-Desktop-App
backend/              FastAPI-Router, App-State, Schemas
src/pb_studio/        Python-Domainlogik für Audio/Video/Render
models/               ML-Modelle
data/                 Laufzeitdaten / Outputs
logs/                 Log-Dateien
Tests/                Python-Tests
archive/              Historische Pläne / Audits / Reports / Setup-Skripte (read-only)
STATUS_MATRIX.md      verifizierter Status je Bereich
WORKLOG.md            laufender Projektbericht
```

---

## Starten

### Empfohlener Produktstart

```powershell
dotnet run --project .\PBStudio.UI\PBStudio.UI.csproj -c Debug
```

Die WPF-App startet das Python-Backend beim Start automatisch über die Bridge.

### Alternativ: Backend separat starten

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

---

## Entwickler-Setup

### One-Shot Setup für Endanwender (Doppelklick)

`setup.bat` doppelklicken — fragt automatisch nach Admin-Rechten und installiert alles.

| Datei      | Zweck                                                  |
|------------|--------------------------------------------------------|
| `setup.bat`| Komplette Installation (Python venv, Brain-Stack, FFmpeg, .NET, Pre-commit-Hook) |
| `start.bat`| App starten (Backend + WPF)                            |
| `test.bat` | Pytest-Suite + UI-Test                                 |

**Logs:** Alle drei `.bat`-Wrapper schreiben Konsolen-Output zusätzlich nach
`logs\<name>_<ts>.log`, damit du nach einem Crash auch ohne offenes Fenster die
ganze Ausgabe rekonstruieren kannst. Plus `logs\setup_log_<ts>.txt` und
`logs\setup_transcript_<ts>.txt` aus dem PS1-Skript selbst (Stack-Traces, Native
exe stderr, alles erfasst).

### Test in Windows Sandbox (sauberer Frischer-PC-Test)

1. **Windows Sandbox aktivieren** (einmalig, mit Admin):
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM
   ```
   Dann Reboot.

2. **`pb_studio_sandbox.wsb` doppelklicken.** Sandbox startet, mountet das
   Repo read-only nach `C:\PB_studio_host` und kopiert es beim Login nach
   `C:\PB_studio` (writable). Internet + GPU-Sharing sind aktiv.

3. **In der Sandbox:** Im geöffneten Explorer-Fenster `setup.bat`
   doppelklicken. Setup loggt alles in `C:\PB_studio\logs\` (innerhalb Sandbox).
   Wenn Sandbox crasht: vorher `logs\` per Drag-and-Drop ins Host-Clipboard
   kopieren, oder Setup-Logs manuell rauskopieren.

4. **Nach Setup-Lauf:** `start.bat` → App-Test. `test.bat` → pytest-Suite.

### One-Shot Setup (PowerShell-direkt)

```powershell
.\setup_pb_studio.ps1
```

Optionen:
- `-SkipBuildTools`     VS Build Tools install ueberspringen
- `-SkipBackupPrompt`   keine Frage fuer Auto-Backup-Task
- `-SkipModelPrecache`  CLAP+SigLIP Download (~1.8 GB) skippen
- `-SkipGpuVerify`      DirectML-Verify-Run skippen
- `-SkipPytest`         pytest am Ende skippen
- `-NoPause`            Kein "Press Enter" am Ende
- `-Force`              venv neu anlegen (statt re-use)

Installiert Python-Venv, FFmpeg, LibreHardwareMonitor, AMD-DirectML-Stack inkl. Brain-Modul (torch-directml + transformers 4.49 + sqlite-vec + librosa) und richtet Pre-commit-Hook ein.

### Manuell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### .NET / WPF
- .NET SDK installieren
- danach:

```powershell
dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug
```

---

## Smoke-Checklist

### Backend / Core
- [ ] `/health` antwortet
- [ ] Audio-Clips abrufbar
- [ ] Video-Clips abrufbar
- [ ] Waveform-/Beat-Endpunkte funktionieren
- [ ] Timeline abrufbar
- [ ] Render start/status/cancel funktionieren

### WPF / Produktpfad
- [ ] App startet ohne Crash
- [ ] Backend wird als online angezeigt
- [ ] Projekt kann erstellt oder geöffnet werden
- [ ] Audio/Video-Listen laden sichtbar
- [ ] Timeline-Ansicht lädt ohne Binding-/UI-Fehler
- [ ] Production-View zeigt Renderstatus / Log sauber
- [ ] Save / Close / Reopen funktionieren ohne Zustandsverlust

---

## Tests

### Python-Tests

```powershell
pytest Tests -q -rs
```

### WPF Build-Smoke

```powershell
dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug
```

### WPF Lauf-Smoke

```powershell
dotnet run --project .\PBStudio.UI\PBStudio.UI.csproj -c Debug
```

### Publish

```powershell
powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Mode framework -Configuration Release
```

Weitere Modi:
- `-Mode selfcontained`
- `-Mode singlefile`

### Release Smoke

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_release_smoke.ps1
```

Der Release-Smoke startet bei Bedarf das Backend selbst, öffnet das aktive Projekt, prüft Audio/Video/Waveform/Beats, generiert eine Timeline, speichert das Projekt und verifiziert einen sicheren Render-Start+Cancel-Pfad.

---

## Bekannte Grenzen

- Die alte PyQt-Oberfläche ist nicht mehr der führende Produktpfad.
- Ein echter interaktiver Timeline-/Player-Editor ist noch nicht vollständig ausgebaut.
- Einige UI-Pfade sind funktional vorhanden, aber noch nicht vollständig end-to-end durchgeklickt.
- Bestimmte modell-/asset-abhängige Tests benötigen lokale Modelle oder Testmedien.

---

## Wichtige Dateien für den Projektstatus

- `STATUS_MATRIX.md` — Ampel-/Verifikationsstand
- `WORKLOG.md` — zuletzt erledigte Blöcke
- `PYQT_MIGRATION_CLASSIFICATION.md` — Alt-UI-zu-WPF-Klassifikation
- `docs/BRAIN_USER_GUIDE.md` — Brain-Modul für End-User
- `docs/HARDWARE_VERIFY_GUIDE.md` — DirectML-Hardware-Verifikation
- `LICENSES.md` — Lizenz-Attribution (CC-BY-4.0 für CLAP-Modell)

---

## Logs / Diagnose

- WPF-Log: `logs/wpf_app.log`
- zusätzliche Backend-/Bridge-Ausgaben erscheinen beim lokalen Start im Konsolen-/Run-Kontext

Bei Problemen zuerst prüfen:
1. startet das Backend?
2. ist `.venv` vollständig?
3. ist FFmpeg erreichbar?
4. zeigt `STATUS_MATRIX.md` den Bereich als live-getestet oder nur code-inspected?
