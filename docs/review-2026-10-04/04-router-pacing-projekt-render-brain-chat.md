# Zone 04 – Router Pacing / Projekt / Render / Brain / Chat

Read-only Review, Stand HEAD `e51e798`. Nichts ausgeführt (kein pytest/Backend/Build).

## Abdeckung
| Datei | Zeilen | vollständig gelesen |
|---|---|---|
| backend/routers/pacing_router.py | 1383 | ja (1-1383) |
| backend/routers/project_router.py | 1165 | ja (1-1165) |
| backend/routers/render_router.py | 1650 | ja (1-1650) |
| backend/routers/brain_router.py | 853 | ja (1-853) |
| backend/routers/chat_router.py | 535 | ja (1-535) |
| Gegenstellen nur stichprobenartig (Grep/Teilleseblöcke): `ApiClient.cs`, `app_state.py`, `pacing_service.py`, `projector_trainer.py` | – | nein |

## Befunde

### Z04-001 · HOCH · Korrektheit / Datenverlust · Chat-Verlauf wird nach Ladefehler überschrieben
- Ort: `backend/routers/chat_router.py:92-120`, `:152-170`
- Was: `bind_project` trägt den Projektschlüssel in `_loaded_project_keys` ein (Z.97) und legt eine leere Liste an (Z.98-99) **bevor** `chat_history.json` gelesen wird. Schlägt das Lesen/Parsen fehl (Z.114: nur `logger.warning`), bleibt die Liste leer und der Key gilt als geladen. Das nächste `append` persistiert `[neuer Eintrag]` per `os.replace` über die vorhandene Datei.
- Beleg: Z.95-99 (Eintrag vor Lesen), Z.114-119 (Exception geschluckt), Z.164-170 (append → `_persist_unlocked`).
- Auswirkung: ein transienter Lesefehler (Datei gesperrt, Virenscanner, halb geschriebene Datei) löscht den gesamten Chat-Verlauf des Projekts beim nächsten Turn, ohne Fehlermeldung.
- Abhängigkeiten: `Tests/test_chat_router.py`; Wiederherstellung (`recovery_bootstrap.py:230` kennt `chat_history.json`).
- Empfehlung: Key erst nach erfolgreichem Laden als geladen markieren (bei Fehler nicht persistieren oder Datei vorher als `.corrupt` sichern).
- Aufwand: S · Risiko: niedrig

### Z04-002 · MITTEL · Korrektheit · `GET /pacing/timeline`: `source_duration`-Fallback ist toter Code
- Ort: `backend/routers/pacing_router.py:841-853`
- Was: Cut-`clip_id` hat das Format `clip_<int>` (`pacing_service.py:1604`, `:290`). `video_clips.get(clip_id)` (Dict mit int-Schlüsseln) liefert `None`; `int("clip_5")` wirft `ValueError` → `pass`. `meta["source_duration"]` wird also nie gesetzt. Es wirkt nur, weil die Engine das Feld meist selbst in die Metadaten schreibt (`pacing_service.py:270`, `:1707`).
- Beleg: Grep `f"clip_{` in pacing_service (7 Treffer); `_cap_entries_against_source` im selben File parst das Präfix korrekt (Z.1127-1130) – die beiden Stellen widersprechen sich.
- Auswirkung: manuell/aus altem `timeline.json` geladene Einträge ohne `source_duration` verlieren die Quelldauer in der UI (`TimelineViewModel.cs:713-716` liest sie für Drag-Begrenzung).
- Empfehlung: Präfix wie in `_cap_entries_against_source` strippen; Hilfsfunktion `_video_id_from_clip_id` gemeinsam nutzen (auch `render_router.py:207-212` parst dasselbe).
- Aufwand: S · Risiko: niedrig

