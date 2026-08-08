# Implementierungsplan: System-wide Bug Hunting & Codebase Audit (Epic 00013)

## Phase 66: Release-Readiness 2026-07-28

### Ausführungsreihenfolge

1. **W0 Governance/SDD:** Audit-Evidence und Baseline-Commit einfrieren; FR-251–FR-310, T228+ und DirectML-ADR registrieren.
2. **W1 P0-Blocker:** C-01, C-02, H-20 und H-23 schließen.
3. **W2 Audio:** H-01–H-06, M-01–M-03 und L-01–L-02 schließen.
4. **W3 GPU/Core:** H-07–H-09 und M-04–M-05 schließen.
5. **W4 Video/Vision:** H-10–H-11, M-06–M-09 und L-03–L-04 schließen.
6. **W5 Pacing/Brain:** H-12–H-16 und M-10–M-11 schließen.
7. **W6 Chat/Models/Terminal:** H-17, H-26, M-12–M-13 und L-06 schließen.
8. **W7 Projekt/Data:** H-21, M-17–M-22 und L-07 schließen.
9. **W8 Render/Export:** H-22, H-24–H-25 und M-23–M-25 schließen.
10. **W9 WPF/Lifecycle:** H-18–H-19, M-14–M-16 und L-05 schließen.

### Micro-Gates

* Nach jedem Write: Syntax- beziehungsweise XML-Balance und Truncation-Prüfung.
* Pro Cluster: genau ein enges Failure-/Regression-Subset.
* Kein Full-Pytest und kein wiederholter WPF-Build während der Clusterarbeit.
* Shared Files, Model-Registry und öffentliche C#-Verträge werden sequenziell geändert.
* Zone-Commit erst nach bestandenem Cluster-Micro-Gate.

### Release-Checkliste

* Alle 60 Finding-Tasks und alle Cluster-Gates sind `[X]`.
* Requirement-Matrix C-01–L-07 ist 60/60 belegt.
* Erst danach wird `.completed` erstellt.
* Statische Gates, Full-Pytest, Skip-Audit, Coverage und WPF Release-Build bestehen.
* Security-, Daten-/Fault-Injection-, Hardware-/E2E-, Modell-/GUI- und Export-Gates bestehen.
* `qc-report.md` enthält pro Finding den Testbeleg.
* Nur bei vollständigem PASS werden `.qc-passed`, Brain-Log und QC-Commit erstellt.

### Verbindliche Skill-Zuordnung

* Immer aktiv: `caveman`, `pb-master`.
* W0: `consulting-team`, `caveman-commit`.
* W1: `pacing-expertise`, `gpu-expertise`, `chat-agent-expertise`, `projekt-expertise`, `rendering-expertise`, `codex-security:threat-model`, `codex-security:fix-finding`.
* W2–W4: `audio-expertise`, `gpu-expertise`, `video-expertise`, `model-registry-expertise`.
* W5–W6: `brain-expertise`, `pacing-expertise`, `chat-agent-expertise`, `model-registry-expertise`, `config-expertise`, `terminal-expertise`, `codex-security:validation`.
* W7–W9: `projekt-expertise`, `brain-expertise`, `engineering:architecture`, `rendering-expertise`, `timeline-expertise`, `wpf-visual-blind-spot`.
* End-QC: `auto-qa-loop`, `run-tests`, `health-check`, `run-pb-studio`, `wpf-gui-verification`, `codex-security:validation`.

### Gebündeltes End-QC

1. `git diff --check`, Iron-Rule-Scan, Python-Compile-Sweep, XAML-Parse, OpenAPI- und C#-DTO-Verträge.
2. Vollständiges `pytest Tests/ -q`, Skip-Audit, Coverage und WPF Release-Build.
3. Chat-Bestätigung: Approve, Reject, Timeout, Replay, Argument-Tampering, Parallelbestätigung und Disconnect.
4. Daten/Fault-Injection nur auf Kopien: SQLite/FAISS/Outbox-Crashfenster, Writer-Diskfehler, Backup-Restore, Migrationslücke, FK-/Integrity-/Orphan-Prüfung.
5. Reale Hardware/E2E: 60–120-Minuten-Mix, RAFT, SigLIP, Vision, Stems, Brain-Pacing, Render, VRAM-/Timeout-/Cancel-Pfade.
6. Modelle/GUI: Vision- und Tool-Use-Modell live; Models-Tab terminiert bei Offline-Ollama; alle 12 Bereiche und Projektwechsel unter Last.
7. Export: vollständige H.264-/HEVC-Dateien, atomarer Zielschutz, AV1 vor Start als unavailable.

