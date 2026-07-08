# AUDIT GPU-Stack + Threading + Concurrency — 2026-05-11

Scope: Deep-Audit GPU-Resource-Management, Lock-Hygiene, DirectML-Session-
Lifecycle, Thread-Pool und Async/Sync-Brücken.

In Scope:
- `src/pb_studio/core/vram_arbiter.py`, `vram_budget_manager.py`, `task_queue.py`,
  `system_monitor.py`, `crash_handler.py`, `model_loader.py`, `thread_pool.py`,
  `worker_signals.py`
- `backend/middleware/gpu_lock.py`, `backend/dependencies.py`
- `src/pb_studio/ai/siglip_wrapper.py` (siglip_embedder nicht existent),
  `clap_wrapper.py`, `clap_pytorch.py`
- `src/pb_studio/video/raft.py` (MotionAnalyzer), `moondream.py`,
  `moondream_wrapper.py`
- `src/pb_studio/audio/separator.py` (LOCKED — read only),
  `beat_detector.py`, `audio_embedder.py`, `streaming_analyzer.py`
- `src/pb_studio/video/video_embedder.py`, `audio_key_detector.py`
- `src/pb_studio/brain/{brain_service,weight_store,feedback_logger}.py`
- `src/pb_studio/storage/{embedding_repository,sqlite_init}.py`
- `backend/routers/{audio_router,video_router,pacing_router,render_router,events_router,brain_router}.py`
- `PBStudio.UI/ViewModels/{TimelineViewModel,DirectorViewModel}.cs`

Read-only. Audio-Pacing, UI-Wiring, Test-Coverage sind NICHT Teil dieser Audit.

---

## 1. VRAM Arbiter / Budget Manager — Lifecycle

End-to-End VRAM-Path:

| # | Stage | File:Line | Beobachtung |
|---|---|---|---|
| 1 | Singleton-Init | `vram_budget_manager.py:181-188` | `__new__` doppel-checked Lock, ok |
| 2 | Limit-Detection | `vram_budget_manager.py:241-342` | Config → Monitor → WMI (32-bit cap) → Registry-by-name → Fallback 8192MB |
| 3 | Register-Model | `vram_budget_manager.py:391-437` | unter `_registry_lock` (RLock) |
| 4 | Reserve | `vram_budget_manager.py:500-554` | `reserve(model_id, force=True)` triggert `_evict_for_space` |
| 5 | Eviction | `vram_budget_manager.py:661-717` | Callback-Aufruf UNTER `_registry_lock` |
| 6 | Commit | `vram_budget_manager.py:556-598` | konvertiert reserved → committed |
| 7 | Release | `vram_budget_manager.py:600-631` | dekrementiert beide Counter |
| 8 | Backend-Wrap | `backend/dependencies.py:27-122` | `with_gpu_task`: reserve → lock → commit → task → release |
| 9 | Telemetrie | `vram_budget_manager.py:787-865` | TelemetryEntry pro `model_id`, separater `_telemetry_lock` |

### Korrektheits-Garantien

| Garantie | Implementiert? | File:Line |
|---|---|---|
| Singleton thread-safe | Ja (double-check + Lock) | `vram_budget_manager.py:181-188` |
| `enable_mem_pattern=False` in ORT-SessionOptions | Ja in **allen** ORT-Wrappern (RAFT, Moondream, SigLIP, CLAP, separator, model_loader) | `raft.py:103`, `moondream.py:110`, `siglip_wrapper.py:56`, `clap_wrapper.py:80`, `separator.py:173`, `model_loader.py:146` |
| `enable_cpu_mem_arena=False` (IRON RULE §2) | Ja in **allen** Wrappern | gleiche Stellen wie oben |
| DirectML-Only (kein CPU-Fallback in `_get_providers`) | RAFT + Moondream: Ja; SigLIP, CLAP: nein (CPU-Fallback aktiv) | `raft.py:122-133`, `moondream.py:120-131`, vs. `siglip_wrapper.py:61-63`, `clap_wrapper.py:85-87` |
| Reserve→Commit→Release Sequenz | Ja über `VRAMContext` + `with_gpu_task` | `vram_budget_manager.py:872-935`, `dependencies.py:42-122` |
| Eviction-Callback ohne Halten des Locks | **Nein** — Callback wird unter `_registry_lock` aufgerufen | `vram_budget_manager.py:697-715` |
| Telemetrie blockiert Task nicht | Ja, separater Lock + Try/Except | `vram_budget_manager.py:801-833` |
| OOM-Fallback ohne CPU-Schwenk (IRON RULE §1) | RAFT, Moondream: Ja; SigLIP/CLAP via PyTorch-Fallback laden auf CPU | `clap_pytorch.py:62-99`, `siglip_wrapper.py:73-82` |
| `force=True` triggert echte Eviction | Ja | `vram_budget_manager.py:527-543` |
| ONNX-Session-Destroy → VRAM-Release | Manuell via `gc.collect()` nach `del session` | `raft.py:669-676`, `moondream.py:729-747`, `model_loader.py:344-355` |
| AppExit cleanup-Hook für DirectML-Sessions | **Nein** — `crash_handler.py` macht NUR `logging.critical`, ruft keine `unload()` |  `crash_handler.py:7-37` |

