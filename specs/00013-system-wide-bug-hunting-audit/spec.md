# Spezifikation: System-wide Bug Hunting & Codebase Audit (Epic 00013)

## Amendment 2026-07-28: Release-Readiness-Finding-Matrix

* **OBJ-69:** Alle 60 Findings des eingefrorenen Berichts `FULLSTACK_STATUS_AUDIT_PB_STUDIO_2026-07-28.md` müssen ohne CPU-/Software-Fallbacks, Datenverlust oder falsche Erfolgszustände geschlossen werden.
* **FR-251 [C-01]:** Semantic Pacing darf ausschließlich ein registriertes CLAP-ONNX-Modell über `DmlExecutionProvider` verwenden; fehlt es, ist Semantic Audio explizit deaktiviert.
* **FR-252 [C-02]:** Jedes mutierende Chat-Tool benötigt eine serverseitig erzwungene, einmalige Benutzerbestätigung mit kanonischen Argumenten, Ablaufzeit und Replay-Schutz.
* **FR-253 [H-01]:** Long-Mix-Subtrack-Erkennung muss Speicher und quadratische SSM-Arbeit begrenzen.
* **FR-254 [H-02]:** Fehler der Streaming-Weiche dürfen nicht auf unbeschränktes Full-Load zurückfallen.
* **FR-255 [H-03]:** Struktur, Key und Spektral müssen die volle Long-Mix-Laufzeit repräsentieren.
* **FR-256 [H-04]:** Teilfehler der Audioanalyse müssen als `partial` oder `failed` erscheinen und dürfen keinen falschen Completed-Status erzeugen.
* **FR-257 [H-05]:** Zusammengesetzte Stem-Separation besitzt genau einen VRAM-Budget-Owner; CPU-Demucs reserviert kein GPU-Budget.
* **FR-258 [H-06]:** Ein fehlgeschlagenes Separator-Budget beendet den Pfad vor Modell- oder Inferenzarbeit.
* **FR-259 [H-07]:** GPU-Deadlines antworten pünktlich, verwerfen Late Results und halten den Lock bis zum echten Worker-Ende.
* **FR-260 [H-08]:** Eviction wird erst nach erfolgreichem Unload-Callback als freigegeben verbucht.
* **FR-261 [H-09]:** VRAM-Allokationen verwenden frische Sensorwerte.
* **FR-262 [H-10]:** RAFT-/SigLIP-Ausfälle werden als Stage-Fehler statt synthetische Nullwerte gemeldet.
* **FR-263 [H-11]:** Die Videoanalyse besitzt ein Registry-bestätigtes, nutzbares Vision-Modell oder meldet den fehlenden Dienst explizit.
* **FR-264 [H-12]:** `use_brain` aktiviert Advanced Pacing und ClipSelector statt Round-Robin.
* **FR-265 [H-13]:** Reale Audio-/Videofeatures und der konfigurierte Threshold erreichen den Brain-Reranker.
* **FR-266 [H-14]:** `use_brain` lädt Videoanalyse unabhängig vom Motion-Matching.
* **FR-267 [H-15]:** Cross-DB-Lernupdates verwenden eine durable, idempotente Outbox.
* **FR-268 [H-16]:** Projektormodell und Dimension müssen exakt passen; Kürzen, Padding und beliebiger Fallback sind unzulässig.
* **FR-269 [H-17]:** `pacing.generate` läuft als korrekt überwachtes Long-Running-Chat-Tool.
* **FR-270 [H-18]:** WPF setzt Runtime-Umgebung vor dem Backendstart.
* **FR-271 [H-19]:** Audioanalyse, Stems und Pacing sind per Projektgeneration und CTS gegen Projektwechsel geschützt.
* **FR-272 [H-20]:** `POST /project/create` lehnt bestehende Projektordner mit HTTP 409 ab und überschreibt nichts.
* **FR-273 [H-21]:** Medienlöschung und Dedupe werden als idempotente Pending-Operationen über SQLite und FAISS konsistent abgeschlossen.
* **FR-274 [H-22]:** `include_audio` und `quality` beeinflussen nachweisbar die Renderargumente und das Ergebnis.
* **FR-275 [H-23]:** Render schreibt in eine temporäre Zieldatei und ersetzt ein vorhandenes Ziel erst nach vollständigem Erfolg.
* **FR-276 [H-24]:** Queue-Dedupe plant bei vorhandener Task-ID keinen zweiten Runtime-Task.
* **FR-277 [H-25]:** Fehlende Timeline-Clips brechen den Render-Preflight ab.
* **FR-278 [H-26]:** Modellprovider werden parallel mit harten Deadlines geprüft; Offline-Ollama blockiert den Models-Tab nicht.
* **FR-279 [M-01]:** Spektralanalyse verwendet einen 44,1-kHz-Pfad für Bänder bis 20 kHz.
* **FR-280 [M-02]:** `/onsets` liefert persistierte `onset_times`.
* **FR-281 [M-03]:** Streaming-Tempdateien werden in allen Erfolgs- und Fehlerpfaden garantiert bereinigt.
* **FR-282 [M-04]:** ModelLoader prüft Commit-/Unload-Erfolg und gibt Budget erst nach physischer Freigabe zurück.
* **FR-283 [M-05]:** Multi-GPU-Sensorwerte bleiben an denselben Adapter gebunden.
* **FR-284 [M-06]:** Farbanalyse ist unabhängig von Captioning aktivierbar.
* **FR-285 [M-07]:** Persistierte Video-Hashes ermöglichen sichere Embedding-Wiederverwendung.
* **FR-286 [M-08]:** Langvideo-RAFT- und SigLIP-Sampling ist begrenzt und repräsentativ.
* **FR-287 [M-09]:** `peak_frames` enthält echte Motion-Peaks.
* **FR-288 [M-10]:** `beat_trigger_mode` steuert aktiv die Triggerauswahl.
* **FR-289 [M-11]:** Synchrone Brain-Reads verlassen den Async-Eventloop.
* **FR-290 [M-12]:** Eine leere `video_clip_ids`-Liste wird abgelehnt und nie als „alle“ beschrieben.
* **FR-291 [M-13]:** Providerwahl prüft die für den Task benötigte Chat-/Vision-Capability.
* **FR-292 [M-14]:** WPF zeigt den echten Embedding-Status aus dem API-DTO.
* **FR-293 [M-15]:** Timeline lädt Assets einmal, projektgebunden und cancellable.
* **FR-294 [M-16]:** Die Brain-Lernliste bindet `SelectedItem` an die bewertete Cut-ID.
* **FR-295 [M-17]:** Projektspeichern propagiert SQLite-Sync-Fehler.
* **FR-296 [M-18]:** Vector-Dedupe entfernt Mapping und Vektor crash-konsistent.
* **FR-297 [M-19]:** Der VectorStore-Writer bleibt bis zu einem erfolgreichen Snapshot dirty.
* **FR-298 [M-20]:** Vector-Suche überholt Tombstones adaptiv, bis `k` gültige Treffer oder der Bestand erschöpft ist.
* **FR-299 [M-21]:** Brain-Backups werden temp+replace geschrieben; Recovery lädt das letzte valide Backup.
* **FR-300 [M-22]:** Embedding-Cache schreibt `.npy` atomar und serialisiert Datei- und SQLite-Index-Update.
* **FR-301 [M-23]:** Preview-Vertrag und tatsächliche Ausgabeauflösung stimmen überein.
* **FR-302 [M-24]:** Render-Cancel wird vor und während der GPU-Lock-Wartezeit geprüft.
* **FR-303 [M-25]:** Encoder-Overrides werden funktional vorgeprüft; nicht verfügbares AV1 scheitert vor Jobstart.
* **FR-304 [L-01]:** Waveform liefert stabil höchstens die angeforderte Punktzahl ohne High-Band-Abschneidung.
* **FR-305 [L-02]:** Waveform-Cache nutzt einen kollisionssicheren Inhaltsfingerprint und gesperrte Statistikzugriffe.
* **FR-306 [L-03]:** Szenen-Confidence ist fachlich ermittelt oder explizit nullable.
* **FR-307 [L-04]:** Importfortschritt basiert auf der Eingabeposition.
* **FR-308 [L-05]:** MediaIngest, Anchor und Timeline-Vor/Zurück-Navigation sind in der aktiven UI erreichbar.
* **FR-309 [L-06]:** Terminalausgaben redigieren Secrets und sensible absolute Pfade.
* **FR-310 [L-07]:** Migrationen lehnen Versionslücken ab.
* **SC-068 [OBJ-69]:** Die Finding-Matrix weist für C-01–C-02, H-01–H-26, M-01–M-25 und L-01–L-07 genau 60/60 PASS mit reproduzierbarem Testbeleg aus.
* **SC-069 [OBJ-69]:** `.completed` entsteht erst nach allen Fix- und Cluster-Tasks; `.qc-passed` erst nach bestandenem gebündeltem End-QC und leerem Arbeitsbaum.

