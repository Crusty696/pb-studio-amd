# Vision-Language Model - Recherche

**Stand:** 04.01.2026
**Bereich:** Video
**Risiko:** 🟡 Mittel
**KRITISCHE KOMPONENTE**

---

## 1. Aktueller Stand (NVIDIA)

Die NVIDIA-Version verwendet:
- Moondream2 (vikhyatk/moondream2)
- PyTorch mit CUDA
- Generative Inferenz für Bild-Beschreibungen

---

## 2. Problem mit Moondream auf AMD

**Moondream hat KEINE funktionierende ONNX-Lösung!**

Bekannte Issues:
- GitHub #88, #244, #215, #296: Shape-Mismatch bei Vision-Encoder Export
- Nur Teil-Konvertierungen existieren

---

## 3. AMD Lösung: Phi-3.5-Vision ONNX ✅

### Der EINZIGE VLM mit offiziellem DirectML Support!

**Repository:** `microsoft/Phi-3.5-vision-instruct-onnx`

| Eigenschaft | Wert |
|-------------|------|
| Entwickler | Microsoft |
| Quantisierung | INT4, FP16 |
| VRAM | ~10 GB (INT4) |
| Kontext | 128K Tokens |
| Lizenz | MIT |

### Fähigkeiten:
- Image Understanding
- OCR
- Chart/Tabellen-Analyse
- Bild-Beschreibungen

---

## 4. Download & Installation

```bash
# Modell herunterladen
huggingface-cli download microsoft/Phi-3.5-vision-instruct-onnx --local-dir ./phi35-vision

# Oder spezifische Variante
huggingface-cli download microsoft/Phi-3.5-vision-instruct-onnx \
    --include "gpu/gpu-int4-rtn-block-32/*" \
    --local-dir ./phi35-vision
```

### Varianten:
- `gpu/gpu-int4-rtn-block-32` - INT4 quantisiert (~10GB VRAM)
- `gpu/gpu-fp16` - Full precision (~20GB+ VRAM) - ZU GROSS!

**EMPFOHLEN:** INT4 Variante

---

## 5. Verwendung

```python
# Ausführung mit DirectML
python model-vision.py -m gpu/gpu-int4-rtn-block-32 -e dml
```

Oder programmatisch:
```python
import onnxruntime as ort

session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False

session = ort.InferenceSession(
    "phi35-vision/gpu/gpu-int4-rtn-block-32/model.onnx",
    sess_options=session_options,
    providers=[('DmlExecutionProvider', {'device_id': 0})]
)
```

---

## 6. Alternative Fallbacks

Falls Phi-3.5 Probleme macht:

### Option A: Florence-2 (ONNX)
- Repository: `onnx-community/Florence-2-large`
- VRAM: ~3-4 GB
- Multi-Task (Captioning, OCR, Detection)
- Einfachere Architektur

### Option B: SmolVLM
- Repository: `HuggingFaceTB/SmolVLM-500M-Instruct`
- VRAM: ~1.2 GB
- Sehr leichtgewichtig
- Für schnelle Prototypen

### Option C: ViT-GPT2 (Nur Captioning)
- Repository: `Xenova/vit-gpt2-image-captioning`
- VRAM: ~500 MB - 1 GB
- Nur einfache Beschreibungen
- Letzter Fallback

---

## 7. VRAM-Vergleich

| Modell | VRAM | Qualität |
|--------|------|----------|
| Phi-3.5 INT4 | ~10 GB | Beste |
| Florence-2-large | ~3-4 GB | Gut |
| SmolVLM-500M | ~1.2 GB | Akzeptabel |
| ViT-GPT2 | ~500 MB | Basic |

---

## 8. Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| VRAM-Overflow | Niedrig | Florence-2 als Fallback |
| Langsame Inferenz | Mittel | Erwartbar bei DirectML |
| Qualitäts-Unterschied | Mittel | Phi-3.5 ist gut |

---

## 9. Quellen

1. Phi-3.5 ONNX: https://huggingface.co/microsoft/Phi-3.5-vision-instruct-onnx
2. Florence-2: https://huggingface.co/onnx-community/Florence-2-large
3. SmolVLM: https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct

---

*Recherche: 04.01.2026*
