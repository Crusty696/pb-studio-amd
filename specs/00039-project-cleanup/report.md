# Bereinigung 2026-11-01

## Entfernt und geprueft
49 Ziele, 734648061 logische Dateibytes (700.6 MiB): alte Refactor-038-Testkopien, Pytest-Verzeichnisse, Ruff-Cache und Python-Bytecode in src/backend/Tests/scripts/archive/scratch.
Inventar: inventory.json. Alle Zielpfade nach Entfernung abwesend. Alle zuvor getrackten Dateien SHA-256-identisch; .venv/Scripts/python.exe SHA-256-identisch. Junction der Testkopie entfernt, echtes Venv nicht verfolgt.
Vorher kein Python-/dotnet-/PBStudio-Prozess mit Projektpfad in seiner Kommandozeile festgestellt. Keine Prozesse beendet.

## Dubletten und bewusst erhaltene Dateien
35 Gruppen identischer nichtleerer getrackter Dateien vollstaendig im Inventar erfasst.
- Abschlussmarker und historische Baseline-/QC-Belege haben eigene Zuordnung und bleiben erhalten.
- Historische Commit-/Vault-/Push-Skripte sind bereits fail-closed (exit 2). test_legacy_git_mutation_wrappers_are_fail_closed verlangt mehrere davon ausdruecklich. Entfernung waere eine Vertragsaenderung; keine Sicherheitsgrenze geaendert.
- Agent-Skillkopien liegen in unterschiedlichen Discovery-Verzeichnissen. Keine ausreichend belegte Entbehrlichkeit, deshalb erhalten.
- archive enthielt ueberwiegend verwaisten Bytecode (entfernt), daneben alte Video-/Logbelege (erhalten).
- scratch enthaelt ONNX-Modelle, Diagnoseprogramme und offene T002/T010-Arbeiten; ausser Bytecode unveraendert.
- temp enthaelt echte Stem-Audiodateien und stem-runs. Kein Nachweis, dass Projekte diese nicht mehr benoetigen; erhalten.
- Release-Binaries, Modelle, Produktionsdaten, Recovery, fremde Aenderungen und Spec00038-Belege erhalten.

## Grenze
Belegte Wegwerfartefakte bereinigt. Keine Behauptung, alle alten Dateien seien entbehrlich oder entfernt. Produktcode unveraendert; kein Build oder App-Neustart notwendig und keine neue GUI-/Medienabnahme. Spec00038 bleibt offen.
