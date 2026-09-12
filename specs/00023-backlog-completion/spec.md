# Spezifikation: Verifizierter Abschluss des offenen Backlogs

**Status:** SPECIFIED, 2026-09-06
**Quelle:** direkter Nutzerauftrag mit 20 Punkten in dieser Sitzung.

## Problem

OBJ-76 besitzt offene reale Tagging-/Canary-Gates. Weitere benannte Fehler,
Integrationslücken und Wartungsentscheidungen brauchen aktuelle Belege.
Historische Testzahlen und Dokumentationsstatus ersetzen keine Prüfung.

## Objective

Die 20 beauftragten Punkte einzeln implementieren oder durch aktuelle
NO-CHANGE-Belege auflösen und unabhängig verifizieren. Unvermeidbare externe
Blocker bleiben explizit offen; keine Abschlussmarker ohne vollständige QC.

## Anforderungen

- Reale GUI-Prüfungen sichtbar im Vordergrund, mit echtem Backend.
- Bestehende OBJ-76-Gates und Stage-Hash-Erhaltung gelten weiter.
- Der aktuelle Auftrag autorisiert Live-Prüfungen einschließlich begrenztem
  Watchdog-Pausieren mit identischer Wiederherstellung und zehn Canary-Clips.
  Massen-Nachanalyse bleibt bis 10/10 und eigener Entscheidung gesperrt.
- Keine erfundenen menschlichen Bewertungen: die 20 Brain-Bewertungen müssen
  als technische Agenten-Eingaben oder echte Nutzerbewertungen bezeichnet sein.
- Python 3.11, NumPy 1.26.4, DirectML-only ML, AMF; vorhandene Runtime nutzen.
- Bestandsmedien, gültige Analysestages und fremde Arbeitsdateien schützen.
- DTOs, Retention/Progress, Hot-Reload, Token-Deltas und Virtualisierung entlang
  der realen Datenkette prüfen; Detaildesign vor jeweiliger Implementierung.
- Legacy/PR/Altumgebungen anhand aktueller Nutzung entscheiden; Ausnahmen
  nicht durch bloße Datumsverschiebung als behoben ausweisen.

## Abnahme

Jeder Task besitzt reproduzierbaren Beleg und klaren Status. Fokussierte Tests,
eine sequenzielle Vollsuite nach Änderungen, C#-Tests und Release-Build sowie
reale GUI-/Medienprüfungen. Brain und autorisierte Codex-Erinnerungsnotiz
halten Ergebnisse und Werkzeugfehler fest.
