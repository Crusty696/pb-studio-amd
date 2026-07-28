# PB Studio Agent-Teams

Zwei Teams à 12 Domain-Spezialisten, 1:1 auf die WPF-Tabs von PB Studio gemappt. Erstellt 2026-07-10 nach `superpowers:writing-skills` (RED-GREEN-REFACTOR pro Domain, siehe "Test-Status" unten).

## Team 1: Entwickler (`dev-*`)

Implementiert Features/Fixes. Folgt CLAUDE.md IRON RULES (Minimalprinzip, VERIFY-BEFORE-CHANGE, Autonomous-Deployment). Schreibt Code.

## Team 2: Analysten (`analyst-*`)

Root-Cause-Analyse, Ursachen + Zusammenhänge finden. **Schreibt keinen Code** — liefert zitierte Diagnose (Datei:Zeile-Belege), kein Doku-Trust, kein Raten. Arbeitsweise wie `full-stack-auditor`, aber domain-fokussiert statt system-weit.

**Faustregel:** Bug/Symptom gemeldet → erst `analyst-<domain>` (Ursache klären), dann `dev-<domain>` (Fix implementieren). Neues Feature → direkt `dev-<domain>`.

## Domain-Matrix

| Tab | Skill (geteiltes Wissen) | Dev-Agent | Analyst-Agent | Kern-Dateien |
|---|---|---|---|---|
| PROJEKT | `projekt-expertise` | `dev-projekt` | `analyst-projekt` | `app_state.py`, `project_router.py`, `ProjectService.cs` |
| AUDIO | `audio-expertise` | `dev-audio` | `analyst-audio` | `audio/analyzer.py`, `beat_detector.py`, `separator.py` (LOCKED) |
| VIDEO | `video-expertise` | `dev-video` | `analyst-video` | `siglip_wrapper.py`, `lmstudio_vision_wrapper.py`, `video_router.py` |
| KI-REGIE | `pacing-expertise` | `dev-ki-regie` | `analyst-ki-regie` | `advanced_pacing_engine.py`, `clip_selector.py`, `DirectorViewModel.cs` |
| TIMELINE | `timeline-expertise` | `dev-timeline` | `analyst-timeline` | `TimelineViewModel.cs`, `timeline_models.py` |
| EXPORT | `rendering-expertise` | `dev-export` | `analyst-export` | `render_service.py`, `preview_renderer.py`, FFmpeg AMF |
| HIRN | `brain-expertise` | `dev-hirn` | `analyst-hirn` | `weight_store.py`, `cross_modal_projector.py`, `brain_router.py` |
| SETTINGS | `config-expertise` | `dev-settings` | `analyst-settings` | `config_manager.py`, `config.json` |
| PERFORMANCE | `gpu-expertise` | `dev-performance` | `analyst-performance` | `vram_arbiter.py`, `backend/dependencies.py` (echter GPU-Lock) |
| MODELLE | `model-registry-expertise` | `dev-modelle` | `analyst-modelle` | `model_registry.py`, `lmstudio_client.py` |
| CHAT | `chat-agent-expertise` | `dev-chat` | `analyst-chat` | `chat_agent.py`, `tool_registry.py` |
| TERMINAL | `terminal-expertise` | `dev-terminal` | `analyst-terminal` | `TerminalViewModel.cs` (reiner Log-Viewer, kein Command-Executor) |

## Verhältnis zu bestehenden Skills/Agents

- **`pb-master`** — System-weiter Master-Architekt für Cross-Module-Fragen, die mehrere Domains gleichzeitig betreffen. Domain-Agents sind der Zoom-in, `pb-master` der Zoom-out.
- **`full-stack-auditor`** — für System-weite Audits (Wiring/Pipelines über alle Domains). `analyst-*` ist das domain-scoped Äquivalent für einen einzelnen Tab/Bereich.
- **`run-pb-studio`** — Live-Verifikation (Backend starten, Screenshot, Health-Check). Beide Teams sollen dieses Skill für Live-Checks nutzen statt nur Code zu lesen.
- **`amd-guard`, `api-documenter`** (bestehend) — hatten beim Bau dieser Teams KEIN YAML-Frontmatter und sind daher aktuell NICHT als Subagents registriert. Nicht in diesem Zug gefixt (außerhalb Scope), aber notiert.