## Amendment 2026-07-28: Vollständige aktive API-DTOs

* **OBJ-32:** Die vom handgeschriebenen `ApiClient` tatsächlich deserialisierten Analyse-DTOs müssen alle aktuell produzierten Audio-Trigger/Subtrack- und Video-Mood/Farb-Felder erhalten.
* **SC-031 [OBJ-32]:** Audio- und Videoanalyse-Records enthalten die Felder des aktuellen OpenAPI-Schemas; WPF Release kompiliert ohne Warnungen oder Fehler.

## Amendment 2026-07-28: Korrelierte SSE-Progress-Events

* **OBJ-31:** Videoanalyse, Videoimport und Pacing dürfen nur Progress-Events des aktuell gestarteten Jobs in ihre ViewModels übernehmen.
* **SC-030 [OBJ-31]:** Backend-Events tragen Domain-/Clip-Korrelation; VideoLibrary filtert nach aktivem Clip bzw. `video_import`, Director ausschließlich nach `pacing_progress` und aktiver Audio-Clip-ID.

## Amendment 2026-07-28: Lernsession Play/Pause-Toggle

* **OBJ-30:** Der sichtbare Play/Pause-Button der Brain-Lernsession muss zwischen Play- und Pause-Ereignis umschalten und seinen Zustand anzeigen.
* **SC-029 [OBJ-30]:** Aufeinanderfolgende `PlayPauseCommand`-Aufrufe lösen Play, Pause, Play aus; Navigation setzt den Zustand zurück und der Buttontext folgt `IsPlaying`.

## Amendment 2026-07-28: Ein RAFT-Flow pro Frame-Paar

* **OBJ-29:** Motion-Magnitude und Scene-Change eines Frame-Paars müssen aus derselben DirectML-RAFT-Inferenz abgeleitet werden.
* **SC-028 [OBJ-29]:** `analyze_video_segment` ruft `calculate_flow` exakt einmal pro verarbeitetem Frame-Paar auf und behält Motion-/Scene-Change-Ergebnisstruktur sowie Progress-Vertrag bei.

## Amendment 2026-07-28: Zeitstabile Streaming-Energy

* **OBJ-28:** Fehlgeschlagene Audio-Chunks dürfen die Zeitachse der aggregierten Energy-Kurve nicht verkürzen oder nachfolgende Peaks vorziehen.
* **SC-027 [OBJ-28]:** Load- und RMS-Fehler erzeugen eine zeitlich gleich lange Null-Lücke; ein Peak nach einem fehlerhaften mittleren Chunk bleibt im letzten Drittel der Kurve.

## Amendment 2026-07-27: Persistente Medien-JSON-Versionen

