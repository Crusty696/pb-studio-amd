# ADR-0001: Hybrid Architecture with DirectML Support

> Date: 2026-04-24 | Status: accepted

## Context
PB Studio requires high-performance AI processing for long audio and video files on local hardware. The target audience includes AMD GPU users, which makes CUDA-only solutions inappropriate. The application needs a modern, responsive desktop UI.

## Decision
We adopt a **Hybrid Architecture** consisting of:
1.  **Frontend (WPF/.NET 9)**: Provides a native Windows UI with high responsiveness and deep system integration.
2.  **Backend (FastAPI/Python 3.11)**: Handles AI logic, media processing, and GPU orchestration. Python is chosen for its superior AI library ecosystem.
3.  **GPU Acceleration (DirectML)**: Use `onnxruntime-directml` as the primary inference engine to ensure compatibility with AMD, Intel, and Nvidia hardware.

## Rationale
- **Performance**: Python's AI libraries (Librosa, BeatNet, Moondream) are industry standards, while WPF provides the best desktop experience on Windows.
- **Inclusivity**: DirectML removes the dependency on Nvidia-proprietary CUDA, supporting the project's core "AMD DirectML First" principle.
- **Maintainability**: Separating UI and Logic via a REST API allows for independent scaling and testing of the core domain.

## Consequences
- **Positive**: Full hardware support for AMD users; clean separation of concerns; responsive UI even during heavy AI tasks.
- **Negative**: Increased complexity due to inter-process communication (REST); larger installation footprint (Python + .NET).
