# Arbeitsplan aus FULL_AUDIT_2026-06-10 — abgeglichen mit Entwicklungsstand 2026-06-12

**Abgleich-Methodik:** git log seit Audit (Commits `7ebf7bf`, `7567055` = Fix-Epic `specs/00015-fix-full-audit`, QC „PASSED": 732 Tests grün, Release-Build 0 Fehler) — **dem QC-Report wurde nicht blind vertraut**: jeder als gefixt gemeldete Punkt wurde per Grep/Read im heutigen Code nachverifiziert (IRON Rule 10).

**Status-Legende:** ✅ erledigt (Code-verifiziert) · 🔶 teilweise · ❌ offen (Code-verifiziert) · ⚪ nicht erneut geprüft

---

## Block A — ERLEDIGT (verifiziert, keine Arbeit mehr nötig)

### Alle 11 🔴-Kritisch-Funde sind gefixt ✅

| # | Fund | Verifikation im heutigen Code |
|---|------|-------------------------------|
| K1 | Beat-Drift (Duration-Cap wirkungslos) | `pacing_service.py:145`: `end_time=current_cut.time + duration` ✅ |
| K2 | Concat-Codec-Mismatch | `render_service.py:282–305`: prüft jetzt `codec_name` + `pix_fmt`; `:478` `select=concatdec_select,setpts=…` ✅ (Rest siehe AP2.2) |
| K3 | Falscher FAISS-Index | `pacing_service.py:527,774`: `VectorStore(index_name="video_index")` ✅ |
| K4 | vector_map-Drift bei Kompaktierung | `vector_store.py:320–334`: `UPDATE vector_map SET faiss_id…` in Transaktion ✅ |
| K5 | SubtrackDetector Zeitachsen | `subtrack_detector.py:266,322`: `np.interp(t_axis, times, …)` ✅ |
| K6 | Onsets ~4× gestaucht | `audio_router.py:446`: `fps = len(energy)/duration` ✅ |
| K7 | Save-on-Exit toter Code | `App.xaml.cs`: Save (Z.148) jetzt VOR `BeginShutdown()` (Z.156) ✅ |
| K8 | AnchorVM ohne Dispatcher | `AnchorViewModel.cs`: 6× Dispatcher-Aufrufe ✅ |
| K9 | Exit-Code-Verlust setup/test.bat | beide enden mit `; exit $LASTEXITCODE` ✅ |
| K10 | Debug-Build/Launcher | `setup_pb_studio.ps1:683` `-c Release`; `launch.ps1:319` matcht nur noch `\Release\` ✅ |
| K11 | evict_if_needed TypeError | `vram_arbiter.py:256ff`: Tuple entpackt, Callbacks werden ausgeführt ✅ |

### Erledigte 🟠-Funde ✅

- `with_gpu_task`: CancelledError-Handling, `await task` im finally (Lock erst frei wenn Thread fertig), `cancel_reservation` abgesichert — `dependencies.py:115–157`
- Eviction-Rollback bei Callback-Failure (`is_loaded=True` + `_committed_mb +=`) — `vram_budget_manager.py:641,838`
- LHM-Thread-Lock — `system_monitor.py:42,182`
- Migrations-Atomicity: `split_sql_statements` in beiden Runnern — `migration_runner.py:18,92` + `embedding_repository.py:107,123`
- `is_render_active()` implementiert — `app_state.py:318` (Zombie-Watcher funktioniert jetzt)
- Chat `.TakeLast(40)` — `ChatViewModel.cs:82`
- `stems_paths`-JSON-String-Parsing in `/audio/analyze` — `audio_router.py:316`
- Brain-Roundtrip `brain_final_score`+`cut_id` in `POST /pacing/timeline` — `pacing_router.py:259–260`
- Video-Pipeline entkoppelt: Scenes via `to_thread` (Z.453), nur RAFT+SigLIP unter `with_gpu_task` (Z.465), Color/Caption/audio_key außerhalb — `video_router.py`
- Stems-Strukturlücke: Fallback-Kette Drums→Instrumental→Mix + `st_size > 0`-Check (0-Byte-Stems) + Streaming-Retry auf Original-Mix bei Stem-Fehler — `audio_router.py:727,798`
- SSE `pacing_progress`: im Server-Filter (`events_router.py:79`), im SSEClient (`:269`) UND in `DirectorViewModel:424` ✅; `stem_progress` in `AudioLibraryViewModel:62` ✅
- HttpClient-Timeout 10→20 min (> stem_timeout 15 min) — `ApiClient.cs:30`
- clip_selector: `from pathlib import Path` (Z.21) + `MotionAnalyzer` statt Phantom-`RAFTOpticalFlow` (Z.800)
- export_handler: Single-Quote-Concat-Format — `export_handler.py:132`
- Hartkodierter Storyboard-Canvas-Default entfernt (`canvas_path` ohne Default) — `pacing_service.py:616`
- FAISS `duration_seconds` wird jetzt gesetzt — `video_router.py:740,841,900` (Rest-Fragilität: `if 'duration_sec' in locals()`)
- `torchaudio==2.4.1` gepinnt — `requirements.txt:15`
- „Dokumente"-Pfad bereinigt (0 Treffer in preflight.ps1/project.json)
- `run_full_test.ps1`: UI-Agent-Exit-Code + `Stop-Process`-Cleanup (Z.79–92)
- `coverage_run_v2.bat`: `Select-Object -First` statt Unix-`head`, Redirects korrigiert
- models_router: `aclose()` in `finally` — Z.339–341, 401–405
- Reentry-Gates: `AnalyzeMarked` mit `IsAnalyzing`-Gate + `NotifyCanExecuteChanged`-Verdrahtung (VideoLibraryViewModel) 🔶→weitgehend ✅

---

## Block B — OFFENE ARBEIT (verifiziert offen, priorisierte Arbeitspakete)

### AP1 — Backend-Korrektheit & Responsiveness (Aufwand: klein, ~½ Tag)

| # | Aufgabe | Datei:Zeile | Befund-Referenz |
|---|---------|-------------|------------------|
| 1.1 | `except HTTPException: raise` vor generische Handler (400 wird zu 500) | `pacing_router.py:154/195` u. `:278/318` | ❌ verifiziert: kein `except HTTPException` im File |
| 1.2 | ffprobe-Call in `asyncio.to_thread` (blockiert Event-Loop/SSE) | `pacing_router.py:274` | ❌ verifiziert: weiterhin sync |
| 1.3 | `state_conn`-Write hinter `db_write_lock` + `to_thread` | `pacing_router.py:145` | ❌ verifiziert: weiterhin ungeschützt |
| 1.4 | `/shutdown`: Windows-graceful (uvicorn `should_exit`/CTRL_BREAK statt SIGTERM=TerminateProcess) | `main.py:367–371` | ❌ verifiziert: unverändert; Kommentar behauptet weiterhin „graceful" (Rule-10-Drift) |
| 1.5 | SSE-Queue-Registrierung in die erste Generator-Iteration (Leak bei nie gestartetem Stream) | `events_router.py:31,70,77` | ❌ Registrierung weiter vor Stream-Start |

### AP2 — Rendering/FFmpeg-Härtung (Aufwand: klein–mittel, ~½–1 Tag)

| # | Aufgabe | Datei:Zeile | Befund |
|---|---------|-------------|--------|
| 2.1 | Bare `"ffmpeg"`/`"ffprobe"` durch `_get_ffmpeg_path()`/`_get_ffprobe_path()` ersetzen | `render_service.py:86,357,466` (+ffprobe-Stellen) | ❌ verifiziert: 3+ bare Aufrufe |
| 2.2 | K2-Restprüfung: Audio-Stream-Präsenz (`-an`-Mismatch Temp vs. Original) + SAR in `_check_needs_normalization` aufnehmen | `render_service.py:282–310` | 🔶 Codec+PixFmt sind drin, Audio/SAR nicht gesichtet |
| 2.3 | AMF→Software-Fallback als SSE-Event/UI-Signal melden (still bisher) | `render_service.py:489–494` | ⚪/❌ Audit-Stand, nicht erneut geprüft |
| 2.4 | Preview-Renderer auf `get_preview_encoder()` (h264_amf speed) umstellen | `preview_renderer.py:121,157` | ⚪ Audit-Stand |

### AP3 — WPF-Lebenszyklus & UI-Korrektheit (Aufwand: mittel, ~1–1½ Tage)

| # | Aufgabe | Datei:Zeile | Befund |
|---|---------|-------------|--------|
| 3.1 | `async void OnExit`-Race beheben (synchroner Shutdown-Pfad) + Windows Job Object gegen uvicorn-Zombies | `App.xaml.cs:137`, `PythonBridgeService.cs` | ❌ verifiziert: unverändert, kein JobObject |
| 3.2 | `BackendReadyMessage` nach Health-OK senden (Settings-Tab zeigt sonst „Offline"); oder tote Registrierungen entfernen (`ProjectClosingMessage` ebenso) | `PythonBridgeService.cs` / `AppMessages.cs` | ❌ verifiziert: 0 Sender im Repo |
| 3.3 | Tote Bindings `SceneIndex`/`MotionScore`: `SceneInfo` erweitern oder XAML bereinigen (+ `Binding Source="100.0"`-String-Bug) | `VideoLibraryView.xaml:459,471,479` ↔ `ApiClient.cs:1000` | ❌ verifiziert: Bindings unverändert, Properties existieren nicht |
| 3.4 | WaveformRenderer/DepthRenderer: `CollectionChanged`-Abo oder Collection-Ersatz statt In-place-Mutation (Waveform erscheint erst bei Zoom/Resize) | `Controls/WaveformRenderer.cs`, `DepthRenderer.cs`, `TimelineViewModel.cs:531–599` | ❌ verifiziert: kein CollectionChanged |
| 3.5 | `TimelineViewModel` auf `IApiClient` umstellen (`GetOnsetsAsync` ins Interface) — zweite ApiClient-Instanz eliminieren | `TimelineViewModel.cs:22,128` | ❌ verifiziert: weiter konkreter `ApiClient` |
| 3.6 | Video-Grid: virtualisierendes Panel statt `WrapPanel` | `VideoLibraryView.xaml:180–186` | ⚪ Audit-Stand |
| 3.7 | SSEClient: Hard-Cap 50 Reconnects entfernen (Delay deckeln statt sterben) | `SSEClient.cs:32,205` | ❌ verifiziert: `MaxReconnectAttempts = 50` |

### AP4 — Audio-Analyse-Qualität (Restpunkte Stems-Komplex) (Aufwand: mittel, ~1 Tag)

| # | Aufgabe | Datei:Zeile | Befund |
|---|---------|-------------|--------|
| 4.1 | Energy-Curve vom Original-Mix berechnen statt Drums-Stem (Semantik-Wechsel für Pacing/UI) | `audio_router.py:727ff` | ❌ verifiziert: `energy_curve` kommt weiter vom `analysis_path` (=Drums) |
| 4.2 | Beat-Strengths für Beats >600 s: neutral (1.0) statt Bogus-Clamping auf Snapshot-Ende | `audio_router.py:776,815` + `beat_detector.py:179ff` | ❌ verifiziert: unverändert (600-s-Snapshot + Full-Mix-Beats) |
| 4.3 | DJ-Mix-Branch erreichbar machen: echte Datei-Dauer an `analyze_song_structure` übergeben (Snapshot ist exakt 600.0 → `>600` nie wahr) | `structure_analyzer.py:192` ↔ `audio_router.py:743` | ❌ verifiziert: unverändert |
| 4.4 | `librosa.get_duration` in `detect_beats` in try ziehen + Router-Retry auf Mix bei Stem-Exception (Non-Streaming-Pfad) | `beat_detector.py:224` | 🔶 Router hat jetzt `st_size>0`-Check (0-Byte abgedeckt), korrupte WAV wirft weiterhin ungefangen |
| 4.5 | WaveformAnalyzer: Langdatei-Strategie (Chunked-Filterung; sosfiltfilt-float64-Peak bei 90-min-Mixen) | `waveform_analyzer.py:74,144` | 🔶 Default-SR offenbar auf 22050 gesenkt, kein Chunking |
| 4.6 | SubtrackDetector-Importkosten: Tempo-Drift-Hop vergrößern / Background-Task für >10-min-Files | `subtrack_detector.py:285ff`, `audio_router.py:132` | ⚪ Interp gefixt, Kostenpunkt nicht erneut geprüft |

### AP5 — IRON-RULES-Hygiene & Scripts (Aufwand: klein, ~½ Tag)

| # | Aufgabe | Datei:Zeile | Befund |
|---|---------|-------------|--------|
| 5.1 | `torch.cuda`-Block aus RecoveryHandler entfernen (R1) — DirectML-Eviction via VRAMBudgetManager | `recovery_handler.py:63–64` | ❌ verifiziert: noch drin |
| 5.2 | `enable_cpu_mem_arena=False` in 4 Model-Scripts ergänzen (R2) | `scripts/download_clap_model.py`, `download_siglip_onnx.py`, `export_moondream_onnx.py`, `export_raft_onnx.py` | ❌ verifiziert: 0 Treffer in allen 4 |
| 5.3 | `$global:LASTEXITCODE = 0` aus finally entfernen (maskiert Fehler) | `verify_release_smoke.ps1:417` | ❌ verifiziert: noch drin |
| 5.4 | EmbeddingCache: vollen Hash im Dateinamen (Kollisions-Überschreibung) + `model_version` sanitisieren | `embedding_cache.py:99` | ❌ verifiziert: weiter `[:16]` |
| 5.5 | BrainStore: `_patterns_lock` analog `_weights_lock` | `brain_store.py:59ff` | ❌ verifiziert: nur weights-Lock existiert |

### AP6 — Backlog ⚪ (aus Audit, seit dem Fix-Epic NICHT erneut verifiziert — vor Bearbeitung je Punkt re-checken)

🟡-Kandidaten (Auswahl, vollständige Liste im Audit): Reset-Tokens ohne TTL · tote tiktoken-Logik · `register_audio_clip`-Reuse verliert stems_paths · Thumbnail-Flag-Semantik · CORS `"null"`-Origin + fehlendes DELETE · Render-Complete-vs-Cancel-Race · BeatDetector-Singleton-Thread-Safety · VRAMBudgetManager-`__init__`-Race · VectorStore-Save-Ordering + Singleton-Registry · DatabaseCore-Connection-Sweep · EmbeddingRepository stale Thread-locals nach close() · Migration-Version=Listenindex · `bulk_update_status([])` · TaskQueue (totes Modul) · VRAMContext-Leak ohne commit() · Streaming-Beat-Dedup an Chunk-Grenzen · Modellnamen-Drift Worker `htdemucs_ft` · VRAM-Doppel-Reservierung Stems · Worker-Sinus-Fake-Energiekurve · MoodGenerator-1-Hz-Annahme · SMPTE-int-fps · AnchorManager-JSON nicht atomar · WeightStore-Write-Lock · Theme-Bonus +1000 · `_plan_beat_sync`-Duplikat-Loop · Energy-Sync-Tail · engine.py-Fallback ohne Returncode-Check · Snap-Min-Interval · SemanticMatcher-O(N)-Scan · ConcatWorker-Apostroph-Escaping · RenderWorker-Plan-Drift · VideoMotionWorker `is_ready` · sync `Dispatcher.Invoke` in SSE-Konsumenten · `_lastProgressUpdate`-Leak · non-2xx-Fehlerdetails verloren · SelectAll-Sync · CTS-Hygiene · `DispatcherUnhandledException Handled=true` · Klick-Logger im MainWindow · Anchors nie persistiert · hartkodierte Pfade in `scripts/` · systemweites `taskkill python.exe` · `build.ps1` ungepinnte pip-Installs · `--no-elevation`-Parameter-Leak · separator `models_dir` relativ (LOCKED-Datei — nur via config.json-Workaround) · htdemucs-CPU-Realität dokumentieren (CLAUDE.md-Aussage „Demucs patched for DirectML" gilt nur für ONNX-MDX-Pfade).

---

## Pflicht-Begleitmaßnahmen pro Arbeitspaket (IRON Rules 9/10/13)

1. **Verify-before-change:** je Punkt aktuellen Code lesen, Fix gegen Root-Cause prüfen (Skills: `pb-master` für Cross-Layer, `code-auditor` statisch).
2. **C#-Änderungen (AP3):** immer `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` + Release-DLL-Verifikation.
3. **Script-Änderungen (AP5.3, AP2):** mit `script-validator` bis 3× clean.
4. **Tests:** `test.bat --no-gui` nach jedem AP; bei Backend-Schema-Berührung `ApiClient.cs`+Records gegenprüfen.
5. **Doku-Sync:** CHANGELOG.md je Fix; CLAUDE.md §3 + Obsidian-Vault (INDEX.md, log.md) nach jedem AP — **Vault-Sync zum Audit vom 10.06. steht noch aus** (in Audit-Session kein Vault-Zugriff).

## Empfohlene Reihenfolge & Gesamtaufwand

**AP1 → AP5 → AP2 → AP3 → AP4 → AP6** (Quick-Wins und Rule-Compliance zuerst, dann UI-Lebenszyklus, dann Analyse-Qualität). Geschätzt: **3½–5 Arbeitstage** für AP1–AP5; AP6 nach Re-Verifikation einzeln schätzen.

## Ehrlichkeits-Hinweise zum Abgleich

- Der QC-Report von E015 behauptet „K1–K11 fully verified" — **das stimmt** nach meiner unabhängigen Code-Prüfung. Die Formulierung „All deliverables meet the required technical specifications" gilt aber nur für die 11 Epic-Tasks; **~20 verifizierte 🟠-Punkte aus dem Audit waren nie Teil des Epics und sind offen** (Block B).
- Verifikationstiefe: Block A/B per Grep/Read im heutigen Code belegt; AP6 (⚪) ist Audit-Stand vom 10.06. ohne Re-Check — einzelne Punkte könnten durch die Commits mitgefixt worden sein.
- Keine Live-Tests in dieser Session (Sandbox ohne DirectML/WPF); QC-Angaben „732 passed / Release-Build OK" stammen aus dem Epic-Report vom 10.06., nicht aus eigener Ausführung.
