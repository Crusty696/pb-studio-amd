# Service Architecture Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Architektur", "Service", "Module", "Plugin", "Bereiche"
- "Dependency Injection", "Singleton", "Factory"
- Arbeit an Modul-Struktur, Cross-Modul Kommunikation
- Fragen zu Code-Organisation, Coupling, Cohesion

## Cross-References
- → `python-backend.md` (Coding Patterns)
- → `gui-framework.md` (Frontend-Backend Trennung)
- → `data-persistence.md` (Repository Pattern)
- → `generic-workflow.md` (Projektstruktur)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Decoupling** | GUI importiert Backend, NIEMALS umgekehrt |
| **Signals** | PyQtSignals oder typisierte Callbacks |
| **Task Queue** | Alle Background-Arbeit über zentrale Queue |

---

## 1. Projekt-Struktur (Bereiche-Konzept)

```
src/pb_studio/
├── __init__.py
├── main.py                    # Entry Point
│
├── core/                      # Kern-Module (Framework)
│   ├── __init__.py
│   ├── config.py             # Konfiguration
│   ├── logging_setup.py      # Logging
│   ├── exceptions.py         # Custom Exceptions
│   └── types.py              # Shared Type Definitions
│
├── data/                      # Datenschicht
│   ├── __init__.py
│   ├── database_core.py      # SQLite Singleton
│   ├── repositories/         # Repository Pattern
│   │   ├── project_repo.py
│   │   └── media_repo.py
│   └── vector_store.py       # FAISS
│
├── services/                  # Business Logic
│   ├── __init__.py
│   ├── task_manager.py       # Zentrale Task Queue
│   ├── project_service.py    # Projekt-Operationen
│   └── analysis_service.py   # Analyse-Koordination
│
├── ai/                        # AI/ML Module
│   ├── __init__.py
│   ├── model_manager.py      # Model Loading
│   ├── inference/
│   │   ├── clip_inference.py
│   │   └── demucs_inference.py
│   └── embeddings.py         # Embedding Generation
│
├── Bereiche/                  # Feature-Module (Plugins)
│   ├── Audio/
│   │   ├── __init__.py
│   │   ├── service.py        # AudioService
│   │   ├── processor.py      # Audio Processing
│   │   └── widgets/          # Audio-spezifische Widgets
│   │
│   ├── Video/
│   │   ├── __init__.py
│   │   ├── service.py        # VideoService
│   │   ├── processor.py
│   │   └── widgets/
│   │
│   └── Search/
│       ├── __init__.py
│       ├── service.py        # SearchService
│       └── widgets/
│
└── gui/                       # UI Layer
    ├── __init__.py
    ├── main_window.py        # Hauptfenster
    ├── styles/               # QSS Stylesheets
    ├── widgets/              # Shared Widgets
    │   ├── progress_widget.py
    │   └── file_browser.py
    └── dialogs/              # Dialoge
        ├── settings_dialog.py
        └── about_dialog.py
```

---

## 2. Dependency Flow (STRIKT einhalten)

```
                    ┌─────────────────┐
                    │      GUI        │
                    │  (gui/*.py)     │
                    └────────┬────────┘
                             │
                             │ imports
                             ▼
                    ┌─────────────────┐
                    │    Services     │
                    │ (services/*.py) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │  Bereiche   │ │     AI      │ │    Data     │
     │  (Plugins)  │ │  (ai/*.py)  │ │ (data/*.py) │
     └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │      Core       │
                    │  (core/*.py)    │
                    └─────────────────┘

❌ VERBOTEN:
- Data → GUI
- Core → Services
- AI → GUI
- Bereiche → GUI (direkt)
```

---

## 3. Service Pattern

