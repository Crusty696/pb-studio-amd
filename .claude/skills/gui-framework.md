# PyQt6 GUI Framework Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "GUI", "PyQt", "Widget", "Window", "Button", "Layout", "Signal", "Slot"
- Arbeit an `src/pb_studio/gui/`, `*_widget.py`, `*_window.py`
- Fragen zu UI-Responsiveness, Threading, Events

## Cross-References
- → `python-backend.md` (Async Patterns, Error Handling)
- → `debugging.md` (UI Freeze Detection)
- → `service-architecture.md` (Frontend-Backend Trennung)
- → `ai-inference.md` (Inference in Background Thread)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Framework** | PyQt6 (nicht PyQt5, nicht PySide6) |
| **Style** | Modern, Dark Mode, Material-inspired |
| **Golden Rule** | Main Thread NIEMALS blockieren (< 16ms) |

---

## 1. Thread Safety - Die GOLDENE Regel

### ❌ CRASH - UI Update aus Thread
```python
# Das wird CRASHEN oder zu undefiniertem Verhalten führen!
def background_task():
    result = heavy_computation()
    self.label.setText(result)  # ❌ NIEMALS!
```

### ✅ RICHTIG - Signals & Slots Pattern
```python
from PyQt6.QtCore import QObject, QThread, pyqtSignal

class Worker(QObject):
    """Worker für Background-Operationen."""
    
    # Signals für Kommunikation mit Main Thread
    started = pyqtSignal()
    progress = pyqtSignal(int, str)  # percent, message
    result = pyqtSignal(object)      # any result
    error = pyqtSignal(str)          # error message
    finished = pyqtSignal()
    
    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False
    
    def run(self):
        """Führt die eigentliche Arbeit aus."""
        self.started.emit()
        
        try:
            # Progress-Callback injizieren falls gewünscht
            if 'progress_callback' in self.kwargs:
                self.kwargs['progress_callback'] = self._emit_progress
            
            result = self.task_func(*self.args, **self.kwargs)
            
            if not self._is_cancelled:
                self.result.emit(result)
                
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))
                logger.error(f"Worker error: {e}", exc_info=True)
        finally:
            self.finished.emit()
    
    def _emit_progress(self, percent: int, message: str = ""):
        """Thread-safe Progress-Emission."""
        if not self._is_cancelled:
            self.progress.emit(percent, message)
    
    def cancel(self):
        """Markiert Worker als abgebrochen."""
        self._is_cancelled = True


class TaskRunner:
    """Verwaltet Worker und Threads."""
    
    def __init__(self, parent: QObject = None):
        self.parent = parent
        self._threads: list[QThread] = []
        self._workers: list[Worker] = []
    
    def run(
        self,
        task_func,
        *args,
        on_result=None,
        on_error=None,
        on_progress=None,
        on_finished=None,
        **kwargs
    ) -> Worker:
        """Startet Task in Background Thread."""
        
        thread = QThread()
        worker = Worker(task_func, *args, **kwargs)
        
        # Worker in Thread verschieben
        worker.moveToThread(thread)
        
        # Connections
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        # Cleanup tracking
        thread.finished.connect(lambda: self._cleanup(thread, worker))
        
        # User callbacks
        if on_result:
            worker.result.connect(on_result)
        if on_error:
            worker.error.connect(on_error)
        if on_progress:
            worker.progress.connect(on_progress)
        if on_finished:
            worker.finished.connect(on_finished)
        
        # Track & Start
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()
        
        return worker
    
    def _cleanup(self, thread: QThread, worker: Worker):
        """Räumt beendete Threads auf."""
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)
    
    def cancel_all(self):
        """Bricht alle laufenden Tasks ab."""
        for worker in self._workers:
            worker.cancel()
        for thread in self._threads:
            thread.quit()
            thread.wait(1000)
```

---

## 2. Responsive Startup Pattern

