# PB Studio - Definitive Compatibility Matrix (AMD/Windows)

**Status:** COMPLETE (Final Verified)
**Python Version:** 3.11.x (Target)
**OS:** Windows 10/11 x64

| Component | Target Version | Dependency of... | Verified Compatible? | Proof Source / Warning |
|-----------|----------------|------------------|----------------------|------------------------|
| **SYSTEM TOOLS** | | | | |
| VS Build Tools | 2022 (17.x) | Llama-cpp (Build) | ✅ YES | [Microsoft Docs](https://learn.microsoft.com/en-us/cpp/build/vscpp-step-0-installation?view=msvc-170) |
| CMake | >= 3.26 | Llama-cpp (Build) | ✅ YES | [CMake 3.26 Release Notes](https://cmake.org/cmake/help/v3.26/release/3.26.html) |
| FFmpeg | 6.x (Gyan.dev) | Audio-Separator | ✅ YES | [Gyan.dev Feature List](https://www.gyan.dev/ffmpeg/builds/) (Includes AMF) |
| **CORE LIBS** | | | | |
| Numpy | **< 2.0.0** | BeatNet, Pandas | ✅ YES | [Numba Compatibility Matrix](https://numba.readthedocs.io/en/stable/user/installing.html#version-support-information) |
| PyTorch (CPU) | 2.1.x+ | Transformers | ✅ YES | [PyTorch Get Started](https://pytorch.org/get-started/locally/) |
| OnnxRuntime-DML| 1.23.0 | Audio-Sep, RAFT | ✅ YES | [PyPI Release Notes](https://pypi.org/project/onnxruntime-directml/1.23.0/) |
| **APP LIBS** | | | | |
| BeatNet | Latest | Beat Detection | ⚠️ PATCH REQUIRED | Incompatible w/ Py3.11 without `collections` patch. |
| Audio-Separator| Latest | Stem Separation | ✅ YES | [Audio-Separator PyPI](https://pypi.org/project/audio-separator/) (Requires Py >= 3.9) |
| Transformers | Latest | Tokenizer | ✅ YES | [HuggingFace Docs](https://huggingface.co/docs/transformers/installation#python) |
| FAISS-CPU | 1.7.4 | Vector DB | ✅ YES | Wheel available for cp311-win_amd64. |
| **MONITORING** | | | | |
| LibreHardWareMonitor | Latest (DLL) | GPU Monitoring | ✅ YES | **Automated via Script**. No Driver-CLI dependency. Uses `pythonnet`. |
| **MODELS** | | | | |
| Moondream GGUF | GGUF | Vision LLM | ✅ YES | [Llama.cpp Vulkan Support](https://github.com/ggerganov/llama.cpp/pull/2059) |
| RAFT ONNX | Opset 17 | Motion | ✅ YES | [OnnxRuntime Compat](https://onnxruntime.ai/docs/reference/compatibility.html) |