```python
from abc import ABC, abstractmethod
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass
import logging

T = TypeVar('T')
logger = logging.getLogger(__name__)

# Service Interface
class ServiceProtocol(Protocol):
    """Basis-Interface für alle Services."""
    
    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
    @property
    def is_ready(self) -> bool: ...

# Base Service Implementation
class BaseService(ABC):
    """Abstrakte Basis-Klasse für Services."""
    
    def __init__(self):
        self._initialized = False
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialisiert den Service."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Beendet den Service sauber."""
        pass
    
    @property
    def is_ready(self) -> bool:
        return self._initialized
    
    def _ensure_initialized(self):
        """Prüft ob Service initialisiert ist."""
        if not self._initialized:
            raise RuntimeError(f"{self.__class__.__name__} not initialized")

# Concrete Service Example
@dataclass
class AudioAnalysisResult:
    bpm: float
    beats: list[float]
    duration: float

class AudioService(BaseService):
    """Service für Audio-Operationen."""
    
    def __init__(
        self,
        task_manager: 'TaskManager',
        model_manager: 'ModelManager'
    ):
        super().__init__()
        self.task_manager = task_manager
        self.model_manager = model_manager
        self._processor = None
    
    def initialize(self) -> None:
        from .processor import AudioProcessor
        self._processor = AudioProcessor()
        self._initialized = True
        self._logger.info("AudioService initialized")
    
    def shutdown(self) -> None:
        self._processor = None
        self._initialized = False
        self._logger.info("AudioService shutdown")
    
    def analyze_file(
        self,
        file_path: Path,
        callback: Callable[[AudioAnalysisResult], None] = None
    ) -> str:
        """Startet Audio-Analyse als Background Task."""
        self._ensure_initialized()
        
        task = AudioAnalysisTask(
            file_path=file_path,
            processor=self._processor,
            callback=callback
        )
        
        return self.task_manager.submit(task)
    
    def get_supported_formats(self) -> list[str]:
        """Gibt unterstützte Audio-Formate zurück."""
        return [".mp3", ".wav", ".flac", ".ogg", ".m4a"]
```

---

## 4. Task Manager (Zentrale Queue)

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any, Optional
from queue import PriorityQueue
import threading
import uuid
from PyQt6.QtCore import QObject, pyqtSignal

