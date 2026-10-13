# Consulting Team Review

## Executive Summary

Der Gesamtplan wurde mit neun Fachagenten und einem unabhängigen Gegenprüfer erneut gegen die tatsächlichen Producer-/Consumerketten geprüft. Ergebnis:18 zusätzliche konkrete Vertrags-, Verdrahtungs- oder Reihenfolgelücken beziehungsweise Präzisierungen bereits bekannter Risiken. Sie sind in den Planungsdokumenten korrigiert; alle45 Umsetzungspakete bleiben offen. Eine hundertprozentige Betriebsgarantie ist daraus nicht ableitbar: Keine neue Produktimplementierung, Runtime-, GUI-, GPU- oder Medienabnahme fand statt.

## Findings (nach Severity)

Keine neue Critical-Einstufung aus dieser statischen Prüfung. Severity bewertet die Folgen einer unvollständigen Umsetzung, nicht einen reproduzierten Produktfehler. Die ersten40 Befunde,19 früheren Gegenprüfungen und14 Kommunikationsbefunde bleiben getrennte historische Register; FP01–FP18 schließen konkrete Restlücken, nicht18 unabhängig reproduzierte Bugs.

### High

- **FP01 — Audiozeitachse bis zum tatsächlichen Pacingconsumer** (Fachgebiet: audio). Gegenmaßnahme: Zeitstützstellen, Sourceoffset, halb offene Coverageintervalle, Endpunktkonvention und profilgebundene Interpolation bis zum Service/Engine-Consumer durchreichen. Keine Streckung von Teilbereichen auf Gesamtdauer und keine stille Extrapolation. Legacyprojektion nur als explizit qualifizierter Adapter. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP03 — Timeline-CAS an sämtliche Schreiber anschließen** (Fachgebiet: pacing). Gegenmaßnahme: Persistierte timeline_uuid/timeline_revision getrennt von Assetplanrevision. Sämtliche manuellen/automatischen Schreib-, Lösch-, Reorder-, Reload-/Savepfade inventarisieren und an einen atomaren Commitvertrag binden. Slotübernahme prüft Projekt, Planrevision, Timelinebasisrevision und stabile Slot-ID gemeinsam. Gapi/Gmigration bleiben offen. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP04 — Feste UI-/Canvas-Anker in Coverage und Assetplan** (Fachgebiet: pacing). Gegenmaßnahme: AnchorSnapshot bindet wirksame UI-/Canvasanker, Quellen, aufgelöste reservierte Intervalle und Revision/Hash. Coverage respektiert Reservierungen; Änderungen invalidieren betroffene Entscheidungen. Fehlende/ungeeignete Anker werden sichtbar geklärt statt automatisch ersetzt. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP06 — Pflichtcacheconsumer an aktive Run-/Vektoridentität binden** (Fachgebiet: video/brain). Gegenmaßnahme: Roh- und Projektionscache verpflichtend an unveränderliche aktive Run-/Vektoridentität, Embeddingraum und Projektorrevision binden. Sourcehash+Modellname reicht nicht. Native-SigLIP-Fall gehört zum Pflichtumfang, unabhängig von optionalem T037. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP08 — Restorezaun verhindert erneuten Remoteversand** (Fachgebiet: project/recovery). Gegenmaßnahme: Jeder tatsächliche Restore/Rücksprung einschließlich konsistenter automatischer Crashrecovery erzeugt neue Storegeneration und Dispatchfence. Restoreepoch außerhalb zurückgespielter Domainrecords dauerhaft binden; unbekannter Restorenachweis sperrt. Recovered pending/prepared/outbox beweist kein Nicht-Send. Fehlende jüngere Jobs/Cancelintents als Ungewissheit behandeln. Abgleich oder needs_decision; Startupscan allein hebt Sperre nicht auf. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP10 — Direkte Preview-/Render-GPU-Aufrufer in Admission aufnehmen** (Fachgebiet: gpu). Gegenmaßnahme: Consumer-Matrix Audio/Video/Preview/Render und direkte synchrone Modellaufrufer verbindlich inventarisieren. Gemeinsame Admission vor allen lokalen Eintrittspunkten, auch direkten Locknutzern. Reihenfolge Ressourcenlease→Async-Lock→gpu_inference_lock; managed qualifiziert genau den kooperierenden Scope. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP11 — Leaseownership bis zum physischen Workerende** (Fachgebiet: gpu). Gegenmaßnahme: Requesttimeout/Cancel überträgt Lease und Erneuerung an tatsächlichen Cleanupowner. Freigabe erst nach Workerende plus gefordertem Ressourcenreceipt. Lokaler Lock und externe Nutzungsberechtigung getrennt. Dead owner/ungeklärter Cleanup bleibt gesperrt/unknown; kein äußeres finally mit vorzeitiger Freigabe. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP15 — Settings-CAS über Neustart, Diskfehler und Reloadrace** (Fachgebiet: settings). Gegenmaßnahme: Opaquer ConfigToken bindet Backendinstanz, Revision und gültigen Snapshotdigest. GET/PATCH liefert bestätigten Snapshot+Token. Schema/Token/Diskdigest vor Mutation prüfen; Patch/Reload serialisieren oder beim Commit erneut vergleichen. Persistenz vor Veröffentlichung effektiven Snapshots, einheitliche Consumerbenachrichtigung; Savefailure erhält letzten gültigen Stand. Neue Jobs erhalten neuen Snapshot, vorhandene Attempts bleiben gepinnt. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP16 — Holdout vom bereits vorhandenen Brainlernen isolieren** (Fachgebiet: brain/acceptance). Gegenmaßnahme: Benchmark-/Holdoutratings verpflichtend in separatem Evaluationsspeicher; keine Weiterleitung an produktives /brain/feedback oder Generatortraining. Testprojekt allein isoliert gemeinsame Brainzustände nicht. Brain-/Directorvergleiche binden eingefrorenen Gewichtsstand, Projektorgeneration und Lernpolicy. T039 qualifiziert nur isolierte Benchmarks; T042 zusätzlich gebunden, nicht alleiniger Owner. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP17 — Parent-Sourcezeit auf Child-lokale Derivatzeit abbilden** (Fachgebiet: timeline). Gegenmaßnahme: DerivationTimeMap bindet Parent/Childhash, rationale Source-/Childbereiche, Fensterorigin/Handles, Mappingrevision und qualifizierte Transformation. Assetübernahme rechnet ausdrücklich in Child-local Sourcein/out um; keine Parentoffsets auf kurzen Child clippen. Unknown/nicht qualifiziertes nichtlineares Retime blockiert Übernahme. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

