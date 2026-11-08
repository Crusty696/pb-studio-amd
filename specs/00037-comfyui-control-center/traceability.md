# Traceability: Originalauftrag, 40 Befunde, Requirements und Tasks

Stand2026-10-13. PLANUNG; alle Produktmaßnahmen unimplementiert. D01/D02 und O01–O04-Grundsätze bestätigt; konkrete O03-Mess-/Referenzgates und O04-Änderungsfreigaben weiterhin offen. Originaltext unverändert; SHA256 `4a1f436e6b1825f79623c93ab2d33918e1d6a69f8b66455ef99be776c7a7e6d6`.

## F01–F40: Schließmaßnahmen und Prüfkriterien

| ID | Befund | Requirements | Pakete |
|---|---|---|---|
| F01 | Unabhängige Comfy-Nutzung benötigt gemeinsamen Admissionvertrag | OR-001, OR-002, OR-003 | T015, T016 |
| F02 | Verlust der Submit-Antwort kann doppelte Ausführung verursachen | FR-013, OR-003, OR-004, RR-002, TR-009 | T012, T013 |
| F03 | Fertigmeldung ohne Importtransaktion gefährdet Katalog und Medienreferenzen | FR-009, FR-010, FR-011, OR-004, OR-005, OR-007, OR-008, RR-001, RR-002, RR-004, RR-005, TR-006, TR-010, TR-011, TR-012 | T017, T018, T019, T020, T021, T026 |
| F04 | Austauschbare Embeddings sind ohne gemeinsamen semantischen Raum nicht austauschbar | RR-001, RR-002, TR-005, TR-006, TR-010, TR-012 | T008, T020, T037 |
| F05 | ROCm-Bereichsentscheidung fehlte bei Erstprüfung; inzwischen geklärt | FR-009, OR-005, RR-004, RR-005, RR-006, TR-001 | T001, T006, T007 |
| F06 | Falsche Comfy-Installation kann Discovery und Quellenprüfung entwerten | FR-001, FR-002, TR-002, TR-004 | T003, T004 |
| F07 | Abbruch, Queue-Clear und Speicherfreigabe haben unterschiedliche Reichweite | FR-013, OR-001, OR-002, OR-003, RR-002 | T014, T015, T016 |
| F08 | Pause/Resume benötigt präzise operative Semantik | FR-013, FR-015, OR-002, OR-003, OR-004, RR-001, RR-002, RR-005, TR-008, TR-009, TR-012 | T010, T014, T021, T041 |
| F09 | Projektwechsel kann verspätete Ergebnisse in falsches Projekt schreiben | FR-010, FR-011, FR-014, OR-004, OR-008, RR-001, RR-002, TR-008, TR-009, TR-010, TR-012 | T010, T019, T021, T040 |
| F10 | Bestehende RenderQueue ist Vorlage, kein fertiger externer Jobmanager | FR-013, OR-003, OR-004, RR-001, TR-008, TR-009 | T010, T011, T012 |
| F11 | Recovery-Inventar und Zombie-Watcher fehlen im Integrationsplan | OR-004, RR-001, RR-002 | T021 |
| F12 | Resultschema braucht Einheiten, Zeitbasis und Herkunft pro Feld/Stufe | FR-005, FR-006, FR-007, FR-008, OR-007, RR-003, TR-005, TR-006, TR-007, TR-012 | T008, T031, T032, T033, T034, T035, T036 |
| F13 | Workflow-JSON ist nicht gleich ausführbarer API-Prompt | FR-003, TR-003 | T005 |
| F14 | Discovery beweist weder Modellhash noch Custom-Node-Version noch erfolgreiche Ausführung | FR-002, FR-003, FR-009, RR-004, TR-003, TR-004 | T004, T005, T007 |
| F15 | Beliebige zukünftige Nodes brauchen adapterfähige Outputverträge | FR-003, TR-003, TR-005, TR-006, TR-012 | T005, T008 |
| F16 | Longform erfordert begrenzte Arbeitsmengen auch innerhalb einzelner Nodes | FR-006, FR-012, FR-015, OR-003, OR-005, OR-007, RR-003, RR-005, TR-005, TR-011, TR-012 | T017, T018, T030, T034, T041 |
| F17 | Generierungs-Shot und Timeline-Cut sind unterschiedliche Einheiten | FR-009, FR-011, FR-012, FR-014, FR-015, OR-003, RR-002, RR-005, TR-012 | T027, T040, T041 |
| F18 | AUTO besitzt ohne qualifizierten Benchmark keine objektive Qualitätsordnung | FR-004, FR-005, RR-003, RR-004 | T002, T038, T039 |
| F19 | Benchmark nach Analyseintegration kommt zu spät | FR-004, FR-005, FR-009, RR-003, RR-004 | T002, T007, T038 |
| F20 | Dateiübernahme braucht Transportvertrag, Volumegrenzen und Vertrauensprüfung | FR-010, FR-011, OR-005, OR-007, OR-008, TR-010, TR-011, TR-012 | T017, T018, T019 |
| F21 | Sicherheitsgrenze endet nicht bei erlaubten Workflow-Metadaten | OR-005, TR-001, TR-011 | T006, T017 |
| F22 | Ausführungsort und PB-Scope von separater ComfyUI-Konfiguration trennen | OR-001, OR-003, OR-005, RR-005, RR-006, TR-001 | T001, T006, T015 |
| F23 | Seed und Prompt garantieren keine bitidentische Wiederholung | FR-003, FR-009, FR-010, FR-011, FR-012, OR-008, RR-004, TR-003, TR-010 | T005, T007, T019, T027 |
| F24 | QC ist erforderlich, aber technische QC allein qualifiziert keinen Director-Clip | FR-004, FR-005, FR-009, FR-010, FR-014, OR-007, RR-002, RR-003, RR-004, RR-005, TR-012 | T002, T018, T026, T038, T040 |
| F25 | Neuer Output darf keine bereits akzeptierte Analyse still überschreiben | FR-004, FR-005, RR-003, TR-005, TR-007 | T009, T031, T038 |
| F26 | Cacheidentität ist größer als Datei/Modell/Workflowname | FR-006, FR-007, RR-003, TR-005, TR-006, TR-007, TR-012 | T008, T009, T033 |
| F27 | Framerate, Dauer und Schnittpunkte benötigen rationale Zeitrechnung | FR-003, FR-012, FR-015, OR-003, OR-007, RR-005, TR-003, TR-005, TR-006, TR-011, TR-012 | T005, T008, T018, T029, T030, T041 |
| F28 | UI-Fortschritt darf weder Ausführung noch Importabschluss vortäuschen | FR-002, FR-003, FR-009, FR-013, FR-016, OR-006, TR-002 | T022, T023, T024, T025 |
| F29 | „Rollback ohne DB-Migration“ ist kein allgemeiner Schemarollback | OR-004, RR-001, RR-002, TR-006, TR-008, TR-009 | T011, T021, T037 |
| F30 | Settings und Fähigkeiten benötigen eindeutige Eigentümer und Refreshpolicy | FR-001, FR-002, FR-004, FR-016, OR-006, RR-003, TR-002 | T003, T022, T023, T039 |
| F31 | Feedbacklernen kann Selbstbestätigung statt Qualität lernen | FR-016, RR-003 | T042 |
| F32 | Langform braucht Budget, Admission Control und Aufbewahrungsregeln | FR-015, OR-001, OR-003, OR-008, RR-001, RR-005, TR-012 | T015, T043, T041 |
| F33 | Revisionsänderungen und Abhängigkeiten brauchen Invalidierung statt stiller Mutation | FR-003, FR-009, FR-011, FR-012, FR-014, OR-004, RR-002, TR-003, TR-008, TR-009, TR-012 | T005, T010, T027, T040 |
| F34 | Abnahmeanforderungen und SDD-Artefakte fehlen für tatsächliche Implementierung | RR-005, RR-006, TR-001 | T001, T045 |
| F35 | Begriff „Render Queue“ vermischt Generierung und finalen Export | FR-013, FR-016, OR-006 | T025 |
| F36 | Statuszahlen im Plan sind Illustrationen, keine Baseline | FR-002, FR-004, FR-005, FR-013, FR-016, OR-006, RR-003, RR-004, TR-004 | T002, T004, T025, T038 |
| F37 | Fehlende Semantik ist kein Beweis fehlender Libraryabdeckung | FR-004, FR-005, FR-014, RR-002, RR-003, TR-012 | T038, T040 |
| F38 | Pfadidentität und Generierungsidentität dürfen nicht zusammenfallen | FR-009, FR-010, FR-011, FR-012, OR-008, RR-001, TR-008, TR-009, TR-010 | T011, T019, T027 |
| F39 | Whole-clip und Segmentvektoren benötigen verschiedene Identitäten | RR-001, RR-002, TR-006, TR-010 | T020, T037 |
| F40 | Cache-, Adapter- und Pacingvalidierung brauchen dieselbe fachliche Strenge | FR-005, RR-003, TR-005, TR-006, TR-007, TR-012 | T008, T009, T031 |