---

## 2. GPU-Lock + with_gpu_task — Async/Sync-Brücke

| Aspekt | Beobachtung | File:Line |
|---|---|---|
| Lock-Typ | `asyncio.Lock()` (single-process, single-event-loop) | `dependencies.py:19` |
| Globaler Scope | 1 Lock für **alle** GPU-Tasks (stem-separation, video-analyze, audio-analyze ist NICHT GPU-locked, render bypasst `with_gpu_task`) | `dependencies.py:19`, `render_router.py:294` |
| Timeout-Default | 300s (config) | `config.py:80` |
| Reserve VOR Lock-Erwerb | Ja, dann inside-lock commit | `dependencies.py:43-68` |
| Cancel/Timeout-Cleanup | `try/finally` released VRAM; Telemetrie eintragend | `dependencies.py:103-122` |
| Reentrancy-Safe (rekursiver Call) | **Nein** — `asyncio.Lock` ist NICHT reentrant. Ein endpoint, der intern `with_gpu_task` zweimal aufruft, deadlocked. Aktuell nicht produktiv vorkommend, aber unbewacht. | `dependencies.py:66` |
| Middleware-Lock | Nur Timer/Logger (KEIN Lock!) trotz Namens. Echter Lock ist nur `with_gpu_task`. | `gpu_lock.py:30-53` |

---

## 3. DirectML Sessions — Lifecycle

| Modul | Provider-Spec | Lazy-Load | unload() vorhanden | Im Hot-Path explizit unloaded? |
|---|---|---|---|---|
| `raft.MotionAnalyzer` | `['DmlExecutionProvider']` (Iron Rule, kein CPU-Fallback) | Ja | Ja (`raft.py:669-678`) | Ja (`video_router.py:697-700`) |
| `moondream.MoondreamAnalyzer` | `['DmlExecutionProvider']` (Iron Rule) | Ja | Ja (`moondream.py:729-747`) | Indirekt via `moondream_wrapper.extract_tags_via_moondream` — kein expliziter Unload nach jeweils einem Frame |
| `siglip_wrapper.SigLIPWrapper` | `['DmlExecutionProvider', 'CPUExecutionProvider']` (CPU-Fallback aktiv, **verstoesst gegen IRON RULE §1** wenn DML fehlt) | Konfigurierbar | Ja (`siglip_wrapper.py:173-176`) | Ja (`video_router.py:781-782` via `del wrapper`) |
| `clap_wrapper.CLAPAnalyzer` | `['DmlExecutionProvider', 'CPUExecutionProvider']` (CPU-Fallback aktiv) + PyTorch-Fallback | Default Lazy | Ja (`clap_wrapper.py:203-206`) | Brain-Pipeline (siehe §5) nutzt CLAP-PyTorch nicht via diesen Wrapper |
| `audio_embedder.AudioEmbedder` (Brain — CLAP via torch-directml) | `torch_directml.device()` mit silent fallback auf CPU | Ja | **Nein** — kein `unload()` definiert | Nie unloaded — singleton lebt bis Prozessende |
| `video_embedder.VideoEmbedder` (Brain — SigLIP-2 via torch-directml, FP16) | `torch_directml.device()` + `float16` mit Fallback auf CPU+FP32 | Ja | **Nein** | Nie unloaded |
| `separator.StemSeparator` (LOCKED) | DirectML via Monkey-Patch von `audio-separator.Separator` | Eager | Ja (`separator.py:186-194`) | Patch wird scoped angewendet/restored (`separator.py:166-184`) |
| `model_loader.ModelLoader` (DEAD CODE in Production-Hot-Path) | DML + CPU | Lazy | Ja (`model_loader.py:326-361`) | Nicht in produktivem Hot-Path verdrahtet (nur Tests + 1 worker-archiv) |

