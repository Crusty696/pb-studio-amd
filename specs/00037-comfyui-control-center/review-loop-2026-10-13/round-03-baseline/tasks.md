# Tasks: PB-Studio Control Center Masterplan

Status: ausschließlich geplant. Alle 45 Pakete offen; keine Implementierung, Migration, Tests, App-/Workflowstarts oder Produkt-QC ausgeführt. Requirements: [spec.md](spec.md). Architektur/Typen/Transitions/Gates: [plan.md](plan.md). Vollständige Rückverfolgbarkeit: [traceability.md](traceability.md). Fachliche Gesamtgegenprüfung: [domain-contracts.md](domain-contracts.md).

## Ausführungskonvention

Neue Source-/Test-/Workflowdateien unten sind geplante Liefergegenstände, keine jetzt vorhandenen Implementierungen. Als „Modify“ aufgeführte zukünftige Dateien werden erst durch benannte Vorgänger erstellt; bestehende Dateien sind auf Existenz geprüft. Produktwrites erst nach Freigabe und dem jeweiligen O-/Ggate. Jede Phase erhält eigenes Manifest/Spec/Tasks/Evidence; Package-Checkbox erst [X], wenn sämtliche ausgewählten Pflichtcapabilities/Iterationsgates bestanden sind. Optionale Erweiterungen benötigen ausdrücklich gewählten Scope.

Verify-PY bedeutet nach Tests implementieren: `PYTHONPATH=src`, `.venv\Scripts\python.exe -m pytest <unten angegebene Testsdatei> -q --basetemp <eigener erzeugter Tasktemp>`. Erwartung erst im realen Lauf PASS/0; konkrete Assertions stehen je Paket. Verify-WPF bedeutet `dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release --logger "trx;LogFileName=comfy-task.trx" --results-directory <eigener Tasktemp>` ausführen, `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`, danach ausdrücklich sichtbaren Flow prüfen. Keine dieser Prüfungen jetzt ausführen. Genauer Temp-/Isolationsvertrag in Plan T.

## Paketindex

| ID | Phase | Abhängigkeiten | Requirements | Ziel |
|---|---|---|---|---|
| T001 | P0 | keine | TR-001, RR-005, RR-006 | Policy, Source-Drift und offene Gates festhalten |
| T002 | P0 | T001 | FR-005, RR-003, RR-004 | Golden Set, Native-Baseline und Qualityprofile |
| T003 | P1 | T001 | FR-001, FR-002, TR-002 | Lesende Endpointbindung und Offlinefähigkeit |
| T004 | P1 | T003 | FR-002, TR-004 | Capability-, Node- und Modellidentitäten |
| T005 | P1 | T004 | FR-003, TR-003 | Workflowregistry, Revisionen und typed Mapping |
| T006 | P1 | T005 | TR-001, OR-005 | Local-only, Trust, Egress und Redaction |
| T007 | P1 | T002, T005, T006 | FR-009, RR-004 | Früher lokaler Hardware- und Medien-Smoke |
| T008 | P2 | T005 | TR-005, TR-006, TR-012 | Result-, Zeit- und Embeddingvalidatoren |
| T009 | P2 | T008, T010, T011 | TR-007, RR-003 | Immutable Analyse-Runs und Cacheidentität |
| T010 | P2 | T001, T008 | TR-008, TR-009, OR-004 | Persistente Projektidentität und drei Automaten |
| T011 | P2 | T007, T010 | TR-008, TR-009, RR-001 | Additiver Store, UUIDmapping und Migrationsvertrag |
| T012 | P2 | T006, T007, T011, T015 | FR-013, TR-009, OR-003 | Scheduler, Submitoutbox und bounded Dispatch |
| T013 | P2 | T012 | TR-009, OR-004, RR-002 | Remote-Beobachtung und Reconciliation |
| T014 | P2 | T013, T010 | FR-013, OR-002, RR-002 | Own-Cancel, Pause, Retry und Priorität |
| T015 | P2 | T001, T007, T011 | OR-001, OR-003 | Shared Admission, Budget und Ressourcenprofil |
| T016 | OPTIONAL | T015, T014 | OR-001, OR-002 | Optionaler kooperativer Managed-GPU-Gate |
| T017 | P2 | T005, T006, T011 | TR-011, OR-005 | Sicherer Input-/Outputtransport |
| T018 | P2 | T002, T008, T017 | OR-007, TR-012 | Technische QC und rationale Medienzeit |
| T019 | P2 | T010, T011, T017, T018, T009 | FR-010, FR-011, TR-010, OR-008 | Canonical Import, Provenance und Ownership |
| T020 | P2 | T008, T019, T009 | TR-006, TR-010, RR-002 | Durable ADD-Vektorsaga im Native-SigLIP-Raum |
| T021 | P2 | T013, T014, T019, T020 | OR-004, RR-001, RR-002 | Recoveryinventar, Remoteactivity und Shutdown |
| T022 | P2 | T014, T019, T021 | TR-002, OR-006 | PB REST-, Snapshot- und SSE-Jobverträge |
| T023 | P3 | T007, T022 | FR-002, FR-016, OR-006 | WPF Verbindung, Settings und Installationshilfe |
| T024 | P3 | T023, T005, T019 | FR-003, FR-009, FR-016 | WPF Workflowlibrary und manuelle Generation |
| T025 | P3 | T023, T024, T014 | FR-013, FR-016, OR-006 | WPF Jobs, Queue-Reorder und Herkunftsfilter |
| T026 | P3a | T007, T009, T020, T021, T025 | FR-009, FR-010, RR-004, RR-005 | Integrierten lokalen Generation-MVP abnehmen |
| T027 | P3b | T026, T019 | FR-009, FR-011, FR-012 | Varianten, Regenerate und weitere Inputfamilien |
| T028 | P4 | T027 | FR-012, TR-012 | Upscale als qualifiziertes Derivat |
| T029 | P4 | T027, T018 | FR-012, TR-012 | Interpolation und rationales FPS-Derivat |
| T030 | P4 | T027, T018 | FR-012, TR-011, TR-012 | Begrenzter Reshot und Kontinuitätsprüfung |
| T031 | P5 | T008, T009, T026 | FR-005, TR-005, TR-007 | Native Stageadapter und Consumerdurchleitung |
| T032 | P5 | T002, T031 | FR-006, FR-005, RR-003 | Alternative Beat-/Downbeat-/Timingprovider |
| T033 | P5 | T002, T031, T019 | FR-006, FR-007, RR-003 | Stems und Drumtriggerprovider |
| T034 | P5 | T002, T031, T032 | FR-006, TR-005, RR-003 | Energie, Struktur, Harmonie und Longmixprovider |
| T035 | P5 | T002, T031 | FR-008, TR-005, RR-003 | Alternative Caption-/Inhalts-/Moodprovider |
| T036 | P5 | T002, T031, T018 | FR-008, TR-005, OR-007 | Szenen, Motion, Technik und Qualityprovider |
| T037 | OPTIONAL | T002, T020, T031 | TR-006, RR-001 | Optionale alternative und segmentweise Embeddingräume |
| T038 | P5 | T002, T009, T031 | FR-004, FR-005, RR-003 | Vergleichsmodus und Kohortenqualifikation |
| T039 | P6 | T038, T031, T015 | FR-004, RR-003 | Qualifiziertes AUTO und sichtbares Degrade |
| T040 | P7 | T026, T027, T031, T038, T043, T030 | FR-014, TR-012, RR-002 | Director Coverage, Asset-DAG und Timelinebindung |
| T041 | P8 | T021, T026, T040, T043 | FR-015, OR-003, TR-012, RR-005 | Bounded Longform-Automation und Gesamtvideo |
| T042 | OPTIONAL | T027, T038, T040 | FR-016, RR-003 | Optionales Generatorfeedback und Lernen |
| T043 | P3/P8-PRE | T019, T020, T021 | OR-008, OR-003, RR-001 | Retention, Ownership, Archivierung und sichere GC |
| T044 | OPTIONAL | T005, T023, T026 | FR-016, TR-004 | Optionaler Setupwizard und Entwicklerhilfe |
| T045 | RECURRING | keine | RR-005, RR-006 | Phasenweise Regression, QC und Liefernachweis |

## Detaillierte Arbeitspakete

### T001 — Policy, Source-Drift und offene Gates festhalten

- [ ] T001 [OBJ-1] {(TR-001)} {(RR-005)} {(RR-006)} Policy, Source-Drift und offene Gates festhalten in `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\clarifications.md`.

**ID / Titel / Ziel:** T001 / Policy, Source-Drift und offene Gates festhalten. Ergebnis: freigegebene Phase-Manifeste, Source-/API-Revisionsbindung und Gateantworten.
**Abhängigkeiten / Gates:** keine. Masterplan-/Phasenscopefreigabe; D01/D02 nicht erneut fragen.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\clarifications.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\phase-manifests.md`

**Interfaces:**
- Consumes: spec.md, bestätigte Entscheidungen und bestehender Review.
- Produces: freigegebene Phase-Manifeste, Source-/API-Revisionsbindung und Gateantworten. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. D01/D02, bestätigte O01–O04-Grundsätze und aktuelle Source-/APIrevision dokumentieren; konkrete O03-Mess-/Referenzgates und O04-Änderungsfreigaben offen halten.
2. Phase-Pflichtmenge/Gates/Owner festlegen; Requirement-/Task-/Findingzuordnung und Dirty-Scope prüfen.
3. Prüfen: D01/D02 und O01–O04-Grundsätze bestätigt; konkrete O03-Mess-/Referenzgates und O04-Schema/API-/Migrationsfreigaben mit Owner/Status offen; keine PB-Dienstesteuerung; keine aktuelle Runtimefreigabe aus historischer Evidence; vorhandene Dirtydateien klassifiziert.
4. Abnahme nur Dokumentvertrag; keine Produktfreigabe aus diesem Plan ableiten.

**Akzeptanzkriterien:** D01/D02 und O01–O04-Grundsätze bestätigt; konkrete O03-Mess-/Referenzgates und O04-Schema/API-/Migrationsfreigaben mit Owner/Status offen; keine PB-Dienstesteuerung; keine aktuelle Runtimefreigabe aus historischer Evidence; vorhandene Dirtydateien klassifiziert. 
**Risiko:** Regelkonflikt oder falscher Source-Stand.
**Rollback:** Dokumentrevision korrigieren; keine Produktmutation.

### T002 — Golden Set, Native-Baseline und Qualityprofile

- [ ] T002 [P] [US3] {(FR-005)} {(RR-003)} {(RR-004)} Golden Set, Native-Baseline und Qualityprofile in `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\benchmark-spec.md`.

**ID / Titel / Ziel:** T002 / Golden Set, Native-Baseline und Qualityprofile. Ergebnis: QualityProfile und Referenz-/Messprotokoll je Kohorte.
**Abhängigkeiten / Gates:** T001. O03 Referenzautorisierung und tatsächliche Qualitäts-/Ressourcenwerte.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\benchmark-spec.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\reference-manifest.json`

**Interfaces:**
- Consumes: Sourceinventar und Scope T001; verbindliche Fachverträge FP12, FP16 in domain-contracts.md.
- Produces: QualityProfile und Referenz-/Messprotokoll je Kohorte. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_benchmark_manifest.py` definieren. Prüfbedingungen/Assertions: Autorisierte Sourcehashes; unabhängige Labels; verwandte Medien nicht über Holdoutgrenzen; fresh/warm/cache getrennt; Qualitätsgrenzen vor Tuning festgelegt. Gesamtgegenprüfung: FP12: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T015 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für QualityProfile und Referenz-/Messprotokoll je Kohorte umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_benchmark_manifest.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Autorisierte Sourcehashes; unabhängige Labels; verwandte Medien nicht über Holdoutgrenzen; fresh/warm/cache getrennt; Qualitätsgrenzen vor Tuning festgelegt. Gesamtgegenprüfung: FP12: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T015 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** falsche Groundtruth oder Cachekontamination.
**Rollback:** betroffene Messung zurückziehen, Native bleibt aktiv.

### T003 — Lesende Endpointbindung und Offlinefähigkeit

- [ ] T003 [US1] {(FR-001)} {(FR-002)} {(TR-002)} Lesende Endpointbindung und Offlinefähigkeit in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\config_manager.py`.

**ID / Titel / Ziel:** T003 / Lesende Endpointbindung und Offlinefähigkeit. Ergebnis: ComfyClient.inspect(EndpointIdentity) → DiscoverySnapshot.
**Abhängigkeiten / Gates:** T001. kein Produkt-GPUlauf.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\config_manager.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\client.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\schemas.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_connection.py`

**Interfaces:**
- Consumes: Endpoint-/Local-only-Scope T001; verbindliche Fachverträge FP15 in domain-contracts.md.
- Produces: ComfyClient.inspect(EndpointIdentity) → DiscoverySnapshot. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_connection.py` definieren. Prüfbedingungen/Assertions: Zwei Server mit verschiedenen Versionen bleiben gebunden; falscher Dienst/Offline/Timeout blockiert PBstart nicht; keine mutierende Discoveryprobe. CM04/CM08/CM11/CM13: ein WS-Owner, clientId/client_id-Mapping, Binärframes getrennt; keine POST-Retries; Connectiongeneration ist kein Bootbeleg; finite profilgebundene Control-/Transferfristen. Gesamtgegenprüfung: FP15: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T023 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ComfyClient.inspect(EndpointIdentity) → DiscoverySnapshot umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_connection.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Zwei Server mit verschiedenen Versionen bleiben gebunden; falscher Dienst/Offline/Timeout blockiert PBstart nicht; keine mutierende Discoveryprobe. CM04/CM08/CM11/CM13: ein WS-Owner, clientId/client_id-Mapping, Binärframes getrennt; keine POST-Retries; Connectiongeneration ist kein Bootbeleg; finite profilgebundene Control-/Transferfristen. Gesamtgegenprüfung: FP15: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T023 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** falsche Instanz oder Startuphang.
**Rollback:** Bridge enabled=false, bestehende App bleibt nutzbar.

### T004 — Capability-, Node- und Modellidentitäten

- [ ] T004 [US1] {(FR-002)} {(TR-004)} Capability-, Node- und Modellidentitäten in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\capabilities.py`.

**ID / Titel / Ziel:** T004 / Capability-, Node- und Modellidentitäten. Ergebnis: DiscoverySnapshot mit readiness, Profilbindung und Missing-/Unknowngründen.
**Abhängigkeiten / Gates:** T003. geprüftes versionspezifisches APIprofil.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\capabilities.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_capabilities.py`

