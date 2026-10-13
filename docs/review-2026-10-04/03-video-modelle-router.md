# Zone 03 – Video- und Modell-Router

Stand: HEAD `e51e798`, read-only. Nichts ausgefuehrt (kein pytest/Backend/Build).

## Abdeckung
| Datei | Zeilen | vollständig gelesen |
|---|---|---|
| backend/routers/video_router.py | 3057 | ja (1-3057) |
| backend/routers/models_router.py | 1433 | ja (1-1433) |
| Querbelege (nur gezielt gelesen) | – | `src/pb_studio/video/moondream.py:60-95`, `backend/dependencies.py` (with_gpu_task-Signatur), `backend/schemas/video_schemas.py:46-56`, `PBStudio.UI/Models/ModelListResponse.cs`, `ApiClient.cs` (Modell-/Video-Routen), `ModelManagerViewModel.cs` (grep) |

## Antworten auf die Zusatzfragen (Kurzform)
- (a) Hilfsfunktionen ohne Aufrufer: keine komplett toten Funktionen in den beiden Dateien. Alle `_`-Helfer haben Produktiv-Aufrufer; vier sind nur Test-Indirektionen (Z03-014). Tot sind Zweige/Variablen: Z03-001, -002, -003.
- (b) Duplikate: Tag-Dedupe doppelt (Router vs. `lmstudio_vision_wrapper`) Z03-007; Frame-Sampling/Thumbnail/ffprobe teils parallel zu `src/pb_studio/video/*` Z03-008; Modellinventar-Statuslogik doppelt in `models_router` Z03-011.
- (c) Routen ohne Aufrufer in `ApiClient.cs`: **keine**. Alle 10 Video-Routen und alle 9 Modell-Routen haben Aufrufer (ApiClient.cs:261-327, 587-683, 801). Nur Request-Felder ohne UI-Sender: `force`, `analyze_colors`, `analyze_audio_key` (Z03-009).
- (d) Ollama/Moondream: **Ollama in `models_router` ist NICHT unerreichbar** – es ist ein per UI umschaltbarer Provider (`POST /models/provider`, `ModelManagerViewModel.cs:97,178,294-381`). Moondream-Fallback ist **belegt unerreichbar** (Z03-002).
- (e) GPU-Lock: nicht konsistent, Z03-010.
- (f) Blockierende Arbeit im async-Pfad: Z03-004.
- (g) `completed` trotz Teilfehler: Z03-005, Z03-006.

## Befunde

### Z03-001 · NIEDRIG · Toter Code · Unerreichbarer else-Zweig im SigLIP-Pfad
- Ort: `backend/routers/video_router.py:2315-2320` und `2430-2432`
- Was: `if not wrapper.is_ready: raise ...` (2315) gefolgt von `if wrapper.is_ready:` (2320). Der zugehoerige `else` (2430-2432, "SigLIP ONNX-Modell nicht gefunden — Embedding übersprungen", `has_embedding=False`) kann nie laufen.
- Beleg: gelesen 2315-2320, 2430-2432; die Bedingung ist nach dem `raise` immer wahr.
- Auswirkung: irrefuehrender Logtext, 110 Zeilen unnoetig um eine Ebene eingerueckt.
- Abhaengigkeiten: keine ausser `Tests/test_video_pipeline_truth.py` (testet `_run_video_gpu_analysis`).
- Empfehlung: `if wrapper.is_ready:` und else entfernen, Block ausruecken.
- Aufwand: S · Risiko: niedrig

