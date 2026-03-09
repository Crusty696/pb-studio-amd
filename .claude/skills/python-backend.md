# Python Backend Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- Python Code schreiben, debuggen, refactoren
- "Type Hints", "AsyncIO", "Error Handling", "Logging"
- Arbeit an `src/pb_studio/`, `*.py` Dateien
- Fragen zu Python Best Practices, Patterns

## Cross-References
- → `debugging.md` (Error Analysis, Profiling)
- → `gui-framework.md` (PyQt6 Integration)
- → `service-architecture.md` (Module Structure)
- → `ai-inference.md` (ONNX Integration)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Python 3.10+** | Union Types `|`, match-case, type hints |
| **Modular** | Service-oriented Architecture |
| **AsyncIO** | Für I/O-bound, Threads/Processes für CPU-bound |

---

## 1. Type Hints - PFLICHT

```python
from typing import Optional, Any, Callable, TypeVar
from collections.abc import Generator, Iterable
from pathlib import Path

T = TypeVar('T')

# ✅ Moderne Syntax (Python 3.10+)
def process_files(
    paths: list[Path],
    callback: Callable[[Path], None] | None = None,
    timeout: int = 30
) -> dict[str, Any]:
    """Verarbeitet Dateien mit optionalem Callback."""
    results: dict[str, Any] = {}
    
    for path in paths:
        result = process_single(path)
        results[str(path)] = result
        
        if callback:
            callback(path)
    
    return results

# ❌ Alte Syntax vermeiden
def old_style(paths: List[Path]) -> Dict[str, Any]:  # Deprecated
    pass

# Generics
def first_or_default(items: Iterable[T], default: T) -> T:
    """Gibt erstes Element oder Default zurück."""
    for item in items:
        return item
    return default

# Dataclasses mit Type Hints
from dataclasses import dataclass, field

@dataclass
class ProcessingResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
```

---

## 2. Error Handling - NIEMALS Silent Failures

```python
import logging
from typing import TypeVar, Callable
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# ❌ VERBOTEN - Silent Failure
def bad_error_handling():
    try:
        dangerous_operation()
    except:
        pass  # ← NIEMALS!

# ❌ VERBOTEN - Zu breites Exception
def also_bad():
    try:
        specific_operation()
    except Exception:
        return None  # ← Verliert Fehler-Info

# ✅ RICHTIG - Spezifisch und geloggt
def good_error_handling(file_path: Path) -> ProcessingResult:
    """Beispiel für korrektes Error Handling."""
    
    try:
        data = load_data(file_path)
        result = process_data(data)
        return ProcessingResult(success=True, message="OK", data=result)
        
    except FileNotFoundError:
        logger.warning(f"Datei nicht gefunden: {file_path}")
        return ProcessingResult(
            success=False,
            message=f"Datei nicht gefunden: {file_path}"
        )
        
    except PermissionError:
        logger.error(f"Keine Berechtigung: {file_path}")
        return ProcessingResult(
            success=False,
            message="Keine Leseberechtigung"
        )
        
    except ValueError as e:
        logger.error(f"Ungültige Daten in {file_path}: {e}")
        return ProcessingResult(
            success=False,
            message=f"Ungültige Daten: {e}"
        )
        
    except Exception as e:
        # Nur für unerwartete Fehler
        logger.exception(f"Unerwarteter Fehler bei {file_path}")
        raise  # Re-raise für kritische Fehler

# Decorator für Error Handling
def handle_errors(
    default_return: T = None,
    log_level: int = logging.ERROR,
    reraise: bool = False
) -> Callable:
    """Decorator für standardisiertes Error Handling."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    f"{func.__name__} failed: {e}",
                    exc_info=True
                )
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator

# Verwendung
@handle_errors(default_return=[], log_level=logging.WARNING)
def get_files(directory: Path) -> list[Path]:
    return list(directory.glob("*.mp3"))
```

---

## 3. Logging Setup

```python
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

def setup_logging(
    log_dir: Path = Path("logs"),
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """Konfiguriert Logging für die Anwendung."""
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Format
    detailed_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_format = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # File Handler (Rotating)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_format)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_format)
    
    # Error File Handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_format)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_handler)
    
    return root_logger

# Per-Module Logger
logger = logging.getLogger(__name__)

# Logging Best Practices
def example_function():
    logger.debug("Entering function with detailed state...")
    logger.info("Starting processing")
    
    try:
        result = do_something()
        logger.info(f"Processing complete: {result}")
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise
```

---

## 4. Path Handling - NUR pathlib

```python
from pathlib import Path
import os

# ❌ FALSCH - String-Manipulation
def bad_path_handling():
    path = "C:\\Users\\test" + "\\" + "file.txt"  # ← Plattform-spezifisch
    if os.path.exists(path):
        with open(path) as f:
            pass

# ✅ RICHTIG - pathlib
def good_path_handling():
    base = Path.home() / "Documents"
    file_path = base / "project" / "file.txt"
    
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
    
    # Relative Pfade
    relative = file_path.relative_to(base)
    
    # Glob
    for py_file in base.glob("**/*.py"):
        print(py_file)

# Path Utilities
def ensure_directory(path: Path) -> Path:
    """Stellt sicher dass Verzeichnis existiert."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def safe_filename(name: str) -> str:
    """Entfernt unsichere Zeichen aus Dateinamen."""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        name = name.replace(char, '_')
    return name

def get_unique_path(path: Path) -> Path:
    """Gibt eindeutigen Pfad zurück (fügt Nummer hinzu wenn existiert)."""
    if not path.exists():
        return path
    
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
```