## Test-Status (RED-GREEN-REFACTOR pro Domain)

Alle 12 Domains wurden von parallelen Fork-Agents gebaut. Ergebnis unterschiedlich rigoros — verschachteltes Subagent-Spawning aus einem Fork heraus funktioniert technisch, wurde aber nicht von allen Forks genutzt:

- **Voller Live-RED/VERIFY** (frischer Subagent gespawnt für RED, dann die neue `analyst-<domain>`-Definition selbst als `subagent_type` für VERIFY genutzt, Diagnosequalität verglichen): TIMELINE, CHAT.
- **Live-RED + Proxy-VERIFY** (frischer Subagent für RED gespawnt; VERIFY lief über `general-purpose`, der die neue Agent-Definition als Arbeitsanweisung bekam, weil `analyst-hirn` zum Zeitpunkt des Verify-Versuchs noch nicht in der Registry propagiert war): HIRN.
- **Unbeabsichtigter Live-RED, kein VERIFY** (Fork ignorierte die vermutete Spawn-Sperre versehentlich, fand dabei einen echten Bug, aber es folgte kein systematischer Verify-Vergleich): AUDIO.
- **Nur dokumentierte Baseline-Analyse, kein Live-Spawn** (Fork ging fälschlich von einer Spawn-Sperre aus, RED-Lücken direkt aus dem Code abgeleitet statt beobachtet): PROJEKT, VIDEO, KI-REGIE, EXPORT, SETTINGS, PERFORMANCE, MODELLE, TERMINAL.

**Offener Punkt:** Die 8 rein dokumentierten Domain-Paare (PROJEKT, VIDEO, KI-REGIE, EXPORT, SETTINGS, PERFORMANCE, MODELLE, TERMINAL) sollten bei Gelegenheit mit echtem Live-RED/VERIFY nachgetestet werden (frischer `general-purpose`-Agent auf ein Szenario ansetzen, dann denselben Szenario-Agent mit `analyst-<domain>` wiederholen, Diagnosequalität vergleichen). Bis dahin gelten sie als **plausibel, aber nicht live-bulletproof-verifiziert**. TIMELINE, CHAT, HIRN, AUDIO gelten als echt getestet.

## Nebenfunde aus dem Bau-Prozess (nicht gefixt, nur dokumentiert)

- `src/pb_studio/ai/chat_agent.py:522-582`: 3-Fälle-Fehlerklassifizierung behandelt jeden nicht per Text-Match erkannten LM-Studio-Fehler als "Modell nicht geladen", churnt durch alle Modelle, meldet am Ende irreführend `NoSuitableModelError` — obwohl `lmstudio_client.py:_raise_for_status` (Zeile 361-371) für jeden HTTP≥400 dieselbe generische Exception wirft (404 vs. 400-Context-Overflow nicht unterscheidbar, da `status_code` nicht auf der Exception liegt).
- `src/pb_studio/brain/cold_start.py`: Rohwerte teils unskaliert bis 8.0 statt normiert auf [0,1] — potenzielle Fehlerquelle für Confidence-Berechnungen.

- `src/pb_studio/audio/audio_router.py`: `sub_bpm`-Feld existiert im Schema, wird aber nie befüllt (Median-BPM über gesamten Mix statt pro Sub-Track/Chunk).
- `src/pb_studio/pacing/`: `beat_trigger_mode` ("downbeat_only"/"strong_only") in Schema+Model definiert, aber nirgends in `advanced_pacing_engine.py` gelesen — tote UI-Verdrahtung.
- `pb-master`-Skill-Referenz `references/module-map.md` ist für den Rendering-Bereich veraltet (nennt `final_renderer.py`/`render_engine.py`/`proxy_service.py`, real existieren `render_service.py`/`preview_renderer.py`/`render_queue.py`).
- TERMINAL-Tab ist entgegen ursprünglicher Annahme kein Command-Executor, sondern reiner Log-Viewer (SSE `/events/log` + `ILoggerProvider`-Interception) — keine Shell-Injection-Oberfläche in dieser Domain.