### Z04-003 · MITTEL · Stabilität · Render-Task-Status bleibt bei Abbruch außerhalb des Workers hängen
- Ort: `backend/routers/render_router.py:1105-1134`, `:919-935`, `:1387-1401`
- Was: Wird die asyncio-Task während `_acquire_gpu_lock_or_cancel` (wait_for) oder `publish_event` abgebrochen (Projektwechsel/Close), läuft `CancelledError` aus `_run_render_task` heraus (nicht von `except Exception` gefangen). `_run_render_task_bound` setzt nur Cancel-Flag + Queue `INTERRUPTED`; `state.render_tasks[task_id]["status"]` bleibt `pending`/`running`. `_on_task_done` (Z.919) kehrt bei `cancelled()` sofort zurück. Nur der Resume-Callback `_on_resumed_done` (Z.689) behandelt den Fall.
- Auswirkung: `/render/status/{id}` meldet ewig „running“, `cancel_render` (Z.1096) liefert `cancelled: True` für nichts; `_cleanup_old_render_tasks` schützt den Eintrag nicht (Task ist done) und entfernt ihn nie, weil kein `finished_at` (→ „invalid_finished_at“ ewig). Bei `state.reset()` wird `render_tasks` ohnehin geleert (`app_state.py:710`), dann ist /status 404.
- Empfehlung: im `except CancelledError` von `_run_render_task_bound` auch `state.update_render_task(... status=cancelled/failed, finished_at=...)`; Text „vor Kontextbindung abgebrochen“ (Z.1132) ist irreführend, weil der Zweig jede Abbruchphase abdeckt.
- Aufwand: S · Risiko: mittel

### Z04-004 · MITTEL · Redundanz / Statusquellen · Dreifache Render-Statusquelle, Completed wird vor der Queue-Persistenz gemeldet
- Ort: `render_router.py:1598-1624` (Worker setzt COMPLETED), `:1203-1217` (Task setzt COMPLETED erneut), `:1166/1203` (Queue), `app_state.render_tasks`
- Was: Der Worker-Thread setzt `status=completed` im In-Memory-State (Z.1598) **bevor** `_queue_update_or_raise(COMPLETED)` (Z.1203) lief und bevor GPU-Lock freigegeben wurde. Schlägt das Queue-Update fehl (`PersistenceError`), springt der Task in `except Exception` → FAILED; zwischendurch sah ein Poller „completed“. Außerdem wird das Ergebnis-Dict dort ein zweites Mal gebaut (Z.1625-1644), die Pfadkonstruktion `output_p.parent/.render_evidence/<job_token>/<run_id>/{result,validation}.json` steht 4x (Z.1566-1572, 1608-1620, 1629-1641) obwohl `terminal_evidence()` sie bereits kapselt.
- Empfehlung: Worker gibt nur Ergebnis zurück; Statuswechsel einmalig in `_run_render_task` nach Queue-Update; Evidenzpfade aus einer Funktion.
- Aufwand: M · Risiko: mittel (Tests `test_render*`, SSE-Reihenfolge, `progress_end`-Semantik)

### Z04-005 · MITTEL · Performance / Korrektheit · Projektor-Training läuft bei JEDEM Feedback über alle Projekte
- Ort: `backend/routers/brain_router.py:272-274`, `:387-495`
- Was: Kommentar (Z.383-384) und `CLAUDE.md` sagen „alle N Feedbacks“; `_maybe_train_projector` prüft nur `total_clicks <= 0` (Z.480). Jeder angewandte Feedback-Klick startet `_fit_projector_v2`: `ProjectRepository().get_all()`, je Projekt `migrate_project_state(state.db)` (**schreibende Migration fremder Projekt-DBs**), neue SQLite-Verbindung, Training über alle `feedback_events`. Fehlende `state.db` oder `project_uuid` eines beliebigen Projekts wirft `RuntimeError` (Z.412, 421, 432) → komplettes Training „übersprungen“ (nur Warning).
- Beleg: `run_v2_fit_step` (`projector_trainer.py:176`) hat kein Intervall-Gating (Grep `interval|every` leer); Router ruft ohne Zähler.
- Auswirkung: Latenz im Feedback-Request (nach Response-relevantem Teil, aber awaited), ein einziges defektes Alt-Projekt blockiert dauerhaft das Training aller Projekte; Docstring widerspricht Verhalten.
- Empfehlung: Gating (`total % N == 0`) oder Fire-and-forget; Projekte mit fehlender `state.db` überspringen statt abbrechen.
- Aufwand: S–M · Risiko: mittel

### Z04-006 · MITTEL · Wartbarkeit · Duplizierte Fehler-Mapping-Blöcke `ProjectContext*Error → HTTPException`
- Ort: pacing_router (Z.519-522, 898-901, 1003-1006 + 2x in `generate`), project_router (844-847, 1096-1099, 1136-1139, 1162-1165, …), brain_router (144-147, 288-291, 372-375, 850-853), chat_router (nein, SSE), render_router (766-769)
- Beleg: Grep `except ProjectContext(Changed|Unavailable)Error` → backend/routers: 8+10+2+8+2 = 30 in den 5 Zonen-Dateien (Gesamt inkl. audio/video 51).
- Inkonsistenz: `ProjectContextUnavailableError` ergibt in pacing/brain/render/save **409**, in `get_anchors`/`set_anchors`/`project_info` **400**.
- Empfehlung: ein App-weiter Exception-Handler (`app.add_exception_handler`) oder Dekorator; Statuscode vereinheitlichen (Client-Verhalten in ApiClient.cs prüfen).
- Aufwand: M · Risiko: mittel (Tests asserten Statuscodes)