### Medium

- **FP02 — Capability-Composer für gruppierte Legacy-Audiostages** (Fachgebiet: audio). Gegenmaßnahme: Capability→Payloadfeld→Legacygruppe als versionierte FieldOwnershipMap definieren. ActiveAnalysisSnapshot bindet konsistent alle gewählten Run-/Stage-/Dependencyrevisionen. Gruppenstatus wird aus tatsächlichen Consumerpflichten abgeleitet; eine Capabilityaktivierung überschreibt keine fremden Resultate. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP05 — Coverage-Einstieg vor leerer Videolibrary-Sperre** (Fachgebiet: pacing). Gegenmaßnahme: Separaten typisierten Director-Planungs-/Coverage-Request vor Cutgenerierung anbieten. Valide leere Library kann insufficient sein; unbekannte Analyse bleibt unknown. Nach qualifizierter Generation/Import/Eignung reguläre Cutgenerierung mit Media-IDs. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP07 — Partielle native Captionstages verlustfrei normalisieren** (Fachgebiet: video). Gegenmaßnahme: Stage.status enthält partial samt gültigen Teilresultaten, Coverage und Fehlergrund. Aggregate getrennt ableiten; profilgebundene Aktivierung/Eignung. Weder completed vortäuschen noch gültige Tags pauschal verwerfen. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP09 — Vorhandene kanonische Projekt-UUID wiederverwenden** (Fachgebiet: project). Gegenmaßnahme: Bestehende stable_project_uuid-Migration/Backfill und Katalog-UUID verwenden. Neu sind dauerhafte Jobbindung und Übergang zum flüchtigen Commitkontext. Keine zweite UUIDvergabe/-migration für identifizierte Projekte; Datei/Katalogkonflikte blockieren Dispatch/Import. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP12 — VRAM-Buchhaltung nicht als gemessenen Hardwarepeak qualifizieren** (Fachgebiet: gpu). Gegenmaßnahme: estimated_committed_mb, beobachtetes Sensormaximum und qualifizierten Profilgrenzwert getrennt führen. Receipt bindet Quelle/Gerät/Abtastrate/Fenster/Abdeckung/Ausfälle/Fremdlast. Vorhandenes vram_peak_mb aus zwei Buchhaltungsständen ist kein Hardwarepeak; Stichprobenmaximum keine exakte Peakgarantie. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP13 — Technischen Farb-/Streamvertrag qualifizieren** (Fachgebiet: export). Gegenmaßnahme: Versioniertes Profil für Streamauswahl, pix_fmt/Bittiefe, Primärfarben, Transfer, Matrix, Range und SAR. Zunächst ausdrücklich qualifizierte SDR-Familien; HDR/unknown außerhalb Profil nicht still akzeptieren. Separate qualifizierte Ableitung möglich, kein neuer pauschaler HDR-Support. Transformation/Profil bis Preview/Final/Derivatprovenance binden. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP14 — DTO-Katalog und neuer Kommunikationsvertrag widersprechen sich** (Fachgebiet: contract consistency). Gegenmaßnahme: ProviderJobEvent auf verbindlichen Invalidierungs-/Changefeedvertrag angleichen. Neue Kommunikations-DTOs im Katalog referenzieren statt alte Event-Deltastruktur parallel normativ zu behalten; Aliasregeln job_id/job_uuid explizit. Maschinenprüfbare Schemafixtures und ein normativer Typenowner vor Gapi. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

