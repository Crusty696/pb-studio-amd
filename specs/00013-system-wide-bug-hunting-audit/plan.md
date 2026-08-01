# Vorgeschlagener Reparaturplan 2026-07-31

## Release-Wahrheit, Projektisolation und reproduzierbare Auslieferung

**Workspace:** `C:\Users\david\Documents\Pb_studio_AMD_version`
**Feature-Workspace:** `specs/00013-system-wide-bug-hunting-audit`
**Fortsetzung:** vorgeschlagen als OBJ-72, T370–T415
**Status:** `SCOPE_APPROVED` – Release-Fähigkeit und ergänzende Betriebssicherheit am 2026-07-31 freigegeben; destruktive/externe Einzelgates bleiben bestätigungspflichtig
**Ausgangsbericht:** `FULLSTACK_AUDIT_PB_STUDIO_2026-07-31.md`
**Produktcode in dieser Planungsphase:** unverändert

### Freigegebener Fokus

Primärziel ist ein vollständig belegter Releasepfad für die Erstellung eines
vollständigen Videos. Betriebssicherheit fließt verpflichtend ein, ohne den
Plan zu einem allgemeinen Funktions-Deep-Audit auszuweiten:

- keine projektübergreifenden Writes,
- kein gemeldeter Erfolg vor bestätigter Persistenz,
- keine beschädigten Zustände durch parallele Jobs,
- kontrolliertes Verhalten bei bekannten und unbekannten Fehlern.

`100 %` bedeutet 100 % PASS der in diesem Plan definierten Release-Gates für
denselben Commit. Es ist keine Behauptung absoluter Fehlerfreiheit.

### Verbindliche Ausführungsregeln des Benutzers

- Vollständig autonom abarbeiten. Routineentscheidungen innerhalb dieses Plans
  benötigen keine Zwischenfreigabe.
- Parallel arbeiten, sobald Code-Zonen disjunkt sind und kein Shared File,
  öffentlicher Vertrag oder Datenbankschema überlappt.
- `caveman` bleibt im Hauptagenten und in allen Agenten-Prompts durchgehend
  aktiv. Sicherheitswarnungen und irreversible Bestätigungen bleiben zur
  Eindeutigkeit in normaler Sprache.
- Richtige Fachskills, Plugins, Tools, Agenten und Subagenten werden je Zone
  verpflichtend eingesetzt, sofern verfügbar und für den Task relevant.
- Der Hauptagent ist Teamleiter. Er besitzt Architekturentscheidungen,
  Shared-Zones, Task-Reihenfolge, Merge, End-QC und Release-Wahrheit.
- Keine Annahmen. Jede Ursache, Änderung und PASS-Aussage benötigt direkten
  Code-, Laufzeit- oder gespeicherten Evidenzbeleg.
- Jeder Agentendiff erhält unabhängige Kritik. Ein implementierender Agent darf
  seinen eigenen Task nicht allein als PASS erklären.
- Funktionale Tests werden, soweit ohne Sicherheitsverlust möglich, in T404–
  T413 gebündelt. Während T374–T403 sind nur Syntax-, XML-, Truncation-,
  statische Vertrags- und notwendige Build-Integritätschecks erlaubt.
- `repair-progress.md` wird automatisch bei Taskstart, Abschluss, Blocker,
  ETA-Änderung und Evidenzgewinn aktualisiert.
- Zwingende Projektregeln bleiben Ausnahmen von der Autonomie: destruktive
  Aktionen, öffentliche API-Verträge, Schemaänderungen, neue Dependencies/
  Lockfiles und externe GitHub-Mutationen werden vor Ausführung explizit
  angekündigt und ausdrücklich freigegeben.

## 1. Sind die Probleme neu oder wiedergekommen?

### 1.1 Strenger Maßstab

- `REGRESSION`: Exakt derselbe Vertrag war früher mit passendem Test nachweislich grün und ist später wieder gebrochen.
- `NEVER_FULLY_FIXED`: Der Fehler war bekannt oder eine Schließung wurde behauptet, aber der konkrete Pfad beziehungsweise Gegenbeweis blieb offen.
- `RELATED_DISTINCT`: Ein früherer Fix betraf ein benachbartes Problem, nicht den jetzt gefundenen Vertrag.
- `NEW`: Erstmals nachgewiesener, technisch eigenständiger Befund.
- `MIXED`: Ein Audit-ID enthält unterschiedlich einzuordnende Teilbefunde.
- `KNOWN_RESIDUE`: Bekannter Hygiene-Rest, kein Produktfehler.

### 1.2 Ergebnis

Es gibt **keinen nachgewiesenen wiedergekehrten Produkt- oder Laufzeitfehler**. Zwei Prozess-/Governance-Verträge sind echte Regressionen:

1. **C-03:** `spec.md` war bis Juni mit rund 3,6 KB regelkonform und wuchs ab 28. Juli auf mehr als 10 KB.
2. **H-07:** Der SDD-Gate-Test erkannte zunächst falsche Marker; Commit `3c71f56` schwächte den Vertrag später zu einer unzureichenden Existenzprüfung ab.

Gesamtklassifikation der 29 Auditbefunde:

| Klasse | Anzahl | Befunde |
|---|---:|---|
| Echte Prozessregression | 2 | C-03, H-07 |
| Nie vollständig behoben | 11 | C-02, H-01, H-02, H-03, H-06, M-08, M-11, M-13, M-14, M-15, L-01 |
| Verwandt, aber eigenständig | 9 | C-01, M-01, M-03, M-04, M-05, M-07, M-09, M-10, M-12 |
| Neu beziehungsweise erstmals nachgewiesen | 5 | H-04, H-05, M-02, M-06, L-02 |
| Gemischt | 1 | M-16 |
| Bekannter Hygiene-Rest | 1 | L-03 |

Die vorherigen Reparaturen waren deshalb nicht wirkungslos. Sie schlossen überwiegend andere, engere Verträge. Das wiederkehrende Muster war eine **zu enge Verifikation**: lokale/incrementelle Builds statt Clean-Checkout, UI-Generationen statt serverseitiger Commit-Grenzen und Quelltexttests statt nativer Laufzeitverträge.

## 2. Verbindliche Architekturentscheidungen

### D01 – Projektidentität ist unveränderlicher Operationskontext

`ProjectOperationContext` enthält mindestens Projekt-ID, Projektwurzel und monotone Epoch. Jede langlaufende oder verzögerte Mutation erfasst den Kontext vor dem ersten `await`, reicht ihn explizit bis zur Persistenz weiter und validiert ihn direkt vor dem Commit. Projektwechsel invalidieren alte Epochen und canceln beziehungsweise drainen projektgebundene Tasks.

### D02 – Erfolg erst nach dauerhafter Persistenz

