# PB Studio Vollaudit — 2026-07-26

## Fix-Fortschritt 2026-07-28

- **C-03 RESOLVED:** ONNX-Stems sind DirectML-only; Demucs bleibt der absichtliche PyTorch-CPU-Pfad. Der prozessglobale SessionOptions-Patch ist über Instanzen serialisiert. DirectML-Zielcluster **37 passed**.
- **C-04 RESOLVED:** Falsche Erfolgsmarker wurden entfernt; Audit-Gate **3 passed**.
- **M-03 RESOLVED:** Live-Orphan 897 wurde wegen mehrdeutiger gleichnamiger Medien sicher tombstoniert statt spekulativ verknüpft. FAISS **898/898**, 113 Tombstones.
- **M-05 RESOLVED:** Live-Migration nach verifiziertem Backup: Metadata **1775/1775 v1**, AI **802/802 v1**, SQLite integer, 0 FK-Verstöße.
- **M-31 RESOLVED:** Parallele Separator-Instanzen hinterlassen immer den originalen ORT-Konstruktor.
- **M-32 RESOLVED:** `/project/open` lädt den SQLite-Katalog isoliert vor; Fehler bewahren das aktive Runtime-Projekt und die Brain-Bindung.
- **M-33 RESOLVED:** Der BeatNet-PyAudio-Importstub wird nach Erfolg oder Fehlschlag aus `sys.modules` entfernt.
- **M-34 RESOLVED:** Der WPF-Launcher startet ausschließlich nachgewiesenes Python 3.11; inkompatible/unversionierte Fallbacks wurden entfernt.
- Vollsuite **853 passed, 11 skipped, 0 failed**; WPF Release **0 Warnungen/0 Fehler**; Python-Compile und Diff-Check **PASS**.

## Fix-Fortschritt 2026-07-27

