# Consulting Team Review — PB Studio Deep Bug-Hunt & Tech-Debt

> **Auftrag:** Tiefen-Audit der PB-Studio-Codebase (147 Quelldateien: `src/pb_studio/*`, `backend/*`, `PBStudio.UI/*`) auf reale Bugs, plus Tech-Debt-Kategorisierung.
> **Methode:** 7 parallele Forensik-Agenten (je 1 Subsystem), statische Analyse (pyflakes/AST/Pattern-Scans), plus manuelle Verifikation der 9 schwersten Befunde am Quellcode.
> **Reversibilität:** two-way door (Fixes sind lokal, kein Architektur-Umbau nötig).
> **Datum:** 2026-07-24 · **Scope-Grenze:** Router-Module (`render_router`, `events_router`), `GPULockMiddleware`, `ApiClient.cs`/`IApiClient.cs` waren nicht im gespiegelten Stand — Backend↔C#-Contract nur teilweise prüfbar.

---

## Executive Summary

Die Codebase ist an der **Oberfläche diszipliniert** (IRON RULES R1/R2/R5 im produktiven Pfad eingehalten, keine SQL-Injection, keine bare-except-Schlucker, keine mutable Default-Args) — aber **semantisch trägt sie 31 reale Bugs**, davon 2 mit Datenverlust-Potenzial und 6 mit Feature-/Reliability-Blockade. Das behauptete „Production / Verified"-Label (CLAUDE.md, Stand 2026-03-16, „186 passed") ist **nicht deckungsgleich mit dem tatsächlichen Zustand**: die Testsuite grün, aber die schwersten Bugs liegen in Pfaden, die die Tests nicht abdecken (Crash-Persistenz von FAISS, langer MP3-Mix, Cancel-danach-Render, `duration_limit`-Preview, VRAM-Accounting über Task-Grenzen).

Drei Muster erklären fast alle Befunde: **(1) Fehler werden geschluckt statt propagiert** (FFmpeg-Encode, Fabrikat-Rückgaben, Retry-Decorators ausgehebelt), **(2) globaler/prozessweiter Zustand ohne Serialisierung** (monkeypatch von `ort.SessionOptions.__init__`, unlocked native LHM-Zugriff, Thread-pro-Embedding), **(3) VRAM-Accounting divergiert von physischer Realität** (reserve ohne release/commit, Callbacks auf Error-Pfad verloren). 

**Recommendation: GO-mit-Modifikation** — die 2 Critical + 6 High vor jedem „Production"-Anspruch fixen. Confidence: **HIGH** für die verifizierten 9, **MEDIUM** für die übrigen (Agenten-Reasoning solide, aber nicht alle einzeln am Laufzeitverhalten reproduziert).

**Befund-Verteilung:** 🔴 2 Critical · 🟠 6 High · 🟡 14 Medium · 🟢 9 Low (inkl. 3 in totem Legacy-Code).

---

## Findings

### 🔴 Critical

**C1 — FAISS-Index-Persistenz: Race + unbounded Threads → Datenverlust bei Crash & OOM bei Bulk-Import** (Rolle: Domain Expert / Data)
- **Was:** `vector_store.add_embedding()` klont bei *jedem* Embedding den kompletten Index (`faiss.clone_index`) und startet einen *neuen* Daemon-Thread, der dieselbe `index_path` schreibt.
- **Warum kritisch:** `src/pb_studio/data/vector_store.py:203-211` + `:452-481`. `threading.Lock` garantiert keine FIFO-Reihenfolge → beim Import von N Clips gewinnt der Thread, der den Lock *zuletzt* bekommt, oft mit einem *frühen* Snapshot. In-Memory bleibt korrekt, aber bei Crash/Kill nach dem Import liegt auf Platte ein veralteter Snapshot → **die meisten importierten Embeddings sind beim Neustart weg** — genau das, was die „save nach jedem Embedding"-Logik verhindern sollte. Zusätzlich: pro Add ein Voll-Klon (~46 MB bei 10k×1152-dim) + bis zu tausende Live-Threads → RAM-Explosion und O(N²)-I/O.
- **Counter-Proposal:** Ein einziger serialisierter Writer-Thread mit „latest-snapshot-wins"-Queue (überholte Snapshots verwerfen) + monoton steigende `seq`, `os.replace` nur wenn keine neuere `seq` schon landete. Debounce: höchstens alle paar Sekunden / alle K Adds speichern, einen Worker wiederverwenden statt Thread-pro-Add. *(Verifiziert am Code.)*

