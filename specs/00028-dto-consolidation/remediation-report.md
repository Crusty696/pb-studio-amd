# Spec00028: Struktur- und Statuskorrektur 2026-11-08

## Anlass und Ursache

Der aktuelle Validator `scripts/validate_sdd.py --feature specs/00028-dto-consolidation --phase qc --json` meldete 14 Befunde. Historische Artefakte entsprachen nicht seinem kanonischen Format. Zusätzlich widersprachen die Erledigungsmarker dem fehlenden Live-Abnahmebeleg. Die Korrektur behebt Dokumentstruktur und Status, nicht 14 nachgewiesene Produktfehler.

## Exakte Befunde und Korrektur

| Nr. | Vorher-Code | Quelle | Korrektur |
|---|---|---|---|
| 1 | OBJECTIVE_COUNT | spec.md | Genau ein explizites OBJ-1 ergänzt. |
| 2 | TASK_RANGE_MISSING | spec.md | Aktiver Bereich T001–T008 angegeben. |
| 3 | TASK_FORMAT | tasks.md Zeile 5, T001 | Neue kanonische Revalidierungsaufgabe. |
| 4 | TASK_FORMAT | tasks.md Zeile 6, T002 | Neue kanonische Revalidierungsaufgabe. |
| 5 | TASK_FORMAT | tasks.md Zeile 7, T003 | Neue kanonische Revalidierungsaufgabe. |
| 6 | TASK_FORMAT | tasks.md Zeile 8, T004 | Neue kanonische Revalidierungsaufgabe. |
| 7 | TASK_FORMAT | tasks.md Zeile 9, T005 | Neue kanonische Revalidierungsaufgabe. |
| 8 | TASK_FORMAT | tasks.md Zeile 10, T006 | Neue offene echte Live-Abnahmeaufgabe. |
| 9 | TASK_FORMAT | tasks.md Zeile 11, T007 | Neue kanonische Revalidierungsaufgabe. |
| 10 | TASK_FORMAT | tasks.md Zeile 12, T008 | Neue offene Vollständigkeits-/Markergateaufgabe. |
| 11 | CHECKLIST_MISSING | checklists/ | Nur tatsächlich ausgeführte Dokumentmigrationsprüfungen erfasst. |
| 12 | COMPLETED_JSON | .completed | Unverändert historisch archiviert, aktiver unbelegter Abschluss zurückgenommen. |
| 13 | QC_JSON | .qc-passed | Unverändert historisch archiviert, kein neuer PASS-Marker. |
| 14 | QC_STATUS_ORDER | qc-report.md | Aktuelles Authoritative OBJ-1 Gate: REOPENED / NOT RELEASE-READY. |

Anforderungsdefinitionen wurden ohne Bedeutungsänderung im erforderlichen Fettdruck formatiert; Tasks haben Objective, getrennte `{(FR-001)}`-Referenzen und Backtick-Dateipfade. Der Validator blieb unverändert. Neue JSON-PASS-Marker wären ohne vollständige commit-/hashgebundene Receipts unzulässig.

## Historie und aktive Aufgaben

Originale Spec/Plan/Tasks/QC/Marker und alle vorhandenen Evidence-Markdowndateien sind bytegleich in `evidence/legacy-2026-11-08/` erhalten; `manifest.json` nennt SHA-256. Zusätzliche vollständige Vorhersicherung liegt im Chat-Arbeitsordner `work/pb-sdd-before`. Die alte Liste wurde nicht rückwärts von [X] nach [ ] verändert. Eine ausdrücklich neue Revalidierungsliste ersetzt sie operativ. Die IDs sind versionsgebunden; das historische Original bleibt eindeutig verlinkt.

Alle acht neuen Aufgaben bleiben offen. Vorhandene Implementierung, Tests und Dokumente sollen zuerst verwertet werden; das ist keine Aufforderung, unveränderte Volltests oder die gesamte Implementierung blind zu wiederholen. Historische Belege tragen eine klare Einordnung.

## Echte offene Nachweise

- T001/T002: Vollständigkeit des konkreten Inventars, Entscheidungen und vorgeschaltetes Gate müssen belegt zugeordnet werden; vorhandene Dokumente allein schließen das nicht.
- T003/T005: Vorhandene Tests und Review sind historische Teilbelege; ihre vollständige Abdeckung aller geforderten Vertragscluster und Grenzfälle ist nicht nachgewiesen.
- T004: Snapshotdriftfreiheit beweist keine vollständige DTO-Migration. `PBStudio.UI/Models/ModelListResponse.cs` bleibt ein manueller REST-Transporttyp, aktiv genutzt in `PBStudio.UI/Services/ApiClient.Models.cs`. Eine konkrete zulässige Ausnahme bzw. vollständige Migration ist in den geprüften Spec00028-Belegen nicht belegt. Daraus allein folgt kein nachgewiesener Laufzeitfehler.
- T006: `evidence/live.md` fehlt. Allgemeine WPF-Smoke-Berichte belegen nicht automatisch die geforderten DTO-Vertragscluster-Hauptflows.
- T007: Historische Test-/Buildzahlen ersetzen keine Zuordnung zu finalem Umfang und Stand. Keine neue Vollsuite oder GUI-Ausführung in dieser Dokumentreparatur.
- T008: Vollständigkeits-/QC-Gate bleibt offen; keine Completion-/QC-PASS-Marker erzeugt.

## Prüfgrenzen

Vorher: aktueller Validator reproduziert exakt die oben genannten 14 Befunde. Nachher: `--phase open` besteht ohne Befund; `--phase qc` scheitert mit fehlendem Markergate und acht offenen Aufgaben. Letzteres ist die beabsichtigte Sperre gegen falsche Freigabe. Beide Ergebnisse hat der Parent frisch geprüft und in `outputs/PB_SDD_PRUEFUNG.json` im Bereinigungs-Chat protokolliert. Kein Produktcode, Provider, Sicherheitsvertrag, Deployment, Build oder Live-Abnahme verändert/ausgeführt.
