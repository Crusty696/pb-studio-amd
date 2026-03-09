---
name: Hardware Control
description: Guidelines for managing hardware resources, integrating LibreHardwareMonitor, and handling GPU acceleration specifics.
---

# Hardware Control Expert Skill

## Core Principles
- **We Know the Hardware:** The app adapts to the user, not the other way around.
- **Monitoring:** We need to know if the GPU is melting or VRAM is full *before* we crash.

## 1. LibreHardwareMonitor (LHM)
- **Integration:** Accessed via `http_api` or `.NET` wrapper (if implemented).
- **Metrics:**
  - `GPU Load`: If > 90%, pause background indexing.
  - `VRAM Used`: If > 7.5GB on an 8GB card, do not load another model.

## 2. GPU Acceleration (FFmpeg)
- **NVIDIA:** `h264_nvenc`, `h264_cuvid`.
- **AMD:** `h264_amf`.
- **Intel:** `h264_qsv`.
- **Detection:** Run `ffmpeg -hide_banner -encoders` to see what is available during setup.

## 3. Thread Affinity
- Heavy AI Workers should run with lower process priority on the OS level if they impact the UI responsiveness too much:
  ```python
  import psutil, os
  p = psutil.Process(os.getpid())
  p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
  ```
