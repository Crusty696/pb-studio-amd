# Architecture Decision Record: VRAM Management System

**Status:** Implemented
**Date:** 2026-02-04
**Author:** System Architect
**Components:** `vram_budget_manager.py`, `vram_arbiter.py`, `model_loader.py`

---

## Context

PB Studio AMD verwendet mehrere ML-Modelle, die VRAM auf der GPU belegen:

| Modell | VRAM (ca.) | Verwendung |
|--------|------------|------------|
| Moondream2 FP16 | 1.5-1.8 GB | Vision-Language Analysis |
| RAFT Optical Flow | 600-800 MB | Scene Detection |
| MDX-NET | 500-600 MB | Stem Separation |
| BeatNet | 150-200 MB | Beat Detection |

**Problem:** Ohne zentrale VRAM-Verwaltung kommt es zu:
- Out-of-Memory (OOM) Errors bei gleichzeitiger Nutzung
- Modelle bleiben geladen, obwohl nicht mehr benoetigt
- Keine Priorisierung (wichtige Modelle werden verdraengt)
- DirectML meldet VRAM verzoegert (reaktive Ueberwachung reicht nicht)

## Decision

Wir implementieren ein **dreistufiges VRAM-Management-System**:

### Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
│  (MoondreamAnalyzer, MotionAnalyzer, StemSeparator, etc.)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MODEL LOADER                              │
│  - Zentrale Schnittstelle fuer alle Model-Operationen          │
│  - Automatische VRAM-Reservierung vor Laden                    │
│  - DirectML Session Options (enable_mem_pattern = False)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VRAM BUDGET MANAGER                           │
│  - Singleton fuer globale VRAM-Verwaltung                      │
│  - Proaktives Budgeting (Reserve → Commit → Release)           │
│  - LRU + Priority Eviction Policy                              │
│  - Thread-safe Operations                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SYSTEM MONITOR                              │
│  - LibreHardwareMonitor Integration                            │
│  - Real-time GPU Stats (Load, Temp, VRAM)                      │
│  - Validierung der Budget-Tracking-Daten                       │
└─────────────────────────────────────────────────────────────────┘
```

### Allocation Flow

```
1. Model registriert sich beim BudgetManager
   → register_model(id, name, vram_mb, priority)

2. Vor dem Laden: Reservierung anfordern
   → reserve(id) → prueft can_fit(), evicted bei Bedarf

3. Nach erfolgreichem Laden: Commitment
   → commit(id) → reservation → committed

4. Bei Nutzung: Touch fuer LRU
   → touch_model(id) → aktualisiert last_used

5. Beim Entladen: Release
   → release(id) → VRAM freigeben
```

### Eviction Policy

```python
# Prioritaet (hoehere Zahl = niedriger Prioritaet = zuerst evicted)
CRITICAL = 1   # Nie evicten (aktive Verarbeitung)
HIGH = 2       # User-angefordert, aktiv genutzt
MEDIUM = 3     # Kuerzlich genutzt
LOW = 4        # Idle, kann evicted werden
BACKGROUND = 5 # Batch-Processing, zuerst evicten

# Eviction Reihenfolge:
# 1. Niedrigste Prioritaet zuerst (BACKGROUND → LOW → ...)
# 2. Bei gleicher Prioritaet: Least Recently Used
```

## Consequences

### Positive

1. **Keine OOM-Crashes mehr** - Proaktive Pruefung vor jedem Laden
2. **Automatisches Cleanup** - Ungenutzte Modelle werden evicted
3. **Priorisierung** - Wichtige Modelle bleiben geladen
4. **Thread-Safety** - Concurrent Model Access moeglich
5. **Debugging** - Vollstaendige VRAM-Statistiken verfuegbar

### Negative

1. **Overhead** - Jede Model-Operation braucht Manager-Calls
2. **Complexity** - Mehr Code zu warten
3. **False Positives** - Bei falschen VRAM-Schaetzungen

### Mitigations

- VRAM-Budgets sind konservativ geschaetzt (inkl. Overhead)
- Dual-Verification mit LHM-Sensor wenn verfuegbar
- Logging bei Diskrepanzen zwischen Budget und Sensor

## Usage Examples

### Direkter Model Loader

```python
from src.pb_studio.core import load_model, unload_model

# Laden mit automatischem VRAM-Management
session = load_model("moondream_fp16", force=True)

if session:
    # Verwenden
    result = session["encoder"].run(...)

# Entladen
unload_model("moondream_fp16")
```

### VRAMContext Manager

```python
from src.pb_studio.core import VRAMContext, get_vram_manager

manager = get_vram_manager()

with VRAMContext(manager, "custom_model", "My Model", 1000) as ctx:
    if ctx.reserved:
        model = load_my_model()
        ctx.set_unload_callback(model.unload)
        ctx.commit()
        # Model verwenden
# Automatisch released bei Error
```

### Statistiken

```python
from src.pb_studio.core import get_vram_manager

stats = get_vram_manager().get_stats()
print(f"Available: {stats['available_mb']}MB")
print(f"Loaded Models: {stats['models']}")
```

## Files

| Datei | Funktion |
|-------|----------|
| `core/vram_budget_manager.py` | Zentrale VRAM-Verwaltung |
| `core/vram_arbiter.py` | Legacy-Interface (nutzt BudgetManager) |
| `core/model_loader.py` | VRAM-aware Model Loading |
| `core/system_monitor.py` | GPU Monitoring (LHM) |

## DirectML-Specific Notes

**KRITISCH:** Alle ONNX Sessions MUESSEN mit diesen Options erstellt werden:

```python
session_options = ort.SessionOptions()
session_options.enable_mem_pattern = False  # MANDATORY!
session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
```

Ohne `enable_mem_pattern = False` produziert DirectML:
- Falsche Ergebnisse
- Crashes
- Memory Corruption

## Future Improvements

1. **Dynamic VRAM Estimation** - Measure actual usage after first load
2. **Memory Pressure Callbacks** - OS-level memory warnings
3. **Model Streaming** - Partial loading for large models
4. **Profiling Integration** - Track actual vs estimated VRAM