### Provider-Inkonsistenz (Iron-Rule-Drift)
- `siglip_wrapper.py:63` und `clap_wrapper.py:87` enthalten **explizit** `CPUExecutionProvider` als Fallback.
- `raft.py:122-133` und `moondream.py:120-131` haben das (richtig) entfernt.
- **Konsequenz:** SigLIP- und CLAP-Embedding läuft stillschweigend auf CPU wenn DirectML fehlt — verstößt gegen IRON RULE §1 ("AMD DirectML ONLY"). Logging gibt keinen WARN.

### Memory-Pattern + CPU-Arena
- ALLE 7 ORT-Wrapper setzen `enable_mem_pattern=False` UND `enable_cpu_mem_arena=False`. ✅
- `model_loader.py:144-147` hat einen R16-Fix-Kommentar: war `True` (falsch) bis BUG-Audit. Aktuell beide `False`.

---

## 4. Task-Queue + Thread-Pool — DEAD CODE

| Modul | Verwendung im Production-Code | Verbleibend? |
|---|---|---|
| `core/task_queue.py` (PriorityQueue) | KEINE (nur `core/__init__.py` re-export) | Ja — soll entfernt werden |
| `core/thread_pool.py` (PyQt6 `QThreadPool`) | **Nur** in `services/analysis_service.py` + `services/generation_service.py` — beide nicht von Backend/UI verdrahtet | Ja |
| `core/worker_signals.py` (PyQt6 Signals) | Nur über `thread_pool.py` | Ja |

→ **Vollständiger PyQt6-Relict-Subtree**. Backend nutzt FastAPI + `asyncio.to_thread`. WPF UI hat nichts mit PyQt6.
→ Cleanup-Effekt: spart Import-Cost beim Backend-Start (PyQt6 wird sonst geladen wenn `pb_studio.core.__all__` traversiert).

---

## 5. Brain — CLAP + SigLIP-2 via torch-directml

| Aspekt | Beobachtung | File:Line |
|---|---|---|
| Modell-Singleton | Beide: `_singleton_lock = threading.Lock()` + double-check | `audio_embedder.py:42-52`, `video_embedder.py:34-44` |
| VRAM-Registrierung | **NICHT** mit `VRAMBudgetManager` registriert | suchgrep: `audio_embedder.py` enthält 0 `register_model`-Calls |
| `enable_mem_pattern` / `enable_cpu_mem_arena` | N/A — torch-directml, nicht ONNX-Runtime. **Aber**: torch-directml hat eigene Allocator-Logik, die mit ORT-DirectML-Sessions im gleichen Prozess **konkurriert** | n/a |
| FP16 für VRAM-Footprint | Ja bei `VideoEmbedder` (siglip2-base, ~600MB) | `video_embedder.py:73-76` |
| FP32 bei CLAP | Ja, default | `audio_embedder.py:73-95` |
| `KNOWN_MODEL_BUDGETS`-Entry | Fehlt für `larger_clap_music` und `siglip2-base`. Existierende `siglip_so400m: 2500MB` ist anderer Modell-Pfad. | `vram_budget_manager.py:59-84` |
| `with_gpu_task`-Wrapper | Doku im audio_embedder sagt "Caller MUSS with_gpu_task verwenden" — **aber pacing_router ruft die Embedder INTERN via `annotate_cuts_with_brain` aus einem `asyncio.to_thread` ohne with_gpu_task** | `pacing_router.py:113-126`, `audio_embedder.py:7-9` |
| OOM-Fallback (Iron Rule §1) | `VideoEmbedder._embed_batched:185-195`: bs/2 Halvierung bei OOM ✅. Aber: `_ensure_loaded` fängt `RuntimeError` → CPU-Fallback (`audio_embedder.py:91-95`, `video_embedder.py:89-95`) — silent → IRON RULE §1 verletzt |
| Sessions werden unloaded? | **Nein** — Beide Embedder leben global, kein `close()`, kein `__del__` | `audio_embedder.py:55-188`, `video_embedder.py:47-216` |

### WeightStore + sqlite-vec — Thread-Safety