**Interfaces:**
- Consumes: ComfyClient.inspect.
- Produces: DiscoverySnapshot mit readiness, Profilbindung und Missing-/Unknowngründen. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_capabilities.py` definieren. Prüfbedingungen/Assertions: Node vorhanden/Modell defekt bleibt unqualified; gleicher Modellname anderer Hash unterscheidbar; extensions ist keine vollständige Custom-Node-Liste; Unknownversion nur lesend. CM09/CM13: profilgebundene Remote-Statusabbildung, Bootidentity unknown ohne Beleg, Clientprompt-ID-Unterstützung für ersten automatisierten MVP erforderlich.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für DiscoverySnapshot mit readiness, Profilbindung und Missing-/Unknowngründen umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_capabilities.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Node vorhanden/Modell defekt bleibt unqualified; gleicher Modellname anderer Hash unterscheidbar; extensions ist keine vollständige Custom-Node-Liste; Unknownversion nur lesend. CM09/CM13: profilgebundene Remote-Statusabbildung, Bootidentity unknown ohne Beleg, Clientprompt-ID-Unterstützung für ersten automatisierten MVP erforderlich. 
**Risiko:** Fake-ready oder falscher Paket-/Modellraum.
**Rollback:** Discoveryprofil unqualified, kein Submit.

### T005 — Workflowregistry, Revisionen und typed Mapping

- [ ] T005 [US1] {(FR-003)} {(TR-003)} Workflowregistry, Revisionen und typed Mapping in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\workflow_registry.py`.

**ID / Titel / Ziel:** T005 / Workflowregistry, Revisionen und typed Mapping. Ergebnis: WorkflowRegistry.get/validate/register/set_enabled, resolve_parameters, parse_outputs; persistiertes WorkflowActivationReceipt mit eigener activation_revision/registry_generation und idempotentem CAS.
**Abhängigkeiten / Gates:** T004. keine Phantommodelle/-Nodes im Bundle.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\workflow_registry.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\workflow_parameters.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\result_parser.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_workflow_bundle.py`

**Interfaces:**
- Consumes: DiscoverySnapshot, WorkflowRevisionKey, typed Adapterfamilien; Reviewloop-Vertrag L05.
- Produces: WorkflowRegistry.get/validate/register/set_enabled, resolve_parameters, parse_outputs; persistiertes WorkflowActivationReceipt mit eigener activation_revision/registry_generation und idempotentem CAS. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_workflow_bundle.py` definieren. Prüfbedingungen/Assertions: UI-Graph als APIprompt abgewiesen; Node-ID/Slots/Outputindex/type/Frameconstraint korrekt; Enable-off verhindert neue Dispatches, pinned Attempts bleiben; unbekannter Outputadapter fail-closed. CM09/CM12: completed ohne Rohsuccess bleibt unbekannt; Pflichtoutputs und tatsächliche Uploadreferenzen typisiert validieren. L05: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T024, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für WorkflowRegistry.get/validate/register/set_enabled, resolve_parameters, parse_outputs; persistiertes WorkflowActivationReceipt mit eigener activation_revision/registry_generation und idempotentem CAS umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_workflow_bundle.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** UI-Graph als APIprompt abgewiesen; Node-ID/Slots/Outputindex/type/Frameconstraint korrekt; Enable-off verhindert neue Dispatches, pinned Attempts bleiben; unbekannter Outputadapter fail-closed. CM09/CM12: completed ohne Rohsuccess bleibt unbekannt; Pflichtoutputs und tatsächliche Uploadreferenzen typisiert validieren. L05: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T024, kein vorzeitiger Integrations-PASS. 
**Risiko:** Graphdrift oder freier Code aus Metadaten.
**Rollback:** betroffene Revision deaktivieren, alte Bundles behalten.

### T006 — Local-only, Trust, Egress und Redaction

- [ ] T006 [US1] {(TR-001)} {(OR-005)} Local-only, Trust, Egress und Redaction in `C:\Users\david\Documents\Pb_studio_AMD_version\backend\dependencies.py`.

**ID / Titel / Ziel:** T006 / Local-only, Trust, Egress und Redaction. Ergebnis: check_workflow_policy(WorkflowBundle, EndpointIdentity) → ValidationReport.
**Abhängigkeiten / Gates:** T005. Lokaler PB-Scope; neue Dependencyfreigabe falls notwendig.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\dependencies.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\workflow_policy.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_workflow_policy.py`

**Interfaces:**
- Consumes: D01/D02, Registry und bestehender SSELogHandler; Backendredaction gezielt ergänzen, vorhandene WPFredaction separat erhalten.
- Produces: check_workflow_policy(WorkflowBundle, EndpointIdentity) → ValidationReport. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_workflow_policy.py` definieren. Prüfbedingungen/Assertions: Manifest/declared Local-only-Policy, Redirectziele und verschachtelte Secrets prüfen; Callback/Replacement, der Prompt/Seed/Localnode ändert, invalidiert Profil/effective Identity. Deklarationsprüfung ist keine Egresssperre; declared_only bleibt unqualified. Audited-frozen Alternative oder separat erzwungener pre-enqueue/Egressvertrag ausdrücklich nachweisen.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für check_workflow_policy(WorkflowBundle, EndpointIdentity) → ValidationReport umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_workflow_policy.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Manifest/declared Local-only-Policy, Redirectziele und verschachtelte Secrets prüfen; Callback/Replacement, der Prompt/Seed/Localnode ändert, invalidiert Profil/effective Identity. Deklarationsprüfung ist keine Egresssperre; declared_only bleibt unqualified. Audited-frozen Alternative oder separat erzwungener pre-enqueue/Egressvertrag ausdrücklich nachweisen. 
**Risiko:** ungeprüfte externe Aufrufe/Uploads oder Geheimnislogs.
**Rollback:** Ausführung deaktivieren; Credential-/Provenancedaten nicht loggen.

### T007 — Früher lokaler Hardware- und Medien-Smoke

- [ ] T007 [US1] {(FR-009)} {(RR-004)} Früher lokaler Hardware- und Medien-Smoke in `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\pilot\manifest.json`.

**ID / Titel / Ziel:** T007 / Früher lokaler Hardware- und Medien-Smoke. Ergebnis: G1-Receipt, gebundene ResourceProfile/WorkflowBundle-Revision.
**Abhängigkeiten / Gates:** T002, T005, T006. O03, bewusster separat autorisierter Smoke; nicht während Planung.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\pilot\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\pilot\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\evidence\g1-profile.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_smoke_profile_contract.py`

**Interfaces:**
- Consumes: autorisierte Referenz/Qualityprofile und Local-only-Bundle; verbindliche Fachverträge FP12 in domain-contracts.md.
- Produces: G1-Receipt, gebundene ResourceProfile/WorkflowBundle-Revision. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_smoke_profile_contract.py` definieren. Prüfbedingungen/Assertions: Source/API/Node/Model/Runtimeprofile exakt; geprüft lokales audited-frozen oder enforced Profil; veränderter effective Graph nicht als submitted hash. Realer kleiner lokaler Lauf, Output geöffnet/Full Decode, echte Peak-Ressourcen; keine Fremdqueue gestört; statischer PASS kein G1. Gesamtgegenprüfung: FP12: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T015 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für G1-Receipt, gebundene ResourceProfile/WorkflowBundle-Revision umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_smoke_profile_contract.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Source/API/Node/Model/Runtimeprofile exakt; geprüft lokales audited-frozen oder enforced Profil; veränderter effective Graph nicht als submitted hash. Realer kleiner lokaler Lauf, Output geöffnet/Full Decode, echte Peak-Ressourcen; keine Fremdqueue gestört; statischer PASS kein G1. Gesamtgegenprüfung: FP12: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T015 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Hardware ungeeignet oder fremde Last beeinträchtigt.
**Rollback:** Profil unqualified, keine großen DB-/WPFpakete starten.

### T008 — Result-, Zeit- und Embeddingvalidatoren

- [ ] T008 [P] [US3] {(TR-005)} {(TR-006)} {(TR-012)} Result-, Zeit- und Embeddingvalidatoren in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\contracts.py`.

**ID / Titel / Ziel:** T008 / Result-, Zeit- und Embeddingvalidatoren. Ergebnis: ResultEnvelope/AnalysisRun/StageResult/EmbeddingPayload, validate_result/validate_embedding.
**Abhängigkeiten / Gates:** T005. kein produktives Umschreiben bestehender APIfelder.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\contracts.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_result_contracts.py`

**Interfaces:**
- Consumes: bestehende Audio-/Video-Schemas und P-Typkatalog; verbindliche Fachverträge FP07 in domain-contracts.md.
- Produces: ResultEnvelope/AnalysisRun/StageResult/EmbeddingPayload, validate_result/validate_embedding. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_result_contracts.py` definieren. Prüfbedingungen/Assertions: ms als s, Chunkoffsetfehler, NaN, Out-of-range, null/empty/unavailable, anderer Raum gleicher Dimension und unkalibrierte Motion abgewiesen; T2V ohne Source gültig. Gesamtgegenprüfung: FP07: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ResultEnvelope/AnalysisRun/StageResult/EmbeddingPayload, validate_result/validate_embedding umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_result_contracts.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** ms als s, Chunkoffsetfehler, NaN, Out-of-range, null/empty/unavailable, anderer Raum gleicher Dimension und unkalibrierte Motion abgewiesen; T2V ohne Source gültig. Gesamtgegenprüfung: FP07: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** syntaktisch gültige fachlich falsche Daten.
**Rollback:** externes Result quarantined; Nativepfad unverändert.

### T009 — Immutable Analyse-Runs und Cacheidentität

- [ ] T009 [US3] {(TR-007)} {(RR-003)} Immutable Analyse-Runs und Cacheidentität in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\embedding_cache.py`.

**ID / Titel / Ziel:** T009 / Immutable Analyse-Runs und Cacheidentität. Ergebnis: AnalysisRunRepository.put/set_active, vollständiger fingerprint.
**Abhängigkeiten / Gates:** T008, T010, T011. Gmigration bei neuer Persistenz; keine fausse Native-Modellidentität.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\embedding_cache.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\post_processor.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\loader_cache.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\cross_modal_projector.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\analysis_runs.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_analysis_runs.py`

**Interfaces:**
- Consumes: TR-005/006-Typen und additiver Job-/Runstore; verbindliche Fachverträge FP02, FP06 in domain-contracts.md.
- Produces: AnalysisRunRepository.put/set_active, vollständiger fingerprint. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_analysis_runs.py` definieren. Prüfbedingungen/Assertions: Geänderter Hop/Processor/LoRA/Workflow/range invalidiert; Vergleich überschreibt aktiven Nativepointer nicht; gleiche Modellnamen kein Lookupalias; Sourcehash gewechselt kein Reuse. Gesamtgegenprüfung: FP02: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP06: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. P2 konkret: Repository, immutable Runs, Snapshot-/FieldOwnershipMap-Vertrag und Cachekern mit bestehenden Native-Cacheconsumern; gemischte Capabilityprojektion erst T031.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für AnalysisRunRepository.put/set_active, vollständiger fingerprint umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_analysis_runs.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Geänderter Hop/Processor/LoRA/Workflow/range invalidiert; Vergleich überschreibt aktiven Nativepointer nicht; gleiche Modellnamen kein Lookupalias; Sourcehash gewechselt kein Reuse. Gesamtgegenprüfung: FP02: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP06: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. P2 konkret: Repository, immutable Runs, Snapshot-/FieldOwnershipMap-Vertrag und Cachekern mit bestehenden Native-Cacheconsumern; gemischte Capabilityprojektion erst T031. 
**Risiko:** Cachevermischung oder verlorene Originalanalyse.
**Rollback:** aktiven Stagepointer auf erhaltene Native-Runrevision.

### T010 — Persistente Projektidentität und drei Automaten

- [ ] T010 [US2] {(TR-008)} {(TR-009)} {(OR-004)} Persistente Projektidentität und drei Automaten in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\models.py`.

**ID / Titel / Ziel:** T010 / Persistente Projektidentität und drei Automaten. Ergebnis: ProjectIdentity, ProductionBatch-Minimalmodell, LogicalJobSnapshot, AttemptIdentity, ArtifactReceipt und Q-Transitions.
**Abhängigkeiten / Gates:** T001, T008. O02-Betriebsregel bestätigt; technische Zustands-/Lifecycleabnahme offen.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\models.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_state_machine.py`

**Interfaces:**
- Consumes: aktueller project_id/root/epoch-Guard und bestätigte O02-Policy; verbindliche Fachverträge FP09, FP14 in domain-contracts.md; Reviewloop-Vertrag L01; Reviewloop-Vertrag L06.
- Produces: ProjectIdentity, ProductionBatch-Minimalmodell, LogicalJobSnapshot, AttemptIdentity, ArtifactReceipt und Q-Transitions. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_state_machine.py` definieren. Prüfbedingungen/Assertions: Jede nicht aufgeführte Q-Transition verboten; terminales Event reaktiviert nicht; Epoch nach Restart keine UUID; cancelled Job bleibt cancelled bei Remoteerfolg; Progress kein Importready. CM06/CM07/CM14: Wirepflichtfelder/Enums/null/UUID/int64 explizit; frühe Beobachtungen nicht direkt auf dispatching anwenden; ungeklärtes Remote-Cancel bounded nach needs_decision. Gesamtgegenprüfung: FP09: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T011 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ProjectIdentity, ProductionBatch-Minimalmodell, LogicalJobSnapshot, AttemptIdentity, ArtifactReceipt und Q-Transitions umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_job_state_machine.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Jede nicht aufgeführte Q-Transition verboten; terminales Event reaktiviert nicht; Epoch nach Restart keine UUID; cancelled Job bleibt cancelled bei Remoteerfolg; Progress kein Importready. CM06/CM07/CM14: Wirepflichtfelder/Enums/null/UUID/int64 explizit; frühe Beobachtungen nicht direkt auf dispatching anwenden; ungeklärtes Remote-Cancel bounded nach needs_decision. Gesamtgegenprüfung: FP09: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T011 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS. 
**Risiko:** gemischte Zustände oder stale Projektcommits.
**Rollback:** neue Jobs gesperrt; vorhandene lokale Zustände erhalten.

### T011 — Additiver Store, UUIDmapping und Migrationsvertrag

- [ ] T011 [US2] {(TR-008)} {(TR-009)} {(RR-001)} Additiver Store, UUIDmapping und Migrationsvertrag in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\database_core.py`.