---

## Sweep 2026-07-10: Vollständiger Projekt-Durchlauf (beide Teams, alle 12 Domains)

Auf User-Wunsch: alle 24 Agents parallel über das ganze Projekt, mit Tiefen-Fokus auf KI-REGIE/Pacing ("welche Daten werden wirklich verwendet und wie"). Reiner Audit — keine Code-Änderungen außer einer Selbstkorrektur (siehe HIGH-5). Alle Befunde zitiert, Datei:Zeile-Belege in den jeweiligen Agent-Reports (Session-Transkript), hier konsolidiert.

### Pacing-Datenfluss-Tabelle (Kernfrage des Users)

Live-Pfad verifiziert: `DirectorViewModel.cs` → `pacing_router.py:40 generate_cut_list` → `pacing_service.py:704` → `AdvancedPacingEngine(trigger_settings=...)` → `clip_selector.select_clip`. Die `SyncMode`/`PacingConfig`-Klasse und `plan_cuts` werden **nie** aufgerufen (bestätigt toter Zweig).

| Feature | Berechnet in | Gelesen in Pacing | Beeinflusst Cut-Liste | Anmerkung |
|---|---|---|---|---|
| Beat-Zeitstempel | BeatDetector | `advanced_pacing_engine.py:1041` | **JA (primär)** | Dominanter Cut-Treiber |
| Per-Beat-Strength | BeatDetector | `:1814-1831` | **JA** | Nur wenn `strength` vorhanden |
| Downbeats | BeatDetector | `:1825` | **JA, meist leer** | `_inject` setzt i.d.R. keine Downbeats |
| BPM/Tempo | audio_router | `:1107-1109` | **INDIREKT/schwach** | Nicht für Cut-Platzierung, nur Dauer-Schätzung + Kapitel |
| Energy-Kurve | SpectralAnalyzer | `clip_selector.energy_curve` | **INDIREKT** | Als Trigger im Cache-Pfad TOT (s. HIGH-1), wirkt nur über Drop/Break-Boni |
| Spektral-Bands (bass) | SpectralAnalyzer | `_apply_structure_weights:1417` | **JA** | Drop-Boost |
| Spektral-Bands (mid/high) | SpectralAnalyzer | `_mid/_high_weight_at_time` | **NEIN — tot** | Helper existiert, nie aufgerufen |
| Song-Struktur-Segmente | StructureAnalyzer | `:1579-1580,1356` | **JA, nur wenn `use_structure_awareness=True`** | |
| `beat_trigger_mode` | Schema/Model | — | **NEIN — tot** | 0 Treffer in Engine |
| `onset_sensitivity` | Schema/Model | — | **NEIN — tot** | 0 Treffer |
| `max_cut_interval` | Schema/Model | — | **NEIN — tot** | 0 Treffer, `max_clip_length` wird stattdessen genutzt |
| SigLIP-Video-Embeddings (1152-dim) | video_router → FAISS | `clip_selector.py:741` | **JA, nur bei `use_semantic_matching=True`** | Text-Query-Suche, nicht Video-Vergleich |
| RAFT-Motion-Scores | video_router | `clip_selector.py:631,638` | **JA, nur bei `use_motion_matching=True`** | |
| LM-Studio-Vision-Tags | video_router | `clip_selector.py:669` (`belongs_to_theme`) | **JA, nur bei aktivem Theme** | +1000-Score-Bonus |
| Scene-Detection-Grenzen | video_router | — | **NEIN — tot** | Geschrieben, nirgends gelesen |
| Dominant-Colors | video_router | — | **NEIN — tot** | Nur in totem `SemanticMatcher` referenziert |
| Key/Tonart | KeyDetector | `clip_selector.py:692-699` | **JA, nur bei `use_key_matching=True`** | |
| Subtrack-Segmente | SubtrackDetector | `:1173` (Snap) | **JA** | |
| `tempo_curve` (Subtrack) | SubtrackDetector | `_tempo_at_time` | **NEIN — tot** | Nie aufgerufen |
| Brain-Suggest/Reranker | Brain-Modul | `pacing_service.py:799` + `pacing_router.py:113` | **JA, nur bei `use_brain=True`** | Zwei echte Touchpoints |
| Manuelle Canvas-Anchors | Obsidian `.canvas` | — | **NEIN — unerreichbar** | `PacingConfigSchema` hat kein `canvas_path`-Feld |
| Anchor-Manager (JSON) | `anchor_manager.py` | — | **NEIN — nicht angebunden** | Nur von Tests/Legacy-UI genutzt |

