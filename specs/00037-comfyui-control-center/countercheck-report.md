# Gegenprüfung des Masterplans — zweite vertiefte Prüfung

Auditstand2026-10-12; Entscheidungsfortschreibung2026-10-13. Die ausgeführten Gegenprüfungen in countercheck-evidence.json sind datierte Auditbelege; aktuelle Entscheidungsprüfung separat in decision-validation-2026-10-13.json. Drei unabhängige read-only Fachprüfungen, danach Planänderungen und Gegenkontrolle. **19 weitere Vertrags-/Planlücken**, getrennt von ursprünglichen F01–F40. Severity beschreibt Risiko ungeprüfter späterer Umsetzung, keinen eingetretenen Produktschaden.

## Beweisniveau

[BEOBACHTUNG] Masterplan, JSON/Taskscopes und relevante aktuelle Quelldateien gelesen. [NACHWEIS] 12 Baseline-Gegenprüfungen als Dokumentprädikate und ausdrücklich vereinfachte In-memory-Modelle ausgeführt; danach dieselben Vertragsbedingungen gegen korrigierte Dokumente geprüft. Das ist kein Produkt-, GPU-, Servercallback-, Stromausfall-, Crash- oder Real-Media-Test. Solche Tests sind unten konkrete spätere Abnahmegates.

Baselinekopien: countercheck-baseline/. Baselinehashes/ausgeführte Prädikate: countercheck-evidence.json. Die ursprüngliche planning-validation.json belegte Strukturabdeckung; sie beweist keine semantische Ausführbarkeit und wird deshalb erweitert statt als Vollbeweis behandelt.

## Befunde und Korrekturen

| ID | Priorität | Vertragslücke | Pakete |
|---|---|---|---|
| CC01 | HIGH | Batchbasis erst nach Consumer | T010,T011,T014,T041 |
| CC02 | HIGH | Fehlende PB-Mutationsroutes | T022,T023,T024,T025 |
| CC03 | HIGH | Routerregistrierung ohne zuständiges Paket | T022 |
| CC04 | HIGH | Persistierter AnalysisRun ohne Vorgänger | T009,T019,T020 |
| CC05 | HIGH | Terminalretry widersprüchlich | T014,T022 |
| CC06 | HIGH | Manifest-only Workflowlieferung | T027,T032,T033,T034,T035,T036 |
| CC07 | MEDIUM | WPF-DI/Controlverdrahtung unvollständig | T024,T025 |
| CC08 | MEDIUM | AUTO-/O02-Status inkonsistent | T001,T039 |
| CC09 | HIGH | Cancel nach Katalogcommit ohne Abschluss | T019,T020,T021 |
| CC10 | HIGH | Compaction invalidiert completed Receipts | T020,T021,T037 |
| CC11 | HIGH | Writerdrain unter äußerem Projektguard | T020,T021 |
| CC12 | HIGH | Unbounded Writerjoin | T020,T021 |
| CC13 | MEDIUM | Teilresultat kann nicht needs_decision werden | T010,T019 |
| CC14 | MEDIUM | Vektorlose Completion nur im Text | T010,T018,T019 |
| CC15 | HIGH | IDmengenvalidator beweist keine Vektoridentität | T020,T021 |
| CC16 | HIGH | Autoritativer externer Cancel nicht repräsentierbar | T010,T013,T014 |
| CC17 | HIGH | Manifestprüfung als Egressdurchsetzung | T006,T007 |
| CC18 | HIGH | EffectiveGraph verpflichtend und gleichzeitig optional | T005,T006,T007 |
| CC19 | MEDIUM | G8 Outputdauer beweist keine Generationslast | T041 |

### CC01 — Batchbasis erst nach Consumer

**Problem / Gegenbeispiel:** T014 benötigt ProductionBatch vor T041.

**Planänderung:** T010/T011 definieren/persistieren minimale Batchbasis; T041 erweitert Longform.

**Späterer konkreter Gegen-/Abnahmetest:** T014 ohne T041: create/reorder/pause/restart/CAS funktionieren.

**Pakete:** T010,T011,T014,T041. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC02 — Fehlende PB-Mutationsroutes

**Problem / Gegenbeispiel:** Workflowregister/Enable/Settings/Priority/Reorder/manualImport fehlten in routedefiniertem Vertrag.

**Planänderung:** D-Routen ergänzen, typed Requests/Responses/Ownership/CAS/Idempotency; lokaler Importintent.

**Späterer konkreter Gegen-/Abnahmetest:** WPF nur PB erreichbar; jede Aktion sowie cross-project/stale/duplicate Fälle.

**Pakete:** T022,T023,T024,T025. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC03 — Routerregistrierung ohne zuständiges Paket

**Problem / Gegenbeispiel:** T022 erstellt Router nach letztem main.py-Owner T021.

**Planänderung:** T022 erhält main.py für include_router/DI/Startupbindung.

**Späterer konkreter Gegen-/Abnahmetest:** Echte App/OpenAPI enthält Pflichtpfade; disabled Startup funktioniert.