### Z04-007 · MITTEL · Redundanz · Zwei Wrapper für denselben Brain-Lease
- Ort: `brain_router.py:59-74` (`_acquire_project_state_lease`) vs. `backend/_brain_singleton.py:49` (`project_state_lease`/`acquire_project_state_lease`, benutzt in `pacing_router.py:658,685,739`)
- Was: zwei Zugänge zur selben Leasing-Logik, nur der Brain-Router mappt Fehler auf 409. `Tests/test_t410_project_switch_e2e.py:369-379` und `test_release_repair_brain_runtime_contracts.py:361` patchen die Router-private Funktion → Refactor-Hürde.
- Empfehlung: einen Einstieg, Fehler-Mapping zentral.
- Aufwand: M · Risiko: mittel

### Z04-008 · MITTEL · Stabilität · Persistenzpfade der Timeline redundant und mit gegensätzlicher Semantik
- Ort: `project_router.py:407-475` (`persist_timeline_for_context`), `:852-953` (`_save_project_in_context`), pacing_router `:775-782` (RAM) und `:744-759`, `:690` (state.db `timelines/timeline_cuts`)
- Was: Timeline lebt an vier Orten: RAM (`state.current_timeline`), `timeline.json`, `state.db` (Brain), `AppState`-DB-Metadaten (`has_timeline` in `project.json` + Katalog). Zwei Schreiber für `timeline.json` mit bewusst entgegengesetzter Leer-Semantik (Save löscht, Close/Wechsel lässt stehen – im Docstring selbst als „Falle“ beschrieben, Z.424-427). Nach „alle Cuts löschen → Close“ taucht die alte Timeline wieder auf. `project.json` wird in `create` (594), `_write_project_meta` und `save` (906-918, ohne `_write_project_meta`) auf drei verschiedenen Wegen geschrieben (atomar-Muster dreimal kopiert: Z.289-295, 460-472, 1122-1128, plus Snapshot-Variante 297-308).
- Auswirkung: Wartbarkeit, Divergenz zwischen `timeline.json` und `state.db` (Pacing mit `use_brain=False` deaktiviert alte DB-Timelines per `is_current=0`, `timeline.json` bleibt).
- Empfehlung: ein `ProjectFileWriter` (atomic write + optional Snapshot/Rollback) für project.json/timeline.json/anchors.json/chat_history.json; Leer-Semantik als expliziten Parameter.
- Aufwand: L · Risiko: hoch (Recovery-Journal-Besitzer „ProjectLifecycle“, `recovery_bootstrap.py:524`)

### Z04-009 · NIEDRIG · Toter Code · Unbenutzter Import + redundante lokale Re-Imports
- Ort: `project_router.py:36` `resolve_project_db_id` (Grep in Datei: nur Importzeile); `project_router.py:284` `import os` (schon Z.15); `brain_router.py:661` `import asyncio as _aio` (asyncio Z.13); `render_router.py:1416` `Path as _Path` (Path Z.18); `render_router.py:1532` `RenderService as _RenderServiceForAudio` (Z.1417 importiert bereits `RenderService`); `pacing_router.py:624` `import time as _time` (kein Top-Level-`time`).
- Aufwand: S · Risiko: niedrig

### Z04-010 · NIEDRIG · Toter Code · Totzweig in `_find_or_create_project_db_record`
- Ort: `project_router.py:199-216` mit Aufruf `:784-792`
- Was: Aufruf nur, wenn `_find_project_db_record_id(project_path)` (Z.219-225) bereits `None` lieferte, also über dieselbe `repo.get_all()`-Schleife nichts gefunden wurde. Die Suchschleife + Update-Zweig (Z.202-209) in `_find_or_create…` ist produktiv unerreichbar (zwei identische Table-Scans). Tests patchen beide Namen (6 Dateien, siehe Grep), daher Refactor nicht trivial.
- Empfehlung: zu `_create_project_db_record` reduzieren.
- Aufwand: S · Risiko: niedrig (Tests anpassen)

