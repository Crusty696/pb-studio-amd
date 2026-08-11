# Spezifikation: OBJ-77 Vollstaendige Anforderungsremediation

**Status:** SPECIFIED  
**Feature-Workspace:** `specs/00022-complete-requirements-remediation`  
**Audit-Baseline:** `REQUIREMENTS_GAP_AUDIT_2026-08-11.md`  
**Audit-SHA-256:** `D77F233535BD3E13F6DCCB9F7FEE34589FD4FE56ACD6DC355D369E4C208016EA`

## Problem

Der Audit vom 2026-08-11 weist 74 nummerierte Hauptbefunde und sechs separat
gefuehrte OBJ74-Rueckstaende nach. Zusaetzlich verhindern ungeloeste SDD-,
Traceability-, Live-, Hardware-, Performance- und Release-Gates eine ehrliche
Requirements-Complete- oder Release-Aussage. Einzelne gruen markierte Tests
beweisen nicht die vollstaendige Produktkette von WPF ueber API und Core bis
Persistenz, Restart/Resume, SSE und sichtbarem UI-Ergebnis.

## Scope

### Enthalten

- alle Befunde `A-01..A-23`, `V-01..V-11`, `P-01..P-12`, `K-01..K-19`,
  `D-01..D-09` sowie `P-B01..P-B06`
- additive, rueckwaertskompatible Stage-Receipts und wahrheitsgetreue
  Gesamtstatusableitung
- FAISS als produktiver Mediensuchindex und sqlite-vec als produktiver
  Brain-KNN-Store mit gemeinsamem Owner-/Recovery-Vertrag
- Audio-, Video-, Pacing-, KI-, Datenbank- und WPF-Reparaturen durch die
  vollstaendige UI-API-Core-Persistenz-Signalkette
- echte Ground-Truth-, DirectML-, GUI-, Restart-/Resume-, Last- und Live-Gates
- additive Compliance-Metadaten fuer historische SDD-Workspaces ohne
  Umschreiben historischer Evidence
- sieben sequenzielle Lieferwellen mit eigenem gruenen Merge-Gate

### Ausgeschlossen

- CUDA, ROCm, CPU-EP oder PyTorch als ONNX-Inference-Fallback
- Ersetzen von FAISS durch sqlite-vec
- fachfremde Features oder Refactorings
- Aenderung der LOCKED Stem-Separationsdateien ohne explizite Freigabe
- Bulk-Nachanalyse vor erfolgreichem T003, Recovery-Probe, T019-Canary und Go
- Umschreiben oder Rueckdatieren historischer Spec-/Task-/QC-Inhalte
- Veraendern des vorgefundenen dirty Ursprungsworktrees

## Objective

**OBJ-77:** PB Studio schliesst jeden Auditbefund einzeln, nachweisbar und
rueckwaertskompatibel. Kein Befund darf durch Sammelstatus, alte Evidence,
Build-only-Nachweis oder nicht ausgefuehrte Live-/Hardware-Gates verdeckt
werden.

## Functional Requirements

- **FR-402:** Ein maschinenlesbares Ledger fuehrt alle 80 Befundzeilen mit
  qualifizierter Requirement-ID, Wave, Zone, Reproduktion, Vertrag, Test,
  Evidence, Commit und Status.
- **FR-403:** Audio- und Videoanalyse verwenden additive versionierte
  Stage-Receipts mit requested/status, Fingerprints, Artefaktidentitaet,
  Validitaet, Zeiten, Fehler, Provider, Modell, Attempts und Korrelation.
- **FR-404:** Gesamtstatus und Retry werden ausschliesslich aus angeforderten
  Stages abgeleitet. Valide abgeschlossene Stages ueberleben Fehler, Shutdown,
  Restart, Projekt-Reload und Retry.
- **FR-405:** FAISS bleibt 1152-D-Mediensuchindex. sqlite-vec wird produktiver
  Brain-KNN-Store. Jeder Write validiert manifestierte Dimension, dtype,
  Endlichkeit, Nicht-Nullvektor, Owner, Projekt, Medium und Recovery-Generation.
- **FR-406:** Alle 23 Audio-Befunde werden von Producer bis WPF und Messbeleg
  geschlossen, einschliesslich Downbeats/Takte, Mel/Depth, Long-Mix-Quellen,
  Hash-Invaliderung, Subtracks, Embedding- und Waveformwahrheit.
- **FR-407:** Alle elf Video-Befunde werden von Analyse/Persistenz bis Suche,
  virtualisierter Library, sequenziellem Decode, DirectML-Scene-Pfad und
  realem Tagging-/Canary-Receipt geschlossen.
- **FR-408:** Alle zwoelf Pacing-Befunde und sechs OBJ74-Rueckstaende werden im
  konvergierten Tree geschlossen; Auswahlprovenienz, Timeline-Lifecycle,
  Virtualisierung, Performance, Cut-Genauigkeit und Sync-Drift sind sichtbar
  und gemessen.
- **FR-409:** Alle 19 KI-Befunde werden geschlossen, einschliesslich effektiver
  Mode-/Override-Wahrheit, Live-Modellstatus, Brain-Deep-Hook, DirectML-Assets,
  UI-Bindings, DPI, High Contrast und Hardwarematrix.
