---
name: Service Architecture
description: Guidelines for the internal module communication, plugin system (Bereiche), and frontend-backend decoupling.
---

# Service Architecture Expert Skill

## Core Principles
- **Decoupling:** The GUI imports the Backend. The Backend *never* imports the GUI.
- **Signals:** Use `PyQtSignals` or a strictly typed `Callback` system for communication.
- **Task Queue:** All background work goes through `task_queue.py`.

## 1. The "Bereiche" (Areas) Concept
PB Studio is modular.
- `Bereiche/Audio`: Self-contained logic for Audio.
- `Bereiche/Video`: Self-contained logic for Video.
- **Interface:** Each Area should expose a `Service` class (e.g., `AudioService`) that the main app consumes.

## 2. Task Queue Pattern
Instead of firing threads wildly:
```python
# In MainController
task = AnalysisTask(file_path="song.mp3")
task_id = self.task_manager.submit(task)
```
- **Benefits:** Cancellation, Progress Tracking, concurrency limits (Max 2 AI tasks at once).

## 3. Dependency Injection
- Pass the `Database` or `Config` instance to the Service. Do not instantiate global Singletons inside the service logic if possible (makes testing hard).
  - *Exception:* `DatabaseCore` is currently a Singleton for safety, but pass it explicitly where possible.

## 4. Startup Sequence
1. **Bootstrapper:** Environment checks.
2. **Splash:** Loading Core Services.
3. **Main Window:** Ready for user input.
*Do not start heavy indexers until the UI is visible.*
