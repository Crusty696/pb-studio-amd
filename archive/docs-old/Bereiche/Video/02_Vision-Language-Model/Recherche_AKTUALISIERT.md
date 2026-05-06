# Vision Language Models für AMD RX 7800 XT auf Windows
## AKTUALISIERTE RECHERCHE - 04.01.2026

---

## ⚠️ KRITISCHE ERKENNTNIS

**ROCm ist NICHT verfügbar für RX 7800 XT auf Windows!**
- Nur RX 7900 Serie (XT/XTX/GRE) hat offiziellen Support
- DirectML über ONNX Runtime ist der EINZIGE stabile Weg
- Microsoft hat DirectML in "Maintenance Mode" versetzt

---

## 🏆 EMPFOHLENE LÖSUNG: Phi-3.5-Vision ONNX

### Warum Phi-3.5-Vision?
- **Einziges VLM mit offizieller DirectML ONNX-Unterstützung**
- Von Microsoft explizit für AMD/Intel/NVIDIA via DirectML getestet
- MIT Lizenz

### Spezifikationen

| Eigenschaft | Wert |
|-------------|------|
| HuggingFace Repo | `microsoft/Phi-3.5-vision-instruct-onnx` |
| Quantisierung | INT4 (RTN), FP16 verfügbar |
| VRAM-Bedarf | ~10 GB kombiniert |
| Kontextlänge | 128K Tokens |
| Lizenz | MIT |

### Installation

```bash
pip install onnxruntime-directml==1.23.0
pip install huggingface-hub[cli] transformers pillow

huggingface-cli download microsoft/Phi-3.5-vision-instruct-onnx --local-dir ./phi35-vision
```

### Ausführung

```bash
python model-vision.py -m gpu/gpu-int4-rtn-block-32 -e dml
```

---

## 🥈 ALTERNATIVE 1: Florence-2 ONNX

### Warum Florence-2?
- Sehr niedriger VRAM-Bedarf
- Multi-Task fähig (Captioning, OCR, Object Detection)
- Schnellere Inferenz als große VLMs

### Verfügbare Modelle

| Modell | Parameter | VRAM | HuggingFace |
|--------|-----------|------|-------------|
| Florence-2-base | ~230M | ~1-2 GB | `onnx-community/Florence-2-base` |
| Florence-2-large | ~770M | ~3-4 GB | `onnx-community/Florence-2-large` |

---

## 🥉 ALTERNATIVE 2: SmolVLM

### Warum SmolVLM?
- Kleinste VLM-Option
- Offizielle ONNX-Checkpoints verfügbar

### Modelle

| Modell | VRAM |
|--------|------|
| SmolVLM-256M-Instruct | < 1 GB |
| SmolVLM-500M-Instruct | ~1.23 GB |
| SmolVLM-Instruct (2.2B) | ~4-6 GB |

---

## ❌ MOONDREAM - NICHT EMPFOHLEN

### Problem
- Kein funktionierender ONNX-Export
- GitHub Issues #88, #244, #215, #296 dokumentieren Shape-Mismatch-Fehler
- Nur Teil-Konvertierungen existieren (Text-Modell)

**Fazit: Moondream auf AMD Windows = NICHT MÖGLICH**

---

## 🔧 TECHNISCHE ANFORDERUNGEN

### Exakte Versionen (validiert)

| Komponente | Version |
|------------|---------|
| onnxruntime-directml | **1.23.0** |
| DirectML | 1.15.2 (gebündelt) |
| ONNX Opset | Bis Opset 20 |
| Python | 3.10-3.13 |
| Windows | 10 (1903+) oder 11 |

### Kritische Session-Konfiguration

```python
import onnxruntime as ort

session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False  # PFLICHT!
session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # PFLICHT!

session = ort.InferenceSession(
    "model.onnx",
    sess_options=session_options,
    providers=[
        ('DmlExecutionProvider', {'device_id': 0}),
        'CPUExecutionProvider'
    ]
)
```

### Nicht unterstützte Operatoren (vermeiden!)

- GridSample 20:5d
- DeformConv
- BFloat16 (FP16 oder FP32 verwenden!)
- aten::scaled_dot_product_attention

---

## 📊 PERFORMANCE-ERWARTUNGEN

| Metrik | Wert |
|--------|------|
| Nutzbares VRAM | ~12-13 GB |
| DirectML vs ROCm | ~2-4x langsamer |
| DirectML vs CUDA | ~2-4x langsamer |

---

## 📋 FAZIT

### Primäre Empfehlung
**Phi-3.5-Vision ONNX DirectML** - Einzige offiziell unterstützte Lösung

### Fallback-Optionen
1. Florence-2 ONNX (leichtgewichtig, Multi-Task)
2. SmolVLM ONNX (minimal VRAM)
3. ViT-GPT2 (einfaches Captioning)

### VRAM-Budget für RX 7800 XT (16 GB)

| Komponente | VRAM |
|------------|------|
| Phi-3.5-Vision INT4 | ~10 GB |
| System-Reserve | ~3-4 GB |
| **Verfügbar** | ✅ Ausreichend |

---

## 🔗 QUELLEN

1. https://huggingface.co/microsoft/Phi-3.5-vision-instruct-onnx
2. https://huggingface.co/onnx-community/Florence-2-large
3. https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct
4. https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html
5. https://github.com/microsoft/DirectML

---

*Recherche: 04.01.2026*
*Status: VALIDIERT*