### Z04-011 · NIEDRIG · Redundanz · `getattr(config, …)` auf garantierten Pydantic-Feldern
- Ort: `pacing_router.py:656, 699-700, 1290, 1298-1299, 1305`
- Beleg: `pacing_schemas.py:76, 80, 86-87` definieren `use_key_matching`, `use_stem_pacing`, `use_brain`, `brain_min_confidence` mit Defaults.
- Empfehlung: direkter Attributzugriff.
- Aufwand: S

### Z04-012 · NIEDRIG · Wartbarkeit · Zu lange Funktionen
- `_generate_cut_list_for_project` (pacing 525-823, ~300 Z.), `_execute_render` (render 1404-1650, ~245), `_run_render_task` (1151-1368, ~220), `_resume_render_queue_on_startup` (555-732, ~180), `open_project` (674-834, ~160), `explain` (brain 669-853, ~185), `feedback` (150-291, ~140), `post_message._generator` (chat 323-462, ~140).
- Insbesondere `_run_pacing_generation` kopiert 25 Videoanalyse-Felder von Hand in `clip_data` (pacing 1248-1280), dabei `scene_changes` und `scenes` beide aus `va["scenes"]`, `motion_score` und `avg_motion` Doppelung (Z.1257-1261/1265,1270).

### Z04-013 · NIEDRIG · Redundanz · Zweimaliges Lesen/Duplikate in `open_project`
- Ort: `project_router.py:693` und `:775` `_read_project_meta(project_path)` zweimal (zweites Ergebnis überschreibt das erste; dazwischen kein Schreiber ausgenommen Race).
- Zusätzlich: `ProjectInfo`-Konstruktion Reopen-Pfad (721-736) und Normalpfad (793-811) fast gleich.

### Z04-014 · NIEDRIG · Redundanz · Zweimal derselbe Render-Task-Dict und Dauerberechnung
- Ort: `render_router.py:644-657` (Resume) vs `:885-901` (Start); `:635-643` vs `:833-840` (Gesamtdauer/Frames). Zwei fast identische Done-Callbacks (`_on_resumed_done` 683-717 vs `_on_task_done` 919-935), der Start-Callback behandelt `cancelled()` nicht und verschluckt Fehler mit `except Exception: pass` (Z.930-931).
- Empfehlung: `_new_render_task_record(...)` und gemeinsamer Done-Callback.

### Z04-015 · NIEDRIG · Redundanz gegenüber `src/` · Private Methoden fremder Klassen aus Routern
- Ort: `RenderService()._get_audio_duration` (pacing_router.py:966; render_router.py:1534), `RenderService._validate_timeline_clips` (render_router.py:382), `PacingService()._finalize_cut_list` (render_router.py:1060), `_history_store._count_tokens` (chat_router.py:316).
- `_cap_entries_against_source` (pacing_router.py:1102-1180) repliziert laut eigenem Docstring die Cap-Logik aus `pacing_service` (Z.374-380) – zwei Implementierungen derselben Regel. Die ffprobe-Dauer wird in zwei Routern mit je neuer `RenderService()`-Instanz ermittelt.
- Empfehlung: öffentliche Fassade in `RenderService`/`PacingService`, Cap-Logik nur einmal.

### Z04-016 · NIEDRIG · Stabilität · Kleine Leaks / Zustandsreste
- `_shutdown_cancelled_task_ids` (render_router.py:75) wird nur beim Startup geleert; `cancel_flags` werden in `close_project` für ALLE Tasks (inkl. fertiger) auf True gesetzt (`project_router.py:980-983`) und in `_cleanup_old_render_tasks` nur entfernt, wenn der Task noch in `render_tasks` stand (Z.1020-1028). Nach `state.reset()` (leert `render_tasks`, `app_state.py:710`) bleiben sie dauerhaft (unbegrenzt wachsend pro Close).
- `_pending_reset_tokens` (brain_router.py:50) wird nur bei `/reset` aufgeräumt (ok, klein).
- `_ChatHistoryStore.bind_project` setzt `_active_project_key` global bei jedem Aufruf (Z.94); nebenläufige Requests verschiedener Projekte lassen `snapshot()`/`clear()` mit `project_key=None` auf das falsche Projekt zeigen (nur `post_message` reicht Key explizit durch; `get_history`/`clear_history` ebenfalls, daher praktisch NIEDRIG).

