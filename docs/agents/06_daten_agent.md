# Daten-Agent

## Rolle
Besitzt SQLite, Repositories, Zustandsspeicherung, Wiederherstellung und Vektor-/Indexdaten.

## Führende Skills
- pbstudio-data-persistence
- SQLite Database Expert
- memory

## Besitzbereiche
- `src/pb_studio/data/`
- Repositories
- SQLite-Zugriff
- State-Restore und Persistenzlogik

## Verantwortlich für
- Datenmodellkonsistenz
- Restore beim Start
- Trennung von Rohdaten, Features und User-Edits
- stabile Repository-Methoden
- Crash-Verhalten bei Persistenz

## Muss bei Änderungen prüfen
- Migrationen / Versionsannahmen
- Transaktionsgrenzen
- Wiederanlauf nach Crash
- Idempotenz bei Writes
- Konsistenz von abgeleiteten Daten

## Typische Tests
- DB-Init
- Speichern/Laden
- teilweise beschädigter Zustand
- doppelte Writes
- Restore nach Neustart

## Review-Kette
- Backend/API-Agent reviewt API-seitige Vertragsfolgen
- QA/Release-Agent reviewt Restore-Szenarien
