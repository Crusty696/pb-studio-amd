# PB Studio — Manuelle Nutzung und Verifikation

## Start

Im Projektverzeichnis PowerShell öffnen:

```powershell
Set-Location 'C:\Users\david\Documents\Pb_studio_AMD_version'
.\launch.ps1
```

Der Launcher setzt `PYTHONPATH=src`, verwendet das projektlokale FFmpeg/AMF-Bundle und schreibt pro Lauf ein vollständiges Log nach `logs\e2e_YYYYMMDD_HHMMSS.log`.

## Einzelne Prüfungen

```powershell
.\.agents\skills\run-pb-studio\driver.ps1 -Command check
.\.agents\skills\run-pb-studio\driver.ps1 -Command full-smoke -OutFile logs\manual-smoke.png -WaitSec 45

$env:PYTHONPATH = 'src'
$env:PATH = (Resolve-Path 'tools\ffmpeg\bin').Path + ';' + $env:PATH
.venv\Scripts\python.exe -m pytest Tests/ -x -q --tb=short
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
```

## Optionale AMD-Hardwareprüfung

```powershell
$env:PYTHONPATH = 'src'
$env:PBSTUDIO_RUN_T357_HARDWARE = '1'
.venv\Scripts\python.exe -m pytest Tests\test_t357_gpu_wpf_nullability_contracts.py -q -rs
Remove-Item Env:PBSTUDIO_RUN_T357_HARDWARE
```

Erwartung: aktuelle RX 7800 XT-LUID `0x00000000_0x000119f1`; ein historisches LHM-Backup bleibt bewusst übersprungen.

## LM Studio / Vision

LM Studio muss auf `http://127.0.0.1:1234` laufen:

```powershell
lms ls
lms load qwen3-4b-computer-science --gpu max --context-length 8192 --yes
lms load qwen2.5-vl-7b-instruct --gpu max --context-length 8192 --yes
```

Die verifizierten REST-Antworten sind `PB_STUDIO_LM_OK` und `PB_STUDIO_VISION_OK`.

## Logs und Status

- Lauf-Logs: `logs\e2e_*.log`
- GUI-Screenshot: `logs\verification-final-20260925.png`
- Statusaufnahme: `docs\statusaufnahme-2026-09-23.md`
- QC-Reports: `specs\00024-*` bis `specs\00028-*`

Recovery-Tests sequenziell ausführen; der Recovery-Control-Root ist ein gemeinsamer Produktzustand.
