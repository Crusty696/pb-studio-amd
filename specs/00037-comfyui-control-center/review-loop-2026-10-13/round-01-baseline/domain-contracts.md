# Ergänzende fachliche Integrationsverträge

Stand2026-10-13. Bestandteil des Masterplans, ausschließlich [ABSICHT]. Quellenbelege und vor Änderung gesicherte Planstellen stehen in full-plan-audit-2026-10-13/findings.json. Folgende Abnahmen sind geplant, nicht ausgeführt. Bereits bestätigte Entscheidungen werden nicht erneut geöffnet. Konkrete Zahlenprofile, Medienfreigaben, DDL und öffentliche API-Freigaben bleiben offen.

Die stärkste tragfähige Architektur bleibt: unabhängiges ComfyUI, PB als Eigentümer von Jobs/Medien/Timeline, revisionsgebundene Resultate, begrenzte Ausführung und nachweisgebundene Qualifikation. Die folgenden Verträge schließen konkrete Übergangslücken dieser Architektur.

## FP01 — Audiozeitachse bis zum tatsächlichen Pacingconsumer

Zeitstützstellen, Sourceoffset, halb offene Coverageintervalle, Endpunktkonvention und profilgebundene Interpolation bis zum Service/Engine-Consumer durchreichen. Keine Streckung von Teilbereichen auf Gesamtdauer und keine stille Extrapolation. Legacyprojektion nur als explizit qualifizierter Adapter.

**Verantwortliche Pakete:** T031, T034.

**Endabnahme:** T031 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Peak bei Sourcezeit40s in Range[30,50) eines120sMediums bleibt nach Service→Engine an40s; mehrere Hopraten, Chunkgrenzen und Coverage-Lücken prüfen. Toleranz O03 offen.

## FP02 — Capability-Composer für gruppierte Legacy-Audiostages

Capability→Payloadfeld→Legacygruppe als versionierte FieldOwnershipMap definieren. ActiveAnalysisSnapshot bindet konsistent alle gewählten Run-/Stage-/Dependencyrevisionen. Gruppenstatus wird aus tatsächlichen Consumerpflichten abgeleitet; eine Capabilityaktivierung überschreibt keine fremden Resultate.

**Verantwortliche Pakete:** T009, T031.

**Endabnahme:** T031 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Nativebeats A, externe Energie B, Drums C: A→A2 verändert weder B/C noch deren Provenance; C unavailable führt nur zur ausdrücklich erlaubten Degradation. Reload liefert denselben Snapshot.

## FP03 — Timeline-CAS an sämtliche Schreiber anschließen

Persistierte timeline_uuid/timeline_revision getrennt von Assetplanrevision. Sämtliche manuellen/automatischen Schreib-, Lösch-, Reorder-, Reload-/Savepfade inventarisieren und an einen atomaren Commitvertrag binden. Slotübernahme prüft Projekt, Planrevision, Timelinebasisrevision und stabile Slot-ID gemeinsam. Gapi/Gmigration bleiben offen.

**Verantwortliche Pakete:** T040.

**Endabnahme:** T040 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Manuelles Edit nach Jobstart, konkurrierende Commits und Restart: veraltete Übernahme liefert Konflikt; kein Überschreiben und keine still verlorenen Edits.

## FP04 — Feste UI-/Canvas-Anker in Coverage und Assetplan

AnchorSnapshot bindet wirksame UI-/Canvasanker, Quellen, aufgelöste reservierte Intervalle und Revision/Hash. Coverage respektiert Reservierungen; Änderungen invalidieren betroffene Entscheidungen. Fehlende/ungeeignete Anker werden sichtbar geklärt statt automatisch ersetzt.

**Verantwortliche Pakete:** T040.

**Endabnahme:** T040 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Mit/ohne Anker, fehlendes Asset, Überlappung, Verschiebung während Generation und beide Pacingpfade: reservierte Bereiche bleiben erhalten; keine unnötigen Ersatzjobs.

