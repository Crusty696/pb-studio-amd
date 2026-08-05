# Reparaturstrategie — PB Studio — 2026-08-05

**Grundlage:** `docs/LOG_AUDIT_2026-08-05.md` (Log-Audit) + 6-Slice-Datenfluss-Audit
(Audio · Video · Pacing/Render · Chat/Modelle/Settings/Terminal/GPU · SSE/Brain · Schema-Parität).

**Diese Strategie ist nicht generisch.** Sie ist an den Regeln dieses Projekts ausgerichtet:

| Regel | Konsequenz für die Reihenfolge |
|---|---|
| **IR-10 (100 % Ehrlichkeit)** | Diagnose-Kanäle zuerst. Solange 403-Gründe verworfen und Fehlerstrings leer geloggt werden, ist **jede** spätere Erfolgsmeldung unbelegbar. |
| **IR-13 (Verify-before-Change)** | Jeder Fix unten trägt ein **Verifikat** — ein konkretes Kommando mit erwartetem Ergebnis. Kein Fix gilt als erledigt ohne grünes Verifikat. |
| **IR-9 (Autonomes Deployment)** | C#-Änderung → `dotnet build -c Release`. Schema-Änderung → NSwag-Regen + `openapi.snapshot.json`. Script → `script-validator`. |
| **Minimalprinzip** | Tote Felder werden **gelöscht**, nicht nachträglich mit Producern beglückt — außer das Feature ist erkennbar gewollt (Semantik-Achse, Stem-Regler). |
| **IR-1/2 (DirectML)** | Kein Fix darf einen CPU-Fallback einführen. Fehlende Assets bleiben ehrlich `unavailable`. |
| **IR-3 (NumPy < 2.0)** | Kein Fix fasst gepinnte Versionen an, außer madmom (T4, explizit entschieden). |

---

## Leitprinzip der Reihenfolge

> **Erst sehen können. Dann entsperren. Dann Lügen abstellen. Dann Leitungen legen. Dann aufräumen.**

Der Grund ist konkret: drei unabhängige Auditoren sind über dieselbe Wand gestolpert —
`ApiClient.PostAsync<T>` verwirft jeden `detail`-Body, `model_registry` loggt `error=` leer,
`render_router.py:746` wirft 403 ohne Logzeile. Jede Reparatur, die wir vor diesen drei
Ein-Zeilen-Fixes machen, verifizieren wir blind.

---

## T0 — Diagnosefähigkeit (Voraussetzung für alles Weitere)

Ohne T0 können wir T1–T4 nicht ehrlich verifizieren. Alles hier ist klein und risikoarm.

| # | Fix | Datei | Verifikat |
|---|---|---|---|
| T0.1 | `PostAsync<T>` liest `detail` aus dem 4xx-Body und reicht ihn an den Aufrufer | `PBStudio.UI/Services/ApiClient.cs:803-826` | Render mit Pfad außerhalb Projekt → UI zeigt „Output-Pfad außerhalb…" statt „konnte nicht gestartet werden" |
| T0.2 | 403 im Render-Gate loggen (`output_path` + `allowed_render`) | `backend/routers/render_router.py:746` | Log enthält die Zeile beim 403 |
| T0.3 | Failover-Fehler nicht leer loggen: `%r` + `type(exc).__name__` + Response-Body | `src/pb_studio/ai/model_registry.py:758-765, 776` | Log zeigt echten LM-Studio-Fehlertext statt `error=` |
| T0.4 | **Datum in den Log-Zeitstempel** + Rotation | Backend-Logging-Setup | `logs/backend.log` beginnt Zeilen mit `YYYY-MM-DD HH:MM:SS` |
| T0.5 | `persist_error` in Filter + WPF-Handler + Toast | `events_router.py:96`, `SSEClient.cs`, `MainViewModel` | Schreibfehler simulieren → UI zeigt Fehler |
| T0.6 | `llm_status`-Status `unavailable` eigener Zweig statt „Bereit"; `idle` nach Turn-Ende | `MainViewModel.cs:169-188`, `chat_agent.py:835` | Moondream-Caption anstoßen → Statusbalken sagt „nicht verfügbar" |

