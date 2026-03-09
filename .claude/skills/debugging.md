# Debugging & Profiling Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Error", "Bug", "Crash", "Fehler", "Debug", "Traceback", "Exception"
- "Langsam", "Performance", "Memory", "Leak", "Profiling"
- Analyse von Log-Dateien oder Stack Traces

## Cross-References
- → `python-backend.md` (Error Handling Patterns)
- → `gui-framework.md` (UI Freezes diagnostizieren)
- → `ai-inference.md` (GPU/VRAM Probleme)
- → `hardware-control.md` (System-Metriken)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Evidence-Based** | Nicht raten - Logs analysieren |
| **Reproducibility** | Ohne Reproduktion keine sichere Lösung |
| **Isolation** | Problem eingrenzen durch Ausschlussverfahren |

---

## 1. Strukturierte Log-Analyse

```python
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from collections import Counter

@dataclass
class LogEntry:
    timestamp: str
    level: str
    module: str
    message: str
    line_number: int

class LogAnalyzer:
    """Analysiert Log-Dateien strukturiert."""
    
    # Standard Python Logging Format
    LOG_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+'
        r'(\w+)\s+-\s+(\w+)\s+-\s+(.+)'
    )
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.entries: list[LogEntry] = []
        self._parse()
    
    def _parse(self):
        """Parsed Log-Datei in strukturierte Einträge."""
        if not self.log_path.exists():
            return
        
        with open(self.log_path, encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                match = self.LOG_PATTERN.match(line.strip())
                if match:
                    self.entries.append(LogEntry(
                        timestamp=match.group(1),
                        level=match.group(2),
                        module=match.group(3),
                        message=match.group(4),
                        line_number=i
                    ))
    
    def get_errors(self) -> list[LogEntry]:
        """Gibt alle ERROR und CRITICAL Einträge zurück."""
        return [e for e in self.entries if e.level in ('ERROR', 'CRITICAL')]
    
    def get_warnings(self) -> list[LogEntry]:
        """Gibt alle WARNING Einträge zurück."""
        return [e for e in self.entries if e.level == 'WARNING']
    
    def get_by_module(self, module: str) -> list[LogEntry]:
        """Filtert nach Modul."""
        return [e for e in self.entries if module.lower() in e.module.lower()]
    
    def get_error_summary(self) -> dict:
        """Erstellt Fehler-Zusammenfassung."""
        errors = self.get_errors()
        
        # Gruppiere ähnliche Fehler
        error_types = Counter()
        for e in errors:
            # Extrahiere Exception-Typ falls vorhanden
            exc_match = re.search(r'(\w+Error|\w+Exception)', e.message)
            if exc_match:
                error_types[exc_match.group(1)] += 1
            else:
                error_types['Unknown'] += 1
        
        return {
            "total_errors": len(errors),
            "error_types": dict(error_types),
            "first_error": errors[0] if errors else None,
            "last_error": errors[-1] if errors else None
        }
    
    def search(self, pattern: str) -> list[LogEntry]:
        """Sucht nach Pattern in Messages."""
        regex = re.compile(pattern, re.IGNORECASE)
        return [e for e in self.entries if regex.search(e.message)]

def analyze_logs(log_dir: Path = Path("logs")) -> dict:
    """Analysiert alle Logs im Verzeichnis."""
    results = {}
    
    for log_file in log_dir.glob("*.log"):
        analyzer = LogAnalyzer(log_file)
        results[log_file.name] = analyzer.get_error_summary()
    
    return results
```

---

## 2. Stack Trace Parser

