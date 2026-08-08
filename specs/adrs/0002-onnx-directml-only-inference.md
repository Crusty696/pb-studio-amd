# ADR-0002: ONNX Runtime DirectML-only Inference

> Date: 2026-07-28 | Status: accepted | Supersedes incompatible inference guidance in ADR-0001 and earlier Brain notes

## Context

Earlier PB Studio notes allowed CPU SigLIP/CLAP fallbacks or `torch-directml`. Those paths conflict with the current AMD architecture rules and make resource ownership and failure states unreliable.

## Decision

1. AI inference uses `onnxruntime-directml` with `DmlExecutionProvider` only.
2. Every DirectML session sets `enable_mem_pattern=False` and `enable_cpu_mem_arena=False`.
3. `CPUExecutionProvider`, PyTorch CPU inference and `torch-directml` are forbidden as runtime fallbacks.
4. FAISS-CPU, BeatNet/librosa analysis and the explicitly documented Demucs PyTorch-CPU path are data/DSP exceptions, not ONNX inference fallbacks.
5. Missing or incompatible ONNX assets make the capability explicitly unavailable. Semantic Audio is disabled when a functional CLAP-ONNX model is absent.
6. DirectML execution remains serialized through the project GPU lock and VRAM budget lifecycle.

## Consequences

* Failures are explicit instead of silently moving workload to CPU/RAM.
* Model registry capability checks become release gates.
* Earlier CPU-SigLIP, CPU-CLAP and `torch-directml` recommendations are superseded.