- **FP18 — Native-AnalysisRun-Producer vor MVP eindeutig zuweisen** (Fachgebiet: independent phase countercheck). Gegenmaßnahme: Schmale Native-SigLIP→validierter/persistierter AnalysisRun-Anbindung ausdrücklich T020 zuweisen; T019 liefert Importclaim/Mediaidentität. Breite capabilityweise Native-Stage-/Consumeradaption bleibt T031 nach MVP. T020 darf nicht auf einen erst in T031 vorhandenen Producer angewiesen sein. Quellen/ursprüngliche Planstellen und zukünftiger Gegenbeweis: [Register](findings.json), [verbindlicher Vertrag](../domain-contracts.md).

## Prüfabdeckung und tatsächlich eingesetzte Agenten

| Agent | Fachskill | Bereich / Ergebnis |
|---|---|---|
| full_audio / analyst-audio | audio-expertise | Streaming, Stems, Zeitreihen, gruppierte Audiostages; FP01/02; gezielte Korrekturprüfung |
| full_pacing / analyst-ki-regie | pacing-expertise, audio-video-pacing-specialist | Coverage, Asset-DAG, Timeline, Anker; FP03/04/05 |
| full_video / analyst-video | video-expertise | Captionpartial, Motion, Embeddingconsumer; FP06/07 |
| full_project / analyst-projekt | projekt-expertise | vorhandene UUID, Recovery, Katalog-/Rootbindung; FP08/09; gezielte Korrekturprüfung |
| full_gpu / analyst-performance | gpu-expertise | native Eintrittspunkte, Cleanup, Lease, Messquellen; FP10/11/12 |
| full_export / analyst-export | rendering-expertise | Preview/AMF/Probe, Farbprofil und FPSübergabe; FP13 |
| full_settings / analyst-settings | config-expertise | persistierte/effective Settings, Reload/CAS/Neustart; FP15 |
| full_brain / analyst-hirn | brain-expertise | bestehendes Lernen, Holdout, Vergleich/AUTO; FP16 |
| full_timeline / analyst-timeline | timeline-expertise | Derivatzeit, Sourceoffset, Save/Reopen/Preview; FP17 |
| full_independent / unabhängiger Prüfer | consulting-team: Devil's Advocate/Steel-Man | erhielt Artefakt ohne andere Befunde; Phasen-/Producerreihenfolge FP18; spätere gezielte Korrekturprüfung |
| Parent | caveman, pb-master, consulting-team; config-/model-registry-expertise; pb-studio-real-media-acceptance-team als Abnahmeleitfaden | Vertragskonsistenz FP14, Synthese, Quellenrecherche, Dokumentänderungen und Strukturprüfung |

