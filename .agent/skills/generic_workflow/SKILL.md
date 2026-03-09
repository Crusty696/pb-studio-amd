---
name: General Development Workflow (The Finalizer)
description: The standard operating procedure for all development tasks in the PB Studio project. Enforces a strict Analysis -> Planning -> Execution -> Reflection cycle.
---

# General Development Workflow: "The Finalizer"

## Purpose
To ensure every code change, no matter how small, is safe, compatible with the project's strict requirements (AMD/ONNX/Offline), and doesn't break existing functionality. We are in the "Finalization Phase", so stability is paramount.

## The Core Cycle

### 1. 🔍 Analyze (The Context Check)
**Before writing a single line of plans or code:**
- **Read the Master Plan:** Ensure your actions align with `MASTER_PLAN_v10.md`.
- **Read Related Code:** Use `view_file` on all files you intend to touch AND their direct dependencies.
- **Check Hardware Context:** Remind yourself: Is this code safe for AMD users? Does it require CUDA? If so, is there a DirectML fallback?
- **Verify Dependencies:** Check `pyproject.toml` or `requirements.txt` before assuming a library exists.

### 2. 📝 Plan (The Roadmap)
**Never skip this step for complex changes.**
- **Create an Implementation Plan:** For any task involving more than one file or complex logic, write an `implementation_plan.md`.
- **Define Success Criteria:** How will you know it works? (e.g., "Script runs without error", "GUI opens within 2 seconds").
- **Identify Risks:** specific to Offline/AMD context (e.g., "Model download might fail offline", "FP16 might overflow").

### 3. 💻 Execute (The Implementation)
- **Use Expert Skills:** Refer to `python_backend`, `pyqt6_gui`, or `ai_inference` skills for specific implementation details.
- **No Placeholders:** Write complete, functional code. No `pass # TODO`.
- **Preserve Existing Logic:** Comment out old code with `# DEPRECATED: [Reason]` instead of deleting it immediately, unless you are 100% sure.
- **Log Everything:** Use `logger.info()` / `logger.error()` generously.

### 4. 🧠 Reflect (The Self-Correction)
**Before marking the task as done:**
- **The "AMD Check":** Will this crash on an AMD card?
- **The "Offline Check":** Did I add a hidden internet dependency (e.g., `huggingface_hub.snapshot_download` without a local check)?
- **The "UI Check":** Did I put a heavy task on the main thread?
- **Run Verification:** Execute the code or a test script.

## Common Pitfalls to Avoid
- **Assuming NVIDIA:** Never assume `cuda` is available. Always check `onnxruntime.get_available_providers()`.
- **Silent Failures:** Never use bare `try: ... except: pass`. Always log the exception.
- **UI Blocking:** Never run AI inference or heavy IO in the `def __init__` of a widget.