* **OBJ-27:** Neue und regulär aktualisierte Medien-JSON-Blobs müssen die aktuelle Schema-Version dauerhaft speichern und alle unterstützten Videoendungen korrekt klassifizieren.
* **SC-026 [OBJ-27]:** `.wmv`/`.flv` verwenden Video-Migrationen; `add_media`, `update_metadata` und `update_status(ai_data=...)` schreiben `__schema_version`. Bestehende Live-Blobs werden ohne Freigabe nicht massenweise verändert.

## Amendment 2026-07-27: Brain-Stats Connection-Lock

* **OBJ-26:** Der Brain-Stats-Endpunkt muss alle direkten Reads der geteilten `weights_conn` gegen Feedback, Reset, Rebind und Close serialisieren.
* **SC-025 [OBJ-26]:** Sämtliche `axis_weights`-Queries in `/brain/stats` laufen innerhalb von `BrainStore._weights_lock`; bestehende Brain-API-Tests bleiben grün.

## Amendment 2026-07-27: Atomarer FAISS-Medienlink

* **OBJ-25:** Ein neues FAISS-Embedding darf nicht als aktiver Suchtreffer verbleiben, wenn sein relationaler `vector_map`-Link fehlt oder fehlschlägt.
* **SC-024 [OBJ-25]:** `media_id=None` wird vor dem Index-Write abgelehnt; bei Linkfehler wird der gerade angelegte letzte Vektor zurückgerollt oder bei Konkurrenz sicher tombstoniert und der Fehler erneut ausgelöst.

## Amendment 2026-07-27: Projektgebundener Medienimport

* **OBJ-24:** Audio- und Videoimporte dürfen ohne aktives Projekt weder In-Memory-Clips erzeugen noch über den Legacy-Fallback in DB-Projekt 1 schreiben.
* **SC-023 [OBJ-24]:** Beide Import-Endpunkte antworten ohne Projekt mit HTTP 409; Registrierungs- und Persistenzpfade verlangen eine explizite aktive DB-Projekt-ID.

## Amendment 2026-07-27: Wahrheitsgemäße Medien-Löschung

* **OBJ-23:** Audio- und Video-Löschungen dürfen den In-Memory-Katalog erst nach erfolgreicher SQLite-/FAISS-Verarbeitung verändern und Persistenzfehler nicht als Erfolg melden.
* **SC-022 [OBJ-23]:** Bei DB- oder Tombstone-Fehler bleiben Clip und Analyse-Cache erhalten, die Exception erreicht den API-Fehlerpfad, und `deleted_count=1` wird ausschließlich nach erfolgreicher Löschung geliefert.

## Amendment 2026-07-27: Live-Pacing Cache-Vertrag

* **OBJ-8:** Wiederherstellung des atomaren Audio-Cache-Vertrags im Live-Pacing-Pfad, sodass injizierte Analysemetadaten und lazy geladene Waveform-Daten nicht als derselbe Cache-Zustand behandelt werden.
* **SC-007 [OBJ-8]:** Der reale Ablauf Audio-Analyse → Cache-Injektion → `/pacing/generate` erzeugt eine Cut-Liste ohne fehlendes `_cached_y`-Attribut; ein Regressionstest deckt den unvollständigen Trigger-Cache ab.

## Amendment 2026-07-27: AMF-only Render-Vertrag

* **OBJ-9:** Software-Encoder und nicht-AMF Hardware-Encoder vollständig aus Live-API, WPF-Auswahl, Render-Service, Video-Engine und Chat-Tool-Schema entfernen.
* **SC-008 [OBJ-9]:** Alle Live-Renderpfade nutzen ausschließlich `h264_amf`, `hevc_amf` oder `av1_amf`; bei fehlendem/funktionsunfähigem AMF bricht der Vorgang mit explizitem Fehler ab.

## Amendment 2026-07-27: DirectML-only ONNX- und Motion-Vertrag

* **OBJ-10:** Implizite CPU-ExecutionProvider und den Farneback-CPU-Motion-Pfad aus `ModelLoader`, RAFT-Factory und `SmartDirector` entfernen; der gesperrte Audio-Separator wird erst nach expliziter Freigabe geändert.
* **SC-009 [OBJ-10]:** Live-ONNX- und Motion-Pfade verwenden ausschließlich `DmlExecutionProvider`; fehlt DirectML, wird explizit abgebrochen oder ein neutraler Analysewert geliefert, ohne CPU-Inferenz.

## Amendment 2026-07-27: Wahrheitsgemäße SDD/QC-Gates

* **OBJ-11:** Audit-Tasks, QC-Bericht und Statusmarker müssen den aktuell nachgewiesenen Zustand widerspruchsfrei abbilden.
* **SC-010 [OBJ-11]:** Erledigte Tasks verwenden ausschließlich `[X]`; historische Pass-Berichte sind ausdrücklich invalidiert; `.completed` und `.qc-passed` fehlen, solange Tasks, Findings oder Pflicht-QC offen sind.

## Amendment 2026-07-27: Nicht-destruktiver Restore fehlender Medien

* **OBJ-12:** Temporär nicht erreichbare Medien beim Projekt-Open überspringen, ohne SQLite-, Analyse- oder Vector-Mapping-Daten zu löschen.
* **SC-011 [OBJ-12]:** `AppState.load_from_db()` ruft für fehlende Dateien kein `delete_media()` auf und reserviert deren persistierte Clip-ID weiterhin, damit spätere Imports keine ID-Kollision erzeugen.

## Amendment 2026-07-27: Atomarer Projekt↔Brain-Rebind

* **OBJ-13:** Ein Projektwechsel darf nur erfolgreich sein, wenn die neue Brain-`state.db` geöffnet und initialisiert wurde; ein Bind-Fehler darf weder den alten Brain-Zustand noch den alten Runtime-Projektzustand zerstören.
* **SC-012 [OBJ-13]:** Neue Brain-Verbindung wird vor dem Swap vollständig vorbereitet; Pfad und Connection wechseln atomar; `/project/open` liefert bei Bind-Fehler HTTP 500 und lässt den bisherigen `AppState` unverändert.