### Z03-002 · MITTEL · Toter Code · Moondream-Fallback in der Videoanalyse faktisch unerreichbar
- Ort: `video_router.py:2451-2467` (`_run_moondream_inference_on_frames`), `2750-2766`, `2767-2880`, Imports `2635-2638`
- Was: Der Fallback laeuft nur, wenn `onnx_models_available()` True liefert. Die Funktion verlangt `moondream_decoder.onnx` (oder `moondream.onnx`), `src/pb_studio/video/moondream.py:86-91`.
- Beleg: `ls models/` enthaelt `moondream_encoder.onnx`, `moondream_pytorch.pt`, `moondream_tokenizer`, aber **kein** `moondream_decoder.onnx` und kein `moondream.onnx`. `find models -iname "*moondream*"` bestaetigt. Zweig 2750 (`not onnx_models_available()`) wird also real immer genommen. Der Code ist nur auf dieser Maschine/diesem Modellstand tot; faellt aber bei Nachinstallation des Decoders wieder aktiv. Entscheidung "Moondream endgueltig raus" ist eine Produktentscheidung.
- Auswirkung: ~140 Zeilen Fallback inkl. dreier `llm_status`-Events ("Moondream2 (ONNX)"), `moondream_worker_*`-Zustandsmaschine, zweiter Fortschrittsphase. Jede Captioning-Stage publiziert bei LM-Studio-Ausfall ein "unavailable"-Event fuer ein Modell, das nie existierte.
- Abhaengigkeiten: `src/pb_studio/video/moondream.py`, `moondream_wrapper.py` (`extract_tags_via_moondream`, auch `compute_color_features`/`extract_dominant_colors_with_weights` werden von hier benutzt – NICHT mitentfernen), WPF `llm_status`-Anzeige, `Tests/test_video_pipeline_truth.py`.
- Empfehlung: Entscheidung treffen. Wenn raus: Block 2735-2880 + 2451-2467 + `moondream_*`-Variablen entfernen; `compute_color_features` bleibt in `moondream_wrapper` (oder wandert nach `video/color_features.py`, siehe Z03-008). `caption_progress`-Phase 2 und `CAPTION_PRIMARY_PROGRESS_END_PERCENT` entfallen dann ebenfalls.
- Aufwand: M · Risiko: mittel (Tests mocken den Fallback)

### Z03-003 · NIEDRIG · Toter Code · `all_tags`/`seen_tags` redundant, Farbfeature-Nachberechnung tot
- Ort: `video_router.py:2624-2625, 2675-2678, 2828-2831, 2888`; `1471-1489`
- Was: (1) `all_tags`/`seen_tags` werden ausschliesslich in denselben Zweigen gefuellt, in denen auch `frame_tag_lists.append` laeuft. `all_tags[:10]` (2888) wird nur benutzt, wenn `frame_tag_lists` leer ist – dann ist `all_tags` ebenfalls leer. Der Fallback liefert immer `[]`. (2) Der Block 1471-1489 berechnet Helligkeit/Saettigung/Farbtemperatur/mood_tags nach, wenn `color_caption_res` eines der vier Felder nicht hat. `_run_color_and_caption_analysis` macht `result.update(compute_color_features(...))` (2612) vor `stage_status["colors"]="completed"`; `compute_color_features` liefert alle vier Schluessel (1486-1489 indiziert sie ohne `.get`). Der Nachberechnungs-Block ist damit nur mit einem Fake/Mock erreichbar (Schluss aus Code, nicht ausgefuehrt).
- Beleg: Lesen 2624-2888 / 1471-1489; Grep `all_tags|seen_tags` in video_router.py: 8 Treffer, alle oben.
- Auswirkung: Rauschen, falsche Sicherheit (der "Fallback" wirkt, tut aber nichts).
- Empfehlung: `all_tags/seen_tags` streichen, `tags = _merge_frame_tags(frame_tag_lists)`; Block 1471-1489 nach Pruefung der Mocks in `Tests/test_video_pipeline_truth.py` entfernen.
- Aufwand: S · Risiko: niedrig

### Z03-004 · HOCH · Stabilitaet/Performance · Blockierende Arbeit im Event-Loop
- Ort:
  - `video_router.py:2581-2612` (`_run_color_and_caption_analysis`, `async`): `cv2.VideoCapture`, bis zu 3 `cap.set/read`, `cvtColor`, `np.vstack`, **KMeans** (`extract_dominant_colors_with_weights`, k=5) laufen synchron im Loop.
  - `931-1046` (`list_clips`, `async`): pro Clip ohne Cache-Eintrag `_load_persisted_video_analysis` → `MediaRepository().find_by_project_and_path` + `json.loads` (SQLite-Zugriff, bis 200 Clips/Seite).
  - `1525-1527`: `state.project_commit` mit `_commit_pending_video_embedding` (FAISS `add_embedding_with_media_link`, Brain-Cache-Write) + DB-Persistenz synchron im Loop.
  - `1144-1151` (`get_thumbstrip`): bis 32 JPEG-Encodes im Loop.
  - `models_router.py:1221` und `382-391`: Config-Datei lesen/ConfigManager im Loop (klein).