## Phase 31: Aktive DTO-Schemas synchronisieren

1. Regression für fehlende Audio-/Videoanalyse-Felder ergänzen.
2. Handgeschriebene Records additiv mit dem OpenAPI-Snapshot synchronisieren.
3. Vertragstest und WPF Release-Build ausführen.

## Phase 30: SSE-Progress-Korrelation

1. Statischen Vertrag für aktive IDs und Domain-Filter ergänzen.
2. Videoimport- und Pacing-Events mit Task-/Clip-Korrelation versehen.
3. VideoLibrary und Director auf den aktiven Request begrenzen.
4. Router-/Vertragstests und WPF Release-Build ausführen.

## Phase 29: Lernsession Playback-Toggle

1. Statischen WPF-Vertrag für Toggle-State, beide Events und Buttonlabel ergänzen.
2. `LearningSessionViewModel` um `IsPlaying` und echten Toggle erweitern.
3. XAML-Buttontext an den Playback-State binden.
4. Vertragstest und WPF Release-Build ausführen.

## Phase 28: RAFT-Flow-Wiederverwendung

1. Regression für exakt einen Flow-Aufruf pro Frame-Paar ergänzen.
2. Flow-basierte Statistik- und Scene-Change-Helfer extrahieren.
3. Segmentanalyse über einen gemeinsamen Pair-Analyzer verdrahten.
4. RAFT-/Video-/DirectML-Tests und Compile-Sweep ausführen.

## Phase 27: Streaming-Energy-Zeitachse

1. Regression mit fehlerhaftem mittleren Chunk und spätem Peak ergänzen.
2. Energy-Aggregator um deterministische Null-Lücken erweitern.
3. Load- und RMS-Fehlerpfade an die Lückenaggregation anbinden.
4. Streaming-/Audio-/Pacing-Tests und Compile-Sweep ausführen.

## Phase 26: Medien-JSON-Schreibschema

1. Persistenzregression für `.wmv`-Metadata und AI-Data ergänzen.
2. Medienart-Klassifikation zentralisieren und `.wmv`/`.flv` aufnehmen.
3. Schema-Migration vor allen normalen JSON-Schreibpfaden anwenden.
4. Repository-/Schema-Tests und Compile-Sweep ausführen; Live-Batchmigration auslassen.

## Phase 25: Brain-Stats Lock-Sicherheit

1. Regression mit einer Connection ergänzen, die ungesperrte Queries ablehnt.
2. Alle direkten Stats-Queries in einen gemeinsamen `_weights_lock`-Scope verschieben.
3. Brain-Router-, Recovery- und Core-Tests sowie Compile-Sweep ausführen.

## Phase 24: FAISS-Link als Commit-Gate

1. Regressionen für fehlende `media_id` und fehlgeschlagenen `vector_map`-Insert ergänzen.
2. Unverlinkte Writes vor dem Index-Add ablehnen.
3. Linkfehler durch sicheren Last-Vector-Rollback oder Tombstone kompensieren und propagieren.
4. VectorStore-/Data-Tests und Compile-Sweep ausführen.

## Phase 23: Projekt-Guard für Medienimporte

1. API-Regressionen für Audio-/Videoimport ohne aktives Projekt ergänzen.
2. Strikten AppState-Zugriff auf die aktive DB-Projekt-ID ergänzen.
3. Import, Registrierung und Persistenz auf den strikten Projektkontext verdrahten.
4. Router-, AppState- und Persistenztests sowie Compile-Sweep ausführen.

## Phase 22: Persistenzsichere Medien-Löschung

