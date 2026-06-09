# Implementierungsplan: System-wide Bug Hunting & Codebase Audit (Epic 00013)

## Technical Context
* **WPF Frontend:** .NET 9 SDK WPF Core
* **Python Backend:** Python 3.11.x, NumPy 1.26.4
* **Database & Vector Store:** SQLite (SQLAlchemy) + FAISS-CPU + sqlite-vec
* **AI Runtime:** ONNX Runtime DirectML (AMD Hardware Profile)

---

## Proposed Audit Approach (Der Audit-Plan)

Um eine lückenlose Verifikation zu gewährleisten, gliedern wir das System-Audit in 5 disjunkte, parallel/sequenziell prüfbare Audit-Phasen basierend auf den `fullstack-audit-expert` Zonen:

### Phase 1: Z-DATA & Z-CORE (Speicher- & Thread-Audit)
* **Aktivität:** 
  1. Untersuchung von `src/pb_studio/core/vram_arbiter.py` und `src/pb_studio/core/vram_budget_manager.py` auf mögliche Evizierungs-Deadlocks und VRAM-Lecks.
  2. Prüfung der SQLite-WAL-Modus Konfiguration in `src/pb_studio/data/storage_layer.py` und `backend/dependencies.py` bezüglich asynchroner Schreibzugriffe.
  3. Untersuchung des FAISS-Index-Lebenszyklus in `src/pb_studio/data/vector_store.py` (insbesondere atexit-Leaks).

### Phase 2: Z-AUDIO & Z-VIDEO (Pipeline- & Fallback-Audit)
* **Aktivität:**
  1. Untersuchung aller `with_gpu_task(...)` Aufrufe in `src/pb_studio/audio/` und `src/pb_studio/video/` auf unvollständige Fehlerbehandlung (Exception-Handling) und ungenügende Freigaben im `finally`-Block.
  2. Prüfung der Fallback-Mechanismen bei Ausbleiben von GPU-Hardware-Hardware-Acceleratoren (z.B. librosa-Fallback bei BPM-Detection).
  3. Verifikation der FFmpeg-Subprozess-Bereinigung bei Render-Abbrüchen in `src/pb_studio/rendering/ffmpeg_amf_encoder.py`.

### Phase 3: Z-UI-VM & Z-UI-VIEWS (WPF Frontend-Audit)
* **Aktivität:**
  1. Statische Triage über alle WPF-ViewModels in `PBStudio.UI/ViewModels/` auf ungeschlossene Event-Subskriptionen, ungesicherte `Ioc.Default`-Aufrufe und `IDisposable`-Verletzungen bei Register/Unregister.
  2. Prüfung aller `Dispatcher.Invoke` Aufrufe auf Blockierungsgefahren des Haupt-Rendering-Threads.
  3. Untersuchung von `ApiClient.cs` und `SSEClient.cs` bezüglich Timeout-Resilienz und reconnect-Deadlocks.

### Phase 4: Shared-Zones & Z-INFRA (API- & Router-Audit)
* **Aktivität:**
  1. Untersuchung aller REST-Endpunkte in `backend/routers/` auf Pfadüberquerungsschutz (`Path-Traversal`) und unzureichende Validierung von Client-Inputs.
  2. Überprüfung von `main.py` und `app_state.py` bezüglich Singleton-Lebenszyklus und sauberen Shutdown-Hooks.

### Phase 5: Z-TESTS (Testabdeckung & Coverage-Audit)
* **Aktivität:**
  1. Prüfung der Pytest-Suite auf unzureichend getestete Edge-Cases oder stumme Assert-Mocks.
  2. Ausführung der vollständigen Testabdeckungsprüfung per `verify_release_smoke.ps1` und `gui_screenshot_v4.py`.

