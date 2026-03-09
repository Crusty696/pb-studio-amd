---
name: Verification & QA
description: Guidelines for testing, manual verification, and ensuring stability in the PB Studio project.
---

# Verification & QA Expert Skill

## Core Principles
- **No Unverified Claims:** Never say "it works" until you have seen it run or have a robust test output; otherwise say "implemented, pending verification".
- **AMD First:** Always verify that typical NVIDIA-only assumptions aren't breaking the build.

## 1. Automated Testing Strategy
- **Unit Tests:** Use `pytest`. Located in `tests/`.
- **Integration Tests:** Run scripts in `Src/` or `tools/` that simulate a full workflow (e.g., `test_pipeline.py`).

## 2. Manual Verification Checklist
When a task is "Done", perform these checks:
1. **Startup:** Does the app launch without warnings in the console?
2. **GUI Latency:** Does clicking the button freeze the UI?
3. **Logic:** Does the output match expectations (e.g., is the generated file actually there)?
4. **Logs:** Are there any `ERROR` or `CRITICAL` logs in `logs/app.log`?

## 3. UI Automation
- We (the agent) cannot "see" the screen.
- **Proxy Verification:** Use screenshot analysis or check accessibility trees if possible, OR rely on internal state dumps.
- **Best Practice:** Add a "Debug Dump" button or command if a feature is hard to verify blindly.