**ID / Titel / Ziel:** T011 / Additiver Store, UUIDmapping und Migrationsvertrag. Ergebnis: JobRepository.create/prepare_attempt/transition/record_cancel, minimale production_batch/production_batch_job-Persistenz und additive Tabellen.
**Abhängigkeiten / Gates:** T007, T010. Gmigration: konkrete SQL zuerst reviewen, Kopie testen, gesondert freigeben.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\database_core.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\repository.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\schema-contract.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_repository.py`

**Interfaces:**
- Consumes: Q-Modelle, ProjectIdentity, G1; verbindliche Fachverträge FP08, FP09 in domain-contracts.md; Reviewloop-Vertrag L01.
- Produces: JobRepository.create/prepare_attempt/transition/record_cancel, minimale production_batch/production_batch_job-Persistenz und additive Tabellen. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_repository.py` definieren. Prüfbedingungen/Assertions: Job/Attempt/Outbox atomic; CAS Revisionrace; gleiche client_request_id anderer Payload Konflikt; alte Projekte öffnen; zukünftige JSONschema nicht still herunterstufen; FK-/UUID-/ReaderWritervertrag. CM01/CM02/CM11: dauerhafte Prompt-ID und Intent-Deduplizierung; provider_job_change atomar mit Domainänderung, store_generation_uuid, Snapshotcursor-/Retentionvertrag; alte Intentkeys nicht durch GC wieder ausführbar. Journal/Snapshot unterscheiden entity_kind job/batch und entity_uuid/entity_revision; reine Batchänderungen ohne Jobrevision bleiben rekonstruierbar. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP09: Bestehendes Projekt öffnen, Job anlegen, reopen/Recovery: Katalog-, Datei- und Job-UUID unverändert. Absichtlich abweichende Datei-UUID blockiert vor Mutation. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für JobRepository.create/prepare_attempt/transition/record_cancel, minimale production_batch/production_batch_job-Persistenz und additive Tabellen umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_job_repository.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Job/Attempt/Outbox atomic; CAS Revisionrace; gleiche client_request_id anderer Payload Konflikt; alte Projekte öffnen; zukünftige JSONschema nicht still herunterstufen; FK-/UUID-/ReaderWritervertrag. CM01/CM02/CM11: dauerhafte Prompt-ID und Intent-Deduplizierung; provider_job_change atomar mit Domainänderung, store_generation_uuid, Snapshotcursor-/Retentionvertrag; alte Intentkeys nicht durch GC wieder ausführbar. Journal/Snapshot unterscheiden entity_kind job/batch und entity_uuid/entity_revision; reine Batchänderungen ohne Jobrevision bleiben rekonstruierbar. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP09: Bestehendes Projekt öffnen, Job anlegen, reopen/Recovery: Katalog-, Datei- und Job-UUID unverändert. Absichtlich abweichende Datei-UUID blockiert vor Mutation. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. 
**Risiko:** Datenmigration/inkompatibler Binärdowngrade.
**Rollback:** neue Dispatches stoppen; konsistente Generation erhalten, kein DB-only-Restore.

### T012 — Scheduler, Submitoutbox und bounded Dispatch

- [ ] T012 [US2] {(FR-013)} {(TR-009)} {(OR-003)} Scheduler, Submitoutbox und bounded Dispatch in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\scheduler.py`.

**ID / Titel / Ziel:** T012 / Scheduler, Submitoutbox und bounded Dispatch. Ergebnis: PinnedSubmission und ComfyClient.submit-Aufruf unter Dispatch-/Admissionvertrag.
**Abhängigkeiten / Gates:** T006, T007, T011, T015. G1+O01 observed_shared bestätigt; kein blindes Interrupted-Requeue.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\scheduler.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_submit_outbox.py`

**Interfaces:**
- Consumes: JobRepository.prepare_attempt, WorkflowBundle, ResourceProfile; verbindliche Fachverträge FP08 in domain-contracts.md; Reviewloop-Vertrag L06.
- Produces: PinnedSubmission und ComfyClient.submit-Aufruf unter Dispatch-/Admissionvertrag. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_submit_outbox.py` definieren. Prüfbedingungen/Assertions: Crash nach Send/Accept vor Receipt →submission_unknown; keine Leaseexpiry-Doppelsendung; kein Networkwait in DBtransaction; Shape/Inputhash/Policy vor Send gebunden. CM11/CM14: prompt_id vor Send persistent und exakt mitsenden; fremde/fehlende WS-Prompt-ID nie zuordnen; frühe Events puffern, spätes ACK keine Regression. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für PinnedSubmission und ComfyClient.submit-Aufruf unter Dispatch-/Admissionvertrag umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_submit_outbox.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Crash nach Send/Accept vor Receipt →submission_unknown; keine Leaseexpiry-Doppelsendung; kein Networkwait in DBtransaction; Shape/Inputhash/Policy vor Send gebunden. CM11/CM14: prompt_id vor Send persistent und exakt mitsenden; fremde/fehlende WS-Prompt-ID nie zuordnen; frühe Events puffern, spätes ACK keine Regression. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS. 
**Risiko:** doppelte Generation nach Timeout.
**Rollback:** Dispatch deaktivieren, Outbox/Unknownattempts reconciliieren.

### T013 — Remote-Beobachtung und Reconciliation

- [ ] T013 [US2] {(TR-009)} {(OR-004)} {(RR-002)} Remote-Beobachtung und Reconciliation in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\reconciliation.py`.

**ID / Titel / Ziel:** T013 / Remote-Beobachtung und Reconciliation. Ergebnis: reconcile_attempt(AttemptIdentity) →RemoteJobSnapshot/needs_decision.
**Abhängigkeiten / Gates:** T012. versionsgebundene WS/Queue/Historyverträge.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\reconciliation.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_reconciliation.py`

**Interfaces:**
- Consumes: ComfyClient.observe, durable receipts/pinned identity; verbindliche Fachverträge FP08 in domain-contracts.md; Reviewloop-Vertrag L06.
- Produces: reconcile_attempt(AttemptIdentity) →RemoteJobSnapshot/needs_decision. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_reconciliation.py` definieren. Prüfbedingungen/Assertions: Leere History nach Serverrestart →unknown; falsche Instanz/session/UUID kein Match; fehlende Outputs kein Erfolg; bounded Probes; kein zweiter Submit nach verlorener Antwort. CM07–CM14: normalisierte States mit Rohbeleg prüfen; Success vor History ist result_evidence_pending; sidlose/fremde/binäre Events ignorieren; unbekanntes Cancel bounded sichtbar, kein Resubmit. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L06: Nur gebundenes autoritatives Rejectreceipt oder bewiesener Nicht-Send löst Unknown; leere History/Proxyfehler/fremder Beleg/Acceptkonflikt erlauben keinen Retry.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für reconcile_attempt(AttemptIdentity) →RemoteJobSnapshot/needs_decision umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_reconciliation.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Leere History nach Serverrestart →unknown; falsche Instanz/session/UUID kein Match; fehlende Outputs kein Erfolg; bounded Probes; kein zweiter Submit nach verlorener Antwort. CM07–CM14: normalisierte States mit Rohbeleg prüfen; Success vor History ist result_evidence_pending; sidlose/fremde/binäre Events ignorieren; unbekanntes Cancel bounded sichtbar, kein Resubmit. Gesamtgegenprüfung: FP08: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T021 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L06: Nur gebundenes autoritatives Rejectreceipt oder bewiesener Nicht-Send löst Unknown; leere History/Proxyfehler/fremder Beleg/Acceptkonflikt erlauben keinen Retry. 
**Risiko:** False never-run oder duplizierte Ausführung.
**Rollback:** needs_decision sichtbar, keine automatische Neuberechnung.

### T014 — Own-Cancel, Pause, Retry und Priorität

- [ ] T014 [US2] {(FR-013)} {(OR-002)} {(RR-002)} Own-Cancel, Pause, Retry und Priorität in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\control.py`.

**ID / Titel / Ziel:** T014 / Own-Cancel, Pause, Retry und Priorität. Ergebnis: record_cancel, cancel_owned, set_priority/reorder/pause_batch gemäß Q.
**Abhängigkeiten / Gates:** T013, T010. O02 bestätigt; kein globaler clear/free/interrupt.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\control.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_control.py`

**Interfaces:**
- Consumes: Job-/Attemptstore, Reconciliation und O02; Reviewloop-Vertrag L06.
- Produces: record_cancel, cancel_owned, set_priority/reorder/pause_batch gemäß Q. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_job_control.py` definieren. Prüfbedingungen/Assertions: PBqueued neben fremdem running: nur PBID geändert; Cancel vor Send atomar sperrt Outbox; Unknown hält Cancelintent und cancelt nach Reconciliation; Cancel gegen fertige ID trifft Nachfolger nicht; HTTP200 kein terminal; Reorder nur undispatched; Retry nur definitiver alter Attempt+Budget. Terminalfailed Retry erzeugt neuen linked Intent; ready/cancelled/obsolete/unresolved →409. Minimale Batchpause/Reorder/Restart funktionieren ohne T041. CM07: cancelled:true ist dispatch_accepted, kein Remote-Terminalreceipt; Pendingdelete ohne History und Pending→Running-Rennen enden bei fehlendem Beleg bounded needs_decision, Cancelintent bleibt. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für record_cancel, cancel_owned, set_priority/reorder/pause_batch gemäß Q umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_job_control.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** PBqueued neben fremdem running: nur PBID geändert; Cancel vor Send atomar sperrt Outbox; Unknown hält Cancelintent und cancelt nach Reconciliation; Cancel gegen fertige ID trifft Nachfolger nicht; HTTP200 kein terminal; Reorder nur undispatched; Retry nur definitiver alter Attempt+Budget. Terminalfailed Retry erzeugt neuen linked Intent; ready/cancelled/obsolete/unresolved →409. Minimale Batchpause/Reorder/Restart funktionieren ohne T041. CM07: cancelled:true ist dispatch_accepted, kein Remote-Terminalreceipt; Pendingdelete ohne History und Pending→Running-Rennen enden bei fehlendem Beleg bounded needs_decision, Cancelintent bleibt. L06: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T013, kein vorzeitiger Integrations-PASS. 
**Risiko:** fremder Abbruch oder verlorene Nutzerentscheidung.
**Rollback:** neue Aktionen disable; Cancelintent und Verlauf bleiben.

### T015 — Shared Admission, Budget und Ressourcenprofil

- [ ] T015 [US2] {(OR-001)} {(OR-003)} Shared Admission, Budget und Ressourcenprofil in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\core\vram_budget_manager.py`.

**ID / Titel / Ziel:** T015 / Shared Admission, Budget und Ressourcenprofil. Ergebnis: check_admission(ResourceProfile, job) →ValidationReport + gebundener Admissionreceipt.
**Abhängigkeiten / Gates:** T001, T007, T011. O01 observed_shared bestätigt; gemessenes Ressourcenprofil offen; kein harter Shared-Exklusivitätsclaim.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\core\vram_budget_manager.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\core\model_loader.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\dependencies.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\pacing_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\render_router.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\admission.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_resource_admission.py`

**Interfaces:**
- Consumes: G1 gemessenes Profil, Native-Locks/Sensoren und O01; verbindliche Fachverträge FP10, FP11, FP12 in domain-contracts.md.
- Produces: check_admission(ResourceProfile, job) →ValidationReport + gebundener Admissionreceipt. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_resource_admission.py` definieren. Prüfbedingungen/Assertions: Fremdsubmit zwischen Poll und PBstart nicht als garantiert exklusiv labeln; LHMunknown/Leaseexpiry kein Freibeweis; RAM/Disk/Batchlimits stoppen neue Dispatches; Locks nicht umgangen. Gesamtgegenprüfung: FP10: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP11: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP12: Kurzzeitspitze zwischen Start/Ende, Fremdlast und Sensorlücke: Buchhaltung wird niemals als Hardwaremessung freigegeben. Konkrete Grenzwerte bleiben O03 offen.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für check_admission(ResourceProfile, job) →ValidationReport + gebundener Admissionreceipt umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_resource_admission.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Fremdsubmit zwischen Poll und PBstart nicht als garantiert exklusiv labeln; LHMunknown/Leaseexpiry kein Freibeweis; RAM/Disk/Batchlimits stoppen neue Dispatches; Locks nicht umgangen. Gesamtgegenprüfung: FP10: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP11: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP12: Kurzzeitspitze zwischen Start/Ende, Fremdlast und Sensorlücke: Buchhaltung wird niemals als Hardwaremessung freigegeben. Konkrete Grenzwerte bleiben O03 offen. 
**Risiko:** OOM/deadlock/unwahre Garantie.
**Rollback:** externe Dispatches stoppen; Native-Locks unverändert wirksam.

### T016 — Optionaler kooperativer Managed-GPU-Gate

- [ ] T016 [US4] {(OR-001)} {(OR-002)} Optionaler kooperativer Managed-GPU-Gate in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\admission.py`.

**ID / Titel / Ziel:** T016 / Optionaler kooperativer Managed-GPU-Gate. Ergebnis: versionierter kooperativer Admission-/Lease-/Unloadreceiptvertrag.
**Abhängigkeiten / Gates:** T015, T014. Gesondert qualifizierter kooperativer Scope und externe Gateinstallation; Grundsatzbestätigung ist keine Installationsfreigabe.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\admission.py` — zukünftige Datei aus Vorgängerpaket

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\integrations\comfyui\pb_admission_gate\__init__.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_managed_lease.py`

**Interfaces:**
- Consumes: O01 späteres managed Ziel, Native Admission und Own-Cancel; verbindliche Fachverträge FP10, FP11 in domain-contracts.md.
- Produces: versionierter kooperativer Admission-/Lease-/Unloadreceiptvertrag. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_managed_lease.py` definieren. Prüfbedingungen/Assertions: Alle Clients im garantierten Scope müssen vor GPUstart Lease erwerben; Fencing stale owner sperrt; Expiry bei aktivem Modell kein PBoverlap; fremde Clients außerhalb Scope sichtbar nicht garantiert. Gesamtgegenprüfung: FP10: Jeder inventarisierte Eintrittspunkt konkurriert mit externer Reservierung: managed ohne lokale Umgehung; observed_shared ohne erfundene Exclusivityzusage. FP11: Blockierter Worker, Requesttimeout, externe Dispatchanfrage: keine frühe managed-Freigabe. Zweiter Cancel, Shutdown und Heartbeatausfall prüfen.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für versionierter kooperativer Admission-/Lease-/Unloadreceiptvertrag umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_managed_lease.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Alle Clients im garantierten Scope müssen vor GPUstart Lease erwerben; Fencing stale owner sperrt; Expiry bei aktivem Modell kein PBoverlap; fremde Clients außerhalb Scope sichtbar nicht garantiert. Gesamtgegenprüfung: FP10: Jeder inventarisierte Eintrittspunkt konkurriert mit externer Reservierung: managed ohne lokale Umgehung; observed_shared ohne erfundene Exclusivityzusage. FP11: Blockierter Worker, Requesttimeout, externe Dispatchanfrage: keine frühe managed-Freigabe. Zweiter Cancel, Shutdown und Heartbeatausfall prüfen. 
**Risiko:** externe Pluginänderung oder Deadlock.
**Rollback:** observed_shared mit eingeschränkten Garantien, keine Fremdjobs entladen.

### T017 — Sicherer Input-/Outputtransport

- [ ] T017 [US1] {(TR-011)} {(OR-005)} Sicherer Input-/Outputtransport in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\media_transport.py`.

**ID / Titel / Ziel:** T017 / Sicherer Input-/Outputtransport. Ergebnis: ComfyClient.acquire_output/OutputReference →StagedArtifact, InputArtifactRef.
**Abhängigkeiten / Gates:** T005, T006, T011. Root-/Transportprofil konkret; Remote erst ausdrücklich konfiguriert.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\comfyui\media_transport.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_transport.py`

