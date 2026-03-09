# AI Inference Skill (ONNX DirectML)

## Trigger
Aktiviere diesen Skill automatisch bei:
- "ONNX", "DirectML", "Inference", "AI Model", "GPU", "FP16", "FP32"
- Arbeit an `src/pb_studio/ai/`, `models/`, `*_inference*.py`
- Fragen zu AMD GPU Kompatibilität

## Cross-References
- → `hardware-control.md` (GPU-Monitoring, VRAM-Check)
- → `offline-engineering.md` (Lokale Modelle)
- → `python-backend.md` (Error Handling)
- → `debugging.md` (Performance-Profiling)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Runtime** | `onnxruntime-directml` - AMD GPU Beschleunigung |
| **Precision** | FP16 für GPU, FP32 Fallback für CPU |
| **No PyTorch** | Kein `torch` für Production-Inference - nur ONNX Runtime |

---

## 1. Hardware Detection (AMD-Only)

```python
import onnxruntime as ort
from typing import list
import logging

logger = logging.getLogger(__name__)

def get_optimal_providers() -> list[str]:
    """Ermittelt optimale ONNX Execution Providers für AMD."""
    available = ort.get_available_providers()
    providers = []
    
    # Priority 1: DirectML (AMD/Intel) - Unsere Zielplattform
    if 'DmlExecutionProvider' in available:
        providers.append('DmlExecutionProvider')
        logger.info("DirectML Provider verfügbar - AMD GPU Support aktiv")
    
    # Priority 2: CPU Fallback (immer verfügbar)
    providers.append('CPUExecutionProvider')
    
    logger.info(f"Aktive Provider-Reihenfolge: {providers}")
    return providers

def get_device_info() -> dict:
    """Gibt detaillierte Geräteinformationen zurück."""
    return {
        "available_providers": ort.get_available_providers(),
        "selected_providers": get_optimal_providers(),
        "device": ort.get_device(),
    }
```

---

## 2. Session Management Pattern

```python
from pathlib import Path
from contextlib import contextmanager
import onnxruntime as ort

class ONNXSessionManager:
    """Singleton für ONNX Session Management mit Caching."""
    
    _instances: dict[str, ort.InferenceSession] = {}
    
    @classmethod
    def get_session(cls, model_path: Path, use_fp16: bool = True) -> ort.InferenceSession:
        """Holt oder erstellt eine ONNX Session (gecacht)."""
        cache_key = f"{model_path}_{use_fp16}"
        
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls._create_session(model_path, use_fp16)
        
        return cls._instances[cache_key]
    
    @classmethod
    def _create_session(cls, model_path: Path, use_fp16: bool) -> ort.InferenceSession:
        """Erstellt eine neue ONNX Session mit Fehlerbehandlung."""
        if not model_path.exists():
            raise FileNotFoundError(f"Model nicht gefunden: {model_path}")
        
        providers = get_optimal_providers()
        
        # Session Options für Performance
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 4
        
        try:
            session = ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=providers
            )
            logger.info(f"Session erstellt: {model_path.name} auf {session.get_providers()}")
            return session
            
        except Exception as e:
            logger.error(f"Session-Erstellung fehlgeschlagen: {e}")
            # Fallback: Nur CPU
            logger.warning("Fallback zu CPU-only Provider")
            return ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=['CPUExecutionProvider']
            )
    
    @classmethod
    def clear_cache(cls):
        """Leert den Session-Cache (für Memory Management)."""
        cls._instances.clear()
        logger.info("ONNX Session Cache geleert")
```

---

## 3. FP16/FP32 Handling

