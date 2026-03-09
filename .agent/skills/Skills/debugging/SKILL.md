---
name: Debugging & Profiling
description: Expert guidelines for diagnosing issues, analyzing logs, and profiling performance in PB Studio.
---

# Debugging & Profiling Skill

## Core Principles
- **Evidence-Based:** Don't guess. Look at the logs.
- **Reproducibility:** If you can't reproduce it, you can't definitively fix it.

## 1. Log Analysis
- **Location:** `logs/debug.log` or `logs/app.log`.
- **Pattern:** Look for "Traceback", "Error", "Warning".
- **Context:** Check the lines *before* the error to understand the state.

## 2. Debugging Techniques
### The "Print" Debugger (Enhanced)
Instead of just `print()`, use the logger or a structured output:
```python
logger.debug(f"State Dump: var1={var1}, var2={type(var2)}")
```
### Dependency Conflicts
- If an import fails, check `sys.path` and `pip list`.
- Use `tools/verify_env.py` (if it exists) to check the environment sanity.

## 3. Profiling (Performance)
- **Slow UI?** Check if you are blocking the Main Thread.
- **Slow Inference?** Check if you are actually using the GPU (DirectML) or falling back to CPU.
  - *Tip:* Log `session.get_providers()` to see what is active.
