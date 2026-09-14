# Plan: C#-Transporttypen auf NSwag konsolidieren

**Status:** PLANNED, 2026-09-07. **Basis:** spec.md.

## Voraussetzungen und Clarify
Spec gelesen; Umfang durch FR/TR-IDs begrenzt. Konkrete vorgeschlagene Entscheidungen stehen in spec.md. Kein Nutzerwunsch wird als bereits getestet ausgegeben. Vor Implementation prüft Parent das vorgelagerte OBJ-75-Gate sowie neue Architektur-/API-Entscheidungen; keine stillschweigende Umgehung.

## Architektur und Umsetzung
Endpoint-/Transport-/UI-Modell-Matrix zuerst erstellen. In kleinen Clustern zunächst reine Datenverträge, dann komplexe Enums/nullability, zuletzt Observable-Adapter migrieren. Schemafehler im Backend berichtigen, Snapshot über vorhandenen Generator regenerieren. Öffentliche IApiClient-Vertragsänderungen vor Umsetzung explizit im Review auflisten. Generated-Typen vollständig qualifizieren oder klare Aliase verwenden. Keine parallele Consumer-Migration in gemeinsamen Dateien. Referenzfreie manuelle Deklarationen nur nach bestehender Änderungs-/Löschfreigabe entfernen; kein dauerhafter doppelter Vertrag.

## Dateien und Ownership
PBStudio.UI/Models; PBStudio.UI/Services/ApiClient.cs und IApiClient.cs; PBStudio.UI/ViewModels; PBStudio.UI/openapi.snapshot.json; Backend-Schemas/Router nur bei fehlendem Vertrag. Der Implementierer besitzt nur ausdrücklich vom Parent zugewiesene Dateien. Tests erhalten eigene eindeutige Pfade; bestehende Änderungen anderer Agenten bleiben erhalten. Shared-Zonen und C#-Builds sequenziell, keine parallele Vollsuite.

## Verifikation
JSON-Vertragsfixtures pro Endpointcluster, API-Mocks/VM-Tests, Snapshot-Reproduktion, C#-Tests und Release sowie GUI-Hauptflows. Zuerst sinnvolle Regressionen, dann fokussierte Tests. Parent führt finale Python-Vollsuite und C#-Builds gemäß tatsächlich betroffenen Bereichen sowie sichtbare Live-QC aus. Test- und Live-Belege getrennt mit Laufzeit, Versionen und Resultaten speichern.

## Risiken und Rückkehrpfad
Unvollständige Consumer-Inventare, Nebenläufigkeit und Wire-Compatibility explizit prüfen. Änderungen in klaren Feature-Diffs reviewen; keine Produktionsdatenmigration. Bei Livefehlern Originalkonfiguration/Runtime geordnet wiederherstellen, Fehlerbeleg erhalten und Gate offen lassen. Rollback bedeutet gezielten Review des Feature-Diffs, niemals blindes Reset fremder Änderungen.

## Fertigstellung
Tasks erst nach belegter Umsetzung abhaken. .completed erst nach vollständiger Implementation, qc-report.md und .qc-passed erst nach bestandener tatsächlicher QC. Brain-Log durch Parent aktualisieren.

