# PB Studio GRAND AUDIT Report — 2026-03-29

**Methodik:** 8 parallele Experten-Agenten, 3 Audit-Runden, 120+ Dateien Zeile fuer Zeile gelesen.
Runde 3: 40+ bisher UNGEPRUEFTE Dateien (workers/, models/, utils/, etc.) + E2E Runtime-Test.
Jeder Fund am echten Code gegengeprüft. Falsche Alarme als solche markiert.

---

## ZUSAMMENFASSUNG

| Schwere | Runde 1+2 | Runde 3 (neu) | GESAMT |
|---------|-----------|---------------|--------|
| KRITISCH | 1 | 0 | 1 |
| HOCH | 5 | 4 | 9 |
| MITTEL | 14 | 8 | 22 |
| NIEDRIG | 12 | 5 | 17 |
| DEAD CODE | 3 | 0 | 3 |
| **GESAMT** | **35** | **17** | **52** |

**E2E Runtime-Test: 0 Runtime-Bugs** (komplette Pipeline Audio→Analyse→Pacing→Render erfolgreich)

---

## KRITISCH (1)

### BUG-051: VideoLibraryViewModel Semaphore Double-Release
**Datei:** `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs:72-76,129-133`

Wenn `_loadGate.WaitAsync(0)` false zurueckgibt (Semaphore belegt), wird im finally trotzdem `Release()` aufgerufen fuer eine Semaphore die ein anderer Thread haelt. Zwei gleichzeitige Video-Loads koennen laufen → UI-Crash.

---

## HOCH (5)

### BUG-052: SmartDirector CLAP laed nie
**Datei:** `src/pb_studio/ai/smart_director.py:303-304`
`CLAPPyTorch` hat kein `active_provider` Attribut → AttributeError → CLAP-Loading scheitert IMMER still. Mood-Analyse gibt immer neutral zurueck.

### BUG-053: ProductionViewModel ETA-Flicker
**Datei:** `PBStudio.UI/ViewModels/ProductionViewModel.cs:330`
Waehrend Render ueberschreibt `OnGpuStatusReceived` alle 5s die EtaText mit GPU-Info statt Render-Fortschritt.

### BUG-054: PythonBridgeService Watchdog kann StopAsync rueckgaengig machen
**Datei:** `PBStudio.UI/Services/PythonBridgeService.cs:48,210-231`
Watchdog ruft `StartAsync()` → setzt `_isStopping=false` → Backend wird nach App-Schliessung neu gestartet.

### BUG-066: Pacing Energy-Modulation wirkungslos bei pacing=5
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:254-266`
Bei pacing=5 (schnellstes): `pacing_bias=0.0`, `speed_factor` wird negativ → clamp auf 0 → ALLE Clips bekommen min_clip_length. Energy-Slider hat NULL Effekt.

### BUG-067: generate_cut_list_with_stems nutzt falsche Audio-Dauer
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:1145`
`duration = filtered[-1].time` = letzter Trigger-Zeitpunkt statt Audio-Gesamtdauer. Letzte Sekunden des Tracks koennten keine Cuts bekommen.

---

## MITTEL (14)

### BUG-055: engine.py Concat schreibt nur Dateinamen
`src/pb_studio/video/engine.py:327` — `seg.name` statt vollstaendiger Pfad. Nur relevant wenn VideoGenerator direkt aufgerufen wird (nicht ueber API).

### BUG-056: SSEClient Race bei schnellem Stop+Start
`PBStudio.UI/Services/SSEClient.cs:53-58` — Alter CTS disposed bevor laufende Tasks cancellation bemerken.

### BUG-057: ffprobe/ffmpeg als bare command
`backend/routers/audio_router.py:380`, `video_router.py:284,335` — Nutzt `"ffprobe"` statt `config.ffprobe_path`. Funktioniert aktuell weil auf PATH, bricht auf anderen Systemen.

### BUG-058: DJ-Mix-Analyzer falsche Zeitstempel
`src/pb_studio/audio/dj_mix_analyzer.py:118` — `chroma_times[i]` mit RMS-Index = falsches Windowing-Mapping.