### Z04-017 · NIEDRIG · Verschluckte / stille Fehler (Gesamtliste, Aufgabe f)
| Ort | Verhalten | Bewertung |
|---|---|---|
| chat_router.py:114 | Ladefehler Verlauf → Warning | siehe Z04-001 (gefährlich) |
| chat_router.py:253-255 | jede Exception → Bindung an `None`, `DELETE /chat/history` antwortet „cleared“ ohne Wirkung (Key None wird nicht persistiert) | irreführend |
| pacing_router.py:277 | Anker laden → Warning, Lauf ohne Anker | ok, dokumentiert |
| pacing_router.py:764-765 | `is_current=0`-Update fehlgeschlagen → nur Log (kein Degradations-Eintrag wie beim Brain-Zweig) | Geisterdaten in `/brain/suggest` möglich, MITTEL-NIEDRIG |
| pacing_router.py:1204-1205 | SSE-Progress-Fehler → debug | ok |
| project_router.py:63, 502-508, 971-975 | Announce-/Timeline-Sicherung-Fehler → Log | dokumentiert; Timeline-Sicherungsfehler beim Wechsel verliert Daten still (nur `logger.error`, kein SSE/persist_error) |
| project_router.py:386-390 | jede Exception beim Timeline-Laden → leere Timeline, `has_timeline` aus Metadaten trotzdem True | Inkonsistenz |
| render_router.py:930-931 | `except Exception: pass` | Z04-014 |
| render_router.py:725-729 | Resume-Fail → `update_status` ohne eigenen try (wirft aus der Schleife und bricht übrige Jobs ab, wenn Queue selbst fehlerhaft) | NIEDRIG |
| brain_router.py:490-495 | Training-Fehler → Warning | siehe Z04-005 |
| brain_router.py:554, 566 | `sqlite3.Error` → leer | ok |
| brain_router.py:800-832 | Narrator-Fehler → Warning, `narrative=None` | ok (Iron Rule 10 dokumentiert) |
| render_router.py:1535-1537 | ffprobe-Fehler → `audio_duration=0.0`, Overflow-Check wird übersprungen, Render läuft ungekürzt | Warning, aber fachlich relevant |

### Z04-018 · NIEDRIG · Routen ohne C#-Aufrufer (Aufgabe c)
- `GET /chat/tools` (`chat_router.py:503`): `IApiClient.cs:146` nur Kommentar, `ApiClient.cs` hat keinen Aufruf (Grep `chat/tools` in `*.cs`: nur Kommentarzeile). Nur Tests (`Tests/test_chat_router.py:57,69`) und Registry-Docstring rufen sie auf. Debug-Endpoint, bewusst.
- `GET /chat/history` (`:516`): kein C#-Aufrufer; `ChatViewModel.cs:133` ruft nur `"/chat/history"` (Zweck dort nicht verifiziert: Kontext nicht gelesen → UNBEKANNT ob GET), `ApiClient.cs:1318` nur DELETE.
- Alle anderen Routen (`/pacing/generate|timeline|preview`, `/project/create|open|save|close|info|anchors`, `/render/start|status|cancel`, `/brain/*`, `/chat/message|confirm`) haben einen ApiClient-Treffer (Zeilen in Grep belegt). Aufrufer in ViewModels wurden **nicht** einzeln verifiziert (ApiClient-Methode ≠ genutzt).
- Schema-Folge: `ToolInventoryEntry/Response`, `HistoryResponse` ohne C#-Typ (Grep `*.cs` leer).

### Z04-019 · NIEDRIG · Doppelte Konstante / Logik · Pfad- und Kontextprüfungen
- Pfadvalidierung `is_relative_to(Path(config.project_dir).resolve())` in `project_router.py:546` und `:688` identisch kopiert (SEC-001), `render_router.py:490` (Resume) ähnlich, `:795-797` gegen `context.project_root`. Keine gemeinsame Funktion.
- Atomic-write (`tmp.write_text` → `os.replace` → `finally unlink`) 5x manuell: project_router 289-295, 460-472, 1122-1142, `_restore_file_snapshot` 300-308; chat_router 133-139 (zusätzlich mit fsync, die anderen ohne → inkonsistente Dauerhaftigkeit).
- SSE-Publish-Boilerplate: `publish_log(...)` direkt vor/nach `logger.info(...)` mit derselben Aussage in pacing (531-541, 794-799), render (938-943, 1232-1239, 1313-1318), chat (360-365, 384-395, 415-420).

### Z04-020 · UNBEKANNT · Race in `TimelineUpdateBodyLimitRoute`
- `pacing_router.py:109` setzt `request._receive` (private Starlette-API). Funktion hängt an Starlette-Interna; Verhalten bei Versionsupgrade (CLAUDE.md erwähnt starlette-Lockwechsel 2026-08-30) nicht geprüft. Pfadvergleich `request.url.path != "/pacing/timeline"` (Z.58) bricht bei `root_path`/Mount.

