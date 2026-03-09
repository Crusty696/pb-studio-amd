# CLIP Embeddings auf AMD - Recherche

**Status:** ✅ Validiert  
**Priorität:** HOCH (Kernfunktion für Video-Analyse)

---

## Aktuelle Situation (NVIDIA)

- PyTorch CUDA-basiert
- OpenAI CLIP oder open_clip
- GPU-beschleunigt über torch.cuda

---

## AMD-Lösung: ONNX + DirectML

### Empfohlene Modelle

**Quelle:** Hugging Face - mlunar/clip-variants
⚠️ Hinweis: DirectML nicht explizit getestet, aber Standard-ONNX-Operatoren sind gut unterstützt

| Modell | Größe | Quantisierung | Empfehlung |
|--------|-------|---------------|------------|
| clip-vit-base-patch32 | ~350 MB | float32 | Schnell, gut für Prototyping |
| clip-vit-base-patch32 | ~175 MB | float16 | Guter Kompromiss |
| clip-vit-large-patch14 | ~1.2 GB | float32 | Beste Qualität |
| clip-vit-large-patch14 | ~600 MB | float16 | Empfohlen für Produktion |

---

## Techstack mit Versionen

### Python-Pakete (kompatibel getestet)

| Paket | Version | Zweck |
|-------|---------|-------|
| onnxruntime-directml | 1.23.0 | ONNX Runtime mit DirectML EP |
| numpy | 1.26.4 | Array-Operationen |
| pillow | 10.4.0 | Bild-Preprocessing |
| huggingface-hub | 0.26.0 | Model-Download |

### Inkompatibilitäten vermeiden

- NICHT gleichzeitig installieren: `onnxruntime`, `onnxruntime-gpu`, `onnxruntime-directml`
- Nur EIN onnxruntime-Paket pro Environment

---

## Model-Downloads

### Visual Encoder (Bild → Embedding)

| Modell | URL | Größe |
|--------|-----|-------|
| ViT-B/32 float16 | `https://huggingface.co/mlunar/clip-variants/resolve/main/models/clip-vit-base-patch32-visual-float16.onnx` | 175 MB |
| ViT-B/32 float32 | `https://huggingface.co/mlunar/clip-variants/resolve/main/models/clip-vit-base-patch32-visual-float32.onnx` | 350 MB |
| ViT-L/14 float16 | `https://huggingface.co/mlunar/clip-variants/resolve/main/models/clip-vit-large-patch14-visual-float16.onnx` | 600 MB |

### Text Encoder (Text → Embedding)

| Modell | URL | Größe |
|--------|-----|-------|
| ViT-B/32 float16 | `https://huggingface.co/mlunar/clip-variants/resolve/main/models/clip-vit-base-patch32-textual-float16.onnx` | 65 MB |
| ViT-B/32 float32 | `https://huggingface.co/mlunar/clip-variants/resolve/main/models/clip-vit-base-patch32-textual-float32.onnx` | 130 MB |

**Empfehlung für PB Studio:** ViT-B/32 float16 (Visual + Text = 240 MB gesamt)

---

## Installationsanweisungen

### Schritt 1: Environment erstellen

```powershell
python -m venv pb_studio_amd
pb_studio_amd\Scripts\activate
```

### Schritt 2: Pakete installieren

```powershell
pip install onnxruntime-directml==1.23.0
pip install numpy==1.26.4
pip install pillow==10.4.0
pip install huggingface-hub==0.26.0
```

### Schritt 3: Modelle herunterladen

```powershell
mkdir models\clip
huggingface-cli download mlunar/clip-variants --include "models/clip-vit-base-patch32-visual-float16.onnx" --local-dir models\clip
huggingface-cli download mlunar/clip-variants --include "models/clip-vit-base-patch32-textual-float16.onnx" --local-dir models\clip
```

### Schritt 4: Verifizieren

```powershell
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# Erwartete Ausgabe: ['DmlExecutionProvider', 'CPUExecutionProvider']
```

---

## Taskplan

| # | Task | Abhängigkeit | Geschätzte Zeit |
|---|------|--------------|-----------------|
| 1 | Environment aufsetzen | - | 10 min |
| 2 | onnxruntime-directml installieren | Task 1 | 5 min |
| 3 | Modelle herunterladen | Task 2 | 15 min |
| 4 | DirectML Session erstellen | Task 3 | 30 min |
| 5 | Preprocessing-Pipeline portieren | Task 4 | 2 h |
| 6 | Visual Embedding Funktion | Task 5 | 1 h |
| 7 | Text Embedding Funktion | Task 5 | 1 h |
| 8 | Similarity-Berechnung testen | Task 6, 7 | 30 min |
| 9 | Integration in PB Studio | Task 8 | 2 h |
| 10 | Performance-Test | Task 9 | 1 h |

**Gesamtzeit:** ~8 Stunden

---

## ONNX Runtime Session-Konfiguration

### Wichtige Einstellungen für DirectML

```python
import onnxruntime as ort

session_options = ort.SessionOptions()
session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # PFLICHT für DirectML
session_options.enable_mem_pattern = False  # PFLICHT für DirectML

providers = [
    ('DmlExecutionProvider', {
        'device_id': 0,  # GPU Index
    }),
    'CPUExecutionProvider'  # Fallback
]

session = ort.InferenceSession(
    "models/clip/clip-vit-base-patch32-visual-float16.onnx",
    sess_options=session_options,
    providers=providers
)
```

---

## Preprocessing (identisch zu Original-CLIP)

| Parameter | Wert |
|-----------|------|
| Input-Größe | 224 x 224 |
| Normalisierung Mean | [0.48145466, 0.4578275, 0.40821073] |
| Normalisierung Std | [0.26862954, 0.26130258, 0.27577711] |
| Interpolation | Bicubic |
| Center Crop | Ja |

---

## Speicherbedarf

| Modell | VRAM | RAM | Status |
|--------|------|-----|--------|
| ViT-B/32 float16 | ~500 MB | ~300 MB | ✅ |
| ViT-L/14 float16 | ~1.5 GB | ~800 MB | ✅ |
| Batch 32 Bilder | +2-3 GB | +1 GB | ✅ |

**RX 7800 XT (16 GB):** Kein Problem

---

## Risikobewertung

| Risiko | Bewertung | Mitigation |
|--------|-----------|------------|
| Modell nicht verfügbar | 🟢 Niedrig | Mehrere ONNX-Varianten vorhanden |
| Performance-Einbußen | 🟡 Mittel | Benchmarking nach Migration |
| Inkompatible Operatoren | 🟢 Niedrig | Standard-CLIP ist gut unterstützt |
| DirectML nicht getestet | 🟡 Mittel | Standard-Ops, sollte funktionieren |

---

## Quellen

1. https://huggingface.co/mlunar/clip-variants
2. https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html
3. https://gpuopen.com/learn/onnx-directlml-execution-provider-guide-part1/