## Vollständige Dispositionen

### F01 — Unabhängige Comfy-Nutzung benötigt gemeinsamen Admissionvertrag

**Verbindliche Planänderung:** Zwei explizite Betriebsmodi: `observed_shared` bietet Wartelogik und Warnungen, keine Exklusivgarantie; `managed_exclusive` benötigt einen kooperierenden Comfy-seitigen Admission-Gate für **alle** GPU-Aufträge derselben Maschine. Fremde LM-Studio/Hermes-Last bleibt gesondert zu koordinieren. Ohne Gate werden harte Garantien aus dem Plan gestrichen.

**Zuordnung:** T015, T016; OR-001, OR-002, OR-003.

**Abnahme / falsifizierbarer Test:** Manuellen Job zwischen PB-Probe und PB-Start starten; entweder serverseitig abweisen/warten oder ehrlich Shared-Modus melden. Keinen fremden Job abbrechen/entladen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F02 — Verlust der Submit-Antwort kann doppelte Ausführung verursachen

**Verbindliche Planänderung:** Durable Submit-Outbox, Attempt-ID, Payloadhash, persistierter Status `submission_unknown`; vor Wiederholung Queue/History/Receipt/Outputmanifest abgleichen. Bei nicht entscheidbarem Zustand kein automatisches erneutes Rechnen. Genau-einmaliger Import ist mit Unique-Constraint erreichbar; genau-einmalige entfernte Ausführung benötigt zusätzlichen Serververtrag.

**Zuordnung:** T012, T013; FR-013, OR-003, OR-004, RR-002, TR-009.

**Abnahme / falsifizierbarer Test:** Verbindung nach serverseitigem Accept gezielt verlieren; PB-Neustart darf keinen zweiten Submit und keinen zweiten Medienimport auslösen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F03 — Fertigmeldung ohne Importtransaktion gefährdet Katalog und Medienreferenzen

**Verbindliche Planänderung:** Eindeutige Staging-Datei pro Attempt, vollständige QC, Contenthash, atomare Veröffentlichung auf demselben Volume, DB-Ingest-Receipt und reparierbare Vektoroperation. Neue Dateien/Manifeste in bestehende Recovery-Owner-Inventare aufnehmen. `ready` erst nach den für diesen Workflow verbindlichen Stufen.

**Zuordnung:** T017, T018, T019, T020, T021, T026; FR-009, FR-010, FR-011, OR-004, OR-005, OR-007, OR-008, RR-001, RR-002, RR-004, RR-005, TR-006, TR-010, TR-011, TR-012.

**Abnahme / falsifizierbarer Test:** Crash an jeder Commitgrenze; nach Restart genau ein gültiger Clip oder klarer reparierbarer/quarantänisierter Zustand. Keine dangling Timeline-ID.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F04 — Austauschbare Embeddings sind ohne gemeinsamen semantischen Raum nicht austauschbar

**Verbindliche Planänderung:** Phase 1 übernimmt nur den bestehenden registrierten SigLIP-Raum einschließlich Processor-/Normalisierungsidentität. Andere Encoder zunächst Benchmarks/Quarantäne. Spätere Raumwechsel brauchen getrennte Namespaces und Mappingmigration oder vollständig validiertes Re-Embedding; kein Padding/Truncation als Reparatur.

**Zuordnung:** T008, T020, T037; RR-001, RR-002, TR-005, TR-006, TR-010, TR-012.

**Abnahme / falsifizierbarer Test:** Zwei verschiedene Encoder gleicher Dimension müssen abgewiesen oder getrennt geroutet werden; bestehende Suche bleibt unverändert.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F05 — ROCm-Bereichsentscheidung fehlte bei Erstprüfung; inzwischen geklärt

**Verbindliche Planänderung:** D01 ist bestätigt: ComfyUI externe AMD-/ROCm-Ausnahme, PB-interne ONNX-/GPU-Pfade DirectML. Policy-/Deploychecks exakt darauf binden; keine erneute Grundsatzfrage.

**Zuordnung:** T001, T006, T007; FR-009, OR-005, RR-004, RR-005, RR-006, TR-001.

**Abnahme / falsifizierbarer Test:** Deployment-Check klassifiziert jede Laufzeit nach explizitem Policy-Scope; ungeklärte Ausführung bleibt gesperrt.

**Status:** Governanceentscheidung bestätigt; technische Checks noch offen.

### F06 — Falsche Comfy-Installation kann Discovery und Quellenprüfung entwerten

**Verbindliche Planänderung:** Persistierte `server_id`, Endpoint, Transportmodus, aktive Version, Discovery-Fingerprint, optionale lokale Source-Zuordnung. Bei mehreren Kandidaten Auswahl statt Port-Hopping. Sourcepfad niemals aus alter Notiz übernehmen.

**Zuordnung:** T003, T004; FR-001, FR-002, TR-002, TR-004.

**Abnahme / falsifizierbarer Test:** Zwei lokale Server mit unterschiedlichen Nodes/Modellen; ausgewählter Workflow darf nur gegen den gebundenen Server validiert und ausgeführt werden.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F07 — Abbruch, Queue-Clear und Speicherfreigabe haben unterschiedliche Reichweite

**Verbindliche Planänderung:** Nur eigene IDs mit bevorzugtem `/api/jobs/{id}/cancel`; fallback nur versiongeprüft und ownership-sicher. Kein Queue-Clear, History-Clear oder globaler Interrupt durch PB. `/free` ausschließlich nach ausdrücklichem Instanz-/Ressourcenvertrag; Abschluss und Telemetrie abwarten.

**Zuordnung:** T014, T015, T016; FR-013, OR-001, OR-002, OR-003, RR-002.

