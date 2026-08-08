# PB Studio — Bug-Fix Summary (2026-07-24)

Fixes für die verifizierten Critical/High-Befunde aus `pb_studio_bug_report.md`, plus die zwei verifizierten Mediums und die `workers/`-Deprecation. Alle Änderungen sind lokal (two-way door), berühren keine IRON RULE und kein DB-Schema.

## Was geändert wurde

| ID | Datei | Änderung | Verifikation |
|----|-------|----------|--------------|
| **C1** | `data/vector_store.py` | Ein einziger **coalescing Writer-Thread** statt `faiss.clone_index` + neuer Daemon-Thread pro `add_embedding`. Adds/Tombstones setzen nur ein Dirty-Flag; der Writer klont den *aktuellen* Zustand unter Lock, debounced (2 s), und schreibt atomar (`temp` + `os.replace`). „Latest-wins" ist dadurch inhärent. | **Live-Test bestanden**: 300 Adds → 2 Threads (statt ~300), On-Disk-Index = 300 (newest), keine `.tmp`-Leichen. |
| **H1** | `services/pacing_service.py` | `_finalize_cut_list` bekommt jetzt `duration_limit or total_duration` (Generierungs-Budget) statt der vollen Songlänge → kein Riesen-Endclip mehr bei Preview/Kurz-Renders. | Alle 7 Call-Sites + Methoden-Signatur geprüft. |
| **H2** | `video/engine.py` | `generate_from_timeline()` resettet `self.cancel_flag = False` beim Eintritt (wie `generate()`). | Code verifiziert; Symmetrie zu `generate()`. |
| **H3** | `video/engine.py` | `_ffmpeg_extract` prüft jetzt `returncode` + Output-Existenz/Größe und **wirft** bei Fehlschlag; Fallback-`stderr` wird geloggt (war DEVNULL). Beide Caller (`_render_segments`, `generate_from_timeline`) **überspringen** fehlgeschlagene Segmente statt 0-Byte-Files in den Concat zu hängen. | Code verifiziert. |
| **H4** | `core/system_monitor.py` | `_query_temperature_alternative` iteriert natives LibreHardwareMonitor jetzt unter `_lhm_lock` (wie `_collect_lhm_stats`). Kein Deadlock (Aufruf liegt außerhalb gehaltener Locks — geprüft). | Call-Graph auf Reentrancy geprüft. |
| **H5** | `audio/streaming_analyzer.py` | Kann soundfile die Datei nicht öffnen (MP3), wird **einmal** nach Temp-WAV transkodiert (`_transcode_to_wav`) und alle Chunks nutzen O(1)-Block-I/O statt O(n²)-`librosa.load(offset=)`. Temp-WAV wird aufgeräumt. | Code verifiziert; Logik isoliert. |
| **H6** | `video/video_embedder.py` | SigLIP-2 macht jetzt `reserve()`+`commit()`, registriert `unload_callback`, und hat eine `unload()`-Methode mit `release()` (spiegelt RAFT-Muster). Kein Phantom-VRAM mehr. | Code verifiziert gegen RAFT-Pattern. |
| **M3** | `ai/clap_wrapper.py` | `classify_audio` gibt im ONNX-Modus `[]` + Warning zurück statt fabrizierter Fake-Tags. | Code verifiziert. |
| **M13** | `backend/dependencies.py` | `SSELogHandler.emit` nutzt den geteilten `_main_loop` statt `asyncio.get_running_loop()` → Worker-Thread-Logs erreichen das SSE-Live-Log wieder. | Code verifiziert. |
| **D1** | `workers/base_worker.py` | `BaseWorker.run()` gibt jetzt sein `_execute()`-Result zurück (war implizit `None` → Orchestrator-`AttributeError`). | Code verifiziert. |
| **Dep** | `workers/__init__.py` | Deprecation-Hinweis: Paket ist toter PyQt6-Code, von nichts außerhalb `workers/` importiert. | Importgraph verifiziert. |

## H6 — jetzt VOLLSTÄNDIG (vom User freigegeben)
`with_gpu_task` gibt committed VRAM im `finally` jetzt für **transiente** Modelle frei (kein `unload_callback` → nicht von ModelLoader/RAFT/SigLIP verwaltet). Persistente, owner-verwaltete Modelle (mit `unload_callback`) bleiben resident. **Live getestet**: transientes Modell nach Task released (→0MB), persistentes bleibt (1500MB), 5 Tasks akkumulieren 0MB (alt: ~4000MB Leak).

### (ursprüngliche Notiz, jetzt erledigt)
`backend/dependencies.py::with_gpu_task` gibt committed VRAM nach dem Task nicht frei (`cancel_reservation` ist nach `commit()` ein No-op). Das ist für **persistent geladene** ModelLoader-Modelle **korrekt** (sie sollen resident bleiben). Ein pauschales `release()` im `finally` würde persistente Modelle nach jedem Task evakuieren → Regression. Der genaue Leak betrifft nur transiente `model_id`s ohne besitzendes Unload-Objekt; das sauber zu trennen braucht die Router-Module (nicht im gespiegelten Stand) und **deine Freigabe**. Der konkret verifizierte Leak (`video_embedder`) ist gefixt.

## D2 (Low, totes Modul)
VRAM-Leak-on-Cancel in `audio_stem_worker`/`video_motion_worker` bewusst **nicht** refactored — das Modul wird gelöscht (`delete_dead_workers.ps1`), und untesteten toten Code umzubauen bringt mehr Risiko als Nutzen.

## Verifikations-Stand (ehrlich)
- **AST/Syntax**: alle 10 Dateien fehlerfrei. **pyflakes**: keine neuen Undefined-Names/Typos.
- **C1**: echter Laufzeit-Test mit `faiss-cpu` bestanden (s. o.).
- **H1–H6, M3, M13, D1**: statisch am Quellcode verifiziert, aber **nicht** gegen die volle `pytest Tests/`-Suite gelaufen — die braucht deine Windows/DirectML-Umgebung (onnxruntime-directml, torch, librosa, LibreHardwareMonitor). Bitte dort laufen lassen: `pytest Tests/ -x -q`.

## Anwenden
1. Patch: aus dem Repo-Root `git apply pb_studio_fixes.patch` (oder die 10 Dateien aus dem Zip übernehmen).
2. Dead-Code entfernen (reversibel): `powershell -ExecutionPolicy Bypass -File .\delete_dead_workers.ps1`
3. `pytest Tests/ -x -q` in deiner Umgebung, dann WPF-Smoke-Test (Preview-Render mit `duration_limit`, Cancel→Re-Render, langer MP3-Mix).