RAM, Cache, Erfolgsevent und HTTP-2xx dürfen erst nach erfolgreichem DB-/Datei-Commit veröffentlicht werden. Persistenzfehler werden typisiert propagiert. Partielle Analyse bleibt partiell und retryfähig.

### D03 – Generierter C#-Code entsteht vor `CoreCompile`

NSwag schreibt in den Intermediate-Output. Das Build-Target nimmt die generierte Datei im selben Target explizit in `@(Compile)` auf. Ein bereits vorhandener lokaler Generator-Output darf niemals Voraussetzung eines erfolgreichen Builds sein.

### D04 – Kanonische Runtime statt scheinbar freier FFmpeg-Wahl

Wegen der AMF-/DirectML-IRON-RULES zeigt die UI die validierte kanonische FFmpeg-Runtime read-only. Ein frei wählbarer Binärpfad wäre ein separates Trust- und Kompatibilitätsfeature.

### D05 – Releases kommen nur aus reproduzierbarem, geschütztem Main

Gelockte Abhängigkeiten, Clean-Windows-Build, Tests, Security-Gates, Asset-Provisioning und Provenienzmanifest müssen für denselben Commit bestehen. Lokale Workstation-Evidenz allein ist kein Releasebeweis.

### D06 – Aktive SDD-Artefakte bleiben klein und beweisbar

Die aktive `spec.md` bleibt bei höchstens 10.240 Bytes. Historische Anforderungen bleiben unverändert in versionierten Anhängen mit ID-Mapping und Hash erhalten. `.completed` und `.qc-passed` enthalten beziehungsweise referenzieren prüfbare Digests statt nur zu existieren.

## 3. Einzelreparaturen