```python
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QSplashScreen

class MainWindow(QMainWindow):
    """MainWindow mit deferred Loading."""
    
    def __init__(self):
        super().__init__()
        
        # 1. Minimales UI sofort aufbauen
        self._setup_minimal_ui()
        
        # 2. Schwere Initialisierung NACH show() deferred
        QTimer.singleShot(0, self._deferred_init)
    
    def _setup_minimal_ui(self):
        """Nur das Nötigste - muss < 100ms sein."""
        self.setWindowTitle("PB Studio")
        self.resize(1200, 800)
        
        # Placeholder für Content
        self.setCentralWidget(QWidget())
        self.statusBar().showMessage("Initialisiere...")
    
    def _deferred_init(self):
        """Schwere Initialisierung nach UI-Show."""
        # Jetzt ist das Fenster sichtbar
        # Hier können wir weitere Komponenten laden
        
        self.task_runner = TaskRunner(self)
        
        # Weitere schwere Loads in Background
        self.task_runner.run(
            self._load_services,
            on_result=self._on_services_loaded,
            on_error=self._on_init_error
        )
    
    def _load_services(self) -> dict:
        """Lädt Services (läuft in Background Thread)."""
        from src.pb_studio.data import DatabaseCore
        from src.pb_studio.ai import ModelManager
        
        return {
            "database": DatabaseCore(),
            "models": ModelManager()
        }
    
    def _on_services_loaded(self, services: dict):
        """Callback wenn Services geladen (Main Thread)."""
        self.database = services["database"]
        self.models = services["models"]
        
        # Jetzt vollständiges UI aufbauen
        self._setup_full_ui()
        self.statusBar().showMessage("Bereit", 3000)
    
    def _on_init_error(self, error: str):
        """Fehler bei Initialisierung."""
        QMessageBox.critical(self, "Initialisierungsfehler", error)
```

---

## 3. Signal Management

```python
from PyQt6.QtCore import pyqtSignal, QObject
from typing import Callable
from weakref import WeakMethod, ref

class SignalManager:
    """Verwaltet Signal-Connections sicher."""
    
    def __init__(self):
        self._connections: list[tuple] = []
    
    def connect(self, signal, slot: Callable, connection_type=None):
        """Verbindet Signal mit Slot und trackt Connection."""
        if connection_type:
            signal.connect(slot, connection_type)
        else:
            signal.connect(slot)
        
        self._connections.append((signal, slot))
    
    def disconnect_all(self):
        """Trennt alle getrackten Connections."""
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass  # War bereits disconnected
        
        self._connections.clear()


# Sicheres Connect/Disconnect Pattern
def safe_connect(signal, slot):
    """Verbindet Signal, trennt vorher falls bereits verbunden."""
    try:
        signal.disconnect(slot)
    except TypeError:
        pass  # War nicht verbunden
    signal.connect(slot)

def safe_disconnect(signal, slot=None):
    """Trennt Signal sicher."""
    try:
        if slot:
            signal.disconnect(slot)
        else:
            signal.disconnect()
    except TypeError:
        pass  # War nicht verbunden
```

---

## 4. Custom Widgets mit State Management

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal
from dataclasses import dataclass
from enum import Enum, auto

class WidgetState(Enum):
    IDLE = auto()
    LOADING = auto()
    READY = auto()
    ERROR = auto()

@dataclass
class AudioFileState:
    path: str = ""
    duration: float = 0.0
    bpm: float = 0.0
    is_analyzed: bool = False

