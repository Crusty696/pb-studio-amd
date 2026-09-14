# Plan: Externes Config-Hot-Reload mit letztem gültigen Stand

**Status:** PLANNED, 2026-09-07. **Basis:** spec.md.

## Voraussetzungen und Clarify
Spec gelesen; Umfang durch FR/TR-IDs begrenzt. Konkrete vorgeschlagene Entscheidungen stehen in spec.md. Kein Nutzerwunsch wird als bereits getestet ausgegeben. Vor Implementation prüft Parent das vorgelagerte OBJ-75-Gate sowie neue Architektur-/API-Entscheidungen; keine stillschweigende Umgehung.

## Architektur und Umsetzung
Zuerst sämtliche get/set-Reader und settings.json-Abgrenzung inventarisieren. Poller liest Dateibytes mit Digest und stabilisiert Änderungen über zwei Abtastungen (Intervall 1 s); Schema-validierten Kandidaten atomar publizieren. Snapshotrevision und applied/pending/rejected-Key-Status führen. Live-Consumer invalidieren explizit; Startparameter separat als restart_required erhalten. UI-Saves verwenden Konflikterkennung gegenüber letzter Dateirevision. Watcher im bestehenden Lifecycle starten/stoppen; Recovery erhält exklusiven Vorrang.

## Dateien und Ownership
src/pb_studio/config_manager.py; backend/main.py (Shared-Zone); backend/routers/models_router.py; tatsächliche weitere Config-Consumer nach Matrix. Der Implementierer besitzt nur ausdrücklich vom Parent zugewiesene Dateien. Tests erhalten eigene eindeutige Pfade; bestehende Änderungen anderer Agenten bleiben erhalten. Shared-Zonen und C#-Builds sequenziell, keine parallele Vollsuite.

## Verifikation
Temporäre config.json, gültig/ungültig/Replace/Save-Race/Recovery; echter nächster Modellauftrag mit Original-Restore. Zuerst sinnvolle Regressionen, dann fokussierte Tests. Parent führt finale Python-Vollsuite und C#-Builds gemäß tatsächlich betroffenen Bereichen sowie sichtbare Live-QC aus. Test- und Live-Belege getrennt mit Laufzeit, Versionen und Resultaten speichern.

## Risiken und Rückkehrpfad
Unvollständige Consumer-Inventare, Nebenläufigkeit und Wire-Compatibility explizit prüfen. Änderungen in klaren Feature-Diffs reviewen; keine Produktionsdatenmigration. Bei Livefehlern Originalkonfiguration/Runtime geordnet wiederherstellen, Fehlerbeleg erhalten und Gate offen lassen. Rollback bedeutet gezielten Review des Feature-Diffs, niemals blindes Reset fremder Änderungen.

## Fertigstellung
Tasks erst nach belegter Umsetzung abhaken. .completed erst nach vollständiger Implementation, qc-report.md und .qc-passed erst nach bestandener tatsächlicher QC. Brain-Log durch Parent aktualisieren.