**Abnahme / falsifizierbarer Test:** Fremder Job läuft, PB-Job wartet: PB-Cancel entfernt ausschließlich PB-Job. Cancel gegen inzwischen abgeschlossene ID trifft keinen Nachfolgejob.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F08 — Pause/Resume benötigt präzise operative Semantik

**Bestätigte O02-Policy:** `pause` stoppt neue Dispatches; laufender Shot darf fertig werden. Nach Restart validierte Outputs übernehmen, ungeklärte Attempts abgleichen. Echte Mid-Workflow-Resume nur capability-spezifisch mit Checkpointhash/Versionsbindung.

**Zuordnung:** T010, T014, T021, T041; FR-013, FR-015, OR-002, OR-003, OR-004, RR-001, RR-002, RR-005, TR-008, TR-009, TR-012.

**Abnahme / falsifizierbarer Test:** Bei 342 fertigen Shots und fehlendem Shot 17 nicht blind bei Index 343 beginnen; alle offenen Abhängigkeiten/Receipts prüfen. Bereits veröffentlichte Outputs nicht regenerieren.

**Status:** O02-Policy am 2026-10-13 bestätigt; keine technische Umsetzung oder Abnahme.

### F09 — Projektwechsel kann verspätete Ergebnisse in falsches Projekt schreiben

**Verbindliche Planänderung:** Dauerhafte Jobbindung an Projekt-UUID/Root, Sourcehash, Shotplanrevision; niemals beim Callback erneut `current_project` als Eigentümer verwenden. In-memory Epoch nicht als nach Restart gültige Identität persistieren. Ergebnis nach Wechsel sicher stagen und erst im gültigen Projektkontext committen.

**Zuordnung:** T010, T019, T021, T040; FR-010, FR-011, FR-014, OR-004, OR-008, RR-001, RR-002, TR-008, TR-009, TR-010, TR-012.

**Abnahme / falsifizierbarer Test:** Auftrag in A, Wechsel nach B, Output für A: B-Katalog/Timeline bleiben unverändert; A-Auftrag bleibt erreichbar.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F10 — Bestehende RenderQueue ist Vorlage, kein fertiger externer Jobmanager

**Verbindliche Planänderung:** CAS-/Repository-/Dedupe-Patterns wiederverwenden; Render-Fachmodell unverändert lassen. Eigene typisierte externe Attempts mit `submission_unknown`, Remote-Receipt und Importsaga ergänzen. Gemeinsame Queue-Ansicht darf mehrere Fachqueues aggregieren.

**Zuordnung:** T010, T011, T012; FR-013, OR-003, OR-004, RR-001, TR-008, TR-009.

**Abnahme / falsifizierbarer Test:** Interrupted-Comfy-Attempt wird nicht wie ein sicher neu startbarer lokaler FFmpeg-Job blind wiederholt.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F11 — Recovery-Inventar und Zombie-Watcher fehlen im Integrationsplan

**Verbindliche Planänderung:** Aktive externe Arbeit und dauerhafte pending commits in Lifespan/Owner-Lease/Idle-Policy berücksichtigen. Snapshot darf nicht auf fremde Netzwerkjobs warten; lokale Commits unter Recovery-Barrier, externe Zustände dauerhaft als reconciliable speichern. Neue Quarantäne-/Jobdateien inventarisieren.

**Zuordnung:** T021; OR-004, RR-001, RR-002.

**Abnahme / falsifizierbarer Test:** WPF schließen, Comfy-Job läuft: PB verhält sich entsprechend dokumentierter Detach-/Drain-Policy; Restart stellt keine abgeschlossene neue Generation unbemerkt auf alte Jobzustände zurück.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F12 — Resultschema braucht Einheiten, Zeitbasis und Herkunft pro Feld/Stufe

**Verbindliche Planänderung:** ProviderResult-Envelope plus typisierte Stagepayloads, rationale Zeitbasis, Offset, Sample-/Hoprate, Mess-/Ableitungsstatus, Sourcehash, Adapter-/Model-/Workflowidentität. Validierung von Reihenfolge, Dauergrenzen, finiten Zahlen und Einheiten vor Persistenz.

**Zuordnung:** T008, T031, T032, T033, T034, T035, T036; FR-005, FR-006, FR-007, FR-008, OR-007, RR-003, TR-005, TR-006, TR-007, TR-012.

**Abnahme / falsifizierbarer Test:** Millisekunden als Sekunden, lokale Chunkzeit als globale Zeit, NaN-Motion und zu lange Kurven müssen klar abgewiesen werden; leere valide Beatliste bleibt von „unavailable“ unterscheidbar.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F13 — Workflow-JSON ist nicht gleich ausführbarer API-Prompt

**Verbindliche Planänderung:** API-Prompt als kanonisches Ausführungsartefakt; UI-Graph optional zum Bearbeiten. Semantisches Mapping außerhalb des Graphs auf konkrete Node-ID/Inputslot der **gepinnten** Revision. Node-IDs dürfen technische Adressen sein, aber keine globale Bedeutung besitzen. Kein Mapping über übersetzbare Titel.

**Zuordnung:** T005; FR-003, TR-003.

**Abnahme / falsifizierbarer Test:** UI-Graph darf nicht versehentlich als API-Prompt eingereiht werden; geänderte IDs oder Widgetlayouts invalidieren betroffene Mappings verständlich.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F14 — Discovery beweist weder Modellhash noch Custom-Node-Version noch erfolgreiche Ausführung

**Verbindliche Planänderung:** Vier getrennte Zustände: entdeckt, statisch kompatibel, Smoke bestanden, für Profil qualifiziert. Paket-/Modellmanifest lokal oder über optionalen Inspector; bei unbekanntem Hash `identity_unverified`. Modellrolle plus gesamter Bundlehash statt einzelner Modellname. Fehlerbehebung zeigt echten Loader-/Inputbedarf.

**Zuordnung:** T004, T005, T007; FR-002, FR-003, FR-009, RR-004, TR-003, TR-004.

**Abnahme / falsifizierbarer Test:** Zwei Modelle gleichen Dateinamens mit anderem Inhalt; Provider darf nicht selben Provenance-/Cachekey erhalten. Node vorhanden, Modell defekt: Status ist nicht „BEREIT“.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F15 — Beliebige zukünftige Nodes brauchen adapterfähige Outputverträge

**Verbindliche Planänderung:** Versionierter ResultAdapter-Katalog für `analysis`, `media_file`, `embedding`, `stems`, `checkpoint`. Manifest wählt registrierten Adapter; Metadaten führen keinen beliebigen Python-/Shellcode aus. Neue Semantik benötigt neuen Adapter und Tests, keinen Director-Neubau.

**Zuordnung:** T005, T008; FR-003, TR-003, TR-005, TR-006, TR-012.

**Abnahme / falsifizierbarer Test:** Unbekannte Outputstruktur wird `unsupported_output_contract`, nicht automatisch „completed“ oder blind importiert.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F16 — Longform erfordert begrenzte Arbeitsmengen auch innerhalb einzelner Nodes

**Verbindliche Planänderung:** Clip-/Chunkgrenzen, Overlap, Offset, Dedup, Peak-RAM-/VRAM-Limits, Download-/Decoded-Bytebudgets pro Workflow. Reshot erhält begrenzten Source-Ausschnitt mit Handles. Drei Stunden Mastervideo niemals ungeprüft an Full-Decode-Node übergeben.