### Priorisierte Findings (alle 12 Domains, HIGH zuerst)

**HIGH**

1. ✅ **GEFIXT (2026-07-10):** ~~Pacing: `SessionManager`-Import existiert nicht im Repo.~~ `advanced_pacing_engine.py:1022` importierte ein nie existierendes Modul, ImportError wurde verschluckt, Onset/Kick/Snare/HiHat/Energy-Trigger waren im Normalfall tot. Fix: Audio-Pipeline (`audio_router.py`) berechnet+cacht diese Trigger-Kandidaten jetzt bei `/audio/analyze`, injiziert via `pacing_service.py`, toter Import entfernt, Audio-Load-Gate granular pro Trigger-Typ korrigiert. Details: [[project_onset_caching_fix]] / Memory. pytest 749/761 grün.
2. ⬇️ **DOWNGRADE nach Verifikation (2026-07-10, HIGH→LOW):** ~~Pacing: `beat_trigger_mode`, `onset_sensitivity`, `max_cut_interval` sind tote UI-Felder~~ — verifiziert: keins der 3 Felder ist an ein sichtbares WPF-UI-Element gebunden (`grep` über `PBStudio.UI/Views/`: 0 Treffer für alle 3; `DirectorViewModel.cs` setzt nur `OnsetSensitivity` als Request-Property, aber ohne XAML-Slider dahinter). `max_cut_interval` ist zudem funktional redundant zu `max_clip_length` (bereits korrekt verdrahtet, macht exakt dasselbe über `_enforce_clip_lengths`). Kein User-Impact aktuell, da niemand diese Werte je ändern kann — kein Fix vorgenommen (waere Scope-Creep: neue Funktionalitaet fuer Felder ohne UI-Zugang erfinden). Kandidat fuer spaeteres Cleanup (Felder entfernen) statt Wiring.
3. **Pacing: `SemanticMatcher`, `MoodGenerator`, `MotionPreferenceCalculator`, `AnchorManager` sind im Live-Pfad komplett tot.** Nur in Tests/Legacy-UI referenziert. Der reale `ClipSelector` hat eine eigene, einfachere Parallel-Implementierung — zwei divergente "Regie-Intelligenzen" im Code, nur eine läuft.
4. ✅ **GEFIXT (2026-07-10):** ~~GPU-Lock-Bypass~~: `clip_selector.py:782` ruft `SmartDirector.encode_text()` auf, die intern nur ein privates Instanz-`threading.Lock()` hielt — nicht das geteilte `pb_studio.core.gpu_lock.gpu_inference_lock`, das siglip_wrapper.py/raft.py/moondream.py/clap_wrapper.py/separator.py alle nutzen. Konnte parallel zu z.B. RAFT-Motion-Analyse auf der GPU laufen (OOM-Risiko). Fix: `SmartDirector._inference_lock` auf das geteilte Lock umgestellt (`smart_director.py` __init__). pytest 749/761 grün, kein C#-Rebuild noetig (reiner Python-Fix).
5. **Selbstkorrektur CrossModalProjector:** der in dieser Session zuvor gemachte Fix (`DEFAULT_VIDEO_DIM` 768→1152) war falsch — verwechselte `siglip_wrapper.py` (1152-dim, nur FAISS-Suche) mit dem tatsächlichen Brain-Feeder `video_embedder.py` (768-dim, `google/siglip2-base-patch16-384`). Zurückgesetzt auf 768, Tests grün (34 passed).
6. ✅ **VERIFIZIERT, KEIN LIVE-BUG (2026-07-10):** ~~Zwei parallele Audio-Analyse-Pfade~~ — `AudioAnalyzer`-Klasse (`analyzer.py`) wird nur von `SmartDirector.analyze_audio()` genutzt, dessen einziger Aufrufer `generation_service.py:88` ist. `generation_service.py`, `analysis_service.py`, `video/engine.py`, `audio_analyze_worker.py`, `workers/orchestrator.py` haben **0 Referenzen im laufenden FastAPI-Backend** (grep bestätigt) — PyQt6-Aera-Legacy-Code, gleiches Muster wie die bereits von der EXPORT-Analyse gefundenen toten `orchestrator.py`/`generation_service.py`-Pfade. Nur der `audio_router.py`-Inline-Pfad läuft live. Kein Fix nötig — Finding war eine Fehleinschätzung des ersten Sweep-Durchlaufs (Static-Grep ohne Reachability-Check).
7. ✅ **GEFIXT (2026-07-10):** ~~chat_agent.py: 8 von 9 `process_message`-Exit-Pfaden publizieren nie einen finalen `llm_status`~~ — WPF-Statuswidget blieb bei "loading" hängen. Fix: kompletter `for turn`-Loop-Body in `try/finally` gewrappt, `finally` publiziert garantiert genau einmal einen Terminal-Status (kein `yield` im `finally`, nur der reine Funktionsaufruf — Generator-sicher). Plus: `LMStudioResponseError` bekam `status_code`-Attribut, neuer Fall 1c in `chat_agent.py` behandelt HTTP-400 (Context-Overflow) ehrlich statt Modell-Churn. pytest 749/761 grün.
8. ✅ **GEFIXT (2026-07-10):** ~~AMF-Encoder-Cache wird nie invalidiert~~ — `check_amf_available()`/`check_av1_amf_available()` (`encoder_utils.py`) und `RenderService._working_encoder` (`render_service.py`) hatten TTL-losen Prozess-Lifetime-Cache. Fix: 10-Minuten-TTL statt neuem UI/Endpoint (einfachster Fix ohne neue Oberfläche) — Treiber-Update/GPU-Handoff wird jetzt automatisch innerhalb von 10min erkannt.
9. **Video-Pacing-Datenverlust (teilweise gefixt):** `scene_changes`, `has_embedding` werden weiter geschrieben, nirgends in Pacing gelesen (offen, gehört zu Finding 3). `dominant_colors` wird jetzt aktiv genutzt (s. Finding 10) — nicht mehr komplett tot. `_tags_overlap_score`/`_color_similarity_score` in `semantic_matcher.py` weiterhin toter Code (gehört zu Finding 3).
10. ✅ **GEFIXT (2026-07-10):** ~~Brain: 2 von 17 Bridge-Achsen strukturell tot~~ — `mood_match_weight`/`color_temp_match_weight` fielen immer auf Cold-Start-Default zurück, weil kein Producer `mood_tags`/`avg_color_temp` befüllte. Wichtig: LM-Studio-Vision-Tags sind freies Deutsch und können nicht gegen das feste englische Audio-Mood-Vokabular (`_audio_mood_score`: dark/cold/cool/moody/uplifting/warm/happy/energetic) matchen — daher NICHT von Vision-Tags abgeleitet. Fix: neue `compute_color_features()` (`moondream_wrapper.py`) leitet `avg_brightness`/`avg_saturation`/`avg_color_temp`/`mood_tags` deterministisch aus den bereits berechneten `dominant_colors` (HSV-Analyse) ab, im selben Vokabular wie Audio. Verdrahtet durch `video_router.py`→`app_state.update_video_analysis()`→Restore-Block→`VideoAnalysisResult`-Schema (das diese Felder in einem früheren Fix L-VIDEO-4 fälschlich als "kein Konsument" entfernt hatte — Konsument war der interne Cache-Dict, nicht das API-Schema). pytest 210 grün (video/brain-Subset), Release-Build 0 Fehler.
11. ✅ **GEFIXT (2026-07-10):** ~~BrainViewModel reagiert nicht auf Projekt-Wechsel~~ — `BrainViewModel.cs` implementierte `IDisposable`+`UnregisterAll`, aber registrierte nie `Register<...>` im Konstruktor (toter Cleanup-Pfad). Fix: `ProjectOpenedMessage` → `RefreshStatsAsync()`, `ProjectClosedMessage` → neue `ResetForProjectClose()` (leert alle Collections/Counts, Status="Kein Projekt geladen."). Muster von `TimelineViewModel` übernommen. Release-Build 0 Fehler.
12. 🟡 **TEILWEISE GEFIXT (2026-07-10):** Timeline/Director-Sync-Bruch — Director-Tab und Timeline-Tab führen weiterhin zwei unabhängige `TimelineEntryModel`-Collections aus zwei getrennten Requests (strukturelle Unification wäre riskanterer Eingriff, nicht vorgenommen). ABER die zweite Hälfte des Findings ("ohne Fehleranzeige") war der eigentlich fixbare Teil: `TimelineViewModel.StatusText` wurde bei Refresh-Fehlern korrekt auf "Timeline laden fehlgeschlagen" gesetzt, war aber an **kein einziges XAML-Element gebunden** — der Fehler war für den User komplett unsichtbar, Timeline zeigte lautlos veraltete/leere Daten. Fix: neuer `StatusTextToBrushConverter` (rot bei "fehlgeschlagen"/"fehler", sonst gedimmt) + `TextBlock` in `TimelineView.xaml` Toolbar gebunden an `StatusText`. Release-Build 0 Fehler, Live-Smoke mit Screenshot bestätigt sauberen Start.
13. ⚠️ **PRÄZISIERT (2026-07-10) — User-Action, kein Code-Fix:** MODELLE/SETTINGS-Finding war ungenauer als gedacht: LM Studio läuft, antwortet aber mit **HTTP 401 `invalid_api_key`** — verlangt jetzt zwingend einen API-Token. `lmstudio_client.py` unterstützt aktuell **keinerlei** Authentication (kein `Authorization`-Header irgendwo im Code) — nicht nur ein Modell-Set-Mismatch, jeder LM-Studio-Call schlägt fehl, `provider="auto"` fällt deshalb komplett auf Ollama zurück (dessen Modell-Set fast keine Überschneidung mit den LM-Studio-Preferenzlisten hat). User-Entscheidung: LM-Studio-Server-Auth selbst deaktivieren (Settings → Developer → "Require API Token" aus), kein Code-Fix noetig. Falls das Verhalten wiederkehrt: Code-Support fuer `Authorization: Bearer`-Header in `lmstudio_client.py` waere der Fix (Token via config.json/Env-Var, NIEMALS im Code committen).
14. ✅ **GEFIXT (2026-07-10):** ~~SETTINGS: FFmpeg-Pfad-Einstellung ist komplett tot~~ — `SettingsViewModel.cs:332` setzt Env-Var `PBSTUDIO_FFMPEG_PATH`, kein Python-Reader existierte. Fix: `_get_ffmpeg_path()` (`encoder_utils.py`) prüft die Env-Var jetzt zuerst (analog `PBSTUDIO_PYTHON_EXE`-Muster), vor ConfigManager/PATH/Fallback. `_get_ffprobe_path()` leitet davon ab, kein separater Fix nötig. Bereits seit 2026-05-07/05-11 in Alt-Audits dokumentiert.