- Beleg: gelesen; im Gegensatz dazu sind `_get_video_info`, `_generate_thumbnail`, Scene-Detection, GPU-Analyse und `detect_video_audio_key` korrekt per `asyncio.to_thread`/`with_gpu_task` ausgelagert – die genannten Stellen sind die Ausnahmen.
- Auswirkung: SSE-Heartbeat (alle 5 s), Health und andere Requests stehen waehrend KMeans/FAISS-Write/Listen-DB-Reads. Bei Captioning laeuft der Heartbeat-Task im selben Loop und kann in der Zeit nicht senden.
- Abhaengigkeiten: `Tests/test_video_pipeline_truth.py:119,187` ruft `_run_color_and_caption_analysis` direkt; ein `to_thread` fuer die Frame-/KMeans-Strecke aendert nur die Aufrufart.
- Empfehlung: Frame-Sammlung + KMeans in eine sync-Helferfunktion, per `asyncio.to_thread`; `list_clips` DB-Nachlesen als ein `to_thread`-Batch (oder eine Abfrage fuer alle Clip-IDs der Seite); Commit-Block per `to_thread` falls `project_commit` threadsicher ist (UNBEKANNT, `AppState` nicht Teil der Zone).
- Aufwand: M · Risiko: mittel

### Z03-005 · MITTEL · Korrektheit · "completed" ohne dass Stages gelaufen sind (`skipped` zaehlt als gesund)
- Ort: `video_router.py:453-465` (`_derive_video_analysis_status`), `1364-1366`, `525` (`is_analyzed = status == "completed"`)
- Was: Nicht angeforderte Stages werden `skipped` gesetzt. `_derive_video_analysis_status` wertet `skipped` nicht als Fehler. Ein Aufruf mit z.B. nur `detect_scenes=true` auf einen frischen Clip ergibt Status `completed`, `is_analyzed=True`, obwohl Motion/Embedding/Farben/Captions/Key nie liefen.
- Beleg: gelesen; der WPF-Client (`ApiClient.cs:304-310`) sendet immer 4 Flags, `VideoLibraryViewModel.cs:677-683` uebergibt die Flags aus `pass.*` (Mehrpass-Betrieb, einzelne Passes mit Teilmengen). Backend-Default `generate_captions=False` (`video_schemas.py:53`) weicht von der C#-Methodendefault `generateCaptions=true` ab.
- Auswirkung: UI/`list_clips` zeigt `is_analyzed=True` und `analysis_status=completed` fuer teilanalysierte Clips; Downstream-Gates, die `is_analyzed` statt `stage_status` lesen, lassen sie durch. Ob es durch den Mehrpass-Ablauf im Normalbetrieb kaschiert wird: UNBEKANNT (nicht live geprueft).
- Empfehlung: `completed` nur, wenn alle Pflicht-Stages (`scenes/motion/embedding/colors/captions`) `completed` sind; `skipped` ausserhalb des laufenden Passes → `partial`. Produktentscheidung (Pass-Konzept).
- Aufwand: M · Risiko: hoch (Tests `test_video_analysis_resume`, `test_video_status_audio_key_optional`, WPF-Statusanzeige)

### Z03-006 · MITTEL · Korrektheit · Teilfehler, die als Erfolg durchgehen
- Ort: `video_router.py:1529-1536`, `2603-2613`, `2275-2282`
- Was:
  1. `_dedupe_old_video_embeddings` schlaegt fehl → nur `logger.error`, Status bleibt `completed` und HTTP 200. Alte Vektoren bleiben (Outbox-Recovery soll es richten, nicht im Router belegt).
  2. Farb-Stage wird `completed`, sobald **ein** Frame lesbar war (3 geplant); fehlende Frames fliessen nicht in `stage_errors` (anders als bei Captions: `unread_frame_indices` → `partial`).
  3. Motion: ein unlesbares Sample (Toleranz 1) bleibt ohne Vermerk `completed`.
- Beleg: gelesen.
- Auswirkung: gering einzeln, aber Statuswahrheit (IRON RULE 10) weicht von der strengen Caption-Logik ab.
- Empfehlung: Stage-Fehlerdetail ("1/3 Frames lesbar") in `stage_errors` ohne Statuswechsel, bzw. `partial` bei Coverage < Plan.
- Aufwand: S · Risiko: niedrig