| ID | Einordnung | Verbindliche Lösung | Gegenentwurf / warum nicht bevorzugt | Abnahme |
|---|---|---|---|---|
| C-01 | `RELATED_DISTINCT` | Zentralen `ProjectOperationContext` und Task-Registry einführen; Audio, Video, Pacing, Ingest und Timeline-Mutationen epochgebunden machen; stale Commit mit 409 ablehnen. Timeline-Autosave in den VM-Lifecycle verlagern, Snapshot+CTS+Generation verwenden. | Nur UI-Cancellation wäre kleiner, schützt aber Backendjobs und direkte API-Aufrufe nicht. | Pausierte Jobs A, Wechsel A→B, Fortsetzung: keinerlei Mutation in B; alter Autosave sendet keinen POST. |
| C-02 | `NEVER_FULLY_FIXED` | NSwag `BeforeTargets="CoreCompile"` ausführen, Output unter `obj/` erzeugen und innerhalb des Targets explizit als `Compile` aufnehmen; `Exists`-Bedingung entfernen. | Generierte Datei tracken ist einfach, erzeugt aber Drift und Merge-Rauschen. | `git archive`/temporärer Clean-Checkout ohne `Generated/*.g.cs` baut Release erfolgreich. |
| C-03 | `REGRESSION` | Aktive Spec auf ≤10.240 Bytes verdichten; abgeschlossene Historie in versionierten Anhang mit Requirement-Mapping und Hash auslagern; Byte-Limit in SDD-Validator. | Nur Grenzwert erhöhen verletzt die verbindliche Projektregel und löst Kontextwachstum nicht. | Bytegenaue Prüfung ≤10.240; alle aktiven IDs definiert; historische IDs lückenlos aufgelöst. |
| H-01 | `NEVER_FULLY_FIXED` | `PersistenceError`; DB-first beziehungsweise atomare Unit-of-Work; keine broad catches ohne Re-raise; keine Success-Events/2xx vor Commit. | Nur `persist_error` loggen reproduziert den bisherigen Scheinerfolg. | Fault-Injection für Import, Analyse, Stems: Fehlerstatus, kein RAM-Geisterzustand, Neustart konsistent. |
| H-02 | `NEVER_FULLY_FIXED` | `analysis_status`, Stage-Status und Fehler persistieren; `is_analyzed` nur bei `completed`; explizites `False` muss altes `True` überschreiben; Liste nutzt Status statt Cache-Existenz. | Partielle Daten komplett verwerfen verliert nützliche Stage-Ergebnisse. | completed, partial und partial-after-completed bleiben nach Reload wahrheitsgetreu. |
| H-03 | `NEVER_FULLY_FIXED` | Zielclip, ID, Projektkontext und Generation vor Await erfassen; Ergebnis nach ID auf A anwenden; Selected/Batch durch gemeinsamen Analyse-Gate und CTS serialisieren. | Nur `SelectedClip` nach Await prüfen verliert legitime Ergebnisse für A oder bleibt race-anfällig. | Auswahl A→B während Analyse verändert B nie; paralleler Start erzeugt exakt einen aktiven Job. |
| H-04 | `NEW` | `IConfirmationService`/Dialogservice; Anzahl, Namen und Folgen anzeigen; Default ist Abbruch; erst nach `Yes` API aufrufen. | Undo wäre nutzerfreundlicher, verlangt aber transaktionale Wiederherstellung von DB, Cache und Vektorindex. | Cancel: null API-Aufrufe/null State-Änderung; Confirm: genau ein Löschlauf. |
| H-05 | `NEW` | Gepinntes DirectML-Release-Bundle mit Revision, Lizenz und SHA-256; Provisioning in Staging, Allowlist-Extraktion, Einzelhashprüfung und atomare Übernahme; Setup schlägt ohne gültige Assets geschlossen fehl. | ONNX-Dateien ins Git-Repository legen vergrößert Historie und löst Lizenz-/Transformationsprovenienz nicht. | Frische Windows-VM ohne Modelle: Setup, Hashprüfung und Hardware-Smoke für alle Pflichtworkloads. |
| H-06 | `NEVER_FULLY_FIXED` | CI für PRs und Arbeitsbranches; nach grünen Gates PR nach `main`; Default-Branch auf `main`; Required Checks, Reviews und Force-Push-Verbot. | Direktes Fast-Forward-Pushen bewahrt keinen überprüfbaren Merge-Gate. | Release-SHA stammt aus geschütztem Main/Tag; neuester Required-Check-Satz ist grün. |
| H-07 | `REGRESSION` | Generischer `validate_sdd.py`: Spec-Bytegröße, kanonische Tasks, offene Checklisten, Evidenz, Marker-Digests und QC-Reihenfolge; negative Fixtures müssen scheitern. | Manuelles Prüfen oder Marker-mtime ist nicht reproduzierbar. | Falsche Taskbox, fehlende Requirement-ID, vorzeitiger Marker und falscher QC-Hash werden jeweils abgelehnt. |
| M-01 | `RELATED_DISTINCT` | Projekt in eindeutig besessenem Staging-Verzeichnis vollständig vorbereiten und atomar zum Ziel umbenennen; Fehler kompensieren nur eigene Staging-/DB-Artefakte. | Nach jedem Schritt ad-hoc löschen ist schwer vollständig und riskanter. | Injizierter Fehler an jeder Stufe hinterlässt keinen Zielpartialzustand; Retry gelingt. |
| M-02 | `NEW` | Deduplizierung nur für aktive Jobs; terminaler Retry erhält neue Attempt-ID; Identität umfasst kanonische Timeline, Einstellungen, Projekt und gespeicherte Medien-Contenthashes. | Pfad+mtime ist schneller, erkennt aber Inhaltswechsel und Restorefälle nicht sicher. | Aktiver Doppelstart 409; completed/failed darf Retry; gleicher Pfad mit neuem Inhalt erzeugt neue Identität. |
| M-03 | `RELATED_DISTINCT` | Projekt-/epochgebundene Brain-Connection-Lease; neue DB vorab öffnen; alte Connection erst nach Ende aktiver Leases schließen. | Ein globaler Lock um Einzelstatements schützt keine mehrstufige SQL-Einheit. | Laufende A-Abfrage plus Rebind B: kein closed-database-Fehler, kein A-Write nach Wechsel. |
| M-04 | `RELATED_DISTINCT` | `SSELogHandler` ausschließlich über zentralen Drop-Oldest-Fanout; QueueFull abfangen und Drop-Metrik führen. | Queue unbeschränkt machen verschiebt das Problem in RAM-Wachstum. | Volle Queue verursacht keine Eventloop-Exception und genau definierte Drop-Oldest-Reihenfolge. |
| M-05 | `RELATED_DISTINCT` | FFmpeg-Pfad read-only als kanonische Runtime/Provenienz anzeigen; Browse entfernen. | Frei wählbarer Pfad erweitert den Trust-Bereich und kann AMF-Regeln umgehen. | UI bietet keine unwirksame Auswahl; Anzeige entspricht tatsächlich gestarteter Runtime. |
| M-06 | `NEW` | Typisiertes Load-/Save-Ergebnis; atomischer temp+replace-Write; UI meldet Erfolg nur nach bestätigtem Write und Fehler sichtbar. | Stiller Default-Fallback bleibt bequem, verbirgt aber Datenverlust. | Malformed JSON, Write-Denied und erfolgreicher Roundtrip werden nativ getestet. |
| M-07 | `RELATED_DISTINCT` | Preview-Token bis `HttpClient.SendAsync`/Response-Read propagieren; CTS, Generation und Projektkontext bei Wechsel/Dispose invalidieren. | Nur späte Ergebnisprüfung verschwendet Arbeit und lässt Status-Finalizer konkurrieren. | Verzögerte Preview wird real gecancelt; alter `finally` überschreibt neuen Status nicht. |
| M-08 | `NEVER_FULLY_FIXED` | Multi- und Einzelmodell-Telemetrie in zwei generierte Response-Typen/Methoden trennen. | Union-/Dictionary-Heuristik bleibt für JSON-Drift anfällig. | Native C#-Deserialisierung beider OpenAPI-Beispiele einschließlich non-null `modelId`. |
| M-09 | `RELATED_DISTINCT` | P1 Automation-Namen/HelpText für primäre/destruktive Aktionen; P2 Keyboard-Kommandos für Timeline-Nudge/Trim/Scrub; P3 Fokus-/AccessKey-/High-Contrast-Matrix. | Alle 162 Controls blind mit Namen zu versehen erzeugt redundante oder falsche Screenreader-Ausgabe. | Keyboard-only und UIA bei 100/150/200 % DPI; alle P1-Aktionen erreichbar und benannt. |
| M-10 | `RELATED_DISTINCT` | Video-Toolbar als zweizeiliges Grid/WrapPanel; Status/Progress getrennt von Aktionen. | Nur Mindestfenster vergrößern schließt kleinere Displays aus. | Alle Aktionen bei 1280×720, 1400×900 und 150 % DPI sichtbar/erreichbar. |
| M-11 | `NEVER_FULLY_FIXED` | Nur bekannte recoverable Fehler lokal behandeln; unbekannte Dispatcher-Exception kritisch loggen, einmal Fatal-Dialog und kontrolliertes Shutdown beziehungsweise `Handled=false`. | Globales `Handled=true` hält UI scheinbar am Leben, aber möglicherweise mit beschädigtem State. | Injizierte unbekannte Exception beendet kontrolliert und schreibt redigiertes Crashlog. |
| M-12 | `RELATED_DISTINCT` | Chat nur bei `success=true` lokal leeren; GPU-Cleanup typisiert auswerten; KI-Empfehlung mit CTS/Generation und angefragtem Modus korrelieren. | Optimistische UI-Aktualisierung ist schneller, aber unwahr bei Backendfehlern. | false/null/Exception bleiben sichtbar; vertauschte Empfehlungen können neuesten Zustand nicht überschreiben. |
| M-13 | `NEVER_FULLY_FIXED` | Python-3.11-Windows-Lock mit vollständigen Pins+Hashes; NuGet `packages.lock.json` und Locked Mode; `global.json` für freigegebene .NET-9-Familie; Publish-Provenienz/SBOM/Artefakthashes. | Nur Top-Level-Pins lassen transitive Auflösung und SDK variieren. | Frischer Restore nutzt exakt Lockgraph; absichtliche Drift schlägt geschlossen fehl. |
| M-14 | `NEVER_FULLY_FIXED` | Natives `PBStudio.UI.Tests`-Projekt für Serialisierung, Services, ViewModels, Cancellation und Controls; Coverage-Nichtregressionsgrenze; Skip-Allowlist mit Owner/Ablauf; Hardwarelane separat. | Weitere Python-Substringtests beweisen kein C#-Laufzeitverhalten. | Native Tests laufen auf Windows; Coverage und alle Skips werden pro Commit veröffentlicht. |
| M-15 | `NEVER_FULLY_FIXED` | Repo-eigener Security-Workflow: Secret Scan, Python-/NuGet-SCA, Dependency Review, optional CodeQL, SBOM und zeitlich begrenzte Ausnahmen; Connector nur als Zusatz. | Nur den defekten Security-Connector reparieren schafft erneut eine einzelne Ausfallstelle. | Seeded Secret und verwundbare Fixture blockieren Gate; aktueller Report hat bekannte Reichweite. |
| M-16 | `MIXED` | CLAP-/DirectML-Dokumentation und Modulkarte auf Hardwareevidenz aktualisieren; autoritative Skillquelle festlegen; fehlendes `specs/dod.md` anlegen oder Referenz bewusst entfernen; Link-/Widerspruchstest. | Nur einen Satz in `pb-master` ändern lässt Duplikate weiter driften. | Keine widersprüchliche CLAP-Aussage; alle konfigurierten Dokumentpfade existieren. |
| L-01 | `NEVER_FULLY_FIXED` | Handgeschriebene Transport-DTOs durch NSwag-Typen ersetzen; UI-Adapter separat halten; struktureller OpenAPI↔C#-Vergleich. | Weitere manuelle Feldkopien vergrößern den Driftbereich. | `SpectralData` inklusive `band_means`, `band_variances`, `events` roundtript nativ. |
| L-02 | `NEW` | Bei `CachedTabControl.OnApplyTemplate` Presenter aus altem Holder lösen und genau einmal in neuen Holder übernehmen; Cache-/TabItem-Konsistenz sichern. | Cache komplett verwerfen verhindert Parentfehler, verliert aber View-State. | Zweifaches Template-Reapply: ein Parent je Presenter, Inhalt sichtbar, State erhalten. |
| L-03 | `KNOWN_RESIDUE` | Tests nutzen definiertes Temp-Root und `finally`-Cleanup; `.pytest_t362_*/` ignorieren. Bestehende acht Ordner erst nach expliziter Löschfreigabe entfernen. | Automatische Repository-Bereinigung wäre destruktiv und könnte fremde Evidenz entfernen. | Neuer QC-Lauf hinterlässt keine zusätzlichen Scratch-Verzeichnisse. |

