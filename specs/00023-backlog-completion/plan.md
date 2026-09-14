# Plan: Verifizierter Backlog-Abschluss

**Status:** PLANNED, 2026-09-06
**Spec:** spec.md

## Reihenfolge

1. Read-only Baseline: Branch/Dirty-State, Skills/Brain, Runtime/Recovery,
   aktuelle Codebefunde und Wartung. Unveränderter GUI-Start vor Produktpatches.
2. Bestätigte kleine Fehler mit disjunkten File-Zonen und Regressionen beheben.
3. Detaildesign je Feature festhalten; bestehende Infrastruktur weiterverwenden,
   dann getrennte Implementierungen samt fokussierter Verifikation.
4. Parent führt native GUI-/GPU-/Datenläufe seriell aus, samt Vorher/Nachher-
   Nachweisen und sauberem Shutdown. Keine Agenten mutieren Live-Daten.
5. Wartung evidenzbasiert abschließen; unabhängige Reviews, Vollsuite, Release,
   Live-QC und Wissenspflege. Marker erst bei tatsächlicher Vollständigkeit.

## Isolation

Parent besitzt SDD, Brain, Runtime, GUI und finale Tests. Agenten bekommen
explizite disjunkte Dateien; Shared-Zones nur sequenziell. Native PowerShell
ist verifiziert; Linux-Mount-Workarounds passen hier nicht. Tests verwenden
eindeutige temporäre Pfade und keinen parallelen vollständigen pytest-Lauf.

## Aktuelle Baseline

HEAD 9234f441fe58fd2f8ef8c2cea92b270e814d62b6, Branch
codex/obj76-runtime-truth. Vorhandene ungetrackte function_inventory.json und
patch.py bleiben unangetastet. Kein PB-Studio-/8765-Listener beobachtet;
RUNTIME_DIRTY fehlt; Recovery-Journal COMMITTED vom 2026-08-31.
Computer Use @oai/sky initialisiert, Windows-App-Inventar erfolgreich.

## Verifikation und Risiken

Test-PASS ist kein Live-PASS. Keine harten Backend-/WPF-Abbrüche;
Shutdown gilt erst bei verschwundenem RUNTIME_DIRTY als sauber.
Alte Start-Skills enthalten gefährliche taskkill-Anleitungen; tatsächlichen
Code vor Aufruf prüfen. Protected Datenwrites nur mit validiertem Recovery-
und Erhaltungsnachweis. Bei Restfehlern keine falschen grünen Marker.