class TaskPriority(Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0

class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass
class TaskResult:
    success: bool
    data: Any = None
    error: str = None

@dataclass(order=True)
class Task:
    priority: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    name: str = field(default="", compare=False)
    func: Callable = field(default=None, compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    callback: Optional[Callable[[TaskResult], None]] = field(default=None, compare=False)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)

class TaskManager(QObject):
    """Zentrale Task Queue mit Concurrency Control."""
    
    # Signals für UI-Updates
    task_started = pyqtSignal(str, str)      # task_id, task_name
    task_progress = pyqtSignal(str, int)     # task_id, percent
    task_completed = pyqtSignal(str, object) # task_id, result
    task_failed = pyqtSignal(str, str)       # task_id, error
    
    def __init__(
        self,
        max_concurrent: int = 2,
        max_ai_tasks: int = 1
    ):
        super().__init__()
        
        self.max_concurrent = max_concurrent
        self.max_ai_tasks = max_ai_tasks
        
        self._queue: PriorityQueue[Task] = PriorityQueue()
        self._running: dict[str, Task] = {}
        self._completed: dict[str, TaskResult] = {}
        
        self._lock = threading.Lock()
        self._shutdown = False
        
        # Worker Threads
        self._workers: list[threading.Thread] = []
        self._start_workers()
    
    def _start_workers(self):
        """Startet Worker Threads."""
        for i in range(self.max_concurrent):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
    
    def _worker_loop(self):
        """Worker Thread Loop."""
        while not self._shutdown:
            try:
                task = self._queue.get(timeout=1.0)
                self._execute_task(task)
            except:
                continue
    
    def _execute_task(self, task: Task):
        """Führt einen Task aus."""
        with self._lock:
            task.status = TaskStatus.RUNNING
            self._running[task.id] = task
        
        self.task_started.emit(task.id, task.name)
        
        try:
            result_data = task.func(*task.args, **task.kwargs)
            result = TaskResult(success=True, data=result_data)
            task.status = TaskStatus.COMPLETED
            
            self.task_completed.emit(task.id, result)
            
        except Exception as e:
            result = TaskResult(success=False, error=str(e))
            task.status = TaskStatus.FAILED
            
            logger.error(f"Task {task.id} failed: {e}", exc_info=True)
            self.task_failed.emit(task.id, str(e))
        
        finally:
            with self._lock:
                del self._running[task.id]
                self._completed[task.id] = result
            
            if task.callback:
                try:
                    task.callback(result)
                except Exception as e:
                    logger.error(f"Task callback failed: {e}")
    
    def submit(
        self,
        func: Callable,
        *args,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        callback: Callable[[TaskResult], None] = None,
        **kwargs
    ) -> str:
        """Submittet neuen Task."""
        task = Task(
            priority=priority.value,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback
        )
        
        self._queue.put(task)
        logger.debug(f"Task submitted: {task.id} ({task.name})")
        
        return task.id
    
    def cancel(self, task_id: str) -> bool:
        """Markiert Task als cancelled (wenn noch pending)."""
        # Implementierung...
        pass
    
    def get_status(self, task_id: str) -> TaskStatus:
        """Gibt Task-Status zurück."""
        with self._lock:
            if task_id in self._running:
                return TaskStatus.RUNNING
            if task_id in self._completed:
                return self._completed[task_id]
        return TaskStatus.PENDING
    
    def shutdown(self, wait: bool = True):
        """Beendet TaskManager."""
        self._shutdown = True
        
        if wait:
            for worker in self._workers:
                worker.join(timeout=5.0)
```

---

## 5. Dependency Injection Container

```python
from typing import TypeVar, Type, Callable, Any
from dataclasses import dataclass
import inspect

T = TypeVar('T')

@dataclass
class ServiceRegistration:
    service_type: Type
    factory: Callable[..., Any]
    singleton: bool
    instance: Any = None

class DIContainer:
    """Einfacher Dependency Injection Container."""
    
    def __init__(self):
        self._registrations: dict[Type, ServiceRegistration] = {}
    
    def register(
        self,
        service_type: Type[T],
        implementation: Type[T] = None,
        factory: Callable[..., T] = None,
        singleton: bool = True
    ):
        """Registriert einen Service."""
        if implementation is None and factory is None:
            implementation = service_type
        
        if factory is None:
            factory = implementation
        
        self._registrations[service_type] = ServiceRegistration(
            service_type=service_type,
            factory=factory,
            singleton=singleton
        )
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolved einen Service mit Dependencies."""
        if service_type not in self._registrations:
            raise KeyError(f"Service not registered: {service_type}")
        
        reg = self._registrations[service_type]
        
        # Singleton: Existierende Instanz zurückgeben
        if reg.singleton and reg.instance is not None:
            return reg.instance
        
        # Dependencies auflösen
        if callable(reg.factory):
            sig = inspect.signature(reg.factory)
            deps = {}
            
            for param_name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    dep_type = param.annotation
                    if dep_type in self._registrations:
                        deps[param_name] = self.resolve(dep_type)
            
            instance = reg.factory(**deps)
        else:
            instance = reg.factory
        
        # Singleton speichern
        if reg.singleton:
            reg.instance = instance
        
        return instance

# Verwendung
container = DIContainer()

# Registrierungen
container.register(DatabaseCore, singleton=True)
container.register(TaskManager, singleton=True)
container.register(ModelManager, singleton=True)
container.register(AudioService)
container.register(VideoService)

# Auflösung
audio_service = container.resolve(AudioService)
```

---

## 6. Event Bus (Loose Coupling)

```python
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum, auto
import weakref

class EventType(Enum):
    # Project Events
    PROJECT_CREATED = auto()
    PROJECT_OPENED = auto()
    PROJECT_CLOSED = auto()
    
    # Media Events
    MEDIA_IMPORTED = auto()
    MEDIA_ANALYZED = auto()
    MEDIA_DELETED = auto()
    
    # Processing Events
    PROCESSING_STARTED = auto()
    PROCESSING_PROGRESS = auto()
    PROCESSING_COMPLETED = auto()
    PROCESSING_FAILED = auto()

@dataclass
class Event:
    type: EventType
    data: dict[str, Any]
    source: str = ""

class EventBus:
    """Zentraler Event Bus für loose Coupling."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: dict[EventType, list] = {}
        return cls._instance
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ):
        """Subscribt auf Event-Typ."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        # WeakRef um Memory Leaks zu vermeiden
        self._subscribers[event_type].append(weakref.ref(handler))
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ):
        """Unsubscribt von Event-Typ."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                ref for ref in self._subscribers[event_type]
                if ref() is not None and ref() != handler
            ]
    
    def publish(self, event: Event):
        """Publisht Event an alle Subscriber."""
        if event.type not in self._subscribers:
            return
        
        # Cleanup dead refs
        live_refs = []
        for ref in self._subscribers[event.type]:
            handler = ref()
            if handler is not None:
                live_refs.append(ref)
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
        
        self._subscribers[event.type] = live_refs

# Verwendung
event_bus = EventBus()