## 4. Ausführung T370–T415

### Phase 0 – Governance und Wahrheitsbasis

**Governance-Bootstrap vor T370, keine Produktimplementierung:** Nach
ausdrücklicher Freigabe werden zuerst aktuelle Spec, Tasks, QC und Marker
bytegenau gehasht; `spec.md` und `tasks.md` als exakte historische Kopien mit
Manifest archiviert; historische Requirement-IDs ausschließlich aus Git-Blobs
rekonstruiert; aktive Spec, freigegebener Plan, kanonische T370–T415 und
Release-Checklist registriert. Dies ist Abschluss der SDD-Phasen Specify,
Plan, Checklist und Tasks. Erst danach beginnt Taskausführung.

- **T370 [Z-DOCS] – Evidenz und Archivmanifest bestätigen:** Audit, Git, Branch/CI/Security, Originalhashes und exakte Archivkopien verifizieren.
- **T371 [Z-DOCS] – Spec/Requirement-Registry validieren:** C-03 gemäß D06 schließen; aktive Spec ≤10 KB; historische IDs vollständig und ohne erfundene Definitionen auflösen.
- **T372 [Z-DOCS/Z-TESTS] – SDD-Gate reparieren:** H-07-Validator und negative Governance-Fixtures ausführen. Diese Validator-Selbsttests sind die einzige Testausnahme vor T404.
- **T373 [SHARED] – Release-Gates neu öffnen / Marker invalidieren:** `.completed`/`.qc-passed` nach ausdrücklicher Freigabe entfernen; `qc-report.md` auf `REOPENED / NOT RELEASE-READY`; Checklist-Gate prüfen.

**Gate A:** Keine Produktimplementierung vor gültiger Spec, Tasks, Checklist und wahrheitsgemäß geöffneten Markern.

### Phase 1 – Projektisolation und Persistenzwahrheit

- **T374 [Z-CORE/SHARED] – ProjectOperationContext:** D01, Epoch, Lifecycle-Lock und projektgebundene Task-Registry.
- **T375 [Z-AUDIO] – Audio-Kontext:** Import, Analyse und Stems kontext-/commitgebunden.
- **T376 [Z-VIDEO] – Video-Kontext:** Ingest und Analyse kontext-/commitgebunden.
- **T377 [Z-PACING] – Pacing-Kontext:** Generate/Finalize und Timeline-Mutationen kontextgebunden.
- **T378 [Z-UI-VM/Z-UI-SERVICES] – Timeline-Lifecycle:** Autosave/Preview Snapshot, CTS, Generation und Kontext.
- **T379 [SHARED/Z-DATA] – Persistenzfehler:** H-01 DB-first und typisierte Fehler.
- **T380 [Z-VIDEO/Z-UI-VM] – Analysewahrheit:** H-02 und H-03 schließen.
- **T381 [Z-BRAIN] – Connection-Leases:** M-03 schließen.
- **T382 [Z-PROJEKT] – Atomare Erstellung:** M-01 Staging/Commit/Compensation.
- **T383 [Z-SSE] – Bounded Fanout:** M-04 schließen.

**Gate B:** Fault-Injection und A→B-Barrieren beweisen null projektübergreifende Mutation und null Scheinerfolg.

### Phase 2 – Build, DTO und Runtime-Provisioning

- **T384 [Z-UI-SERVICES/Z-INFRA] – NSwag-Clean-Build:** C-02/D03.
- **T385 [Z-UI-SERVICES] – DTO-Konvergenz:** M-08 und L-01.
- **T386 [Z-RENDER/Z-DATA] – Render-Retry-Identität:** M-02; Schemaänderung nur nach Backup/Freigabe.
- **T387 [Z-INFRA] – DirectML-Provisioning:** H-05 Bundle, Manifest, sichere Installation.
- **T388 [Z-INFRA] – Python-Lock:** M-13 Python-Pins, Hashes und Windows-Wheelvertrag.
- **T389 [Z-INFRA/Z-UI] – .NET-Lock:** `global.json`, NuGet-Lock und Locked Mode.
- **T390 [Z-INFRA] – Provenienz:** Commit, Dirty-State, SDKs, Lockhashes, SBOM und Artefakthashes.

**Gate C:** Frischer externer Windows-Checkout ohne lokale Generator-/Modellreste besteht Restore, Build und Assetprüfung.

### Phase 3 – UI-Sicherheit, Wahrheit und Bedienbarkeit

- **T391 [Z-UI-SERVICES/Z-UI-VM] – Löschbestätigung:** H-04.
- **T392 [Z-UI-VIEWS/Z-UI-VM] – FFmpeg-/Settings-Wahrheit:** M-05 und M-06.
- **T393 [Z-UI-VM/Z-UI-SERVICES] – UI-Ergebniswahrheit:** M-12.
- **T394 [Z-UI] – Exception-Policy:** M-11.
- **T395 [Z-UI-VIEWS] – Responsive Video-Toolbar:** M-10.
- **T396 [Z-UI-VIEWS/Z-UI-VM] – Accessibility P1/P2/P3:** M-09.
- **T397 [Z-UI-CONTROLS] – CachedTab-Reapply:** L-02.

**Gate D:** Cancel/Fehler bleiben wahrheitsgetreu; destruktive Aktionen sind geschützt; 1280×720/1400×900/DPI- und Keyboard/UIA-Matrix besteht.

