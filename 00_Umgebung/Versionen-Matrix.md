# Versionen-Matrix AMD

**Stand:** 04.01.2026
**Validiert für:** RX 7800 XT, Windows 10/11

---

## Python & Runtime

| Komponente | Version | Quelle | Status |
|------------|---------|--------|--------|
| Python | 3.10.x oder 3.11.x | python.org | ✅ Validiert |
| onnxruntime-directml | 1.23.0 | PyPI | ✅ Validiert |
| DirectML | 1.15.2 | (in ORT) | ✅ Validiert |
| ONNX Opset | bis 20 | - | ✅ |

---

## ML Pakete

| Paket | Version | Verwendung |
|-------|---------|------------|
| transformers | >=4.36.0 | Tokenizer, Preprocessing |
| huggingface-hub | >=0.20.0 | Model Downloads |
| Pillow | >=10.0.0 | Bildverarbeitung |
| numpy | >=1.24.0 | Arrays |
| scipy | >=1.11.0 | Signal Processing |

---

## Audio Pakete

| Paket | Version | Verwendung |
|-------|---------|------------|
| audio-separator | >=0.17.0 | Stem Separation (DirectML) |
| librosa | >=0.10.0 | Audio-Analyse |
| soundfile | >=0.12.0 | Audio I/O |

---

## Video Pakete

| Paket | Version | Verwendung |
|-------|---------|------------|
| opencv-python | >=4.8.0 | Frame Processing |
| scenedetect | >=0.6.0 | Scene Detection |

---

## Datenbank

| Paket | Version | Verwendung |
|-------|---------|------------|
| chromadb | >=0.4.0 | Vector Store |

---

## ONNX Modelle (HuggingFace)

| Modell | Repository | Größe |
|--------|------------|-------|
| CLIP ViT-B-32 | sayantan47/clip-vit-b32-onnx | ~600 MB |
| CLAP Music | Xenova/larger_clap_music_and_speech | ~400 MB |
| Phi-3.5-Vision | microsoft/Phi-3.5-vision-instruct-onnx | ~10 GB |
| Florence-2 (Alt) | onnx-community/Florence-2-large | ~3-4 GB |

---

## FFmpeg

| Komponente | Version | Hinweis |
|------------|---------|---------|
| FFmpeg | >=6.0 | Mit AMF Support |
| h264_amf | - | AMD H.264 Encoder |
| hevc_amf | - | AMD HEVC Encoder |
| av1_amf | - | AMD AV1 (RDNA3 only) |

---

## AMD Treiber

| Komponente | Version | Hinweis |
|------------|---------|---------|
| Adrenalin | 24.x+ | Aktuell halten! |
| DirectX | 12 | Windows integriert |

---

## requirements-amd.txt

```txt
# Core Runtime
onnxruntime-directml==1.23.0

# ML & Transformers
transformers>=4.36.0
huggingface-hub>=0.20.0
Pillow>=10.0.0
numpy>=1.24.0
scipy>=1.11.0

# Audio
audio-separator[dml]>=0.17.0
librosa>=0.10.0
soundfile>=0.12.0

# Video
opencv-python>=4.8.0
scenedetect>=0.6.0

# Database
chromadb>=0.4.0

# UI (falls benötigt)
PyQt6>=6.5.0
```

---

## NICHT installieren (Konflikte!)

```txt
# Diese Pakete NICHT installieren:
# onnxruntime (kollidiert mit directml)
# onnxruntime-gpu (CUDA only)
# torch-directml (Maintenance Mode)
# nvidia-ml-py
# torch+cu* (CUDA builds)
```

---

*Matrix erstellt: 04.01.2026*
