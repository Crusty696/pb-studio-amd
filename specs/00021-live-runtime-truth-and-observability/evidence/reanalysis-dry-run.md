# Reanalysis Dry Run — 2026-08-11

## Recovery-Gate

- Live-Control-Plane read-only konsistent: CURRENT, Journal und Manifest-Hash
  zeigen auf Generation
  `20260809T113808303983Z-42cf3a26dc864eeba15c969730842718`.
- Manifest: 366 Artefakte und 402 Referenzen.
- Restore wurde ausschließlich gegen eine GUID-isolierte temporäre Kopie
  bewiesen; Live-Daten waren ausgeschlossen.
- Test:
  `Tests/test_recovery_owner_adapters.py::test_restore_older_generation_removes_later_optional_owner_files`.
- Ergebnis: 1 passed, 0 failed in 15,90 s.

## Read-only Inventar

- Projekte: 3; taglose Videos: 465.
- Analyse-Gesamtstatus: completed 1, failed 1, missing 203, partial 260.
- Captions: failed 209, interrupted 2, missing 252, skipped 2.
- Farben: completed 260, interrupted 1, missing 204.
- Geplante Wiederholung: Captions 465, Farben 205.
- Zu erhaltende valide Stages: Szenen 261, Motion 260, Embedding 259,
  Farben 260.
- Anonymisierter Inventar-SHA-256:
  `60f060a7920f44a512db2cc4d3bb3ec2166e61a1bc03f5d9565e259f3177c0c1`.

## Entscheidung

Dry-Run und isolierter Restore-Vertrag sind grün; es gab keine Mutation. Die
frühere Zahl 209 beschreibt nur fehlgeschlagene Caption-Stages, nicht den
aktuellen Gesamtbestand von 465 taglosen Videos. Canary bleibt gesperrt.