1. Regressionen für Audio-DB-Fehler und Video-Tombstone-Fehler ergänzen.
2. SQLite-/FAISS-Arbeit vor der In-Memory-Entfernung ausführen.
3. Persistenzfehler protokollieren, als `persist_error` publizieren und erneut auslösen.
4. AppState-, Router- und Persistenztests sowie den Python-Compile-Sweep ausführen.

## Phase 7: C-01 Live-Pacing Cache-Vertrag

* **Analyse:** Fehler im echten Ablauf Audio-Analyse → `_inject_cached_into_engine()` → `AdvancedPacingEngine._generate_cut_list_from_audio()` reproduzieren.
* **Test:** Regressionstest für vorab injizierte Beats/Energie bei fehlenden Onset-/Drum-Kandidaten; Exceptions dürfen nicht geschluckt werden.
* **Implementierung:** Waveform-Cache-Felder atomar im Engine-Konstruktor initialisieren. Analysemetadaten-Injektion darf `_cached_audio_path` nicht als geladen markieren.
* **QC:** Pacing-Subset, Python-Compile-Sweep, vollständige Pytest-Suite und Release-Smoke ausführen.

## Phase 8: C-02 AMF-only Render-Vertrag

* **Analyse:** Encoder-Werte vom WPF-Request über Pydantic/Tool-Schema bis FFmpeg-Argumente verfolgen und Software-Fallbacks reproduzieren.
* **Test:** AMF-only Enum-/Utility-/RenderService-Regressionen; fehlendes AMF muss explizit fehlschlagen.
* **Implementierung:** Nur `h264_amf`, `hevc_amf`, `av1_amf` zulassen; `libx264`, `libx265`, `libsvtav1`, `h264_mf` und `force_software` aus Live-Pfaden entfernen.
* **QC:** Encoder-/Render-/OpenAPI-Tests, Python-Compile, WPF Release-Build, vollständige Suite und Release-Smoke.

## Phase 9: C-03 DirectML-only Provider- und Motion-Vertrag

* **Analyse:** Providerketten in `ModelLoader`, RAFT-Factory, `SmartDirector` und Audio-Separator gegen den DirectML-Vertrag prüfen.
* **Test:** Regressionen für verpflichtenden DirectML-Provider und CPU-freie Motion-Analyse ergänzen.
* **Implementierung:** CPU-Provider und Farneback aus nicht gesperrten Live-Pfaden entfernen; `audio/separator.py` erst nach expliziter Nutzerfreigabe ändern.
* **QC:** DirectML-Zieltests, Python-Compile und vollständige Pytest-Suite; C-03 bis zur Separator-Freigabe als teilweise behoben führen.

## Phase 10: C-04 SDD/QC-Gate-Konsistenz

* **Analyse:** Task-Checkboxen, QC-Aussagen und Markerdateien gegen den aktuellen Test- und Finding-Stand prüfen.
* **Test:** Repository-Regression für Checkboxformat, invalidierten historischen Pass und abwesende Erfolgsmarker ergänzen.
* **Implementierung:** Checkboxen normalisieren, historischen QC-Pass eindeutig invalidieren und falsche Marker nach expliziter Löschfreigabe entfernen.
* **QC:** SDD-Gate-Test, Marker-Suche und vollständige Metadatenprüfung ausführen.

## Phase 11: H-01 Nicht-destruktiver Medien-Restore

* **Analyse:** Projekt-Open über `project_router.open_project()` bis `AppState.load_from_db()` und `MediaRepository.delete_media()` verfolgen.
* **Test:** Temporär fehlendes Medium muss übersprungen, aber weder gelöscht noch seine Clip-ID wiederverwendet werden.
* **Implementierung:** Metadaten und Clip-ID vor dem Dateisystem-Gate validieren; fehlende Dateien nur als nicht verfügbar protokollieren.
* **QC:** AppState-/Projektpersistenz-Cluster, Compile-Sweep und relevante DB-Restore-Regressionen ausführen.

## Phase 12: H-02 Atomarer Projekt↔Brain-Rebind