## Amendment 2026-07-27: FAISS/SQLite-Kompaktierungs-Gate

* **OBJ-14:** Eine Tombstone-Kompaktierung darf neue FAISS-IDs nur veröffentlichen, wenn das zugehörige SQLite-`vector_map`-Remapping vollständig committed wurde.
* **SC-013 [OBJ-14]:** Schlägt die Remap-Transaktion fehl, bleiben aktiver FAISS-Index, Metadaten und Tombstones unverändert; eine spätere Bereinigung kann sicher erneut versuchen.

## Amendment 2026-07-27: Valider VectorStore-Testaufbau

* **OBJ-15:** Der isolierte `add_embedding()`-Unit-Test muss die bewusst übersprungene Writer-Infrastruktur explizit mocken, statt an einem unvollständig konstruierten Objekt zu scheitern.
* **SC-014 [OBJ-15]:** Der vollständige VectorStore-Cluster läuft ohne `_save_cv`-Fixturefehler und prüft weiterhin ID, Metadaten und Save-Anforderung.

## Amendment 2026-07-27: Verlustfreier Generation-Cancel

* **OBJ-16:** Ein Cancel-Signal, das nach Jobannahme während Audio-/Videoanalyse gesetzt wird, muss bis zum Timeline-Render erhalten bleiben; ein neuer Job darf keinen Cancel-Zustand des vorherigen Jobs erben.
* **SC-015 [OBJ-16]:** `GenerationService.start_generation()` setzt den Zustand synchron bei Jobannahme zurück; `VideoGenerator.generate()` und `generate_from_timeline()` löschen danach kein Cancel-Signal mehr und liefern bei vorliegendem Signal `cancelled=True`.

## Amendment 2026-07-27: Crash-konsistenter FAISS-Dreifach-Snapshot

* **OBJ-17:** `.faiss`, Metadata-JSON und Tombstone-JSON müssen als eine logische Generation veröffentlicht werden, ohne das bestehende Dateiformat zu migrieren.
* **SC-016 [OBJ-17]:** Vor dem ersten Live-Replace existieren Backups und ein persistiertes Journal; Fehler oder Neustart mit Journal stellen die vollständige vorige Dreiergeneration wieder her, bevor der Index geladen wird.

## Amendment 2026-07-27: Eindeutige VRAM-Budget-Verantwortung

* **OBJ-18:** Zusammengesetzte GPU-Tasks müssen global serialisiert und telemetriert werden können, ohne zusätzlich zu ihren intern verwalteten Modell-Sessions ein zweites VRAM-Budget zu reservieren.
* **SC-017 [OBJ-18]:** Die Videoanalyse hält weiter den globalen GPU-Lock und schreibt Telemetrie unter `video_analysis_full`; committed VRAM enthält dabei ausschließlich die RAFT- und SigLIP-Budgets.

## Amendment 2026-07-27: Vollständige Trigger-Coverage langer Mixe

* **OBJ-19:** Onset-, Kick-, Snare- und HiHat-Kandidaten langer Audiodateien müssen über dieselben Streaming-Chunks wie Beats und Energy ermittelt werden, ohne einen vollständigen Mix in den RAM zu laden.
* **SC-018 [OBJ-19]:** Bei Dateien über 600 Sekunden enthalten persistierte Triggerlisten Kandidaten nach Minute 10; Overlap-Duplikate werden dedupliziert und `energy_only` erzeugt keine Trigger.

## Amendment 2026-07-27: Ausführbarer Render-Restart

* **OBJ-20:** Persistierte Render-Jobs müssen nach einem Backend-Abbruch aus einem vollständigen, validierbaren Request- und Timeline-Snapshot automatisch rekonstruierbar sein.
* **SC-019 [OBJ-20]:** Startup überführt `running` nach `interrupted`, plant `queued` und `interrupted` erneut ein und markiert historische Jobs ohne Resume-Payload explizit als fehlgeschlagen statt sie dauerhaft warten zu lassen.

## Amendment 2026-07-27: Projektgebundene WPF-Caches

* **OBJ-21:** Ein direkter Projektwechsel muss denselben Closing/Closed/Open-Lifecycle wie ein explizites Schließen auslösen und alle projektgebundenen Audio-, Video- und Thumbnail-Caches invalidieren.
* **SC-020 [OBJ-21]:** Alte Warm-Cache-Daten und noch laufende Refresh-Tasks können nach dem Switch weder Collections noch State-Services des neuen Projekts überschreiben; numerisch gleiche Clip-IDs verwenden keine alten Thumbnails.

## Amendment 2026-07-27: UI-Thread-sichere Projektmeldungen

* **OBJ-22:** Alle ProjectClosing-/ProjectClosed-/ProjectOpened-Meldungen des `ProjectService` müssen in definierter Reihenfolge auf dem WPF-Dispatcher zugestellt werden.
* **SC-021 [OBJ-22]:** Direkte Collection-Resets in Timeline/Video laufen nicht mehr auf einer Threadpool-Continuation nach `ConfigureAwait(false)`; WPF Release baut ohne Fehler.

## Amendment 2026-07-28: Nicht-blockierendes WPF-Dateilogging

* **OBJ-33:** Produktionslogging darf weder allgemeine Benutzer-Klicks erfassen noch Dateizugriffe auf dem WPF-UI-Thread ausführen.
* **SC-032 [OBJ-33]:** `MainWindow` besitzt keinen globalen Klick-Audit-Hook; `FileLoggerProvider` übernimmt Logzeilen über eine begrenzte Queue und schreibt sie auf einem einzelnen Hintergrund-Writer, der beim Dispose ausstehende Zeilen geordnet leert.

