# Validierungstest - Anleitung

## Voraussetzungen

- Windows 10 (Build 19041+) oder Windows 11
- AMD RX 7800 XT mit aktuellem Treiber
- Python 3.11.x installiert (`python --version` prüfen!)

---

## Ausführungsreihenfolge

### Schritt 1: Installationstest

```powershell
# PowerShell als Admin öffnen
cd C:\Users\david\Documents\App_Projekte\PB_Studio_Projekt_Alle__Versionen\Pb_studio_AMD_version\05_VALIDIERUNGSTEST

# Ausführen
.\01_install_test.ps1
```

**Dauer:** 5-10 Minuten
**Ergebnis:** `C:\Temp\pb_studio_amd_test\INSTALL_REPORT.txt`

---

### Schritt 2: Import-Test

```powershell
# Im selben Verzeichnis, venv muss aktiv sein!
C:\Temp\pb_studio_amd_test\.venv\Scripts\Activate.ps1

# Test ausführen
python 02_import_test.py
```

**Ergebnis:** `C:\Temp\pb_studio_amd_test\IMPORT_REPORT.txt`

---

### Schritt 3: GPU-Test

```powershell
# venv muss aktiv sein
python 03_gpu_test.py
```

**Ergebnis:** `C:\Temp\pb_studio_amd_test\GPU_REPORT.txt`

---

### Schritt 4: Aufräumen (optional)

```powershell
.\04_cleanup.ps1
```

Löscht das Test-Verzeichnis `C:\Temp\pb_studio_amd_test`

---

## Erwartete Ergebnisse

### ✅ ERFOLG

- Alle Pakete installiert ohne Fehler
- `pip check` zeigt keine Konflikte
- Alle Imports funktionieren
- DirectML Provider verfügbar
- AMD GPU erkannt

### ❌ FEHLSCHLAG

Falls Fehler auftreten, Reports an mich senden:
- INSTALL_REPORT.txt
- IMPORT_REPORT.txt  
- GPU_REPORT.txt
- pip_freeze.txt

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Python nicht 3.11 | Python 3.11.x installieren |
| pip install Fehler | Einzelne Pakete manuell testen |
| DirectML nicht verfügbar | AMD Treiber aktualisieren |
| FFmpeg AMF fehlt | BtbN Build herunterladen |

---

## Nach erfolgreichem Test

Die Datei `pip_freeze.txt` enthält alle exakten Versionen.
Diese kann als Basis für die finale `requirements.txt` dienen.