- **C-01 RESOLVED:** Waveform-Cache-Tupel wird atomar im `AdvancedPacingEngine` initialisiert; Analysemetadaten markieren `_cached_audio_path` nicht mehr als geladen.
- **C-02 RESOLVED:** Live-API, WPF, Chat-Tool, RenderService und VideoGenerator sind AMF-only; fehlendes AMF erzeugt einen expliziten Fehler statt CPU-Fallback.
- **C-03 RESOLVED 2026-07-28:** `ModelLoader`, RAFT-Factory/-Export, SmartDirector-Motion und ONNX-Audio-Separation sind DirectML-only.
- Regression: `Tests/test_pacing_cached_energy.py` **4 passed**; Pacing-Cluster **101 passed, 1 skipped**.
- C-03-Regression: DirectML-/Motion-Cluster **26 passed**; reale Providerlisten enthalten ausschließlich `DmlExecutionProvider`.
- Realer Release-Smoke **PASS**: 3 Cuts erzeugt, Timeline gespeichert, Render-Task gestartet und sauber abgebrochen.
- WPF Release-Build **0 Fehler/0 Warnungen**; Python-Compile **274/274**.
- C-02-Live-Proof: echte Encoder-Erkennung wählte `hevc_amf`; Release-Smoke danach vollständig PASS.
- Finale C-03-Suite: **762 passed, 11 skipped, 2 failed**; Python-Compile **276/276**.
- **H-01 RESOLVED:** Fehlende/offline Medien bleiben in SQLite erhalten; ihre Clip-IDs werden beim Restore weiterhin reserviert. Persistenz-Cluster **46 passed**.
- **H-02 RESOLVED:** Brain-Pfad und `state_conn` wechseln atomar; Bind-Fehler stoppen Create/Open vor dem Runtime-State-Reset. Brain-/Projekt-Cluster **137 passed**.
- **H-03 RESOLVED:** FAISS-Kompaktierung veröffentlicht neue IDs nur nach erfolgreichem SQLite-Remap. VectorStore-/Data-Cluster **22 passed**.
- Der vorbestehende VectorStore-`_save_cv`-Testfehler ist als ungültige `__new__`-Fixture korrigiert; vollständiger VectorStore-Cluster **6 passed**.
- Der vorbestehende Generation-Cancel-Fehler ist behoben: Reset bei Jobannahme, danach verlustfreies Cancel bis Render. Integration **24 passed**, angrenzende Render-Cluster **36 passed**.
- Finale Vollsuite nach M-14: **825 passed, 11 skipped, 1 failed**; einziger Fehler ist der absichtliche Gate-Test für die noch vorhandenen `.completed`/`.qc-passed`-Marker. Python-Compile-Sweep für Backend, Source und Tests sowie `git diff --check` **PASS**.
- **H-04 RESOLVED:** Dreifach-Snapshot nutzt Journal+Backups; Mid-Replace-Fehler und Neustart-Recovery stellen die vorige Generation vollständig her. VectorStore/Data **25 passed**.
- **H-05 RESOLVED:** Videoanalyse behält GPU-Lock und Telemetrie, reserviert aber kein zusätzliches Composite-Budget über RAFT/SigLIP. VRAM/DirectML/Video **36 passed**.
- **H-06 RESOLVED:** Streaming-Analyse aggregiert Onset/Kick/Snare/HiHat über alle Chunks; Kandidaten nach Minute 10 erreichen den Pacing-Cache. Audio/Streaming/Pacing **28 passed**.
- **H-07 RESOLVED:** Render-Jobs persistieren versionierten Request-/Timeline-Snapshot und werden im Lifespan wirklich neu eingeplant. Render/Router/AMF **52 passed**.
- **H-08/H-09 RESOLVED:** Direkter Projektwechsel invalidiert State-/Thumbnail-Generationen; Lifecycle-Nachrichten laufen geordnet über den WPF-Dispatcher. Vertrag **5 passed**, Release **0/0**.
- **M-01 RESOLVED:** Medien werden erst nach erfolgreicher DB-/Tombstone-Verarbeitung aus RAM und Analyse-Cache entfernt; Fehler erreichen den API-Fehlerpfad. AppState-/Router-/Persistenz-Cluster **55 passed**.
- **M-02 RESOLVED:** Audio-/Videoimport verlangt einen aktiven DB-Projektkontext; ohne Projekt antworten beide Endpunkte mit HTTP 409 und erzeugen keinen Clip. Router-/Persistenz-Cluster **59 passed**.
- **M-03 PIPELINE RESOLVED / LIVE DATA OPEN:** Neue Embeddings ohne Medienlink werden abgelehnt; Linkfehler rollen den Vektor zurück oder tombstonieren ihn. Data-/Router-Cluster **72 passed**. Der bereits vorhandene Live-Orphan bleibt bis zur expliziten Datenreparatur-Freigabe unverändert.
- **M-04 RESOLVED:** Brain-Stats serialisiert alle direkten `weights_conn`-Reads über `_weights_lock`. Brain-Router/Recovery/Core/Binding **45 passed**.
- **M-05 CODE RESOLVED / LIVE MIGRATION OPEN:** `.wmv/.flv` verwenden Video-Schemata; normale Metadata-/AI-Schreibpfade persistieren `__schema_version`. Repository/Schema/Storage/Persistenz **57 passed**. Die 2.544 bestehenden Live-Blobs wurden nicht verändert.
- **M-06 RESOLVED:** Fehlgeschlagene Streaming-Chunks reservieren ihre Energy-Zeit als Null-Lücke; spätere Peaks verschieben sich nicht nach vorn. Streaming/Audio/Pacing/Router **44 passed**.
- **M-07 RESOLVED:** Segmentanalyse berechnet einen RAFT-Flow pro Frame-Paar und leitet Motion sowie Scene-Change daraus ab. Progress/DirectML/VRAM/Video **30 passed**.
- **M-08 RESOLVED:** Lernsession-Button toggelt Play/Pause, zeigt den Zustand an und setzt ihn bei Cut-Wechsel zurück. WPF-Vertrag **1 passed**, Release **0/0**.
- **M-09 RESOLVED:** Videoanalyse/-import und Pacing filtern SSE-Progress nach aktiver Clip-/Task-Korrelation. Router/Pacing/Vertrag **36 passed**, WPF Release **0/0**.
- **M-10 RESOLVED:** Der aktive handgeschriebene `ApiClient`-Vertrag enthält die aktuellen Audio-Trigger/Subtracks und Video-Mood/Farb-/Embedding-Felder. Vertrag **1 passed**, WPF Release **0/0**.
- **M-11 RESOLVED:** Produktion erfasst keine globalen UI-Klicks mehr; Dateilogzeilen laufen über eine begrenzte Queue und einen einzelnen Hintergrund-Writer. WPF-Verträge **10 passed**, Release **0/0**.
- **M-12 RESOLVED:** Ein VectorStore-Indexwechsel schließt, leert und speichert die vorige Instanz; Close beendet den Writer und erlaubt eine frische Neuerzeugung. Data-/AppState-/Router-Cluster **74 passed**.
- **LOW-02 RESOLVED:** `canvas_path` läuft durch Backend/OpenAPI/WPF in den aktiven Pacing-Pfad; Clip-IDs werden genau einmal präfixiert. Pacing **98 passed**, Canvas/OpenAPI **7 passed**, Release **0/0**.
- **LOW-07 RESOLVED:** Projektübersicht unterscheidet kein Projekt, fehlende Timeline und generierte Timeline; der Director-Button erscheint nicht ohne Projekt. Verträge **6 passed**, Release **0/0**.
- **LOW-08 RESOLVED:** WPF- und Backend-SSE-Logs laufen in einen gemeinsamen 100k-History-Puffer und werden beim Terminal-ViewModel-Start replayed. WPF-Verträge **13 passed**, Release **0/0**.
- **LOW-04 RESOLVED:** Brain-Narrator und LM-Studio-Vision verwenden denselben ConfigManager-first-/Disk-Fallback-Helper; private und Ollama-Shim-Aliase bleiben kompatibel. AI/Provider/Registry **94 passed**.
- Gesamtstatus bleibt **FAIL**: C-03 ist teilweise offen, C-04 sowie 2 MEDIUM-Livedatenfälle und 4 LOW/Dead sind offen. Alle HIGH-Findings sind behoben.

