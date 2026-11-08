# Spec: Sicherheits- und Dependency-Aktualisierung

**OBJ-1:** Sicherheitsbefunde und Merge-Gates nachvollziehbar beheben.

Aktive Aufgaben: T001-T006.

## Ziel
PR 34 nach vertretbarer Ausnahmepruefung, reproduzierbarem Paketupdate und
gruenen Pflichtchecks regulaer nach main mergen. Nutzerfreigabe 2026-11-08:
Ausnahmen aktualisieren; Paketinstallationen erst nach Projektbereinigung.
Bereinigungsabschluss im zugehoerigen Chat am 2026-11-08 bestaetigt.

## Anforderungen
- **FR-001:** Bestehende SCA-Ausnahmen nur nach Erreichbarkeitspruefung maximal
  30 Tage erneuern; keine pauschalen Ausnahmen fuer neue Befunde.
- **FR-002:** Neue Findings durch kompatible, hashgebundene Windows-Wheels beheben.
  NumPy 1.26.4, Python 3.11, DirectML und CPU-Torch-Vertrag bewahren.
- **FR-003:** Bestehende Produktionsumgebung waehrend isolierter Pruefung bewahren.
- **FR-004:** Skip-Ausnahmen anhand aktueller Tests pruefen, veraltete entfernen.
- **TR-001:** Lockvalidierung, gezielte Regressionen, frischer SCA-Report und alle
  acht GitHub-Pflichtchecks muessen den finalen Commit abdecken.
- **OR-001:** Keine Schutzregel umgehen; fremde Bereinigungsarbeit erhalten.

## Grenzen
Keine neue GUI-/Medienabnahme und kein Abschluss von Spec 00028/00037/00038.
Scanbefunde und Erreichbarkeitsgrenzen: docs/security-review-2026-11-08.md.