### Phase 6: Z-AUDIO Stem-Fehlerbehebung & Pipeline-Integration (Neu)
* **Aktivität:**
  1. In `backend/schemas/audio_schemas.py` den Enum-Wert `StemModel.HTDEMUCS` von `"htdemucs"` auf `"htdemucs.yaml"` ändern, damit `audio-separator` das Modell korrekt auflöst.
  2. In `backend/routers/audio_router.py` die Funktion `_run_audio_analysis` so anpassen, dass sie das Dictionary `stems_paths` (aus dem Clip-State) als optionalen Parameter übergeben bekommt.
  3. Bei der Beat-Detection (sowohl Streaming als auch Offline) prüfen, ob ein `drums_path` in den `stems_paths` existiert und physisch vorhanden ist. Falls ja, diesen Pfad für BeatNet / Beat-Detection verwenden.
  4. Bei der Key-Detection prüfen, ob ein `instrumental_path` in `stems_paths` existiert und physisch vorhanden ist. Falls ja, dieses Audio für die Key-Detection laden und analysieren (begrenzt auf max. 600s).
  5. In `analyze_audio` in `audio_router.py` die `stems_paths` aus dem Clip-State auslesen und an `_run_audio_analysis` übergeben.

---

## Verification Plan

### Automatisierte Tests
* Pytest Suite: `pytest Tests/ -x -q` (insbesondere `Tests/test_audio_analyzer.py`)
* WPF Release Build: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
* E2E Smoke-Pipeline: `powershell.exe -ExecutionPolicy Bypass -File .\verify_release_smoke.ps1`

### Manuelle Verifikation
* Stem-Separation über Swagger-UI oder App testen mit dem Demucs-Modell.
* Audio-Analyse nach der Stem-Separation ausführen und prüfen, ob die Ausgaben die Drums/Instrumental-Pfade verwenden.

---

## Realisierte Findings & Behebungen

Während des Audits wurden 5 konkrete Schwachstellen und 1 Performance-Engpass identifiziert und behoben:

1. **Z-CORE (VRAM Context Link):** `VRAMContext.set_unload_callback()` aktualisiert nun auch das registrierte `ModelBudget` im Manager, um stumme Entladungen zu verhindern.
2. **Z-DATA (Vector Store Save Lock):** `_save_unlocked()` wurde mit einem non-blocking Lock-Erwerb via `write_lock.acquire(blocking=False)` ausgestattet, um zu verhindern, dass der Haupt-Thread bei concurrent Speichervorgängen blockiert. Beim Shutdown wird `force=True` verwendet.
3. **Z-CORE (Model Loader GC):** `unload_all()` führt nun explizit `gc.collect()` aus, um C++ ONNX-Sessions sofort aus dem GPU-VRAM zu entfernen.
4. **Z-DATA (SQLite Cross-Thread Shutdown):** Verbindungserstellung in `database_core.py` auf `check_same_thread=False` umgestellt, damit der Haupt-Thread beim Anwendungs-Shutdown alle Thread-lokalen Verbindungen sauber schließen kann.
5. **Z-VIDEO (Moondream VRAM Leak):** Die Tag-Extraktion in `moondream_wrapper.py` läuft in einem `try...finally`-Block, der den `MoondreamAnalyzer` im `finally`-Block garantiert entlädt.
6. **Z-INFRA (Smoke Test Process Tree Kill):** `verify_release_smoke.ps1` wurde so modifiziert, dass der gesamte Uvicorn-Backend-Prozessbaum via `taskkill /f /t` beendet wird, um Windows-Prozesszombies dauerhaft auszuschließen.
7. **Z-CORE/Z-AUDIO (SmartDirector VRAM-Thrashing):** Korrektur der Entladelogik in `SmartDirector._ensure_clap_loaded()` – da CLAP auf CPU (Budget = 0) läuft, entladen wir SigLIP nicht mehr präventiv, um PCIe/VRAM-Thrashing zu verhindern.
8. **Z-VIDEO/Z-CORE (SigLIP Batch Inferenz):** Umstellung von `SigLIPWrapper.encode_images_batch()` auf echte ONNX Batch-Inferenz über 4D-Tensoren zur optimalen GPU-Auslastung auf AMD-Karten.
9. **Z-DATA (Vector Store Tombstone Re-Indexing):** Hinzufügen von `clean_tombstones()` zur physischen Index-Bereinigung und Re-Indexing zur Vermeidung von Suchzeit- und Speicherbloat bei vielen gelöschten Medien.
10. **Z-AUDIO (Demucs Modellname):** `StemModel.HTDEMUCS` in `audio_schemas.py` auf `"htdemucs.yaml"` geändert.
11. **Z-AUDIO (Stems-Analyse-Pipeline):** Die Audio-Analyse liest `stems_paths` aus dem Clip-State und leitet die Beat-Detection auf die Drums-Spur und die Key-Detection auf die Instrumental-Spur um.


