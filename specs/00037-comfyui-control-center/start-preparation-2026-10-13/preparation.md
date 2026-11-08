# Startvorbereitung: PB-Studio / ComfyUI

Stand 2026-10-13. [ABSICHT] Erster Entwicklungsumfang ist Welle A in [phase-manifests.md](../phase-manifests.md). [BEOBACHTUNG] Aktuelle Quellen-/Statusbelege in [current-state.json](current-state.json). Nichts implementiert.

## Aktueller Stand

PB HEAD e51e798cc05cd6ec4f42a9e69ee3e9284dc5bcdb, Branch codex/full-audit-remediation. 254 inventarisierte Quellen, zusätzliche Kommunikationsquellen und neun normative Dokumente frisch gegen Reviewhashes geprüft; siehe JSON für genaue Ergebnisse. Keine Abweichung in diesen Inventaren; kein umfassender Hashnachweis aller Modelle/Custom Nodes oder ignorierten Dateien.

Arbeitsbaum enthält fünf bereits bestehende Änderungen: .claude/settings.local.json (lokale Einstellung, nicht inhaltlich ausgewertet), CHANGELOG.md/CLAUDE.md (Spec00036-Berichte), SSEClient.cs (Ereignisdiagnose), TerminalLoggerProvider.cs (Redaktion). Untracked: Recorder/Tests/Manual-Abnahme Spec00036, Reviewdokumente und Spec00037. Keine dieser Änderungen wird verworfen, mitimplementiert oder pauschal committed. Arbeitsbasis ist HEAD plus vorhandene Änderungen, nicht HEAD allein.

ComfyUI-Quell-HEAD 3c1b7a17fdf239d35ce98cc777756f572d089795, Gitstatus ohne Ausgabe. HTTP localhost8188 meldete Version0.39.2, Python3.13.12, torch2.12.0+rocm7.14.0 und RX7800XT. Queue meldete einen laufenden Auftrag und keine wartenden; Eigentümer/Zweck unbekannt. Keine Eingriffe. PB /health auf127.0.0.1:8765 verweigerte Verbindung; andere Instanzen/Ports daraus nicht ausgeschlossen.

RUNTIME_DIRTY im vorhandenen produktiven Recoveryverzeichnis existiert weiterhin. Ursache/Konsistenz heute nicht untersucht; vor späterem produktivem PBstart readonly Recovery-Preflight erforderlich, Marker niemals blind entfernen. Blockiert isolierte Vertragscodearbeit nicht. Brainpfad _wiki/decisions fehlt; bestehende aktuelle Learnings und bestätigte clarifications wurden herangezogen. Kein Ersatzentscheid erfunden.

## Reihenfolge

1. T001 vorbereiten, Welle-A-Scope und aktuelle Arbeitsbasis binden; explizite Freigabe abwarten.
2. Nach Freigabe T003 (lesende Verbindung) → T004 (Capabilities), T045-Nachweise passend zu dieser Welle.
3. Parallel T002-Referenzinventar/Autorisierung/Qualitätsziele konkretisieren. Baseline- und GPUausführung brauchen eigenen abgegrenzten Laufauftrag.
4. Danach T005 → T006 → T007; T007 zusätzlich abhängig von T002 und ausdrücklicher Pilotfreigabe.
5. Erst G1 und konkrete weitere Gates öffnen größere Schema-/GPU-/WPF-Integration.

## Medien: jetzt und später

Für Welle A: KEINE Audio-, Video- oder Bilddatei nötig. Ein echter Modellname/Dateipfad ist kein Medienqualitätsbeleg. Keine Quelle ungefragt durchsuchen oder als freigegeben übernehmen.

Für T002 bitte einen konkreten Ordner oder einzelne lokale Dateien benennen und Lesen, Hashen sowie spätere lokale Analyse ausdrücklich erlauben. Originale bleiben unverändert. Historische Projektfreigaben gelten nicht automatisch als Freigabe dieses Benchmarks.

Vorschlag für den ersten kleinen Referenzbestand (keine statistisch ausreichende Pflichtstückzahl): ein typischer eigener Musiktrack mit bekanntem Beat/Abschnittswechsel und kurze reale Videos, die ruhige Szene, schnelle Bewegung und schwierige Lichtbedingungen abdecken. Bildreferenz nur nötig, wenn ein I2V-/Referenzworkflow gewählt wird. Für reines T2V keine Source-Datei nötig; Prompt und erwartetes Motiv genügen als Generierungseingabe. Reale Vergleichsmedien bleiben für den zugesagten Qualitätsnachweis erforderlich.

Zusätzliche unabhängige Quellen für den späteren unangetasteten Holdout reservieren; derselbe Track/Clip in anderer Variante zählt nicht als unabhängige Quelle. Breiter Audio-/Video-/Longformbenchmark erst für die jeweiligen späteren Fähigkeiten. Nicht jetzt sämtliche Familien messen.

Benötigte Angaben je autorisierter Quelle: absoluter Pfad, erlaubte Nutzung, Entwicklungs- oder Holdoutzuordnung, relevantes Qualitätsziel und vorhandene Referenzmarken (z.B. Beat/Abschnitt oder erwarteter Bildinhalt). Technische Eigenschaften und Hashes erheben wir später; der Nutzer muss keine FPS-/VRAMwerte erraten. Fehlende Fachlabels bleiben unknown und werden nicht aus dem zu prüfenden System als Wahrheit übernommen.

## Konkrete Freigaben

A JETZT NÄCHSTE ENTSCHEIDUNG: Umsetzung T003/T004 gemäß phase-manifests.md einschließlich eng begrenzter config_manager-Codeänderung, isolierter Vertragstests und lesender Discovery. Keine Medien-/GPUjobs, Datenmigration oder neue Dependencies enthalten. Status: NICHT FREIGEGEBEN.
B MEDIENAUSWAHL: benannte Quellen mit Nutzungsumfang; erst danach Manifest mit Hash/Labels/Split. Status: KEINE QUELLEN AUTORISIERT.
C SPÄTER PILOT: exakter vorhandener Workflow/APIexport, Modell-/Noderevision, ein festgelegter Testumfang, separate Ausgabewurzel, Zeit-/Speicher-/Abbruchgrenzen; aktive fremde Arbeit respektieren. Vor Ausführung konkrete Werte vorlegen. Status: NICHT FREIGEGEBEN. Keine pauschale Erlaubnis für Downloads oder Serveränderungen.
D SPÄTER MIGRATION/API: konkrete Änderungen samt Kopie-/Recovery-/Kompatibilitätsnachweis; nicht Voraussetzung für lesende Welle A. Status: OFFEN.

Freigaben A/C/D bleiben getrennt, weil der Masterplan §S, T001/T007 und clarifications O04 diese phasenbezogenen Gates verlangt und der Nutzer bisher ausdrücklich keine Implementierung autorisiert hat. D01/D02/O01/O02 müssen nicht erneut entschieden werden.

## Stopkriterien

Quell-/API-Drift, nötige neue Dependency, unerwartete produktive Mutation oder Konflikt mit bestehender Arbeit: betroffenen Schritt stoppen und konkreten Änderungsbedarf vorlegen. Fehlende Medien blockieren Medienläufe, nicht die reine Bridge. Keine erfolgreiche Kommunikation behaupten, bevor tatsächliche Produktadapter und Fehlerfälle geprüft sind.
