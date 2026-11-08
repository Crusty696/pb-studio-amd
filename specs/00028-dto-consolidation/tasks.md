# Tasks: DTO-Konsolidierung – Revalidierung 2026-11-08

**Status:** OPEN / NOT RELEASE-READY. Neue aktive Aufgabenliste zur Prüfung der vollständigen Abnahme, keine Behauptung fehlender historischer Implementierung.

Die bisherige Liste ist unverändert in `evidence/legacy-2026-11-08/tasks.md` erhalten. Ihre historischen [X] wurden nicht rückwärts geändert. Die folgenden Aufgaben sind neue Revalidierungsaufträge; gleichlautende IDs gelten nur innerhalb dieser aktiven Version. Historische Tests werden als datierte Belege verwertet, nicht als aktuelle Gesamtabnahme ausgegeben.

- [ ] T001 [OBJ-1] {(TR-001)} Vorhandenen Implementierungsstand und vorgelagertes OBJ-75-Gate mit `specs/00028-dto-consolidation/evidence/baseline.md` abgleichen und offene Grenzen dokumentieren.
- [ ] T002 [OBJ-1] {(FR-001)} {(TR-001)} Konkrete Endpoint-/DTO-/Consumer-Matrix und Entscheidungen anhand `specs/00028-dto-consolidation/evidence/design-review.md` auf Vollständigkeit prüfen.
- [ ] T003 [OBJ-1] {(FR-002)} {(FR-004)} Aussagekraft vorhandener Vertragsfixtures und fehlende Grenzfälle in `Tests/test_openapi_snapshot_drift.py` sowie `PBStudio.UI.Tests/TransportContractTests.cs` prüfen; gezielt fehlende Nachweise erfassen.
- [ ] T004 [OBJ-1] {(FR-001)} {(FR-002)} {(FR-003)} {(FR-004)} {(TR-001)} {(TR-002)} Alle Anforderungen in `specs/00028-dto-consolidation/evidence/requirements-matrix.md` auf konkrete Umsetzung und belastbare Belege abbilden.
- [ ] T005 [OBJ-1] {(FR-003)} {(FR-004)} Unabhängiges Review von Vertrag, Adaptern und Abnahmeabdeckung in `specs/00028-dto-consolidation/evidence/review.md` aktualisieren.
- [ ] T006 [OBJ-1] {(FR-003)} {(FR-004)} Sichtbare echte Backend-/GUI-Hauptflows und Schutzinvarianten in `specs/00028-dto-consolidation/evidence/live.md` nachweisen; Fixtures ersetzen diese Abnahme nicht.
- [ ] T007 [OBJ-1] {(TR-001)} {(TR-002)} Vorhandene finale Suite-/C#-/Release-/Gatebelege in `specs/00028-dto-consolidation/evidence/final-checks.md` hinsichtlich Stand und Scope zuordnen; nur begründet erneut prüfen.
- [ ] T008 [OBJ-1] {(FR-001)} {(TR-001)} Nach vollständiger Revalidierung `specs/00028-dto-consolidation/qc-report.md` aktualisieren und erst dann echte commit-/hashgebundene Completion-/QC-Marker erzeugen; offene Abnahme nicht als PASS umdeuten.