```python
import numpy as np

def prepare_input(data: np.ndarray, session: ort.InferenceSession) -> np.ndarray:
    """Konvertiert Input zur erwarteten Precision des Models."""
    input_info = session.get_inputs()[0]
    expected_type = input_info.type
    
    if 'float16' in expected_type:
        return data.astype(np.float16)
    elif 'float32' in expected_type:
        return data.astype(np.float32)
    else:
        return data

def safe_inference(session: ort.InferenceSession, input_data: np.ndarray) -> np.ndarray:
    """Führt Inference mit automatischer Precision-Anpassung durch."""
    input_name = session.get_inputs()[0].name
    prepared_input = prepare_input(input_data, session)
    
    try:
        outputs = session.run(None, {input_name: prepared_input})
        return outputs[0]
    except Exception as e:
        logger.error(f"Inference fehlgeschlagen: {e}")
        # Bei FP16-Fehler: Retry mit FP32
        if 'float16' in str(e).lower():
            logger.warning("FP16 Fehler - Retry mit FP32")
            return session.run(None, {input_name: input_data.astype(np.float32)})[0]
        raise
```

---

## 4. Image Preprocessing (NCHW Format)

```python
import numpy as np
from PIL import Image

def preprocess_image(
    image: Image.Image | np.ndarray,
    target_size: tuple[int, int] = (224, 224),
    normalize: bool = True
) -> np.ndarray:
    """Preprocessed Image für ONNX Model (NCHW Format)."""
    
    # PIL zu numpy
    if isinstance(image, Image.Image):
        image = image.convert("RGB")
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        img_array = np.array(image)
    else:
        img_array = image
    
    # HWC -> CHW
    img_array = img_array.transpose(2, 0, 1)
    
    # Batch dimension: CHW -> NCHW
    img_array = np.expand_dims(img_array, axis=0)
    
    # Normalisierung (ImageNet Standard)
    if normalize:
        mean = np.array([0.485, 0.456, 0.406]).reshape(1, 3, 1, 1)
        std = np.array([0.229, 0.224, 0.225]).reshape(1, 3, 1, 1)
        img_array = (img_array / 255.0 - mean) / std
    
    return img_array.astype(np.float32)
```

---

## 5. VRAM-Safe Batch Processing

```python
def batch_inference_safe(
    session: ort.InferenceSession,
    inputs: list[np.ndarray],
    max_batch_size: int = 4,
    vram_limit_gb: float = 6.0
) -> list[np.ndarray]:
    """Batch-Inference mit VRAM-Überwachung."""
    results = []
    
    for i in range(0, len(inputs), max_batch_size):
        batch = inputs[i:i + max_batch_size]
        batch_array = np.stack(batch, axis=0)
        
        # VRAM Check (siehe hardware-control.md)
        # if get_vram_used_gb() > vram_limit_gb:
        #     logger.warning("VRAM Limit erreicht - reduziere Batch Size")
        #     max_batch_size = max(1, max_batch_size // 2)
        
        output = safe_inference(session, batch_array)
        results.extend([output[j] for j in range(output.shape[0])])
    
    return results
```

---

## Checkliste: AI Inference

### Vor der Implementierung
- [ ] Model existiert lokal in `models/`?
- [ ] Model-Format: `.onnx`?
- [ ] FP16 oder FP32 Version verfügbar?
- [ ] Input-Shape dokumentiert (NCHW)?

### Bei der Implementierung
- [ ] `get_optimal_providers()` verwendet?
- [ ] Session wird gecacht (nicht bei jedem Aufruf neu erstellt)?
- [ ] Error Handling für DLL-Load-Fehler?
- [ ] Fallback zu CPU implementiert?

### Nach der Implementierung
- [ ] Auf AMD GPU getestet?
- [ ] VRAM-Verbrauch gemessen?
- [ ] Inference-Zeit geloggt?
- [ ] Offline-Betrieb verifiziert?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `DLL load failed` | DirectML nicht installiert | `pip install onnxruntime-directml` |
| `Invalid input shape` | Falsches Format (HWC statt NCHW) | `transpose(2,0,1)` + `expand_dims` |
| `Out of memory` | VRAM voll | Batch Size reduzieren oder CPU Fallback |
| `Float16 overflow` | FP16 auf CPU | Explizit FP32 Model für CPU nutzen |
| `Provider not found` | Falsche onnxruntime Version | `onnxruntime-directml` für AMD |