# In AudioService
def on_analysis_complete(result):
    event_bus.publish(Event(
        type=EventType.MEDIA_ANALYZED,
        data={"file": str(file_path), "result": result},
        source="AudioService"
    ))

# In GUI
def setup_event_handlers(self):
    event_bus.subscribe(EventType.MEDIA_ANALYZED, self._on_media_analyzed)

def _on_media_analyzed(self, event: Event):
    # UI Update
    self.refresh_media_list()
```

---

## 7. Startup Sequence

```python
class Application:
    """Haupt-Anwendungsklasse mit definierter Startup-Sequenz."""
    
    def __init__(self):
        self.container = DIContainer()
        self.services: list[BaseService] = []
    
    def run(self):
        """Startet die Anwendung."""
        try:
            self._phase1_bootstrap()
            self._phase2_core_services()
            self._phase3_show_splash()
            self._phase4_load_services()
            self._phase5_main_window()
            
            return self._run_event_loop()
            
        except Exception as e:
            logger.critical(f"Startup failed: {e}", exc_info=True)
            self._show_error_dialog(str(e))
            return 1
    
    def _phase1_bootstrap(self):
        """Phase 1: Umgebung prüfen."""
        logger.info("Phase 1: Bootstrap")
        
        # Python Version
        import sys
        if sys.version_info < (3, 10):
            raise RuntimeError("Python 3.10+ required")
        
        # Verzeichnisse erstellen
        for dir_name in ["logs", "data", "models", "output"]:
            Path(dir_name).mkdir(exist_ok=True)
        
        # Logging Setup
        setup_logging()
    
    def _phase2_core_services(self):
        """Phase 2: Core Services registrieren."""
        logger.info("Phase 2: Core Services")
        
        self.container.register(DatabaseCore, singleton=True)
        self.container.register(TaskManager, singleton=True)
        self.container.register(EventBus, singleton=True)
    
    def _phase3_show_splash(self):
        """Phase 3: Splash Screen zeigen."""
        logger.info("Phase 3: Splash Screen")
        
        self.app = QApplication(sys.argv)
        self.splash = SplashScreen()
        self.splash.show()
        self.app.processEvents()
    
    def _phase4_load_services(self):
        """Phase 4: Feature Services laden."""
        logger.info("Phase 4: Feature Services")
        
        services_to_load = [
            ("Models", ModelManager),
            ("Audio", AudioService),
            ("Video", VideoService),
            ("Search", SearchService)
        ]
        
        for i, (name, service_class) in enumerate(services_to_load):
            progress = int((i / len(services_to_load)) * 100)
            self.splash.set_progress(progress, f"Loading {name}...")
            
            self.container.register(service_class, singleton=True)
            service = self.container.resolve(service_class)
            service.initialize()
            self.services.append(service)
    
    def _phase5_main_window(self):
        """Phase 5: Main Window erstellen."""
        logger.info("Phase 5: Main Window")
        
        self.splash.set_progress(100, "Starting...")
        
        self.main_window = MainWindow(self.container)
        self.main_window.show()
        
        self.splash.finish(self.main_window)
    
    def _run_event_loop(self) -> int:
        """Führt Qt Event Loop aus."""
        return self.app.exec()
    
    def shutdown(self):
        """Fährt Anwendung sauber herunter."""
        logger.info("Shutting down...")
        
        for service in reversed(self.services):
            try:
                service.shutdown()
            except Exception as e:
                logger.error(f"Service shutdown error: {e}")
        
        logger.info("Shutdown complete")
```

---

## Checkliste: Service Architecture

### Dependency Flow
- [ ] GUI importiert nur Services (nicht Data/AI direkt)?
- [ ] Keine zirkulären Imports?
- [ ] Core hat keine Abhängigkeiten nach oben?

### Services
- [ ] Jeder Service hat initialize/shutdown?
- [ ] Services nutzen TaskManager für Background-Ops?
- [ ] Loose Coupling via EventBus?

### Startup
- [ ] Klare Phasen-Trennung?
- [ ] Splash für lange Initialisierung?
- [ ] Error Handling für jede Phase?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| Circular Import | Falsche Dependency-Richtung | Imports umstrukturieren |
| Service not ready | initialize() nicht aufgerufen | Startup Sequence prüfen |
| UI Freeze | Service blockiert Main Thread | TaskManager verwenden |
| Memory Leak | Event-Handler nicht unsubscribed | WeakRef oder explizit cleanup |