---

## 5. AsyncIO Patterns

```python
import asyncio
from typing import TypeVar, Coroutine, Any
from concurrent.futures import ThreadPoolExecutor
import functools

T = TypeVar('T')

# Async File I/O
async def read_file_async(path: Path) -> str:
    """Liest Datei asynchron."""
    loop = asyncio.get_event_loop()
    
    def _read():
        return path.read_text(encoding='utf-8')
    
    return await loop.run_in_executor(None, _read)

# CPU-bound in Thread auslagern
async def run_cpu_bound(func: callable, *args, **kwargs) -> Any:
    """Führt CPU-intensive Funktion in Thread aus."""
    loop = asyncio.get_event_loop()
    
    partial_func = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, partial_func)

# Parallele Ausführung
async def process_files_parallel(
    paths: list[Path],
    processor: Coroutine,
    max_concurrent: int = 5
) -> list[Any]:
    """Verarbeitet Dateien parallel mit Limit."""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_process(path: Path):
        async with semaphore:
            return await processor(path)
    
    tasks = [limited_process(p) for p in paths]
    return await asyncio.gather(*tasks, return_exceptions=True)

# Timeout Wrapper
async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float
) -> T:
    """Führt Coroutine mit Timeout aus."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")
        raise

# WICHTIG: AsyncIO und PyQt6 mischen
# PyQt6 hat seinen eigenen Event Loop - nicht asyncio.run() verwenden!
# Stattdessen: qasync oder QThread für Background-Tasks
```

---

## 6. Dataclasses & Enums

```python
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Optional
import json

class ProcessingStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass
class Task:
    id: str
    name: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    progress: float = 0.0
    result: Optional[dict] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Konvertiert zu Dictionary (für JSON)."""
        data = asdict(self)
        data['status'] = self.status.name
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Erstellt aus Dictionary."""
        data['status'] = ProcessingStatus[data['status']]
        return cls(**data)
    
    def is_finished(self) -> bool:
        return self.status in (
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED
        )

# Frozen Dataclass (immutable)
@dataclass(frozen=True)
class AudioMetadata:
    duration_sec: float
    sample_rate: int
    channels: int
    format: str
```

---

## 7. Context Managers

```python
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator
import time

@contextmanager
def timer(name: str) -> Generator[None, None, None]:
    """Context Manager zum Zeitmessen."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.debug(f"{name}: {elapsed:.4f}s")

@contextmanager
def temporary_file(suffix: str = ".tmp") -> Generator[Path, None, None]:
    """Erstellt temporäre Datei die automatisch gelöscht wird."""
    import tempfile
    
    fd, path = tempfile.mkstemp(suffix=suffix)
    path = Path(path)
    
    try:
        os.close(fd)
        yield path
    finally:
        if path.exists():
            path.unlink()

@asynccontextmanager
async def async_lock(lock: asyncio.Lock, timeout: float = 10.0):
    """Async Lock mit Timeout."""
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        yield
    finally:
        lock.release()

# Verwendung
with timer("Processing"):
    result = heavy_operation()

with temporary_file(".wav") as temp_path:
    export_audio(data, temp_path)
    process_audio(temp_path)
# temp_path wird automatisch gelöscht
```

---

## 8. Dependency Injection

```python
from typing import Protocol, runtime_checkable

# Interface via Protocol
@runtime_checkable
class StorageProtocol(Protocol):
    def save(self, key: str, data: bytes) -> bool: ...
    def load(self, key: str) -> bytes | None: ...
    def delete(self, key: str) -> bool: ...

# Konkrete Implementierung
class FileStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, key: str, data: bytes) -> bool:
        path = self.base_dir / key
        path.write_bytes(data)
        return True
    
    def load(self, key: str) -> bytes | None:
        path = self.base_dir / key
        if path.exists():
            return path.read_bytes()
        return None
    
    def delete(self, key: str) -> bool:
        path = self.base_dir / key
        if path.exists():
            path.unlink()
            return True
        return False

# Service mit DI
class CacheService:
    def __init__(self, storage: StorageProtocol):
        self.storage = storage
    
    def cache(self, key: str, data: bytes):
        self.storage.save(f"cache_{key}", data)

# Verwendung
storage = FileStorage(Path("data/storage"))
cache = CacheService(storage)
```

---

## Checkliste: Python Backend

### Code Qualität
- [ ] Type Hints für alle Funktionen?
- [ ] Docstrings für öffentliche APIs?
- [ ] Keine bare `except:` Statements?
- [ ] Logging statt print()?

### Patterns
- [ ] pathlib statt os.path?
- [ ] Dataclasses für Datenstrukturen?
- [ ] Context Manager für Ressourcen?
- [ ] Dependency Injection wo sinnvoll?

### Performance
- [ ] AsyncIO für I/O-bound?
- [ ] Threads für CPU-bound?
- [ ] Keine blocking Calls im Event Loop?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `TypeError: unsupported operand` | Falsche Types | Type Hints + mypy |
| `UnicodeDecodeError` | Falsches Encoding | `encoding='utf-8'` explizit |
| `RecursionError` | Zirkuläre Imports | Import-Struktur überdenken |
| `AttributeError: None` | Ungeprüfter Return | Optional Type + Check |
| `asyncio.run() error` | Nested Event Loop | `nest_asyncio` oder umstrukturieren |
