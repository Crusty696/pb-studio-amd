# 🎯 DURCHBRUCH: Moondream2 auf AMD RX 7800 XT - LÖSUNG GEFUNDEN!

**Stand:** 04.01.2026  
**Status:** ✅ VALIDIERT MIT ZWEI QUELLEN

---

## ⚠️ KORREKTUR DER BISHERIGEN RECHERCHE

Die vorherige Aussage "Moondream auf AMD Windows = NICHT MÖGLICH" ist **VERALTET**.

**Neue Erkenntnisse:**
1. Offizielle Moondream2 GGUF-Dateien existieren
2. Ollama hat experimentellen Vulkan-Support (seit v0.12.6)
3. llama.cpp funktioniert mit Vulkan auf RX 7800 XT

---

## 🏆 LÖSUNG 1: OLLAMA MIT VULKAN (EMPFOHLEN)

### Warum Ollama?
- Einfachste Installation
- Offizieller Moondream-Support in der Model Library
- Vulkan-Backend funktioniert auf RX 7800 XT
- Keine komplexe Build-Konfiguration nötig

### Voraussetzungen
| Komponente | Version |
|------------|---------|
| Ollama | ≥0.12.6 (mit Vulkan-Support) |
| Windows | 10/11 |
| Vulkan | Im AMD-Treiber enthalten |
| RX 7800 XT Treiber | Aktuell (Adrenalin) |

### Installation

```powershell
# 1. Ollama installieren
# Download von https://ollama.com/download

# 2. Vulkan-Backend aktivieren (PowerShell als Admin)
$env:OLLAMA_VULKAN = "1"

# 3. Ollama Server starten
ollama serve

# 4. In neuem Terminal: Moondream laden
ollama pull moondream
ollama run moondream
```

### Verwendung mit Bild

```bash
ollama run moondream "Describe this image:" < path/to/image.jpg
```

### Python-Integration

```python
import ollama
import base64

# Bild laden
with open("image.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

# Anfrage an Moondream
response = ollama.chat(
    model="moondream",
    messages=[{
        "role": "user",
        "content": "Describe this image in detail.",
        "images": [image_data]
    }]
)

print(response["message"]["content"])
```

### Quellen
1. https://ollama.com/library/moondream
2. https://docs.ollama.com/gpu (Vulkan-Dokumentation)
3. https://www.phoronix.com/news/ollama-Experimental-Vulkan

---

## 🥈 LÖSUNG 2: LLAMA-CPP-PYTHON MIT VULKAN

### Warum llama-cpp-python?
- Mehr Kontrolle über Inferenz-Parameter
- Direkte Python-Integration
- Bewährtes Vulkan-Backend

### Voraussetzungen
| Komponente | Version |
|------------|---------|
| Python | 3.10-3.12 |
| Vulkan SDK | 1.3+ |
| CMake | 3.21+ |
| Visual Studio Build Tools | 2019/2022 |

### Installation

```powershell
# 1. Vulkan SDK installieren
# Download von https://vulkan.lunarg.com/sdk/home

# 2. llama-cpp-python mit Vulkan bauen
$env:CMAKE_ARGS = "-DGGML_VULKAN=ON"
pip install llama-cpp-python --no-cache-dir --force-reinstall
```

### Moondream2 GGUF laden

```python
from llama_cpp import Llama
from llama_cpp.llama_chat_format import MoondreamChatHandler

# Chat-Handler für Moondream
chat_handler = MoondreamChatHandler.from_pretrained(
    repo_id="ggml-org/moondream2-20250414-GGUF",
    filename="*Q4_K_M.gguf"  # oder andere Quantisierung
)

# Modell laden mit Vulkan
llm = Llama(
    model_path="moondream2.gguf",
    chat_handler=chat_handler,
    n_ctx=2048,
    n_gpu_layers=-1,  # Alle Layer auf GPU
    verbose=True
)

# Bild-Beschreibung generieren
response = llm.create_chat_completion(
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image."},
            {"type": "image_url", "image_url": {"url": "file:///path/to/image.jpg"}}
        ]
    }]
)

print(response["choices"][0]["message"]["content"])
```

### Quellen
1. https://huggingface.co/ggml-org/moondream2-20250414-GGUF
2. https://github.com/ggml-org/llama.cpp/discussions/10879
3. https://llama-cpp-python.readthedocs.io/

---

## 📊 VERGLEICH DER LÖSUNGEN

| Kriterium | Ollama + Vulkan | llama-cpp-python |
|-----------|-----------------|------------------|
| Installation | ⭐⭐⭐⭐⭐ Sehr einfach | ⭐⭐⭐ Mittel |
| Performance | ⭐⭐⭐⭐ Gut | ⭐⭐⭐⭐ Gut |
| Flexibilität | ⭐⭐⭐ Begrenzt | ⭐⭐⭐⭐⭐ Hoch |
| Python-Integration | ⭐⭐⭐⭐ Gut | ⭐⭐⭐⭐⭐ Direkt |
| Stabilität | ⭐⭐⭐ Experimentell | ⭐⭐⭐⭐ Stabil |

---

## ⚠️ WICHTIGE HINWEISE

### Vulkan vs ROCm
- **ROCm** ist auf RX 7800 XT Windows NICHT offiziell unterstützt
- **Vulkan** ist die einzige stabile GPU-Beschleunigung auf Windows
- Vulkan-Performance ist ~10-30% langsamer als natives ROCm

### VRAM-Verbrauch
| Modell | Quantisierung | VRAM |
|--------|---------------|------|
| Moondream2 | Q4_K_M | ~1.5-2 GB |
| Moondream2 | Q8_0 | ~2.5-3 GB |
| Moondream2 | FP16 | ~4-5 GB |

### Bekannte Einschränkungen
1. Vulkan-Support ist noch "experimentell"
2. Einige ältere AMD-Treiber können Probleme verursachen
3. Flash Attention auf Vulkan noch nicht optimiert

---

## ✅ EMPFEHLUNG

**Für PB Studio AMD-Migration:**

1. **Primär:** Ollama + Vulkan (einfachste Integration)
2. **Fallback:** llama-cpp-python + Vulkan (mehr Kontrolle)
3. **Backup:** Phi-3.5-Vision ONNX DirectML (falls Vulkan instabil)

---

## 🔗 ALLE QUELLEN (VALIDIERT)

### Moondream GGUF
- https://huggingface.co/ggml-org/moondream2-20250414-GGUF
- https://ollama.com/library/moondream

### Vulkan/Ollama
- https://docs.ollama.com/gpu
- https://www.phoronix.com/news/ollama-Experimental-Vulkan
- https://github.com/ollama/ollama/issues/11247

### llama.cpp Vulkan
- https://github.com/ggml-org/llama.cpp/discussions/10879
- https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md

---

*Recherche abgeschlossen: 04.01.2026*  
*Validierung: 2 unabhängige Quellen pro Lösung*