**Warum zuerst:** T0.1 allein macht **jedes** 4xx der gesamten App zum ersten Mal erklärbar —
nicht nur Render, sondern auch Chat, Modelle, Projekt.

---

## T1 — Blocker entsperren (User kann wieder arbeiten)

| # | Fix | Datei | Verifikat |
|---|---|---|---|
| T1.1 | `BrowseOutput` mit `initialDirectory = projectRoot`; Client-Validierung vor dem Request; `OutputPath` beim Projektöffnen vorbelegen | `ProductionViewModel.cs:84-94`, `DialogService.cs:53` | Render startet aus der UI heraus erfolgreich |
| T1.2 | Owner-Capability-Vorabprüfung streichen (Handler prüft ohnehin fail-closed unter Lease) | `ApiClient.cs:1027-1034` | `/models/test` 10× hintereinander → 0 Blockaden |
| T1.3 | Watchdog im Attach-Modus: nicht abbrechen, sondern mit Backoff weiter revalidieren; Log **vor** das `break` | `PythonBridgeService.cs:362-372` | Backend kurz killen und neu starten → UI erholt sich ohne Neustart |
| T1.4 | Startup-Race: Erst-Requests an `BackendReadyMessage` koppeln oder einmaliger Retry | MainWindow/ViewModel-Init | `GET /project/info` scheitert beim Start nicht mehr |

---

## T2 — Falsche Daten abstellen (die App belügt sich selbst)

Diese Fixes sind wichtiger als neue Features: sie verhindern, dass wir auf falscher Grundlage weiterbauen.

| # | Fix | Datei | Verifikat |
|---|---|---|---|
| T2.1 | **`vlm` nicht bedingungslos auf chat+vision mappen.** Denylist gegen `arch=audiocpp` / ID-Token `audio.cpp`, `stable-audio`, `vevo`; Namens-Heuristik als Konjunktion statt Ersetzung | `lmstudio_client.py:575-580`, `model_registry.py:265-277` | `/models/list` zeigt für die zwei audio-GGUFs **keine** Vision-Capability |
| T2.2 | **`family = raw.get("type")` ist ein Verwechsler** — `type` ist `llm`/`vlm`, die Architektur steht in `arch`. Trennen. | `lmstudio_client.py:465-486` | `family` enthält `qwen35`/`granitehybrid`, nicht `llm` |
| T2.3 | `usable` erst nach bewiesener Ladbarkeit; Modelle mit `Engine protocol runtime … exited` für die Session sperren (session-weite Blacklist statt call-lokal) | `model_inventory.py:368`, `model_registry.py:724` | Zweiter Tagging-Lauf probiert die toten Modelle **nicht** erneut |
| T2.4 | **Band-Key-Drift**: `SpectralAnalyzer` liefert `sub_bass…air`, `pacing_service` liest `low/mid/high`. Aggregat-Keys `low = sub_bass+bass`, `high = presence+brilliance+air` additiv ergänzen | `spectral_analyzer.py:25-34`, `pacing_service.py:343-376` | `_pre_cached_bass_curve` und `_high_curve` sind nach einem Analyse-Lauf **nicht leer** |
| T2.5 | `feature_adapter` prüft `if values is None` gegen einen Wert, der `[]` ist → Fallback greift nie. Auf `if not values` ändern **und** `motion_curve` aus den Migrations-Defaults nehmen | `feature_adapter.py:152-154`, `media_json_schema.py:133` | Brain sieht nicht-leere Motion-Curves |
| T2.6 | `avg_brightness/saturation/color_temp` für 782 Legacy-Rows aus vorhandenen `dominant_colors` backfillen (reine Berechnung, keine Neuanalyse) | Skript + `compute_color_features` | Feldpräsenz 1359/1359 statt 577/1359 |
| T2.7 | Provider-Label nicht hardcoden | `chat_agent.py:47`, `llm_narrator.py:52` | Ollama-Antwort zeigt „Ollama" |

