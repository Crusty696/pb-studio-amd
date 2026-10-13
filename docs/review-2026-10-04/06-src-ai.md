# Zone 06 – KI-Schicht (src/pb_studio/ai)
Status: SKELETT, wird laufend ergaenzt.

## Abdeckung
| Datei | Zeilen | vollstaendig gelesen |
|---|---|---|
| (wird ergaenzt) | | |

## Befunde
(noch keine)

## Refactoring-Kandidaten (priorisiert)

## Nicht geprueft / Unsicherheiten

---
## ZWISCHENSTAND 1 (Rohnotizen, werden unten in Befunde ueberfuehrt)
Gelesen bisher: __init__.py, config_loader.py, llm_provider.py, siglip_wrapper.py, clap_wrapper.py, video_specialist.py, smart_director.py (alle vollstaendig), model_registry.py (vollstaendig).
- Aufrufer smart_director: produktiv nur get_instance/get_dominant_mood (pacing_service.py:143-146), encode_text (clip_selector.py:1388-1392), reset_instance (backend/main.py:428). analyze_audio/analyze_clips/generate_timeline/_analyze_*: 0 Aufrufer in src/backend (Grep), nur Tests.
- video_specialist: produktiv 0 Aufrufer in src/backend; nur scripts/long_stress_run.py:30 + Tests. 
- siglip_wrapper produktiv: backend/routers/video_router.py:115 (cached). video_embedder.py ist LEGACY (liefert nur Konstanten); Projektnotiz "Brain-Feeder = video_embedder.py" ist ueberholt: Producer ist siglip_wrapper via video_router.
- clap_wrapper produktiv: backend/routers/audio_router.py:874-876 (neuer CLAPAnalyzer je Aufruf), smart_director._load_clap.
- llm_provider.get_provider() liefert nie "auto" -> model_registry.py:226 Zweig toter Code.

## ZWISCHENSTAND 2
Zusaetzlich vollstaendig gelesen: model_inventory.py (555), lmstudio_client.py (1064).
- lmstudio_client: get_vision_model_names (633) 0 Aufrufer in src/backend/Tests/scripts (Grep) -> tot. embeddings() nur Tests/test_lmstudio_client.py. pull_model/delete_model auf Client: nur Tests, models_router hat eigene Routen. is_alive nur scripts/lmstudio_client_smoke.py. generate(): 1 Aufrufer backend/routers/models_router.py:1396. to_dict() (168) ohne neue Felder.
- /api/v0/models wird pro Inventar-Refresh mehrfach geholt: list_models->_get_native_model_details, get_model_capabilities, _loaded_lmstudio (model_inventory.py:436) = 3 identische GETs je LM-Studio-Probe.
- Ollama-Rest: Client erkennt Ollama (is_ollama, lmstudio_client.py:472,664), ModelInventoryService probt IMMER beide Provider (PROVIDER_NAMES, model_inventory.py:22,195) inkl. registry.ollama.ai HEAD (498-503) und Ollama-Zweig in get_model_capabilities; llm_provider VALID_PROVIDERS/"auto"; ModelRegistry.get_provider_override. Projektregel "Ein-Modell-Betrieb LM Studio".
- select_best_for_task (model_registry.py:583): produktiv nur brain/llm_narrator.py:393 im Zweig `client is not None` (laut Kommentar Test-Hook); Produktion nutzt selection_receipts_for_task. recommendation_with_reason (679): nur Tests/test_model_registry.py. _sort_models_by_mode/TASK_KEYWORDS nur von select_best_for_task.
- Dopplung Preferenzlisten: DEFAULT_TASK_PREFERENCES (model_registry.py:39) vs config.json ai.task_preferences (noch zu pruefen).