### Z03-007 · MITTEL · Redundanz · Zwei Tag-Dedupe-/Normalisierungssysteme mit unterschiedlichen Stamm-Parametern
- Ort: Router `video_router.py:339-450` (`_merge_frame_tags`, `_tag_stems` = 5 Zeichen, `_same_tag_meaning`, `_without_articles`, `_looks_english`, Konstanten 393-413) gegen `src/pb_studio/video/lmstudio_vision_wrapper.py:235-392` (`_normalize_tag`, `_parse_tags`, `_STEM_LEN = 7`, `_MAX_PER_STEM = 2`, Negations-/Hautfarben-/Zahl-Regeln).
- Was: Beide dedupen/normalisieren Tags (Stamm-Vergleich, Zahlwoerter/"gruppe", Artikel). Stammlaenge 5 vs. 7, andere Zahlwort-Listen (`_NUMBER_STEMS` im Router vs. 'gruppe von' im Wrapper). Das Router-Modul traegt damit Textverarbeitungs-Domaenenlogik (~110 Zeilen + 6 Konstantenmengen) in einer Routerdatei.
- Beleg: Grep `def _looks_english|_ENGLISH_WORDS` ausserhalb video_router.py: 0 Treffer; `_merge_frame_tags` wird von `scripts/dev/t014_caption_eval.py:24` und `Tests/test_video_caption_tag_merge.py:7` direkt aus dem Router importiert.
- Auswirkung: Aenderung eines Tag-Verhaltens muss in zwei Dateien nachgezogen werden; Wartbarkeit.
- Empfehlung: Kandidat `src/pb_studio/video/tag_merge.py`; Router importiert; alte Importpfade in Skript/Test mitziehen. Die zwei Stammlaengen bewusst vereinheitlichen oder dokumentieren (verhaltensaendernd!).
- Aufwand: M · Risiko: mittel

### Z03-008 · NIEDRIG · Redundanz · Parallele Implementierungen zu `src/pb_studio/video/*`
- Ort: `video_router.py:1789-1842` (`_get_video_info` ffprobe), `1845-1876` (`_generate_thumbnail`), `1956-2015` (Frame-Index/Addressable/Replacement), `2018-2056` (`_select_motion_peak_frames`), `3049-3057` (`_classify_motion`)
- Was: `src/pb_studio/video/frame_extractor.py:93` (`FrameGrabber.extract_thumbnail_strip`) + eigener Thumbnail-Weg im Router; ffprobe-Parsing von `r_frame_rate` auch in `rendering/render_service.py:661`; `CAP_PROP_FRAME_COUNT`-Sampling an 10 Stellen in `src` (`scene_detect.py:57`, `frame_extractor.py:57,117`, `visual_curves.py:51`, `smart_director.py:784,835,947`, `video_specialist.py:130,527`, `clip_selector.py:1418,1449`). `_classify_motion` existiert nur im Router (Grep `def _?classify_motion`: 1 Treffer), wird aber auch von `list_clips` benutzt – gehoert zu `video/raft.py`/Motion-Domaene.
- Beleg: Grep siehe oben. Ob die Duplikate semantisch identisch sind, wurde NICHT verglichen (UNBEKANNT).
- Empfehlung: Kandidat `video/media_probe.py` (ffprobe + Duration-Bounding + Sampling-Indizes). Nur planen, nicht blind zusammenfuehren.
- Aufwand: L · Risiko: mittel

### Z03-009 · NIEDRIG · Producer ohne Consumer · `VideoAnalyzeRequest`-Felder ohne UI-Sender, Schema-Default-Abweichung
- Ort: `backend/schemas/video_schemas.py:53-56`, `ApiClient.cs:304-310`
- Was: `force`, `analyze_colors`, `analyze_audio_key` werden von der WPF nie gesendet (immer Default). `generate_captions` Default Backend `False`, C#-Methode `true`.
- Beleg: gelesen; Grep `AnalyzeVideoAsync` in PBStudio.UI: 2 Aufrufer, beide ohne diese Felder. Andere Clients (Skripte, Tests) nicht geprueft → `force` kann von Tests/Skripten benutzt werden.
- Empfehlung: dokumentieren oder Default angleichen; nichts loeschen ohne Skriptpruefung.
- Aufwand: S · Risiko: niedrig