**Pakete:** T022. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC04 — Persistierter AnalysisRun ohne Vorgänger

**Problem / Gegenbeispiel:** T019/T020 konsumieren Run, aber T009 war nicht in Dependencyclosure.

**Planänderung:** T009 vor T019/T020, vor ADD persistierten Run/Hash/Space prüfen.

**Späterer konkreter Gegen-/Abnahmetest:** Fehlender Run kein ADD; gleicher Run/Operation idempotent; MVP ohne T031 möglich.

**Pakete:** T009,T019,T020. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC05 — Terminalretry widersprüchlich

**Problem / Gegenbeispiel:** Retry versprach neuen Attempt trotz terminalem unveränderlichem Intent.

**Planänderung:** Nichtterminal nur bestätigter retry_wait; failed neuer linked Intent; ready/cancelled/obsolete/unresolved409.

**Späterer konkreter Gegen-/Abnahmetest:** Retrymatrix bewahrt Originalzustände; Unknown nie Resubmit.

**Pakete:** T014,T022. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC06 — Manifest-only Workflowlieferung

**Problem / Gegenbeispiel:** T027/T032–T036 fehlten API-Prompts/Fixtures/Profilreceipts im Create-Scope.

**Planänderung:** Executable Bundlefiles je Familie deklarieren; externe Inputs nur mit gepinntem Vertrag.

**Späterer konkreter Gegen-/Abnahmetest:** Saubere Installation mit deklarierter Lieferung lädt Bundle; Manifest-only kein qualified.

**Pakete:** T027,T032,T033,T034,T035,T036. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC07 — WPF-DI/Controlverdrahtung unvollständig

**Problem / Gegenbeispiel:** T024/T025 schaffen Views/StateService ohne App/ApiClient-Kontraktowner.

**Planänderung:** App.xaml.cs und erforderliche ApiClient/IApiClientfiles ergänzen.

**Späterer konkreter Gegen-/Abnahmetest:** Reale AppDI/Navigation/Subscriptions, kein manuell verdrahtetes VM als Integrationsbeleg.

**Pakete:** T024,T025. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC08 — AUTO-/O02-Status inkonsistent

**Problem / Gegenbeispiel:** AUTO als OPTIONAL bezeichnet; O02 in Traceability verbindlich/geschlossen trotz unbestätigter Policy.

**Planänderung:** AUTO späterer Pflichtzielumfang außerhalb MVP; O02 war beim Audit offen; am 2026-10-13 als Betriebsregel bestätigt, technische Abnahme offen.

**Späterer konkreter Gegen-/Abnahmetest:** O02-Betriebsregel seit 2026-10-13 bestätigt; keine Implementierungs-/Runtime-/Migrationsfreigabe daraus ableiten; technische Pause/Detach/Reconciliation-Abnahme bleibt offen.

**Pakete:** T001,T039. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC09 — Cancel nach Katalogcommit ohne Abschluss

**Problem / Gegenbeispiel:** Q3 Quarantänepfad endete vor catalog_committed.

**Planänderung:** Cancel-vs-Catalog-CAS; nach Commit Media erhalten/Eignung sperren, konsistent drainen→locally_cancelled.

**Späterer konkreter Gegen-/Abnahmetest:** Cancel an jeder Catalog/Analyse/Vektorgrenze, keine Löschung/unerlaubte Timelinefreigabe.

**Pakete:** T019,T020,T021. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC10 — Compaction invalidiert completed Receipts

**Problem / Gegenbeispiel:** IDverschiebung nach completed ADD lässt historische ID/Generation veralten.

**Planänderung:** MVP Compaction/Reindex sperren bis Remapspec; immutable Receipt von IndexMembership trennen.

**Späterer konkreter Gegen-/Abnahmetest:** Completed opB ID1→Compaction ID0; Gate blockiert oder qualifizierter Remap, kein stale Replay.

**Pakete:** T020,T021,T037. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC11 — Writerdrain unter äußerem Projektguard

**Problem / Gegenbeispiel:** VideoRouter1525–1526 hält Kontextguard beim inneren Vektoradd.

**Planänderung:** Aufrufer split: Preflight/drain außerhalb Projekt-/Recoverylocks, Kontext danach kurz revalidieren.

**Späterer konkreter Gegen-/Abnahmetest:** Projektwechsel+Native/Sagaadd+Snapshot/Close ohne Joindeadlock/stale Commit.

**Pakete:** T020,T021. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC12 — Unbounded Writerjoin

**Problem / Gegenbeispiel:** Bestehender join ohne Timeout; persistent Dirty/Publishfailure kann Drain blockieren.

**Planänderung:** Endliche Profildeadline, Abbruch repair_required; lebender Writer kein Erfolg/zweiter Writer.

**Späterer konkreter Gegen-/Abnahmetest:** Diskfull/RecoveryBusy/repeated Publishfail/Deadline; bounded Rückkehr mit sichtbarem Fehler.

**Pakete:** T020,T021. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC13 — Teilresultat kann nicht needs_decision werden

**Problem / Gegenbeispiel:** Q1 erlaubte active→needs_decision, nicht available_partial.