```python
import traceback
from dataclasses import dataclass

@dataclass
class StackFrame:
    file: str
    line: int
    function: str
    code: str

def parse_traceback(tb_string: str) -> list[StackFrame]:
    """Parsed einen Traceback-String in strukturierte Frames."""
    frames = []
    
    # Pattern für Traceback-Zeilen
    frame_pattern = re.compile(
        r'File "(.+)", line (\d+), in (\w+)\n\s+(.+)'
    )
    
    for match in frame_pattern.finditer(tb_string):
        frames.append(StackFrame(
            file=match.group(1),
            line=int(match.group(2)),
            function=match.group(3),
            code=match.group(4).strip()
        ))
    
    return frames

def get_root_cause(tb_string: str) -> Optional[dict]:
    """Extrahiert die Ursache aus einem Traceback."""
    frames = parse_traceback(tb_string)
    
    if not frames:
        return None
    
    # Letzter Frame ist meist der relevante
    last_frame = frames[-1]
    
    # Exception-Typ und Message extrahieren
    exc_match = re.search(
        r'(\w+Error|\w+Exception):\s*(.+)$',
        tb_string,
        re.MULTILINE
    )
    
    return {
        "location": f"{last_frame.file}:{last_frame.line}",
        "function": last_frame.function,
        "code": last_frame.code,
        "exception_type": exc_match.group(1) if exc_match else "Unknown",
        "exception_message": exc_match.group(2) if exc_match else "",
        "all_frames": frames
    }
```

---

## 3. Performance Profiling

```python
import time
import functools
import cProfile
import pstats
import io
from contextlib import contextmanager

# Simple Timer Decorator
def profile_time(func):
    """Decorator zum Messen der Ausführungszeit."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        logger.debug(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper

# Context Manager für Profiling
@contextmanager
def profile_block(name: str):
    """Context Manager für Block-Profiling."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info(f"[PROFILE] {name}: {elapsed:.4f}s")

# Detailliertes cProfile
def profile_function(func, *args, **kwargs) -> tuple:
    """Führt Funktion mit cProfile aus."""
    profiler = cProfile.Profile()
    
    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()
    
    # Stats als String
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20
    
    return result, stream.getvalue()

# Memory Profiling (benötigt memory_profiler)
def get_memory_usage() -> dict:
    """Gibt aktuellen Memory-Verbrauch zurück."""
    import psutil
    process = psutil.Process()
    mem_info = process.memory_info()
    
    return {
        "rss_mb": mem_info.rss / (1024 * 1024),
        "vms_mb": mem_info.vms / (1024 * 1024),
        "percent": process.memory_percent()
    }
```

---

## 4. GPU/VRAM Debugging (AMD)

```python
def diagnose_gpu() -> dict:
    """Diagnostiziert GPU-Status für ONNX/DirectML."""
    import onnxruntime as ort
    
    result = {
        "available_providers": ort.get_available_providers(),
        "device": ort.get_device(),
        "issues": []
    }
    
    # DirectML Check (AMD)
    if 'DmlExecutionProvider' not in result["available_providers"]:
        result["issues"].append(
            "DirectML nicht verfügbar - pip install onnxruntime-directml"
        )
    
    # Test Session
    try:
        test_session = ort.InferenceSession(
            bytes(16),  # Dummy
            providers=['CPUExecutionProvider']
        )
        result["onnx_functional"] = True
    except Exception as e:
        result["onnx_functional"] = False
        result["issues"].append(f"ONNX Runtime Fehler: {e}")
    
    return result

def check_vram_pressure() -> dict:
    """Prüft VRAM-Auslastung (AMD via LibreHardwareMonitor)."""
    
    # AMD VRAM via LibreHardwareMonitor
    try:
        import requests
        response = requests.get("http://localhost:8085/data.json", timeout=2)
        if response.status_code == 200:
            # Parse LHM data for AMD GPU metrics
            return {
                "vendor": "AMD",
                "source": "LibreHardwareMonitor",
                "note": "Verwende LHM für detaillierte AMD VRAM-Infos"
            }
    except:
        pass
    
    return {
        "vendor": "AMD",
        "vram_used_mb": None,
        "vram_total_mb": None,
        "note": "LibreHardwareMonitor für VRAM-Monitoring empfohlen"
    }
```

---

## 5. UI Freeze Detection