### Phase 4 – Native Tests, Security und Dokumentation

- **T398 [Z-TESTS] – Native C#-Tests:** M-14; neue Testdependency nur nach Freigabe.
- **T399 [Z-TESTS/Z-INFRA] – Python-Coverage/Skips/Temp:** Coverage-Baseline, Ablauf-Allowlist und künftige Temp-Hygiene; bestehende Altordner nicht löschen.
- **T400 [Z-INFRA] – Security-Workflow:** M-15 mit negativen Seed-Fixtures.
- **T401 [Z-INFRA] – PR-/Branch-CI:** H-06 Workflow für alle Arbeitsbranches und PRs.
- **T402 [Z-DOCS] – Dokumentationswahrheit:** M-16.
- **T403 [SHARED/Z-REVIEW] – Implementierungswahrheit:** unabhängiger Gesamt-Diff-, Architektur-, Security- und Vollständigkeitsreview; erst danach `.completed` mit Task-/Evidence-/Commitdigest erzeugen.

**Gate E:** Native und Python-Gates, SCA/Secrets, Doc-Links und CI laufen für denselben Commit.

### Phase 5 – End-QC und Veröffentlichung

- **T404 – Gezielte Fault-Injection:** Projektwechsel, Persistenz, Settings, QueueFull, Render-Retry.
- **T405 – Python-Gesamtsuite:** Python 3.11, NumPy 1.26.4, `PYTHONPATH=src`, `Tests/`.
- **T406 – Native C#-Tests und WPF Release:** locked restore, 0 Fehler/0 Warnungen.
- **T407 – Clean-Checkout-Windows-Gate:** kein lokaler Generated-/Asset-/Cache-Vorteil.
- **T408 – GUI-Wahrheit:** 14 Views, Löschdialog, Fehlerzustände, 1280×720, 1400×900, DPI-Matrix.
- **T409 – Accessibility-QC:** Keyboard-only, Fokus, UIA, High Contrast.
- **T410 – Projektwechsel-E2E:** aktive Audio-/Video-/Pacing-/Timeline-/Brain-Operationen A→B.
- **T411 – DirectML-/AMF-Fresh-Install:** RX 7800 XT, LUID, Memory-Flags und Pflichtassets.
- **T412 – Render-Retry/Restart:** aktive Deduplizierung, terminaler Retry, Inhaltsidentität.
- **T413 – Security/Provenienz:** validierte Release-Befunde beheben;
  Secret/SCA/SBOM/Hashes/Backend-Autorisierung/Commitidentität für denselben SHA.
- **T414 – Abschlusswahrheit:** QC-Bericht, Changelog, ADR, Brain und Marker-Digests; `.qc-passed` nur bei 100 % PASS.
- **T415 – Veröffentlichung:** PR, Required Checks, Review/Merge, Default-Branch/Protection und Release aus geschütztem Main; externe Mutation nur nach Freigabe.

#### T413-Reparaturpakete

| Paket | Zone | ETA | Inhalt | Gate |
|---|---|---:|---|---|
| T413-S1 | SHARED/Z-UI-SERVICES | 4–8 h | Backend-Besitzbeweis, Default-Deny-Autorisierung, WPF-/SSE-/interne Client-Bindung | Spoof-, Missing-/Wrong-Capability- und Attach-Tests |
| T413-S2 | Z-CHAT | 1–2 h | Prompt-/Antwortinhalte aus Backend-Logs entfernen | Secret bleibt im Chat, nie im Log-SSE |
| T413-S3 | Z-PACING | 1–2 h | Timeline-Anzahl und Bodygröße vor Parse begrenzen | Grenz-/Oversize-Tests |
| T413-S4 | Z-DATA | 2–4 h | Legacy-Pickle nur als geprüfte primitive Struktur migrieren | Safe-/Malicious-/Malformed-Migration |
| T413-S5 | Z-INFRA | 4–12 h | OSV-SCA auf exakten Lockgraph umstellen; Python-Graph schließen | Lock=Report, Hash-, Alias- und Negativfixtures |
| T413-S6 | Z-INFRA | 1–3 h | MCP ohne `@latest`, versioniert und integritätsgebunden starten | Offline-/Tamper-Vertrag |
| T413-S7 | QC | 3–6 h | Voll-/Diff-Scan, Secrets, SCA, SBOM, Publish-Artefakt und Provenienz auf finalem SHA | keine offenen Releaseblocker; `release_eligible=true` |

S1, S2, S3 und S4 dürfen bei disjunkten Dateien parallel laufen. S5/S6
beginnen erst nach der in Abschnitt 5 geforderten Einzelgenehmigung. S7 folgt
erst nach unabhängigem Diff-Review aller Pakete. Der bestehende Loop-Guard
gilt je Paket; ein unveränderter Fehllauf wird nicht wiederholt.

## 5. Zwingende Freigaben vor Ausführung

Der Plan ist noch keine Freigabe für folgende Aktionen:

1. Entfernen beziehungsweise Neuerzeugen von `.completed` und `.qc-passed`.
2. Kompaktieren/Verschieben historischer Spec-Inhalte.
3. Änderung des öffentlichen WPF/API-Projektkontextvertrags (`IApiClient.cs`).
4. RenderQueue-Schemaänderung und zugehöriges Backup.
5. Neue Lockfiles, `global.json`, Test-/Security-Dependencies oder Tooling.
6. Löschen der acht vorhandenen `.pytest_t362_*`-Ordner.
7. Veröffentlichung eines DirectML-Asset-Bundles beziehungsweise externe Downloads.
8. GitHub-PR, Merge, Default-Branch, Ruleset/Branchschutz und Release.

## 6. Parallelität und Reihenfolge

- Shared State, `backend/app_state.py`, öffentliche DTOs, Projektkontext und Datenbankschema bleiben sequenziell.
- Nach T374 dürfen Z-AUDIO, Z-VIDEO, Z-PACING und Z-BRAIN parallel arbeiten, solange keine Shared Files überlappen.
- UI-Accessibility beginnt erst nach stabilen Controls/Toolbars und DTOs.
- Clean-Build C-02 ist Voraussetzung für M-08, L-01 und native C#-Tests.
- CI-/Branchschutz wird erst nach lokal und im Clean-Checkout grünen Gates extern aktiviert.
- Parent führt nach jeder parallelen Welle Syntax-/XML-/Truncation-Sweep,
  statische Vertragsprüfung, unabhängiges Diff-Review und `git status --short`
  aus. Funktionale Tests und Gesamtsuite bleiben für T404–T413 reserviert.

### Team- und Skill-Routing