## Amendment 2026-07-28: Vollständiger VectorStore-Writer-Lifecycle

* **OBJ-34:** Ein Wechsel des FAISS-Indexnamens darf weder einen alten Writer-Thread noch ungespeicherten Zustand zurücklassen.
* **SC-033 [OBJ-34]:** Vor Veröffentlichung einer neuen Singleton-Instanz wird die alte Instanz geschlossen, ihr Writer beendet und ihr letzter Zustand gespeichert; ein späterer Zugriff auf denselben Namen erzeugt nach Close eine frische Instanz.

## Amendment 2026-07-28: Erreichbarer Canvas-Pacing-Pfad

* **OBJ-35:** Der intern implementierte Obsidian-Canvas-Pfad muss vom WPF-Request bis zur aktiven Pacing-Engine transportiert werden und gültige Timeline-Clip-IDs erzeugen.
* **SC-034 [OBJ-35]:** `canvas_path` ist in Backend-, OpenAPI- und aktivem C#-Requestvertrag enthalten; Director reicht den Wert weiter; rohe und bereits präfixierte IDs werden genau einmal zu `clip_<id>` normalisiert.

## Amendment 2026-07-28: Wahrheitsgemäßer Projekt-Timeline-Status

* **OBJ-36:** Die Projektübersicht darf weder eine generierte Timeline noch eine ausführbare Generierungsaktion anzeigen, wenn kein Projekt geöffnet ist.
* **SC-035 [OBJ-36]:** Timeline-Statustext unterscheidet kein Projekt, offene Timeline und fehlende Timeline; der Director-Button ist nur bei offenem Projekt ohne Timeline sichtbar.

## Amendment 2026-07-28: Terminal-History vor View-Erzeugung

* **OBJ-37:** WPF- und Backend-SSE-Logs dürfen nicht verloren gehen, bevor das Terminal-ViewModel registriert oder nach einem View-Lifecycle neu erzeugt wird.
* **SC-036 [OBJ-37]:** Beide Quellen schreiben in einen thread-sicheren, auf 100.000 Zeichen begrenzten Singleton-Puffer; TerminalViewModel abonniert atomar mit Snapshot-Replay und Clear leert auch die zentrale History.

## Amendment 2026-07-28: Gemeinsamer AI-Config-Fallback

* **OBJ-38:** Brain-Narrator und LM-Studio-Vision dürfen keinen duplizierten ConfigManager-/Direktdatei-Reader besitzen, der zwischen den Modellpfaden auseinanderdriften kann.
* **SC-037 [OBJ-38]:** Ein gemeinsamer Helper bewahrt ConfigManager-first und Disk-only-as-fallback; lokale `_load_ai_config`-Aliase sowie der deprecated Ollama-Re-Export bleiben identisch kompatibel.

## Amendment 2026-07-28: Erreichbare Projekt-Lifecycle-Aktionen

* **OBJ-39:** Projekt speichern und schließen müssen in der Projektübersicht erreichbar sein; intern aufgerufene Reload-Worker dürfen keine ungebundenen WPF-Commands erzeugen.
* **SC-038 [OBJ-39]:** Die Projektübersicht bindet Save/Close an ihr eigenes ViewModel und deaktiviert beide Aktionen ohne offenes Projekt; `AnchorViewModel` behält den internen Audio-Reload ohne generiertes `LoadAudioSourcesCommand`.

## Amendment 2026-07-28: Keine unverwalteten Modell-Shortcuts

* **OBJ-40:** Nicht exportierte, unreferenzierte Convenience-Helper dürfen keine neuen SigLIP- oder Moondream-Instanzen außerhalb der aktiven Modell-Lifecycles erzeugen.
* **SC-039 [OBJ-40]:** `video_specialist.py` enthält nur die aktive Klassen-API; `moondream.py` exportiert ausschließlich den verwendeten Analyzer und keinen unreferenzierten `analyze_image`-Shortcut.

## Amendment 2026-07-28: Geordneter Lifespan-Task-Shutdown

* **OBJ-41:** Der Zombie-Wächter darf während der nachfolgenden Backend-Ressourcenbereinigung nicht weiterlaufen oder als ausstehender Task zerstört werden.
* **SC-040 [OBJ-41]:** Der Lifespan cancelt und awaited den Wächter vor Publisher-, Modell- und Datenbank-Cleanup; ausschließlich die erwartete `asyncio.CancelledError` wird abgefangen.

## Amendment 2026-07-28: Atomarer WPF-Projekt-Close

* **OBJ-42:** Ein fehlgeschlagener Backend-Close darf weder lokale Projektzustände noch projektgebundene UI-Caches leeren.
* **SC-041 [OBJ-42]:** `ProjectService.CloseProjectAsync()` liefert `false`, wenn die API keine erfolgreiche `StatusResponse` liefert; Closing/Closed/ProjectChanged werden ausschließlich nach bestätigtem Erfolg publiziert und die Projektübersicht zeigt den Fehler.

## Amendment 2026-07-28: Einfacher UI-Thread-Projekt-Refresh

* **OBJ-43:** Ein Backend-Reconnect darf `ProjectChanged`/`ProjectOpenedMessage` weder außerhalb des WPF-Dispatchers noch doppelt publizieren.
* **SC-042 [OBJ-43]:** `RefreshProjectInfoAsync()` verwendet den zentralen `SwitchToProject()`-Lifecycle und `MainViewModel` sendet keine zusätzliche Open-Meldung; ein fehlgeschlagener Info-Abruf überschreibt den lokalen Zustand nicht.

## Amendment 2026-07-28: UI-Thread-sicherer Projekt-Save