| Aspekt | Beobachtung | File:Line |
|---|---|---|
| `WeightStore._lock` | `threading.Lock()` (non-RLock) | `weight_store.py:54` |
| Cache-Read mit Lock | Ja: 2× `with self._lock:` pro `get_posterior_mean` (Read + Write-on-Miss) | `weight_store.py:104-115` |
| `update()` triggert `_invalidate()` mit `self._lock` | Ja — Cache komplett gedroppt | `weight_store.py:157, 219-224` |
| `update()` ohne Lock um SQL-Write | **Ja, Write läuft OHNE `_lock`** (`weight_store.py:148-157`). Korrekt wegen SQLite-mutex, aber Versions-Counter-Update ist nach SQL-Commit → kurze Cache-Stale-Window (Reader bekommt alten Wert, schreibt ihn neu in Cache) | `weight_store.py:148-157` |
| `FeedbackLogger.log_feedback` | 85 Bucket-Updates (17 axes × 5 Levels) **in einer Transaktion** auf `weights.conn` — alle innerhalb des `_lock`-bumps in `WeightStore.update()`. SQL-Mutex serialisiert weiter. Läuft **synchron im Event-Loop** wenn von brain_router aufgerufen | `feedback_logger.py:64-79`, `brain_router.py:88-92` |
| `EmbeddingRepository` (sqlite-vec) | `check_same_thread=False`, `isolation_level=None`, WAL aktiv | `embedding_repository.py:73-76`, `sqlite_init.py:11` |
| sqlite-vec KNN Multi-Threaded | Connection wird zwischen Threads geteilt — Python SQLite C-Mutex serialisiert weiterhin → keine parallelen Reads aber keine Race | `embedding_repository.py:72-76` |
| `brain_router` SQLite-Calls im Event-Loop | **Ja** — Alle 6 Endpoints rufen `svc.state_conn.execute(...)` direkt aus `async def` ohne `asyncio.to_thread`. Bei sqlite-vec-Lookups → Event-Loop hängt. | `brain_router.py:42-48, 71-74, 109-113, 161-181, 195-208` |

---

## 6. Threading-Brücken Backend → UI

### `asyncio.run_coroutine_threadsafe` (Worker → SSE)

| Fundort | Coroutine | Thread-Safe? |
|---|---|---|
| `audio_router.py:96` (Hash-Progress) | `publish_event("import_progress", ...)` | Ja (event-loop passed via `_loop`) |
| `audio_router.py:478` (Stem-Progress) | `publish_event("stem_progress", ...)` | Ja |
| `audio_router.py:599` (Analysis-Progress) | `publish_event("analysis_progress", ...)` | Ja |
| `video_router.py:88` (Video-Hash) | `publish_event("import_progress", ...)` | Ja |
| `video_router.py:654` (Motion-Progress, RAFT C1) | `publish_event("analysis_progress", ...)` | Ja |
| `pacing_router.py:398` (Pacing-Progress L-M7) | `publish_event("pacing_progress", ...)` | Ja |

→ Alle Fundstellen reichen `loop = asyncio.get_running_loop()` an die Worker-Funktion. Pattern korrekt.

### `publish_event` Fan-out + `QueueFull`

| Aspekt | File:Line | Beobachtung |
|---|---|---|
| Fan-out auf alle Queues | `dependencies.py:142-158` | Korrekt (BUG-028-Fix) |
| `maxsize=500` pro Queue | `dependencies.py:132` | Drop-Oldest bei Voll-Lauf |
| Drop-Strategy | `get_nowait()` → `put_nowait()` | Korrekt aber **nicht atomisch unter Lock** (asyncio Queue ist single-thread-safe, kein Issue im Event-Loop, aber `publish_event` wird auch aus Worker-Threads via `run_coroutine_threadsafe` aufgerufen → der Block landet immer im Event-Loop, ok) |

### WPF Dispatcher.Invoke (TimelineViewModel + DirectorViewModel)

| Fundort | `Invoke` / `InvokeAsync` | Risk |
|---|---|---|
| `TimelineViewModel.cs:82, 95` | `Dispatcher.Invoke` (sync) | Wird aus `UpdateSpectralPoints` aufgerufen. Wenn Caller bereits auf UI-Thread → **kein Deadlock** (Invoke detected reentrance). Wenn Caller auf BG-Thread → blockiert BG bis UI fertig. |
| `TimelineViewModel.cs:214, 232, 313, 451, 550, 565, 573, 593, 604` | `InvokeAsync` | Korrekt — non-blocking |
| `DirectorViewModel.cs:96` | `Dispatcher.Invoke(ResetProjectState)` | Wird aus `ProjectClosedMessage`-Handler aufgerufen, der via `WeakReferenceMessenger.Send()` getriggert wird. Wenn `Send()` aus BG-Thread → ok. Wenn aus UI-Thread → reentrante Invoke = no-op, kein Deadlock. |
| `DirectorViewModel.cs:406` | `Dispatcher.Invoke(...)` (sync) | Im Brain-Recovery-Path. Selbe Logik. |