**Interfaces:**
- Consumes: Workflow-Loadervertrag/Local-only-Policy und Inputhashes.
- Produces: ComfyClient.acquire_output/OutputReference →StagedArtifact, InputArtifactRef. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_transport.py` definieren. Prüfbedingungen/Assertions: Traversal/Junction/Reparse/UNC/Redirect, wechselnde Source und Byteüberlauf fail-closed; kein Audio-/Video-Upload aus image-Route voraussetzen; Crossvolume Zielstaging; Originalhash bleibt. CM12: multipart image; UploadReceipt name/subfolder/type bindet Loader, tatsächliche Kollisionsumbenennung übernehmen; /view filename URL-encoden, keine Preview-/Channeltransformation für kanonische Bytes.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ComfyClient.acquire_output/OutputReference →StagedArtifact, InputArtifactRef umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_media_transport.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Traversal/Junction/Reparse/UNC/Redirect, wechselnde Source und Byteüberlauf fail-closed; kein Audio-/Video-Upload aus image-Route voraussetzen; Crossvolume Zielstaging; Originalhash bleibt. CM12: multipart image; UploadReceipt name/subfolder/type bindet Loader, tatsächliche Kollisionsumbenennung übernehmen; /view filename URL-encoden, keine Preview-/Channeltransformation für kanonische Bytes. 
**Risiko:** unkontrollierter Dateizugriff/Sourceveränderung.
**Rollback:** Staging quarantined, Originale und bestätigte Medien bleiben.

### T018 — Technische QC und rationale Medienzeit

- [ ] T018 [US1] {(OR-007)} {(TR-012)} Technische QC und rationale Medienzeit in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\media_quality.py`.

**ID / Titel / Ziel:** T018 / Technische QC und rationale Medienzeit. Ergebnis: ImportService.validate →ArtifactReceipt mit QC-/actual metadata.
**Abhängigkeiten / Gates:** T002, T008, T017. O03 QCgrenzen vor Test; technische QC keine visuelle Qualifikation.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\media_quality.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_quality.py`

**Interfaces:**
- Consumes: StagedArtifact, QualityProfile/ResourceProfile; verbindliche Fachverträge FP13 in domain-contracts.md.
- Produces: ImportService.validate →ArtifactReceipt mit QC-/actual metadata. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_quality.py` definieren. Prüfbedingungen/Assertions: Truncated/defekte Frames/Framezahl/FPS/Duration erkannt; Full Decode Pflicht; bewusst dunkel/static nach Profilregel; NaNmetadata/zu große Decodermenge kein PASS; rationale Frame/Samplegrenzen. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ImportService.validate →ArtifactReceipt mit QC-/actual metadata umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_media_quality.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Truncated/defekte Frames/Framezahl/FPS/Duration erkannt; Full Decode Pflicht; bewusst dunkel/static nach Profilregel; NaNmetadata/zu große Decodermenge kein PASS; rationale Frame/Samplegrenzen. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** ungültiger Clip trotz oberflächlicher Probe.
**Rollback:** quarantine/rejected, keine Librarybereitschaft.

### T019 — Canonical Import, Provenance und Ownership

- [ ] T019 [US1] {(FR-010)} {(FR-011)} {(TR-010)} {(OR-008)} Canonical Import, Provenance und Ownership in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\repositories\media_repository.py`.

**ID / Titel / Ziel:** T019 / Canonical Import, Provenance und Ownership. Ergebnis: ImportService.commit →ImportCommitResult(artifact, media_import_receipt), vollständige Herkunft.
**Abhängigkeiten / Gates:** T010, T011, T017, T018, T009. O02 Late-output und Gmigration; Origincontext neu erwerben.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\repositories\media_repository.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\video_router.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\import_service.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_canonical_import.py`

**Interfaces:**
- Consumes: ProjectCommitContext, published Artifact/QCreceipt und Jobintent; verbindliche Fachverträge FP18 in domain-contracts.md; Reviewloop-Vertrag L01.
- Produces: ImportService.commit →ImportCommitResult(artifact, media_import_receipt), vollständige Herkunft. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_canonical_import.py` definieren. Prüfbedingungen/Assertions: Doppelcallback gleicher Claim ein Media; anderer Hash Konflikt; Projekt A→B kein Bcommit; immutable Namen/Parent erhalten; failed QC/Cancelled late output keine automatische Timelinefreigabe. Cancel-vs-Catalog-CAS: davor kein Medium, danach Medium erhalten/Eligibility gesperrt/locally_cancelled. Manueller Import eigener lokaler Intent; ein Canonical-Medium je Projekt+Artifact. CM10/CM12: Ergebnisbeleg nach Success kann verzögert sein; ohne Pflichtreferenzen kein Import; spät vorhandener Output wird genau einmal übernommen. Gesamtgegenprüfung: FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP18-Teilnachweis hier nur gültiger Importclaim und Mediaidentität; Native-Run/ADD folgt T020. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für ImportService.commit →ImportCommitResult(artifact, media_import_receipt), vollständige Herkunft umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_canonical_import.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Doppelcallback gleicher Claim ein Media; anderer Hash Konflikt; Projekt A→B kein Bcommit; immutable Namen/Parent erhalten; failed QC/Cancelled late output keine automatische Timelinefreigabe. Cancel-vs-Catalog-CAS: davor kein Medium, danach Medium erhalten/Eligibility gesperrt/locally_cancelled. Manueller Import eigener lokaler Intent; ein Canonical-Medium je Projekt+Artifact. CM10/CM12: Ergebnisbeleg nach Success kann verzögert sein; ohne Pflichtreferenzen kein Import; spät vorhandener Output wird genau einmal übernommen. Gesamtgegenprüfung: FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP18-Teilnachweis hier nur gültiger Importclaim und Mediaidentität; Native-Run/ADD folgt T020. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. 
**Risiko:** falsches Projekt/overwrite/dangling Medien.
**Rollback:** lokale Saga repair/quarantine; akzeptierte Outputs erhalten.

### T020 — Durable ADD-Vektorsaga im Native-SigLIP-Raum

- [ ] T020 [US1] {(TR-006)} {(TR-010)} {(RR-002)} Durable ADD-Vektorsaga im Native-SigLIP-Raum in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\vector_store.py`.

**ID / Titel / Ziel:** T020 / Durable ADD-Vektorsaga im Native-SigLIP-Raum. Ergebnis: durable_add_embedding →VectorOperationReceipt mit Generation/Marker und Mapping; schmaler Native-SigLIP-Adapter produziert und persistiert den validierten AnalysisRun vor ADD.
**Abhängigkeiten / Gates:** T008, T019, T009. Q5 konkreter Writer-/Generationvertrag und isolierte Failuretests.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\vector_store.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\video_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\ai\video_specialist.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\clip_selector.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\vector_add_operation_outbox.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_vector_add_saga.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\native_embedding_adapter.py`

**Interfaces:**
- Consumes: validierter Native EmbeddingPayload+immutable AnalysisRun/Importclaim; verbindliche Fachverträge FP18 in domain-contracts.md.
- Produces: durable_add_embedding →VectorOperationReceipt mit Generation/Marker und Mapping; schmaler Native-SigLIP-Adapter produziert und persistiert den validierten AnalysisRun vor ADD. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_vector_add_saga.py` definieren. Prüfbedingungen/Assertions: Q5 Crashmatrix jede Publish/Mappinggrenze; genau ein Operationmarker/Vector/Mapping oder repair_required; alter Writerclone kann neuen Snapshot nicht überschreiben; Concurrent Nativeadd/Close/Compaction gatekoordiniert. Persistierten AnalysisRun zuerst prüfen; VideoRouter drain außerhalb Projektguard; endliche Writerdeadline bei Publishfehler; Compaction/Reindex bis qualifiziertem Remapvertrag gesperrt. Gesamtgegenprüfung: FP18: Reale Native-Erzeugung→persistierter Run→ADDreceipt→ready wird vor T026 abgenommen; kein selbstgebautes AnalysisRun-Fixture als alleiniger Integrationsnachweis. T031 bleibt nicht Voraussetzung für T026.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für durable_add_embedding →VectorOperationReceipt mit Generation/Marker und Mapping; schmaler Native-SigLIP-Adapter produziert und persistiert den validierten AnalysisRun vor ADD umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_vector_add_saga.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Q5 Crashmatrix jede Publish/Mappinggrenze; genau ein Operationmarker/Vector/Mapping oder repair_required; alter Writerclone kann neuen Snapshot nicht überschreiben; Concurrent Nativeadd/Close/Compaction gatekoordiniert. Persistierten AnalysisRun zuerst prüfen; VideoRouter drain außerhalb Projektguard; endliche Writerdeadline bei Publishfehler; Compaction/Reindex bis qualifiziertem Remapvertrag gesperrt. Gesamtgegenprüfung: FP18: Reale Native-Erzeugung→persistierter Run→ADDreceipt→ready wird vor T026 abgenommen; kein selbstgebautes AnalysisRun-Fixture als alleiniger Integrationsnachweis. T031 bleibt nicht Voraussetzung für T026. 
**Risiko:** Index-/Mappingkorruption; zentraler Writervertrag.
**Rollback:** Schreibgate sperren, konsistente Generation/reconciliation, kein blindes Readd.

### T021 — Recoveryinventar, Remoteactivity und Shutdown

- [ ] T021 [US2] {(OR-004)} {(RR-001)} {(RR-002)} Recoveryinventar, Remoteactivity und Shutdown in `C:\Users\david\Documents\Pb_studio_AMD_version\backend\recovery_runtime.py`.

**ID / Titel / Ziel:** T021 / Recoveryinventar, Remoteactivity und Shutdown. Ergebnis: JobActivitySnapshot und bounded quiesce/reconcile owner integration.
**Abhängigkeiten / Gates:** T013, T014, T019, T020. shared main/recovery Zone sequenziell; keine harten Normalprozesskills.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\recovery_runtime.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\main.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\recovery_adapters.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\recovery_generation.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\recovery_bootstrap.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\lifecycle.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_recovery_lifecycle.py`

**Interfaces:**
- Consumes: O02 Shutdownpolicy, durable Attempts/Import-/Vectorreceipts; verbindliche Fachverträge FP08, FP11 in domain-contracts.md; Reviewloop-Vertrag L01.
- Produces: JobActivitySnapshot und bounded quiesce/reconcile owner integration. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_recovery_lifecycle.py` definieren. Prüfbedingungen/Assertions: Snapshot wartet nur lokale bounded Commits, nicht Remoteende; WPFclose mit Runningjob richtige Detached/Pausestatuspersistenz; Sidecars/Ownmedia inventarisiert; Restore missingoutput ehrlich, kein alter Epochcommit. Restore prüft Operation/Media/Space/Vectorhash, nicht bloß IDs; vertauschte Media-ID/Marker/Bytes fail-closed. Diskfull/RecoveryBusy/Writerdeadline ohne unbounded join. CM05: lifecycle prepare-close friert Dispatch ein und quittiert durable Handoff vor Stop; Zombie-Watcher zählt lokale Commit-/Quiesceaktivität, harter Crash benötigt Write-ahead-Recovery, Comfy außerhalb PB-Killbaum. Gesamtgegenprüfung: FP08: Snapshot vor Send, Remote führt aus, anschließend Restore optional mit leerer History: null weitere POST/prompt. Verlorener Cancel/WPF-Neustart ebenfalls; Generation/Cursorreset und sichtbarer blockierter Zustand. FP11: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für JobActivitySnapshot und bounded quiesce/reconcile owner integration umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_recovery_lifecycle.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Snapshot wartet nur lokale bounded Commits, nicht Remoteende; WPFclose mit Runningjob richtige Detached/Pausestatuspersistenz; Sidecars/Ownmedia inventarisiert; Restore missingoutput ehrlich, kein alter Epochcommit. Restore prüft Operation/Media/Space/Vectorhash, nicht bloß IDs; vertauschte Media-ID/Marker/Bytes fail-closed. Diskfull/RecoveryBusy/Writerdeadline ohne unbounded join. CM05: lifecycle prepare-close friert Dispatch ein und quittiert durable Handoff vor Stop; Zombie-Watcher zählt lokale Commit-/Quiesceaktivität, harter Crash benötigt Write-ahead-Recovery, Comfy außerhalb PB-Killbaum. Gesamtgegenprüfung: FP08: Snapshot vor Send, Remote führt aus, anschließend Restore optional mit leerer History: null weitere POST/prompt. Verlorener Cancel/WPF-Neustart ebenfalls; Generation/Cursorreset und sichtbarer blockierter Zustand. FP11: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T016 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. 
**Risiko:** Recoveryrollback oder unbounded Shutdown.
**Rollback:** Dispatch gesperrt, gültige Recoverygeneration erhalten.

### T022 — PB REST-, Snapshot- und SSE-Jobverträge

- [ ] T022 [US2] {(TR-002)} {(OR-006)} PB REST-, Snapshot- und SSE-Jobverträge in `C:\Users\david\Documents\Pb_studio_AMD_version\backend\dependencies.py`.

**ID / Titel / Ziel:** T022 / PB REST-, Snapshot- und SSE-Jobverträge. Ergebnis: PB Routes D, LogicalJobSnapshot und ProviderJobEvent.
**Abhängigkeiten / Gates:** T014, T019, T021. OpenAPI-/Consumervertrag; Gapi vor IApiClient-Änderung.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\dependencies.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\events_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\main.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\comfyui_router.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\jobs_router.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\comfyui_schemas.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\jobs_schemas.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_jobs_api.py`

**Interfaces:**
- Consumes: Repository/control/Registry; vorhandener Owner-/Projektguard; verbindliche Fachverträge FP14, FP15 in domain-contracts.md; Reviewloop-Vertrag L01; Reviewloop-Vertrag L05.
- Produces: PB Routes D, LogicalJobSnapshot und ProviderJobEvent. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_jobs_api.py` definieren. Prüfbedingungen/Assertions: 202durable Job ohne minutenlange Request; duplicate key gleicher/anderer Payload 200/409; Scopeowner und erwartete Revision; >500 verlorene Events durch Snapshot heilbar; sampling100 nicht ready. Echte App/OpenAPI enthält Settings/Register/Enable/Batchcreate/Priority/Reorder/manualImport-Routes; WPF ausschließlich PB; Scope/CAS/Idempotencytests. CM01/CM02/CM03/CM06: eigener provider_job_changed DTO/Filter, ErrorEnvelope und kurze Controlrequests; by-request/changes/prepare-close registriert; konsistente Pagination+durabler Catch-up, Cursorreset410. CloseReceipt-GET und guarded abort-close registriert; Job-/Batchprojektionen im gleichen Snapshot/Changefeed. Gesamtgegenprüfung: FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP15: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T023 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L05: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T024, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für PB Routes D, LogicalJobSnapshot und ProviderJobEvent umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_jobs_api.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** 202durable Job ohne minutenlange Request; duplicate key gleicher/anderer Payload 200/409; Scopeowner und erwartete Revision; >500 verlorene Events durch Snapshot heilbar; sampling100 nicht ready. Echte App/OpenAPI enthält Settings/Register/Enable/Batchcreate/Priority/Reorder/manualImport-Routes; WPF ausschließlich PB; Scope/CAS/Idempotencytests. CM01/CM02/CM03/CM06: eigener provider_job_changed DTO/Filter, ErrorEnvelope und kurze Controlrequests; by-request/changes/prepare-close registriert; konsistente Pagination+durabler Catch-up, Cursorreset410. CloseReceipt-GET und guarded abort-close registriert; Job-/Batchprojektionen im gleichen Snapshot/Changefeed. Gesamtgegenprüfung: FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. FP15: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T023 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L05: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T024, kein vorzeitiger Integrations-PASS. 
**Risiko:** APIbruch oder fehlende UIevents.
**Rollback:** neue Routes disable, alte API unverändert; persistente Jobs erhalten.