* **Analyse:** `_bind_brain_to_project()` über `_brain_singleton.set_project_state()` bis `BrainService.bind_project_state()` verfolgen.
* **Test:** Bind-Fehler muss alten Pfad, alte Connection und alten `AppState` erhalten; erfolgreicher Swap schließt die alte Connection erst nach Initialisierung der neuen.
* **Implementierung:** Connection und globalen Pfad atomar tauschen; Projekt-Create/Open vor jedem Runtime-State-Reset bindend preflighten und Fehler als HTTP 500 melden.
* **QC:** Projekt-Lifecycle- und Brain-Binding-Regressionen sowie Compile-Sweep ausführen.

## Phase 13: H-03 FAISS/SQLite-Kompaktierungs-Gate

* **Analyse:** Tombstone-Reindexing, `vector_map`-Remap und Snapshot-Save als eine Commit-Kette verfolgen.
* **Test:** Erzwungener SQLite-Remap-Fehler darf weder Index/Metadaten tauschen noch Tombstones löschen oder einen Save anfordern.
* **Implementierung:** Remap-Fehler bis zur äußeren Kompaktierungsgrenze propagieren und den In-Memory-Swap ausschließlich nach erfolgreichem Commit ausführen.
* **QC:** VectorStore-Tombstone-Regressionen und Compile-Sweep ausführen.

## Phase 14: VectorStore-Testfixture reparieren

* **Analyse:** Bekannten `_save_cv`-Fehler gegen den echten `VectorStore.__init__`-Vertrag prüfen.
* **Implementierung:** Beim absichtlich per `__new__` erzeugten Unit-Testobjekt `_request_save()` mocken und dessen Aufruf verifizieren.
* **QC:** Vollständigen VectorStore-Testcluster ausführen.

## Phase 15: Generation-Cancel-Race

* **Analyse:** Cancel-Signal von `GenerationService.cancel()` über SmartDirector-Analyse bis `VideoGenerator.generate_from_timeline()` verfolgen.
* **Test:** Timeline-Render respektiert ein bereits gesetztes Cancel; jede neue Jobannahme ruft genau einmal `reset_cancel()` auf.
* **Implementierung:** Cancel ausschließlich bei synchroner Jobannahme zurücksetzen und in beiden Generator-Einstiegen früh prüfen.
* **QC:** SmartDirector-/GenerationService-/VideoGenerator-Cluster und Compile-Sweep ausführen.

## Phase 16: H-04 Crash-konsistenter FAISS-Snapshot

* **Analyse:** Synchrone und coalesced Save-Pfade sowie Loader-Recovery über alle drei Snapshot-Dateien verfolgen.
* **Test:** Erzwungener Fehler zwischen Live-Replaces und simuliertes Neustart-Journal müssen exakt die alte Dreiergeneration wiederherstellen.
* **Implementierung:** Gemeinsames Commit-Journal, Backups und idempotente Recovery vor `_load_index()` ergänzen; beide Writer verwenden denselben Commit-Helper.
* **QC:** Snapshot-/VectorStore-Regressionen und Compile-Sweep ausführen.

## Phase 17: H-05 Doppelte VRAM-Reservierung

* **Analyse:** Budget-Lebensdauer von `video_analysis_full`, RAFT und SigLIP über Router, GPU-Lock und Modell-Loader verfolgen.
* **Test:** Zusammengesetzter GPU-Task muss Lock und Telemetrie nutzen, ohne sein äußeres Budget zu reservieren oder zu committen.
* **Implementierung:** `with_gpu_task()` erhält einen expliziten Schalter für intern verwaltete Modellbudgets; Videoanalyse deaktiviert nur die äußere Reservierung.
* **QC:** VRAM-Telemetrie-, Video-Router- und DirectML-Zieltests sowie Compile-Sweep ausführen.

## Phase 18: H-06 Trigger-Coverage langer Mixe

* **Analyse:** 600-s-Snapshot, Streaming-Result, Audio-Cache-Persistenz und Pacing-Injektion als eine Triggerkette verfolgen.
* **Test:** Mehrfenster-Audio muss Onsets aus späten Chunks liefern; `energy_only` hält Triggerlisten leer.
* **Implementierung:** Trigger pro Streaming-Chunk mit absoluten Zeitstempeln sammeln und an Overlap-Grenzen deduplizieren; Audio-Router verwendet diese Listen statt des 600-s-Snapshots.
* **QC:** Streaming-, Audioanalyse- und Pacing-Cache-Cluster sowie Compile-Sweep ausführen.

