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

---

## Verification Plan

### Automatisierte Tests
* Pytest Suite: `pytest Tests/ -x -q`
* WPF Release Build: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
* E2E Smoke-Pipeline: `powershell.exe -ExecutionPolicy Bypass -File .\verify_release_smoke.ps1`
* Visual Verification: `python Tests/gui_screenshot_v4.py`

---

## Realisierte Findings & Behebungen

Während des Audits wurden 5 konkrete Schwachstellen und 1 Performance-Engpass identifiziert und behoben:

1. **Z-CORE (VRAM Context Link):** `VRAMContext.set_unload_callback()` aktualisiert nun auch das registrierte `ModelBudget` im Manager, um stumme Entladungen zu verhindern.
2. **Z-DATA (Vector Store Save Lock):** `_save_unlocked()` wurde mit einem non-blocking Lock-Erwerb via `write_lock.acquire(blocking=False)` ausgestattet, um zu verhindern, dass der Haupt-Thread bei concurrent Speichervorgängen blockiert. Beim Shutdown wird `force=True` verwendet.
3. **Z-CORE (Model Loader GC):** `unload_all()` führt nun explizit `gc.collect()` aus, um C++ ONNX-Sessions sofort aus dem GPU-VRAM zu entfernen.
4. **Z-DATA (SQLite Cross-Thread Shutdown):** Verbindungserstellung in `database_core.py` auf `check_same_thread=False` umgestellt, damit der Haupt-Thread beim Anwendungs-Shutdown alle Thread-lokalen Verbindungen sauber schließen kann.
5. **Z-VIDEO (Moondream VRAM Leak):** Die Tag-Extraktion in `moondream_wrapper.py` läuft in einem `try...finally`-Block, der den `MoondreamAnalyzer` im `finally`-Block garantiert entlädt.
6. **Z-INFRA (Smoke Test Process Tree Kill):** `verify_release_smoke.ps1` wurde so modifiziert, dass der gesamte Uvicorn-Backend-Prozessbaum via `taskkill /f /t` beendet wird, um Windows-Prozesszombies dauerhaft auszuschließen.
