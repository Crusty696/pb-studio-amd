# Spezifikation: OBJ-74 Tiefenaudit, Analyse-Resume und Pacing-Wahrheit

**Status:** ACTIVE / SPECIFIED
**Feature-Workspace:** `specs/00019-deep-app-audit-resume-pacing`

## Problem

PB Studio besitzt 14 WPF-Bereiche, 60+ API-Operationen und mehrere teure
Audio-/Video-Analysestufen. Der aktuelle Zustand beweist weder jeden
Nutzerpfad neu noch eine verlustfreie Wiederaufnahme nach Abbruch. Gezielte
Teilanalysen können bestehende Ergebnisse überschreiben; laufende Analysen
besitzen keine dauerhaften Stage-Checkpoints. Pacing kann unvollständig
analysierte Clips konsumieren, ohne die für aktive Matching-Modi fehlenden
Daten sichtbar zu machen.

## Scope

### Enthalten

- vollständiger Funktionskatalog aller 14 WPF-Tabs, REST-/SSE-Pfade und Core-Stufen
- frische statische, automatisierte, API-, GUI- und echte Medienprüfung
- Audio-/Video-Analysezustände `unavailable`, `running`, `interrupted`,
  `partial`, `failed`, `completed` pro Stage und Clip
- verlustfreie Wiederaufnahme nur fehlender/ungültiger Stages und Chunks
- explizite Force-Neuanalyse als einzige bewusste Vollwiederholung
- Pacing-Preflight, Clip-Eignung, Auswahlqualität, Diversität, Semantik,
  Motion, Struktur, Key, Brain, Anchors und Triggerdaten
- DB-/Cache-/FAISS-/SSE-/WPF-Vertragsparität und Abbruch-/Restart-Verhalten
- vollständige Prüfung und nachvollziehbare Integration aller vorhandenen
  lokalen und Remote-Branches ohne Rücknahme neuerer Main-Fixes oder fremder
  Arbeitsdateien; `claude/*` bleibt eine separat belegte Teilmenge
- Regressionstests, reale Testdaten und belegte Auditberichte

### Ausgeschlossen

- Datenbankmigration oder neue Dependency ohne separate Freigabe
- CPU-, CUDA-, ROCm-, NVENC- oder Software-Encoder-Fallback
- Löschen bestehender Nutzerprojekte, Medien oder Analyseergebnisse
- ungefragte Änderungen an `src/pb_studio/audio/separator.py`
- Produktionsdeployment oder Releasefreigabe vor QC

## Objective

**OBJ-74:** Jede Appfunktion muss inventarisiert und frisch geprüft sein.
Unterbrochene oder partielle Analysen müssen nach Neustart exakt erkennen,
welche Arbeit gültig vorhanden ist, ausschließlich fehlende Arbeit fortsetzen
und vorhandene Resultate bewahren. Pacing darf Auswahlentscheidungen nur aus
nachweislich verfügbaren Daten treffen und muss fehlende Voraussetzungen
sichtbar melden.

## Functional Requirements

- **FR-354:** Funktionskatalog bildet jeden UI-Command auf API, Core,
  Persistenz, SSE und sichtbares Ergebnis ab.
- **FR-355:** Audio- und Video-Stages besitzen kanonische IDs, Status,
  Eingabe-/Konfigurations-Fingerprint, Artefaktvalidität, Fehler und Zeitstempel.
- **FR-356:** Analyseplanung berechnet `requested - valid_completed`; bestehende
  gültige Stage-Ergebnisse werden standardmäßig nicht neu berechnet.
- **FR-357:** Teilretry merged nur neu erzeugte Felder; deaktivierte oder nicht
  angeforderte Stages dürfen bestehende Daten und Status nicht überschreiben.
- **FR-358:** Abbruch, Backend-Neustart und Projektwechsel persistieren einen
  ehrlichen terminalen Zustand; spätere Wiederaufnahme beginnt am ersten
  fehlenden oder ungültigen Checkpoint.
- **FR-359:** Long-Mix-Verarbeitung checkpointet abgeschlossene Chunks so, dass
  ein Retry keine bereits belegten Chunks neu analysiert.