**Scope:** aktueller Working Tree auf `00013-system-wide-bug-hunting-audit`  
**Status:** **FAIL — nicht release-ready**  
**Änderungen durch Audit:** keine Produktcode-Fixes; nur Bericht, GUI-Screenshots und neues isoliertes Smoke-Testprojekt  
**Bekannte Ausgangslage:** Working Tree war vor Audit bereits stark verändert und enthielt uncommittete/staged Löschungen sowie untracked Fix-/Audit-Dateien.

## Ergebnis

| Schwere | Anzahl |
|---|---:|
| KRITISCH | 4 |
| HOCH | 10 |
| MITTEL | 12 |
| NIEDRIG / Dead Code | 8 |

Kernworkflow ist aktuell blockiert: realer Release-Smoke erreicht Audio-Import und -Analyse, bricht aber bei `/pacing/generate` mit fehlendem `_cached_y` ab. Full-Test-Suite hat zusätzlich 2 Fehler.

## Verifikation

| Prüfung | Ergebnis |
|---|---|
| Python | 3.11.9 — PASS |
| NumPy | 1.26.4 — PASS |
| ONNX Runtime | 1.19.2, `DmlExecutionProvider` verfügbar — PASS |
| Kernimporte | 11/11 — PASS |
| Python-Syntax | 274 Dateien, 0 Fehler — PASS |
| SQLite | 23 DBs: `integrity_check=ok`, 0 FK-Verletzungen — PASS |
| FFmpeg | `h264_amf`, `hevc_amf`, `av1_amf` vorhanden — PASS |
| Backend `/health` | HTTP 200, sauberer Shutdown — PASS |
| WPF Release-Build | 0 Fehler, 0 Warnungen — PASS |
| XAML | 17 Dateien XML-valide — PASS |
| OpenAPI | Snapshot-Drift-Tests und HTTP-Methoden-Abgleich — PASS |
| Pytest komplett | **735 passed, 12 skipped, 2 failed — zweimal identisch reproduziert — FAIL** |
| Release-E2E | **FAIL bei Pacing-Generation** |
| WPF UIA/Render | 13/13 Checks, alle 12 Tabs sichtbar — PASS |
| Terminal Log-SSE | Post-Connect-Warning live empfangen — PASS |
| Ruff | 252 Meldungen; überwiegend Test-Hygiene/Low, mehrere F821 durch lokale Lazy-Imports falsch-positiv |

## KRITISCH

### C-01 — Live-Pacing crasht im normalen API-Workflow

**Beweis:** `verify_release_smoke.ps1` erzeugte ein Projekt, importierte Audio/Video, analysierte Audio und rief `/pacing/generate` auf. Antwort:

```text
Generierung fehlgeschlagen: Cut-List-Generierung endgültig fehlgeschlagen:
'AdvancedPacingEngine' object has no attribute '_cached_y'
```

**Root Cause:**

- `src/pb_studio/services/pacing_service.py:227` setzt `_cached_audio_path`, aber nicht `_cached_y`.
- `src/pb_studio/pacing/advanced_pacing_engine.py:1091-1094` initialisiert `_cached_y` nur, wenn `_cached_audio_path` noch nicht existiert.
- `advanced_pacing_engine.py:1096` greift danach zwingend auf `_cached_y` zu.

**Impact:** Audio → Pacing → Timeline → Render ist im realen Release-Smoke unterbrochen.

### C-02 — Software-Encoder sind trotz AMF-only-Regel live verdrahtet

**Belege:**

- `PBStudio.UI/ViewModels/ProductionViewModel.cs:43` und `PBStudio.UI/Views/ProductionView.xaml:91-106` bieten `libx264` als CPU-Fallback an.
- `backend/schemas/render_schemas.py:17-23` akzeptiert `libx264`/`libx265`.
- `src/pb_studio/rendering/render_service.py:90-122,353-387,516-527,563-571` wählt/benutzt CPU-Encoder live.
- `src/pb_studio/video/encoder_utils.py:250-371` implementiert `libx264`, `libx265`, `libsvtav1`.
- `src/pb_studio/ai/tool_registry.py:39` exponiert verbotene Encoder an Tools.

**Impact:** Direkter Verstoß gegen IRON RULE R4; Laufzeit kann unbemerkt von AMF auf CPU-Encoding wechseln.

### C-03 — RESOLVED: Live-ONNX-Pfade erlaubten CPU-Fallback

**Status 2026-07-27:** **TEILWEISE BEHOBEN.** `ModelLoader` akzeptiert nur noch `DmlExecutionProvider`; Farneback und `ALLOW_CPU_FALLBACK` wurden aus RAFT und dem aktiven SmartDirector-Pfad entfernt. SmartDirector verwendet eine RAFT-Session pro Clip-Batch und entlädt sie garantiert. Restbefund: `audio/separator.py` ist durch den aktiven `audio-expertise`-Skill gesperrt und wurde ohne explizite Nutzerfreigabe nicht verändert.

**Belege:**