```python
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import time

class FreezeDetector(QThread):
    """Erkennt UI-Freezes durch Heartbeat-Monitoring."""
    
    freeze_detected = pyqtSignal(float)  # Dauer in Sekunden
    
    def __init__(self, threshold_ms: int = 500):
        super().__init__()
        self.threshold_ms = threshold_ms
        self.last_heartbeat = time.time()
        self.running = True
    
    def heartbeat(self):
        """Vom Main Thread regelmäßig aufrufen."""
        self.last_heartbeat = time.time()
    
    def run(self):
        """Monitor Thread."""
        while self.running:
            elapsed = time.time() - self.last_heartbeat
            if elapsed > self.threshold_ms / 1000:
                self.freeze_detected.emit(elapsed)
                logger.warning(f"UI Freeze erkannt: {elapsed:.2f}s")
            time.sleep(0.1)
    
    def stop(self):
        self.running = False

# Verwendung im MainWindow:
# self.freeze_detector = FreezeDetector()
# self.heartbeat_timer = QTimer()
# self.heartbeat_timer.timeout.connect(self.freeze_detector.heartbeat)
# self.heartbeat_timer.start(100)  # 100ms Heartbeat
# self.freeze_detector.start()
```

---

## 6. Debug Helper Functions

```python
def dump_object_state(obj, max_depth: int = 2) -> dict:
    """Dumped Objekt-Zustand für Debugging."""
    def _dump(o, depth):
        if depth > max_depth:
            return f"<{type(o).__name__}>"
        
        if isinstance(o, (str, int, float, bool, type(None))):
            return o
        elif isinstance(o, (list, tuple)):
            return [_dump(i, depth + 1) for i in o[:10]]  # Max 10 Items
        elif isinstance(o, dict):
            return {k: _dump(v, depth + 1) for k, v in list(o.items())[:10]}
        elif hasattr(o, '__dict__'):
            return {k: _dump(v, depth + 1) for k, v in o.__dict__.items() if not k.startswith('_')}
        else:
            return f"<{type(o).__name__}>"
    
    return _dump(obj, 0)

def create_debug_report() -> dict:
    """Erstellt umfassenden Debug-Report."""
    import platform
    import sys
    
    return {
        "system": {
            "platform": platform.platform(),
            "python": sys.version,
            "cwd": str(Path.cwd())
        },
        "memory": get_memory_usage(),
        "gpu": diagnose_gpu(),
        "logs": analyze_logs(),
        "timestamp": datetime.now().isoformat()
    }
```

---

## Debugging Workflow

```
┌─────────────────────────────────────────────────────────┐
│                    PROBLEM ERKANNT                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  1. LOGS ANALYSIEREN                                     │
│     - analyze_logs() ausführen                          │
│     - get_error_summary() prüfen                        │
│     - Traceback parsen mit get_root_cause()             │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  2. REPRODUZIEREN                                        │
│     - Minimales Beispiel erstellen                      │
│     - Inputs/State dokumentieren                        │
│     - Zuverlässig wiederholbar machen                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  3. ISOLIEREN                                            │
│     - Binary Search durch Code                          │
│     - Komponenten einzeln testen                        │
│     - Dependencies prüfen                               │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  4. FIX IMPLEMENTIEREN                                   │
│     - Root Cause beheben (nicht Symptome)               │
│     - Regression Test hinzufügen                        │
│     - Dokumentieren warum                               │
└─────────────────────────────────────────────────────────┘
```

---

## Checkliste: Debugging

### Bei Errors
- [ ] Vollständigen Traceback gesichert?
- [ ] `get_root_cause()` analysiert?
- [ ] Ähnliche Fehler in Logs gesucht?
- [ ] Kann reproduziert werden?

### Bei Performance-Problemen
- [ ] `profile_block()` um verdächtige Stellen?
- [ ] Memory-Leak mit `get_memory_usage()` geprüft?
- [ ] GPU-Auslastung gecheckt (LHM)?
- [ ] UI-Thread blockiert?

### Bei Crashes
- [ ] Core Dump / Crash Report vorhanden?
- [ ] Letzte erfolgreiche Operation in Logs?
- [ ] System-Ressourcen zum Zeitpunkt?

---

## Häufige Fehler & Lösungen

| Symptom | Mögliche Ursache | Diagnose-Tool |
|---------|------------------|---------------|
| UI friert ein | Main Thread blockiert | `FreezeDetector` |
| Out of Memory | Memory Leak / große Dateien | `get_memory_usage()` |
| GPU Fehler | Falsche Provider / VRAM voll | `diagnose_gpu()` |
| Langsame Inference | CPU statt GPU | Session.get_providers() loggen |
| Sporadische Crashes | Race Condition | Threading-Logs analysieren |