**MEDIUM**

- PROJEKT: `audio_count`/`video_count` im `current_project`-Meta-Feld drifted kurzzeitig gegen `/project/info` (Anzeige-Inkonsistenz direkt nach Open, keine Datenkorruption).
- Path-Traversal-Schutz nur an Schreibzielen (`project_router.py`, `render_router.py`), nicht an Import-Quellen (`audio_router.py:71`, `video_router.py:58`) — architektonisch gewollt (freie Quellwahl), aber asymmetrisch zur ursprünglichen Doku-Erwartung.
- AUDIO: `sub_bpm` beidseitig tot (Backend befüllt nie, kein ViewModel liest es).
- Timeline: A1-Waveform nutzt nur 1 von 3 berechneten Bändern (`bands:1` statt `bands:3`).
- Video: `use_semantic_matching` defaultet auf `False` — SigLIP-Suche im Normalfall inaktiv.
- Brain-Reranker bekommt bei `use_brain=True` immer `motion_score=0.0`/`mood_tags=[]` für Video-Kandidaten (`brain_video_features_by_clip` nie befüllt) — Reranking video-blind.
- Pacing: kein Vollständigkeits-Check vor Generierung — fehlende Energy/Spectral/Tempo-Analyse wird lautlos ignoriert statt nachgeholt; fehlende Video-Analyse degradiert Motion-Matching auf neutralen Default.
- `canvas_path` fehlt im `PacingConfigSchema` — manuelle Storyboard-Anchors über API nicht ansteuerbar.
- TERMINAL: `uvicorn`/`fastapi`-Logger werden explizit gefiltert → unbehandelte 500er-Exceptions erscheinen NICHT im Terminal-Tab (kritischster Fehlerfall unsichtbar).
- TERMINAL: volle Dateipfade (inkl. Windows-Username) ungefiltert geloggt — PII, keine Secrets (Secret-Verdacht widerlegt).
- SETTINGS-Tab kann `provider`/`lmstudio_base_url`/`ollama_base_url`/`task_preferences` nicht bearbeiten — nur Datei-Edit.
- MODELLE-Tab zeigt die Auswahl-Begründung (`recommendation_with_reason`) nur im Fehlerfall, nicht bei Erfolg.
- SETTINGS: VRAM-Limit-Slider schreibt nur in-memory (`VRAMBudgetManager.update_max_vram()`) + clientseitige `%APPDATA%\PBStudio\settings.json` — `config.json:hardware.vram_limit_mb` wird nie aktualisiert, Wert geht bei Backend-Neustart verloren.
- SETTINGS: `task_overrides` (Model-Manager-Aktivierung) gewinnt immer vor dem KI-Modus-Slider (`default_mode`) — Slider-Änderung wirkt lautlos nicht für Tasks mit aktivem Override, keine UI-Anzeige welche Overrides aktiv sind.