## FP05 — Coverage-Einstieg vor leerer Videolibrary-Sperre

Separaten typisierten Director-Planungs-/Coverage-Request vor Cutgenerierung anbieten. Valide leere Library kann insufficient sein; unbekannte Analyse bleibt unknown. Nach qualifizierter Generation/Import/Eignung reguläre Cutgenerierung mit Media-IDs.

**Verantwortliche Pakete:** T040.

**Endabnahme:** T040 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Audio plus valide leere Library erreicht Coverage; Profil/Budget kontrollieren Generation. Fehlende Analyse löst keine Generation aus; manuelle Cutgenerierung behält ihre Validierung.

## FP06 — Pflichtcacheconsumer an aktive Run-/Vektoridentität binden

Roh- und Projektionscache verpflichtend an unveränderliche aktive Run-/Vektoridentität, Embeddingraum und Projektorrevision binden. Sourcehash+Modellname reicht nicht. Native-SigLIP-Fall gehört zum Pflichtumfang, unabhängig von optionalem T037.

**Verantwortliche Pakete:** T009, T031.

**Endabnahme:** T031 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Warmen Cache A füllen, B mit gleichem Source/Modell aber anderem Range/Sampling aktivieren: alle Brain/Pacingconsumer liefern B; Rückwahl A liefert A. Vergleich ohne Aktivierung verändert A nicht; Prozess/Restart prüfen.

## FP07 — Partielle native Captionstages verlustfrei normalisieren

Stage.status enthält partial samt gültigen Teilresultaten, Coverage und Fehlergrund. Aggregate getrennt ableiten; profilgebundene Aktivierung/Eignung. Weder completed vortäuschen noch gültige Tags pauschal verwerfen.

**Verantwortliche Pakete:** T008, T031, T035.

**Endabnahme:** T031 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Mindestens ein gültiger und ein fehlgeschlagener Captionframe: Tags und Lücken bleiben bis API/WPF/Director sichtbar. Vollfehler und valide leere Caption unterscheidbar.

## FP08 — Restorezaun verhindert erneuten Remoteversand

Jeder tatsächliche Restore/Rücksprung einschließlich konsistenter automatischer Crashrecovery erzeugt neue Storegeneration und Dispatchfence. Restoreepoch außerhalb zurückgespielter Domainrecords dauerhaft binden; unbekannter Restorenachweis sperrt. Recovered pending/prepared/outbox beweist kein Nicht-Send. Fehlende jüngere Jobs/Cancelintents als Ungewissheit behandeln. Abgleich oder needs_decision; Startupscan allein hebt Sperre nicht auf.

**Verantwortliche Pakete:** T011, T012, T013, T021.

**Endabnahme:** T021 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Snapshot vor Send, Remote führt aus, anschließend Restore optional mit leerer History: null weitere POST/prompt. Verlorener Cancel/WPF-Neustart ebenfalls; Generation/Cursorreset und sichtbarer blockierter Zustand.

## FP09 — Vorhandene kanonische Projekt-UUID wiederverwenden

Bestehende stable_project_uuid-Migration/Backfill und Katalog-UUID verwenden. Neu sind dauerhafte Jobbindung und Übergang zum flüchtigen Commitkontext. Keine zweite UUIDvergabe/-migration für identifizierte Projekte; Datei/Katalogkonflikte blockieren Dispatch/Import.

**Verantwortliche Pakete:** T010, T011.

**Endabnahme:** T011 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Bestehendes Projekt öffnen, Job anlegen, reopen/Recovery: Katalog-, Datei- und Job-UUID unverändert. Absichtlich abweichende Datei-UUID blockiert vor Mutation.

## FP10 — Direkte Preview-/Render-GPU-Aufrufer in Admission aufnehmen

Consumer-Matrix Audio/Video/Preview/Render und direkte synchrone Modellaufrufer verbindlich inventarisieren. Gemeinsame Admission vor allen lokalen Eintrittspunkten, auch direkten Locknutzern. Reihenfolge Ressourcenlease→Async-Lock→gpu_inference_lock; managed qualifiziert genau den kooperierenden Scope.

