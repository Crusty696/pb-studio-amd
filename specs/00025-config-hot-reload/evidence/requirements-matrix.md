# Requirements Matrix: Config-Hot-Reload (Spec 00025)

| Anforderung | Beschreibung | Implementierung | Test | Status |
|---|---|---|---|---|
| FR-001 | Externe Aenderungen innerhalb von 3s erkannt | src/pb_studio/config_manager.py | test_config_watcher_background_polling | VERIFIED |
| FR-002 | Validierung, Last-Known-Good Schutz bei Fehlern | src/pb_studio/config_manager.py | test_config_hot_reload_invalid_json_keeps_last_good, test_config_hot_reload_invalid_structure_keeps_last_good | VERIFIED |
| FR-003 | Revision, Diff, keine Endlosschleifen bei Eigen-Saves | src/pb_studio/config_manager.py | test_config_hot_reload_valid_update, test_config_hot_reload_conflict_detection | VERIFIED |
| FR-004 | Verbraucher-Matrix (ai.task_overrides etc.) | src/pb_studio/config_manager.py | test_config_hot_reload_valid_update | VERIFIED |
| FR-005 | Dokumentation von live/next_job/restart_required | src/pb_studio/config_manager.py | test_key_classification_coverage | VERIFIED |
| TR-001 | Lifecycle-Poller ohne neue Abhaengigkeiten | src/pb_studio/config_manager.py | test_config_watcher_background_polling | VERIFIED |