| Verantwortung | Owner | Pflichtskills/Tools |
|---|---|---|
| Gesamtleitung, Shared-Zones, Merge, Wahrheit | Hauptagent/Teamleiter | `caveman`, `pb-master`, Plan-/Git-/Evidence-Tools |
| SDD, Fortschritt, Doku | Z-DOCS-Agent | `caveman`, SDD-Regeln, `doc-coauthoring` bei Bedarf |
| Projektkontext/Persistenz | Z-CORE/Z-DATA-Leads | `caveman`, `projekt-expertise`, `pb-master` |
| Audio | Z-AUDIO-Agent | `caveman`, `audio-expertise` |
| Video | Z-VIDEO-Agent | `caveman`, `video-expertise` |
| Pacing/Brain | Z-PACING/Z-BRAIN-Agenten | `caveman`, `pacing-expertise`, `brain-expertise` |
| Render/Runtime | Z-RENDER/Z-INFRA-Agenten | `caveman`, `rendering-expertise`, `gpu-expertise` |
| WPF/API/UI | Z-UI-Agenten | `caveman`, `timeline-expertise`, `wpf-gui-verification` |
| Tests/QC | unabhängige Z-TESTS-Agenten + Parent | `caveman`, `run-tests`, `auto-qa-loop`, `wpf-gui-verification` |
| Security | unabhängiger Reviewer | Codex-Security-Tools, falls Runtime verfügbar; repo-eigener Fallback bleibt Pflicht |
| Externer Zweitreview/abgegrenzte Teilaufgaben | Claude-Code-Worker unter Kontrolle des Teamleiters | Claude Code CLI, Safe-Mode, explizite Tool-Allowlist, Kosten-/Zeitlimit, JSON-Ergebnis |

`cavecrew`-Investigator lokalisiert; Builder ändert höchstens zwei klar
zugewiesene Dateien; Reviewer prüft Diffs. Cross-cutting Änderungen bleiben
beim Teamleiter oder einem spezialisierten Entwicklungsagenten. Plugins werden
nur genutzt, wenn ihre reale Verbindung und Relevanz geprüft ist.

### Claude-Code-Zusatzagent

Claude Code CLI `2.1.212` ist am 2026-07-31 lokal geprüft und über das
vorhandene Claude.ai-Max-Abo angemeldet. Ein isolierter Headless-Lauf ergab
`CLAUDE_CONTROLLER_READY`; ein zweiter, echter Read-only-Repo-Lauf ergab
`CLAUDE_READ_READY`. Der Hauptagent bleibt alleiniger Teamleiter und PASS-Owner.

Der vorgesehene `claude-session-driver` `4.0.0` kann auf diesem nativen
Windows-System keine stabile tmux-Workersitzung erzeugen; der Start endet nach
30 Sekunden ohne Session oder Artefakte. Nach Anti-Loop-Regel wird dieser Pfad
nicht blind wiederholt. Bis WSL beziehungsweise ein kompatibles tmux bewusst
bereitgestellt wird, erfolgt die Steuerung Windows-nativ über `claude -p`.

Verbindlicher Startvertrag je Claude-Worker:

- eindeutige Ticket-ID, disjunkte Zone, erlaubte Dateien, Non-Goals,
  Abnahmekriterium und maximale Ausgabe,
- standardmäßig `--safe-mode`, minimales Systemprompt,
  `--no-session-persistence`, `--output-format json` und `--effort low`,
- Read-only mit expliziter `--tools`-Allowlist; `Write`, `Edit`, `Bash`,
  Webzugriff und Claude-Subagenten bleiben gesperrt,
- Schreibrechte nur für einen ausdrücklich als Builder zugewiesenen Task in
  einer reservierten disjunkten Zone. Jeder Builder läuft in einem eigenen
  temporären Git-Worktree ohne Shared-File-Auftrag; kein Diff wird übernommen,
  bevor ein Pfad-Allowlist-Validator ausschließlich die zugewiesenen Dateien
  bestätigt. Fremd-/Shared-Zonenänderungen verwerfen den gesamten Worker-Diff,
- `--max-budget-usd` ist pro Lauf zwingend und wird vor Start im Evidence-
  Datensatz vermerkt; Erhöhung nur nach neuer Evidenz und Ledger-Begründung,
- ein Controller pro Worker, keine doppelte Ticket-/Zonenbearbeitung und kein
  automatisches Resume nach Fehler oder Budgetabbruch,
- der Teamleiter prüft Git-Diff, Dateiinhalte und Verify-Artefakte selbst;
  Claude-Prosa ist niemals PASS-Evidenz.

Feste Claude-Laufgrenzen:

| Rolle | Wallclock | `--max-budget-usd` | Starts je Ticket |
|---|---:|---:|---:|
| Investigator/read-only | 10 min | 0,15 | 2 |
| Reviewer/read-only | 15 min | 0,25 | 1 |
| Builder im isolierten Worktree | 30 min | 0,75 | 1 |

Maximal zwei Claude-Worker dürfen gleichzeitig in disjunkten Zonen laufen.
Für OBJ-72 gilt ein Gesamtkontingent von 10,00 USD gemeldeter
CLI-Kostenäquivalenz. Danach startet ohne ausdrückliche Nutzerfreigabe kein
weiterer Claude-Lauf. `--max-budget-usd` ist ein Abbruchschwellwert und kann
durch einen bereits laufenden Modellaufruf überschritten werden; deshalb
bleiben Safe-Mode, minimale Kontexte und explizite Modelle/Tools Pflicht.

Setup-Nachweis:
`evidence/claude-controller-setup-2026-07-31.md`.

### Zeitplan pro Task

Schätzungen sind aktive Arbeitszeit, keine Garantie. Ledger ersetzt ETA
automatisch durch Ist-Zeit und neue Evidenz.

| Task | ETA | Task | ETA | Task | ETA |
|---|---:|---|---:|---|---:|
| T370 | 0,5–1 h | T386 | 6–10 h | T402 | 3–5 h |
| T371 | 2–4 h | T387 | 8–16 h | T403 | 2–4 h |
| T372 | 3–6 h | T388 | 6–12 h | T404 | 3–6 h |
| T373 | 0,5–1 h | T389 | 3–6 h | T405 | 1–3 h |
| T374 | 6–10 h | T390 | 4–8 h | T406 | 1–3 h |
| T375 | 4–8 h | T391 | 2–3 h | T407 | 2–5 h |
| T376 | 5–10 h | T392 | 5–8 h | T408 | 3–6 h |
| T377 | 4–8 h | T393 | 4–6 h | T409 | 3–6 h |
| T378 | 4–8 h | T394 | 2–4 h | T410 | 4–8 h |
| T379 | 6–10 h | T395 | 2–3 h | T411 | 4–8 h |
| T380 | 6–10 h | T396 | 16–32 h | T412 | 3–6 h |
| T381 | 5–8 h | T397 | 2–4 h | T413 | 2–5 h |
| T382 | 4–6 h | T398 | 12–20 h | T414 | 2–4 h |
| T383 | 1–2 h | T399 | 4–8 h | T415 | 1–3 h |
| T384 | 1–2 h | T400 | 6–12 h |  |  |
| T385 | 3–5 h | T401 | 4–8 h |  |  |