**Zuordnung:** T017, T018, T030, T034, T041; FR-006, FR-012, FR-015, OR-003, OR-005, OR-007, RR-003, RR-005, TR-005, TR-011, TR-012.

**Abnahme / falsifizierbarer Test:** Gleicher Workflow auf kurzen und langen Quellen; Peak-Speicher muss gemäß gebundenem Arbeitsfenster statt linear mit gesamter Dauer wachsen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F17 — Generierungs-Shot und Timeline-Cut sind unterschiedliche Einheiten

**Verbindliche Planänderung:** Unveränderlicher Shot-/Assetplan mit Seedstrategie, Referenzabhängigkeiten, Style/Character-Bindung und Handles; Timeline-Cuts referenzieren Teilbereiche dieser Assets. Abhängigkeits-DAG für First/Last-Frame-/Continuations; parallele Ausführung nur bei erfüllten Abhängigkeiten.

**Zuordnung:** T027, T040, T041; FR-009, FR-011, FR-012, FR-014, FR-015, OR-003, RR-002, RR-005, TR-012.

**Abnahme / falsifizierbarer Test:** Umordnung/Retry ändert weder bereitgestellte Seeds noch bereits bestätigte Assetzuordnung. Nach Planänderung werden betroffene Jobs `obsolete`, nicht still auf neue Cuts angewendet.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F18 — AUTO besitzt ohne qualifizierten Benchmark keine objektive Qualitätsordnung

**Verbindliche Planänderung:** Native Baseline und Holdout vor Providerablösung; feste Quality-/Zeit-/Memory-Gates, danach deterministische Auswahl mit SelectionReceipt und sichtbarem Fallbackgrund. Unqualifizierte Provider nur manuell/experimentell. Stochastic Generationcache nur mit explizitem Reuseziel.

**Zuordnung:** T002, T038, T039; FR-004, FR-005, RR-003, RR-004.

**Abnahme / falsifizierbarer Test:** Besserer validierter Provider fällt aus: kein stiller minderwertiger Ersatz; `waiting_for_provider` oder ausdrücklich genehmigtes Degrade mit Receipt.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F19 — Benchmark nach Analyseintegration kommt zu spät

**Verbindliche Planänderung:** Phase 0 definiert Referenzen/Grundmetriken; Phase 1 erstellt Mini-Smoke; jede Providerphase vergleicht Native/Comfy auf identischen Quellen/Versionen. Holdouts nicht zur Parameteroptimierung verwenden; Ergebnisqualität und Betriebssicherheit getrennt bewerten.

**Zuordnung:** T002, T007, T038; FR-004, FR-005, FR-009, RR-003, RR-004.

**Abnahme / falsifizierbarer Test:** Fachliche Regression in einer schwierigen Kohorte darf nicht durch Gesamtdurchschnitt oder schnelleres Laufzeitergebnis verdeckt werden.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F20 — Dateiübernahme braucht Transportvertrag, Volumegrenzen und Vertrauensprüfung

**Verbindliche Planänderung:** Local-reference nur mit expliziter Rootfreigabe und kompatiblem Loader; Remote-stream nur über verifizierten Media-Transportadapter. Pfadcontainment nach Resolve, Reparse-/Junction-/UNC-Prüfung, Größen-/Format-/Decodebudget, Hashprüfung, quarantänisierter Download, stabile Destination. Cross-Volume-Move ist nicht atomar: erst zur Destination stagen, dann veröffentlichen. Originale bleiben read-only.

**Zuordnung:** T017, T018, T019; FR-010, FR-011, OR-005, OR-007, OR-008, TR-010, TR-011, TR-012.

**Abnahme / falsifizierbarer Test:** Path traversal, Junction-Ausbruch, unvollständige Datei, fremde URL, riesiger Decoderinput, Output auf E: nach Import verschwunden: kein beschädigter veröffentlichter Clip.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F21 — Sicherheitsgrenze endet nicht bei erlaubten Workflow-Metadaten

**Verbindliche Planänderung:** Vertrauenswürdige/gepinnte Workflow- und Node-Pakete, lokale/remote Endpointallowlist, keine Umleitungen auf ungeprüfte Hosts, Netzwerk-/Ausführungsdeklaration, eingeschränkte Rootrechte/Prozessidentität soweit erforderlich. „Comfy erhält keine DB-Schreibberechtigung“ entweder als technische ACL-/Account-Grenze implementieren oder ehrlich nur als Integrationsvertrag formulieren.

**Zuordnung:** T006, T017; OR-005, TR-001, TR-011.

**Abnahme / falsifizierbarer Test:** Workflow mit ungenehmigtem externem Dienst-/Download-/Commandnode wird vor Submit gesperrt; Logging redigiert verschachtelte Secrets und Payloads.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F22 — Ausführungsort und PB-Scope von separater ComfyUI-Konfiguration trennen

**Verbindliche Planänderung:** D02 wurde am 2026-10-13 präzisiert: PB plant ausschließlich lokale Profile. Externe Dienstekonfiguration liegt separat in ComfyUI; keine PB-Verwaltung, APIkeys, Kostensteuerung, Erweiterungstasks oder Folgefreigaben dafür. Historischer F22 bleibt nachvollziehbar, sein früherer Ausbauvorschlag ist gestrichen. Lokale Profilqualifikation und allgemeine Netzwerk-/Datensicherheit bleiben erforderlich.

**Zuordnung:** T001, T006, T015; OR-001, OR-003, OR-005, RR-005, RR-006, TR-001.

**Abnahme / falsifizierbarer Test:** PB-Schema, Settings, Taskgraph und Routing enthalten keine externe Dienstesteuerung; lokale Dispatch-/Retry-/Zeit-/Speicherbudgets begrenzen fehlende Shots. Separat in ComfyUI konfigurierte Funktionen erzeugen keine implizite PB-Qualifikation.

**Status:** Local-first-Scope bestätigt; technische Policy-/Budgetprüfung noch offen.

### F23 — Seed und Prompt garantieren keine bitidentische Wiederholung

**Verbindliche Planänderung:** Reproducibility-Level: `traceable`, `rerunnable`, `deterministic_verified`. Provenance bindet gerenderten Promptgraph, aufgelöste Zufallsseeds, alle Modell-/LoRA-/Processorhashes, Node-/Server-/Adapterrevisionen, Samplerparameter, Hardware-/Runtimeprofil, Input- und Outputhashes. Gewollte Variante erhält neuen Intent; Retry bleibt eigener Attempt mit dokumentierter Seedpolicy.

**Zuordnung:** T005, T007, T019, T027; FR-003, FR-009, FR-010, FR-011, FR-012, OR-008, RR-004, TR-003, TR-010.

**Abnahme / falsifizierbarer Test:** Gleicher Seed bei geänderter Modellrevision darf nicht als gleiche Generation oder byteidentischer Nachweis gelten. Reproduzierbarkeit nur nach Wiederholung auf gepinntem Profil behaupten.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F24 — QC ist erforderlich, aber technische QC allein qualifiziert keinen Director-Clip

**Verbindliche Planänderung:** Technische harte Gates, profilabhängige visuelle Signale und menschliche Freigabe für Golden-Set getrennt. `eligible_for_director` hängt an dokumentierter Mindestdaten-/Qualitätsregel; Partial Results bleiben sichtbar. Ungenügende generierte Clips nicht automatisch als Trainingswahrheit nutzen.