Fachskills liefern Suchhinweise, keine automatisch aktuellen Fakten. Veraltete Skillpfade und alte UI-/Runtimeannahmen wurden nicht als Belege übernommen. Nicht ausgelöst: Implementierungsagenten, Auto-QA, Appstart/GUIsteuerung oder pauschale Healthchecks. Chat-/Terminalagenten würden den hier geprüften Integrationsverträgen keine eigenständige zusätzliche Prüfung liefern; neue Jobwire-Diagnose ist bereits im Kommunikationsaudit abgedeckt.

## Sieben Consulting-Perspektiven

Diese Perspektiven sind Rollen der Synthese, keine sieben zusätzlich gestarteten Prozesse.

- Engagement Manager: Aufgabe in Daten-/Recovery-, Medien-/Consumer-, Ressourcen-, UI-/Wire- und Abnahmeverträge zerlegt. Falsifizierbar: jedes FP hat konkrete Paket- und Nachweiszuordnung.
- Senior Partner: Additive Architektur und früher Profil-Smoke bleiben tragfähig. Gegenprobe FP18 zeigt: ein formal azyklischer Taskgraph reicht ohne verfügbare Producer nicht.
- Analyst: Zahlenwerte bleiben ausdrücklich offen. FP12 trennt vorhandene Buchhaltung von Sensormessung; offizielle Python-, SQLite- und FFmpeg-Dokumentation wurde ergänzend geprüft.
- Domain Expert: Tatsächliche Consumer müssen geplante Semantik erhalten. FP01/02/06/17 verfolgen Werte bis Pacing, Brain beziehungsweise Source-Seek, statt allein Payloadschemas zu beurteilen.
- Risk Officer: Pre-mortem Restore nach Remote-Send und Cancel vor Workerende. FP08/11 sperren wiederholten Versand beziehungsweise vorzeitige Ressourcenfreigabe, sofern spätere Gegenprüfungen bestehen.
- Devil's Advocate: Unabhängige Erstprüfung fand FP18; keine übrigen Agentenberichte gelesen. Stärkste Gegenposition unten. Erst danach gezielte Korrekturprüfung erlaubt.
- Synthesizer: Befunde dedupliziert, Unterschiede zwischen Quellbeleg/Planabsicht/Runtimebeweis erhalten. Keine Erfolgswertung aus Umfang, Agentenzahl oder bloßer Dokumentvollständigkeit.

## Steel-Man Gegenposition (Devil's Advocate)

Der Plan enthält bereits viele sinnvolle Grenzen: früher Hardware-Smoke, ein durchgängiger MVP vor Varianten, getrennte Job-/Attempt-/Importzustände und kein blindes Resubmit. Optionale Erweiterungen sind keine pauschalen Voraussetzungen. Zusätzliche Verträge dürfen diese Architektur nicht unnötig durch neue Systeme ersetzen; vorhandene Projekt-UUID und vorhandene Consumer sind weiterzuverwenden. Die richtige Konsequenz ist ein schmaler, nachweisbarer erster Medienflow mit anschließender phasenweiser Erweiterung, keine Behauptung, alle Risiken seien allein durch Planung beseitigt.

