---
name: Python Backend Expert
description: Expert guidelines for Python backend development in PB Studio, focusing on async patterns, error handling, and type safety.
---

# Python Backend Expert Skill

## Core Principles
- **Python Version:** 3.10+ (Use Union types `|`, strict type hinting).
- **Architecture:** Modular, Service-oriented.
- **AsyncIO:** strictly for I/O bound tasks; use Threads/Processes for CPU bound AI tasks.

## 1. Code Standards
### Type Hinting
Every function signature MUST have type hints.
```python
def process_data(data: dict[str, Any], timeout: int = 30) -> list[ResultObject]:
    ...
```

### Docstrings
Use Google-style docstrings for complex logic.
```python
def complex_algorithm(param1: int) -> bool:
    """Calculates the metric based on...

    Args:
        param1: The input parameter.

    Returns:
        True if successful, False otherwise.
    """
    ...
```

## 2. Asynchronous Patterns
PB Studio uses a mix of AsyncIO (for network/file I/O) and QThread (for GUI-blocking work).
- **Rule:** Do NOT mix `asyncio.run()` inside a running event loop.
- **Rule:** Use `QThread` or `QRunnable` for long-running AI inference to keep the GUI responsive.

## 3. Error Handling Stratagems
**NEVER** swallow exceptions without logging.
```python
import logging
logger = logging.getLogger(__name__)

try:
    dangerous_operation()
except FileNotFoundError:
    logger.warning("File missing, using default...")
    use_default()
except Exception as e:
    logger.error(f"Critical failure in operation: {e}", exc_info=True)
    raise  # Re-raise if the app state is invalid
```

## 4. Path & File Handling
- Use `pathlib.Path` exclusively. No string manipulation for paths.
- **Cross-Platform:** Always assumes Windows paths but use `/` internally or `Path.joinpath`.
```python
from pathlib import Path
base_dir = Path(__file__).parent / "data"
```
