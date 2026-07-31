# Spezifikation: OBJ-72 Release-Fähigkeit

**Status:** DRAFT / NOT ACTIVE
**Ziel:** reproduzierbares vollständiges Windows-Release; Betriebssicherheit ergänzend
**Feature-Workspace:** `specs/00013-system-wide-bug-hunting-audit`

## Historische Basis

Abgeschlossene OBJ-1–OBJ-71 bleiben unverändert in:

- `history/spec-through-obj71-2026-07-30.md`
  - SHA-256: `f9a3a816fd153f11ca5704e69308f1ddd417ebd02630d5f2853075f6eb6c543a`
- `history/tasks-through-t369.md`
  - SHA-256: `3b3be044962dc9051e0c6d4fb97b72b2226417e6d18ffb3be519f5a922440e22`
- `history/requirement-registry-through-obj71.md`
  - Hash im Archivmanifest
- `history/archive-manifest-obj71.json`
  - SHA-256: `942219d02437fef0b8369b2f7b1139915d226c8679a77c3510ecdba8a589fc8a`

Archivkopien müssen bytegenau sein. Fehlender oder falscher Hash blockiert Gate A.

## Problem

Lokaler Lauf und inkrementeller Build beweisen kein auslieferbares Release.
Aktuell fehlen reproduzierbarer Clean-Build, gelockte Abhängigkeiten,
vollständige Runtime-Bereitstellung, geschützter Releasepfad und belastbare
Security-/Native-Test-Gates. Zusätzlich dürfen Projektwechsel,
Persistenzfehler und parallele Jobs keine falschen Erfolge oder
projektübergreifenden Writes erzeugen.

## Scope

### Enthalten

- Clean-Checkout, Restore, Build, Runtime-/Modell-Provisioning
- Dependency Locks, SBOM, Hash- und Commitprovenienz
- CI, Security-Gates, geschützter Main-/Releasepfad
- native Python-/C#-, GUI-, Hardware- und Installations-QC
- Projektkontext, Persistenzwahrheit, Cancellation und kontrollierte Fehler
- sichtbare Fehler-, Lösch-, Settings- und Accessibility-Verträge

### Ausgeschlossen

- allgemeiner Deep-Audit jeder internen Funktion
- neue Produktfeatures ohne Releasebezug
- CPU-, CUDA-, ROCm- oder Software-Encoder-Fallbacks
- Treiber-/Systeminstallation ohne Einzelgenehmigung
- Beseitigung historischer Scratch-Verzeichnisse ohne Löschfreigabe

## Objective

**OBJ-72:** PB Studio muss aus einem sauberen externen Windows-Checkout für
exakt einen geschützten Commit vollständig wiederherstellbar, baubar,
installierbar, startbar, prüfbar und veröffentlichbar sein. Ergänzend dürfen
Projektwechsel, Persistenzfehler und Parallelität keine Daten dem falschen
Projekt zuordnen oder Erfolg vortäuschen.

## Governance Requirements

- **OR-335:** Bytegenaue Archive, Requirement-Registry, aktive Spec ≤10.240
  UTF-8-Bytes, kanonische T370–T415 und abgeschlossene Checklist müssen vor
  Produktimplementierung bestehen.
- **OR-336:** Frühere OBJ-71-Marker bleiben historische Evidenz. Aktive
  `.completed`/`.qc-passed` fehlen bis zu ihren OBJ-72-Gates; `qc-report.md`
  lautet bis T414 `REOPENED / NOT RELEASE-READY`.
- **OR-337:** Jeder Task besitzt Owner, Zone, erlaubte Dateien, ETA, Evidenz
  und unabhängigen Review. Anti-Loop-, Budget-, Rechte- und Freigaberegeln des
  genehmigten Plans sind verbindlich.

## Functional Requirements

- **FR-337:** Jede langlaufende Mutation trägt unveränderliche Projekt-ID,
  Projektwurzel und Epoch bis zum Commit; stale Epochen schreiben nichts.
- **FR-338:** HTTP-2xx, RAM-/Cache-Update und Success-Event entstehen erst nach
  erfolgreichem dauerhaftem Commit; Persistenzfehler bleiben sichtbar und
  retryfähig.
- **FR-339:** Videoanalyse speichert `completed`, `partial` und `failed`
  wahrheitsgetreu; Auswahlwechsel oder Parallelstart verändern keinen falschen
  Clip.
- **FR-340:** Projekterstellung ist atomar; Brain-Connections verwenden
  projektgebundene Leases; voller SSE-Log-Fanout bleibt bounded und
  exceptionfrei.
- **FR-341:** NSwag erzeugt und kompiliert den Client im selben Clean-Build
  unter `obj/`; ignorierte lokale Generatorausgaben sind keine
  Buildvoraussetzung.
- **FR-342:** OpenAPI-generierte C#-Transporttypen decken Einzel-/Multi-Modell-
  Telemetrie und vollständige Analysefelder ohne manuelle DTO-Drift ab.
- **FR-343:** Render-Dedupe blockiert nur aktive identische Jobs; terminale
  Jobs sind retryfähig; Identität enthält Projekt, Timeline, Settings und
  Medien-Contenthashes.
- **FR-344:** Alle Pflichtmodelle und DirectML-Runtimeassets besitzen Quelle,
  Lizenz, Version und SHA-256; Installation erfolgt allowlisted, geprüft und
  atomar.
- **FR-345:** Python-3.11-Windows-Graph, NuGet-Graph und .NET-9-SDK sind
  gelockt; Release enthält SBOM, Lock-, Binär- und Artefakthashes.
