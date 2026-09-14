# Plan: Render-Retention und einheitlicher Fortschritt

**Status:** PLANNED, 2026-09-07. **Basis:** spec.md.

## Voraussetzungen und Clarify
Spec gelesen; Umfang durch FR/TR-IDs begrenzt. Konkrete vorgeschlagene Entscheidungen stehen in spec.md. Kein Nutzerwunsch wird als bereits getestet ausgegeben. Vor Implementation prüft Parent das vorgelagerte OBJ-75-Gate sowie neue Architektur-/API-Entscheidungen; keine stillschweigende Umgehung.

## Architektur und Umsetzung
Retention-Owner und persistierten Jobpfad vollständig inventarisieren; Status-/Worker-/Recovery-Grenzen erfassen. Zeit-/Anzahlregeln und UTC-Abschlussmetadaten an bestehende Persistenz anbinden. Cleanup entscheidet unter Owner-Lock, ausschließlich über terminale Metadaten. Progress an einem gemeinsamen Normalisierungspunkt schreiben, percent als kompatiblen Alias führen; Export-UI konsumiert progress_percent.

## Dateien und Ownership
backend/routers/render_router.py; backend/schemas/render_schemas.py; Queue-Owner nach Inventar; PBStudio.UI/Models und ViewModels des Exports. Der Implementierer besitzt nur ausdrücklich vom Parent zugewiesene Dateien. Tests erhalten eigene eindeutige Pfade; bestehende Änderungen anderer Agenten bleiben erhalten. Shared-Zonen und C#-Builds sequenziell, keine parallele Vollsuite.

## Verifikation
Retention-/Worker-Race und Neustart-Verträge; JSON/SSE/Queue-Fortschritt; AMF-Liveprobe. Zuerst sinnvolle Regressionen, dann fokussierte Tests. Parent führt finale Python-Vollsuite und C#-Builds gemäß tatsächlich betroffenen Bereichen sowie sichtbare Live-QC aus. Test- und Live-Belege getrennt mit Laufzeit, Versionen und Resultaten speichern.

## Risiken und Rückkehrpfad
Unvollständige Consumer-Inventare, Nebenläufigkeit und Wire-Compatibility explizit prüfen. Änderungen in klaren Feature-Diffs reviewen; keine Produktionsdatenmigration. Bei Livefehlern Originalkonfiguration/Runtime geordnet wiederherstellen, Fehlerbeleg erhalten und Gate offen lassen. Rollback bedeutet gezielten Review des Feature-Diffs, niemals blindes Reset fremder Änderungen.

## Fertigstellung
Tasks erst nach belegter Umsetzung abhaken. .completed erst nach vollständiger Implementation, qc-report.md und .qc-passed erst nach bestandener tatsächlicher QC. Brain-Log durch Parent aktualisieren.