### T023 — WPF Verbindung, Settings und Installationshilfe

- [ ] T023 [US1] {(FR-002)} {(FR-016)} {(OR-006)} WPF Verbindung, Settings und Installationshilfe in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs`.

**ID / Titel / Ziel:** T023 / WPF Verbindung, Settings und Installationshilfe. Ergebnis: Settingsflow und DiscoverySnapshot-basierter StatusDTO.
**Abhängigkeiten / Gates:** T007, T022. Gapi; Releasebuild+native WPFtests+sichtbarer Flow.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\IApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\SettingsViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\SettingsView.xaml` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\App.xaml.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Models\ComfyStatusResponse.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ComfySettingsTests.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\installation.md`

**Interfaces:**
- Consumes: GET comfyui/status/capabilities und ConfigManager owner; verbindliche Fachverträge FP15 in domain-contracts.md.
- Produces: Settingsflow und DiscoverySnapshot-basierter StatusDTO. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ComfySettingsTests.cs` definieren. Prüfbedingungen/Assertions: Offline/Missinginstallation verständlich; getrennte readinessstufen; URL next_job statt running umbiegen; Backend URLowner, WPF nur Anzeige; kein zweites Frontend/Grapheditor. Gesamtgegenprüfung: FP15: Gleiche numerische Revision nach Neustart, zwei Settingsfenster, externe Edit, Write/Replacefehler und Watcher/PATCH-Rennen: Konflikt ohne Teilmutation; Publish erst nach Commit; UI-Erfolg nur bestätigtes Receipt.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Settingsflow und DiscoverySnapshot-basierter StatusDTO umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-WPF; Test PBStudio.UI.Tests/ComfySettingsTests.cs.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Offline/Missinginstallation verständlich; getrennte readinessstufen; URL next_job statt running umbiegen; Backend URLowner, WPF nur Anzeige; kein zweites Frontend/Grapheditor. Gesamtgegenprüfung: FP15: Gleiche numerische Revision nach Neustart, zwei Settingsfenster, externe Edit, Write/Replacefehler und Watcher/PATCH-Rennen: Konflikt ohne Teilmutation; Publish erst nach Commit; UI-Erfolg nur bestätigtes Receipt. 
**Risiko:** WPFAPIbruch/irreführend bereit.
**Rollback:** neuer Bereich Featureflag off, vorhandene Settings weiter.

### T024 — WPF Workflowlibrary und manuelle Generation

- [ ] T024 [US1] {(FR-003)} {(FR-009)} {(FR-016)} WPF Workflowlibrary und manuelle Generation in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\VideoLibraryViewModel.cs`.

**ID / Titel / Ziel:** T024 / WPF Workflowlibrary und manuelle Generation. Ergebnis: Workflowlibrary integriert in vorhandene Navigation; Generate-Aktion.
**Abhängigkeiten / Gates:** T023, T005, T019. Gapi; UIflowdefinition keine zusätzliche Tabanzahl behaupten.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\VideoLibraryViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\VideoLibraryView.xaml` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\IApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\App.xaml.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Models\ProviderApiOutcome.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\PendingProviderIntentStore.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\WorkflowLibraryViewModel.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\WorkflowLibraryView.xaml`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\WorkflowLibraryTests.cs`

**Interfaces:**
- Consumes: WorkflowRegistry/PB Routes, CreateJobRequest; verbindliche Fachverträge FP14 in domain-contracts.md; Reviewloop-Vertrag L01; Reviewloop-Vertrag L05.
- Produces: Workflowlibrary integriert in vorhandene Navigation; Generate-Aktion. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\WorkflowLibraryTests.cs` definieren. Prüfbedingungen/Assertions: Revision/Enable/Disable/Register/typed Promptinputs; In Comfy bearbeiten→neue Revision; Jobstart local-only; Autoimport und Autoanalyse getrennt; keine ungefragten Downloads. CM01/CM06: PendingIntentStore vor POST dauerhaft; verlorenes202 plus WPF-Neustart gleicher Schlüssel, explizite Stringenum-/UUID-/null-Wirefixtures; eigener requestbezogener ApiOutcome. Gesamtgegenprüfung: FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L05: Zwei konkurrierende Toggle, verlorene Antwort, identische Wiederholung, Reopen: stale409; Bundlehash unverändert.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Workflowlibrary integriert in vorhandene Navigation; Generate-Aktion umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-WPF; Test PBStudio.UI.Tests/WorkflowLibraryTests.cs.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Revision/Enable/Disable/Register/typed Promptinputs; In Comfy bearbeiten→neue Revision; Jobstart local-only; Autoimport und Autoanalyse getrennt; keine ungefragten Downloads. CM01/CM06: PendingIntentStore vor POST dauerhaft; verlorenes202 plus WPF-Neustart gleicher Schlüssel, explizite Stringenum-/UUID-/null-Wirefixtures; eigener requestbezogener ApiOutcome. Gesamtgegenprüfung: FP14: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T025 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. L05: Zwei konkurrierende Toggle, verlorene Antwort, identische Wiederholung, Reopen: stale409; Bundlehash unverändert. 
**Risiko:** Tabflut/falsche Defaults/Livegraphmutation.
**Rollback:** Generation/UIflag off, native Library weiter.

### T025 — WPF Jobs, Queue-Reorder und Herkunftsfilter

- [ ] T025 [US2] {(FR-013)} {(FR-016)} {(OR-006)} WPF Jobs, Queue-Reorder und Herkunftsfilter in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\SSEClient.cs`.

**ID / Titel / Ziel:** T025 / WPF Jobs, Queue-Reorder und Herkunftsfilter. Ergebnis: Job-/Queueansicht, StateService und stabile Navigations-ID.
**Abhängigkeiten / Gates:** T023, T024, T014. Releasebuild sequenziell, sichtbare GUIabnahme.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\MainWindow.xaml.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\PythonBridgeService.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\SSEClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\ProductionViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\ProductionView.xaml` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\MainViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\VideoLibraryViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\App.xaml.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\IApiClient.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Models\ProviderJobEvent.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Models\ProviderJobResponse.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ProviderJobStateService.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ProviderJobStateTests.cs`

**Interfaces:**
- Consumes: ProviderJobEvent/LogicalJobSnapshot/PB Jobcontrol; verbindliche Fachverträge FP14 in domain-contracts.md; Reviewloop-Vertrag L01.
- Produces: Job-/Queueansicht, StateService und stabile Navigations-ID. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ProviderJobStateTests.cs` definieren. Prüfbedingungen/Assertions: Reconnectgap Snapshot korrekt; project/revisionstale Event ignoriert; Dispose kein Duplicate; indeterminate progress; undispatched reorder CAS, running immutable; Imported/Generated/Processed/Variants/Favorites/Used/Unused/BadRating. Reale App-DI/Navigation statt manuell konstruiertem VM; PBcontrols und Snapshot erreichbar. CM02–CM06: eigener Providerparser/nullable Progress; view_generation+Snapshot/Changefeed-Catch-up; job_stream health getrennt, Idlewatchdog; CloseReceipt vor BeginShutdown/StopAsync, niemals Comfy-Prozessbaumkill. MainWindow.Closing vor OnExit kontrolliert abbrechbar/reentrancygeschützt; Closeabort löst nur eigenen Freeze nach Reconciliation. Gesamtgegenprüfung: FP14: Katalog/Schema/WPF/Python-Goldenfixtures enthalten denselben Event/Identity/Outcomevertrag; Job- und Batchänderung sowie unbekannte Pflichtsemantik prüfen. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Job-/Queueansicht, StateService und stabile Navigations-ID umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-WPF; Test PBStudio.UI.Tests/ProviderJobStateTests.cs.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Reconnectgap Snapshot korrekt; project/revisionstale Event ignoriert; Dispose kein Duplicate; indeterminate progress; undispatched reorder CAS, running immutable; Imported/Generated/Processed/Variants/Favorites/Used/Unused/BadRating. Reale App-DI/Navigation statt manuell konstruiertem VM; PBcontrols und Snapshot erreichbar. CM02–CM06: eigener Providerparser/nullable Progress; view_generation+Snapshot/Changefeed-Catch-up; job_stream health getrennt, Idlewatchdog; CloseReceipt vor BeginShutdown/StopAsync, niemals Comfy-Prozessbaumkill. MainWindow.Closing vor OnExit kontrolliert abbrechbar/reentrancygeschützt; Closeabort löst nur eigenen Freeze nach Reconciliation. Gesamtgegenprüfung: FP14: Katalog/Schema/WPF/Python-Goldenfixtures enthalten denselben Event/Identity/Outcomevertrag; Job- und Batchänderung sowie unbekannte Pflichtsemantik prüfen. L01: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T026, kein vorzeitiger Integrations-PASS. 
**Risiko:** falscher Finalstatus oder Indexnavigation.
**Rollback:** neue Jobansicht aus, durable Status bleibt backendlesbar.

### T026 — Integrierten lokalen Generation-MVP abnehmen

- [ ] T026 [US1] {(FR-009)} {(FR-010)} {(RR-004)} {(RR-005)} Integrierten lokalen Generation-MVP abnehmen in `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\evidence\g3-media-flow.md`.

**ID / Titel / Ziel:** T026 / Integrierten lokalen Generation-MVP abnehmen. Ergebnis: G3 und Qualified-Profile-Receipt; erster eigener Produktfreigabekandidat.
**Abhängigkeiten / Gates:** T007, T009, T020, T021, T025. O03 echte Medien/Humanquality; .completed vor QC, .qc-passed erst nach T045; Gapi vor öffentlicher Vertragsänderung, Gmigration vor persistierter Timeline-/Mappingerweiterung.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\rendering\render_service.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\rendering\preview_renderer.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\ProductionViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\IApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\render_schemas.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\evidence\g3-media-flow.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\scripts\dev\comfyui_media_acceptance.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_acceptance_contract.py`

**Interfaces:**
- Consumes: G1 und alle verpflichtenden P2-Belege sowie T023–T025; T027 ist nachgelagerter P3b-Ausbau, keine MVPvoraussetzung; verbindliche Fachverträge FP13, FP18 in domain-contracts.md; Reviewloop-Vertrag L01.
- Produces: G3 und Qualified-Profile-Receipt; erster eigener Produktfreigabekandidat. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_media_acceptance_contract.py` definieren. Prüfbedingungen/Assertions: Echter autorisierter Flow Clip→Library→native Analyse/SigLIP/FAISS→Director→Timeline→Preview→AMF→Full Decode/Reopen; Originalhashes unverändert; Cancel/Retry/Restart sichtbar; ein T2VProfil kein I2Vnachweis. Gwire W01–W29 und W31–W32 mit Produktadaptern und W30 echter sichtbarer WPF↔PB↔Comfy-Flow zusätzlich verpflichtend; Dokument-/Fixturepass ist kein Gwirepass. Gesamtgegenprüfung: FP13: Freigegebene SDR limited/full und10bit/HDR-Fälle korrekt nach Profil behandeln oder sichtbar abweisen; Preview/Final mit Farbreferenz vergleichen. Messgrenzen O03 offen. Full Decode allein kein Farbbeweis. FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: Vier Autoimport/Autoanalyse-Kombinationen, Restart und spätere Freigaben; keine ungewollte Arbeit, keine Dauerschleife, kein neuer Generierungsattempt.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für G3 und Qualified-Profile-Receipt; erster eigener Produktfreigabekandidat umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_media_acceptance_contract.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Echter autorisierter Flow Clip→Library→native Analyse/SigLIP/FAISS→Director→Timeline→Preview→AMF→Full Decode/Reopen; Originalhashes unverändert; Cancel/Retry/Restart sichtbar; ein T2VProfil kein I2Vnachweis. Gwire W01–W29 und W31–W32 mit Produktadaptern und W30 echter sichtbarer WPF↔PB↔Comfy-Flow zusätzlich verpflichtend; Dokument-/Fixturepass ist kein Gwirepass. Gesamtgegenprüfung: FP13: Freigegebene SDR limited/full und10bit/HDR-Fälle korrekt nach Profil behandeln oder sichtbar abweisen; Preview/Final mit Farbreferenz vergleichen. Messgrenzen O03 offen. Full Decode allein kein Farbbeweis. FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. L01: Vier Autoimport/Autoanalyse-Kombinationen, Restart und spätere Freigaben; keine ungewollte Arbeit, keine Dauerschleife, kein neuer Generierungsattempt. 
**Risiko:** Tests/build als Nutzerabnahme ausgeben.
**Rollback:** Profil unqualified, akzeptierte Medien behalten.

### T027 — Varianten, Regenerate und weitere Inputfamilien

- [ ] T027 [US3] {(FR-009)} {(FR-011)} {(FR-012)} Varianten, Regenerate und weitere Inputfamilien in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\repository.py`.

**ID / Titel / Ziel:** T027 / Varianten, Regenerate und weitere Inputfamilien. Ergebnis: Derivation-DAG und geprüfte Input-/Variant-Profile.
**Abhängigkeiten / Gates:** T026, T019. Profile familyweise abnehmen; nicht vorhandene Inputs unavailable.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\repository.py` — zukünftige Datei aus Vorgängerpaket
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\VideoLibraryViewModel.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\derivations.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_variants.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\reference\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\i2v\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\i2v\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\i2v\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\i2v\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\v2v\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\v2v\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\v2v\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\v2v\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\reference\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\reference\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\generation\reference\profile-receipt.json`