- `src/pb_studio/core/model_loader.py:201-212` hängt immer `CPUExecutionProvider` an die Provider-Liste.
- Live-SigLIP nutzt diesen Loader über `siglip_wrapper.py:113-140`.
- `src/pb_studio/audio/separator.py:158-168` setzt `["DmlExecutionProvider", "CPUExecutionProvider"]` und fällt ohne DML komplett auf CPU zurück.
- `src/pb_studio/video/raft.py:718-809` enthält einen aktivierbaren Farneback-CPU-Fallback.

**Impact:** ONNX Runtime darf einzelne Nodes oder ganze Modelle still auf CPU ausführen. Direkter Verstoß gegen IRON RULE R1; RAM-/Latenzspitzen und falsche GPU-Statusannahmen möglich.

### C-04 — RESOLVED: SDD/QC-Metadaten meldeten fälschlich Erfolg

**Belege:**

- `specs/00013-system-wide-bug-hunting-audit/qc-report.md` meldet `PASSED` und „release ready“.
- Pflichtmarker `.completed` und `.qc-passed` fehlen.
- `tasks.md` nutzt `[x]` statt des einzig erlaubten `[X]`.
- Aktueller Stand hat 2 Pytest-Fehler und einen reproduzierten E2E-Blocker.

**Impact:** Release-Gate und dokumentierter Zustand widersprechen realer Software. Verstoß gegen verbindliche SDD-Phase-Gates.

## HOCH

### H-01 — Projekt-Öffnen löscht Daten bei temporär fehlenden Mediendateien

**Status 2026-07-27:** **BEHOBEN.** `load_from_db()` löscht fehlende Medien nicht mehr. Metadaten werden vor dem Dateisystem-Gate gelesen, sodass die persistierte Clip-ID trotz offline Datei reserviert bleibt und kein späterer Import dieselbe ID erhält.

`backend/app_state.py:962-975` ruft `repo.delete_media()` auf, wenn `Path.exists()` false ist; `backend/routers/project_router.py:225-228` nutzt dies beim Öffnen. Offline-Netzlaufwerk/removable media führt damit zu dauerhaftem Verlust von Analyse und `vector_map`. FAISS wird in diesem Pfad nicht tombstoned.

### H-02 — Fehlgeschlagener Brain-Rebind kann Feedback ins alte Projekt schreiben

**Status 2026-07-27:** **BEHOBEN.** Die neue SQLite-Connection wird vollständig geöffnet und initialisiert, bevor Pfad/Connection getauscht und die alte Verbindung geschlossen wird. Create/Open führen das Brain-Binding vor `AppState.reset()` aus und antworten bei Fehler mit HTTP 500.

`backend/routers/project_router.py:38-49` verschluckt Bind-Fehler. `src/pb_studio/brain/brain_service.py:53-70` ersetzt die alte `state_conn` erst nach erfolgreichem Öffnen der neuen DB. Projektwechsel kann erfolgreich erscheinen, während Brain weiter auf vorherige `state.db` schreibt.

### H-03 — FAISS-Kompaktion ignoriert fehlgeschlagenes SQLite-ID-Remapping

**Status 2026-07-27:** **BEHOBEN.** Ein Fehler der `vector_map`-Transaktion propagiert bis zur äußeren Kompaktierungsgrenze. Der aktive Index, Metadaten und Tombstones bleiben unverändert; kein Snapshot-Save wird angefordert.

`src/pb_studio/data/vector_store.py:334-345` loggt fehlgeschlagene `vector_map`-Updates, tauscht Index/Metadaten aber trotzdem aus und löscht Tombstones (`:347-354`). Danach können Deletes falsche Vektoren tombstonen und Suche falsche Clip-Metadaten liefern.

### H-04 — FAISS-Snapshot ist nur pro Datei atomar

**Status 2026-07-27:** **BEHOBEN.** Beide Save-Pfade schreiben vor dem ersten Live-Replace Backups und ein fsync-gesichertes Journal. Fehler oder Loader-Neustart mit vorhandenem Journal stellen alle drei alten Dateien wieder her, bevor FAISS geladen wird.

`vector_store.py:415-435,489-509` ersetzt `.faiss`, Metadata-JSON und Tombstone-JSON nacheinander. Crash zwischen zwei `os.replace` erzeugt generationenübergreifend inkonsistente Dateien. `_load_index` (`:117-168`) prüft weder Generation, Checksumme noch ID-Anzahl.

### H-05 — Videoanalyse bucht VRAM mehrfach

**Status 2026-07-27:** **BEHOBEN.** `with_gpu_task(..., manage_vram=False)` trennt Lock/Telemetrie von der äußeren Reservierung. RAFT und SigLIP bleiben alleinige Besitzer ihrer Sessions und Budgets; Regression misst 2400 MB interne Commitments statt 5300 MB Doppelzählung.

`backend/routers/video_router.py:465-468` reserviert `video_analysis_full=2900 MB`. RAFT reserviert erneut (`raft.py:188-198`), SigLIP nochmals über `ModelLoader` (`siglip_wrapper.py:113-134`, `model_loader.py:268-314`). Buchhaltung kann 5.3–5.8 GB statt 2.9 GB zeigen: falsche OOMs/Evictions.