- **FR-346:** Irreversible/bulk Löschungen benötigen sichtbare Bestätigung mit
  Ziel und Umfang; Abbruch erzeugt keinen API-Aufruf.
- **FR-347:** UI zeigt ausschließlich kanonische FFmpeg-AMF-Runtime; Settings
  Load/Save meldet Erfolg nur nach atomarem Write.
- **FR-348:** Preview-, Chat-, GPU- und Empfehlungsergebnisse sind request-/
  generation-/projektgebunden; unbekannte Dispatcherfehler führen zu Crashlog
  und kontrolliertem Shutdown.
- **FR-349:** Primäre/destruktive UI-Aktionen sind benannt, keyboarderreichbar
  und bei 1280×720, 1400×900 sowie 100/150/200 % DPI sichtbar;
  CachedTab-Reapply bewahrt genau einen Parent.
- **FR-350:** Native C#-Tests prüfen DTOs, Services, ViewModels, Cancellation
  und Controls; Python-Coverage und Skips besitzen Baseline, Owner und Ablauf;
  Tests hinterlassen keine neuen Scratch-Reste.
- **FR-351:** PR-/Branch-CI führt Restore, Build, Tests, Secret-/Dependency-/
  SCA-Gates aus; Release stammt ausschließlich aus geschütztem `main` mit
  Required Checks.
- **FR-352:** Autoritative Dokumentation beschreibt DirectML-/CLAP-/AMF-
  Realität widerspruchsfrei; alle Pflichtlinks und DoD-Pfade existieren.

## Recovery Requirement

- **RR-237:** Jede RenderQueue-Schemaänderung benötigt gehashtes Backup,
  Kopie-Rehearsal, Integritätsprüfung und erfolgreichen Restore-Probe vor
  Migration realer Daten.

## Test Requirements

- **TR-346:** SDD-Validator lehnt Spec-Übergröße, nichtkanonische Taskbox,
  fehlende ID, offene Checklist, falschen Archivhash, vorzeitigen Marker und
  falschen QC-Digest ab.
- **TR-347:** Fault-Injection beweist Rollback und sichtbaren Fehler für
  Projektwechsel, Persistenz, Settings, QueueFull und Render-Retry.
- **TR-348:** Frischer externer Windows-Checkout besteht locked Restore und
  Release-Build ohne vorhandene `Generated/`, Modelle, Caches oder lokale
  SDK-Zufälle.
- **TR-349:** Python-Gesamtsuite und native C#-Tests bestehen; WPF Release baut
  mit 0 Fehlern und 0 Warnungen.
- **TR-350:** Alle 14 Views bestehen GUI-, Fehlerzustands-, Auflösungs-, DPI-,
  Keyboard-, Fokus-, UIA- und High-Contrast-QC.
- **TR-351:** Aktive Audio-, Video-, Pacing-, Timeline- und Brain-Operationen
  überstehen A→B-Projektwechsel ohne Write in B oder stale UI-Publikation.
- **TR-352:** Fresh-Install-Smoke beweist RAFT, SigLIP, Moondream, CLAP und
  Audio-MDX auf RX 7800 XT/korrektem LUID mit beiden
  DirectML-Speicherflags sowie H.264/HEVC-AMF.
- **TR-353:** Secret Scan, Python-/NuGet-SCA, Dependency Review, SBOM,
  Provenienz- und Artefakthashprüfung bestehen für denselben Commit.
- **TR-354:** PR, Required Checks, Review, Merge, Tag und Releaseartefakt
  verweisen auf denselben geschützten Main-SHA.

## Success Criteria

- **SC-076 [OBJ-72]:** Gate A bestätigt gültiges Archiv, aktive Spec ≤10.240
  Bytes, eindeutige IDs, 46 kanonische Tasks und abgeschlossene Checklist.
- **SC-077 [OBJ-72]:** Alle A→B-, Fault- und Paralleltests melden null
  projektübergreifende Writes, null RAM-Geisterzustände und null falsche
  Erfolge.
- **SC-078 [OBJ-72]:** Externer Clean-Checkout besteht locked Restore, NSwag,
  native Tests und WPF Release ohne lokale Hilfsdateien.
- **SC-079 [OBJ-72]:** GUI zeigt Lösch-, Settings-, Partial-, Failure- und
  Fatalzustände korrekt und besteht Accessibility-/DPI-Matrix.
- **SC-080 [OBJ-72]:** Security-, SCA-, Secret-, SBOM-, Provenienz- und
  Hash-Gates sind vollständig PASS; keine unbegründete Ausnahme bleibt offen.
- **SC-081 [OBJ-72]:** Fresh Install startet alle Pflicht-DirectML-/AMF-Pfade
  auf freigegebener AMD-Hardware ohne verbotenen Fallback.
- **SC-082 [OBJ-72]:** T370–T415 sind `[X]`; QC-Evidenz und Marker-Digests
  stimmen; Release-SHA stammt aus geschütztem `main`.

## Traceability

| Tasks | Requirements |
|---|---|
| T370–T373 | OR-335–OR-337, TR-346, SC-076 |
| T374–T383 | FR-337–FR-340, TR-347, TR-351, SC-077 |
| T384–T390 | FR-341–FR-345, RR-237, TR-348 |
| T391–T397 | FR-346–FR-349, TR-350 |
| T398–T403 | FR-350–FR-352, TR-346, TR-353 |
| T404–T413 | TR-347–TR-353, SC-077–SC-081 |
| T414–T415 | TR-354, SC-082 |