**Interfaces:**
- Consumes: Qualified Pilotbundle, InputArtifactRef, immutable Job-/Artifactrecords; verbindliche Fachverträge FP17 in domain-contracts.md.
- Produces: Derivation-DAG und geprüfte Input-/Variant-Profile. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_variants.py` definieren. Prüfbedingungen/Assertions: Neue Seed/Prompt/Model/Workflow/Quality/Motionvariation neuer Intent/Child; Parent unverändert; I2V/V2V/Reference je eigenes tatsächliches Profil; Inputroles/maxcount/crop/LoRA gebunden; keine automatische Timelineübernahme. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP17: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T040 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Derivation-DAG und geprüfte Input-/Variant-Profile umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_variants.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Neue Seed/Prompt/Model/Workflow/Quality/Motionvariation neuer Intent/Child; Parent unverändert; I2V/V2V/Reference je eigenes tatsächliches Profil; Inputroles/maxcount/crop/LoRA gebunden; keine automatische Timelineübernahme. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP17: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T040 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Provenanceverlust/Parentoverwrite.
**Rollback:** Parent weiter verwenden, neue Profile deaktivieren.

### T028 — Upscale als qualifiziertes Derivat

- [ ] T028 [US3] {(FR-012)} {(TR-012)} Upscale als qualifiziertes Derivat in `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\upscale\manifest.json`.

**ID / Titel / Ziel:** T028 / Upscale als qualifiziertes Derivat. Ergebnis: qualified media.upscale WorkflowBundle/ArtifactReceipt.
**Abhängigkeiten / Gates:** T027. G4 einzelne Operation Real-Media.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\upscale\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\upscale\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_upscale_contract.py`

**Interfaces:**
- Consumes: Derivation, MediaQC, ResourceProfile; verbindliche Fachverträge FP13 in domain-contracts.md.
- Produces: qualified media.upscale WorkflowBundle/ArtifactReceipt. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_upscale_contract.py` definieren. Prüfbedingungen/Assertions: Reale Targetresolution/Color/Codec/Dauer gemessen, Childhash/Parentlink korrekt; Parentbytes bleiben; Artefakt-/Qualitygate; kein Name→1080pClaim. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für qualified media.upscale WorkflowBundle/ArtifactReceipt umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_upscale_contract.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Reale Targetresolution/Color/Codec/Dauer gemessen, Childhash/Parentlink korrekt; Parentbytes bleiben; Artefakt-/Qualitygate; kein Name→1080pClaim. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Qualitätsverlust/unpassende Sourcegröße.
**Rollback:** Parent auswählen; Upscaleprofil unqualified.

### T029 — Interpolation und rationales FPS-Derivat

- [ ] T029 [US3] {(FR-012)} {(TR-012)} Interpolation und rationales FPS-Derivat in `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\interpolate\manifest.json`.

**ID / Titel / Ziel:** T029 / Interpolation und rationales FPS-Derivat. Ergebnis: qualified media.interpolate Bundle/Childartifact.
**Abhängigkeiten / Gates:** T027, T018. G4 FPS-/Qualityprofil abnehmen.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\interpolate\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\interpolate\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_interpolation_contract.py`

**Interfaces:**
- Consumes: Derivation/Timebase/QCprofile; verbindliche Fachverträge FP13 in domain-contracts.md.
- Produces: qualified media.interpolate Bundle/Childartifact. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_interpolation_contract.py` definieren. Prüfbedingungen/Assertions: Rationale In-/OutFPS, tatsächliche Frames/PTS/Duration, AVsync; 23.976/29.97 kein kumulativer Drift; Parent und Originalaudio bleiben; Flowartefakte bewertet. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für qualified media.interpolate Bundle/Childartifact umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_interpolation_contract.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Rationale In-/OutFPS, tatsächliche Frames/PTS/Duration, AVsync; 23.976/29.97 kein kumulativer Drift; Parent und Originalaudio bleiben; Flowartefakte bewertet. Gesamtgegenprüfung: FP13: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T026 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Zeitdrift oder Ghosting.
**Rollback:** Parent verwenden.

### T030 — Begrenzter Reshot und Kontinuitätsprüfung

- [ ] T030 [US3] {(FR-012)} {(TR-011)} {(TR-012)} Begrenzter Reshot und Kontinuitätsprüfung in `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\reshot\manifest.json`.

**ID / Titel / Ziel:** T030 / Begrenzter Reshot und Kontinuitätsprüfung. Ergebnis: qualified media.reshot Bundle mit Window-/Handlevertrag.
**Abhängigkeiten / Gates:** T027, T018. G4 Window/RAM/Continuity-Humanquality.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\derivations.py` — geplant; durch Vorgänger erstellt

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\reshot\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\postprocess\reshot\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_reshot_contract.py`

**Interfaces:**
- Consumes: Derivation/References und bounded Transport/QC; verbindliche Fachverträge FP17 in domain-contracts.md.
- Produces: qualified media.reshot Bundle mit Window-/Handlevertrag. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_reshot_contract.py` definieren. Prüfbedingungen/Assertions: 5sReshot in Stundenquelle dekodiert nur Range+Handles; Full-source-node ungeeignet/fail; Übergänge/Unchanged-Bereich gemäß Encodingvertrag; Parentbytes unverändert, Herkunft vollständig. Gesamtgegenprüfung: FP17: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T040 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für qualified media.reshot Bundle mit Window-/Handlevertrag umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_reshot_contract.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** 5sReshot in Stundenquelle dekodiert nur Range+Handles; Full-source-node ungeeignet/fail; Übergänge/Unchanged-Bereich gemäß Encodingvertrag; Parentbytes unverändert, Herkunft vollständig. Gesamtgegenprüfung: FP17: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T040 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Full-source-RAM/OOM/Nahtbruch.
**Rollback:** Parent und unveränderte Timeline verwenden.

### T031 — Native Stageadapter und Consumerdurchleitung

- [ ] T031 [US3] {(FR-005)} {(TR-005)} {(TR-007)} Native Stageadapter und Consumerdurchleitung in `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\audio_router.py`.

**ID / Titel / Ziel:** T031 / Native Stageadapter und Consumerdurchleitung. Ergebnis: Native capabilityadapter →AnalysisRun/StageResult.
**Abhängigkeiten / Gates:** T008, T009, T026. Gapi falls öffentliche DTOs ändern; keine separator.py-Änderung.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\audio_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\video_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\pacing_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\audio_schemas.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\video_schemas.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\services\pacing_service.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\advanced_pacing_engine.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\post_processor.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\loader_cache.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\cross_modal_projector.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\native_adapters.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_native_stage_wiring.py`

**Interfaces:**
- Consumes: bestehende Schemas/Stageprovenance und gemeinsame Validatoren; verbindliche Fachverträge FP01, FP02, FP06, FP07, FP18 in domain-contracts.md.
- Produces: Native capabilityadapter →AnalysisRun/StageResult. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_native_stage_wiring.py` definieren. Prüfbedingungen/Assertions: Feldwerte Router→AppState→Pacing→DTO→ViewModel tatsächlich durchgeleitet; kick_times/energy_curve/structure_segments korrekt; missing/derived/partial ehrlich; ohne explizite Aktivierung aktiver Nativecache unverändert. Gesamtgegenprüfung: FP01: Peak bei Sourcezeit40s in Range[30,50) eines120sMediums bleibt nach Service→Engine an40s; mehrere Hopraten, Chunkgrenzen und Coverage-Lücken prüfen. Toleranz O03 offen. FP02: Nativebeats A, externe Energie B, Drums C: A→A2 verändert weder B/C noch deren Provenance; C unavailable führt nur zur ausdrücklich erlaubten Degradation. Reload liefert denselben Snapshot. FP06: Warmen Cache A füllen, B mit gleichem Source/Modell aber anderem Range/Sampling aktivieren: alle Brain/Pacingconsumer liefern B; Rückwahl A liefert A. Vergleich ohne Aktivierung verändert A nicht; Prozess/Restart prüfen. FP07: Mindestens ein gültiger und ein fehlgeschlagener Captionframe: Tags und Lücken bleiben bis API/WPF/Director sichtbar. Vollfehler und valide leere Caption unterscheidbar. FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Native capabilityadapter →AnalysisRun/StageResult umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_native_stage_wiring.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Feldwerte Router→AppState→Pacing→DTO→ViewModel tatsächlich durchgeleitet; kick_times/energy_curve/structure_segments korrekt; missing/derived/partial ehrlich; ohne explizite Aktivierung aktiver Nativecache unverändert. Gesamtgegenprüfung: FP01: Peak bei Sourcezeit40s in Range[30,50) eines120sMediums bleibt nach Service→Engine an40s; mehrere Hopraten, Chunkgrenzen und Coverage-Lücken prüfen. Toleranz O03 offen. FP02: Nativebeats A, externe Energie B, Drums C: A→A2 verändert weder B/C noch deren Provenance; C unavailable führt nur zur ausdrücklich erlaubten Degradation. Reload liefert denselben Snapshot. FP06: Warmen Cache A füllen, B mit gleichem Source/Modell aber anderem Range/Sampling aktivieren: alle Brain/Pacingconsumer liefern B; Rückwahl A liefert A. Vergleich ohne Aktivierung verändert A nicht; Prozess/Restart prüfen. FP07: Mindestens ein gültiger und ein fehlgeschlagener Captionframe: Tags und Lücken bleiben bis API/WPF/Director sichtbar. Vollfehler und valide leere Caption unterscheidbar. FP18: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T020 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Producer ohne Consumer/Api-Doppelstruktur.
**Rollback:** Nativepointer erhalten, neue Adapterdisable.

### T032 — Alternative Beat-/Downbeat-/Timingprovider

- [ ] T032 [US3] {(FR-006)} {(FR-005)} {(RR-003)} Alternative Beat-/Downbeat-/Timingprovider in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_timing.py`.

**ID / Titel / Ziel:** T032 / Alternative Beat-/Downbeat-/Timingprovider. Ergebnis: capabilityweise Timing-StageResults+Benchmarkreceipts.
**Abhängigkeiten / Gates:** T002, T031. G5 jede in O gelistete Timingfähigkeit einzeln; kein stilles Nativeersetzen.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_timing.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\timing\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_audio_timing.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\timing\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\timing\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\timing\profile-receipt.json`

**Interfaces:**
- Consumes: Nativeadapter/Qualityprofile/SharedAdmission.
- Produces: capabilityweise Timing-StageResults+Benchmarkreceipts. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_audio_timing.py` definieren. Prüfbedingungen/Assertions: BPM/Tempoabschnitte/Beatphase/Downbeat/Grid/Onsets/Transienten mit Sourceoffset und Chunknähte; Half-/Doubletempo getrennt; unabhängige Labels; kein BPMallein-Abnahme. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für capabilityweise Timing-StageResults+Benchmarkreceipts umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_audio_timing.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** BPM/Tempoabschnitte/Beatphase/Downbeat/Grid/Onsets/Transienten mit Sourceoffset und Chunknähte; Half-/Doubletempo getrennt; unabhängige Labels; kein BPMallein-Abnahme. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Jede Capabilityfamilie aus Plan O einzeln qualifizieren; bei fehlendem Profil unavailable/unverified, keine pauschale Familiensuccessmeldung.
**Risiko:** musikalisch falsche Trigger bei formalem PASS.
**Rollback:** aktive Native-Timingrevision auswählen.

### T033 — Stems und Drumtriggerprovider

- [ ] T033 [US3] {(FR-006)} {(FR-007)} {(RR-003)} Stems und Drumtriggerprovider in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_stems_drums.py`.

**ID / Titel / Ziel:** T033 / Stems und Drumtriggerprovider. Ergebnis: StageResults+StemArtifactrollen+Drumtiming.
**Abhängigkeiten / Gates:** T002, T031, T019. G5 Rollen/Drumpräzision/Delay jede Fähigkeit.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_stems_drums.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\stems\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_stems_drums.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\stems\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\stems\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\stems\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\drums\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\drums\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\drums\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\drums\profile-receipt.json`

**Interfaces:**
- Consumes: Nativeadapter, Input-/Artifactvertrag; locked separator nur außen wrappen.
- Produces: StageResults+StemArtifactrollen+Drumtiming. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_stems_drums.py` definieren. Prüfbedingungen/Assertions: Drums/Bass/Other/Vocals und zusätzliche Rollen tatsächlich verfügbar; SR/Channels/Samplecount/Delayalignment, Leakage und Triggerqualität getrennt; Cachefingerprint verhindert unnötige Separation. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für StageResults+StemArtifactrollen+Drumtiming umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_stems_drums.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Drums/Bass/Other/Vocals und zusätzliche Rollen tatsächlich verfügbar; SR/Channels/Samplecount/Delayalignment, Leakage und Triggerqualität getrennt; Cachefingerprint verhindert unnötige Separation. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Jede Capabilityfamilie aus Plan O einzeln qualifizieren; bei fehlendem Profil unavailable/unverified, keine pauschale Familiensuccessmeldung.
**Risiko:** misaligned Stems oder False-Drums.
**Rollback:** Nativeprovider/stems erhalten; Comfyresult nicht aktivieren.

### T034 — Energie, Struktur, Harmonie und Longmixprovider

- [ ] T034 [US3] {(FR-006)} {(TR-005)} {(RR-003)} Energie, Struktur, Harmonie und Longmixprovider in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_features.py`.

**ID / Titel / Ziel:** T034 / Energie, Struktur, Harmonie und Longmixprovider. Ergebnis: familyweise Feature-/Harmony-/Longmix-StageResults und qualify matrix.
**Abhängigkeiten / Gates:** T002, T031, T032. G5 je einzelne Fähigkeit, keine pauschale Sammelfreigabe.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\audio_features.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\features\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_audio_features.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\energy\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\energy\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\energy\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\energy\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\structure\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\structure\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\structure\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\structure\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\harmony\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\harmony\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\harmony\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\harmony\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\longmix\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\longmix\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\longmix\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\audio\longmix\profile-receipt.json`

**Interfaces:**
- Consumes: Native-Timing/Qualityprofile/Chunkcontracts; verbindliche Fachverträge FP01 in domain-contracts.md.
- Produces: familyweise Feature-/Harmony-/Longmix-StageResults und qualify matrix. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_audio_features.py` definieren. Prüfbedingungen/Assertions: RMS/Peak/LUFS/Bandenergie skalengültig; neutrale Struktur bei unsicherem Drop; Key/Mode/Camelotversion/Keychange; annotierte Mixblenden/equalBPM/Tempoänderungen; bounded Speicher. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP01: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für familyweise Feature-/Harmony-/Longmix-StageResults und qualify matrix umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_audio_features.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** RMS/Peak/LUFS/Bandenergie skalengültig; neutrale Struktur bei unsicherem Drop; Key/Mode/Camelotversion/Keychange; annotierte Mixblenden/equalBPM/Tempoänderungen; bounded Speicher. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP01: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. Jede Capabilityfamilie aus Plan O einzeln qualifizieren; bei fehlendem Profil unavailable/unverified, keine pauschale Familiensuccessmeldung.
**Risiko:** semantisch erfundene Struktur oder lange Mix-OOM.
**Rollback:** Nativeaktive Stages zurückwählen.

### T035 — Alternative Caption-/Inhalts-/Moodprovider

- [ ] T035 [US3] {(FR-008)} {(TR-005)} {(RR-003)} Alternative Caption-/Inhalts-/Moodprovider in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\video_contents.py`.

