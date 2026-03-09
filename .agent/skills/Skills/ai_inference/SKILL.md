---
name: AI Inference (ONNX DirectML)
description: Guidelines for implementing AI models using ONNX Runtime with a strict focus on AMD DirectML compatibility and fallback mechanisms.
---

# AI Inference Expert Skill

## Core Principles
- **Runtime:** `onnxruntime-directml` (Primary) or `onnxruntime-gpu` (NVIDIA only).
- **Precision:** FP16 (Float16) for modern GPUs, FP32 fallback for CPU.
- **Library:** Do NOT use PyTorch (`torch`) for inference in production if possible. Use ONNX Runtime to ensure AMD compatibility without minimal dependencies.

## 1. Hardware Detection Strategy
Always detect providers dynamically. NEVER hardcode `['CUDAExecutionProvider']`.

```python
import onnxruntime as ort

def get_optimal_providers():
    available = ort.get_available_providers()
    providers = []
    
    # Priority 1: DirectML (AMD/Intel/NVIDIA) - Broadest compatibility
    if 'DmlExecutionProvider' in available:
        providers.append('DmlExecutionProvider')
    
    # Priority 2: CUDA (NVIDIA only)
    if 'CUDAExecutionProvider' in available:
        providers.append('CUDAExecutionProvider')
        
    # Priority 3: CPU (Fallback)
    providers.append('CPUExecutionProvider')
    
    return providers
```

## 2. Session Management
- **InferenceSession:** Create sessions ONCE and reuse them. Creating a session is expensive.
- **Context Manager:** Wrap session creation in try/except blocks to catch DLL load errors (common with missing DirectML libs).

## 3. FP16 vs FP32
- Most ONNX models for this project (Moondream, etc.) should be exported/loaded in FP16 for speed on GPU.
- **Caveat:** If DirectML fails, falling back to CPU with an FP16 model might crash or be slow.
- **Solution:** Maintain distinct model paths for `fp16` (GPU) and `fp32` (CPU/Compat) if critical, OR use models that support dynamic casting (less common).
- **Default:** Assume the user has a GPU capable of FP16 via DirectML.

## 4. Input Pre-processing
- Use `numpy` for pre-processing images/audio effectively.
- Ensure shapes match exactly what the ONNX model expects (NCHW format is standard).
