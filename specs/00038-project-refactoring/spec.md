# Specification: Projektweite Refaktorierung

Datum: 2026-10-30. Auftrag: Gesamtrefaktorierung; Nutzer priorisiert Wartbarkeit, Leistung und Bedienung gemeinsam.

## Objective

OBJ-1 (P1): UI, Backend und Medienpipeline entlang klarer Verantwortungen entkoppeln, bestehende Funktionen und Daten erhalten.
OBJ-2 (P1): Vermeidbare Arbeit und blockierende Bedienabläufe reduzieren, mit reproduzierbaren Belegen.
OBJ-3 (P1): Bestehende Bedienabläufe nachvollziehbar und reaktionsfähig halten; sichtbare Abnahme getrennt von Tests dokumentieren.

## User Stories

### US1 — Wartbare Anwendung (P1)
Änderungen an API-Verträgen, Timelineabschluss und Projektpersistenz lassen sich getrennt nachvollziehen und testen, ohne komplette Router oder große ViewModels ändern zu müssen.

### US2 — Effiziente Bearbeitung (P1)
Wiederholte Arbeit an denselben Medien und vermeidbare Initialisierung werden reduziert. Ergebnisse, Reihenfolge und Fehlerverhalten bleiben erhalten.

### US3 — Verlässliche Bedienung (P1)
Bestehende Bibliotheks-, Analyse- und Timelineabläufe bleiben bedienbar. Lange Arbeit blockiert keine unnötigen Eingaben; Abbruch und Projektwechsel bleiben korrekt.

## Functional Requirements

- FR-001: Öffentliche Python-Importpfade und C#-Typen, HTTP/SSE-Verträge und persistierte Formate bleiben kompatibel.
- FR-002: API-Transport und Response-Modelle erhalten getrennte Zuständigkeiten; gemeinsame Lifecycle-/Cancellationzustände bleiben einmalig.
- FR-003: Timelineabschluss wird von der Pacing-Orchestrierung getrennt und gemeinsam von Pacing und Export genutzt.
- FR-004: Projektdateiverträge werden unabhängig von HTTP-Routern nutzbar.
- FR-005: Pipeline-Refaktoren erhalten Timing, Provenance, Wiederaufnahme und Ergebnisidentität.
- FR-006: Leistungsoptimierungen benötigen Vergleichsbelege; Dateiaufteilung allein zählt nicht als Beschleunigung.
- FR-007: Bedienänderungen benötigen einen konkreten reproduzierbaren Anlass, Regressionstests und sichtbare Prüfung; kein spekulatives Redesign.

## Technical Requirements

- TR-001: WPF/.NET 9, Python 3.11.x, NumPy 1.26.4, DirectML, AMF und bestehende LM-Studio-Verträge bleiben erhalten. Keine Installation oder Providerumschaltung.
- TR-002: Vor Änderungen Caller/Tests lesen. Tests mit PYTHONPATH=src und isoliertem APPDATA/LOCALAPPDATA ausführen.
- TR-003: C#-Änderungen verlangen Release-Build; geänderte Runtime muss vor Funktionsbehauptungen tatsächlich geladen sein.
- TR-004: Vorhandene uncommittete Änderungen einschließlich Spec 00037 bleiben erhalten. Keine Medien-, Datenbank- oder Konfigurationsmigration.
- TR-005: separator.py bleibt geschützt. Recovery-, Auth-, GPU-Lock- und Persistenzregeln werden nicht beiläufig geändert.
- TR-006: Neue Artefakt-/Testpfade verwenden ASCII-Namen ohne Leerzeichen, Umlaute oder Shellmetazeichen. Bestehende Nutzerpfade werden nicht umbenannt; PowerShell-Dateizugriffe verwenden LiteralPath, Prozessparameter werden korrekt getrennt und quotiert. Nutzerpraezisierung 2026-10-30.

## Scope and Approach

Inkrementelle Extraktionen innerhalb der bestehenden Architektur. Ein Komplettneubau würde bestehende Verträge und offene Arbeiten unnötig gefährden; reine Formatierung erfüllt die drei Nutzerziele nicht.

Alle Domänen werden inventarisiert. Änderungen erfolgen dort, wo konkrete Kopplung, Duplikation oder vermeidbare Arbeit belegt ist. Nicht jedes unveränderte Modul benötigt einen künstlichen Umbau. Höherriskante Zustands-/Recoveryumbauten benötigen eigene Charakterisierung vor Umsetzung.

## Acceptance

Caller und Vertragsprüfungen bestehen; Vergleichsbelege zu geänderten Algorithmen vorhanden; Release-Build und passende native Tests dokumentiert; sichtbare Bedienprüfung getrennt berichtet. Keine .completed/.qc-passed-Marker für bloße Planung, bestandene Teiltests oder ausstehende Gesamtprüfung.

## Initial Evidence

Branch codex/full-audit-remediation; 20 bereits geänderte getrackte Dateien plus ungetrackte Vorarbeiten. Drei unabhängige lesende Analysen für UI, Backend/Core und Medienpipeline durchgeführt. Vault-Projektindex gelesen; _wiki/decisions fehlt, vorhandene specs/adrs/0001–0004 und bestätigte ComfyUI-Entscheidungen berücksichtigt.
