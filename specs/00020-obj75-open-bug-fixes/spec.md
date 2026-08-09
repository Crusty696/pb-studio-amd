# Spezifikation: OBJ-75 belegte Restfehler

**Status:** ACTIVE
**Feature-Workspace:** `specs/00020-obj75-open-bug-fixes`

## Problem

Nach OBJ-74 bleiben belegte Video-, Stem-, Lifecycle-, Projector- und
Recovery-Fehler sowie offene Live-QC.

## Scope

### Enthalten

- dauergebundenes, fehlertolerantes Video-Frame-Sampling
- korrekte Szenen-/Embedding-Dauer bei Edit-List-/Preroll-Medien
- Stem-Erfolg nur nach vollständiger Marker- und Artefaktvalidierung
- ehrliche, korrelierte terminale Analyse-/Stem-SSE-Ereignisse
- zwei getrennte zonierte Audits mit Bericht
- Rest-Highs: projektgebundene Chat-Tools, Projector-Training und Recovery
- Migration erst nach Backup, Restore-Probe und Rollback
- alle globalen/projektlokalen Truth-Sources crash-konsistent sichern
- risikobasierte Test-, Build-, API/SSE-, Medien- und GUI-QC

### Ausgeschlossen

- neue Dependencies oder Produktionsdeployment
- Render-Queue-Retention, persistierter Render-Fortschritt, Config-Hot-Reload und
  Chat-Tokenstream; diese nicht release-blockierenden Themen erhalten ein eigenes
  Feature-Workspace nach OBJ-75

## Objective

**OBJ-75:** Alle belegten Restfehler und drei Rest-Highs werden vor Release
minimal geschlossen; Full-, Live-, Medien- und GUI-QC müssen konvergieren.

## Functional Requirements

- **FR-368:** Video-Sampling begrenzt adressierbare Frames anhand der
  persistierten ffprobe-Dauer und verwendet diese Dauer für Ergebnis-Metadaten.
- **FR-369:** Ein einzelner nicht lesbarer Sample-Frame darf vorhandene valide
  Samples nicht verwerfen; echte Inferenzfehler bleiben harte Stage-Fehler.
- **FR-370:** Szenen- und Frame-Helfer dürfen Container-Preroll nicht als
  sichtbare zusätzliche Laufzeit publizieren.
- **FR-371:** Stem-Pfade werden nur nach erfolgreicher vollständiger
  Marker-/Artefaktvalidierung beantwortet und persistiert.
- **FR-372:** Analyse- und Stem-SSE tragen Clip-/Task-Korrelation und einen
  ehrlichen terminalen Status; späte Worker-Events überschreiben keinen
  Abbruchstatus.
- **FR-373:** Per-Stem-Resume nutzt source-/modellgebundene Checkpoints und nur
  validierte Ausgaben; unsichere Orphan-Adoption bleibt verboten.
- **FR-374:** `onset_sensitivity` und `max_cut_interval` beeinflussen die
  Pacing-Berechnung entsprechend ihrem bestehenden UI-/API-Vertrag.
- **FR-375:** Mood-Tags werden vor Brain-Matching sprach- und
  synonymübergreifend kanonisiert.
- **FR-376:** Der Pacing-Fehlerfallback ist unabhängig vom zuvor gescheiterten
  Generator und liefert ein einfaches gültiges Zeitraster.
- **FR-377:** Ein Stem-Timeout darf nicht gleichzeitig Fehler melden und später
  unkontrolliert Erfolgsfortschritt publizieren; der Hintergrundabschluss wird
  eindeutig behandelt.
- **FR-378:** Audio-Long-Mix bewahrt getrennte Quellen für Energy, Chroma und
  Stem-Synthese und verarbeitet lange Stem-Dateien speicherbegrenzt.
- **FR-379:** Video erzwingt ehrliche Scene-/Embedding-/Farb- und Kaltstart-
  Ergebnisse; `force` umgeht valide Reuse-Pfade wirklich.
- **FR-380:** Pacing-Gates, Semantic-Ranking, UI-Anker und Snap-Invarianten
  beeinflussen die Auswahl entsprechend ihrem sichtbaren Vertrag.
- **FR-381:** Render-Cancel bleibt pollbar; Video-only braucht keine Audioquelle.
- **FR-382:** Projekt-, Brain- und Chat-Lebenszyklen bleiben bei Wechsel,
  Retry, Recovery und Backup an dieselbe Projektidentität gebunden.