→ Keine offensichtlichen Cross-Thread-Deadlocks im UI-Layer, aber `Dispatcher.Invoke(sync)` auf 3 Stellen ist Anti-Pattern: bei langlaufenden UI-Mutationen blockiert das den Background-Thread.

---

## 7. Spezifische Audit-Fragen

### L-N8 — `compute_beat_strengths` im Async-Context

| Beobachtung | File:Line |
|---|---|
| Aufruf-Pfad | `audio_router.py:650` (innerhalb `_run_audio_analysis`) |
| Async-Wrapper | Ja: `_run_audio_analysis` läuft via `asyncio.to_thread` (`audio_router.py:305`). |
| GPU-Lock | **Nein**, korrekt (CPU-only librosa). |
| Blocking? | Ja, blockiert nur Worker-Thread, nicht Event-Loop. |
| Status | OK |

### L-K2 — Moondream blocking, Lazy-Load

| Beobachtung | File:Line |
|---|---|
| Aufruf-Pfad | `video_router.py:813` → `moondream_wrapper.extract_tags_via_moondream` → `MoondreamAnalyzer(lazy_load=True)._init_model()` |
| Lazy-Load | Ja (`moondream.py:100-101`) |
| Im Hot-Path neu instanziert | **Ja** — pro `_run_video_analysis`-Call wird ein neuer Analyzer angelegt und nach Frame-Verarbeitung garbage-collected. **Re-loadet das ONNX-Modell bei jedem Video!** | `moondream_wrapper.py:115`, kein Singleton |
| Im GPU-Lock | Ja — `_run_video_analysis` ist über `with_gpu_task` (`video_router.py:380`). |
| VRAM-Eviction-Conflict | Wenn RAFT noch nicht entladen (race zwischen `motion_analyzer.unload()` und neu erzeugtem Moondream) → kann 2× DML-Session gleichzeitig allokieren. RAFT-Unload mit `gc.collect()` (video_router:699) sollte VRAM freigeben, aber DirectML-Free ist nicht synchron. |
| Status | **WARNING** — kein Singleton, re-init bei jedem Video, VRAM-Spike möglich |

### L-K4 — ffmpeg-subprocess Async-Blocking

| Beobachtung | File:Line |
|---|---|
| `subprocess.run(...)` synchron | Ja (`audio_key_detector.py:62`) |
| Aufruf-Pfad | `_run_video_analysis:835` → `detect_video_audio_key` → `subprocess.run` 30s ffmpeg + librosa load |
| Innerhalb `with_gpu_task` | **Ja, kritisch** — `_run_video_analysis` läuft im GPU-Lock. ffmpeg-Subprocess + librosa + Krumhansl-Kessler hält den **globalen GPU-Lock** für CPU-Arbeit bis zu ~30s pro Video |
| Async-Variante (`asyncio.create_subprocess_exec`) | Nein |
| Status | **CRITICAL** — GPU-Lock-Holding für CPU-Arbeit |

### L-M7 — `on_progress` Cross-Thread

| Beobachtung | File:Line |
|---|---|
| Pattern | `_emit_pacing_progress(loop, pct)` ruft `asyncio.run_coroutine_threadsafe(publish_event(...), loop)` (`pacing_router.py:391-406`) |
| Loop-Quelle | `asyncio.get_running_loop()` IM Request-Handler vor `to_thread`-Boundary (`pacing_router.py:80`) |
| Exception-Safe | Ja — `try/except` swallowed |
| Status | OK |

### TimelineVM Dispatcher-Invoke

Siehe §6. Keine Deadlocks. 2× `Invoke(sync)` ist suboptimal aber nicht kaputt.

---

## 8. Race-Conditions / Deadlock-Findings

### F1 (CRITICAL) — Eviction-Deadlock in `ModelLoader.load_model`

Quelle: `model_loader.py:216-267` + `vram_budget_manager.py:697-715` + `model_loader.py:338-355`.

