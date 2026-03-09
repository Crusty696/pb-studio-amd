# PB Studio - AMD Premium Edition

Video- und Audio-Produktionsanwendung, optimiert fuer AMD-Grafikkarten mit DirectML-Beschleunigung.

## Features

- **Beat Detection**: Automatische Erkennung von Beats und Rhythmus mit BeatNet
- **Stem Separation**: Trennung von Vocals, Drums, Bass und anderen Instrumenten mit Demucs
- **Scene Detection**: Automatische Erkennung von Szenenwechseln
- **Vision Analysis**: Bildbeschreibung und -analyse mit Moondream (ONNX)
- **Optical Flow**: Motion-Analyse mit RAFT fuer Szenenuebergaenge
- **Hardware Monitoring**: Echtzeit-Ueberwachung von GPU, CPU und RAM
- **AMF Encoding**: Hardware-beschleunigtes Video-Encoding (H.264, HEVC, AV1)

## Hardware-Anforderungen

### Minimum
- AMD Radeon RX 5000 Serie oder neuer
- 8 GB VRAM (16 GB empfohlen)
- Windows 10 (Version 1903+) oder Windows 11
- 16 GB RAM

### Empfohlen
- AMD Radeon RX 7800 XT oder besser
- 16 GB VRAM
- Windows 11
- 32 GB RAM
- SSD fuer schnellen Dateizugriff

### Software
- Python 3.10 oder 3.11 (NICHT 3.12!)
- AMD Adrenalin Treiber 24.x oder neuer
- FFmpeg mit AMF Support (fuer Hardware-Encoding)

## Installation

### One-Click Installer (Empfohlen)

1. PowerShell als Administrator oeffnen
2. Zum Projektverzeichnis navigieren:
   ```powershell
   cd C:\CLAUDE_PROJEKTE\Pb_studio_AMD_version
   ```
3. Installer ausfuehren:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

### Manuelle Installation

1. Python 3.10 oder 3.11 installieren
2. Virtuelle Umgebung erstellen:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Dependencies installieren:
   ```bash
   pip install -r requirements.txt
   ```
4. Installation verifizieren:
   ```bash
   python verify_env_v2.py
   ```

## Schnellstart

1. Virtuelle Umgebung aktivieren:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Anwendung starten:
   ```powershell
   python run_ui.py
   ```

## Verzeichnisstruktur

```
Pb_studio_AMD_version/
    src/pb_studio/       # Hauptanwendung
        audio/           # Audio-Verarbeitung (BeatNet, Demucs)
        video/           # Video-Verarbeitung (Moondream, RAFT, AMF)
        ui/              # Benutzeroberflaeche (PyQt6)
        core/            # Kernsysteme (VRAM, Tasks, Monitoring)
        data/            # Datenpersistenz (SQLite, FAISS)
        services/        # Business Logic
    models/              # Heruntergeladene ML-Modelle
    data/                # Anwendungsdaten
    logs/                # Log-Dateien
    tests/               # Unit-Tests
    install.ps1          # One-Click-Installer
    run_ui.py            # Anwendungs-Einstiegspunkt
    requirements.txt     # Python-Abhaengigkeiten
    verify_env_v2.py     # Umgebungs-Validierung
    CLAUDE.md            # Claude Code Konfiguration
```

## Bekannte Einschraenkungen

### Python-Version
- **Python 3.12+ wird NICHT unterstuetzt** aufgrund von Inkompatibilitaeten mit BeatNet
- Nur Python 3.10 oder 3.11 verwenden

### DirectML vs CUDA
- Diese Version verwendet **DirectML** (Windows, AMD)
- CUDA/ROCm werden nicht unterstuetzt
- Keine Installation von `onnxruntime-gpu`!

### BFloat16
- DirectML unterstuetzt KEIN BFloat16
- Alle Modelle muessen FP16 oder FP32 sein

### Memory Pattern Bug
- `enable_mem_pattern = False` ist Pflicht bei DirectML
- Ohne diese Einstellung kommt es zu Abstuerzen

## Fehlerbehebung

### "DmlExecutionProvider not found"
```bash
pip uninstall onnxruntime onnxruntime-gpu -y
pip install onnxruntime-directml
```

### BeatNet Crash beim Import
```bash
pip install numpy==1.26.4 --force-reinstall
```

### FFmpeg AMF Encoder fehlt
FFmpeg mit AMF-Support herunterladen:
https://github.com/BtbN/FFmpeg-Builds/releases

### LibreHardwareMonitor Fehler
Die DLL muss im lib/ Verzeichnis vorhanden sein:
https://github.com/LibreHardwareMonitor/LibreHardwareMonitor

## Tests ausfuehren

```bash
# Alle Tests
pytest tests/ -v

# Nur schnelle Tests
pytest tests/ -v -m "not slow"

# Mit GPU-Tests
pytest tests/ -v -m gpu
```

## Lizenz

Internes Projekt - Nicht zur Veroeffentlichung bestimmt.

## Support

Bei Problemen die Log-Dateien unter `logs/` pruefen oder `verify_env_v2.py` ausfuehren.