### Z03-010 · MITTEL · Stabilitaet · GPU-Lock/`with_gpu_task` uneinheitlich
- Ort: `video_router.py:1419-1425` (RAFT+SigLIP: `model_id="video_analysis_full"`, `manage_vram=False`), `2797-2803` (Moondream: `model_id="moondream_fp16"`, `manage_vram` Default True, `timeout_seconds=remaining` float gegen `int | None`-Signatur `dependencies.py:34`); LM-Studio-Vision (`extract_tags_and_model_via_lmstudio_async`, 2666) laeuft ohne Router-GPU-Lock; `models_router.py:1380-1399` (`/models/test`) ebenfalls ohne Lock.
- Was: Zwei Vorgehen (Lock+VRAM vs. Lock ohne VRAM), und LM-Studio nutzt dieselbe RX 7800 XT ausserhalb des Locks (extern, Vulkan; Steuerung nur ueber `active_vision_task_lease`, `models_router.py:502-515`). Die Doppelkontrolle Moondream: `wait_for(..., timeout=remaining)` UND `timeout_seconds=remaining` → zwei konkurrierende Timeouts.
- Beleg: gelesen; Projektstand in CLAUDE.md: VRAM-Reservierungscode laeuft heute nie.
- Auswirkung: kein akuter Fehler belegt; LM-Studio-VRAM und DirectML-RAFT/SigLIP koennen parallel konkurrieren (nur Sensor, kein Gate – bewusste Entscheidung laut CLAUDE.md).
- Empfehlung: dokumentieren, bei Moondream-Entfernung (Z03-002) erledigt sich der Sonderfall.
- Aufwand: S · Risiko: niedrig

### Z03-011 · NIEDRIG · Redundanz/Stil · `models_router.py`
- Ort: 
  - `610-730` und `736-810`: identischer Block `provider_by_name`/`lmstudio_ok`/`ollama_ok` doppelt.
  - `689` und `697`: `vision` wird im Konstruktor und danach nochmals gesetzt.
  - `691-694`: `getattr(model, "context_length", None)` obwohl das Dataclass-Feld existiert (`model_inventory.py:115-118`), nur `runtime_state` mappt auf `state` (`:423`).
  - `719`: `ProviderStatusEntry(**provider.__dict__)` bricht bei `slots`/Feldaenderung im Dataclass.
  - `35-95` `CURATED_VISION_MODELS`: Schluessel `suggested_mode` und `vision` werden nirgends gelesen (nur `description` und `size_estimate_gb`, `:289-327,358`); Docstring behauptet "Mirrors the defaults in model_registry" ohne Pruefung. Eintraege wie `qwen3.5-9b-uncensored-hauhaucs-aggressive` sind "Vision-Liste" mit `vision: False`.
  - `1-9` Modul-Docstring listet `/provider`, `/activate`, `/mode`, `/test` nicht.
  - `145-147` Kommentar "ollama_available ist jetzt tatsaechlich lmstudio_available" widerspricht dem Code (`ollama_ok` ist echter Ollama-Status; `lmstudio_available` separat).
  - `1422` Logtext "GPU-Smoke-Test" fuer Chat/Vision ueber LM Studio.
  - `850-867` Variable `completed` nur lokal als Flag, kein Terminalevent bei Stream-Ende ohne "success".
- Beleg: gelesen; Grep `CURATED_VISION_MODELS`: Definition `:35`, Nutzung `:289`, Test `test_t357_...:525` (prueft nur Abwesenheit im `/available`-Endpoint).
- Empfehlung: Helper `_provider_flags(snapshot)`; Kuratierliste auf (`name`→`description`,`size`) reduzieren oder an `model_registry` koppeln; Docstrings/Kommentare korrigieren.
- Aufwand: S · Risiko: niedrig