Gesamtschätzung: **160–285 aktive Stunden**, zuzüglich Clean-VM-, Hardware-,
Full-Length-Render-, CI-Warte- und Reviewlaufzeiten. Parallelität reduziert
Wandzeit, nicht Arbeitsaufwand.

### Automatische Fortschrittsanzeige

`repair-progress.md` ist einzige laufende Statusquelle. Pro Task:

- Status: `OPEN`, `IN_PROGRESS`, `REVIEW`, `PASS` oder `BLOCKED`
- Prozent gesamt und je Phase
- ursprüngliche ETA, Ist-Zeit, Owner und Zone
- Evidenzlink und nächster Schritt

Start, aktuelle ETA, Agent, Skills, erlaubte Dateien, Root Cause, Blocker,
Diff, Review, Commit und Remote-SHA stehen im verlinkten Task-Evidence-Datensatz
und werden bei jeder Statusänderung aktualisiert.

Nur der Teamleiter ändert `PASS`. Nach jedem Statuswechsel werden Plan,
Tasks-Checkbox, Ledger und Evidence abgeglichen.

### Custom-Zonen

| Zone | Exakte Filegrenze |
|---|---|
| `Z-PROJEKT` | `backend/routers/project_router.py`, `backend/schemas/project_schemas.py`, `PBStudio.UI/Services/ProjectService.cs`, projektbezogene Tests |
| `Z-SSE` | `backend/routers/events_router.py`, `backend/events.py`, `PBStudio.UI/Services/SSEClient.cs`, SSE-Tests |
| `Z-UI-CONTROLS` | `PBStudio.UI/Controls/**`, zugehörige Control-/GUI-Tests |
| `Z-REVIEW` | read-only gesamter Diff; schreibt ausschließlich Review-Evidence unter `specs/00013-system-wide-bug-hunting-audit/evidence/` |

`backend/app_state.py`, `backend/main.py`, `IApiClient.cs`, `ApiClient.cs`,
öffentliche Schemas, Datenbankschema und SDD-Kernartefakte bleiben Shared Files
und werden sequenziell vom Teamleiter reserviert.

### Anti-Loop- und Token-Schutz

Diese Regeln gelten für Hauptagent, Skills, Plugins, Tools, Agenten und
Subagenten:

1. **Keine Wiederholung ohne neue Evidenz:** Derselbe Befehl mit denselben
   Argumenten und demselben erwartbaren Zustand darf höchstens zweimal
   ausgeführt werden.
2. **Drei Fixzyklen maximal:** Dieselbe Fehlersignatur erhält höchstens drei
   Änderung→Prüfung-Zyklen. Danach stoppt der Task und wechselt zwingend zu
   unabhängiger Root-Cause-Prüfung oder `BLOCKED`.
3. **Drei Hypothesen maximal:** Gleichzeitig dürfen höchstens drei konkrete,
   falsifizierbare Ursachenhypothesen offen sein. Neue Hypothese erst nach
   Verwerfen oder Bestätigen einer alten.
4. **Evidence-Deduplizierung:** Teamleiter führt pro Task bekannte Suchorte,
   gelesene Dateien, Befehle, Fehlerhashes und Ergebnisse im Ledger. Kein Agent
   untersucht dieselbe Frage erneut, außer als ausdrücklich unabhängiger
   Reviewer.
5. **Harte Zeitgrenze:** 45 Minuten ohne neue Evidenz oder zweimalige
   Überschreitung der aktuellen ETA beendet den laufenden Ansatz. Agent meldet
   letzten Beleg, offene Hypothese und kleinsten nächsten Versuch.
6. **Agenten-Liveness:** Agent meldet spätestens alle 30 Minuten neue Evidenz
   oder einen Blocker. Teamleiter unterbricht Agenten ohne Fortschritt und
   startet nicht blind denselben Prompt erneut.
7. **Begrenzte Prompts:** Jeder Subagent erhält Zone, Non-Goal, Ticket,
   Deliverable, Verify und maximale Ausgabegröße. Kontext wird nur soweit
   geforkt, wie der Task benötigt.
8. **Caveman-Ausgabe:** Agenten liefern path:line, Änderung, Verify und Blocker;
   keine Erzählung, Wiederholung oder ungefragte Architekturbreite.
9. **Keine doppelten Volltests:** Gesamtsuite, Clean-Checkout, GUI, Hardware und
   Full-Length-Render laufen nur in ihren T404–T413-Gates oder nach einer
   belegten Gate-relevanten Änderung.
10. **Keine Scope-Erweiterung:** Entdeckte Nebenbefunde werden mit Evidenz
    registriert. Nur releasekritische Befunde dürfen den aktiven Task erweitern;
    andere gehen in ein späteres Backlog.
11. **Tool-Polling begrenzen:** Unveränderter externer Zustand wird nicht in
    schneller Folge abgefragt. Langläufer werden nur im fachlich notwendigen
    Intervall geprüft.
12. **Stop bei Zielerreichung:** Sobald Task-Abnahmekriterien und Reviewbeleg
    vollständig sind, endet Arbeit am Task. Keine zusätzliche „Verbesserung“.
13. **Claude-Budgetabbruch ist final für den Lauf:** Nach
    `error_max_budget_usd` wird nicht automatisch mit höherem Limit
    wiederholt. Der Teamleiter reduziert zuerst Kontext/Tools; höchstens ein
    kalibrierter Folgelauf ist zulässig.
14. **Claude-Worker bleiben isoliert:** Kein Claude-Worker darf eigene
    Subagenten starten, eine bereits aktive Zone übernehmen, Shared Files
    schreiben oder ohne neuen Auftrag eine persistierte Sitzung fortsetzen.
15. **Claude-Worktree-Gate:** Builder arbeiten nur in einem temporären
    Worktree. Der Teamleiter übernimmt Änderungen erst, wenn der geänderte
    Pfadsatz eine exakte Ticket-Allowlist erfüllt; jeder Fremdpfad verwirft
    den Worker-Diff.

Standard-Ausgabebudgets:

- Investigator: höchstens 800 Output-Tokens beziehungsweise 8 Findings.
- Builder: höchstens 500 Output-Tokens plus Diff-/Verify-Verweis.
- Reviewer: höchstens 700 Output-Tokens beziehungsweise 10 Findings.
- Mehr Kontext oder Ausgabe nur nach Teamleiterbegründung im Ledger.
- Full-History-Fork nur bei echtem Cross-Module-Vertrag; sonst minimaler
  Turn-Fork oder expliziter Dateikontext.