* **OBJ-44:** Ein erfolgreicher Projekt-Save darf `CurrentProject` und `ProjectChanged` nach `ConfigureAwait(false)` nicht auf einem Threadpool-Thread aktualisieren.
* **SC-043 [OBJ-44]:** Der Save-Pfad holt die aktualisierte Projektinfo asynchron und veröffentlicht Zustandsupdate und Event anschließend gemeinsam über `RunOnUiThread()`.

## Amendment 2026-07-28: UI-Thread-sicheres VRAM-Debounce

* **OBJ-45:** Der Settings-VRAM-Slider darf ObservableProperties nicht aus einem expliziten Threadpool-Task aktualisieren und darf ersetzte Debounce-Tokenquellen nicht ansammeln.
* **SC-044 [OBJ-45]:** Der Debounce startet als UI-kontextbewahrende Async-Methode ohne `Task.Run`; vorherige CTS werden gecancelt und disposed, und nach Dispose erfolgen keine Statusupdates.

## Amendment 2026-07-28: Eindeutiger VRAM-Telemetrie-Load-Lifecycle

* **OBJ-46:** Wiederholte Telemetrie-Refreshes dürfen weder CTS-Instanzen leaken noch den Loading-Zustand eines neueren Requests durch den `finally`-Block eines älteren Requests löschen.
* **SC-045 [OBJ-46]:** Jeder Load besitzt und disposed seine CTS; nur der aktuell registrierte Load darf `_loadCts` leeren und `IsLoading=false` publizieren.

## Amendment 2026-07-28: Scope-gebundener Chat-Stream

* **OBJ-47:** Ein Chat-Stream darf nach Unload/Scope-Dispose weder das alte ViewModel festhalten noch dessen Collections und Status weiter aktualisieren; Clear darf nicht durch einen verspäteten Stream-Finalizer überschrieben werden.
* **SC-046 [OBJ-47]:** `ChatViewModel` implementiert `IDisposable`, cancelt den aktiven Stream und verwendet eine Generation; nur die aktuelle, nicht-disposed Generation darf Events, Fehler und Finalstatus publizieren, und jede Send-Ausführung disposed ihre CTS.

## Amendment 2026-07-28: Eindeutiger Model-Manager-Load-Lifecycle

* **OBJ-48:** Überlappende Model-Manager-Loads dürfen weder CTS-Instanzen ansammeln noch den Loading-State eines neueren Modellabrufs durch einen älteren `finally`-Block löschen.
* **SC-047 [OBJ-48]:** Jede Load-Ausführung besitzt und disposed ihre CTS; nur der aktuell registrierte Load darf `_loadCts` leeren und `IsLoading=false` setzen.

## Amendment 2026-07-28: Pfadgebundener FFmpeg-Probe-Lifecycle

* **OBJ-49:** Eine laufende FFmpeg-Probe darf nach Pfadänderung weder eine Version des alten Pfads veröffentlichen noch Loading-State/CTS einer neueren Probe überschreiben.
* **SC-048 [OBJ-49]:** Pfadänderung cancelt die aktive Probe; jede Probe besitzt und disposed ihre CTS, und nur die aktuell registrierte Probe darf `_probeCts` leeren und `IsProbingFfmpeg=false` setzen.

## Amendment 2026-07-28: Selektionsgebundener Video-Szenenload

* **OBJ-50:** Ein verspäteter Szenenabruf für Clip A darf nach Auswahl von Clip B weder dessen Szenenliste noch dessen Loading-State überschreiben.
* **SC-049 [OBJ-50]:** Jeder Szenenload trägt eine monotone Sequenz und prüft vor sowie innerhalb des Dispatcher-Updates zusätzlich die aktuelle Clip-ID; nur die aktuelle Sequenz darf `IsLoadingScenes=false` setzen.

## Amendment 2026-07-28: Reset-sichere Timeline-Async-Pfade

* **OBJ-51:** Projekt-Close oder View-Dispose darf keine laufende Timeline-, Waveform- oder Motion-Ausführung alte Daten nach dem Reset veröffentlichen lassen oder durch Dispose des noch gehaltenen Load-Semaphors crashen.
* **SC-050 [OBJ-51]:** Reset/Dispose invalidieren Timeline-, Waveform- und Motion-Sequenzen; Dispatcher-Callbacks prüfen die Generation erneut, nur der aktuelle Waveform-Load beendet dessen Loading-State, und der Load-Gate bleibt bis zum natürlichen Task-Ende gültig.

## Amendment 2026-07-28: Scope-sichere WPF-Load-Gates

* **OBJ-52:** Das Schließen von Anchor-, VideoLibrary- oder Director-Scopes darf keinen noch gehaltenen Load-Semaphor disposen und keine bereits invalidierte Ladeausführung alte UI-Daten veröffentlichen lassen.
* **SC-051 [OBJ-52]:** Dispose cancelt oder invalidiert weitere Loads, sperrt Rekursionen nach Shutdown und lässt den jeweiligen Load-Gate bis zum natürlichen Ende aller laufenden Tasks gültig.

## Amendment 2026-07-28: Timeout-sicherer Backend-Bridge-Gate

* **OBJ-53:** Ein OnExit-Timeout mit anschließendem ServiceProvider-Dispose darf keinen noch von `StartAsync` oder `StopAsync` gehaltenen Bridge-Lifecycle-Gate zerstören.
* **SC-052 [OBJ-53]:** `PythonBridgeService.Dispose()` sperrt neue Starts, lässt den Lifecycle-Gate für laufende `finally`-Releases gültig und darf dadurch keinen Shutdown-Task mit `ObjectDisposedException` beenden.

## Amendment 2026-07-28: Generationsgebundene SSE-Listener-Token

* **OBJ-54:** Listener einer alten SSE-Startgeneration dürfen bei schnellem Stop/Start nicht versehentlich den Token der neuen Generation lesen und dadurch als doppelte Streams weiterlaufen.
* **SC-053 [OBJ-54]:** `StartListening()` bindet alle gestarteten Tasks an eine lokale CTS derselben Generation und startet nach Service-Dispose keine Listener mehr.