- **FR-383:** GPU-Cleanup nutzt existierende Manager-APIs; Session-Eviction
  meldet erst nach Freigabe aller produktiven Owner Erfolg.
- **FR-384:** Timeline, Terminal und WPF-Lifecycle verlieren weder pending
  Writes noch Selection, Replay-Wahrheit oder gebundene Speicherlimits.
- **FR-385:** Settings-Werte besitzen eindeutige Priorität und gemeinsame
  Reader; sichtbare Overrides und Modi melden ihre echte Wirkung.
- **FR-386:** Brain-Feedback ist request-idempotent; fehlende Features werden
  nicht als beobachtete Evidenz gelernt; Projector-Training gewichtet Events
  unabhängig vom Batch-Zeitpunkt.
- **FR-387:** Chat-Turn und Loopback-Toolrequests bleiben bis zum letzten Commit
  an dieselbe Projekt-ID, Epoch und Root-Identität gebunden. Nach SSE-Start werden
  Kontextfehler als typisiertes Stream-Ereignis publiziert.
- **FR-388:** Projector-Feedback besitzt dauerhafte Projekt-/Event-UUIDs.
  Copy-on-write veröffentlicht Modell, Checkpoint und Pending-Events gemeinsam;
  V1→V2-Rebuild verlangt das vollständige Projekt-/Embedding-Inventar.
- **FR-389:** Backup und Restore bilden logisch eine Generation. Nach einem Crash
  konvergiert Startup-Recovery per Roll-forward oder Rollback vor Produktöffnung.
- **FR-390:** Vor Recovery-Implementierung registriert eine versionierte Matrix
  je Truth-Source Owner, Pfad, Konsistenzgruppe, Klasse, Quiesce und Restore.
- **FR-391:** Baseline bindet HEAD, Porcelain-/Diff-Digest und Artefakt-SHA-256;
  spätere Änderungen werden gesondert nachauditiert.

## Operational Requirements

- **OR-343:** Änderungen bleiben minimal, DirectML-/AMF-konform und ohne neue
  Pakete; nur die gesicherte, rollbackfähige OR-348-Migration ändert Schemas.
- **OR-344:** Die Nutzerfreigabe vom 2026-08-09 erlaubt lokale Tests, Builds,
  API/SSE-, Medien-, GUI-, CI- und Auditläufe.
- **OR-345:** Bestehende OBJ-74-Artefakte und fremde Arbeitsdateien bleiben
  unverändert.
- **OR-346:** Durchgang 1 und Durchgang 2 werden getrennt inventarisiert.
  Durchgang 2 startet erst nach Fix- und Verifikationskonvergenz von Runde 1.
- **OR-347:** CRITICAL/HIGH-Reparaturen besitzen Reproduktion und Primärquelle
  oder empirischen Projektnachweis.
- **OR-348:** Nutzer hat am 2026-08-09 Migrationen und vollständige QC freigegeben.
  Backup, Restore-Dry-Run und Rollback-Punkt bleiben vor jeder Migration Pflicht.
- **OR-349:** Recovery garantiert Prozesscrash-Konsistenz und strebt Power-loss-
  Konsistenz über Staging, Flush/Fsync, Pointer und dauerhaftes Journal an.
- **OR-350:** Snapshot-Koordination quiesziert Writes über Projekt-, Brain-, Cache-
  und DB-Owner-Grenzen; offene Handles werden nicht umgangen.
- **OR-351:** Nicht release-blockierende P1-Themen werden nicht vor OBJ-75-QC
  implementiert und erhalten ein separates Feature-Workspace.
- **OR-352:** Recovery-Control liegt außerhalb zu restaurierender Config-/Datenpfade
  und läuft vor deren Öffnung.
- **OR-353:** Eigene mutable Daten werden gesichert; externe Medien werden per
  Pfad/Hash geprüft und bei Abweichung ehrlich als nicht verfügbar markiert.
- **OR-354:** Der P1-Aufschub ist eine reversible technische Scope-Entscheidung,
  keine bestätigte Nutzerpriorisierung.

## Test Requirements

- **TR-367:** Nach Freigabe beweist ein fokussierter Video-Vertrag 20,0 s,
  adressierbare Samples und erfolgreichen Embedding-Retry bei Preroll-Medien.
