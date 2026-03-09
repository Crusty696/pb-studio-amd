---
name: PyQt6 GUI Expert
description: Guidelines for building responsive, professional, and thread-safe GUIs using PyQt6.
---

# PyQt6 GUI Expert Skill

## Core Principles
- **Framework:** PyQt6.
- **Style:** Modern, Dark Mode compliant.
- **Responsiveness:** Main Thread MUST remain free at all times (latency < 16ms).

## 1. Thread Safety (The Golden Rule)
**NEVER** update UI widgets from a secondary thread.
- **Wrong:** `thread.run(lambda: label.setText("Done"))` -> CRASH.
- **Right:** Use Signals & Slots.

### Pattern: Worker Thread with Signals
```python
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    error = pyqtSignal(str)

    def run(self):
        try:
            # Heavy calculation
            ...
            self.progress.emit(50)
            ...
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

# In your Widget:
self.thread = QThread()
self.worker = Worker()
self.worker.moveToThread(self.thread)
self.thread.started.connect(self.worker.run)
self.worker.finished.connect(self.thread.quit)
self.thread.start()
```

## 2. Preventing "Not Responding"
- Any task taking > 100ms MUST be moved to a thread.
- Use `QTimer.singleShot(0, callback)` to defer heavy initialization after the window shows.

## 3. Project Style
- Use `qss` (Qt Style Sheets) for styling, not hardcoded `setStyleSheet` calls if possible.
- Use Layouts (`QVBoxLayout`, `QHBoxLayout`, `QGridLayout`) exclusively. No absolute positioning.

## 4. Signal Disconnection
Always clean up signals or check connection status to avoid "double-firing" events.
```python
try:
    self.button.clicked.disconnect()
except TypeError:
    pass # Was not connected
self.button.clicked.connect(self.action)
```
