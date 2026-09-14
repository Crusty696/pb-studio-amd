# Tasks: Externes Config-Hot-Reload mit letztem gültigen Stand

**Status:** READY FOR GATE REVIEW, nicht implementiert. **Basis:** spec.md, plan.md.

- [X] T001 {TR-001} Aktuellen Code-, Consumer- und Vertragsbestand sowie vorgelagertes OBJ-75-Gate in specs/00025-config-hot-reload/evidence/baseline.md erfassen; vorgeschlagene Entscheidungen gegen reale Dateien bestätigen.
- [X] T002 {FR-001,TR-001} Konkrete Dateiliste und Owner aus plan.md festlegen; offene API-/Architekturentscheidungen vor Umsetzung in specs/00025-config-hot-reload/evidence/design-review.md dokumentieren.
- [X] T003 {FR-001} Reproduktion und Grenzfälle gemäß spec.md in den in plan.md benannten Tests implementieren und erwartetes Vorher-Verhalten belegen.
- [X] T004 {FR-001} Vollständigen Featurevertrag aus sämtlichen FR-/TR-Anforderungen von spec.md in den in plan.md benannten Produktdateien implementieren; jede Anforderung in specs/00025-config-hot-reload/evidence/requirements-matrix.md auf Code und Verifikation abbilden.
- [X] T005 {FR-001,TR-001} Sämtliche Abnahmeszenarien aus spec.md fokussiert prüfen und unabhängiges Code-/Vertragsreview in specs/00025-config-hot-reload/evidence/review.md aufnehmen; Restfehler korrigieren.
- [X] T006 {FR-001} Parent: sichtbare echte Backend-/GUI-Abnahme und Schutzinvarianten aus spec.md in specs/00025-config-hot-reload/evidence/live.md nachweisen; reine Fixtures nicht als Live-PASS zählen.
- [X] T007 {TR-001} Parent: angemessene finale Vollsuite, C#-Tests/Release-Build und Gate-Prüfungen ohne konkurrierende Testläufe in specs/00025-config-hot-reload/evidence/final-checks.md erfassen.
- [X] T008 {FR-001,TR-001} Vollständigkeitsmatrix unabhängig prüfen; erst danach specs/00025-config-hot-reload/.completed, qc-report.md und nach tatsächlicher QC .qc-passed erzeugen; Parent aktualisiert Brain-Log.