---

## T3 — Leitungen legen (das eigentliche „Daten werden nicht weitergeleitet")

| # | Fix | Datei | Verifikat |
|---|---|---|---|
| T3.1 | **WPF sendet 3 TriggerSettings-Felder nie.** `ClipLengthVariation`, `MaxCutInterval`, `BeatTriggerMode` im Konstruktoraufruf ergänzen + ObservableProperties + XAML | `DirectorViewModel.cs:308-319`, `DirectorView.xaml` | HTTP-Body enthält alle 13 Felder |
| T3.2 | XAML-Regler für `SnareWeight`, `HihatWeight`, `MinClipLength`, `MaxClipLength` (Engine liest sie bereits) | `DirectorView.xaml:210-309` | Regler bewegen → andere Cut-Liste |
| T3.3 | **EmbeddingCache-Dual-Write für Video** + **Backfill aus den 898 FAISS-Vektoren** (kein Reanalysieren) | `video_router.py:231-247` + Skript | `media_embedding_index` > 0 |
| T3.4 | **CLAP-Audio-Producer** in `/audio/analyze` einhängen, Ergebnis unter `clap_audio@onnx-dml-v1` in denselben Cache | `audio_router.py`, `clap_wrapper.py:228` | `semantic_match_weight` erscheint in `brain_scores_json` |
| T3.5 | **`projector_trainer` hat null Aufrufer** — periodischen `run_fit_step` nach N Feedbacks schedulen | `brain_router.py` | Projector-Weights werden geschrieben |
| T3.6 | VRAM-Limit persistieren (aktuell nur in-memory + `settings.json`, `config.json` bleibt 0) | `SettingsViewModel.cs`, neuer Config-Endpoint | Slider auf 8192 → Backend-Neustart → `/health/vram` zeigt 8192 |
| T3.7 | LHM-Sensoren vollständig durchreichen (aktuell 4 von ~20) | `system_monitor.py:454-482`, `events_router.py:145` | `/events/gpu` liefert Takt, Leistung, Lüfter, Hot-Spot |
| T3.8 | Chat-Verlauf persistieren + an `current_project` binden (heute Prozess-Singleton mit Cross-Project-Leak) | `chat_router.py:40-106` | Verlauf überlebt Backend-Neustart, kein Leak über Projektgrenze |
| T3.9 | Kontextfenster + `arch` bis in die Modell-Karte durchreichen | `lmstudio_client` → `model_inventory` → `models_router` → WPF | Karte zeigt „Kontext: 262 144" |
| T3.10 | `ModelSelectionReceipt` in Response + UI-Detail + Persistenz | `models_router.py`, `ChatViewModel.cs` | Receipt pro Antwort aufklappbar |
| T3.11 | `SelectedClip.metadata` nicht verwerfen (heute doppelt berechnet → 7,3 s Overhead) | `pacing_service.py:851, 1185` | Brain-Overhead sinkt messbar |
| T3.12 | Clip-Dauern aus DB-Snapshot statt 571 ffprobe-Subprozesse | `pacing_service.py:108-134` | Pacing-Lauf < 20 s statt 71 s |
| T3.13 | SSE mit `id:` + `Last-Event-ID` + Ring-Puffer (heute stiller Verlust bei Reconnect) | `events_router.py`, `SSEClient.cs` | Reconnect während Analyse verliert keinen `completed` |

---

### T3b — Der letzte Meter (Schema-Paritäts-Slice)

