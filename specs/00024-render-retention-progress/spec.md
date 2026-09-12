# Render-Retention und einheitlicher Fortschritt

**Status:** SPECIFIED, 2026-09-07. **Quelle:** Nutzerauftrag Punkt 12; specs/00023-backlog-completion.

## Ziel und Geltungsbereich
Den genannten Backlogpunkt vollständig im realen App-Pfad schließen. Die folgenden Designentscheidungen sind Vorschläge dieser Spezifikation, keine behaupteten früheren Beschlüsse. Keine Implementations- oder Live-Abnahme wird hier behauptet.

## Befund
`backend/routers/render_router.py::_cleanup_old_render_tasks` entfernt terminale Einträge bei mehr als 50 Tasks, ohne belastbare Sortierung nach Abschlusszeit. Cancel-Flags werden separat zeitabhängig entfernt. `backend/schemas/render_schemas.py::RenderProgress` liefert `percent`; Queue-Aufrufe verwenden bereits `progress_percent`.

## Anforderungen
- FR-001: Eine dokumentierte konfigurierbare Alters- und Anzahlgrenze begrenzt ausschließlich abgeschlossene Render-Metadaten. Vorgeschlagener Default: 30 Tage und 50 terminale Jobs, jeweils älteste zuerst. Aktive, wartende, pausierte, resumierbare Jobs und Jobs mit lebendem Worker sind ausgenommen.
- FR-002: Persistierte Queue und In-Memory-Historie verwenden dieselbe Retention-Entscheidung. Wiederholter Cleanup und Neustart sind idempotent. Fehlender oder ungültiger Abschlusszeitpunkt schützt den Eintrag und erzeugt Diagnose.
- FR-003: Medien, Renderausgaben, Projektdateien, Recovery-Generationen, Evidenz und Clip-Cache werden nicht gelöscht. Cancel-Flags bleiben bis belegtem Worker-Ende erhalten.
- FR-004: `progress_percent` ist kanonisch, endlich und 0..100. Legacy-`percent` bleibt während kompatibler Migration wertgleich. HTTP, SSE, persistierter Queue-Status und WPF zeigen denselben Wert. Nur erfolgreicher vollständiger Abschluss erreicht 100; Fehler/Abbruch behalten letzten belegten Wert.
- TR-001: Zeitgrenzen verwenden UTC-Wanduhr für Neustart-Persistenz; monotone Zeit nur für laufende Dauer. Retention läuft unter vorhandenen Owner-/Recovery-Grenzen, ohne neue DB-Migration.
## Abnahme
Boundary-Tests für beide Grenzen, Restart, aktive Worker, fehlende Zeit und konkurrierenden Abschluss. API/SSE/Queue/WPF-Parität für Start, Fortschritt, Erfolg, Fehler und Cancel. Echte sichtbare AMF-Probe mit Backend. Vorher/Nachher-Hashes geschützter Dateien identisch.

## Gates
Getrenntes Feature gemäß specs/00020-obj75-open-bug-fixes/residual-remediation-plan.md. Dessen OBJ-75-Release-Vorbedingung vor Implementierung anhand aktueller Marker prüfen; fehlendes Gate explizit beim Parent behandeln. Spec → Plan → Tasks → Implement → QC. Keine .completed/.qc-passed ohne reale Belege. Python 3.11/NumPy 1.26.4, DirectML/AMF und bestehende Recovery-Grenzen gelten.