**LOW**

- `pb-master`-Modul-Map veraltet für Rendering (nennt `final_renderer.py`/`render_engine.py`/`proxy_service.py`, real: `render_service.py`/`preview_renderer.py`/`render_queue.py`).
- Doku nennt "ExportView", real heißt es `ProductionView`/`ProductionViewModel`.
- TERMINAL: `MaxLogLength` kappt nur den Gesamt-Puffer, nicht einzelne sehr lange Log-Zeilen (z.B. Stack-Traces); `TextBox`-Rebind pro Log-Zeile ist ein Perf-Risiko bei Log-Bursts.
- `amd-guard.md`/`api-documenter.md` weiterhin ohne Frontmatter, nicht registriert (bereits aus Team-Build bekannt).

### Was NICHT gefunden wurde (positiv)

- Kein Fake-/Zufalls-Embedding als Signal-Ersatz mehr im Pacing (früherer `np.random`-Bug bereits behoben, verifiziert).
- PROJEKT-Lifecycle (Create/Open/Save/Close) komplett verdrahtet, kein Bruch.
- EXPORT-Kette (Trigger→FFmpeg→SSE→Disk) komplett verdrahtet, IRON RULE 4 (kein NVENC) bestätigt eingehalten (0 funktionale Treffer).
- HIRN: alle 6 REST-Endpoints voll verdrahtet bis zur UI.
- PERFORMANCE: GPU-Zugriffskette (bis auf Finding HIGH-4) korrekt, alle SessionOptions-Flags gesetzt, `/gpu/status` live mit echten AMD-Werten bestätigt.
- CHAT: Tool-Dispatch robust gegen halluzinierte Tool-Namen (sauberer Error statt Silent-Swallow).
- TERMINAL: SSE-Kette live bestätigt (echter curl-Test während laufendem Backend).