## Phase 19: H-07 Render-Queue-Restart

* **Analyse:** Persistierten Queue-Datensatz, Startup-Restore und `_run_render_task()` auf vollständige Rekonstruierbarkeit verfolgen.
* **Test:** `running`-Job mit Resume-Payload muss nach Startup erneut geplant werden; Altjob ohne Payload muss terminal und erklärbar fehlschlagen.
* **Implementierung:** Versionierten Request-, Timeline- und Projektwurzel-Snapshot in `settings_json` speichern und Pending-Jobs im Lifespan rekonstruieren.
* **QC:** Render-Persistenz-, Router- und Cancel/AMF-Cluster sowie Compile-Sweep ausführen.

## Phase 20: H-08 WPF-Projektcache-Invalidierung

* **Analyse:** Direkten Projektwechsel über `ProjectService`, Messenger-Empfänger, Shared-State-Services und Thumbnail-Cache verfolgen.
* **Test:** Statischer Lifecycle-Vertrag fordert Closing→Closed→Opened, Audio-State-Clear, Generation-Invalidierung und Thumbnail-Clear.
* **Implementierung:** Erfolgreichen Switch atomar publizieren; State-Service-Generationen verhindern Late-Write alter Refreshes.
* **QC:** WPF-Vertragstests und Release-Build ausführen.

## Phase 21: H-09 UI-Thread-sichere Projektmeldungen

* **Analyse:** Alle Sender von ProjectClosing/Closed und direkte Collection-Mutationen der Empfänger auf Thread-Herkunft prüfen.
* **Test:** Statischer Vertrag fordert Dispatcher-Marshalling für Close und Direct-Switch.
* **Implementierung:** Zentralen `RunOnUiThread`-Pfad des `ProjectService` für alle Lifecycle-Publikationen verwenden.
* **QC:** WPF-Lifecycle-Vertrag und Release-Build ausführen.

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

## Phase 32: Nicht-blockierendes WPF-Dateilogging

1. Den manuellen globalen Klick-Audit-Hook aus `MainWindow.xaml.cs` entfernen.
2. `FileLoggerProvider` auf eine begrenzte Multi-Writer-/Single-Reader-Queue mit Hintergrund-Dateiwriter umstellen.
3. Statischen WPF-Vertrag testen und den Release-Build ausführen.

## Phase 33: VectorStore-Writer-Lifecycle

1. Regressionen für Indexwechsel, Thread-Ende und Neuerzeugung nach Close ergänzen.
2. Beim Singleton-Wechsel die alte Instanz geordnet schließen und final speichern.
3. VectorStore-/Persistenztests und Python-Compile-Sweep ausführen.

## Phase 34: Canvas-Pacing-Datenfluss

1. Vertragstests für Canvas-Weitergabe und einmalige Clip-ID-Präfixierung ergänzen.
2. Backend-Schema, Router, OpenAPI-Snapshot und aktives C#-DTO synchronisieren.
3. Canvas-Pfad im Director-ViewModel/View erreichbar machen und an den Request binden.
4. Pacing-/OpenAPI-/WPF-Verträge, Compile-Sweep und Release-Build ausführen.

## Phase 35: Projektübersicht-Timeline-Status

1. Statischen WPF-Vertrag für die drei Timeline-Zustände ergänzen.
2. Abgeleiteten Statustext und Generate-Sichtbarkeit im ViewModel implementieren.
3. XAML-Bindings und WPF Release-Build verifizieren.

## Phase 36: Terminal-Log-History

1. Vertrag für zentrale History, beide Logquellen und Replay ergänzen.
2. Begrenzten thread-sicheren TerminalLogBuffer als Singleton implementieren.
3. TerminalLoggerProvider und SSEClient in den Puffer schreiben lassen; ViewModel auf Replay/Subscription umstellen.
4. Terminal-/WPF-Verträge und Release-Build ausführen.

## Phase 37: AI-Config-Reader konsolidieren