## Hinweise zu Korrektheit, die sauber waren (damit nichts doppelt geprüft wird)
- Keine CUDA/NVENC/pynvml/ROCm-Verwendung, keine ONNX-`SessionOptions` in dieser Zone. Encoder nur über `RenderService` (`encoder_override` nur aus Enum, AV1-AMF-Probe mit 503).
- Pfadschutz Render-Ausgabe (`render_router.py:794-815`) und Identitätsprüfung (`_reject_render_output_identity`) schlüssig; Quality-Mapping (`_QUALITY_PRESETS`) deckt vier Werte; ob das `RenderRequest.quality`-Enum genau diese Schlüssel liefert, wurde nicht gegengeprüft.
- `render_status` lässt `RenderProgress(**task)` zu: Felder `queue_job_id`, `validation_path` etc. hängen am Schema `RenderProgress` (nicht gelesen) – falls das Schema kein `extra="allow"` hat, würde ein Task-Dict mit Zusatzfeld (z. B. `finished_at`, `run_id`, `error`) 500 erzeugen. UNBEKANNT, nicht geprüft (Schema-Datei außerhalb der Zone). Hinweis: `finished_at` (`render_router.py:1216`) und `validation_phase` werden in das Task-Dict geschrieben und in `RenderProgress(**task)` expandiert.

## Antworten auf die Zusatzfragen
- (a) Hilfsfunktionen ohne Aufrufer: in den fünf Dateien **keine vollständig unreferenzierte** Funktion gefunden; unbenutzt sind nur der Import `resolve_project_db_id` (Z04-009) und der Totzweig in `_find_or_create_project_db_record` (Z04-010); `_reset_render_runtime_for_startup` wird nur von `_resume_render_queue_on_startup` aufgerufen (Aufrufer im Lifespan `backend/main.py` nicht gesondert verifiziert).
- (b) Duplikate: Z04-006, -007, -015, -019.
- (c) Routen ohne C#-Aufrufer: Z04-018.
- (d) Render-Lifecycle: Z04-003, -004, -014, -016.
- (e) Persistenz: Z04-008, -013, -019.
- (f) Verschluckte Exceptions: Z04-017.

## Refactoring-Kandidaten (priorisiert)
1. Z04-001 (Datenverlust-Risiko Chat) – S, sofort.
2. Z04-003 + Z04-004: Render-Statusmaschine in einem Ort (`RenderJobLifecycle`), Worker ohne Statusschreibzugriff – M.
3. Z04-005: Projektor-Training gaten – S.
4. Z04-006 + Z04-007: zentrale Projektkontext-Fehlerbehandlung und ein Brain-Lease-Einstieg – M.
5. Z04-008/019: gemeinsamer atomarer Datei-Schreiber für Projektdateien – L (Recovery-Ownership beachten).
6. Z04-002: gemeinsame `clip_id`→`video_id`-Funktion (pacing 847, 1127; render 207) – S.
7. Z04-009/010/011/013: Kleinkram-Cleanup – S.
8. Z04-012: Aufteilen der >150-Zeilen-Funktionen, besonders `_generate_cut_list_for_project` und `_execute_render`.

## Nicht geprüft / Unsicherheiten
- Nicht gelesen: `app_state.py` (nur Zeilenstichproben 637-715, 741), `media_path_policy.py`, `schemas/*`, `render_service.py`, `render_queue.py`, `pacing_service.py` (nur Grep), `_brain_singleton.py`, `projector_trainer.py` (nur 170-240), ViewModels (nur Grep). Aussagen dazu sind Grep-Belege, kein Vollbeleg.
- Z04-003 und Z04-004 sind per Codepfad-Analyse hergeleitet, **nicht** durch Ausführung reproduziert.
- Die Behauptung „Statuscodes 400 vs 409“ (Z04-006) leitet sich aus dem Quelltext ab; Auswirkung auf den WPF-Client (`ApiClient.cs`) nicht geprüft.
- OpenAPI-Snapshot / C#-Records für Änderungen an Schemas wurden nicht verglichen (keine Schemaänderung vorgeschlagen außer Entfernen toter Chat-Antwortmodelle, die C# nicht kennt).
- `ProjectInfo`-Felder `db_project_id`, `project_uuid` (Z.793-811) – Schema nicht gelesen.
