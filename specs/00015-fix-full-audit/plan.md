# Plan: Full-Stack Audit Fixes Phase 2 (2026-06-10)

**Feature-Branch**: `00013-system-wide-bug-hunting-audit`  
**Status**: Draft  

## Ziele
- OBJ4: Behebung der hohen VRAM/GPU-Thread-Leaks, Migrations-Atomicity und Thread-Sicherheit.
- OBJ5: Behebung von Stem/Audio/Beat-Detection-Fehlern.
- OBJ6: Behebung der Concat-GOP-Ausrichtung und FFmpeg-Pfad-Auflösungen.
- OBJ7: Behebung der WPF Chat-History, Reentry-Gates und SSE-Verkabelungen.

## Vorgeschlagene Änderungen

### Z-CORE (Hardware / VRAM / State)
#### [MODIFY] [backend/dependencies.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/dependencies.py)
- In `with_gpu_task` fangen wir `asyncio.CancelledError` explizit ab und stellen sicher, dass das Modell storniert wird, falls der Thread abgebrochen wird.
- Verhindere Zombie-GPU-Threads bei Timeout: `asyncio.to_thread` kann physisch nicht abgebrochen werden, aber wir können im Fall eines Timeouts oder einer Cancellation verhindern, dass der Lock vorzeitig freigegeben wird, ODER wir entladen das Modell physisch, um die GPU wieder in einen sauberen Zustand zu bringen.
- Da wir den CPU-Thread nicht killen können, halten wir den Lock, bis der Thread wirklich beendet ist, oder wir implementieren ein robustes Cancellation-Handling. Wenn ein Timeout auftritt, sollte der Lock erst freigegeben werden, wenn der Hintergrund-Thread seine Ausführung tatsächlich beendet hat (d.h. wir warten mit `join` oder indem wir das Thread-Objekt überwachen, bevor wir den Lock freigeben). Das verhindert parallele Zugriffe auf die GPU, während der Zombie noch läuft!
- Genauer gesagt: Wir können das `asyncio.to_thread` Ergebnis im `finally`-Block mit `await` abwarten, falls wir abgebrochen werden oder ein Timeout auftritt, ODER wir blockieren weitere GPU-Tasks, bis der Thread fertig ist.
  Moment, wenn wir im `finally` auf den Thread warten, blockieren wir die gesamte App? Nein, nur diese eine Route, aber der `gpu_lock` bleibt belegt. Das ist genau das, was wir wollen: Keine neue GPU-Task darf laufen, solange die alte noch auf der GPU rechnet!
  Also: Wenn `asyncio.TimeoutError` oder `asyncio.CancelledError` auftritt, warten wir im `finally`-Block via `await thread_task`, um den Lock zu halten, bis der Thread fertig ist.
  Lass uns das entwerfen:
  ```python
  # dependencies.py
  task = asyncio.to_thread(func, *args, **kwargs)
  try:
      result = await asyncio.wait_for(task, timeout=timeout_seconds)
      success = True
      return result
  finally:
      # Wenn die Task abgebrochen wurde oder Timeout auftrat, läuft der Thread weiter.
      # Wir warten darauf, damit der gpu_lock nicht vorzeitig freigegeben wird.
      if not task.done():
          try:
              await task
          except Exception:
              pass
  ```
  Das ist extrem elegant und einfach! Es verhindert, dass der `gpu_lock` freigegeben wird, während der Thread noch auf der GPU rechnet.

#### [MODIFY] [src/pb_studio/core/vram_budget_manager.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/vram_budget_manager.py)
- In `_evict_for_space` und `evict_all`: Wenn ein `unload_callback` fehlschlägt, machen wir ein Rollback des Accountings (setzen `is_loaded = True` und addieren das VRAM-Budget wieder zu `self._committed_mb`).

#### [MODIFY] [src/pb_studio/core/system_monitor.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/system_monitor.py)
- Definiere `self._lhm_lock = threading.Lock()` in `__init__`.
- Schütze alle `hardware.Update()` und `Sensors`-Iterationen in `_collect_lhm_stats` mit diesem Lock.

### Z-DATA (Datenintegrität)
#### [MODIFY] [src/pb_studio/storage/migration_runner.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/migration_runner.py)
- Implementiere `split_sql_statements(sql: str) -> list[str]` zur robusten Zerlegung von SQL-Skripten.
- Führe in `migrate` die Statements einzeln mit `conn.execute` innerhalb der Transaktion (`BEGIN` / `COMMIT`) aus, anstatt `conn.executescript(sql)`.

#### [MODIFY] [src/pb_studio/storage/embedding_repository.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_repository.py)
- Importiere `split_sql_statements` aus `migration_runner`.
- Ändere `_migrate_with_vec` so ab, dass die Statements einzeln innerhalb einer Transaktion ausgeführt werden.

### Z-AUDIO (Audio-Analyse)
#### [MODIFY] [backend/routers/audio_router.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/audio_router.py)
- Falls `stems_paths` als JSON-String übermittelt wird, parse ihn robust zu einem Dictionary oder einer Liste, um HTTP 500 zu vermeiden.

### Z-UI-VM & Z-UI-VIEWS (WPF)
#### [MODIFY] [PBStudio.UI/ViewModels/ChatViewModel.cs](file:///C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI/ViewModels/ChatViewModel.cs)
- Ersetze `.Take(40)` durch `.TakeLast(40)`, damit die neuesten 40 Nachrichten an das Backend gesendet werden.

## Verifikationsplan
1. Führe Backend-Testsuite aus (`test.bat`).
2. Führe WPF Build aus (`build.ps1`).