1. ConfigManager-Priorität, Disk-Fallback und Alias-Kompatibilität regressieren.
2. Gemeinsamen AI-Config-Helper anlegen und beide identischen Funktionskörper durch lokale Aliase ersetzen.
3. Brain-/Vision-/Provider-Tests und Compile-Sweep ausführen.

## Phase 38: Projekt-Lifecycle-Command-Wiring

1. Statischen Vertrag für Save/Close-Bindings und den internen Anchor-Reload ergänzen.
2. Save/Close im zuständigen Projektübersicht-ViewModel implementieren und in der View binden.
3. Ungenutzte MainViewModel-Projektcommand-Duplikate sowie das ungebundene Anchor-Reload-Command entfernen.
4. WPF-Verträge und Release-Build ausführen.

## Phase 39: Tote Modell-Convenience-Helper

1. Aufrufer und Exporte der gemeldeten SigLIP-/Moondream-Helper vollständig prüfen.
2. Ausschließlich nachweislich unreferenzierte Convenience-Funktionen entfernen.
3. Statischen Vertrag, Moondream-/SigLIP-Tests und Compile-Sweep ausführen.

## Phase 40: Zombie-Wächter-Shutdown

1. Lifespan-Vertrag für Cancel-before-cleanup und vollständiges Task-Join ergänzen.
2. Zombie-Wächter gezielt canceln und vor Ressourcen-Cleanup awaiten.
3. Backend-Vertrag, Main-/Lifespan-Tests und Compile-Sweep ausführen.

## Phase 41: Atomarer WPF-Projekt-Close

1. Fehlervertrag für erfolglosen Close und ausbleibende Lifecycle-Meldungen ergänzen.
2. API-Erfolg vor lokaler Closing/Closed-Zustandsänderung prüfen.
3. Projektübersicht auf den booleschen Close-Vertrag umstellen.
4. WPF-Projektverträge und Release-Build ausführen.

## Phase 42: WPF-Projekt-Refresh-Lifecycle

1. Vertrag für Dispatcher-Zustellung, fehlertoleranten Refresh und genau eine Open-Meldung ergänzen.
2. Refresh über den zentralen `SwitchToProject()`-Pfad leiten.
3. Doppelte Open-Meldung aus `MainViewModel` entfernen.
4. WPF-Projektverträge und Release-Build ausführen.

## Phase 43: WPF-Projekt-Save-Dispatcher

1. Vertrag für atomaren UI-Thread-Save-State ergänzen.
2. Save-Info und ProjectChanged gemeinsam über `RunOnUiThread()` veröffentlichen.
3. WPF-Projektverträge und Release-Build ausführen.

## Phase 44: Settings-VRAM-Debounce

1. Vertrag für UI-kontextbewahrendes Debounce und CTS-Lifecycle ergänzen.
2. Threadpool-Wrapper durch eine cancelbare Async-Methode ersetzen.
3. WPF-Settings-Vertrag und Release-Build ausführen.

## Phase 45: VRAM-Telemetrie-Load-Lifecycle

1. Vertrag für CTS-Ownership und generationssicheren Loading-State ergänzen.
2. Ersetzte Loads canceln und ihre CTS im jeweiligen `finally` disposen.
3. WPF-Telemetrie-Vertrag und Release-Build ausführen.

## Phase 46: Chat-Stream-View-Lifecycle

1. Vertrag für Scope-Dispose, Stream-CTS und Generation-Ownership ergänzen.
2. ChatViewModel disposable machen und späte Stream-/Clear-Updates sperren.
3. Chat-Verträge, Backend-Chat-Cluster und WPF Release-Build ausführen.

## Phase 47: Model-Manager-Load-Lifecycle

1. Vertrag für CTS-Ownership und generationssicheren Loading-State ergänzen.
2. Pro Load eine lokale CTS besitzen und nur dem aktuellen Load Status-Cleanup erlauben.
3. Modell-Verträge, Registry-/Router-Tests und WPF Release-Build ausführen.

## Phase 48: Settings-FFmpeg-Probe-Lifecycle

1. Vertrag für Pfad-Cancellation, CTS-Ownership und aktuellen Probe-State ergänzen.
2. Aktive Probe bei Pfadänderung canceln und Ressourcen pro Ausführung besitzen.
3. Settings-/Config-Verträge und WPF Release-Build ausführen.