**Zuordnung:** T002, T018, T026, T038, T040; FR-004, FR-005, FR-009, FR-010, FR-014, OR-007, RR-002, RR-003, RR-004, RR-005, TR-012.

**Abnahme / falsifizierbarer Test:** Technisch korrekter, semantisch falscher Clip bleibt in Bibliothek sichtbar, aber je Profil ungeeignet; bewusst schwarzer Übergang folgt expliziter Ausnahme statt Fake-„Artefakt“.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F25 — Neuer Output darf keine bereits akzeptierte Analyse still überschreiben

**Verbindliche Planänderung:** Immutable Resultrecords; aktive Stageauswahl mit Versions-/Kontextprüfung; Degrade/Partial schreibt nur definierte Stages. Rollback wechselt Pointer, verliert keine neue Provenance.

**Zuordnung:** T009, T031, T038; FR-004, FR-005, RR-003, TR-005, TR-007.

**Abnahme / falsifizierbarer Test:** Benchmark mit schlechterem Ergebnis ändert weder produktives Pacing noch Cache des aktiven Providers.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F26 — Cacheidentität ist größer als Datei/Modell/Workflowname

**Verbindliche Planänderung:** Hash aus Sourceinhalt, Sourcebereich, Decoder-/Resampling-/Processorversion, API-Prompt + Manifest + ResultAdapter, vollständigem Modellbundle, aufgelösten Parametern/Seed und Resultschemaversion. Generation-Reuse und Analyse-Dedupe sind getrennte Regeln. Cacheentry erst nach Hash-/QCprüfung veröffentlicht.

**Zuordnung:** T008, T009, T033; FR-006, FR-007, RR-003, TR-005, TR-006, TR-007, TR-012.

**Abnahme / falsifizierbarer Test:** Verändertes Hopsize-/Chunkoverlap-/LoRA-Profil invalidiert Cache; umbenanntes identisches Medium kann korrekt dedupliziert werden.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F27 — Framerate, Dauer und Schnittpunkte benötigen rationale Zeitrechnung

**Verbindliche Planänderung:** `fps_num/fps_den`, exakte Frames/PTS und Source-/Timelinezeit trennen; Endpunktkonvention definieren. Workflowconstraints wie Länge `n*k+c` validieren; generierten Überhang mit Handles trimmen. Kein Float-Runden pro Shot, das über Stunden driftet. Masteraudio explizit einzige Exportaudioquelle; generiertes Shot-Audio standardmäßig deaktiviert.

**Zuordnung:** T005, T008, T018, T029, T030, T041; FR-003, FR-012, FR-015, OR-003, OR-007, RR-005, TR-003, TR-005, TR-006, TR-011, TR-012.

**Abnahme / falsifizierbarer Test:** 29.97/23.976-FPS-Quellen über lange Timeline behalten A/V-Sync innerhalb freigegebener Grenze; Cut-Wunsch darf nicht unbemerkt Modellframelimit verletzen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F28 — UI-Fortschritt darf weder Ausführung noch Importabschluss vortäuschen

**Verbindliche Planänderung:** SSE für Anzeige, Jobstore für Wahrheit. Phasenstatus getrennt: queued/running/QC/import/analyse/ready. Unbekannter Fortschritt bleibt indeterminate. Nach Reconnect Jobliste abrufen; UI filtern nach Projekt und Jobrevision. Keine zusätzliche WPF-WebSocket-Wahrheit.

**Zuordnung:** T022, T023, T024, T025; FR-002, FR-003, FR-009, FR-013, FR-016, OR-006, TR-002.

**Abnahme / falsifizierbarer Test:** Sampling 100 % bei laufendem Decode/Import zeigt keinen „bereit“-Clip. Eventverlust wird durch Snapshot korrigiert.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F29 — „Rollback ohne DB-Migration“ ist kein allgemeiner Schemarollback

**Verbindliche Planänderung:** Providerumschalten ohne weitere Migration ermöglichen; davon getrennt neue persistente Jobs/Provenance additiv migrieren. Unterstützte Reader-/Writer-Versionen, fehlende Felddefaults und Umgang mit unbekannten Feldern dokumentieren. Alte Appversion darf neue Provenance nicht still verwerfen. Restore nur konsistente Generation, niemals DB allein zurückspielen.

**Zuordnung:** T011, T021, T037; OR-004, RR-001, RR-002, TR-006, TR-008, TR-009.

**Abnahme / falsifizierbarer Test:** Neuer DB-Stand mit älterem unterstütztem Reader bewahrt neue Records oder wird verständlich fail-closed abgewiesen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F30 — Settings und Fähigkeiten benötigen eindeutige Eigentümer und Refreshpolicy

**Verbindliche Planänderung:** Backend autoritativ für Endpoint/Workflow-/Providerpolicy; WPF speichert Darstellung. Discovery TTL, invalidierbare Generation und Revalidate vor Submit. Kein `comfyui` in vorhandenes `ai.provider` einschmuggeln.

**Zuordnung:** T003, T022, T023, T039; FR-001, FR-002, FR-004, FR-016, OR-006, RR-003, TR-002.

**Abnahme / falsifizierbarer Test:** Endpointwechsel während Job A läuft ändert nicht A-Serverbindung; nächste Jobs verwenden neue Konfiguration. Offline-Provider blockiert keinen Appstart.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F31 — Feedbacklernen kann Selbstbestätigung statt Qualität lernen

**Verbindliche Planänderung:** Menschliche Bewertungen von automatischer QC trennen; Impressionen, Auswahlgrund und Exposurebias speichern. Holdoutbewertungen nicht als Training wiederverwenden. Workflow-/Promptversionen und Stilkontext mitführen; keine vermeintlich „guten Seeds“ global generalisieren.

**Zuordnung:** T042; FR-016, RR-003.

**Abnahme / falsifizierbarer Test:** Anbieter, der mehr Clips erzeugt, steigt nicht allein wegen höherer absoluten Positivzahl im Ranking.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F32 — Langform braucht Budget, Admission Control und Aufbewahrungsregeln

**Verbindliche Planänderung:** Projektbudget für GPUzeit, RAM, Disk, Batchjobs, Varianten und Retries; nur begrenztes Dispatchfenster. Diskreserven vor Outputdecode/-download. Pin verwendeter Assets, Retention temporärer Latents/Stems/Diagnosen, keine Löschung verwendeter Varianten. ETA aus gemessenen vergleichbaren Profilen, ohne erfundene Stundenangaben.

**Zuordnung:** T015, T043, T041; FR-015, OR-001, OR-003, OR-008, RR-001, RR-005, TR-012.

**Abnahme / falsifizierbarer Test:** Disk voll oder Budget erreicht stoppt neue Dispatches sauber; akzeptierte Timeline bleibt nutzbar.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F33 — Revisionsänderungen und Abhängigkeiten brauchen Invalidierung statt stiller Mutation

**Verbindliche Planänderung:** Jobs frieren Workflow-/Manifest-/Referenz-/Shotplanrevision ein. Update erstellt neue Revision, alte Jobs bleiben reproduzierbar. Retake/Upscale verändert nie Elternasset; Timelineänderung separat bestätigen. Dependency-Ausfall blockiert Nachfolger.

**Zuordnung:** T005, T010, T027, T040; FR-003, FR-009, FR-011, FR-012, FR-014, OR-004, RR-002, TR-003, TR-008, TR-009, TR-012.