Zwei unabhängige Auditoren haben dasselbe gefunden — das ist kein Einzelfall, sondern eine Klasse.
Im CHANGELOG ist sie bereits **zweimal** protokolliert (BrainViewModel, Timeline-StatusText).

| # | Fix | Umfang | Verifikat |
|---|---|---|---|
| T3b.1 | **25 DTO-Felder werden deserialisiert und nie gelesen.** `VideoAnalysisResult` 9/19 (u.a. `AudioKey`, `DominantColors`, `MoodTags`, `Avg*`), `AudioAnalysisResult` 10/21 (u.a. `OnsetTimes`, `KickTimes`, `SnareTimes`, `HihatTimes`, `StructureSegments`, `TempoCurve`), `ProjectInfo` 6/8 | Mapper + Bindings | Grep `\.AudioKey\b` liefert Treffer außerhalb der Deklaration |
| T3b.2 | **22 ViewModel-Properties ohne XAML-Binding** — darunter 5 Pacing-Regler (deckungsgleich mit T3.2) und 6× `IsLoading`/`IsDeleting`/`IsCleaningGpu` (deshalb sieht der User bei laufenden Aktionen nichts) | 9 ViewModels | Binding-Guard-Test grün |
| T3b.3 | `Tags` ist required+positional im C#-Record, im Pydantic optional → `NullReferenceException`-Kandidat | `ApiClient.cs:1251-1271` | Response ohne `tags` crasht nicht |
| T3b.4 | `EmbeddingDim` Default 1152 (C#) vs. 0 (Pydantic, „0 = kein Embedding") — semantische Umkehrung | `ApiClient.cs:1280` | Defaults identisch |
| T3b.5 | `min_cut_interval` doppelt deklariert (Parent **und** Kind) — Dual-Source | `pacing_schemas.py:33` + `:67` | nur noch eine Deklaration |
| T3b.6 | **NSwag-Layer ist zu 40 % Zombie:** 33 von 83 generierten Klassen ohne Referenz; die restlichen werden durch gleichnamige Hand-Records in `ApiClient.cs:1130-1330` verdeckt. Der Drift-Test schützt Code, den niemand konsumiert — der real genutzte Pfad ist ungeschützt. | Entscheidung nötig (T4.5) | — |
| T3b.7 | Drift-Test vergleicht **nur Property-Namen** — Typwechsel, Default-Drift, required↔optional rutschen durch (genau T3b.3/T3b.4) | `test_openapi_snapshot_drift.py:75-81` | Test fängt einen künstlichen Default-Drift |

---

## T4 — Entscheidungen, die dir gehören

Diese vier fixe ich **nicht** ohne dein Wort, weil sie Verhalten oder gepinnte Versionen ändern:

| # | Frage | Optionen |
|---|---|---|
| T4.1 | **madmom** — BeatNet ist installiert, madmom fehlt in jeder requirements-Datei, Downbeats existieren deshalb nirgends | (a) madmom aufnehmen und Installierbarkeit auf 3.11 empirisch testen · (b) ehrlicher librosa-Downbeat-Fallback statt `return []` |
| T4.2 | **Stem-Timeout** — 900 s Budget vs. 2710 s reale Laufzeit; Worker ignoriert Cancel | (a) nur Budget erhöhen (nicht locked) · (b) echte Cancel-Kooperation (berührt `separator.py`, **LOCKED**) |
| T4.3 | **Anker-Tab** — hat null Backend, null Persistenz, null Wirkung auf Cuts | (a) fertigbauen (Endpoints + Persistenz + Einspeisung) · (b) entfernen |
| T4.4 | **Brain-Auto-Wipe** — hat am 29.07. 03:59 ungefragt die Lernhistorie neutralisiert, Backup liegt vor | (a) Migration owner-gaten + Toast · (b) zusätzlich alte Buckets mit halbem Gewicht übernehmen statt löschen |
| T4.5 | **NSwag-Layer** — 4450 Zeilen generierter Code, praktisch ungenutzt, aber testgeschützt; der real genutzte Hand-Record-Pfad ist ungeschützt | (a) auf NSwag committen und Hand-Records löschen · (b) NSwag auf die 2 real genutzten Klassen begrenzen und den Drift-Test auf die Hand-Records richten |
| T4.6 | **Fünf wirkungslose `config.json`-Schlüssel** — `hardware.enable_monitoring`, `ai.audio_backend`, `ai.parallel_tasks`, `ui.theme`, `ui.scale_factor`. Repo-weit ohne Leser verifiziert. Sind in `config_manager.py` jetzt als Attrappe markiert, aber nicht entfernt: Löschen ändert die nutzersichtbare Config-Oberfläche und erfordert `Tests/conftest.py` synchron | (a) aus DEFAULTS **und** conftest entfernen · (b) verdrahten, falls die Funktion gewollt ist · (c) als dokumentierte Attrappe belassen |

---

## T5 — Aufräumen (Minimalprinzip)

Erst **nach** T0–T3, weil Löschen ohne Diagnosefähigkeit riskant ist.

- 5 Video-Blob-Felder ohne Producer **und** ohne Consumer löschen: `brightness_curve`, `saturation_curve`, `color_temp_curve`, `style_tags`, `object_tags` (je 1359 present / 0 non-empty)
- 8 Audio-Schema-Felder ohne Consumer: `band_means`, `band_variances`, `events`, `frequency_ranges`, `chunk_evidence`, `beats[*].beat_type`, `subtracks[*].confidence`, `sub_bpm`/`sub_key`
- 5 tote Config-Schalter: `hardware.enable_monitoring`, `ai.audio_backend`, `ai.parallel_tasks`, `ui.theme`, `ui.scale_factor`
- `TriggerSettings.min_cut_interval` (Schatten-Duplikat zu `PacingConfig.min_cut_interval`), `max_cut_interval` (Kommentar in `pacing_models.py:93` behauptet fälschlich Nutzung)
- `ClipSelector.add_clip` ohne Aufrufer → `_get_clip_neighbors` direkt über `vector_store.metadata`
- `logs/native_crash.log` (27. Juni, alter Codestand) nach `logs/archive/`
- Chat- und Modelle-Router: 18 Inline-Pydantic-Klassen nach `backend/schemas/{chat,models}_schemas.py`

---

## Regressionsschutz (damit das nicht wiederkommt)

Die Lehre aus dem Audit: **Tests, die ihren eigenen Store befüllen, beweisen keine Verdrahtung.**
`Tests/test_brain_cross_modal.py` ist grün, während `EmbeddingCache` produktiv nie beschrieben wird.

Drei neue Guards:

1. **Feld-Verdrahtungstest** — jedes `TriggerSettings`-Feld muss (a) im WPF-Konstruktoraufruf stehen,
   (b) im OpenAPI-Schema, (c) einen Leser in der Engine haben. Fehlt eins → rot.
2. **Producer-Test statt Store-Test** — nach `/video/analyze` muss eine Zeile in `media_embedding_index`
   stehen. Der Test darf den Store **nicht** selbst befüllen.
3. **ViewModel-Binding-Test** — jede `[ObservableProperty]` braucht entweder ein XAML-Binding oder
   ein explizites `// intentionally unbound`-Attribut. Im Projekt bereits dreimal aufgetreten.

---

## Verifikationskette pro Batch (IR-9 + IR-13)

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe -m pytest Tests/ -x -q          # Backend
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release      # Frontend, Release (Launcher lädt Release!)
```
Bei Schema-Änderung zusätzlich: NSwag-Regen + `openapi.snapshot.json` aktualisieren + Drift-Test.
Bei Script-Änderung: `script-validator` bis 3× clean.

**Kein Batch gilt als fertig, bevor beide Kommandos grün sind und das jeweilige Verifikat der Tabelle erfüllt ist.**