## Phase 49: Video-Szenen-Selection-Race

1. Vertrag für Szenenload-Sequenz, Clip-ID-Prüfung und Loading-Ownership ergänzen.
2. Auswahlwechsel und Szenen-Refresh über eine monotone Sequenz absichern.
3. Video-/WPF-Verträge und Release-Build ausführen.

## Phase 50: Timeline-Reset-Async-Races

1. Vertrag für Reset-Invalidierung, Dispatcher-Rechecks und sicheren Gate-Lifecycle ergänzen.
2. Timeline-, Waveform- und Motion-Generationen bei Reset/Dispose invalidieren.
3. Timeline-/WPF-Verträge und Release-Build ausführen.

## Phase 51: WPF-Load-Gate-Dispose-Races

1. Vertrag für scope-sichere Load-Gates und Shutdown-Invalidierung ergänzen.
2. Anchor-, VideoLibrary- und Director-Gates nicht während laufender Tasks disposen.
3. Anchor/Director bei Dispose invalidieren und Folge-Reloads nach Shutdown sperren.
4. WPF-Lifecycle-Verträge und Release-Build ausführen.

## Phase 52: PythonBridge-OnExit-Gate-Race

1. Vertrag für OnExit-Timeout und noch laufende Bridge-Operationen ergänzen.
2. Lifecycle-Gate beim synchronen Service-Dispose nicht vor In-flight-Releases zerstören.
3. Bridge-/App-Lifecycle-Verträge und Release-Build ausführen.

## Phase 53: SSE-Listener-Token-Generation

1. Vertrag für lokale CTS-Bindung pro SSE-Startgeneration ergänzen.
2. Listener-Tasks mit dem unveränderlichen lokalen Token starten und Starts nach Dispose sperren.
3. SSE-Lifecycle-Verträge und Release-Build ausführen.

## Phase 54: SSE-Reconnect-Dictionary-Race

1. Vertrag für atomare Reconnect-Throttle-Zugriffe ergänzen.
2. Dictionary-Lookup und -Update unter dem vorhandenen State-Lock bündeln.
3. SSE-Threading-Verträge und Release-Build ausführen.

## Phase 55: SSE-Multi-Stream-Verbindungsstatus

1. Vertrag für aggregierten Stream-Status und Generation-Isolation ergänzen.
2. Verbindungszustand pro Stream-Art unter State-Lock führen.
3. EOF, Cancellation und Fehler generationstreu austragen; Unerreichbarkeit nur ohne offene Streams melden.
4. SSE-Statusverträge und Release-Build ausführen.

## Phase 56: ProjectOverview-Refresh-Coalescing

1. Vertrag für generationssicheren, verlustfreien Dashboard-Refresh ergänzen.
2. Aktiven Refresh atomar besitzen und überlappende Signale coalescen.
3. Ergebnisse nach jedem Await gegen Generation/Dispose prüfen und letzten Refresh nachholen.
4. Projekt-Dashboard-Verträge und Release-Build ausführen.

## Phase 57: ProjectOverview-Dead-DI

1. Vertrag gegen ungenutzte Dashboard-DI ergänzen.
2. Totes Video-State-Feld und Konstruktorparameter entfernen.
3. Dashboard-Vertrag und Release-Build ausführen.

## Phase 58: Brain-UI-Load-Generationen

1. Vertrag für projektgebundene Stats-/Learning-Loads und Loading-Ownership ergänzen.
2. Stats und Learning Session vor Late-Writes durch eigene Generationen schützen.
3. Projekt-Close und Dispose invalidieren Loads; nur aktuelle Loading-Generation beendet den Spinner.
4. Brain-/WPF-Verträge und Release-Build ausführen.

## Phase 59: Freigegebene Live-Datenreparaturen

1. Backend-Ausstand prüfen und timestamped SQLite-/FAISS-Backups erzeugen.
2. Backup-Integrität und Dateihashes vor Mutation verifizieren.
3. Mehrdeutigen FAISS-Orphan 897 tombstonieren und Snapshot geordnet schließen.
4. JSON-Blobs mit zentralen Migratoren in einer SQLite-Transaktion persistieren.
5. Live-DB, Index, Tombstones, Schlüsselbewahrung und Versionszählungen verifizieren.