**Abnahme / falsifizierbarer Test:** Workflowedit während 720-Shot-Batch bewirkt keinen Mix mehrerer unmarkierter Versionen; alte Ergebnisse sind über eigene Provenance auffindbar.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F34 — Abnahmeanforderungen und SDD-Artefakte fehlen für tatsächliche Implementierung

**Verbindliche Planänderung:** Dieser Review bleibt Audit. Vor Lieferung Featureworkspace mit `spec.md → clarify → plan.md → tasks.md`; jedes Paket erhält Abhängigkeiten, Dateien, Tests, Akzeptanz und Rollback. `.completed`/`.qc-passed` nur nach tatsächlicher Implementierung/QC. Der angehängte Entwurf ist Vorschlag, kein künstlich passender Marker.

**Zuordnung:** T001, T045; RR-005, RR-006, TR-001.

**Abnahme / falsifizierbarer Test:** Kein Codingagent beginnt eine Implementierungsphase ohne freigegebenen Scope und bestehende Pflichtartefakte.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F35 — Begriff „Render Queue“ vermischt Generierung und finalen Export

**Verbindliche Planänderung:** Gemeinsame Produktionsjobansicht mit Typfiltern, separaten Fachzuständen und eindeutiger „Finalexport“-Aktion. Queueposition des Servers nicht als garantierte ETA darstellen.

**Zuordnung:** T025; FR-013, FR-016, OR-006.

**Abnahme / falsifizierbarer Test:** Nutzer erkennt, ob „completed“ einen generierten Clip, eine Analyse oder finalen Export bezeichnet.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F36 — Statuszahlen im Plan sind Illustrationen, keine Baseline

**Verbindliche Planänderung:** Zahlen wie 842 Nodes, 600 Shots, 342/720 und 139.70 BPM ausdrücklich als Beispiele belassen. Reale Werte aus Jobstore/Discovery und autorisierten Referenzen anzeigen.

**Zuordnung:** T002, T004, T025, T038; FR-002, FR-004, FR-005, FR-013, FR-016, OR-006, RR-003, RR-004, TR-004.

**Abnahme / falsifizierbarer Test:** Diagnoseexport enthält Messzeit, Serverbindung und Beweisniveau; kein illustrative Zahl wird als getestete Produktfähigkeit übernommen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F37 — Fehlende Semantik ist kein Beweis fehlender Libraryabdeckung

**Verbindliche Planänderung:** Eigene `CoverageDecision` mit `sufficient / insufficient / unknown`, Eignungsgründen und kalibriertem Profil; Unknown zuerst analysieren oder Nutzerentscheidung. Dauer/Handles/Loop/Retiming/Style/Kontinuität separat prüfen.

**Zuordnung:** T038, T040; FR-004, FR-005, FR-014, RR-002, RR-003, TR-012.

**Abnahme / falsifizierbarer Test:** Gute Library mit fehlenden Embeddings löst keine ungeprüfte 180-Shot-Generation aus; klare Unterdeckung auf gelabeltem Holdout dagegen schon innerhalb Budget.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F38 — Pfadidentität und Generierungsidentität dürfen nicht zusammenfallen

**Verbindliche Planänderung:** Immutable jobspezifische Outputnamen; Artifact-/Attempt-/Slotidentität und zusätzlicher Unique-Importclaim. Identische Bytes dürfen durch getrennte Provenancebeziehungen mehreren Intents zugeordnet werden; keine Hashglobalisierung ohne Produktregel.

**Zuordnung:** T011, T019, T027; FR-009, FR-010, FR-011, FR-012, OR-008, RR-001, TR-008, TR-009, TR-010.

**Abnahme / falsifizierbarer Test:** Zwei Varianten gleicher Outputbasename erzeugen getrennte unveränderte Artefakte; doppelter Callback desselben Attempts importiert genau einmal.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F39 — Whole-clip und Segmentvektoren benötigen verschiedene Identitäten

**Verbindliche Planänderung:** Granularität `asset / scene / window` plus Sourcebereich im Resultvertrag. Segmentindex erst mit passenden Mapping-/Dedupe-/Query-/Tombstoneänderungen, damit mehrere Segmentvektoren derselben Media-ID nicht als Dubletten entfernt werden.

**Zuordnung:** T020, T037; RR-001, RR-002, TR-006, TR-010.

**Abnahme / falsifizierbarer Test:** Zwei Szenen eines Clips behalten getrennte passende Treffer und werden weder bei Import noch Reanalyse zusammengeworfen.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

### F40 — Cache-, Adapter- und Pacingvalidierung brauchen dieselbe fachliche Strenge

**Verbindliche Planänderung:** Gemeinsamer semantischer Validator und immutable Analyse-Run-Identitäten; Stageabhängigkeiten auf konkrete Resultrevision binden. Ein Comfyadapter darf keine native Cacheidentität vortäuschen.

**Zuordnung:** T008, T009, T031; FR-005, RR-003, TR-005, TR-006, TR-007, TR-012.

**Abnahme / falsifizierbarer Test:** Negative BPM, inkonsistente Chunkzeiten oder falsche Sourcehashes dürfen über keinen der drei Übergabepfade als gültige Providerresultate in Pacing gelangen. Konkrete bestehende Fehlfreigabe wurde hier nicht ausgeführt.

**Status:** Im Plan geschlossen; Umsetzung/Abnahme NICHT durchgeführt.

## Alle 82 Originalabschnitte

Abschnitte werden nicht pauschal als funktional erfüllt markiert. Im Masterplan A–U stehen die jeweiligen Zielverträge; unten Paketzuordnung. §73 geforderte A–O-Deliverables sind vollständig in Masterplan A–O plus Q/S/T und Task-/Traceabilitydateien enthalten.

