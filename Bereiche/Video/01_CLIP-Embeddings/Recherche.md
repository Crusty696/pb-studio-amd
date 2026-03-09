# CLIP Embeddings - Recherche

**Stand:** 04.01.2026
**Bereich:** Video
**Risiko:** 🟢 Niedrig

---

## 1. Aktueller Stand (NVIDIA)

Die NVIDIA-Version verwendet:
- OpenAI CLIP (openai/clip-vit-base-patch32)
- PyTorch mit CUDA
- transformers Bibliothek

---

## 2. AMD Lösung: CLIP ONNX

### Verfügbare ONNX Modelle auf HuggingFace

| Repository | Größe | Beschreibung |
|------------|-------|--------------|
| **sayantan47/clip-vit-b32-onnx** | ~600 MB | ✅ EMPFOHLEN - hat Quantisierungen |
| openai/clip-vit-base-patch32 (onnx/) | 606 MB | Offizielles Modell |
| onnx-community/clip-vit-base-patch16-ONNX | ~580 MB | Community konvertiert |
| immich-app/ViT-B-32__laion2b-s34b-b79k | ~500 MB | OpenCLIP ONNX |

---

## 3. Download & Verwendung

```python
from huggingface_hub import hf_hub_download
import onnxruntime as ort

# Modell herunterladen
model_path = hf_hub_download(
    repo_id="sayantan47/clip-vit-b32-onnx",
    filename="onnx/model.onnx"
)

# ONNX Session mit DirectML
session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False

session = ort.InferenceSession(
    model_path,
    sess_options=session_options,
    providers=[
        ('DmlExecutionProvider', {'device_id': 0}),
        'CPUExecutionProvider'
    ]
)

# Inferenz
outputs = session.run(None, {'input': image_tensor})
```

---

## 4. Preprocessing

CLIP benötigt spezifisches Preprocessing:

```python
from transformers import CLIPProcessor
from PIL import Image

processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

image = Image.open("image.jpg")
inputs = processor(images=image, return_tensors="np")

# inputs['pixel_values'] für ONNX Session
```

---

## 5. VRAM-Verbrauch

| Variante | VRAM |
|----------|------|
| ViT-B-32 | ~500 MB |
| ViT-B-16 | ~600 MB |
| ViT-L-14 | ~1.5 GB |

✅ Sehr niedrig für 16 GB!

---

## 6. Output-Format

CLIP liefert:
- Image Embeddings: 512-dimensional (ViT-B-32)
- Text Embeddings: 512-dimensional

Identisch zu PyTorch-Version!

---

## 7. Quellen

1. HuggingFace: https://huggingface.co/sayantan47/clip-vit-b32-onnx
2. ONNX Runtime DirectML: https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html

---

## 8. Risiko-Bewertung

| Risiko | Einschätzung |
|--------|--------------|
| ONNX-Konvertierung | ✅ Bereits fertig |
| DirectML-Kompatibilität | ✅ Standard-Ops |
| Qualitäts-Verlust | ✅ Keiner (FP32) |

**Gesamt-Risiko: NIEDRIG**

---

*Recherche: 04.01.2026*