### H-06 — Lange Mixe verlieren Trigger nach Minute 10

**Status 2026-07-27:** **BEHOBEN.** `StreamingAudioAnalyzer` extrahiert Onset/Kick/Snare/HiHat pro Chunk, korrigiert auf absolute Zeiten und dedupliziert Overlap-Grenzen. Der Audio-Router übernimmt bei langen Mixen diese vollständigen Listen statt Trigger aus dem 600-s-Snapshot. Regression bestätigt einen Onset bei 701 s.

`audio_router.py:702-716,762-763` lädt bei Dateien >600 s nur 600 Sekunden. Onset/Kick/Snare/HiHat werden ausschließlich daraus berechnet (`:877-913`). `pacing_service.py:311-323` injiziert keine Coverage-Information; `advanced_pacing_engine.py:1081-1090` behandelt nichtleere Listen als vollständigen Cache.

### H-07 — Render-Queue wird nach Crash nicht fortgesetzt

**Status 2026-07-27:** **BEHOBEN.** Neue Queue-Jobs speichern RenderRequest, Timeline-Snapshot und Projektwurzel versioniert in `settings_json`. Startup rekonstruiert und plant `queued`/`interrupted` erneut; historische Jobs ohne Payload werden mit erklärbarem Fehler terminal markiert.

`render_queue.py:14-18` dokumentiert Retry. Startup setzt `running → interrupted` (`render_queue.py:352-391`, `app_state.py:1161-1185`), startet Jobs aber nie neu. `list_pending()` hat außerhalb Tests keinen Aufrufer.

### H-08 — Projektwechsel lässt alte UI-Caches sichtbar

**Status 2026-07-27:** **BEHOBEN.** Erfolgreicher Direct-Switch publiziert Closing→Closed→Opened. Audio-/Video-State-Services verwenden Generationen gegen Late-Write alter Refreshes; Audio-Reset leert Shared State, Video-Reset leert Thumbnail- und Failure-Cache.

`ProjectOverviewViewModel.cs:116` öffnet direkt ein anderes Projekt. `ProjectService.cs:42` sendet dabei kein `ProjectClosing`/`ProjectClosed`. Audio-/Video-State-Services behalten Cache und Refresh-Tasks; Thumbnail-Cache ist nur nach numerischer Clip-ID indiziert (`VideoLibraryViewModel.cs:25`). Gleiche ID im neuen Projekt kann altes Bild/Clip zeigen.

### H-09 — `ProjectClosed` mutiert WPF-Collections vom Hintergrund-Thread

**Status 2026-07-27:** **BEHOBEN.** `ProjectService` marshalt Close und Direct-Switch vollständig über `Application.Current.Dispatcher`; Timeline-/Video-Collection-Handler werden dadurch auf dem UI-Thread aufgerufen.

`ProjectService.cs:82` nutzt `ConfigureAwait(false)` und publiziert danach `ProjectClosed`. `TimelineViewModel.cs:139` und `VideoLibraryViewModel.cs:89` leeren gebundene Collections ohne Dispatcher. Folge: WPF-Cross-Thread-Ausnahme.

### H-10 — Cancel vor Renderphase wird verworfen

**Status 2026-07-27:** **BEHOBEN.** Cancel-Reset erfolgt bei synchroner Jobannahme; Render-Einstiege erhalten ein danach gesetztes Cancel-Signal. Integration 24 passed.

Reproduzierter Testfehler: `test_generate_from_timeline_cancel`. `GenerationService.cancel()` setzt das Flag schon während Audio-/Videoanalyse; `VideoGenerator.generate_from_timeline()` setzt es am Eintritt wieder auf `False` (`video/engine.py:429-456`). Cancellation zwischen Analyse und Renderstart geht verloren.

## MITTEL

### M-01 — RESOLVED: Delete-Endpunkte melden Erfolg nach DB-/FAISS-Fehler

Behoben: `AppState` verarbeitet SQLite und Video-Tombstones vor der RAM-Entfernung. Fehler erhalten Clip und Analyse-Cache, publizieren `persist_error` und werden erneut ausgelöst; Router können dadurch keinen falschen Erfolg mehr liefern.

### M-02 — RESOLVED: Import ohne geöffnetes Projekt kontaminiert Projekt 1

Behoben: Beide Import-Endpunkte prüfen den Projektkontext vor Dateizugriff und antworten ohne Projekt mit HTTP 409. `register_*_clip` und `persist_*_clip` verwenden den strikten aktiven Projekt-ID-Vertrag statt des Legacy-Fallbacks.

### M-03 — RESOLVED: Aktiver FAISS-Orphan tombstoniert

Der Erzeugungspfad ist behoben. Live-ID 897 (`test_20s.mp4`) konnte zwei gleichnamigen Medien verschiedener Projekte nicht eindeutig zugeordnet werden und wurde deshalb ohne erfundenen `vector_map`-Link tombstoniert.

### M-04 — RESOLVED: Brain-Stats umgeht DB-Lock