**Verantwortliche Pakete:** T015, T016.

**Endabnahme:** T016 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Jeder inventarisierte Eintrittspunkt konkurriert mit externer Reservierung: managed ohne lokale Umgehung; observed_shared ohne erfundene Exclusivityzusage.

## FP11 — Leaseownership bis zum physischen Workerende

Requesttimeout/Cancel überträgt Lease und Erneuerung an tatsächlichen Cleanupowner. Freigabe erst nach Workerende plus gefordertem Ressourcenreceipt. Lokaler Lock und externe Nutzungsberechtigung getrennt. Dead owner/ungeklärter Cleanup bleibt gesperrt/unknown; kein äußeres finally mit vorzeitiger Freigabe.

**Verantwortliche Pakete:** T015, T016, T021.

**Endabnahme:** T016 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Blockierter Worker, Requesttimeout, externe Dispatchanfrage: keine frühe managed-Freigabe. Zweiter Cancel, Shutdown und Heartbeatausfall prüfen.

## FP12 — VRAM-Buchhaltung nicht als gemessenen Hardwarepeak qualifizieren

estimated_committed_mb, beobachtetes Sensormaximum und qualifizierten Profilgrenzwert getrennt führen. Receipt bindet Quelle/Gerät/Abtastrate/Fenster/Abdeckung/Ausfälle/Fremdlast. Vorhandenes vram_peak_mb aus zwei Buchhaltungsständen ist kein Hardwarepeak; Stichprobenmaximum keine exakte Peakgarantie.

**Verantwortliche Pakete:** T002, T007, T015.

**Endabnahme:** T015 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Kurzzeitspitze zwischen Start/Ende, Fremdlast und Sensorlücke: Buchhaltung wird niemals als Hardwaremessung freigegeben. Konkrete Grenzwerte bleiben O03 offen.

## FP13 — Technischen Farb-/Streamvertrag qualifizieren

Versioniertes Profil für Streamauswahl, pix_fmt/Bittiefe, Primärfarben, Transfer, Matrix, Range und SAR. Zunächst ausdrücklich qualifizierte SDR-Familien; HDR/unknown außerhalb Profil nicht still akzeptieren. Separate qualifizierte Ableitung möglich, kein neuer pauschaler HDR-Support. Transformation/Profil bis Preview/Final/Derivatprovenance binden.

**Verantwortliche Pakete:** T018, T026, T028, T029.

**Endabnahme:** T026 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Freigegebene SDR limited/full und10bit/HDR-Fälle korrekt nach Profil behandeln oder sichtbar abweisen; Preview/Final mit Farbreferenz vergleichen. Messgrenzen O03 offen. Full Decode allein kein Farbbeweis.

## FP14 — DTO-Katalog und neuer Kommunikationsvertrag widersprechen sich

ProviderJobEvent auf verbindlichen Invalidierungs-/Changefeedvertrag angleichen. Neue Kommunikations-DTOs im Katalog referenzieren statt alte Event-Deltastruktur parallel normativ zu behalten; Aliasregeln job_id/job_uuid explizit. Maschinenprüfbare Schemafixtures und ein normativer Typenowner vor Gapi.

**Verantwortliche Pakete:** T010, T022, T024, T025.

**Endabnahme:** T025 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Katalog/Schema/WPF/Python-Goldenfixtures enthalten denselben Event/Identity/Outcomevertrag; Job- und Batchänderung sowie unbekannte Pflichtsemantik prüfen.

## FP15 — Settings-CAS über Neustart, Diskfehler und Reloadrace

Opaquer ConfigToken bindet Backendinstanz, Revision und gültigen Snapshotdigest. GET/PATCH liefert bestätigten Snapshot+Token. Schema/Token/Diskdigest vor Mutation prüfen; Patch/Reload serialisieren oder beim Commit erneut vergleichen. Persistenz vor Veröffentlichung effektiven Snapshots, einheitliche Consumerbenachrichtigung; Savefailure erhält letzten gültigen Stand. Neue Jobs erhalten neuen Snapshot, vorhandene Attempts bleiben gepinnt.

