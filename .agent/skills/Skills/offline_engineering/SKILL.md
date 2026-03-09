---
name: Offline Engineering
description: Guidelines for building fully offline-capable systems, managing local assets, and preventing accidental internet dependencies.
---

# Offline Engineering Skill

## Core Principles
- **No "Phoning Home":** The application must function 100% without an internet connection after installation.
- **Local Assets:** Models, icons, and configuration files must be bundled or downloaded explicitly *once* during setup.

## 1. Model Asset Management
Do not use `transformers.pipeline(model="openai/whisper-base")` during runtime. This triggers a Hugging Face Hub download.

**Correct Pattern:**
1. **Download Phase (Installer/Setup):**
   Explicitly download the model files (`.onnx`, `.json`) to a local `models/` directory.
2. **Runtime Phase:**
   Load strictly from the local path.
   ```python
   model_path = Path("models/moondream.onnx")
   if not model_path.exists():
       raise FileNotFoundError("Model not found. Please run setup.")
   session = ort.InferenceSession(str(model_path), ...)
   ```

## 2. Dependency Management
- **Pip:** We assume the user has installed dependencies via the specific requirements file or the One-Click Installer.
- **Venv:** The application should be able to identify its own virtual environment.

## 3. The "Airplane Mode" Test
- When verifying, ask yourself: "If I unplug the ethernet cable, will this feature crash?"
- If the answer is "Maybe", add a check:
  ```python
  def ensure_offline_safe():
      # Pseudo-code logic
      if requires_download and not internet_available:
          show_error("Offline Mode: Cannot download new model.")
          return False
  ```