## Phase 60: DirectML-Separator und Dead-Code

1. Separator-Vertrag für ONNX-DML-only und Demucs-CPU-Ausnahme ergänzen.
2. CPU-Provider/-Fallback nur aus ONNX-Pfad entfernen; Session-Flags erhalten.
3. Aktive Referenzen der freigegebenen Dead-Dateien erneut prüfen und Dateien/Baum löschen.
4. Audio-/Dead-Code-Verträge, Compile und WPF-Build ausführen.

## Phase 61: SDD-Gate und Gesamt-QC

1. Falsche Erfolgsmarker löschen.
2. Audit-Gate, Zielcluster, Vollsuite und Release-Build ausführen.
3. QC-Bericht nur anhand realer Resultate aktualisieren; Marker erst bei vollständigem Pass neu erzeugen.

## Phase 62: Separator-Patch-Parallelität

1. Einen Parallelitätsvertrag für zwei DirectML-Separator-Instanzen ergänzen.
2. Den globalen `SessionOptions`-Patch über seinen vollständigen Lebenszyklus serialisieren.
3. Separator-Zieltests, Python-Compile und vollständige Regression erneut ausführen.

## Phase 63: Atomarer Projekt-Open

1. DB-Ladefehler und Erhalt des aktiven Projekts als Router-Vertrag abdecken.
2. Den neuen Medienkatalog in einem isolierten `AppState` vorladen.
3. Brain und Live-State erst nach erfolgreichem Preload umschalten.
4. Projekt-, DB- und vollständige Regressionstests erneut ausführen.

## Phase 64: BeatNet-Import-Hygiene

1. Die reale `sys.modules`-Kontamination bei fehlendem PyAudio abdecken.
2. Den PyAudio-Stub auf den BeatNet-Importversuch begrenzen.
3. Beat-/Audio-Zieltests, Compile und Gesamtregression ausführen.

## Phase 65: Python-3.11-Launcher-Gate

1. Den WPF-Launcher-Vertrag gegen Python 3.12 und unversionierte Fallbacks absichern.
2. Kandidaten auf eine reale `Python 3.11.x`-Versionsausgabe prüfen.
3. WPF-Verträge, Release-Build und Gesamtregression ausführen.

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

## Strategische Consulting Fixes (F1 - F5) (Neu)

Um die vollständige Release-Bereitschaft zu erreichen, beheben wir die folgenden 5 identifizierten Risiken:
- **F1 (VRAM-Absicherung):** Einführung eines globalen synchronen `gpu_inference_lock` in `src/pb_studio/core/gpu_lock.py` und Absicherung aller ONNX Inferenz-Aufrufe (RAFT, SigLIP, Moondream, AudioSeparator) zur Verhinderung paralleler GPU-Auslastungen auf Systemen mit <= 8GB VRAM.
- **F2 (Native Crash Logging):** Registrierung von Pythons nativem `faulthandler` beim Start des Backends (`backend/main.py`), um native C++ Access Violations der `onnxruntime.dll` / DirectML in `logs/native_crash.log` zu loggen statt stummem Absturz.
- **F3 (VLM-Timeout):** Kürzung des LM Studio VLM-Timeouts von 60s auf 15s in `src/pb_studio/video/lmstudio_vision_wrapper.py` mit `asyncio.wait_for`-Absicherung, um bei hängenden Verbindungen zügig auf das lokale Moondream-ONNX Fallback umzuschalten.
- **F4 (4h-Resilience-Gate):** Korrektur des relativen Pfad-Bugs in `scripts/qa/stress_4h.bat` und Starten des Langzeit-Stresstests im Hintergrund zur Absicherung der 4h-Resilienz.
- **F5 (SQLite write block):** Entkoppelung der CPU-/IO-intensiven FAISS Tombstone-Markierung (`vs.mark_tombstoned`) aus dem SQLite Transaktions-Scope in `backend/routers/video_router.py`, um SQLite-Lock-Contention zu verhindern.