**Verantwortliche Pakete:** T003, T022, T023.

**Endabnahme:** T023 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Gleiche numerische Revision nach Neustart, zwei Settingsfenster, externe Edit, Write/Replacefehler und Watcher/PATCH-Rennen: Konflikt ohne Teilmutation; Publish erst nach Commit; UI-Erfolg nur bestätigtes Receipt.

## FP16 — Holdout vom bereits vorhandenen Brainlernen isolieren

Benchmark-/Holdoutratings verpflichtend in separatem Evaluationsspeicher; keine Weiterleitung an produktives /brain/feedback oder Generatortraining. Testprojekt allein isoliert gemeinsame Brainzustände nicht. Brain-/Directorvergleiche binden eingefrorenen Gewichtsstand, Projektorgeneration und Lernpolicy. T039 qualifiziert nur isolierte Benchmarks; T042 zusätzlich gebunden, nicht alleiniger Owner.

**Verantwortliche Pakete:** T002, T038, T039, T042.

**Endabnahme:** T038 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Holdoutrating verändert keine produktiven feedback_events, Gewichtsbuckets, total_clicks oder Projektorgeneration. Paralleles normales Feedback ändert eingefrorenen Vergleich nicht; Restart/Replay übernimmt Evaluation nie ins Training.

## FP17 — Parent-Sourcezeit auf Child-lokale Derivatzeit abbilden

DerivationTimeMap bindet Parent/Childhash, rationale Source-/Childbereiche, Fensterorigin/Handles, Mappingrevision und qualifizierte Transformation. Assetübernahme rechnet ausdrücklich in Child-local Sourcein/out um; keine Parentoffsets auf kurzen Child clippen. Unknown/nicht qualifiziertes nichtlineares Retime blockiert Übernahme.

**Verantwortliche Pakete:** T027, T030, T040.

**Endabnahme:** T040 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Parentfenster[599,606), Ersatz[600,605), Child7s: Childrange[1,6) durch sichtbare Übernahme→Save→Reopen→Scrub→Preview→Export. Niemals Sourceoffset600; Grenzframes/Handles und FPSwechsel prüfen.

## FP18 — Native-AnalysisRun-Producer vor MVP eindeutig zuweisen

Schmale Native-SigLIP→validierter/persistierter AnalysisRun-Anbindung ausdrücklich T020 zuweisen; T019 liefert Importclaim/Mediaidentität. Breite capabilityweise Native-Stage-/Consumeradaption bleibt T031 nach MVP. T020 darf nicht auf einen erst in T031 vorhandenen Producer angewiesen sein.

**Verantwortliche Pakete:** T019, T020, T026, T031.

**Endabnahme:** T020 im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.

**Verbindliche spätere Gegenprüfung:** Reale Native-Erzeugung→persistierter Run→ADDreceipt→ready wird vor T026 abgenommen; kein selbstgebautes AnalysisRun-Fixture als alleiniger Integrationsnachweis. T031 bleibt nicht Voraussetzung für T026.

## Ergänzende Festlegungen für Umsetzung und Abnahme