| Original | Titel | Aufgaben / spätere Gates |
|---|---|---|
| 0 | AUFTRAG UND ARBEITSMODUS | T001, T045 |
| 1 | HAUPTZIEL DES UMBAUS | T002, T005, T008, T038, T039 |
| 2 | GRUNDARCHITEKTUR | T017, T018, T019, T020, T021, T026, T027, T040, T041 |
| 3 | STRIKTE TRENNUNG PB-STUDIO / COMFYUI | T001, T006, T007, T015, T016, T017 |
| 4 | COMFYUI BRIDGE | T005, T008, T010, T011, T012 |
| 5 | VERBINDUNG ZU COMFYUI | T003, T004, T005, T007, T014, T015, T016 |
| 6 | COMFYUI STATUS IN PB-STUDIO | T002, T004, T005, T007, T022, T023, T024, T025, T038 |
| 7 | WORKFLOW-REGISTRY | T004, T005, T007, T008 |
| 8 | WORKFLOW-PARAMETER | T005, T008, T018, T029, T030, T041 |
| 9 | PROVIDER-ARCHITEKTUR | T002, T008, T020, T031, T032, T033, T034, T035, T036, T037, T038, T039 |
| 10 | AUTO-PROVIDER | T002, T003, T022, T023, T038, T039 |
| 11 | WICHTIGE REGEL FÜR BESTEHENDEN CODE | T002, T007, T038 |
| 12 | VERGLEICHSMODUS | T002, T007, T009, T031, T038, T039 |
| 13 | AUDIOANALYSE | T008, T009, T017, T018, T030, T031, T032, T033, T034, T035, T036, T041 |
| 14 | STEM SEPARATION | T008, T009, T033 |
| 15 | VIDEOANALYSE | T008, T020, T031, T032, T033, T034, T035, T036, T037 |
| 16 | VIDEO-GENERIERUNG | T001, T004, T005, T006, T007, T015, T026, T027 |
| 17 | GENERIERTE CLIPS | T002, T010, T011, T017, T018, T019, T020, T021, T026, T027, T038, T040 |
| 18 | PROVENANCE FÜR GENERIERTE CLIPS | T005, T007, T011, T019, T027 |
| 19 | PB-STUDIO DIRECTOR | T027, T038, T040, T041 |
| 20 | CLIP-ENTSCHEIDUNG | T002, T018, T026, T038, T040 |
| 21 | LANGFORM-DJ-VIDEOS | T005, T008, T015, T017, T018, T027, T029, T030, T034, T040, T041, T043 |
| 22 | JOBSYSTEM | T010, T011, T012, T013, T014 |
| 23 | PAUSE / RESUME / RECOVERY | T010, T012, T013, T014, T021, T041 |
| 24 | RENDER QUEUE | T010, T014, T015, T016, T021, T025, T041 |
| 25 | LIVE-FORTSCHRITT | T022, T023, T024, T025 |
| 26 | GPU-KOORDINATION | T014, T015, T016 |
| 27 | AMD-ZIELSYSTEM | T001, T006, T007 |
| 28 | MODELLVERWALTUNG | T003, T004, T005, T007 |
| 29 | NODE-DISCOVERY | T004, T005, T006, T007, T017 |
| 30 | WORKFLOW-KOMPATIBILITÄT | T004, T005, T007, T010, T027, T040 |
| 31 | AUDIO-/VIDEO-DATEIÜBERGABE | T017, T018, T019 |
| 32 | STANDARD RESULT SCHEMA | T008, T009, T020, T031, T032, T033, T034, T035, T036, T037 |
| 33 | PARTIAL RESULTS | T002, T008, T009, T018, T026, T031, T032, T033, T034, T035, T036, T038, T040 |
| 34 | DATENBANK | T006, T011, T017, T018, T019, T020, T021, T026, T037, T043 |
| 35 | FAISS | T008, T020, T037 |
| 36 | MEDIENBIBLIOTHEK | T011, T019, T025, T027 |
| 37 | WORKFLOW-LIBRARY UI | T022, T023, T024, T025 |
| 38 | WORKFLOW EDITING | T005, T024 |
| 39 | MANUELLE GENERIERUNG | T002, T018, T022, T023, T024, T025, T026, T038, T040 |
| 40 | AUTOMATISCHE GENERIERUNG | T001, T006, T015, T027, T038, T040, T041, T043 |
| 41 | VARIANTEN | T005, T007, T010, T011, T019, T027, T040 |
| 42 | RESHOT | T005, T008, T010, T017, T018, T027, T029, T030, T034, T040, T041 |
| 43 | UPSCALING | T005, T008, T010, T018, T027, T028, T029, T030, T040, T041 |
| 44 | FRAME INTERPOLATION | T005, T008, T010, T018, T027, T029, T030, T040, T041 |
| 45 | QUALITÄTSKONTROLLE | T002, T017, T018, T019, T020, T021, T026, T038, T040 |
| 46 | AUTOMATISCHER RETRY | T001, T006, T012, T013, T014, T015, T016 |
| 47 | DIRECTOR FEEDBACK LOOP | T042 |
| 48 | FEHLERTOLERANZ | T010, T017, T018, T019, T020, T021, T026, T040 |
| 49 | COMFYUI-AUSFALL | T003, T010, T014, T021, T022, T023, T039, T041 |
| 50 | UPDATE-SICHERHEIT | T004, T005, T007, T010, T019, T027, T040 |
| 51 | SICHERHEIT | T001, T006, T015, T017, T018, T019 |
| 52 | LOGGING | T005, T006, T007, T017, T019, T027 |
| 53 | DIAGNOSTIK | T004, T005, T007, T022, T023, T024, T025 |
| 54 | PB-STUDIO UI | T022, T023, T024, T025 |
| 55 | SETTINGS | T003, T022, T023, T039 |
| 56 | INSTALLATION | T001, T003, T004, T006, T007, T023 |
| 57 | SETUP-ASSISTENT | T003, T004, T005, T007, T044 |
| 58 | PERFORMANCE | T002, T007, T015, T017, T018, T030, T034, T038, T041, T043 |
| 59 | CACHE | T005, T007, T008, T009, T012, T013, T019, T027, T031, T033 |
| 60 | CONTENT HASHING | T008, T009, T011, T019, T027, T033 |
| 61 | KEINE DATENDUPLIKATION | T010, T011, T012, T017, T018, T019, T020, T021, T026 |
| 62 | FINALEXPORT | T005, T008, T018, T026, T029, T030, T041 |
| 63 | ARCHITEKTURPRINZIP | T005, T008, T027, T040, T041 |
| 64 | MIGRATION | T001, T002, T007, T038, T045 |
| 65 | VOR JEDEM ERSETZEN EINER PB-KOMPONENTE | T002, T007, T038, T039 |
| 66 | ROLLBACK | T009, T011, T021, T031, T037, T038 |
| 67 | TESTS | T001, T010, T012, T013, T017, T018, T019, T020, T021, T026, T040, T045 |
| 68 | EXISTIERENDE TESTS | T001, T045 |
| 69 | DOKUMENTATION | T001, T023, T044, T045 |
| 70 | ENTWICKLER-WORKFLOW | T005, T006, T008, T017, T024, T044 |
| 71 | ZUKUNFTSSICHERHEIT | T005, T008, T020, T027, T037 |
| 72 | ZENTRALE PRODUKTVISION | T027, T040, T041 |
| 73 | ERWARTETES ERGEBNIS DEINER PLANUNG | T001, T045 |
| 74 | ARBEITSPAKETE | T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012, T013, T014, T015, T016, T017, T018, T019, T020, T021, T022, T023, T024, T025, T026, T027, T028, T029, T030, T031, T032, T033, T034, T035, T036, T037, T038, T039, T040, T041, T042, T043, T044, T045 |
| 75 | KEINE SCHÄTZUNGEN OHNE GRUNDLAGE | T001, T002, T004, T025, T038 |
| 76 | QUELLEN UND FAKTEN | T001, T003, T004, T005, T007 |
| 77 | KEINE BLINDEN ANNAHMEN | T001, T002, T004, T005, T007, T025, T038 |
| 78 | ABSCHLUSSENTSCHEIDUNG | T001, T045 |
| 79 | NICHT VERHANDELBARE ANFORDERUNGEN | T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012, T013, T014, T015, T016, T017, T018, T019, T020, T021, T022, T023, T024, T025, T026, T027, T028, T029, T030, T031, T032, T033, T034, T035, T036, T037, T038, T039, T040, T041, T042, T043, T044, T045 |
| 80 | ENDZIEL | T002, T018, T026, T027, T038, T040, T041 |
| 81 | OBERSTES ARCHITEKTURPRINZIP | T001, T005, T008, T019, T027, T040, T041 |

## Requirements ohne versteckte Lieferung