Behoben: Die positiven/negativen Buckets und die Learned-Axis-Abfrage laufen in einem gemeinsamen `BrainStore._weights_lock`-Scope. Ein Regressionstest verweigert jede ungesperrte Connection-Query.

### M-05 — RESOLVED: JSON-Schema-Migration persistiert

Der Codepfad ist behoben. Nach geprüftem Backup migrierte eine einzelne SQLite-Transaktion alle gültigen Live-Dicts mit den zentralen Audio-/Video-Migratoren: 1775 Metadata- und 802 AI-Blobs sind auf Schema v1; Originalschlüssel und -werte blieben erhalten.

### M-06 — RESOLVED: Streaming-Energy komprimiert Zeit nach Chunk-Fehler

Behoben: Load- und RMS-Fehler fügen anhand Chunkdauer, Overlap, Sample-Rate und Hop-Length eine downsample-kompatible Null-Lücke ein. Ein Regressionstest erzwingt den Fehler im mittleren Drittel und hält den späten Peak im letzten Drittel.

### M-07 — RESOLVED: RAFT berechnet Flow pro Frame-Paar doppelt

Behoben: `analyze_frame_pair` führt `calculate_flow()` einmal aus, erstellt gemeinsame Motion-Statistiken und leitet daraus P95-Magnitude sowie Scene-Change ab. Der Segmentpfad nutzt ausschließlich dieses Ergebnis.

### M-08 — RESOLVED: Brain-Lernsession kann nicht pausieren

Behoben: `PlayPauseCommand` toggelt `IsPlaying` und löst abwechselnd `PlayRequested`/`PauseRequested` aus. Das XAML bindet den dynamischen Buttontext; Cut-Wechsel setzt Playback auf gestoppt.

### M-09 — RESOLVED: Globale SSE-Progress-Events werden falschen Views zugeordnet

Behoben: Videoimport-Events tragen `video_import`, Pacing-Events `pacing:{audio_clip_id}` plus Clip-ID. VideoLibrary akzeptiert Analyse nur für `_activeAnalysisClipId` und Import nur für seine Domain; Director akzeptiert ausschließlich Pacing für `_activePacingAudioClipId`.

### M-10 — RESOLVED: Generierte und handgeschriebene API-DTOs driften

Behoben: Die tatsächlich von `ApiClient` deserialisierten Records enthalten Audio-Subtracks, Tempo-/Onset-/Drum-Listen sowie Video-Embedding-Samples, Audio-Key, Tag-Source, Mood-Tags und Farbmetriken. Ein Vertrags-Test schützt die aktuelle OpenAPI-Feldmenge.

### M-11 — Jeder UI-Klick schreibt synchron auf Disk

Behoben: Der globale manuelle Klick-Audit-Hook wurde aus `MainWindow` entfernt. `FileLoggerProvider` nimmt Logzeilen nicht-blockierend über eine begrenzte Queue an und schreibt sie geordnet auf einem einzelnen Hintergrund-Writer; Dispose schließt die Queue und leert sie mit begrenzter Shutdown-Wartezeit.

### M-12 — VectorStore-Writer-Lifecycle ist unvollständig

Behoben: Vor einem `index_name`-Wechsel wird die vorige Singleton-Instanz geschlossen, ihr Writer geordnet beendet und der letzte Zustand gespeichert. `close()` ist idempotent; eine geschlossene Instanz wird bei erneutem Zugriff nicht wiederverwendet. Der Atexit-Pfad stoppt den aktiven Writer vor dem finalen Snapshot.

### M-13 — RESOLVED: Zombie-Wächter wird beim Backend-Shutdown nicht gejoint

Behoben: Der Lifespan cancelt und awaited den Wächter vor Publisher-, Modell- und Datenbank-Cleanup. Nur die erwartete `asyncio.CancelledError` wird abgefangen; der Task kann nicht mehr parallel zur Ressourcenbereinigung weiterlaufen oder ausstehend zerstört werden.

### M-14 — RESOLVED: Fehlgeschlagener Projekt-Close leert WPF-Zustand

Behoben: `ProjectService` prüft die Close-Antwort vor jeder lokalen Lifecycle-Meldung und Zustandsänderung. Bei `null`/`success=false` bleiben aktuelles Projekt und UI-Caches erhalten; die Projektübersicht zeigt den Fehler statt fälschlich „geschlossen“.

### M-15 — RESOLVED: Projekt-Reconnect publiziert doppelt und außerhalb des Dispatchers

Behoben: `RefreshProjectInfoAsync()` leitet erfolgreiche Antworten durch den zentralen `SwitchToProject()`-Lifecycle. Damit laufen ProjectChanged/Open auf dem Dispatcher; die zusätzliche Open-Meldung in `MainViewModel` ist entfernt und ein fehlgeschlagener Info-Abruf überschreibt den lokalen Zustand nicht.

### M-16 — RESOLVED: Projekt-Save publiziert ProjectChanged vom Threadpool

Behoben: Der Save-Pfad lädt die aktualisierte Projektinfo nach dem API-Erfolg und veröffentlicht `CurrentProject` plus `ProjectChanged` anschließend atomar über `RunOnUiThread()`.

