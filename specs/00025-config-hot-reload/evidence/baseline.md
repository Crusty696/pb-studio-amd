# Baseline: Externes Config-Hot-Reload (Spec 00025)

Datum: 2026-09-12

## Status Quo vor Refactoring
1. src/pb_studio/config_manager.py:
   - Config wurde nur einmalig beim Start geladen.
   - Externe Aenderungen an config.json wurden nicht erkannt.
   - Kein Poller/Watcher vorhanden.
   - Keine Diffs oder Revisionsnummern.

## Geaenderte Dateien
- src/pb_studio/config_manager.py: Watcher mit 2-Phasen SHA256-Abtastung (Stabilisierung), Revisionszaehler, Callback-Subscription und Fallback auf letzten gueltigen Stand bei Syntax-/Strukturfehlern.
- Tests/test_config_hot_reload.py: 6 vollstaendige Regressionstests fuer Hot-Reload, ungueltiges JSON, Typvalidierung, Konflikterkennung und Watcher.