- FP01/FP02: FieldOwnershipMap muss vor Implementierung jedes bestehende Audiofeld einschließlich tempo_curve/subtrack_segments einem Producer und Consumer zuordnen. Gemischte Snapshots prüfen konkrete Abhängigkeiten; inkompatible Kombinationen bleiben unqualified. Ein atomar aktivierter Snapshot ersetzt keine unabhängigen unveränderlichen Runs. Kurven dürfen bei fehlender Coverage nicht durch erfundene Nullwerte vollständige Messung vortäuschen.
- FP03/FP04: Zeitlinenschreiber umfassen Generator, manuelle Edits, Autosave, Reload, Import und Clear. Ankeränderung benötigt eine zur Timeline/Assetplanbindung vergleichbare stabile Revision oder geprüften Snapshotdigest. Kein DB-Lock über Netzwerk-/GPU-Warten. Konflikt hält erzeugtes Asset auffindbar, blockiert aber automatische Slotübernahme.
- FP08: Restoreepoch muss vor Freigabe von Scheduler/HTTPmutationen dauerhaft bekannt sein. Bei nicht nachweisbarer Herkunft einer zurückkopierten DB fail closed; bloß identische UUID/gesunde SQLiteintegrität ist kein Frischebeweis. Bewusst neue Jobs nach Restore benötigen neuen Intent und bestätigten Recoveryumfang. Alte unbekannte Outcomes bleiben getrennt sichtbar; kein Freischalten der gesamten alten Outbox durch einen neuen Auftrag.
- FP10/FP11: Consumer-Matrix nennt konkreten Eintritt, Leaseowner, Lockreihenfolge, Timeout-/Cancelcleanup und Endreceipt. observed_shared bleibt Beobachtung ohne Garantie gegenüber fremden Prozessen; lokale Admission allein macht managed nicht kooperativ. Unbekannter Physikzustand wird nicht durch Lease-TTL oder numerische Nullbuchhaltung geheilt.
- FP13: Eingabemetadaten allein beweisen keine korrekte Farbreproduktion. Profile definieren akzeptierte Metadaten/fehlende Angaben, explizite Transformation und Abnahmeausgabe. Keine stille HDR→SDR-Umetikettierung; Original unverändert. Tatsächliche lokale FFmpegfilter/AMFfähigkeit vor Profilfreigabe prüfen. Die rationale FPS-Kette ProductionViewModel→ApiClient→RenderRequest→FFmpeg ebenfalls abnehmen: Dezimal23.976 ist nicht stillschweigend gleich24000/1001. Gapi bleibt offen.
- FP14: communication-contract.md ist normativer Owner des neuen Wireformats; Plan P indiziert dessen Typen. Konkrete JSONschemas/OpenAPI und Goldenfixtures vor Gapi erstellen, unauflösbare Widersprüche blockieren Implementierung. Bestehende Legacyevents behalten ihren separaten Vertrag.
- FP15: Externe Configänderungen sind konkurrierende Schreiber. Genau ein erfolgreicher Commit veröffentlicht den neuen effektiven Snapshot; fehlgeschlagene Persistenz erzeugt keine vorgetäuschte Wirksamkeit. PinnedAttempt enthält den vollständigen für Ausführung benötigten Snapshot/Fingerprint, nicht nur einen flüchtigen Revisionszähler.
- FP16: Evaluationsspeicher gehört zum Benchmarkbereich, kein zweiter Medienkatalog. Gefrorene Brainstände dürfen Vergleichsleser nicht aus laufendem globalem Singleton beziehen. Native-/Provider-Rohqualität und lernabhängige Directorqualität getrennt ausweisen; ein Vergleich ohne Brainabhängigkeit benötigt keinen erfundenen Trainingslauf.
- FP17: Allgemeiner ClipStart bleibt Child-lokale Sourceposition. Mapping wird vor Timelinecommit aufgelöst und in Provenance erhalten; Seekhelper soll keine Parentbeziehung erraten. Bei nichtlinearer Transformation nur tatsächlich qualifiziertes Mapping anwenden.

Öffentliche Grundlagen, gegen die die Planableitung geprüft wurde: [Python3.11 Future.cancel](https://docs.python.org/3.11/library/concurrent.futures.html#concurrent.futures.Future.cancel) unterscheidet wartende und bereits laufende Arbeit; [SQLite Backup API](https://sqlite.org/backup.html) beschreibt einen Datenbanksnapshot, keine atomare Rücksetzung eines externen Ausführungsprozesses; [FFmpeg colorspace](https://ffmpeg.org/ffmpeg-filters.html#colorspace) trennt Farbparameter und Transformation. Diese Dokumentation ersetzt weder den lokalen Buildnachweis noch die qualifizierte Medienabnahme.