### M-17 — RESOLVED: Settings-VRAM-Debounce schreibt vom Threadpool in die UI

Behoben: Der Slider-Debounce läuft als UI-kontextbewahrende Async-Methode ohne `Task.Run`. Ersetzte CTS werden gecancelt und disposed; nach ViewModel-Dispose erfolgen keine Statusupdates mehr.

### M-18 — RESOLVED: Telemetrie-Refresh leakt CTS und löscht neueren Loading-State

Behoben: Jeder Telemetrie-Load besitzt und disposed seine CTS. Nur die aktuell in `_loadCts` registrierte Ausführung darf die Referenz leeren und `IsLoading=false` setzen; ein gecancelter Vorgänger kann den Zustand des Nachfolgers nicht mehr überschreiben.

### M-19 — RESOLVED: Chat-Stream überlebt View-Scope und überschreibt Clear

Behoben: `ChatViewModel` ist disposable und cancelt seinen aktiven SSE-Stream beim Scope-Ende. Stream-Generationen sperren späte Event-, Fehler- und Finalstatusupdates nach Clear/Dispose; jede Send-Ausführung disposed ihre CTS.

### M-20 — RESOLVED: Model-Manager-Load überschreibt neueren Loading-State

Behoben: Jeder Modellabruf besitzt und disposed seine CTS. Nur die aktuell registrierte Load-Ausführung darf `_loadCts` leeren und `IsLoading=false` setzen; gecancelte Vorgänger können den neuen Status nicht mehr verfälschen.

### M-21 — RESOLVED: Alte FFmpeg-Probe schreibt nach Pfadwechsel zurück

Behoben: Eine FFmpeg-Pfadänderung cancelt die aktive Probe. Jede Probe besitzt und disposed ihre CTS; nur die aktuell registrierte Ausführung darf Probe-State und CTS leeren.

### M-22 — RESOLVED: Verspätete Videoszenen überschreiben neue Clip-Auswahl

Behoben: Szenenloads sind über monotone Sequenz und aktuelle Clip-ID an die Auswahl gebunden. Vor und innerhalb des Dispatcher-Updates wird erneut geprüft; nur die aktuelle Sequenz darf den Loading-State beenden.

### M-23 — RESOLVED: Timeline-Async-Daten kehren nach Projekt-Reset zurück

Behoben: Reset/Dispose invalidieren Timeline-, Waveform- und Motion-Generationen. Dispatcher-Callbacks prüfen die Generation erneut; Waveform-Loading gehört nur dem aktuellen Load, und der Load-Semaphore bleibt bis zum natürlichen Ende laufender Tasks gültig.

### M-24 — RESOLVED: View-Dispose zerstört Load-Gates laufender Tasks

Behoben: Anchor-, VideoLibrary- und Director-ViewModels disposen ihre Load-Semaphore nicht mehr, solange In-flight-Tasks sie noch im `finally` freigeben können. Anchor und Director invalidieren laufende Generationen und sperren Folge-Reloads nach Shutdown.

### M-25 — RESOLVED: OnExit-Timeout zerstört Bridge-Gate vor Task-Ende

Behoben: `PythonBridgeService.Dispose()` sperrt weitere Starts, lässt den Lifecycle-Gate aber für laufende `StartAsync`-/`StopAsync`-Finalizer gültig. Der gebundene OnExit-Timeout kann damit keinen späteren `Release()`-Crash mehr erzeugen.

### M-26 — RESOLVED: Alte SSE-Listener übernehmen Token neuer Startgeneration

Behoben: Jede `StartListening()`-Generation erzeugt eine lokale CTS, deren Token direkt von allen drei Listener-Tasks erfasst wird. Schnelles Stop/Start kann alte Listener nicht mehr an den neuen Token binden; Starts nach Dispose sind gesperrt.

### M-27 — RESOLVED: Parallele SSE-Listener schreiben ungeschützt ins Dictionary

Behoben: Reconnect-Throttle-Lookup und -Update auf `_lastReconnectLogUtc` laufen atomar unter `_stateLock`. Logausgabe bleibt außerhalb des Locks.

### M-28 — RESOLVED: Einzelner SSE-Ausfall trennt globalen Backend-Status

Behoben: Verbundene Stream-Arten werden pro Listener-Generation aggregiert. Ein Fehler oder EOF entfernt nur den betroffenen Stream; `IsConnected=false` und Backend-Unreachable werden erst ohne verbleibende Verbindung publiziert. Alte Generationen können neuen Status nicht verändern.

### M-29 — RESOLVED: ProjectOverview verwirft Refresh während laufendem Load

Behoben: Dashboard-Refreshes besitzen eine monotone Generation und einen atomaren Single-Owner. Überlappende Signale werden coalesced und anschließend nachgeholt; alte Projektantworten werden vor jeder Veröffentlichung verworfen. Dispose invalidiert offene Loads.

### M-30 — RESOLVED: Brain-UI-Late-Writes nach Projektwechsel/Dispose