### 🟠 High

**H1 — `duration_limit`-Renders (Preview / gekürzt) erzeugen einen Riesen-Endclip** (Rolle: Domain Expert / Pacing)
- **Was:** Cuts werden gegen `target_duration = duration_limit or total_duration` gebaut (`pacing_service.py:587,820`), aber `_finalize_cut_list` bekommt an *allen* Return-Sites `total_duration` (volle Songlänge) übergeben (`:699,702,712,1027,1030,1038,1049`), und `_stretch_last_cut_to_audio` streckt den letzten Cut auf diesen Wert.
- **Warum kritisch:** `duration_limit` ist ein exponierter Tool-Arg (`tool_registry.py:811`, Stresstest übergibt `10.0`). Bei `duration_limit=10`, `total_duration=200` stoppen die Cuts bei 10 s, aber der letzte Cut wird auf **end_time=200** gestreckt → ~190 s aus einem einzelnen kurzen Clip, out-point weit hinter der physischen Cliplänge. Preview- und Kurz-Renders sind faktisch kaputt.
- **Counter-Proposal:** `_finalize_cut_list(cut_list, target_duration)` mit demselben Budget füttern, gegen das die Cuts erzeugt wurden. *(Verifiziert am Code.)*

**H2 — `VideoGenerator.generate_from_timeline()` resettet `cancel_flag` nie → jeder Render nach einem Cancel ist ein stiller No-op** (Rolle: Risk Officer / Video)
- **Was:** `generate()` setzt `self.cancel_flag = False` (`engine.py:53`); `generate_from_timeline()` (`:389`) tut das nicht, prüft aber `self.cancel_flag` bei Clip 0 (`:424`).
- **Warum kritisch:** `generation_service.py:20` hält *eine* wiederverwendete Instanz (`self.engine = VideoGenerator()`). Nach einem Cancel bleibt `cancel_flag=True`; der nächste Timeline-Render kehrt sofort mit `{"cancelled": True}` zurück, **ohne je ein Video zu erzeugen** — bis Prozess-Neustart.
- **Counter-Proposal:** `self.cancel_flag = False` als erste Zeile von `generate_from_timeline()` (spiegelt `generate()`). *(Verifiziert am Code.)*

**H3 — `_ffmpeg_extract` schluckt Encode-Fehler; Segment wird bedingungslos angehängt → korrupte/leere Concat-Inputs** (Rolle: Risk Officer / Video)
- **Was:** `engine.py:296-318` — Software-Encode und HW→SW-Fallback prüfen `returncode` nicht, `stderr=subprocess.DEVNULL`. `_render_segments`/`generate_from_timeline` hängen `out_name` unabhängig vom Erfolg an (`:243,:441`).
- **Warum kritisch:** Ein fehlgeschlagener Segment-Encode (z. B. `-ss` hinter EOF, Disk voll) erzeugt eine fehlende/0-Byte-`seg_XXXX.mp4`, die dann in `-f concat` läuft → opaker „FFmpeg concat failed" oder korrupter/kurzer Output. Die eigentliche Fehlerursache ist verloren (DEVNULL).
- **Counter-Proposal:** `RuntimeError` werfen, wenn der finale Encode `returncode!=0` liefert oder das Output-File fehlt/leer ist; Fallback-`stderr` per PIPE loggen; `out_name` erst nach verifiziertem Erfolg anhängen. *(Verifiziert am Code.)*