Sequenz:
1. Thread T1 → `ModelLoader.load_model("siglip_so400m", force=True)` nimmt `self._session_lock` (line 216).
2. T1 ruft `self.vram_manager.reserve("siglip_so400m", force=True)` (line 238).
3. `reserve` ruft `_evict_for_space()` (vram_budget_manager:531).
4. `_evict_for_space` läuft unter `_registry_lock` und ruft `budget.unload_callback()` (line 697-699).
5. Callback ist `lambda mid: self._do_unload(mid)` (model_loader:234) → `_do_unload` macht `with self._session_lock:` (model_loader:340).
6. `self._session_lock` ist `threading.Lock()` (**non-reentrant**) → **Deadlock auf gleichem Thread**.

**Mitigation aktuell**: `ModelLoader` ist nicht im produktiven Hot-Path verdrahtet (siehe §4). Nur Tests + 1 archivierter Worker. **Falls er je angeschaltet wird → garantierter Deadlock bei force=True mit voller VRAM.**

Behebung: `_session_lock` → `threading.RLock()`. ODER Callback OHNE Lock aufrufen.

### F2 (HIGH) — `_run_video_analysis` hält GPU-Lock für CPU-FFmpeg

Quelle: `video_router.py:380-383` (`with_gpu_task(_run_video_analysis, ..., model_id="video_analysis_full")`) → `audio_key_detector.detect_video_audio_key` (`video_router.py:835`) → `subprocess.run([ffmpeg, ...], timeout=30)` + `librosa.load` + `KeyDetector.detect_key` (Krumhansl-Kessler).

Konsequenz:
- Globaler GPU-Lock (`asyncio.Lock`) hält für 5-30s **CPU-FFmpeg+librosa**. Stem-Separation, Render, andere Video-Analysen blockieren in dieser Zeit.
- BUG-205 + L-K4 sind in `_run_video_analysis` integriert, weil das früher kein Problem war (Audio-Key fehlte). Heute ist es Friction zu Stem-Job-Latency.

Behebung: ffmpeg+librosa-Block **vor** `with_gpu_task` ausführen, ODER `detect_video_audio_key` aus dem GPU-Code-Pfad herausziehen.

### F3 (HIGH) — Brain-Embedder bypass VRAM-Budget

Quelle: `audio_embedder.py` + `video_embedder.py` — torch-directml singletons, **kein** `register_model`, **kein** `VRAMBudgetManager.commit()`, **kein** `unload()`.

Konsequenz:
- VRAMBudgetManager glaubt 8GB frei, in Wahrheit ~1.1GB belegt von CLAP+SigLIP-2 → falsche `available_vram_mb` → Reserve-Decisions auf veraltetem State.
- `KNOWN_MODEL_BUDGETS` enthält keinen Eintrag → selbst manuelles Register würde Schätzfehler haben.
- DirectML konkurriert mit ORT-Sessions um den gleichen GPU-Pool → unmodellierte Allocator-Konkurrenz.

Behebung: CLAP+SigLIP-2 müssen `vram_manager.register_model(...)` aufrufen und `with_gpu_task` als Caller benutzen. Budget-Konstanten in `KNOWN_MODEL_BUDGETS` ergänzen (CLAP ~512MB, SigLIP2-base FP16 ~600MB).

### F4 (HIGH) — `brain_router` blockt Event-Loop mit SQLite

Quelle: alle 6 Brain-Endpoints (`brain_router.py:36-209`).

Konsequenz:
- `async def` aber `state_conn.execute(...).fetchall()` ohne `asyncio.to_thread` → bei sqlite-vec KNN (100+ms) blockiert der gesamte Event-Loop. Alle SSE-Clients stocken.
- `feedback_logger.log_feedback`: 85 Bucket-Updates in einer Transaktion + Cache-Invalidate → 5-50ms im Event-Loop pro Klick.

Behebung: Alle DB-Calls in den 6 Endpoints in `await asyncio.to_thread(...)` wrappen.

### F5 (MEDIUM) — `render_router` umgeht `with_gpu_task`

Quelle: `render_router.py:294` (`async with gpu_lock:`).

Konsequenz:
- Renders haben **keinen Timeout** (config.gpu_timeout_seconds wird nicht angewendet).
- Renders sind **nicht in VRAM-Telemetrie**.
- Render-Eviction von ML-Modellen passiert nicht (es gibt zwar `model_id="render_ffmpeg_amf"` Konzept aber nicht implementiert).

Behebung: Render in `with_gpu_task` mit custom-timeout (z.B. 2h für lange Mixe).

### F6 (MEDIUM) — `asyncio.Lock` ist nicht reentrant