### BUG-059: VRAMBudgetManager _evict_for_space ohne Lock
`src/pb_studio/core/vram_budget_manager.py:569` — Race-Condition bei externem Aufruf aus VRAMArbiter.

### BUG-060: AudioService falsches Keyword-Argument
`src/pb_studio/services/audio_service.py:34` — `StemSeparator(output_dir=...)` existiert nicht. Nur relevant wenn AudioService.separate() aufgerufen wird (Router umgeht AudioService).

### BUG-061: pacing_router Timeline ohne Lock
`backend/routers/pacing_router.py:179,182` — `state.current_timeline` direkt statt `get_timeline_snapshot()`.

### BUG-068: ConfigManager Shallow-Copy von DEFAULTS
`src/pb_studio/config_manager.py:69` — `self.DEFAULTS.copy()` ist shallow. Direkte Mutation von nested Dicts korrumpiert Klassen-Defaults.

### BUG-069: render_engine.py + final_renderer.py Double-Quote Concat
`src/pb_studio/rendering/render_engine.py:136`, `final_renderer.py:179` — Nutzen `"` statt `'` in FFmpeg concat. Inkonsistent mit render_service.py Fix.

### BUG-070: render_service.py Path(None) Crash
`src/pb_studio/rendering/render_service.py:367` — `Path(None)` → TypeError statt sauberer Fehler.

### BUG-071: render_engine.py _active_processes nicht thread-safe
`src/pb_studio/rendering/render_engine.py:209` — List ohne Lock bei concurrent render()+kill_zombie_processes().

### BUG-072: vector_store normalize_L2 mutiert Caller-Array
`src/pb_studio/data/vector_store.py:140` — `faiss.normalize_L2` aendert Embedding in-place. Caller bekommt normalisiertes Array zurueck.

### BUG-073: video_specialist Similarity-Score ueberschreitet [0,1]
`src/pb_studio/ai/video_specialist.py:427` — Fallback-Suche normalisiert Vektoren nicht vor Dot-Product → Scores >1.0 moeglich.

### BUG-074: generation_service.py crasht wenn PyQt6/VideoGenerator fehlt
`src/pb_studio/services/generation_service.py:19-20,47` — `VideoGenerator()` und `Worker()` werden aufgerufen obwohl Import fehlschlug (=None).

---

## NIEDRIG (12)

### BUG-062: Leerer audio_path passiert Render-Validierung
`backend/schemas/render_schemas.py:41`

### BUG-063: app_state Shallow-Copy erlaubt unsync. Mutation
`backend/app_state.py:120-128`

### BUG-064: TimelineView Spinner dreht endlos
`PBStudio.UI/Views/TimelineView.xaml:27-35`

### BUG-065: MainViewModel PropertyChanged von Background-Thread
`PBStudio.UI/ViewModels/MainViewModel.cs:51,219`

### BUG-075: MainViewModel InitializeAsync ohne try/catch
`PBStudio.UI/ViewModels/MainViewModel.cs:54-73` — Unobserved Exception bei Startup-Fehler.

### BUG-076: smart_director np.random nicht thread-safe
`src/pb_studio/ai/smart_director.py:1173` — Globaler numpy Random-State.

### BUG-077: smart_director _fill_timeline_gaps bricht bei Zero-Duration-Clip
`src/pb_studio/ai/smart_director.py:1307-1310`

### BUG-078: export_handler SMPTE-Drift bei 29.97fps
`src/pb_studio/pacing/export_handler.py:253` — `int(fps)` schneidet 29.97→29 ab.

### BUG-079: export_handler unique_clips zaehlt immer 0
`src/pb_studio/pacing/export_handler.py:41` — Falscher Dict-Key `clip_path` statt `video_path`.

### BUG-080: moondream get_moondream() Singleton nicht thread-safe
`src/pb_studio/ai/moondream_pytorch.py:403-407`

### BUG-081: video_specialist np.linspace mit count=0
`src/pb_studio/ai/video_specialist.py:350` — Zero/negative Duration Clips → leeres Array.

### BUG-082: COM Memory Leak in backend/config.py
`backend/config.py:43-51` — SHGetKnownFolderPath CoTaskMemFree fehlt (einmalig ~100 Bytes).