## Amendment 2026-07-28: Thread-sicheres SSE-Reconnect-Throttling

* **OBJ-55:** Parallele Progress-, Log- und GPU-Listener dürfen das gemeinsame Reconnect-Log-Throttling-Dictionary nicht ungeschützt lesen und beschreiben.
* **SC-054 [OBJ-55]:** Prüfung und Aktualisierung von `_lastReconnectLogUtc` erfolgen atomar unter `_stateLock`; Logging selbst bleibt außerhalb des Locks.

## Amendment 2026-07-28: Aggregierter SSE-Verbindungszustand

* **OBJ-56:** Der Ausfall oder EOF eines einzelnen SSE-Endpunkts darf die gesamte Backend-Verbindung nicht als getrennt oder unerreichbar melden, solange mindestens ein anderer Stream verbunden ist.
* **SC-055 [OBJ-56]:** SSE führt verbundene Stream-Arten pro Listener-Generation; alte Generationen dürfen neuen Zustand nicht verändern, `IsConnected` entspricht „mindestens ein Stream offen“, und Backend-Unreachable wird erst ohne verbundenen Stream nach dem Reconnect-Schwellwert publiziert.

## Amendment 2026-07-28: Verlustfreier ProjectOverview-Refresh

* **OBJ-57:** Ein Projekt-/Medien-Refresh während eines laufenden ProjectOverview-Loads darf nicht verworfen werden und ein alter Projektstand darf nach einem Wechsel keinen neueren Stand überschreiben.
* **SC-056 [OBJ-57]:** Jeder Refresh erhöht eine Generation; während eines aktiven Loads wird mindestens ein Folge-Refresh atomar vorgemerkt, alte Generationen publizieren keine Daten, und Dispose invalidiert sowie sperrt weitere Loads.

## Amendment 2026-07-28: Wahrheitsgetreue Dashboard-DI

* **OBJ-58:** `ProjectOverviewViewModel` darf keine ungenutzte Video-State-Abhängigkeit vortäuschen.
* **SC-057 [OBJ-58]:** Ungelesenes `_videoState`-Feld und dessen Konstruktorparameter sind entfernt; DI kann das ViewModel weiterhin erzeugen.

## Amendment 2026-07-28: Projektgebundene Brain-UI-Loads

* **OBJ-59:** Verspätete Brain-Stats- oder Learning-Session-Antworten dürfen nach Projekt-Close, Projektwechsel, neuerem Load oder View-Dispose keine alten Collections/Statuswerte veröffentlichen; ein älterer Finalizer darf den Loading-State eines neueren Loads nicht löschen.
* **SC-058 [OBJ-59]:** Stats und Learning Session besitzen eigene Generationen, teilen eine eindeutige Loading-Generation und prüfen vor Collection-Updates; Reset/Dispose invalidieren alle drei Generationen.

## Amendment 2026-07-28: Freigegebene Audit-Blocker schließen

* **OBJ-60:** Der aktive ONNX-Stem-Pfad darf weder einzelne Nodes noch die vollständige Inferenz still auf CPU ausführen; der absichtliche PyTorch-CPU-Pfad für Demucs bleibt unverändert.
* **OBJ-61:** Der aktive FAISS-Orphan 897 muss ohne spekulative Zuordnung zu einem von zwei gleichnamigen Medien logisch deaktiviert und atomar persistiert werden.
* **OBJ-62:** Alle gültigen Live-`metadata_json`-/`ai_data_json`-Dict-Blobs müssen nach geprüftem Backup mit dem zentralen Audio-/Video-Migrator auf Schema v1 persistiert werden.
* **OBJ-63:** Freigegebene, nachweislich unreferenzierte Dead-Dateien und der Worker-Backup-Baum müssen entfernt werden.
* **OBJ-64:** Falsche `.completed`-/`.qc-passed`-Marker müssen entfernt bleiben, bis vollständige QC wirklich bestanden ist.
* **OBJ-65:** Der globale ONNX-`SessionOptions`-Patch des Stem-Separators muss über mehrere Separator-Instanzen serialisiert und garantiert auf das echte Original zurückgesetzt werden.
* **OBJ-66:** `/project/open` darf das aktive Runtime-Projekt und die Brain-Bindung erst ersetzen, nachdem der neue SQLite-Medienkatalog vollständig und fehlerfrei in einen isolierten Kandidaten-State geladen wurde.
* **OBJ-67:** Der temporäre PyAudio-Kompatibilitätsstub für den BeatNet-Import darf `sys.modules` nach Erfolg oder Fehlschlag nicht dauerhaft kontaminieren.
* **OBJ-68:** Der WPF-Backend-Launcher darf ausschließlich einen real nachgewiesenen Python-3.11-Interpreter starten und keine Python-3.12-/unversionierten PATH-Fallbacks verwenden.
* **SC-059 [OBJ-60]:** ONNX-Modelle verwenden ausschließlich `DmlExecutionProvider`; ohne DML endet Separation vor Modell-/Inference-Ausführung mit explizitem Fehler, beide DirectML-Session-Flags bleiben gesetzt.
* **SC-060 [OBJ-61]:** FAISS-ID 897 steht in Tombstones, bleibt aus Suchtreffern ausgeschlossen und der dreiteilige Snapshot ist lesbar; kein erfundener `vector_map`-Link wird erzeugt.
* **SC-061 [OBJ-62]:** Backup ist lesbar und integer; Migration läuft in einer Transaktion, bewahrt JSON-Schlüssel, meldet ungültige/non-dict Blobs explizit und hinterlässt 0 gültige unversionierte Blobs.
* **SC-062 [OBJ-63]:** Aktive Referenzsuche bleibt ohne Treffer; Python-Compile, Tests und WPF-Build bestehen nach Löschung.
* **SC-063 [OBJ-64]:** Marker fehlen und `Tests/test_audit_sdd_gate.py` besteht.
* **SC-064 [OBJ-65]:** Ein zweiter DirectML-Separator wartet auf die vollständige Patch-Wiederherstellung des ersten; nach beiden Aufrufen ist `ort.SessionOptions.__init__` identisch zum ursprünglichen Konstruktor.
* **SC-065 [OBJ-66]:** Ein DB-Ladefehler liefert HTTP 500, bindet Brain nicht um und bewahrt Projekt, Medienkatalog und Analyse-Caches des zuvor aktiven Projekts.
* **SC-066 [OBJ-67]:** Bei fehlendem echten PyAudio enthält `sys.modules` nach dem BeatDetector-Import keinen Fake-`pyaudio`-Eintrag; der librosa-Fallback und der BeatNet-Importvertrag bleiben funktionsfähig.
* **SC-067 [OBJ-68]:** `PythonBridgeService` lehnt fehlende und nicht als 3.11 identifizierte Interpreter vor `Process.Start` explizit ab; Python312, unversioniertes `py.exe` und `python` sind keine Kandidaten.