**H4 — `system_monitor._query_temperature_alternative` greift ohne Lock nativ auf LibreHardwareMonitor zu → Data-Race / nativer Crash** (Rolle: Risk Officer / Core)
- **Was:** `_collect_lhm_stats` iteriert `self.computer.Hardware` + `hardware.Update()` *mit* `_lhm_lock` (`system_monitor.py:182-187`); `_query_temperature_alternative` tut dasselbe *ohne* Lock (`:355,371,378`), läuft im Background-Thread `_bg_refresh_ps_stats`.
- **Warum kritisch:** Auf AMD-Adrenalin-Systemen ist `gpu_temp==0.0` der Normalfall → der Fallback feuert bei fast jedem Refresh. Zwei Threads, die gleichzeitig `Update()` auf denselben nativen LHM-Objekten aufrufen, korrumpieren LHMs interne Sensor-Buffer → Garbage-Werte oder harter nativer Access-Violation-Crash des Backends. *(Confidence MEDIUM: native Thread-Safety-Inferenz — sicher ein Race, „Crash" ist die wahrscheinliche, nicht garantierte Folge.)*
- **Counter-Proposal:** Den `self.computer.Hardware`-Durchlauf in `_query_temperature_alternative` mit `with self._lhm_lock:` umschließen. *(Verifiziert am Code.)*

**H5 — `streaming_analyzer` fällt bei MP3 auf `librosa.load(offset=…)` pro Chunk zurück → O(n²), langer Mix „hängt"** (Rolle: Analyst / Audio)
- **Was:** `streaming_analyzer.py:352-361` — schlägt `_load_chunk_soundfile` fehl (soundfile ohne MP3-Support, laut eigenem Kommentar der Erwartungsfall), lädt jeder Chunk via `librosa.load(offset=…)`.
- **Warum kritisch:** Mit dem audioread-Backend dekodiert-und-verwirft Offset-Seeking ab Dateianfang → Chunk *i* kostet O(i·chunk). Für einen 90-min-MP3 (~215 Chunks) ist das Gesamt-Dekodieren O(n²) → die Analyse, die für lange Mixe *leicht* sein sollte, blockiert minutenlang. Das ist exakt der Kern-Use-Case (lange DJ-Mixe, oft MP3).
- **Counter-Proposal:** Einen persistenten Decoder für die ganze Datei öffnen (soundfile-Block-Reads oder ein audioread-Pass) und sequentiell vorwärts streamen; oder MP3→WAV einmal vor-transkodieren (wie `analyzer.py` es bereits tut). *(Verifiziert am Code.)*

**H6 — VRAM-Reservierungen werden über Task-Grenzen nie freigegeben → falsche OOM trotz physisch freiem VRAM** (Rolle: Domain Expert / Core)
- **Was:** `dependencies.with_gpu_task` ruft im `finally` `cancel_reservation(model_id)` — das ist nach `commit()` ein No-op (`vram_budget_manager.py:741`, greift nur wenn `is_reserved and not is_loaded`). Für Modelle, die unter `with_gpu_task` laufen, aber nie `manager.release` aufrufen (raft/moondream/clap/siglip-Wrapper), bleibt `mb` für immer committed (`dependencies.py:154-157`). Zusätzlich reserviert `video_embedder.py:109` SigLIP-2 mit `reserve()` **ohne** `commit()`/`release()` und ohne Unload-Pfad.
- **Warum kritisch:** `_committed_mb` akkumuliert über distinkte `model_id`s bis die Retry-Schleife (`dependencies.py:61-70`) `VRAMAllocationError` wirft — obwohl VRAM physisch frei ist. Selbstheilung nur zufällig, wenn ein späterer `force=True`-Reserve die Phantome evakuiert.
- **Counter-Proposal:** Im `finally` `manager.release(model_id)` aufrufen, wenn der Task committed hat (und das Modell nicht persistent im ModelLoader lebt); `cancel_reservation` nur für den Not-yet-committed-Frühfehler-Fall. `VideoEmbedder`: nach `to(device)` `commit()` + `unload()`-Methode mit `release()` als `unload_callback` (RAFT-Muster spiegeln). *(Verifiziert am Code.)*

### 🟡 Medium

**M1 — `vram_budget_manager.update_max_vram` verliert Eviction-Callbacks auf dem Raise-Pfad** (Core) — `vram_budget_manager.py:399-403`. `_evict_for_space` dekrementiert `_committed_mb` und sammelt physische `unload_callback`s, die erst *nach* dem `with`-Block (`:413`) laufen. Reicht die Eviction nicht (Rest ist CRITICAL), feuert `raise` *innerhalb* des Locks vor `:413` → Modelle als frei verbucht, aber physisch noch im VRAM → späteres `reserve()` über-committet → echter DirectML-OOM. **Fix:** Callbacks vor dem `raise` invoken oder Accounting zurückrollen.

**M2 — `reserve(force=True)` doppelt-zählt VRAM, wenn ein Eviction-Callback wirft** (Core) — `vram_budget_manager.py:637-643`. Neues Modell ist schon reserviert; wirft danach ein evicted `unload_callback()`, re-committet der Except-Handler das evicted Modell, während die Reservierung des neuen steht → `committed+reserved` > nutzbarer VRAM, `available_vram_mb` klemmt dauerhaft auf 0. **Fix:** Bei Callback-Fehler die frisch erteilte Reservierung stornieren oder evicted `mb` nicht re-addieren.

**M3 — `clap_wrapper.classify_audio` liefert *fabrizierte* Ergebnisse im ONNX-Modus** (AI) — `clap_wrapper.py:197`. Wenn CLAP-ONNX-Files existieren, ist `_initialized=True` und `_pytorch_fallback=None` → `return [(labels[i % len(labels)], 1.0/(i+1)) …]` — deterministischer Müll (Labels in Dateireihenfolge, Fake-Scores), an Aufrufer als echte Mood/Genre/Instrument-Tags gemeldet. Diese Tags steuern Pacing & semantisches Matching → Cut-Auswahl still falsch, ohne Fehler. Verletzt „no silent fake success". **Fix:** `NotImplementedError`/`[]` statt Mock. *(Verifiziert.)*

**M4 — `smart_director._fill_timeline_gaps` kann endlos drehen (Thread-Hang)** (AI) — `smart_director.py:1342`. Der `src_avail <= 0.001`-Zweig macht `continue` ohne `pos` zu bewegen und ohne Iterations-Grenze. Sind alle recycelbaren Clips ~0 s lang (kaputte Library), recycelt die Schleife ewig, `pos < gap_end` wird nie falsch → `generate_timeline()` hängt den Worker-Thread. **Fix:** No-Progress-Detection (ein voller Pass über alle Quellen ohne nutzbaren Clip → break) + Iterations-Cap.

**M5 — `_stretch_last_cut_to_audio` re-cappt nicht auf physische Cliplänge** (Pacing) — `pacing_service.py:171`. Der Stretch verlängert `end_time` bedingungslos, während `metadata["clip_start"]` fix bleibt. Ist der letzte Clip physisch kürzer als die gestreckte Spanne, liest der Render hinter EOF → eingefrorener letzter Frame / FFmpeg-Tail-Fehler. **Fix:** Reale Cliplänge nachschlagen und Spanne clampen. *(Unabhängig von H1.)*

**M6 — `advanced_pacing_engine._plan_emotional_sync`: ZeroDivisionError bei `bpm==0`** (Pacing) — `advanced_pacing_engine.py:545`. `.get("bpm", 120)` defaultet nur bei *fehlendem* Key; ein vorhandenes `bpm=0.0` (stille/fehlgeschlagene Beat-Detection) erreicht `(60.0/bpm)*4` → Crash. Der EMOTIONAL_SYNC-Branch guardet nicht (im Gegensatz zu hybrid/beat). **Fix:** `bpm = self.audio_analysis.get("bpm") or 120.0`.

**M7 — `downbeats` bleibt auf dem Cache-Pfad leer → Downbeat-Gewichtung still tot** (Pacing) — `advanced_pacing_engine.py:1033-1034`. `downbeats` wird nur im BeatDetector-Branch gesetzt; der produktive `_pre_cached_beats`-Pfad lässt es `[]`, also `is_downbeat=False` für jeden Beat → der 1.0-vs-0.7-Downbeat-Boost feuert nie. Feature inert im realen Pipeline. **Fix:** Downbeats auch auf dem Cache-Pfad ableiten/injizieren.

**M8 — `separator.py` monkeypatcht `ort.SessionOptions.__init__` global, nicht re-entrant** (Audio) — `separator.py:184-198`. Patch-Fenster läuft ungelockt. Interleaven zwei `separate()`-Aufrufe, speichert der 2. das bereits gepatchte `__init__` als „original"; die Restores lassen den Wrapper installiert mit `_original=None` → nächstes `ort.SessionOptions()` *irgendwo* (video/moondream/RAFT) ruft `None(...)` → TypeError für den Rest der Prozess-Lebenszeit. **Fix:** Reference-counted Lock um apply/restore, oder Optionen explizit konstruieren statt global patchen.

**M9 — `separator.separate()` Progress-Callback ist tot; `stem_progress`-SSE feuert nie** (Audio) — `separator.py:239-251`. Kein Aufrufer übergibt `callback`/`on_progress` (`audio_service.py:55`, `audio_stem_worker.py:107` — Worker definiert `progress_cb` und übergibt ihn nie). Während 2–5-min-Separation springt die UI 20 %→90 % ohne Update → wirkt hängend. **Fix:** `progress_cb` durchreichen.

**M10 — `beat_detector`: `duration`-Limit auf dem BeatNet-Pfad ignoriert** (Audio) — `beat_detector.py:249`. `detect_beats(…, duration=D)` wird nur vom librosa-Fallback beachtet; BeatNet verarbeitet für Files ≤600 s die *ganze* Datei und liefert Beats jenseits von D (+ volle Inferenzkosten). **Fix:** Bei gesetztem `duration` vor Inferenz slicen oder Output-Beats auf `t<=duration` kürzen.

**M11 — `feedback_logger` fährt `BEGIN IMMEDIATE` auf geteilter Connection ohne Conn-Lock über die Transaktion** (Data/Brain) — `feedback_logger.py:66-81`. `weights_conn` ist eine geteilte Connection (`check_same_thread=False`); zwei gleichzeitige Feedback-Events → 2. `BEGIN IMMEDIATE` wirft „cannot start a transaction within a transaction", der Except macht `ROLLBACK` und verwirft die 85 Bucket-Updates des *ersten* Threads → verlorenes/partielles Learning. **Fix:** `_conn_lock` über den ganzen BEGIN…COMMIT-Block halten.

**M12 — `embedding_cache.store()` schreibt `.npy` in-place (kein temp+atomic) → Crash mittendrin poisont den Cache** (Data) — `embedding_cache.py:104-105`. Kill während `np.save` lässt `target` truncated, während der DB-Index-Row weiter darauf zeigt; `lookup()` prüft nur `is_file()` → späteres `np.load` crasht/liefert Garbage. **Fix:** `.npy.tmp` schreiben, dann `os.replace()`.

**M13 — Backend-SSE-Live-Log verliert jeden Log aus Worker-Threads** (Backend) — `dependencies.py:273`. `SSELogHandler.emit` nutzt `asyncio.get_running_loop()` (wirft in Non-Loop-Threads), obwohl der threadsafe-Pfad (`:218`) den globalen `_main_loop` verwendet. Alle Heavy-Work-Logs (Render/Analyse via `to_thread`) landen im RuntimeError-Zweig → `loop=None` → nie publiziert. Das WPF-Live-Log zeigt keinen Render-/Analyse-Fortschritt. **Fix:** `loop = _main_loop; if loop and not loop.is_closed(): loop.call_soon_threadsafe(...)`. *(Verifiziert.)*

**M14 — `encoder_utils` Software-Fallback nutzt `libx264/libx265/libsvtav1` (IRON RULE R4)** (Video) — `encoder_utils.py:293-402`. Ist `check_amf_available()` (evtl. flakiger Funktions-Probe) `False`, emittiert *jeder* Export/Preview libx264 — verletzt „AMD/AMF only". **Fix:** Laut R4 laut fehlschlagen statt still auf libx264 zu fallen, oder hinter explizites Opt-in-Flag (analog `ALLOW_CPU_FALLBACK` in raft.py). *(Regel-Verletzung nur im Fallback-Pfad — daher Medium, nicht High.)*

### 🟢 Low

**L1 — `advanced_pacing_engine._snap_cuts_to_subtrack_boundaries` mutiert Cuts in-place, kann Duplikate/~0 s-Cuts erzeugen** — `:1362`. Snappen auf einen belegten Anchor kollidiert zwei Cuts → Verletzung `min_cut_interval`, ~0 s-Span wird still gedroppt (Cut-Verlust). **Fix:** Nach Snap re-sortieren + `_enforce_minimum_interval` erneut; belegte Anchors überspringen.

**L2 — `clip_selector` inkonsistenter Default-`clip_id` (`""` vs `"unknown"`) schwächt Anti-Repeat-Blacklist** — `:454` vs `:517/528/709`. Für id-lose Clips mischen sich die Keys → derselbe Clip kann back-to-back kommen. **Fix:** Ein Sentinel überall.

**L3 — `model_loader._load_onnx_split` crasht bei `None`-Split-Paths** — `model_loader.py:355`. `Path / None` → `TypeError` statt sauberem „not found" für Custom-Specs. **Fix:** Guard vor Pfadbau.

**L4 — `compression.decompress_array` crasht bei truncated Payload** — `compression.py:19`. `np.frombuffer` wirft, wenn Länge kein Vielfaches von 4 (korruptes Cache-Blob). **Fix:** `len % 4 == 0` validieren.

**L5 — `moondream_pytorch` monkeypatcht `F.scaled_dot_product_attention` prozessweit, verschachtelt bei Reload** — `moondream_pytorch.py:181`. Nie in `unload()` restauriert; jeder load-Zyklus wrappt neu. Latent (heute harmlos), aber prozessweiter Seiteneffekt auf SigLIP/CLAP. **Fix:** „already patched"-Flag + Restore in `unload()`.

**L6 — `waveform_analyzer.get_time_axis` nutzt `self.sr`, während lange Files bei 11025 Hz geladen wurden** — `:254-273`. Timeline eines langen Mix auf halbe Dauer gestaucht. Latent (kein aktiver Consumer). **Fix:** Effektive `sr` zurückgeben/parametrisieren.

**L7 — `waveform_analyzer.get_downsampled_waveform` überschießt `target_points` um bis zu 2×** — `:241`. `len//target_points` floort auf 1. **Fix:** `ceil`, oder auf exakt `target_points` resamplen.

**L8 — `render_service` finaler Subprozess `stdout=PIPE` wird nie gedrained** — `render_service.py:603`. Latent (File-Output schreibt nichts auf stdout), aber Deadlock-Risiko bei stdout-emittierendem ffmpeg. Inkonsistent zu `_transcode_clip` (DEVNULL). **Fix:** `stdout=DEVNULL`.

**L9 — `render_service` fixer Temp-Name `concat_list.txt` kollidiert bei gleichzeitigen Renders in dasselbe `output_dir`** — `:176`. Zwei Renders überschreiben/löschen sich gegenseitig. **Fix:** Per-Render-Subdir/uuid.

#### 🟢 Low — in totem/Legacy-Code (aktuell nicht erreichbar)

Das gesamte `src/pb_studio/workers/`-Paket wird **von keinem Modul außerhalb `workers/` importiert** (verifiziert: nur `workers/__init__.py` referenziert `orchestrator`; kein Import aus `backend/` oder `src/`). Es ist ein PyQt6-Ära-Relikt, das die aktuelle C#-WPF+FastAPI-Architektur nicht mehr aufruft. Ehrliche Einstufung: reale Defekte, aber unerreichbar — daher Low.

**D1 — `orchestrator._run_worker_sync` gibt `worker.run()` zurück, das immer `None` liefert** — `orchestrator.py:238` + `base_worker.py:131` (kein `return`). Alle `import_result.temp_wav_path`-Zugriffe würden `AttributeError` werfen; `run()` schluckt zudem Worker-Exceptions. **Fix:** `BaseWorker.run()` `return result`, oder `_execute()` aufrufen.

**D2 — `audio_stem_worker`/`video_motion_worker` leaken VRAM-Reservierung bei Cancel/Frühfehler** — `audio_stem_worker.py:70`, `video_motion_worker.py:86`. `reserve()` vor dem try/finally; `_check_cancelled()`/`VideoCapture`-Fehler davor leaken die Reservierung. **Fix:** Ab `reserve()` in try/finally wrappen.

---

## Tech-Debt-Kategorisierung (engineering:tech-debt)

| Kategorie | Debt-Item | Belege | Impact | Aufwand | Priorität |
|-----------|-----------|--------|--------|---------|-----------|
| **Design Debt** | Fehler werden geschluckt statt propagiert (kein einheitliches Error-Contract) | H3, M3, L4, D1, project_repository (L→retry ausgehebelt) | Bugs werden unsichtbar, Debugging teuer | M | **P0** |
| **Design Debt** | Prozessweiter Mutable-Global-State ohne Serialisierung | M8 (`ort.SessionOptions` monkeypatch), H4 (LHM), L5 (SDPA) | Nicht-lokale, schwer reproduzierbare Crashes | M | **P0** |
| **Design Debt** | VRAM-Accounting-Modell divergiert von physischer Realität (reserve/commit/release-Semantik uneinheitlich angewandt) | H6, M1, M2, D2 | Falsche OOM, echte OOM, Kaskaden | L | **P0** |
| **Design Debt** | Persistenz ohne atomare Writes / serialisierten Writer | C1, M12 | Datenverlust/Cache-Poisoning bei Crash | M | **P0** |
| **Code Debt** | Zeit-/Einheiten-Budget wird an Return-Sites inkonsistent durchgereicht | H1, M5, M7, M10 | Falsche Cut-Listen, tote Features | L–M | **P1** |
| **Code Debt** | Tote/Legacy-Codepfade (`workers/*` PyQt6-Relikt, `ui_legacy_archived/`) noch im Repo | D1, D2, gesamtes `workers/` | Verwirrung, Fehl-Audits, „grüne Tests" auf totem Code | M | **P1** |
| **Code Debt** | Lazy-Function-Local-Imports + `Any`-Typing überall → statische Analyse blind | `advanced_pacing_engine.py` (23 pyflakes-False-Positives), pacing_service | Bugs von Tools nicht gefunden | M | **P2** |
| **Test Debt** | Testsuite grün, deckt aber Crash-Persistenz, lange MP3-Mixe, Cancel-danach-Render, `duration_limit`, VRAM-über-Task nicht ab | C1, H1, H2, H5, H6 sind alle test-unsichtbar | „Verified"-Label irreführend | M–L | **P1** |
| **Reliability Debt** | Progress/SSE-Verkabelung defekt (Worker→UI) | M9, M13 | UI wirkt „hängend", Support-Last | S | **P1** |
| **Consistency Debt** | Gemischte Sentinels/Defaults, uneinheitliche subprocess-stdout-Behandlung | L2, L8 | Latente Randfall-Bugs | S | **P3** |

**Wichtigster struktureller Hebel:** Die vier **P0-Design-Debts** erzeugen zusammen ~20 der 31 Findings. Ein *einziges* Error-/Resource-Contract (Fehler propagieren, Ressourcen im `finally` freigeben, Writes atomar + serialisiert, kein globaler Patch ohne Lock) würde die Mehrheit strukturell verhindern statt einzeln zu patchen.

---

## Steel-Man Gegenposition

Die stärkste Gegenposition: *„Die meisten dieser Bugs sind Error-Path- oder Edge-Case-Fälle; die Happy-Path-Pipeline läuft (186 Tests grün, produktive IRON-RULE-Pfade sauber), und mehrere Befunde sitzen in totem `workers/`-Code oder in latenten, nie aufgerufenen Methoden (L5/L6). Ein Team mit begrenzter Zeit sollte nicht 31 Findings abarbeiten, sondern nur die 2–3, die im täglichen Betrieb tatsächlich feuern — der Rest ist theoretisch."*

Das ist teilweise stark: die Priorisierung ist richtig, und die Dead-Code-Findings habe ich bewusst runtergestuft. **Wo es bricht:** C1 (FAISS-Datenverlust), H1 (`duration_limit`), H2 (Cancel), H5 (langer MP3-Mix) und H6 (VRAM-OOM) sind **keine** exotischen Edge-Cases — es sind die dokumentierten Kern-Use-Cases (Library-Import, Preview-Render, Cancel-Button, lange DJ-Mixe, GPU-knappe AMD-Systeme). Sie sind nur test-unsichtbar, nicht selten. Die Testsuite grün zu nennen und „Production/Verified" zu labeln, während genau diese Pfade brechen, ist das eigentliche Risiko.

---

## Open Questions

1. **Wird `VideoGenerator`/`GenerationService` pro Render neu instanziiert oder als Singleton wiederverwendet?** — Entscheidet, ob H2 „jeder Folge-Render kaputt" (Singleton) oder „nur bei explizitem Reuse" ist. `generation_service.py:20` deutet auf Wiederverwendung.
2. **Ist der `workers/`-Baum offiziell deprecated?** — Falls ja: löschen (spart Audit-Rauschen, D1/D2 erledigen sich). Falls nein: Warum importiert ihn nichts? *(Datei-Löschung = STOPP-Regel laut CLAUDE.md → eure Freigabe nötig.)*
3. **Existiert CLAP-ONNX real auf den Zielmaschinen (M3)?** — Falls ja, laufen alle Mood/Genre-basierten Cuts *jetzt* auf Fabrikat-Daten. Bestimmt, ob M3 eigentlich High ist.
4. **Welche FAISS-Dimension nutzt der produktive Index — 768 (video_embedder) oder 1152?** — Der Video-Agent flaggte eine mögliche Dim-Diskrepanz zwischen `video_embedder.EMBED_DIM=768` und dem Vector-Store; außerhalb des geprüften Scopes, aber build-brechend wenn inkonsistent.
5. **Soll ich die verifizierten Critical/High-Fixes direkt implementieren?** — Alle 9 verifizierten sind lokale, low-risk Patches (two-way door). Keine berührt eine IRON RULE oder ein Schema (kein STOPP-Trigger außer Datei-Löschung).

---

## Recommendation

**GO-mit-Modifikation** — Codebase ist tragfähig, aber der „Production/Verified"-Status ist erst nach den Critical+High-Fixes gerechtfertigt.

- **Confidence:** HIGH (für die 9 verifizierten C1/H1–H6/M3/M13), MEDIUM (übrige, Agenten-Reasoning solide aber nicht einzeln laufzeit-reproduziert).
- **Reversibilität:** two-way door — alle Fixes sind lokal, kein Architektur-Umbau.

**Modifikationen in Reihenfolge:**
1. **Sofort (P0, blockiert „Production"):** C1 (FAISS-Writer serialisieren + debouncen), H1 (`target_duration` in finalize), H2 (`cancel_flag` reset), H3 (Encode-Fehler propagieren), H4 (LHM-Lock), H5 (Streaming-Decoder), H6 (VRAM release im finally).
2. **Vor nächstem Release (P1):** M1/M2 (VRAM-Accounting-Fehlerpfade), M3 (CLAP-Mock raus), M4 (Gap-Fill-Cap), M9/M13 (Progress/SSE-Verkabelung), M11/M12 (atomare/gelockte Writes).
3. **Backlog (P2/P3):** Rest + strukturelle P0-Design-Debt-Konsolidierung (ein Error-/Resource-Contract).

---

## Appendix — Verifizierte Nicht-Bugs (Anti-Sycophancy-Disziplin)

Damit ihr keine Zeit verschwendet: Folgendes wurde geprüft und ist **kein** Bug —
- **23 pyflakes „undefined name" in `advanced_pacing_engine.py`** (`PacingCut`, `SongSection`, `TriggerSettings`): Function-local Lazy-Imports + quoted Forward-Ref-Annotations (`-> List["PacingCut"]`), die zur Laufzeit nie evaluiert werden. False Positive.
- **IRON RULE R1/R2/R5 im produktiven Pfad:** kein `torch.cuda`/`pynvml`/`nvidia-smi`/`CUDAExecutionProvider`; alle `InferenceSession` im aktiven Code (model_loader, raft, moondream, clap, siglip) setzen **beide** DirectML-Flags; GPU-Monitoring via LibreHardwareMonitor. Sauber. (R4 nur im Software-Fallback verletzt → M14.)
- **SQL-„Injection"-Treffer** (`PRAGMA user_version={version}`, `wal_checkpoint({mode})`): interne Ints, kein User-Input. Kein Risiko.
- **`app_state.py` Lock-Ordering, `render_queue` State-Machine, `App.xaml.cs` OnExit-`.Wait()`** (ConfigureAwait(false) → kein UI-Deadlock): geprüft, sauber.
