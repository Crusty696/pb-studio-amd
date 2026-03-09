---
name: health-check
description: "PB Studio 13-Punkte System-Verifizierung — prueft Venv, Deps, DirectML, Tests, Build, Backend, FFmpeg"
disable-model-invocation: true
---

# PB Studio Health-Check (13-Punkte-Verifizierung)

Fuehre alle 13 Verifikationspunkte der PB Studio Umgebung aus.

## Vorbereitung
```bash
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
```

## Pruefpunkte

### V-01: Python-Version
```bash
.venv/Scripts/python.exe --version
```
**Erwartet:** Python 3.11.x

### V-02: NumPy-Version
```bash
.venv/Scripts/python.exe -c "import numpy; print(numpy.__version__)"
```
**Erwartet:** 1.26.4 (MUSS < 2.0 sein!)

### V-03: ONNX DirectML
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import onnxruntime as ort; print(ort.__version__); print(ort.get_available_providers())"
```
**Erwartet:** Version >= 1.16.0, `DmlExecutionProvider` in der Liste

### V-04: BeatNet
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import BeatNet; print('BeatNet OK')"
```
**Erwartet:** Kein ImportError (librosa-Fallback ist OK)

### V-05: FAISS
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import faiss; print(f'FAISS {faiss.__version__}')"
```
**Erwartet:** Version vorhanden

### V-06: pythonnet
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import clr; print('pythonnet OK')"
```
**Erwartet:** Kein ImportError

### V-07: scenedetect
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import scenedetect; print(f'scenedetect {scenedetect.__version__}')"
```
**Erwartet:** Version >= 0.6.3

### V-08: Demucs
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "import demucs; print('Demucs OK')"
```
**Erwartet:** Kein ImportError

### V-09: Core-Module (11 Stueck)
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "
modules = [
    'pb_studio.audio.beat_detector',
    'pb_studio.audio.spectral_analyzer',
    'pb_studio.audio.structure_analyzer',
    'pb_studio.audio.waveform_analyzer',
    'pb_studio.audio.key_detector',
    'pb_studio.video.scene_detect',
    'pb_studio.video.raft',
    'pb_studio.core.vram_arbiter',
    'pb_studio.data.database_core',
    'pb_studio.data.vector_store',
    'pb_studio.pacing.engine',
]
ok = 0
for m in modules:
    try:
        __import__(m)
        ok += 1
    except Exception as e:
        print(f'FAIL: {m} — {e}')
print(f'{ok}/{len(modules)} Module OK')
"
```
**Erwartet:** 11/11 Module OK

### V-10: pytest
```bash
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
set PYTHONPATH=src
.venv\Scripts\python.exe -m pytest Tests/ -v --tb=short
```
**Erwartet:** 163+ passed, 0 failed

### V-11: dotnet build
```bash
dotnet build PBStudio.UI\PBStudio.UI.csproj
```
**Erwartet:** 0 Errors, 0 Warnings

### V-12: Backend-Start
Starte den FastAPI-Server kurz und pruefe /health:
```bash
PYTHONPATH=src .venv/Scripts/python.exe -c "
import uvicorn, threading, time, urllib.request, json, os
def run(): uvicorn.run('backend.main:app', host='127.0.0.1', port=8769, log_level='error')
t = threading.Thread(target=run, daemon=True); t.start(); time.sleep(6)
try:
    r = urllib.request.urlopen('http://127.0.0.1:8769/health', timeout=5)
    d = json.loads(r.read())
    print(f'Backend OK: status={d[\"status\"]}')
except Exception as e: print(f'FAIL: {e}')
os._exit(0)
"
```
**Erwartet:** Backend OK, Audio+Video Clips geladen

### V-13: FFmpeg AMF-Encoder
```bash
ffmpeg -encoders 2>&1 | grep -i amf
```
**Erwartet:** `h264_amf`, `hevc_amf`, `av1_amf` alle vorhanden

## Ergebnis-Tabelle

```markdown
## Health-Check Ergebnis

| # | Pruefpunkt | Status | Details |
|---|-----------|--------|---------|
| V-01 | Python 3.11.x | ✅/❌ | ... |
| V-02 | NumPy 1.26.4 | ✅/❌ | ... |
| V-03 | ONNX DirectML | ✅/❌ | ... |
| V-04 | BeatNet | ✅/❌ | ... |
| V-05 | FAISS | ✅/❌ | ... |
| V-06 | pythonnet | ✅/❌ | ... |
| V-07 | scenedetect | ✅/❌ | ... |
| V-08 | Demucs | ✅/❌ | ... |
| V-09 | Core-Module | ✅/❌ | X/11 |
| V-10 | pytest | ✅/❌ | X passed, Y failed |
| V-11 | dotnet build | ✅/❌ | X errors, Y warnings |
| V-12 | Backend | ✅/❌ | ... |
| V-13 | FFmpeg AMF | ✅/❌ | ... |

**Gesamt: X/13 BESTANDEN**
```

Falls Failures: Fuer jeden fehlgeschlagenen Punkt den Fix-Vorschlag dokumentieren.