**ID / Titel / Ziel:** T035 / Alternative Caption-/Inhalts-/Moodprovider. Ergebnis: Video-Contents-StageResults und Prompt-/Modellprofile.
**Abhängigkeiten / Gates:** T002, T031. G5 je Inhaltsfähigkeit und menschliche Qualität.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\video_contents.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\contents\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_video_contents.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\contents\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\contents\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\contents\profile-receipt.json`

**Interfaces:**
- Consumes: Nativeadapter/Resultvalidator/Holdout; verbindliche Fachverträge FP07 in domain-contracts.md.
- Produces: Video-Contents-StageResults und Prompt-/Modellprofile. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_video_contents.py` definieren. Prüfbedingungen/Assertions: Caption/Tags/Person/Objekt/Umgebung/Licht/Farbe/Style/Mood/visuelle Energie gegen menschliche Referenz; scope Frames/Scene/Asset; Unknown statt Halluzination; Fehler einer Stage kein Gesamtausfall. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP07: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Video-Contents-StageResults und Prompt-/Modellprofile umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_video_contents.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Caption/Tags/Person/Objekt/Umgebung/Licht/Farbe/Style/Mood/visuelle Energie gegen menschliche Referenz; scope Frames/Scene/Asset; Unknown statt Halluzination; Fehler einer Stage kein Gesamtausfall. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Gesamtgegenprüfung: FP07: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T031 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. Jede Capabilityfamilie aus Plan O einzeln qualifizieren; bei fehlendem Profil unavailable/unverified, keine pauschale Familiensuccessmeldung.
**Risiko:** Halluzinationen beeinflussen Director.
**Rollback:** Nativeaccepted Inhaltsrevision behalten.

### T036 — Szenen, Motion, Technik und Qualityprovider

- [ ] T036 [US3] {(FR-008)} {(TR-005)} {(OR-007)} Szenen, Motion, Technik und Qualityprovider in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\video_measurements.py`.

**ID / Titel / Ziel:** T036 / Szenen, Motion, Technik und Qualityprovider. Ergebnis: Video-Measurement-StageResults+Kalibrationsrevisionen.
**Abhängigkeiten / Gates:** T002, T031, T018. G5 jede Fähigkeit; Feldskalen nicht heimlich ändern.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\video_measurements.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\measurements\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_video_measurements.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\scenes\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\scenes\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\scenes\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\scenes\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\motion\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\motion\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\motion\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\motion\profile-receipt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\quality\manifest.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\quality\api_prompt.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\quality\test-fixture.json`
- `C:\Users\david\Documents\Pb_studio_AMD_version\workflows\video\quality\profile-receipt.json`

**Interfaces:**
- Consumes: Nativeprobe/Motioncontract/Qualityprofile.
- Produces: Video-Measurement-StageResults+Kalibrationsrevisionen. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_video_measurements.py` definieren. Prüfbedingungen/Assertions: SceneF1/Boundaries/VFR; Flow/Intensity/Direction/Camera mit Sampling/Normunit; technische Codec/FPS/Dauer gemessen; Sharp/Blur/Noise/Compression/Freeze/AIartefakthinweise getrennt mit Ausnahmen. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Video-Measurement-StageResults+Kalibrationsrevisionen umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_video_measurements.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** SceneF1/Boundaries/VFR; Flow/Intensity/Direction/Camera mit Sampling/Normunit; technische Codec/FPS/Dauer gemessen; Sharp/Blur/Noise/Compression/Freeze/AIartefakthinweise getrennt mit Ausnahmen. Ladbares APIbundle+Fixture+Adapter/Node/Model/Resourcebinding Pflicht; Manifest-only kein qualified. Jede Capabilityfamilie aus Plan O einzeln qualifizieren; bei fehlendem Profil unavailable/unverified, keine pauschale Familiensuccessmeldung.
**Risiko:** fremde Motion0–1 als RAFT/30 oder falsche QC.
**Rollback:** native Messung/Qualityprofil zurückwählen.

### T037 — Optionale alternative und segmentweise Embeddingräume

- [ ] T037 [US4] {(TR-006)} {(RR-001)} Optionale alternative und segmentweise Embeddingräume in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\database_core.py`.

**ID / Titel / Ziel:** T037 / Optionale alternative und segmentweise Embeddingräume. Ergebnis: getrennte EmbeddingSpace-/Indexidentitäten und passende Consumer.
**Abhängigkeiten / Gates:** T002, T020, T031. eigene Multi-space-Spec/Gmigration/Brainqualifikation; optional.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\database_core.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\data\vector_store.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\post_processor.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\embedding_cache.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\clip_selector.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\embedding_spaces.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_embedding_spaces.py`

**Interfaces:**
- Consumes: NativeADD/Operation-/Spacecontract und gelabelte Retrievaldaten.
- Produces: getrennte EmbeddingSpace-/Indexidentitäten und passende Consumer. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_embedding_spaces.py` definieren. Prüfbedingungen/Assertions: Gleiche Dim anderer Raum abgewiesen; lokale FAISSIDs verschiedener Indizes kollidieren nicht; asset/scene/window-Dedupe korrekt; Query/Projectorcache passenden Raum; Tombstone/Restore/retrievalHoldout.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für getrennte EmbeddingSpace-/Indexidentitäten und passende Consumer umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_embedding_spaces.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Gleiche Dim anderer Raum abgewiesen; lokale FAISSIDs verschiedener Indizes kollidieren nicht; asset/scene/window-Dedupe korrekt; Query/Projectorcache passenden Raum; Tombstone/Restore/retrievalHoldout. 
**Risiko:** Such-/Brainkorruption, invasive Migration.
**Rollback:** Nativeindex unverändert weiter; neue Räume isolieren.

### T038 — Vergleichsmodus und Kohortenqualifikation

- [ ] T038 [US3] {(FR-004)} {(FR-005)} {(RR-003)} Vergleichsmodus und Kohortenqualifikation in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\SettingsViewModel.cs`.

**ID / Titel / Ziel:** T038 / Vergleichsmodus und Kohortenqualifikation. Ergebnis: Qualified-Profile-Registry und auditierbare Benchmarkreceipts.
**Abhängigkeiten / Gates:** T002, T009, T031. G5 pro gewählter Capability; optional T037 nicht pauschal voraussetzen.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\SettingsViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\brain_service.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\feedback_logger.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\projector_trainer.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\brain_router.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\benchmarks.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_provider_qualification.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\provider-system.md`

**Interfaces:**
- Consumes: je Capability resultadapter; T032–T036 Ergebnisse wenn gewählt; verbindliche Fachverträge FP16 in domain-contracts.md.
- Produces: Qualified-Profile-Registry und auditierbare Benchmarkreceipts. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_provider_qualification.py` definieren. Prüfbedingungen/Assertions: Identische Quellen/Versionen/sampling; cold/warm/cache und E2Egetrennt; Mittel/Tail/Peak/Fehlerquote; schwierige Kohorte nicht im Mittel verdeckt; absent expectation niemals PASS. Gesamtgegenprüfung: FP16: Holdoutrating verändert keine produktiven feedback_events, Gewichtsbuckets, total_clicks oder Projektorgeneration. Paralleles normales Feedback ändert eingefrorenen Vergleich nicht; Restart/Replay übernimmt Evaluation nie ins Training.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Qualified-Profile-Registry und auditierbare Benchmarkreceipts umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_provider_qualification.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Identische Quellen/Versionen/sampling; cold/warm/cache und E2Egetrennt; Mittel/Tail/Peak/Fehlerquote; schwierige Kohorte nicht im Mittel verdeckt; absent expectation niemals PASS. Gesamtgegenprüfung: FP16: Holdoutrating verändert keine produktiven feedback_events, Gewichtsbuckets, total_clicks oder Projektorgeneration. Paralleles normales Feedback ändert eingefrorenen Vergleich nicht; Restart/Replay übernimmt Evaluation nie ins Training. 
**Risiko:** unberechtigte globale Qualitätsrangfolge.
**Rollback:** Qualifikation entziehen; Native bleibt explizit auswählbar.

### T039 — Qualifiziertes AUTO und sichtbares Degrade

- [ ] T039 [US3] {(FR-004)} {(RR-003)} Qualifiziertes AUTO und sichtbares Degrade in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\config_manager.py`.

**ID / Titel / Ziel:** T039 / Qualifiziertes AUTO und sichtbares Degrade. Ergebnis: select_provider →ProviderSelectionReceipt pro Capability.
**Abhängigkeiten / Gates:** T038, T031, T015. G6 bestätigte Degradepolicy, nicht pauschal bestesModell.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\config_manager.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\SettingsViewModel.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\routing.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_auto_selection.py`

**Interfaces:**
- Consumes: Qualified registry/Kohorte/Configrevision/Resourcepolicy; verbindliche Fachverträge FP16 in domain-contracts.md.
- Produces: select_provider →ProviderSelectionReceipt pro Capability. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_auto_selection.py` definieren. Prüfbedingungen/Assertions: Unqualified/Unknown nicht automatisch; harte Quality/Budgetgates zuerst; besserer Offlineprovider →wait oder genehmigtes Degrade mit Receipt; laufender Attempt unverändert; LLM ai.provider nicht mitumstellen. Gesamtgegenprüfung: FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für select_provider →ProviderSelectionReceipt pro Capability umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_auto_selection.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Unqualified/Unknown nicht automatisch; harte Quality/Budgetgates zuerst; besserer Offlineprovider →wait oder genehmigtes Degrade mit Receipt; laufender Attempt unverändert; LLM ai.provider nicht mitumstellen. Gesamtgegenprüfung: FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** stiller Qualitätsverlust oder Providerkonflikt.
**Rollback:** manuelle/Native-Auswahl.

### T040 — Director Coverage, Asset-DAG und Timelinebindung

- [ ] T040 [US3] {(FR-014)} {(TR-012)} {(RR-002)} Director Coverage, Asset-DAG und Timelinebindung in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\services\pacing_service.py`.

**ID / Titel / Ziel:** T040 / Director Coverage, Asset-DAG und Timelinebindung. Ergebnis: evaluate_coverage, AssetPlan und budgetgebundene Generationsjobs.
**Abhängigkeiten / Gates:** T026, T027, T031, T038, T043, T030. G7 Coverage-/Kontinuitätslabels; AUTO nur falls T039 qualifiziert; Gapi vor öffentlicher Vertragsänderung, Gmigration vor persistierter Timeline-/Mappingerweiterung.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\services\pacing_service.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\clip_selector.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\DirectorViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\pacing_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\routers\project_router.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\schemas\pacing_schemas.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\backend\app_state.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\TimelineViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\VideoLibraryViewModel.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\ApiClient.cs` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Services\IApiClient.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\coverage.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\pacing\asset_plan.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_director_coverage.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_derivative_timeline_ranges.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ComfyTimelineRevisionTests.cs`

**Interfaces:**
- Consumes: gültige AnalysisRuns/Qualityprofile/qualified generation/Derivation; verbindliche Fachverträge FP03, FP04, FP05, FP17 in domain-contracts.md; Reviewloop-Vertrag L02.
- Produces: evaluate_coverage, AssetPlan und budgetgebundene Generationsjobs. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_director_coverage.py` definieren. Prüfbedingungen/Assertions: Fehlende Semantik→unknown statt Generate; insufficient nach Holdoutthreshold; Asset statt Cutjob; ReferenceDAG/Handles/Seeds unverändert bei Reorder; Timelineedit/Planrevision keine stale Slotübernahme. Gesamtgegenprüfung: FP03: Manuelles Edit nach Jobstart, konkurrierende Commits und Restart: veraltete Übernahme liefert Konflikt; kein Überschreiben und keine still verlorenen Edits. FP04: Mit/ohne Anker, fehlendes Asset, Überlappung, Verschiebung während Generation und beide Pacingpfade: reservierte Bereiche bleiben erhalten; keine unnötigen Ersatzjobs. FP05: Audio plus valide leere Library erreicht Coverage; Profil/Budget kontrollieren Generation. Fehlende Analyse löst keine Generation aus; manuelle Cutgenerierung behält ihre Validierung. FP17: Parentfenster[599,606), Ersatz[600,605), Child7s: Childrange[1,6) durch sichtbare Übernahme→Save→Reopen→Scrub→Preview→Export. Niemals Sourceoffset600; Grenzframes/Handles und FPSwechsel prüfen. L02: T030 liegt vor T040; reale Reshotübernahme erst nach qualifiziertem Reshotproducer.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für evaluate_coverage, AssetPlan und budgetgebundene Generationsjobs umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_director_coverage.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Fehlende Semantik→unknown statt Generate; insufficient nach Holdoutthreshold; Asset statt Cutjob; ReferenceDAG/Handles/Seeds unverändert bei Reorder; Timelineedit/Planrevision keine stale Slotübernahme. Gesamtgegenprüfung: FP03: Manuelles Edit nach Jobstart, konkurrierende Commits und Restart: veraltete Übernahme liefert Konflikt; kein Überschreiben und keine still verlorenen Edits. FP04: Mit/ohne Anker, fehlendes Asset, Überlappung, Verschiebung während Generation und beide Pacingpfade: reservierte Bereiche bleiben erhalten; keine unnötigen Ersatzjobs. FP05: Audio plus valide leere Library erreicht Coverage; Profil/Budget kontrollieren Generation. Fehlende Analyse löst keine Generation aus; manuelle Cutgenerierung behält ihre Validierung. FP17: Parentfenster[599,606), Ersatz[600,605), Child7s: Childrange[1,6) durch sichtbare Übernahme→Save→Reopen→Scrub→Preview→Export. Niemals Sourceoffset600; Grenzframes/Handles und FPSwechsel prüfen. L02: T030 liegt vor T040; reale Reshotübernahme erst nach qualifiziertem Reshotproducer. 
**Risiko:** unbegrenzte Generation oder falsche Szenenzuordnung.
**Rollback:** Library-only Director, Jobs/Outputs bleiben.

### T041 — Bounded Longform-Automation und Gesamtvideo

