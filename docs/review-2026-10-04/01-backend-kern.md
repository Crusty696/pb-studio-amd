# Zone 01 – Backend-Kern
(Skelett, wird fortlaufend ergänzt)

## Abdeckung
| Datei | Zeilen | vollständig gelesen |
|---|---|---|
| backend/__init__.py | 0 | ja (leer) |
| backend/middleware/__init__.py | 0 | ja (leer) |
| backend/_brain_singleton.py | 122 | offen |
| backend/app_state.py | 1845 | offen |
| backend/config.py | 116 | offen |
| backend/dependencies.py | 550 | offen |
| backend/main.py | 824 | offen |
| backend/media_path_policy.py | 230 | offen |
| backend/owner_capability.py | 53 | offen |
| backend/middleware/gpu_lock.py | 83 | offen |
| backend/middleware/owner_capability.py | 122 | offen |
| backend/recovery_bootstrap.py | 1049 | offen |
| backend/recovery_runtime.py | 101 | offen |
| backend/schemas/*.py (9) | 1073 | offen |

## Befunde
(Zwischenstand: gelesen owner_capability*, gpu_lock, _brain_singleton, config, recovery_runtime, media_path_policy, dependencies, main, app_state komplett. Befunde werden nach den Greps final ausformuliert; Rohnotizen:)
- main.py: _zombie_watcher ruft _force_exit() alle 5 s erneut auf (jedes Mal neuer 300-s-Timer); Doppelimporte get_app_state (177/322/349/389), uvicorn/os/threading in _force_exit doppelt; set_status_publisher(None) nur fuer Vision, nicht chat_agent/llm_narrator; /gpu/status blockierend im async-Pfad, SystemMonitor() pro Request; GpuStatusResponse/GpuCleanupResponse inline in main.py.
- app_state.py: update_audio_analysis/update_video_analysis doppelte if-Ketten (ai_data vs cache_update); register_audio/video_clip Schluessellisten 3x kopiert; load_from_db schluckt ValueError (Unsicherer Medienpfad) -> return False; `if ai_data:` immer wahr nach migrate; Docstring "deep copy" bei shallow dict(v); persistence_error/_persistence_error Doppel-Wrapper.
- dependencies.py: manager=None/if manager is None redundant; publish_event client_id ungenutzt.

## Refactoring-Kandidaten (priorisiert)
## Nicht geprüft / Unsicherheiten
