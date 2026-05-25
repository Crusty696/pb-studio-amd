# Plan: Critical System Hardening & Memory/VRAM Optimization

**Feature-Branch**: `00011-critical-system-hardening`
**Status**: Approved (Autopilot-Session)

## Ziele
- OBJ1: Decouple `StemSeparator` VRAM tracking via central `VRAMBudgetManager` to prevent DirectML OOM.
- OBJ2: Rewrite `SubtrackDetector` chroma processing with incremental chunking to avoid RAM spikes on large mix imports.

## Vorgeschlagene Änderungen

### Z-CORE (Hardware- und Speicher-Härtung)
#### [MODIFY] [separator.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/audio/separator.py)
- Binde `VRAMBudgetManager` (`get_vram_manager()`) ein.
- Vor Separation: Reserviere VRAM per `reserve(model_id, force=True)`.
- Nach Modellladen: Bestätige Budget mit `commit(model_id)`.
- Im `finally`-Block und in `unload()`: Gebe Budget mit `release(model_id)` frei.

### Z-AUDIO (Audio-Pipeline RAM-Härtung)
#### [MODIFY] [subtrack_detector.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/audio/subtrack_detector.py)
- Stelle `_foote_novelty` chroma Berechnung auf 5-Minuten-Chunks (300 Sekunden) um, um OOMs bei stundenlangen Audio-Dateien zu verhindern.
- Behandle unvollständige Ränder am Dateiende sauber durch Mergen in den vorletzten Chunk.

## Verifikationsplan
1. Führe `pytest Tests/test_separator.py` aus.
2. Führe `pytest Tests/test_subtrack_detector.py` aus.
3. Führe globale Backend-Tests zur Regressionssicherung aus.