- **FR-410:** Alle neun Datenbankbefunde werden geschlossen, einschliesslich
  strict Project-ID, Partial-Reload, Dual-Store-Sicherheit, 4h/4GB-Stress und
  deterministischer Recovery-Testisolation.
- **FR-411:** WPF nutzt UI- und Datenvirtualisierung gemeinsam; Backend paging,
  Viewport-Prefetch, Thumbnail-Cancellation und Recycling begrenzen RAM und
  UI-Arbeit bei mindestens 10.000 Videos und 1.000 Timeline-Items.
- **FR-412:** Historische Workspaces bleiben inhaltlich unveraendert und
  erhalten additive, hashgebundene Compliance-Metadaten. Aktive Workspaces
  bestehen den strikten aktuellen Validator.

## Technical Requirements

- **TR-384:** Jede ORT-DirectML-Session nutzt nur `DmlExecutionProvider`,
  deaktiviert Memory-Pattern und CPU-Arena, setzt `ORT_SEQUENTIAL` und
  serialisiert `Run` derselben Session ueber GPU-Lock/VRAM-Lifecycle.
- **TR-385:** StageReceipt-V1 ist additiv. Legacy-Daten werden als Version 0
  hochkonvertiert; bestehende Status-/Fehlerfelder bleiben bis nach OBJ-77.
- **TR-386:** Datenmigrationen laufen nur nach Backup, Hashmanifest, Dry-Run,
  Crash-Injection, Restore und verifiziertem Rollback. Keine Altdatei wird
  innerhalb OBJ-77 geloescht.
- **TR-387:** Backend-Schema, OpenAPI, C#-DTO, ApiClient, ViewModel und
  Persistenz besitzen fuer jeden neuen Vertrag Feldparitaetstests.
- **TR-388:** Messreceipts binden Medien-, Git-, Config-, Asset- und
  Hardware-Hashes, Versionen, Cold/Warm-Zustand, Rohdaten und Statistik.
- **TR-389:** Echte Medien stammen ausschliesslich aus den freigegebenen Audio-
  und Video-Testdatenordnern. Mocks oder synthetische Medien ersetzen keinen
  Live-/Ground-Truth-Nachweis.
- **TR-390:** Jede Wave kompiliert geaenderte Python-Dateien, prueft XAML/XML,
  fuehrt fokussierte und Domain-E2E-Tests aus und baut WPF Release bei C#-Aenderung.
- **TR-391:** Nach Wave 6 laufen Python-Vollsuite in getrennten Prozessen,
  native C#-Tests, WPF Release, OpenAPI-Drift, GUI-, Hardware-, Live-,
  Performance-, Recovery-, Secret- und Iron-Rule-Gates.

## Operational Requirements

- **OR-361:** Der dirty Ursprungsworktree bleibt unangetastet. OBJ-77 arbeitet
  in einem separaten Worktree ab Commit `8328d492f8b1`.
- **OR-362:** Sieben Waves werden sequenziell vom jeweils gruenen
  Integrations-SHA erzeugt. Shared-Zones bearbeitet nur der Parent.
- **OR-363:** Externe Hardware, LM Studio, Ground Truth und Langzeitfenster
  werden vor Start der betroffenen Wave reserviert; fehlende Infrastruktur
  blockiert ehrlich statt durch Skip oder Simulation ersetzt zu werden.
- **OR-364:** T019 benoetigt nach T003 ein separates Go. Bulk bleibt bis zu
  10/10 terminal korrekten Canaries gesperrt.
- **OR-365:** IApiClient-Vertragsaenderung, Dateiloeschung K-11 und Pausieren
  eines fremden Watchdogs erhalten die vorgeschriebenen expliziten Gates.
- **OR-366:** Test-Cleanup entfernt nur in einem Testmanifest erfasste IDs und
  Dateien. Nutzerprojekte, Bestandsdaten und fremde Artefakte bleiben erhalten.

## Success Criteria

- **SC-109:** Das Ledger enthaelt exakt 74 Hauptbefunde plus sechs
  Branch-Rueckstaende; keine Zeile fehlt und keine ID ist mehrdeutig.
- **SC-110:** Kein Befund verbleibt `MISSING`, `PARTIAL`, `UNVERIFIED`,
  `NO-GO` oder als ungeloester `DOC-CONFLICT` bei Releasefreigabe.
- **SC-111:** Python-Vollsuite und native C#-Tests haben null Fehler; WPF
  Release baut mit null Fehlern und null Warnungen.
- **SC-112:** Restart/Resume berechnet nur fehlende, failed, interrupted oder
  neu angeforderte unavailable-Stages und veraendert keine validen Artefakte.
- **SC-113:** GUI-, 10k-Library-, 1k-Timeline-, KPI-, 4h/4GB-, LM-Studio- und
  AMD/Intel/NVIDIA-DirectML-Gates besitzen aktuelle commitgebundene Receipts.
- **SC-114:** Alle Wave-Reviews, Required Checks und der finale Main-Merge sind
  gruen; Remote-SHA, Release-Binary und lokaler Produktpfad sind verifiziert.

## Task Range

T001-T080 bilden die 80 einzelnen Befundzeilen ab. T081-T096 bilden Foundation,
Konvergenz und Release-Gates ab. Abschluss- und Markerdateien bleiben gesperrt,
bis alle Success Criteria durch aktuelle Evidence belegt sind.