## Gegenprüfung der Korrekturen

Drei gezielte Read-only-Nachprüfungen: Projekt/Recovery, Audio/Consumer und unabhängige Producer-/Phasenprüfung. Dabei verbleibende Punkte erkannt und danach korrigiert:

1. Restorebetroffene pending/waiting/retry_wait-Jobs dürfen needs_decision erreichen; recovered prepared-Attempts wechseln ohne erfundenen Send zu submission_unknown. Unaufklärbare verlorene Records bleiben blockiert.
2. T009 prüft Repository/Cachekern und bestehende Nativeconsumer; vollständige gemischte Capabilityadaption gehört T031. Frühe Paketabnahme darf spätere Funktionen nicht voraussetzen.
3. T019 liefert den Importclaim; T020 produziert den schmalen Native-SigLIP-AnalysisRun und ADD-Nachweis; T026 nimmt den realen Gesamtflow ab. Breite T031-Adaption folgt später.

Letzte Korrekturen wurden zusätzlich durch den gespeicherten Dokumentvalidator geprüft. Das ist keine weitere eigenständige Runtime- oder Expertenabnahme.

## Open Questions

Keine Wiederöffnung von D01/D02/O01–O04. Offen bleiben konkret:

- O03: autorisierte Referenzmedien/Labels, Qualitäts-/Farb-/Zeit-/Ressourcengrenzen, Abtastung und belastbare Messprofile.
- O04: konkrete DDL-/DTO-/OpenAPI-Verträge und gesonderte API-/Migrationsfreigaben auf isolierten Daten.
- Profilqualifikation: tatsächlicher Comfyworkflow, Node-/Modell-/Runtimehashes, passende lokale Hardware- und Mediennachweise.
- Umsetzungs- und spätere Abnahmefreigaben: keine Implementierung durch diese Planprüfung autorisiert; alle Produktgates bleiben offen.

Cloud bleibt außerhalb des PB-Masterplans. Separate ComfyUI-Konfiguration ist keine von PB versprochene Funktion oder Qualifikation.

## Recommendation

**GO mit dokumentierten Korrekturen für die weitere Planung; Produktfreigabe weiterhin OPEN.**

Confidence: HIGH für die aufgeführten gelesenen Vertrags-/Quellwidersprüche; Laufzeitzuverlässigkeit unbewiesen. Reversibilität: Dokumentänderungen two-way door; Migrationen gesondertes Gate.

Der Plan ist konkreter und überprüfbarer. „100% bombensicher“ wäre ohne ausgeführte Fehler-, Medien- und Native-GUI-Abnahmen eine falsche Aussage.

## Nachweise und Grenzen

[Verifikation](verification.json) enthält Hash-/Strukturprüfungen, keine Produkt-PASSwerte. [Baseline](baseline-manifest.json) hält den Zustand vor diesen Änderungen fest. [Befunde](findings.json) enthalten exakte Quellen und künftige Gegenproben; [Fachverträge](../domain-contracts.md) und aktualisierte45 Arbeitspakete bilden das Ergebnis ab. Bestehende Produktänderungen im Arbeitsbaum wurden nicht zurückgesetzt.

Offizielle Recherche: [Python3.11 Future.cancel](https://docs.python.org/3.11/library/concurrent.futures.html#concurrent.futures.Future.cancel), [SQLite Backup API](https://sqlite.org/backup.html), [FFmpeg colorspace](https://ffmpeg.org/ffmpeg-filters.html#colorspace). Ableitung: ein DBsnapshot setzt keinen externen Dienst zurück; Requestcancel beendet laufende Threadarbeit nicht zwangsläufig; Decodierbarkeit allein qualifiziert keine Farbtransformation. Lokale konkrete Fähigkeiten bleiben separat zu prüfen.