- **TR-368:** Nach Freigabe beweisen Stem-Verträge Marker-Härte sowie terminale
  und korrelierte SSE-Ereignisse bei Erfolg, Fehler und Abbruch.
- **TR-369:** Nach einer breiten Python-Suite genügt für einen einzelnen
  erklärten Last-Harness-Ausreißer Root-Cause-Korrektur, vollständiger
  Fokusvertrag und zehn grüne Stressläufe. C#, WPF Release und SDD bleiben Pflicht.
- **TR-370:** Nach Freigabe beweisen fokussierte Pacing-/Brain-Verträge die
  Reglerwirkung, Tag-Kanonisierung und den unabhängigen Fallback.
- **TR-371:** Runde 1 besteht Zonenregressionen, breite Python-Bestandsaufnahme,
  C#, WPF Release und IRON-Scan; Last-Harness-Ausreißer schließen gemäß TR-369.
- **TR-372:** Runde 2 wiederholt den vollständigen zonierten Audit auf dem
  reparierten Stand und prüft jeden neuen oder wiederkehrenden Befund.
- **TR-373:** Chat-Race-Tests beweisen A→Tool→B, Client-Disconnect,
  Confirmation-Wait und Commit-Guard ohne Mutation oder History-Leak nach B.
- **TR-374:** Projector-Tests beweisen eindeutige Eventwirkung bei A/B/A,
  ID-Wiederverwendung, Parallel-Readern, fehlenden Embeddings, Save-Fehler,
  Prozessneustart sowie V1-Rebuild und Rollback.
- **TR-375:** Fault-Injection unterbricht jede Snapshot-/Restore-Stufe. Neustart
  konvergiert vor Produktöffnung; alle Wahrheitsquellen bleiben verwendbar.
- **TR-376:** Post-Audit-Video/UI-Änderungen erhalten Diff-Review, Regressionen
  und Live-Smoke; alte PASS-Aussagen gelten dafür nicht.
- **TR-377:** Testzahl wird neu gesammelt; GUI-QC verwendet die benannte
  14-Hauptview-Matrix aus `MainWindow.xaml`.

## Success Criteria

- **SC-092 [OBJ-75]:** Das 20-s-Preroll-Medium erzeugt keine 22,4-s-Metadaten
  und keinen Frame-Read-Fehler bei Index 671 mehr.
- **SC-093 [OBJ-75]:** Kein ungültiger oder unvollständig markierter Stem-Lauf
  wird als erfolgreich persistiert.
- **SC-094 [OBJ-75]:** Terminale Analyse-/Stem-Ereignisse sind clipbezogen und
  können nicht durch späten Fortschritt zurück auf `running` gesetzt werden.
- **SC-095 [OBJ-75]:** Marker entstehen nur nach digestgebundener QC. Ein nicht
  wiederholter Langlauf ist ausschließlich mit dem TR-369-Beleg akzeptiert.
- **SC-096 [OBJ-75]:** Jeder sichtbare Pacing-Regler wirkt, Mood-Synonyme werden
  konsistent bewertet und ein Generatorfehler kann nicht denselben Generator
  als Fallback erneut aufrufen.
- **SC-097 [OBJ-75]:** Beide Auditdurchgänge besitzen getrennte Evidence,
  Zahlen, Findings und Verifikationsreceipts; kein Bereich bleibt unbewertet.
- **SC-098 [OBJ-75]:** Der neue Bericht
  `FULLSTACK_DOUBLE_AUDIT_PB_STUDIO_2026-08-09.md` nennt behobene, akzeptierte
  und offene Risiken ehrlich und quellenbelegt.
- **SC-099 [OBJ-75]:** Kein Chat-Tool kann nach Projektwechsel gegen das neue
  Projekt dispatchen oder committen.
- **SC-100 [OBJ-75]:** Jede Projector-Event-UUID beeinflusst den veröffentlichten
  Modellzustand höchstens einmal; ein fehlgeschlagener Publish beeinflusst ihn nie.
- **SC-101 [OBJ-75]:** Nach Crash startet PB Studio mit einer hash-, schema- und
  generationskonsistenten Wahrheit am letzten bestätigten Stand.
- **SC-102 [OBJ-75]:** Jedes Receipt ist baselinegebunden; jede Truth-Source hat
  eine explizite Restore-Entscheidung.

## Task Range

T001–T051 implementieren und prüfen OBJ-75.