Jeder Loop-Abbruch wird im Ledger als `LOOP_GUARD` mit Fehlersignatur,
Versuchszahl, verbrauchter Zeit und nächster Entscheidung protokolliert.

## 7. Consulting-Team-Stresstest

### Executive Summary

Die technisch stärkste Hebelwirkung besitzt D01: Ein durchgängiger Projektkontext schließt C-01 und reduziert M-03, M-07 und Teile von H-03 gemeinsam. Der Plan darf trotzdem nicht als eine große ungeteilte Reparatur ausgeführt werden. Releaseblocker und spätere Produktpolitur bleiben durch Gates getrennt.

### Findings

1. **Analyst – CRITICAL, Confidence 95 %, Reversibilität mittel:** Primärquellen stützen die Build-, Cancellation-, Transaktions- und Lockstrategie. Gegenposition: Frameworkmuster allein beweisen nicht PB-spezifische Korrektheit. Entscheidung: negative Fault-Injection und Clean-Checkout sind verpflichtend.
2. **Devil’s Advocate – HIGH, Confidence 90 %, Reversibilität hoch:** 46 Tasks können Scope und Fehlerrisiko erhöhen. Gegenposition: Nur C/H zu beheben lässt bekannte Wahrheits-/Security-Gates offen. Entscheidung: Gates A–C bilden einen eigenständig releasekritischen ersten Zug; Phasen 3–4 dürfen separat terminiert werden, aber `.qc-passed` bleibt bis T414 gesperrt.
3. **Historian – HIGH, Confidence 95 %, Reversibilität hoch:** Frühere „PASS“-Aussagen scheiterten an zu engen Tests, nicht primär an fehlendem Einsatz. Gegenposition: Die 1.090 Python-Tests und GUI-Smokes bleiben wertvoll. Entscheidung: Bestehende Tests behalten, aber durch Clean-, native und negative Verträge ergänzen.
4. **Pragmatist – HIGH, Confidence 90 %, Reversibilität mittel:** Accessibility mit 2–4 Tagen darf C-01/C-02 nicht blockieren. Gegenposition: Bedienbarkeit ist Produktqualität. Entscheidung: P1 destruktive/primäre Controls ist releasepflichtig; vollständige P2/P3-Matrix bleibt in derselben QC-Evidenz, kann aber nach Stabilisierung der Kernpfade umgesetzt werden.
5. **User Advocate – CRITICAL, Confidence 95 %, Reversibilität hoch:** Löschen ohne Bestätigung und Scheinerfolg sind unmittelbar vertrauensschädlich. Gegenposition: Dialoge erzeugen Reibung. Entscheidung: Nur irreversible/bulk Aktionen bestätigen; Erfolgsmeldungen bleiben strikt backendgebunden.
6. **Security – CRITICAL, Confidence 90 %, Reversibilität mittel:** Ignorierte Assets, ungeschützte Branches und unbekannte SCA-Lage verhindern externe Freigabe. Gegenposition: Lokale Offline-App hat geringere Angriffsfläche. Entscheidung: Herkunft, Hash, sichere Extraktion, Dependency Gate und geschützter Release-SHA bleiben Pflicht.
7. **Systems Thinker – CRITICAL, Confidence 95 %, Reversibilität niedrig:** Ein halb eingeführter ProjectContext wäre gefährlicher als der aktuelle klar erkennbare Singleton. Gegenposition: Big-Bang-Migration erhöht Risiko. Entscheidung: zentraler Kontext zuerst, danach zonenweise Konsumenten, mit Fail-Closed-Kompatibilitätsphase und A→B-Barrieren nach jeder Zone.

### Steel-Man und Cross-Examination

- Stärkstes Gegenargument: Die App ist lokal funktionsfähig; ein 90–150-Stunden-Plan könnte mehr Regressionen erzeugen als er schließt.
- Antwort: Deshalb werden keine 29 unabhängigen Schnellfixes ausgeführt. Fünf Architekturverträge, phasenweise negative Tests und Clean-Checkout-Gates begrenzen die Änderung.
- Analyst fordert messbare Belege statt weiterer Dokumentation; Historian bestätigt, dass Dokumentation ohne Gegenprobe bereits falsche Sicherheit erzeugte.
- Pragmatist fordert Priorisierung; User Advocate und Security setzen H-04, H-01, H-05 und H-06 als nicht verschiebbare Vertrauensgrenzen.

### Nicht verhandelbare Risiken

- Projekt-A-Daten dürfen unter keinem Timing in Projekt B committen.
- Fehlerhafte Persistenz darf nie als Erfolg erscheinen.
- Ein Release darf keine lokalen ignorierten Dateien voraussetzen.
- `.qc-passed` darf ohne belegbaren Task-/Evidence-/Commitdigest nicht existieren.
- Kein Release aus ungeschütztem Backup-/Feature-Branch.

## 8. Primärquellen

- Microsoft: [Generated files in MSBuild](https://learn.microsoft.com/en-us/visualstudio/msbuild/customize-builds-for-generated-files)
- Microsoft: [Custom code generation before CoreCompile](https://learn.microsoft.com/en-us/visualstudio/msbuild/tutorial-custom-task-code-generation)
- Python 3.11: [Task cancellation and TaskGroup](https://docs.python.org/3.11/library/asyncio-task.html)
- SQLite: [Transactions, commit and rollback](https://www.sqlite.org/lang_transaction.html)
- Microsoft: [NuGet lock files and locked mode](https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files)
- Microsoft: [.NET SDK selection with global.json](https://learn.microsoft.com/en-us/dotnet/core/tools/global-json)
- pip: [Repeatable installs and hash checking](https://pip.pypa.io/en/stable/topics/repeatable-installs/)
- GitHub: [Protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- GitHub: [Required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
- Microsoft: [WPF DispatcherUnhandledException](https://learn.microsoft.com/en-us/dotnet/api/system.windows.application.dispatcherunhandledexception)
- Microsoft: [Windows accessibility overview](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-overview)
- Python: [asyncio.Queue overflow behavior](https://docs.python.org/3/library/asyncio-queue.html)

## 9. Release-Abnahmesatz

PB Studio ist erst release-ready, wenn ein sauberer externer Windows-Checkout ohne lokale Modelle, generierte Dateien oder Caches einen gelockten Restore, Build, native und Python-Tests, verifizierte DirectML-Asset-Bereitstellung, AMD-DirectML-/AMF-Smokes, Projektwechsel-Barrieren, Security/SBOM/Hashmanifest und verpflichtende PR-/Main-Gates für exakt denselben geschützten Commit bestanden hat.