**Planänderung:** Neue Kante mit Konflikt-/Missingreceiptguard.

**Späterer konkreter Gegen-/Abnahmetest:** Slot A importiert, Slot B Hashkonflikt/fehlend: Zustand needs_decision, kein Resubmit.

**Pakete:** T010,T019. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC14 — Vektorlose Completion nur im Text

**Problem / Gegenbeispiel:** Strenge Q3-Tabelle verbot die im Absatz versprochene direkte Completion.

**Planänderung:** analysis_pending→completed mit explizitem No-vector-Qualityguard in Tabelle.

**Späterer konkreter Gegen-/Abnahmetest:** Technikprofil ohne Vektor kann lokal komplett sein; semantische Eligibility nicht zugesagt.

**Pakete:** T010,T018,T019. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC15 — IDmengenvalidator beweist keine Vektoridentität

**Problem / Gegenbeispiel:** Bestehender Restorepredicate prüft IDs/Bounds statt Operation/Media/Space/Hash.

**Planänderung:** T021 verifiziert identitätsgebundene Operation-/Vektorreceipts im Restorevalidator.

**Späterer konkreter Gegen-/Abnahmetest:** Vertauschte Media-/Operationmarker bei identischen IDs oder andere Bytes fail-closed.

**Pakete:** T020,T021. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC16 — Autoritativer externer Cancel nicht repräsentierbar

**Problem / Gegenbeispiel:** queued/running→cancelled fehlte ohne eigenen Cancelrequest.

**Planänderung:** Kante ausschließlich bei konkretem Providerterminalreceipt; leere History bleibt Unknown.

**Späterer konkreter Gegen-/Abnahmetest:** Provider-confirmed external cancel darstellbar; bloß verlorener Queueeintrag nicht cancelled.

**Pakete:** T010,T013,T014. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC17 — Manifestprüfung als Egressdurchsetzung

**Problem / Gegenbeispiel:** PBpolicy allein kann serverseitige Callbacks/Replacements/Netzwerk nicht sperren.

**Planänderung:** Assurance declared_only/audited_frozen/enforced trennen; Garantie nur passende Durchsetzung, sonst unqualified.

**Späterer konkreter Gegen-/Abnahmetest:** Isolierter Callback ersetzt Localnode durch ungeprüften externen Dienstaufruf; keine lokale Qualifikation allein aus Manifest.

**Pakete:** T006,T007. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC18 — EffectiveGraph verpflichtend und gleichzeitig optional

**Problem / Gegenbeispiel:** Standard Acceptreceipt enthält keinen effective hash; DTO optional, Claims trotzdem vollständig.

**Planänderung:** Submitted/effective getrennt; unknown sperrt darauf beruhende Claims, frozen Alternative ausdrücklich geprüft.

**Späterer konkreter Gegen-/Abnahmetest:** Callback verändert Prompt/Seed: effective hash anders/unknown, kein erfundener Gleichheitsnachweis.

**Pakete:** T005,T006,T007. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

### CC19 — G8 Outputdauer beweist keine Generationslast

**Problem / Gegenbeispiel:** Reuse-only Langvideo kann G8 scheinbar Freshgenerations-Endurance erfüllen.

**Planänderung:** Receipt trennt Laufzeit/Videodauer/fresh/reused/imported/Profile/ausgeübte Fehlerfenster.

**Späterer konkreter Gegen-/Abnahmetest:** Alle Assets vorher accepted: Export-/Reusebeleg, kein Freshgeneration-Enduranceclaim.

**Pakete:** T041. **Status:** Dokumentvertrag korrigiert; Produktumsetzung/Abnahme offen.

## Quellenbelege der kritischen Produktionsgrenzen

- backend/main.py:805–814 besitzt tatsächliche Routerregistrierung; neue T022-Router brauchen entsprechenden Owner.
- backend/routers/video_router.py:1525–1526 und669: project_commit umschließt Native-Vektorcommit.
- src/pb_studio/data/vector_store.py:656: Writerjoin;783–785: Stop-/Dirty-/Persistenzverhalten;573–599: Compaction/IDmapping/RAMswap.
- src/pb_studio/storage/recovery_adapters.py:312–320: IDmengen/Bounds/Tombstones im geprüften bestehenden Validator, keine behauptete operation/space/byteHashprüfung.
- Aktive gelesene Comfyquelle server.py:1084/1118/1139–1140: Promptcallbacks/Replacements/Queue und begrenztes Acceptresponse. Kein Callback wurde am laufenden Server ausgeführt.

## Urteil

Masterplan an den belegten Punkten präzisiert. Dokumentgegenkontrolle ersetzt keine künftige Produktabnahme; O01–O04-Grundsätze seit 2026-10-13 bestätigt; konkrete O03-Mess-/Referenzgates und O04-Änderungsfreigaben offen, D01/D02 bestätigt. Optionaler harter Egress-/Pre-enqueue-/Remapvertrag braucht eigene technische Qualifikation. Keine Produktdateien/-daten/-konfigurationen/-laufzeiten verändert.