class AudioFileWidget(QWidget):
    """Widget mit explizitem State Management."""
    
    # Signals
    analysis_requested = pyqtSignal(str)  # file_path
    state_changed = pyqtSignal(WidgetState)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._state = WidgetState.IDLE
        self._data = AudioFileState()
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Erstellt UI-Komponenten."""
        layout = QVBoxLayout(self)
        
        self.title_label = QLabel("Keine Datei geladen")
        self.info_label = QLabel("")
        self.analyze_btn = QPushButton("Analysieren")
        self.analyze_btn.setEnabled(False)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.analyze_btn)
    
    def _connect_signals(self):
        """Verbindet interne Signals."""
        self.analyze_btn.clicked.connect(self._on_analyze_clicked)
    
    # State Management
    @property
    def state(self) -> WidgetState:
        return self._state
    
    @state.setter
    def state(self, new_state: WidgetState):
        if new_state != self._state:
            self._state = new_state
            self._update_ui_for_state()
            self.state_changed.emit(new_state)
    
    def _update_ui_for_state(self):
        """Aktualisiert UI basierend auf State."""
        match self._state:
            case WidgetState.IDLE:
                self.analyze_btn.setEnabled(False)
                self.analyze_btn.setText("Analysieren")
            
            case WidgetState.LOADING:
                self.analyze_btn.setEnabled(False)
                self.analyze_btn.setText("Analysiere...")
            
            case WidgetState.READY:
                self.analyze_btn.setEnabled(True)
                self.analyze_btn.setText("Erneut analysieren")
            
            case WidgetState.ERROR:
                self.analyze_btn.setEnabled(True)
                self.analyze_btn.setText("Erneut versuchen")
    
    # Public Methods
    def load_file(self, path: str, duration: float):
        """Lädt Datei-Info."""
        self._data.path = path
        self._data.duration = duration
        
        self.title_label.setText(Path(path).name)
        self.info_label.setText(f"Dauer: {duration:.1f}s")
        
        self.state = WidgetState.IDLE
        self.analyze_btn.setEnabled(True)
    
    def set_analysis_result(self, bpm: float):
        """Setzt Analyse-Ergebnis."""
        self._data.bpm = bpm
        self._data.is_analyzed = True
        
        self.info_label.setText(
            f"Dauer: {self._data.duration:.1f}s | BPM: {bpm:.1f}"
        )
        self.state = WidgetState.READY
    
    def set_error(self, message: str):
        """Zeigt Fehler an."""
        self.info_label.setText(f"Fehler: {message}")
        self.state = WidgetState.ERROR
    
    # Event Handlers
    def _on_analyze_clicked(self):
        """Handler für Analyze-Button."""
        self.state = WidgetState.LOADING
        self.analysis_requested.emit(self._data.path)
```

---

## 5. Layouts - KEINE absoluten Positionen

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QStackedWidget, QGroupBox
)
from PyQt6.QtCore import Qt

def create_responsive_layout() -> QWidget:
    """Beispiel für responsives Layout."""
    
    main_widget = QWidget()
    main_layout = QVBoxLayout(main_widget)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(10)
    
    # Header (horizontal)
    header = QHBoxLayout()
    header.addWidget(QLabel("PB Studio"))
    header.addStretch()  # Füllt Lücke
    header.addWidget(QPushButton("Settings"))
    main_layout.addLayout(header)
    
    # Content mit Splitter (resizable)
    splitter = QSplitter(Qt.Orientation.Horizontal)
    
    # Linke Sidebar
    sidebar = QWidget()
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.addWidget(QLabel("Projekte"))
    sidebar_layout.addWidget(QListWidget())
    sidebar.setMinimumWidth(200)
    sidebar.setMaximumWidth(400)
    splitter.addWidget(sidebar)
    
    # Hauptbereich
    content = QStackedWidget()
    content.addWidget(QLabel("Willkommen"))
    splitter.addWidget(content)
    
    # Splitter-Verhältnis
    splitter.setSizes([250, 750])
    main_layout.addWidget(splitter, stretch=1)
    
    # Footer (fixed height)
    footer = QHBoxLayout()
    footer.addWidget(QLabel("Status: Bereit"))
    footer.addStretch()
    footer.addWidget(QProgressBar())
    main_layout.addLayout(footer)
    
    return main_widget
```

---

## 6. Dark Mode Styling

```python
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 16px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #505050;
    border-color: #666666;
}

QPushButton:pressed {
    background-color: #2d2d2d;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #666666;
}

QPushButton[primary="true"] {
    background-color: #0e639c;
    border-color: #1177bb;
}

QPushButton[primary="true"]:hover {
    background-color: #1177bb;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #264f78;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #0e639c;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #094771;
}

QProgressBar {
    background-color: #3c3c3c;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #0e639c;
    border-radius: 4px;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #5a5a5a;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6a6a6a;
}

QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    padding: 8px 16px;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom: 2px solid #0e639c;
}
"""

def apply_dark_theme(app):
    """Wendet Dark Theme auf QApplication an."""
    app.setStyleSheet(DARK_STYLE)
```

---

## Checkliste: GUI Development

### Thread Safety
- [ ] Alle UI-Updates nur im Main Thread?
- [ ] Worker mit Signals für Background-Tasks?
- [ ] Keine blocking Calls in Event Handlers?

### Responsiveness
- [ ] Startup < 2 Sekunden bis erstes UI sichtbar?
- [ ] Keine Operation > 100ms im Main Thread?
- [ ] Progress-Feedback für lange Operationen?

### Layout
- [ ] Nur Layouts verwendet (keine absolute Positionen)?
- [ ] Stretch/Spacing korrekt für Responsiveness?
- [ ] Minimum/Maximum Sizes wo sinnvoll?

### Cleanup
- [ ] Signals disconnected bei Widget-Destroy?
- [ ] Threads sauber beendet bei Close?
- [ ] Keine Memory Leaks durch zirkuläre Referenzen?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| UI friert ein | Main Thread blockiert | `TaskRunner` für Background-Ops |
| Crash bei Signal | UI-Update aus Thread | Signals verwenden |
| Widget nicht sichtbar | Fehlendes Layout | `setLayout()` aufrufen |
| Style nicht angewendet | QSS Syntax-Fehler | Style validieren |
| Memory Leak | Signal-Connections | `SignalManager` verwenden |
| Langsamer Start | Heavy Init in `__init__` | `QTimer.singleShot(0, ...)` |