| Requirement | Tasks |
|---|---|
| FR-001 | T003 |
| FR-002 | T003, T004, T023 |
| FR-003 | T005, T024 |
| FR-004 | T038, T039 |
| FR-005 | T002, T031, T032, T038 |
| FR-006 | T032, T033, T034 |
| FR-007 | T033 |
| FR-008 | T035, T036 |
| FR-009 | T007, T024, T026, T027 |
| FR-010 | T019, T026 |
| FR-011 | T019, T027 |
| FR-012 | T027, T028, T029, T030 |
| FR-013 | T012, T014, T025 |
| FR-014 | T040 |
| FR-015 | T041 |
| FR-016 | T023, T024, T025, T042, T044 |
| TR-001 | T001, T006 |
| TR-002 | T003, T022 |
| TR-003 | T005 |
| TR-004 | T004, T044 |
| TR-005 | T008, T031, T034, T035, T036 |
| TR-006 | T008, T020, T037 |
| TR-007 | T009, T031 |
| TR-008 | T010, T011 |
| TR-009 | T010, T011, T012, T013 |
| TR-010 | T019, T020 |
| TR-011 | T017, T030 |
| TR-012 | T008, T018, T028, T029, T030, T040, T041 |
| OR-001 | T015, T016 |
| OR-002 | T014, T016 |
| OR-003 | T012, T015, T041, T043 |
| OR-004 | T010, T013, T021 |
| OR-005 | T006, T017 |
| OR-006 | T022, T023, T025 |
| OR-007 | T018, T036 |
| OR-008 | T019, T043 |
| RR-001 | T011, T021, T037, T043 |
| RR-002 | T013, T014, T020, T021, T040 |
| RR-003 | T002, T009, T032, T033, T034, T035, T038, T039, T042 |
| RR-004 | T002, T007, T026 |
| RR-005 | T001, T026, T041, T045 |
| RR-006 | T001, T045 |

## Beweis- und Vollständigkeitsgrenzen

Dieses Mapping beweist Dokumentabdeckung, keine funktionierende Integration. Nicht jede Quellzeile fachlich komplett verifiziert; Hardware/GUI/Real-Media/Crashnachweise müssen später tatsächlich ausgeführt werden. Familienpakete T032–T036 gelten erst nach jeder gewählten Einzeliteration qualifiziert; unavailable/unverified sind keine Fake-PASS. Optionale Scopepakete und spätere Checkpoint-Specs ausdrücklich getrennt.


## Kommunikationspräzisierungen CM01–CM14

Verbindlich: [Kommunikationsvertrag](communication-contract.md). Quellbelege, Korrekturen und Taskzuordnung vollständig in [findings.json](communication-audit-2026-10-13/findings.json);32noch nicht ausgeführte Abnahmefälle W01–W32 im Vertrag. Diese zusätzliche Zuordnung ersetzt weder F01–F40 noch CC01–CC19. O03-Messwerte und O04-konkrete Änderungsfreigaben bleiben offen.

## Fachliche Gesamtgegenprüfung2026-10-13

Alle folgenden Korrekturen präzisieren bestehende Requirements; Produktabnahmen NOT RUN. Quellen/ursprüngliche Planzeilen: [Befundregister](full-plan-audit-2026-10-13/findings.json).

| Befund | Arbeitspakete | Requirements | Vertrag |
|---|---|---|---|
| FP01 | T031, T034 | FR-005, FR-006, RR-003, TR-005, TR-007 | Audiozeitachse bis zum tatsächlichen Pacingconsumer |
| FP02 | T009, T031 | FR-005, RR-003, TR-005, TR-007 | Capability-Composer für gruppierte Legacy-Audiostages |
| FP03 | T040 | FR-014, RR-002, TR-012 | Timeline-CAS an sämtliche Schreiber anschließen |
| FP04 | T040 | FR-014, RR-002, TR-012 | Feste UI-/Canvas-Anker in Coverage und Assetplan |
| FP05 | T040 | FR-014, RR-002, TR-012 | Coverage-Einstieg vor leerer Videolibrary-Sperre |
| FP06 | T009, T031 | FR-005, RR-003, TR-005, TR-007 | Pflichtcacheconsumer an aktive Run-/Vektoridentität binden |
| FP07 | T008, T031, T035 | FR-005, FR-008, RR-003, TR-005, TR-006, TR-007, TR-012 | Partielle native Captionstages verlustfrei normalisieren |
| FP08 | T011, T012, T013, T021 | FR-013, OR-003, OR-004, RR-001, RR-002, TR-008, TR-009 | Restorezaun verhindert erneuten Remoteversand |
| FP09 | T010, T011 | OR-004, RR-001, TR-008, TR-009 | Vorhandene kanonische Projekt-UUID wiederverwenden |
| FP10 | T015, T016 | OR-001, OR-002, OR-003 | Direkte Preview-/Render-GPU-Aufrufer in Admission aufnehmen |
| FP11 | T015, T016, T021 | OR-001, OR-002, OR-003, OR-004, RR-001, RR-002 | Leaseownership bis zum physischen Workerende |
| FP12 | T002, T007, T015 | FR-005, FR-009, OR-001, OR-003, RR-003, RR-004 | VRAM-Buchhaltung nicht als gemessenen Hardwarepeak qualifizieren |
| FP13 | T018, T026, T028, T029 | FR-009, FR-010, FR-012, OR-007, RR-004, RR-005, TR-012 | Technischen Farb-/Streamvertrag qualifizieren |
| FP14 | T010, T022, T024, T025 | FR-003, FR-009, FR-013, FR-016, OR-004, OR-006, TR-002, TR-008, TR-009 | DTO-Katalog und neuer Kommunikationsvertrag widersprechen sich |
| FP15 | T003, T022, T023 | FR-001, FR-002, FR-016, OR-006, TR-002 | Settings-CAS über Neustart, Diskfehler und Reloadrace |
| FP16 | T002, T038, T039, T042 | FR-004, FR-005, FR-016, RR-003, RR-004 | Holdout vom bereits vorhandenen Brainlernen isolieren |
| FP17 | T027, T030, T040 | FR-009, FR-011, FR-012, FR-014, RR-002, TR-011, TR-012 | Parent-Sourcezeit auf Child-lokale Derivatzeit abbilden |
| FP18 | T019, T020, T026, T031 | FR-005, FR-009, FR-010, FR-011, OR-008, RR-002, RR-004, RR-005, TR-005, TR-006, TR-007, TR-010 | Native-AnalysisRun-Producer vor MVP eindeutig zuweisen |

## Vollreviewrunde01

| Befund | Pakete | Status |
|---|---|---|
| L01 Bewusstes Warten auf Import oder Analyse fehlt | T010, T011, T019, T021, T022, T024, T025, T026 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |
| L02 Reshot-Endabnahme ohne T030-Vorgänger | T040 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |
| L03 Unbeaufsichtigtes G8 ohne Managedgate | T041 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |
| L04 Pflicht-Developer-Guide besitzt optionalen Owner | T044, T045 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |
| L05 Mutable Workflowaktivierung ohne CAS-Identität | T005, T022, T024 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |
| L06 Unknown kann belegte Nichtannahme nicht auflösen | T010, T012, T013, T014 | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |

## Vollreviewrunde03

L07 — Native-/Comfy-Ausführungsidentität und getrennte Medienherkunft. T008/T009/T020/T031; bestehende TR005/TR007/FR005. Plan korrigiert, erneuter Vollreview erforderlich; Produktabnahme NOT RUN.