- [ ] T041 [US3] {(FR-015)} {(OR-003)} {(TR-012)} {(RR-005)} Bounded Longform-Automation und Gesamtvideo in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\scheduler.py`.

**ID / Titel / Ziel:** T041 / Bounded Longform-Automation und Gesamtvideo. Ergebnis: Longform-Orchestrierung auf bestehendem ProductionBatch-Grundmodell und G8receipts tatsächlicher Workloadkomposition.
**Abhängigkeiten / Gates:** T021, T026, T040, T043. G8 reale Gesamtproduktion, keine Kurzclip-Abnahme als3hClaim; G8-shared-supervised nur beaufsichtigt; G8-managed-unattended erst nach qualifiziertem T016 für tatsächlich kooperierenden Scope.
**Aufwand:** sehr groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\scheduler.py` — zukünftige Datei aus Vorgängerpaket
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\services\pacing_service.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\rendering\render_service.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\production_batches.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_longform_batches.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\evidence\g8-longform.md`

**Interfaces:**
- Consumes: AssetDAG, Activity/Recovery, qualified bundles und Retentionpins; Reviewloop-Vertrag L03.
- Produces: Longform-Orchestrierung auf bestehendem ProductionBatch-Grundmodell und G8receipts tatsächlicher Workloadkomposition. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_longform_batches.py` definieren. Prüfbedingungen/Assertions: 1h/2h/3h jeweils realer Komplettlauf; Dispatchfenster/RAM/Disk/Retrybudget begrenzt; Lücke Shot17 nicht blind ab343; akzeptierte Assets kein Neurechnen; Originalmasteraudio/Trims/Übergänge/AVsync/Reopen. Je Receipt tatsächliche Laufzeit/Videodauer, fresh/reused/importierte Assets, Samplingprofile und ausgeübte Restart/Unknown/Failurefenster; Reuse-only keine Fresh-Generation-Endurance. L03: ohne qualifiziertes T016 keine verlässlich unbeaufsichtigte Freigabe; beaufsichtigtes Shared-Profil getrennt ausweisen und fehlende Kooperation/Cleanupreceipts blockieren unattended. L03: Shared-Nachweis bleibt beaufsichtigt; unbeaufsichtigter Claim ohne qualifiziertes T016 wird gesperrt.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Longform-Orchestrierung auf bestehendem ProductionBatch-Grundmodell und G8receipts tatsächlicher Workloadkomposition umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_longform_batches.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** 1h/2h/3h jeweils realer Komplettlauf; Dispatchfenster/RAM/Disk/Retrybudget begrenzt; Lücke Shot17 nicht blind ab343; akzeptierte Assets kein Neurechnen; Originalmasteraudio/Trims/Übergänge/AVsync/Reopen. Je Receipt tatsächliche Laufzeit/Videodauer, fresh/reused/importierte Assets, Samplingprofile und ausgeübte Restart/Unknown/Failurefenster; Reuse-only keine Fresh-Generation-Endurance. L03: ohne qualifiziertes T016 keine verlässlich unbeaufsichtigte Freigabe; beaufsichtigtes Shared-Profil getrennt ausweisen und fehlende Kooperation/Cleanupreceipts blockieren unattended. L03: Shared-Nachweis bleibt beaufsichtigt; unbeaufsichtigter Claim ohne qualifiziertes T016 wird gesperrt. 
**Risiko:** langfristiger Drift/Leck/Budgetüberschreitung.
**Rollback:** Batchpause, valide Assets/Library/Timeline weiterverwenden.

### T042 — Optionales Generatorfeedback und Lernen

- [ ] T042 [US4] {(FR-016)} {(RR-003)} Optionales Generatorfeedback und Lernen in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\post_processor.py`.

**ID / Titel / Ziel:** T042 / Optionales Generatorfeedback und Lernen. Ergebnis: gesonderte Feedbackevents/Generatorprofile, keine falsche Brainencoderidentität.
**Abhängigkeiten / Gates:** T027, T038, T040. eigene Learning-Spec/Datenfreigabe; optional nach lokaler Produktabnahme.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\brain\post_processor.py` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\providers\generation_feedback.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_generation_feedback.py`

**Interfaces:**
- Consumes: Derivation/Libraryratings und unabhängige Coveragebaseline; verbindliche Fachverträge FP16 in domain-contracts.md.
- Produces: gesonderte Feedbackevents/Generatorprofile, keine falsche Brainencoderidentität. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_generation_feedback.py` definieren. Prüfbedingungen/Assertions: Humanrating getrennt QC/Selbstrating; Exposure/Impression/Selectionreason und Workflow/Style gespeichert; Holdout kein Training; höhere Positivanzahl ohne Nenner kein Rankingvorteil; Seeds nicht global guteSeeds. Gesamtgegenprüfung: FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für gesonderte Feedbackevents/Generatorprofile, keine falsche Brainencoderidentität umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_generation_feedback.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Humanrating getrennt QC/Selbstrating; Exposure/Impression/Selectionreason und Workflow/Style gespeichert; Holdout kein Training; höhere Positivanzahl ohne Nenner kein Rankingvorteil; Seeds nicht global guteSeeds. Gesamtgegenprüfung: FP16: eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme T038 (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden. 
**Risiko:** Selbstbestätigung oder Brainvertragsbruch.
**Rollback:** Generatorlearning disable, vorhandenes Schnittfeedback erhalten.

### T043 — Retention, Ownership, Archivierung und sichere GC

- [ ] T043 [US2] {(OR-008)} {(OR-003)} {(RR-001)} Retention, Ownership, Archivierung und sichere GC in `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\recovery_adapters.py`.

**ID / Titel / Ziel:** T043 / Retention, Ownership, Archivierung und sichere GC. Ergebnis: Ownedartifactinventar/Pins/Archivepolicy und getrennte GC-Freigabeliste.
**Abhängigkeiten / Gates:** T019, T020, T021. vor T040/T041; echte Löschung nur Gdelete, Dryrun ohne destructive Aktion.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\storage\recovery_adapters.py` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\repository.py` — zukünftige Datei aus Vorgängerpaket

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\src\pb_studio\jobs\retention.py`
- `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_artifact_retention.py`

**Interfaces:**
- Consumes: Artifact-/Vector-/Recoveryreceipts und grundlegendes Ownership T019.
- Produces: Ownedartifactinventar/Pins/Archivepolicy und getrennte GC-Freigabeliste. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\Tests\test_comfyui_artifact_retention.py` definieren. Prüfbedingungen/Assertions: Dryrun pins Activejobs/References/Stems/Timeline/Derivatparents/Recovery; Externaloriginale nie Kandidat; Projektarchiv kein cascade acceptedmedia; missingartifact sichtbar statt stille Regeneration; Diskreserve vor Decode.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Ownedartifactinventar/Pins/Archivepolicy und getrennte GC-Freigabeliste umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-PY mit Tests/test_comfyui_artifact_retention.py.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Dryrun pins Activejobs/References/Stems/Timeline/Derivatparents/Recovery; Externaloriginale nie Kandidat; Projektarchiv kein cascade acceptedmedia; missingartifact sichtbar statt stille Regeneration; Diskreserve vor Decode. 
**Risiko:** Daten-/Provenancelöschung.
**Rollback:** GC aus, Pin-/Inventarrecords und akzeptierte Medien erhalten.

### T044 — Optionaler Setupwizard und Entwicklerhilfe

- [ ] T044 [US4] {(FR-016)} {(TR-004)} Optionaler Setupwizard und Entwicklerhilfe in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\SettingsView.xaml`.

**ID / Titel / Ziel:** T044 / Optionaler Setupwizard und Entwicklerhilfe. Ergebnis: Setupflow und dokumentierter Workflow→Manifest→Test→Qualify-Developerflow.
**Abhängigkeiten / Gates:** T005, T023, T026. eigenes UXscope; optional kein lokaler MVPblocker.
**Aufwand:** mittel; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\SettingsView.xaml` — vorhanden
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\SettingsViewModel.cs` — vorhanden

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\ViewModels\ComfySetupWizardViewModel.cs`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI\Views\ComfySetupWizardView.xaml`
- `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ComfySetupWizardTests.cs`

**Interfaces:**
- Consumes: Discovery/Registry/Qualified Pilot; phasenweiser Developer Guide T045, Ergänzungen über dessen Pflichtowner; Reviewloop-Vertrag L04.
- Produces: Setupflow und dokumentierter Workflow→Manifest→Test→Qualify-Developerflow. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Geplante Tests in `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI.Tests\ComfySetupWizardTests.cs` definieren. Prüfbedingungen/Assertions: Pfad/Endpoint/Nodes/Modelle/Workflow getrennt geprüft; Test ausdrücklich gestartet; nur real geprüftes Medienreceipt Fertig; Missingkomponenten erklärbar, keine automatische Installation oder Downloads. L04: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T045, kein vorzeitiger Integrations-PASS.
2. Fehlenden Vertrag bzw. Fehler im isolierten Testszenario tatsächlich beobachten; erwartetes Scheitern notieren. Kein synthetischer Produkt-/Medien-PASS.
3. Nur benannte Files/Interfaces/Änderungen für Setupflow und dokumentierter Workflow→Manifest→Test→Qualify-Developerflow umsetzen; kein unaufgeforderter Coreumbau.
4. Denselben Test und relevante Consumer-/Regressionchecks ausführen. Verify: Verify-WPF; Test PBStudio.UI.Tests/ComfySetupWizardTests.cs.
5. Reale Zusatzgates aus Acceptance unten durchführen; Evidence/Phasentask erst danach abschließen.

**Akzeptanzkriterien:** Pfad/Endpoint/Nodes/Modelle/Workflow getrennt geprüft; Test ausdrücklich gestartet; nur real geprüftes Medienreceipt Fertig; Missingkomponenten erklärbar, keine automatische Installation oder Downloads. L04: eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme T045, kein vorzeitiger Integrations-PASS. 
**Risiko:** Wizard behauptet unbelegte Bereitschaft.
**Rollback:** Wizard hide; Pflicht-Installationshilfe T023 bleibt.

### T045 — Phasenweise Regression, QC und Liefernachweis

- [ ] T045 [OBJ-1] {(RR-005)} {(RR-006)} Phasenweise Regression, QC und Liefernachweis in `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\architecture.md`.

**ID / Titel / Ziel:** T045 / Phasenweise Regression, QC und Liefernachweis. Ergebnis: qc-report pro tatsächlicher Phase; .completed/.qc-passed ausschließlich nach Gate.
**Abhängigkeiten / Gates:** keine. Phase-Manifest; ohne Umsetzung/ .completed keine Produkt-QC, jetzt nur Planstrukturcheck.
**Aufwand:** groß; technisch bestimmt durch die unten benannten Dateien, Systemübergänge und Failure-/Abnahmefälle; keine Zeitschätzung.

**Betroffene Dateien (Modify):**
- Keine bestehenden Produktdateien.

**Neue Dateien (geplant):**
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\architecture.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\workflow-format.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\troubleshooting.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\specs\00037-comfyui-control-center\evidence\phase-qc-index.md`
- `C:\Users\david\Documents\Pb_studio_AMD_version\docs\comfyui\developer-guide.md`

**Interfaces:**
- Consumes: explizite Phasen-Pflichtmenge und deren wirkliche Nachweise; Reviewloop-Vertrag L04.
- Produces: qc-report pro tatsächlicher Phase; .completed/.qc-passed ausschließlich nach Gate. Signaturen/Typen gemäß Plan P; zusätzliche API- oder Semantikänderung zuerst dort spezifizieren.

**Schritte / Änderungen / Tests:**
1. Gewählte Phase und deren Pflichtpakete aus Manifest lesen; fehlende Evidence als NOT_RUN, nicht PASS markieren.
2. Dokumente/OpenAPI/Source-/Reviewchecks; passende isolierte Python-/native C#-/Releasechecks tatsächlich ausführen, wenn Phase implementiert.
3. GUI/Hardware/Real-Media-Qualitygates separat ausführen und nachweisen; prüfen: Gewählte Phase-Pflichttasks/evidence abgeschlossen; Source/Build/nativeGUI/HW/RealMediaquality getrennt; gesamte relevante Regression isoliert; keine optionalen Nichtscopepakete als Fehler oder FakePASS; exakter geprüfter Stand. Gwire-Protokoll mit tatsächlichen Source-/Profilhashes, ausgeübten Fehlerfenstern und Restunsicherheit;32 Kommunikationsfälle eindeutig referenziert. L04: alle sechs Pflichtdokumente einschließlich Developer Guide ohne optionalen Wizard; pro Phase nur fällige Vertragsabschnitte als geliefert markieren. L04: Alle sechs Pflichtdokumente ohne gewählten Wizard vorhanden und phasenbezogen geprüft.
4. Erst bei Umsetzung .completed der betreffenden Phase, dann qc-report; .qc-passed nur bei bestandenem QC und exakter Versionsbindung.

**Akzeptanzkriterien:** Gewählte Phase-Pflichttasks/evidence abgeschlossen; Source/Build/nativeGUI/HW/RealMediaquality getrennt; gesamte relevante Regression isoliert; keine optionalen Nichtscopepakete als Fehler oder FakePASS; exakter geprüfter Stand. Gwire-Protokoll mit tatsächlichen Source-/Profilhashes, ausgeübten Fehlerfenstern und Restunsicherheit;32 Kommunikationsfälle eindeutig referenziert. L04: alle sechs Pflichtdokumente einschließlich Developer Guide ohne optionalen Wizard; pro Phase nur fällige Vertragsabschnitte als geliefert markieren. L04: Alle sechs Pflichtdokumente ohne gewählten Wizard vorhanden und phasenbezogen geprüft. 
**Risiko:** falsche Vollabnahme oder verfrühte Marker.
**Rollback:** QCFAIL/NOT_RUN offen lassen; keine alten Belege löschen.

## Bedingte Scopeabhängigkeiten

- T016 nur nach konkreter Freigabe und Qualifikation der späteren managed Koordination und externer Gateinstallation; T015 observed_shared allein beansprucht keine harte Exklusivität.
- T037 nur eigener Embeddingraum-/Segmentindexscope; T038/T039 qualifizieren nur tatsächlich geprüfte gewählte Provider, nicht automatisch T032–T037.
- T040 nutzt manuelle qualified Selection; AUTO nur zusätzlich nach T039/G6. T042 setzt keine neue Vektorraummigration voraus und darf bestehende Brainfeedbackverträge nicht umdeuten.
- T043 Retention/Ownedmedienschutz muss vor T040/T041 bestehen; Löschphase bleibt Gdelete, Dryrun alone ist keine GCfreigabe.
- T045 wird wiederkehrend pro Phase angewendet: dynamische Voraussetzung sind deren ausgewählte Pflichtpakete und .completed für Produkt-QC; deps=[] bedeutet keine Blanket-Sofort-QC.
- T001/T002 sind Plan-/Referenzpakete; aktuelle Masterplanerstellung erfüllt nicht automatisch alle zukünftigen Gateantworten oder Messungen.
- T034 hat Einzeliterationsgates Energie/Struktur/Harmonie/Longmix; Phase-Tasksplit vor Umsetzung auf diese Familien, kein gemeinsamer ungeprüfter Auslagerungswechsel.

## Quellenstand

Dieser Aufgabenplan übernimmt die gelesenen Reviewbelege, keine neue Laufzeitfreigabe. Vor betroffener Änderung konkrete aktuelle Caller/DTOs/Lockowner und Tests lesen. Source-/Runtime-/Qualitätsdrift ist expliziter Anlass für neue Evidence, kein Anlass für erfundene Defaults.