Behoben: Brain-Stats und Learning Session besitzen getrennte Daten-Generationen sowie eine gemeinsame Loading-Generation. Projekt-Close, neuere Loads und Dispose invalidieren alte Antworten; nur der aktuelle Load darf Collections und Spinnerzustand veröffentlichen.

## NIEDRIG / DEAD / DUPLICATE

1. `src/pb_studio/pacing/export_handler.py:21-251` ist komplett unimportiert und dupliziert Timeline-/FFmpeg-/EDL-Export.
2. **RESOLVED:** `canvas_path` ist im aktiven Backend-/OpenAPI-/WPF-Vertrag verdrahtet; zentrale ID-Normalisierung verhindert `clip_clip_*`.
3. **PARTIAL:** Die unreferenzierten, nicht exportierten Modell-Shortcuts in `ai/video_specialist.py` und `video/moondream.py:analyze_image` sind entfernt. Offen bleiben die vollständig unreferenzierten Dateien `services/embedding_service.py`, `core/recovery_handler.py` und `utils/logging_setup.py`; ihre Löschung benötigt Freigabe.
4. **RESOLVED:** Gemeinsamer `ai/config_loader.py` erhält ConfigManager-first und Direktdatei-Fallback; beide privaten Symbole und der Ollama-Kompatibilitätsshim zeigen auf denselben Helper.
5. **PARTIAL:** `SaveProjectCommand`/`CloseProjectCommand` sind in der Projektübersicht erreichbar; tote MainViewModel-Duplikate sind entfernt. `LoadAudioSourcesAsync` bleibt als interner Reload-Worker ohne generiertes Command. Offen bleibt nur die Löschung der vollständig auskommentierten Datei `Models/RenderConfig.cs`.
6. `_to_delete_workers_backup_20260725_034933/` ist untracked vollständige Kopie des gelöschten Worker-Legacycodes und verunreinigt Suche/Audit.
7. **RESOLVED:** Abgeleiteter ViewModel-Status zeigt „Kein Projekt geöffnet“, „Noch keine Video-Timeline“ oder „Video Timeline generiert“; Generierungsaktion ist ohne Projekt verborgen.
8. **RESOLVED:** `TerminalLogBuffer` puffert WPF- und Backend-SSE-Logs thread-sicher bis 100.000 Zeichen; TerminalViewModel abonniert mit History-Replay und Clear leert auch den gemeinsamen Puffer.
9. **RESOLVED:** `ProjectOverviewViewModel` injiziert und speichert keinen ungenutzten `VideoLibraryStateService` mehr.

## Datenbank-Befund

Physische Integrität ist gut:

- `data/pb_studio.db`
- 3 globale Brain-DBs
- 19 Projekt-`state.db`-Dateien

Alle: `integrity_check=ok`, keine FK-Verletzungen, WAL aktiv.

Logische Drift:

- 0 aktive bekannte FAISS-Orphans; ID 897 ist tombstoniert.
- 6 Projektzeilen zeigen auf fehlende Verzeichnisse.
- Projektzeile 2 enthält `json_data.db_project_id=130`, SQL-ID ist 2.
- 13 Gruppen gleicher Content-Hashes innerhalb desselben Projekts; meist bewusst duplizierte Dateien unter verschiedenen Pfaden, daher nicht als Fehler gewertet.

## Bestätigte Verbesserungen gegenüber Berichten vom 10./24. Juli

- LHM-Zugriff liegt jetzt vollständig unter `_lhm_lock`.
- FFmpeg-Segment-Returncode und Ausgabedatei werden geprüft.
- BrainViewModel-Collection-Cross-Thread-Finding C#-1 behoben.
- FileLoggerProvider-Startup-Crash C#-2 behoben.
- Alter VectorStore-„ein Thread pro Embedding“-Fehler durch Coalescing-Writer ersetzt.
- Toter `core.session_manager`-Import entfernt; neue Cache-Implementierung enthält jedoch C-01 und H-06.

## Nicht vollständig verifiziert

- Kein echter langer DJ-Mix: H-06 ist Codepfad-belegt, nicht mit 60–120 Minuten Realdatei gemessen.
- Kein vollständiger RAFT-/SigLIP-/Moondream-Happy-Path mit realen Modellen; Smoke stoppte vorher bei C-01.
- Keine absichtliche DB-Korruption, kein Crash mitten im FAISS-Commit, kein Stromausfall-Szenario.
- Kein LM-Studio Happy-Path.
- Audit bewertet aktuellen Dirty Tree; weitere parallele lokale Änderungen können Ergebnisse verschieben.

## Erzeugte Testartefakte

- Projekt: `C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260726_182726`
- Screenshots: `gui_screenshots/tab_*.png`
- Keine Testartefakte gelöscht, da Löschen explizite Freigabe erfordert.

## Selbstprüfung

- Statische Analyse, reale Tests, DB-Integrität, API-Live-Start, Release-Build und GUI-Automation ausgeführt.
- Alte Findings dedupliziert und nur übernommen, wenn im aktuellen Tree noch belegbar.
- Ruff-Funde nicht pauschal als Produktbugs gewertet.
- Keine Produktcode-Fixes durchgeführt.