### Z03-012 · NIEDRIG · Korrektheit/Ehrlichkeit · `_enrich_model_entry` erfindet Groessen
- Ort: `models_router.py:316-349`
- Was: Bei `size_bytes == 0` wird eine Dateigroesse aus Namensregex und **Default 7.0 B** x Quantfaktor geschaetzt und als `size_gb/size_mb/size_bytes` ausgeliefert, ohne Kennzeichnung als Schaetzung. Ebenso Parametergroesse aus Namen (Regex kann Versionszahlen wie `qwen3.5-9b` richtig, MoE-Namen `26b-a4b` wahrscheinlich falsch treffen – nicht getestet).
- Beleg: gelesen; UI zeigt `SizeGb` (`ModelManagerViewModel.cs`: 4 Treffer).
- Auswirkung: Anzeige kann um Faktor falsch sein; verstoesst gegen die Honest-Regel der Projektleitlinien (nicht belegte Zahl als Wert).
- Empfehlung: Feld `size_estimated: bool` oder bei 0 leer lassen.
- Aufwand: S · Risiko: niedrig (OpenAPI-Snapshot + C#-Record)

### Z03-013 · MITTEL · Stabilitaet · `POST /models/provider`: Reihenfolge und TOCTOU
- Ort: `models_router.py:544-595`
- Was: `_require_idle_vision_runtime` laeuft **vor** dem Lock (Check-then-act); danach werden beide Runtimes entladen (`548`) **bevor** die Config geschrieben wird (`570`). Schlaegt die Config-/Reset-Phase fehl (502), sind die Modelle bereits entladen, Provider unveraendert. `httpx.ConnectError` in `_unload_provider_models` liefert `[]` (Provider offline = "erfolgreich entladen"), jeder andere Fehler → 502.
- Beleg: gelesen.
- Auswirkung: Randfall; UI-Zustand "Standby" nicht garantiert.
- Empfehlung: Lease-Check unter dem Lock wiederholen, Config zuerst schreiben.
- Aufwand: S · Risiko: mittel

### Z03-014 · NIEDRIG · Testnutzung · Helfer nur durch Tests benutzt (Indirektionen)
- Ort: `video_router.py:1155-1168` (`_extract_thumbstrip`), `1202-1205` (`_extract_clip_peaks`)
- Beleg: Produktiver Aufruf in `get_thumbstrip` (1129)/`get_clipwave` (1191); Docstrings "Indirection so tests can monkeypatch" (`Tests/test_video_thumbstrip_endpoint.py:31,62`, `test_video_clipwave_endpoint.py:26,55`).
- Empfehlung: Beibehalten oder durch Dependency-Injection ersetzen; kein Loeschkandidat.
- Aufwand: S · Risiko: niedrig

### Z03-015 · NIEDRIG · Stil · Veraltete Kommentare, doppelte Imports, Magic Numbers
- Ort: `video_router.py:1-11` (Docstring listet nur 6 von 12 Routen: fehlen `thumbstrip`, `clipwave`, `DELETE /clips`, `DELETE /clips/{id}`); `1325-1326` verweist auf nicht existierendes `_run_video_analysis` (auch `moondream_wrapper.py:5`, `video_schemas.py:62`, `video_embedder.py:10`); `1791` lokales `import json` ueberdeckt Modulimport (Zeile 15), `1849` `from ..config import config` doppelt zu Zeile 34; `2464` `import gc; gc.collect()` einzeilig; Magic Numbers `360` (Resize-Hoehe 2209), `1e-3` (2386), `(160, 90)`, `n`-Klammern `1..32`/`1..2048`, Frame-Quartile `total//4,//2,*3//4` (2588) – die Captioning-Stichprobe weicht damit von der Embedding-/Motion-Stichprobe ab (`_representative_frame_indices`), bewusst oder nicht: UNBEKANNT.
- Empfehlung: Docstrings/Kommentare nachziehen, Konstanten benennen.
- Aufwand: S · Risiko: niedrig

### Z03-016 · MITTEL · Wartbarkeit · God-Funktionen
- Ort: `_run_color_and_caption_analysis` `video_router.py:2550-3046` (~497 Zeilen, Verschachtelung bis 6), `_analyze_video_in_project` `1300-1702` (~403), `_run_video_gpu_analysis` `2139-2448` (~310), `list_clips` `931-1046` (~115, 9 try/except-Float-Casts)
- Was: Statuszustandsmaschine (partial/unavailable/failed/completed) fuer Captions steckt in einer Funktion mit `locals().get("heartbeat_task")` (3013, 3022) als Variablen-Existenz-Test.
- Auswirkung: Fehleranfaellig (siehe Z03-001/003/005/006 – alle in diesen Funktionen).
- Empfehlung: Zerlegung in (1) `_sample_frames`, (2) `_extract_colors`, (3) `_caption_frames` (Provider), (4) `_derive_caption_status`; `list_clips` Float-Casts in `_as_float()`.
- Aufwand: L · Risiko: mittel

### Z03-017 · NIEDRIG · Stabilitaet · Verschluckte Ausnahmen
- Ort: `video_router.py:869-870` (`except Exception: pass` in `_hash_progress`), `1641-1643`, `2241-2242` (`except Exception: pass` in `_motion_progress`), `2879-2880`, `2982-2983` (llm_status-Publish), `2465-2466` (Moondream-Inferenzfehler → leere Liste, `warning`).
- Beleg: gelesen. Bewusst fuer kosmetische SSE; `run_coroutine_threadsafe`-Future-Ergebnis wird nie geprueft, Fehler im Publish gehen ganz verloren.
- Empfehlung: `logger.debug` statt `pass`.
- Aufwand: S · Risiko: niedrig

### Z03-018 · NIEDRIG · Stale-Rest ausserhalb der Zone (nur Hinweis)
- Ort: `PBStudio.UI/Services/ApiClient.cs:809-816` behandelt HTTP 501 beim Pull ("LM Studio managed Downloads"); `backend/routers/*.py` enthaelt keinen 501-Status (Grep: 0 Treffer). Zweig nicht mehr erreichbar. Ebenso `ModelManagerViewModel.cs:19` "Ollama Vision-Modelle" als Klassenkommentar.
- Empfehlung: bei Refactoring Zone C#-Services mitnehmen.

## Refactoring-Kandidaten (priorisiert)
1. Z03-004: Frame-/KMeans-Strecke und `list_clips`-DB-Reads aus dem Event-Loop nehmen (Stabilitaet, kleiner Umfang).
2. Z03-005/006: Status-Semantik (`skipped`, Teil-Coverage) – erst Produktentscheid, dann Tests anpassen.
3. Z03-002 + Z03-003 + Z03-001: Moondream-Fallback entscheiden/entfernen, tote Zweige weg (~250 Zeilen).
4. Z03-016 + Z03-007: `_run_color_and_caption_analysis` zerlegen, Tag-Merge nach `src/pb_studio/video/tag_merge.py` (Router duenn).
5. Z03-011/-012/-013/-015: `models_router` bereinigen (Helper, Kuratierliste, Provider-Switch-Reihenfolge, Docstrings).
6. Z03-008: gemeinsames `media_probe`-Modul – nur nach separater Zone-Abstimmung (Cross-Zone).

## Nicht geprueft / Unsicherheiten
- Nicht ausgefuehrt: kein Test, kein Backend; Aussagen zur Laufzeit sind aus Code abgeleitet. Z03-003 (Farbfeature-Block tot) ist Schluss aus dem Code von `compute_color_features`-Nutzung, `moondream_wrapper.py` selbst wurde nicht gelesen.
- `AppState.project_commit`/`project_operation` Threadsicherheit nicht geprueft (relevant fuer Z03-004).
- `ModelInventoryService`, `ModelRegistry`, `llm_provider`, `lmstudio_vision_wrapper` (ausser gezielter Greps) liegen in anderen Zonen; Aussagen dazu nur soweit zitiert.
- Ob Vorgaenge in Z03-005 im Mehrpass-Betrieb der WPF real zu falschem `is_analyzed` fuehren: nicht live verifiziert.
- Semantische Gleichheit der Duplikate in Z03-008 nicht verglichen.
- OpenAPI-Snapshot und `ApiTypes.g.cs` nicht auf Feldabdeckung der `ModelListEntry`-Felder geprueft; Hinweis: `SizeMb`, `SizeBytes`, `Family`, `Publisher`, `RuntimeState`, `InventorySources`, `VerifiedAt`, `DiscoverUrl` haben in ViewModel/XAML (Grep) keine Leser – nur Konstruktor-/DTO-Felder, Entfernen waere ein OpenAPI-/C#-Record-Change (Producer ohne UI-Consumer, Konsumenten ausserhalb ViewModel/Views/Services nicht geprueft).