## Problem Statement
Nach dem erfolgreichen Abschluss aller funktionalen Epics der Entwicklungs-Roadmap ist es von kritischer Bedeutung, die Codebase einer rigorosen, evidenzbasierten und lückenlosen Auditierung zu unterziehen. Stumme Ausnahmen (silent exceptions), unvollständige VRAM-Freigaben, Speicherlecks (memory leaks) bei WPF-ViewModels, SQLite-Lock-Contention im Concurrent-Betrieb, obsolete Dateileichen oder stumme Abbrüche in der Audio- und Videoverarbeitung können die Stabilität im Langzeitbetrieb gefährden.

Zusätzlich wurden zwei kritische Probleme im Audio-Bereich identifiziert:
1. **Stem-Separation Crash:** Die Generierung von Stems über die App schlägt mit einem RuntimeError fehl, weil für das `htdemucs`-Modell in `audio_schemas.py` der ungültige Name `"htdemucs"` anstelle des korrekten Dateinamens `"htdemucs.yaml"` definiert ist.
2. **Audio-Analyse Lücke:** Die Audio-Analyse (Beats und Key) verwendet stur das Original-Audio, anstatt bei Vorhandensein von Stems die präziseren Spuren (Drums für Beats, Instrumental für Key) zu nutzen, was die Analyseergebnisse signifikant verschlechtert.

---

## Scope

## Included (Im Audit enthaltene Zonen)
* **Z-AUDIO:** BPM- und Key-Erkennung, Demucs Stem Separation, SpectralAnalyzer-Puffer, Floating-Point Berechnungen.
  * *Ergänzung:* Korrektur des `htdemucs.yaml` Strings in `audio_schemas.py` und Umleitung von Beat-Detection auf `drums_path` und Key-Detection auf `instrumental_path` in `audio_router.py`, falls Stems im Clip vorhanden sind.
* **Z-VIDEO + Z-RENDER:** MotionAnalyzer (RAFT), Vision LLM (Moondream FP16 ONNX), FrameGrabber, FFmpeg-Subprozesse, AMF-Hardware-Encoding-Fallbacks.
* **Z-CORE:** `VRAMBudgetManager`, aktive Modell-Registrierung, Threadpool-Grenzwerte, DirectML-Speicherlimits.
* **Z-DATA:** SQLite WAL-Journaling, FAISS-Index-Lebenszyklen, base64-gzip Serialisierung, `sqlite-vec` KNN-Anfragen.
* **Shared-Zones & Z-INFRA:** `main.py`, `app_state.py`, WPF-to-Python SSE Bridge, REST-Routen.
* **Z-UI-VM & Z-UI-SERVICES:** IDisposable ViewModels, Memory Leakage Probes, eventbasierte UI-Routing-Leaks.

### Excluded
* Externe Hardware-Installationen oder Treiber-Aktualisierungen.

---

## Technical Objectives
* **OBJ-1:** Identifikation aller stillen Exceptions oder stummen Pipeline-Abbrüche in backend/routers/ und src/pb_studio/.
* **OBJ-2:** Aufspüren von Speicherlecks in C#- und Python-Dateien.
* **OBJ-3:** Aufdecken von VRAM-Bottlenecks oder Modell-Evizierungslücken im `VRAMBudgetManager`.
* **OBJ-4:** Überprüfung der SQLite- WAL-Konfiguration und Lock-Contention-Sicherheit.
* **OBJ-5:** Aufspüren von Dateileichen, veralteten Wrappern, toten Importen oder Code-Drifts.
* **OBJ-6:** Behebung des htdemucs Modellauswahl-Crashes bei der Stem-Separation.
* **OBJ-7:** Integration der Stems (Drums für Beats, Instrumental für Key) in die Audio-Analyse-Pipeline.

---

## Success Criteria (SC)
* **SC-001 [OBJ-1]:** Ein lückenloser, klinischer Audit-Bericht listet alle echten Code-Schwachstellen auf.
* **SC-002 [OBJ-2]:** 0 verbleibende IDisposable-Lecks bei WPF-ViewModels.
* **SC-003 [OBJ-3]:** Nachweisbare Stabilität aller DirectML-Fallbacks bei künstlicher VRAM-Reduktion.
* **SC-004 [OBJ-4]:** Keine ungesicherten SQLite-Schreibaufrufe im Backend.
* **SC-005 [OBJ-6]:** Erfolgreiche Stem-Separation mit `htdemucs.yaml` ohne Model-NotFound-RuntimeError.
* **SC-006 [OBJ-7]:** Die Audio-Analyse führt die Beat-Detection auf der Drums-Spur und die Key-Detection auf der Instrumental-Spur durch, wenn diese Stems existieren.

