# AMD Umgebung - Setup-Anleitung

**Stand:** 04.01.2026
**Ziel:** DirectML-Umgebung für RX 7800 XT auf Windows

---

## 1. Voraussetzungen

### Hardware
- AMD Radeon RX 7800 XT (16 GB VRAM)
- Windows 10 (1903+) oder Windows 11
- DirectX 12 fähig

### Software
- Python 3.10 oder 3.11 (NICHT 3.12!)
- Aktueller AMD Adrenalin Treiber (24.x+)
- FFmpeg mit AMF Support

---

## 2. Python Umgebung erstellen

```bash
# Conda empfohlen
conda create -n pb_studio_amd python=3.10
conda activate pb_studio_amd

# Oder venv
python -m venv .venv
.venv\Scripts\activate
```

---

## 3. ONNX Runtime DirectML installieren

```bash
# WICHTIG: Nicht onnxruntime UND onnxruntime-directml gleichzeitig!
pip uninstall onnxruntime onnxruntime-gpu -y
pip install onnxruntime-directml==1.23.0
```

**Test:**
```python
import onnxruntime as ort
print(ort.get_available_providers())
# Sollte enthalten: 'DmlExecutionProvider'
```

---

## 4. Audio-Separator installieren (DirectML)

```bash
pip install audio-separator[dml]
```

**Test:**
```python
from audio_separator.separator import Separator
sep = Separator()
print("audio-separator ready")
```

---

## 5. Weitere Pakete

```bash
pip install transformers>=4.36.0
pip install huggingface-hub[cli]
pip install chromadb>=0.4.0
pip install opencv-python>=4.8.0
pip install Pillow>=10.0.0
pip install librosa>=0.10.0
pip install soundfile>=0.12.0
pip install numpy scipy
```

---

## 6. FFmpeg mit AMF prüfen

```bash
ffmpeg -encoders | findstr amf
```

**Erwartete Ausgabe:**
```
V..... h264_amf             AMD AMF H.264 Encoder
V..... hevc_amf             AMD AMF HEVC Encoder
V..... av1_amf              AMD AMF AV1 Encoder
```

Falls nicht vorhanden: FFmpeg neu kompilieren oder Builds mit AMF verwenden.

---

## 7. GPU-Erkennung testen

```python
import onnxruntime as ort

# DirectML Session erstellen
session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False  # WICHTIG für DirectML!
session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

providers = [
    ('DmlExecutionProvider', {'device_id': 0}),
    'CPUExecutionProvider'
]

print(f"Verfügbare Provider: {ort.get_available_providers()}")
print(f"Gewählte Provider: {providers}")
```

---

## 8. Environment Variablen (Optional)

```bash
# In Windows Umgebungsvariablen oder vor Start:
set DISABLE_ADDMM_CUDA_LT=1
set PYTORCH_TUNABLEOP_ENABLED=1
```

---

## Bekannte Probleme

### BFloat16 nicht unterstützt
DirectML unterstützt KEIN BFloat16. Modelle müssen FP16 oder FP32 sein.

### Memory Pattern Bug
`enable_mem_pattern = False` ist PFLICHT bei DirectML!

### Dynamische Input-Größen
Können Performance um 50% reduzieren (GitHub Issue #15394).

---

## Validierung der Installation

```python
# Speichern als test_amd_setup.py
import sys
print(f"Python: {sys.version}")

import onnxruntime as ort
print(f"ONNX Runtime: {ort.__version__}")
print(f"Provider: {ort.get_available_providers()}")

try:
    from audio_separator.separator import Separator
    print("audio-separator: OK")
except:
    print("audio-separator: FEHLT")

import subprocess
result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
if 'h264_amf' in result.stdout:
    print("FFmpeg AMF: OK")
else:
    print("FFmpeg AMF: FEHLT")

print("\n✅ Setup-Test abgeschlossen")
```

---

*Anleitung erstellt: 04.01.2026*