- **FR-360:** WPF zeigt Clip- und Stage-Zustand, fehlende Arbeit, Retry-Ergebnis
  und Fehler; Batchläufe setzen nach Einzelfehlern mit den übrigen Clips fort.
- **FR-361:** API-/WPF-DTOs transportieren Analyse-, Stage- und Fehlerzustände
  ohne handgeschriebene Drift.
- **FR-362:** Pacing leitet je aktivem Modus benötigte Audio-/Video-Stages ab,
  blockiert oder exkludiert ungeeignete Clips sichtbar und nutzt keine stillen
  Null-/Defaultwerte als echte Analyse.
- **FR-363:** ClipSelector bewahrt Projektgrenzen, Content-Identität,
  Wiederholungsgrenzen, adaptive Diversität und deterministische
  Score-Provenienz über Basis-, Motion-, Semantic-, Brain-, Key- und
  Anchor-Pfade.
- **FR-364:** Pacing-Response und UI nennen verwendete, ausgeschlossene und
  wegen fehlender Analyse abgelehnte Clips samt Gründen.
- **FR-365:** Persistenz bleibt DB-first; RAM, FAISS, Brain-Cache und SSE
  publizieren Erfolg erst nach dauerhaftem Commit.
- **FR-366:** Jeder vorhandene `claude/*`-Branch wird gegen den aktuellen Main
  semantisch klassifiziert. Noch gültige Änderungen werden modern portiert;
  vollständig enthaltene oder überholte Änderungen werden mit Evidenz als
  verarbeitet markiert, ohne veraltete Trees in den Produktcode zu übernehmen.
- **FR-367:** Jeder übrige lokale und Remote-Branch wird commit- und
  funktionsbezogen gegen den aktuellen Main klassifiziert. Gültige Änderungen
  werden modern portiert; doppelte oder überholte Trees werden nicht
  eingespielt, ihre Historie wird vor einer optionalen Ref-Bereinigung
  nachvollziehbar als verarbeitet erfasst.

## Operational Requirements

- **OR-338:** Alle Writes bleiben innerhalb Workspace/Brain-PB-Studio und
  folgen den AMD-/DirectML-/AMF-Iron-Rules.
- **OR-339:** Parallele Agenten arbeiten nur in disjunkten Read-only- oder
  explizit zugewiesenen Code-Zonen; Shared-Zones bleiben sequenziell.
- **OR-340:** Keine bestehende Analyse oder Testdatei wird für QC gelöscht;
  Testartefakte werden über vorab erfasste IDs/Pfade isoliert und bereinigt.
- **OR-341:** Jeder CRITICAL/HIGH-Befund besitzt Reproduktion, file:line-Beleg,
  Impact und quellenbelegte Reparaturempfehlung.
- **OR-342:** Branch-Ref-Löschungen erfolgen ausschließlich nach vollständiger
  Ancestry-/Patch-Evidenz und einer unmittelbar davor wiederholten expliziten
  Bestätigung; Produktdateien, Nutzerdaten und geschützte Historie werden nicht
  gelöscht.

## Test Requirements

- **TR-356:** Aktuelle Python-Gesamtsuite, native C#-Tests und WPF Release-Build
  bestehen auf Python 3.11/NumPy 1.26.4 mit `PYTHONPATH=src`.
- **TR-357:** Fault-Injection unterbricht Audio und Video nach jeder Stage;
  Restart/Retry berechnet nur fehlende Stages und bewahrt Byte-/Wertgleichheit
  aller zuvor abgeschlossenen Ergebnisse.
- **TR-358:** Gezielte Audio-/Video-Teilrequests beweisen merge-only Semantik;
  abgeschaltete Stages löschen keine Beats, Szenen, Motion, Embeddings, Farben,
  Tags, Struktur oder Trigger.
- **TR-359:** Long-Mix-Test beweist Chunk-Resume und keine doppelte Arbeit an
  bereits committed Chunks.