Quelle: `dependencies.py:19` + `with_gpu_task`-Logik.

Konsequenz:
- Wenn eine ML-Pipeline-Komposition intern `with_gpu_task` zweimal aufruft (z.B. RAFT + SigLIP gefolgt von Moondream-Sub-Call) → Deadlock.
- Aktuell nicht produktiv getroffen (alle Sub-Models laufen sequenziell IN dem gleichen `with_gpu_task` über `model_id="video_analysis_full"`).
- Konstellation wäre triggerbar wenn jemand naive Wrapper-Komposition schreibt.

Behebung: `with_gpu_task` mit `try: lock.locked()` check + re-entry-bypass, ODER asyncio.Semaphore(1) (ebenfalls non-reentrant aber explizit) + Pattern-Doku.

### F7 (LOW) — BeatNet-Estimator-Singleton ohne Lock im Inference-Path

Quelle: `beat_detector.py:101-120` + `audio_router.py:41-51` Singleton.

Konsequenz:
- `BeatDetector._estimator` ist global, `_get_beat_detector()` schützt nur Init (`audio_router.py:38`). Inference (`_estimator.process(audio_path)`) hat keinen Lock.
- 2 parallele HTTP-Audio-Analyses → 2 Threads rufen `process()` auf dem gleichen BeatNet-Modell. TCN/CNN-Inference ist nicht garantiert reentrant.

Behebung: BeatNet-Inference unter `threading.Lock` serialisieren ODER pro-Request einen Detector spawnen (model load ~200ms tolerable).

### F8 (LOW) — Telemetrie-VRAM-Peak ist nicht echter Peak

Quelle: `dependencies.py:72-122`.

Konsequenz:
- `vram_baseline_mb` = `total_committed_mb` ZU BEGINN (also vor allem dem Task), `vram_peak_mb = max(baseline, total_committed_mb)` NACH Task. Da das Modell schon vor dem Task committed wurde (siehe `manager.commit(model_id)` Line 68), bleibt `total_committed_mb` während des Tasks **konstant** (kein anderer Commit unter dem GPU-Lock möglich) → Peak == Baseline == committed-after. Telemetrie misst **nicht** echten Sensor-Peak.

Behebung: VRAM-Peak via `monitor.get_stats()` während des Tasks samplen (`asyncio.create_task` background-poll im Lock-Scope).

### F9 (LOW) — `crash_handler.py` ohne VRAM-Cleanup

Quelle: `crash_handler.py:11-38`.

Konsequenz:
- Bei uncaught exception in einem Backend-Worker werden DirectML-Sessions nicht expliziert unloaded. Python-GC räumt sie zwar irgendwann, aber bei OOM-Crash bleibt VRAM lange belegt bis OS-Reclaim.

Behebung: `handle_exception` ruft `RecoveryHandler.get_instance().handle_oom_error()` (existiert!) oder mindestens `VRAMBudgetManager.evict_all(min_priority=LOW)`.

### F10 (INFO) — DEAD CODE: `task_queue.py`, `thread_pool.py`, `worker_signals.py`

Siehe §4. Komplette PyQt6-Relict-Subtree (3 Files), nur von 2 Service-Modulen referenziert die selbst nicht von Backend/UI gerufen werden.

### F11 (INFO) — Eviction-Callback unter Registry-Lock

Quelle: `vram_budget_manager.py:697-715`.

Konsequenz:
- `unload_callback()` läuft UNTER `_registry_lock`. Wenn der Callback langsam ist (z.B. SigLIP-Session destruktor + gc.collect 200-500ms) → blockiert alle anderen Register/Reserve/Stats-Calls in dieser Zeit.
- Kein Deadlock (Callbacks rufen nicht zurück in VRAMBudgetManager), aber Lock-Contention.

Behebung: Callback OUTSIDE des Locks aufrufen (Snapshot-and-execute Pattern).

### F12 (INFO) — `evict_all` und `_evict_for_space` clamp `_committed_mb` auf 0

Quelle: `vram_budget_manager.py:706, 745`.

Beobachtung: `max(0, ...)` ist defensiv für Callback-Doppelt-Release. Verbirgt aber Accounting-Bugs (Reserved→Committed-Pfad). Logger-WARN wäre besser.

---

## 9. Korrektheits-Garantien Übersicht