---

## DEAD CODE (3)

| Datei | Was |
|-------|-----|
| `PBStudio.UI/Models/RenderConfig.cs` | `RenderConfigModel` nirgends referenziert |
| `PBStudio.UI/Services/NavigationService.cs` | Event hat keinen Subscriber |
| `src/pb_studio/ai/clap_wrapper.py:433-451` | `encode_text()` gibt immer None zurueck |

---

## CROSS-LAYER CONTRACTS: SAUBER

21 Endpoints Feld-fuer-Feld geprueft. **0 kritische Mismatches.** 3 mittlere:
- float-Precision (C# float 32bit vs Python float 64bit) — vernachlaessigbar fuer Wertebereiche
- Nullable-Defaults (C# null vs Python []) — Pydantic sendet immer, kein Problem
- AudioClipModel.Key null→"" Konvertierung benoetigt Aufmerksamkeit

## XAML BINDINGS: SAUBER

Alle 8 Views, jeder Binding-Pfad verifiziert. **0 broken Bindings.** Alle Converter registriert, alle Commands vorhanden, alle Properties existieren.

## ASYNC/DISPOSAL: SAUBER

- 0 async void (ausser Framework-Override)
- Alle IDisposable korrekt disposed via DI
- Alle CancellationToken korrekt genutzt
- Alle Event-Subscriptions gepaart mit Unsubscriptions
- 0 Deadlocks gefunden

## E2E RUNTIME-TEST: SAUBER

Komplette Pipeline mit echtem Backend getestet:
- Projekt erstellen → Audio Import → Analyse (BPM/Key/Beats/Struktur) → Video Import → Video Analyse → Pacing (31 Cuts) → Render (h264_amf, 640x360, 31MB) → Persistenz → Fehlerpfade
- **0 Runtime-Bugs, 0 Warnings**
- DB-Eintraege korrekt, Temp-Files aufgeraeumt, Persistenz funktioniert

---

## RUNDE 3: BISHER UNGEPRUEFTE DATEIEN (40+ neue Dateien)

### HOCH (4 neue)

#### BUG-083: Orchestrator _run_worker_sync umgeht Worker-Signals
**Datei:** `src/pb_studio/workers/orchestrator.py:243`
Ruft `worker._execute()` direkt auf statt `worker.run()`. Dadurch werden `finished`- und `error`-Signals NIE emittiert. Progress-Forwarding in Generation-Pipeline ist broken.

#### BUG-084: video_renderer generate_preview INVERTIERTER isinstance-Check
**Datei:** `src/pb_studio/video/video_renderer.py:235`
`isinstance(c, dict)` Branch nutzt `getattr()` statt `c.get()`. Dict-Cuts geben immer start_time=0 zurueck → Filter laesst ALLES durch → Volle Video-Laenge statt Preview-Fenster.

#### BUG-085: ThreadPool Worker injiziert ungewollte kwargs
**Datei:** `src/pb_studio/core/thread_pool.py:32`
`Worker.__init__` fuegt `progress_callback` und `status_callback` in kwargs ein. Funktionen die diese Parameter NICHT akzeptieren crashen mit TypeError.

#### BUG-086: concat_worker Unix-Escaping auf Windows
**Datei:** `src/pb_studio/workers/generation/concat_worker.py:158-159`
Single-Quote-Escaping (`'\\''`) ist Unix-Shell-Konvention. Auf Windows mit Pfaden die `'` enthalten wird die FFmpeg concat-Liste malformed.

### MITTEL (8 neue)

#### BUG-087: audio_import_worker Temp-WAV-Leak
**Datei:** `src/pb_studio/workers/audio/audio_import_worker.py`
`cleanup()` wird vom Orchestrator NIE aufgerufen. Temp-WAV-Dateien akkumulieren bei vielen Imports.

#### BUG-088: streaming_analyzer blockiert bei grossen Dateien
**Datei:** `src/pb_studio/audio/streaming_analyzer.py:262`
SHA-256 ueber komplette Datei (z.B. 2.5GB fuer 4h Audio) blockiert den Analyse-Thread.

#### BUG-089: waveform_cache Thread-Safety-Luecken
**Datei:** `src/pb_studio/audio/waveform_cache.py:248,264`
`get_entry_info()` und `__contains__` lesen ohne Lock. File-I/O innerhalb Lock (Zeile 76) blockiert alle Cache-Ops.

#### BUG-090: worker_registry ohne Thread-Schutz
**Datei:** `src/pb_studio/workers/worker_registry.py:57-84`
`register_worker`, `get_worker`, `unregister_worker` ohne Lock. Dict-Corruption bei gleichzeitigem Zugriff moeglich.

#### BUG-091: logging_setup doppelte Handler + relativer Pfad
**Datei:** `src/pb_studio/utils/logging_setup.py:7,27,32`
Relative `Path("logs")` haengt vom CWD ab. Wiederholte `setup_logging()` Aufrufe fuegen doppelte Handler hinzu → Nachrichten 2x, 3x, ...

#### BUG-092: audio_embedding_worker CLAP_DURATION Mismatch
**Datei:** `src/pb_studio/workers/audio/audio_embedding_worker.py:121`
`CLAP_DURATION` fuer Padding vs `CHUNK_DURATION_SEC` fuer Chunking koennen unterschiedlich sein → Shape-Mismatch.

#### BUG-093: pacing_worker O(n*m) Downbeat-Matching
**Datei:** `src/pb_studio/workers/generation/pacing_worker.py:192`
Linearer Scan durch Set statt `in`-Operator oder bisect. Bei vielen Beats langsam.

#### BUG-094: stem_runner sys.path-Manipulation
**Datei:** `src/pb_studio/audio/stem_runner.py:6-7`
Manuelles `sys.path.insert` widerspricht IRON RULE 7 (PYTHONPATH=src). Bricht bei anderer Verzeichnisstruktur.

### NIEDRIG (5 neue)

#### BUG-095: render_worker nicht-reproduzierbare Renders
**Datei:** `src/pb_studio/workers/generation/render_worker.py:199`
`random.uniform` ohne Seed → jeder Render produziert anderes Ergebnis.

#### BUG-096: anchor_features doppeltes Audio-Laden
**Datei:** `src/pb_studio/audio/anchor_features.py:73`
Audio wird 2x geladen (einmal librosa, einmal SpectralAnalyzer). Verschwendet RAM und CPU.

#### BUG-097: thumbnail_generator ueberspringt clip_id=0
**Datei:** `src/pb_studio/video/thumbnail_generator.py:84`
`if not clip_id` ist True fuer clip_id=0. Sollte `clip_id is None` sein.

#### BUG-098: encoder_utils AMF-Cache nie invalidiert
**Datei:** `src/pb_studio/video/encoder_utils.py:109`
`_amf_available` wird permanent gecacht. Driver-Crash mid-Session wird nicht erkannt.

#### BUG-099: ThreadPoolManager Singleton nicht thread-safe
**Datei:** `src/pb_studio/core/thread_pool.py:54-57`
Kein Lock bei Singleton-Erstellung. Zwei Threads koennten zwei Instanzen erzeugen.

---

## EHRLICHES FAZIT

**52 Funde insgesamt** (1 kritisch, 9 hoch, 22 mittel, 17 niedrig, 3 dead code).

3 Audit-Runden, 8 Experten-Agenten, 120+ Dateien gelesen, E2E-Runtime-Test durchgefuehrt.

Die groesste Entdeckung in Runde 3: Ein **komplettes Workers-Subsystem (18 Dateien)** war in keinem bisherigen Audit enthalten. Dort befinden sich 4 der 9 HOCH-Bugs, darunter der Orchestrator-Bug (BUG-083) der Worker-Signals komplett unterbricht.

**Soll ich die Bugs fixen? Empfohlene Reihenfolge:**
1. BUG-051 (KRITISCH) — Semaphore Double-Release
2. BUG-083 (HOCH) — Orchestrator Worker-Signals
3. BUG-084 (HOCH) — Preview Filter invertiert
4. BUG-066 (HOCH) — Pacing Energy bei pacing=5
5. BUG-052 (HOCH) — CLAP active_provider