- **TR-360:** Pacing-Preflight wird mit vollständig, partiell und nicht
  analysierten Clips für jede Moduskombination geprüft.
- **TR-361:** Clip-Auswahl wird mit festen Kandidaten auf Score-Reihenfolge,
  Diversität, Wiederholungsgrenze, Semantic-/Motion-/Brain-/Key-/Anchor-Effekt
  und deterministische Provenienz geprüft.
- **TR-362:** Echte Dateien aus `C:\Users\david\Videos\test_data\audio` und
  `C:\Users\david\Videos\test_data\video` durchlaufen API und GUI; keine
  Mock-Medien ersetzen diese Abnahme.
- **TR-363:** Backend-Kill, SSE-Reconnect und App-Neustart zeigen
  `interrupted`, erhalten Fortschritt und bieten gezielte Fortsetzung.
- **TR-364:** Alle 14 Tabs bestehen Click-/Status-/Fehler-/Keyboard-/UIA-Smoke;
  Pacing und Analyse werden zusätzlich semantisch geprüft.
- **TR-365:** Branch-Integration belegt Ref, Merge-Base, Ahead/Behind,
  Commitentscheidung, Diff-Prüfung und Tests der selektiv portierten Änderungen.
- **TR-366:** Nach Konvergenz sind alle verarbeiteten Branch-Tips Ancestors des
  Integrationsstands, dessen Tree gegenüber dem beabsichtigten aktuellen Main
  nur die dokumentierten selektiven Ports und Evidence-Änderungen enthält.

## Success Criteria

- **SC-084 [OBJ-74]:** 100 % der katalogisierten Funktionen besitzen PASS,
  FAIL oder begründetes BLOCKED mit Evidenz; keine Funktion bleibt unbewertet.
- **SC-085 [OBJ-74]:** Kein Teilretry verändert nicht angeforderte gültige
  Resultate; alle Fault-Injection-Resume-Tests bestehen.
- **SC-086 [OBJ-74]:** Nach Unterbruch zeigt die App exakt fehlende Stages und
  setzt diese nach Nutzeraktion ohne Vollneuanalyse fort.
- **SC-087 [OBJ-74]:** Pacing verwendet nur für den aktiven Modus geeignete
  Clips und liefert nachvollziehbare Auswahl-/Ausschluss-Provenienz.
- **SC-088 [OBJ-74]:** Gesamt-, Native-, Build-, API-, GUI-, echte Medien- und
  Persistenz-QC bestehen; Auditbericht enthält vollständige Zahlen.
- **SC-089 [OBJ-74]:** `.completed` und `.qc-passed` entstehen erst nach
  vollständiger Task- und QC-Evidenz.
- **SC-090 [OBJ-74]:** Alle Claude-Branch-Tips sind entweder bereits exakte
  Main-Ancestors oder im Integrations-Branch als geprüfte Merge-Eltern erfasst;
  kein gültiger Hunk bleibt unbehandelt und kein Konfliktartefakt gelangt in Main.
- **SC-091 [OBJ-74]:** Alle übrigen lokalen und Remote-Branch-Tips sind entweder
  bereits Main-Ancestors oder als geprüfte Merge-Eltern erfasst. Doppelte oder
  überholte Branch-Refs können danach ohne Verlust aktueller Produktfunktion
  gezielt bereinigt werden.

## Traceability

| Requirements | Abdeckung |
|---|---|
| FR-354, OR-341, SC-084 | Inventar, Audit, Bericht |
| FR-355–FR-361, FR-365 | Analyse-Resume, Persistenz, UI/API |
| FR-362–FR-364 | Pacing-Preflight und Clip-Auswahl |
| TR-356–TR-364 | automatisierte, Live- und GUI-QC |
| FR-366, TR-365, SC-090 | Claude-Branch-Audit und verlustfreie Integration |
| FR-367, OR-342, TR-366, SC-091 | vollständige Branch-Konvergenz und kontrollierte Ref-Bereinigung |
| SC-085–SC-089 | Abschluss- und Release-Gates |

## Task Range

T001–T035 implementieren und prüfen OBJ-74.