| Garantie | Status |
|---|---|
| 1 ONNX-DirectML-Session gleichzeitig (via gpu_lock) | ✅ — außer Render umgeht (F5) |
| `enable_mem_pattern=False` in allen Wrappern | ✅ |
| `enable_cpu_mem_arena=False` in allen Wrappern | ✅ |
| Kein CPU-Fallback (IRON RULE §1) | ⚠️ — SigLIP, CLAP, audio_embedder, video_embedder haben silent CPU-Fallback |
| VRAM-Budget vor Reserve | ✅ via `with_gpu_task` außer Brain-Embedder (F3) |
| VRAM-Release bei Exception | ✅ via `finally`-Block in `with_gpu_task` |
| OOM-Eviction triggert callback | ✅ aber unter Lock (F11) |
| Render-Timeout | ❌ (F5) |
| Brain-DB blockt nicht Event-Loop | ❌ (F4) |
| ffmpeg-Audio-Key blockt nicht GPU-Lock | ❌ (F2) |
| Eviction-Callback ohne Deadlock | ⚠️ — F1 latente Bombe in ModelLoader |
| Telemetrie-Peak echt | ❌ (F8) |
| Crash-Handler räumt VRAM auf | ❌ (F9) |

---

## 10. Recommendations (priorisiert)

1. **F2** (HIGH): `detect_video_audio_key` aus `_run_video_analysis` herausziehen (vor `with_gpu_task`). 1h Arbeit.
2. **F3** (HIGH): Brain-Embedder via `with_gpu_task` + `register_model`. 2-3h Arbeit + KNOWN_MODEL_BUDGETS update.
3. **F4** (HIGH): brain_router DB-Calls in `asyncio.to_thread` wrappen. 1h Arbeit.
4. **F1** (CRITICAL falls aktiviert): `ModelLoader._session_lock = threading.RLock()`. 2min. Oder ModelLoader als Dead Code entfernen.
5. **F5** (MEDIUM): Render in `with_gpu_task` mit custom-timeout. 2h Arbeit.
6. **F10** (INFO): Dead-Code-Cleanup `task_queue.py` + `thread_pool.py` + `worker_signals.py` + Service-Konsumenten. 1h Arbeit.
7. **F11** (INFO): Eviction-Callback aus Lock-Scope herausziehen. 1h Arbeit.
8. **F8** (LOW): Echter VRAM-Peak via Sampling. 2h Arbeit.
9. **F9** (LOW): Crash-Handler hookt RecoveryHandler. 30min.
10. **F6** (LOW): Reentrancy-Guard in `with_gpu_task` doku + assert. 30min.
11. **F7** (LOW): BeatNet-Inference unter Lock oder per-Request-Instanz. 1h.

---

## Anhang — Datei-Inventur

| File | Lines | Status |
|---|---|---|
| `vram_arbiter.py` | 252 | Legacy-Wrapper über BudgetManager |
| `vram_budget_manager.py` | 944 | Production (Singleton + Telemetrie) |
| `system_monitor.py` | 391 | Production (LHM + Fallbacks BUG-205 + D1+D2) |
| `task_queue.py` | 41 | DEAD CODE |
| `thread_pool.py` | 84 | DEAD CODE (PyQt6) |
| `worker_signals.py` | 28 | DEAD CODE (PyQt6) |
| `model_loader.py` | ~430 | DEAD CODE in Hot-Path, hat F1 |
| `crash_handler.py` | 38 | Minimal, kein Cleanup |
| `recovery_handler.py` | ~80 | Production aber crash_handler nicht verdrahtet |
| `dependencies.py` | 172 | Production (with_gpu_task) |
| `gpu_lock.py` | 53 | Production (nur Timer, kein echter Lock) |
| `raft.py` | 775 | Production |
| `moondream.py` | 768 | Production |
| `moondream_wrapper.py` | 151 | Production (L-K2) |
| `siglip_wrapper.py` | 181 | Production (CPU-Fallback drift) |
| `clap_wrapper.py` | 211 | Production (CPU-Fallback drift) |
| `clap_pytorch.py` | 307 | Production fallback |
| `audio_embedder.py` | 188 | Brain Production (F3) |
| `video_embedder.py` | 217 | Brain Production (F3) |
| `audio_key_detector.py` | 91 | Production (L-K4, F2) |
| `separator.py` | 278 | LOCKED |
| `beat_detector.py` | 366 | Production (F7) |
| `brain/brain_service.py` | 102 | Production Singleton |
| `brain/weight_store.py` | 234 | Production (cache + lock) |
| `brain/feedback_logger.py` | 81 | Production |

— ENDE AUDIT —
