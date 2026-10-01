# PB Studio — Vollständige Statusaufnahme

**Datum:** 2026-07-28  
**Audit-Ziel:** aktueller Dirty Worktree, nicht nur Git-HEAD  
**Branch / HEAD:** `00013-system-wide-bug-hunting-audit` / `a4b227d2f291f65c46109810fc9a3faf1bd956b8`  
**Methode:** Brain-Abgleich, sechs disjunkte Fach-Audits, statische Analyse, Volltests, Release-Build, Backend-/API-Live-Smoke, SQLite-/FAISS-Prüfung, LM-Provider-Probe, GUI-UIA/Screenshots, AMF-Funktionsprobe  
**Codeänderungen:** keine  
**Gesamturteil:** **NICHT RELEASE-READY**

## 1. Executive Summary

PB Studio startet, baut und besteht die vorhandene Testsuite vollständig. Short-Path-Basisfunktionen, SQLite/FAISS-Integrität, H.264/H.265-AMF, Backend-Health und alle zwölf WPF-Tabs sind nachweisbar vorhanden. Dieser grüne technische Sockel ist real.

Release-Freigabe ist trotzdem nicht vertretbar:

1. Aktiver Semantic-Pacing-Pfad startet CLAP auf CPU und verletzt die AMD/DirectML-Iron-Rule.
2. Große Audio-/Video-Dateien besitzen mehrere bestätigte OOM-, Full-Load- und nicht abbrechbare GPU-Pfade.
3. Brain-Deep-Hook erhält keine echten Features; `use_brain=true` allein beeinflusst Clip-Auswahl nicht.
4. Chat-Agent kann mutierende Tools ohne technische Bestätigungsschranke ausführen.
5. Projekt-/Render-Pfade können bestehende Daten oder Ausgaben bei Fehlern inkonsistent machen bzw. überschreiben.
6. WPF-Projektwechsel isoliert laufende Audio-/Pacing-Aktionen nicht vollständig.
7. MODELLE-Tab hängt live; Chat/Vision-LLM sind mit aktuellem Modellzustand nicht funktionsfähig.
8. Arbeitsbaum umfasst 208 Status-Einträge; `.completed` und `.qc-passed` fehlen bewusst. SDD/QC ist offen.

## 2. Verifikationsmatrix

| Prüfung | Ist-Ergebnis | Wertung |
|---|---:|---|
| Python-Version | 3.11.9 | PASS |
| NumPy | 1.26.4 | PASS |
| ONNX Runtime | 1.19.2; `DmlExecutionProvider` verfügbar | PASS |
| FAISS | 1.7.4 | PASS |
| PyTorch | 2.4.1+cpu | PASS, dokumentierter Demucs-CPU-Pfad |
| `pip check` | keine gebrochenen Requirements | PASS |
| Python AST | 322/322 | PASS |
| XAML XML | 19/19 | PASS |
| Pytest | 853 passed, 11 skipped, 45 warnings | PASS |
| WPF Release-Build | 0 Fehler, 0 Warnungen | PASS |
| Backend `/health` | HTTP 200, `status=ok`, `gpu_available=true` | PASS |
| OpenAPI | 57 Pfade, 61 Operationen | PASS |
| SQLite | 17 DBs: `integrity_check=ok`, 0 FK-Verstöße | PASS |
| FAISS ↔ SQLite | 898/1152-dim; 113 Tombstones; 785 aktive IDs; 785 Links; 0 Orphans | PASS |
| H.264 AMF | 1-Frame-Funktionsprobe Exit 0 | PASS |
| HEVC AMF | 1-Frame-Funktionsprobe Exit 0 | PASS |
| AV1 AMF | `CreateComponent(AMFVideoEncoderHW_AV1) error 30` | FAIL |
| GUI Release-Smoke | 12/12 Tabs gerendert; 11 Varianz-Pass; MODELLE hängt beim Laden | PARTIAL |
| LM Studio | HTTP 200; nur `text-embedding-nomic-embed-text-v1.5` geladen | PARTIAL |
| Ollama | Port 11434 verweigert Verbindung | OFFLINE |
| Models API | `/models/list`, `/available`, `/recommendations` >10 s Timeout | FAIL |
| RUFF | nicht installiert; keine Installation autorisiert | NICHT GEPRÜFT |
| Coverage | keine aktuelle Coverage-Datei | NICHT GEPRÜFT |
| Formeller Codex-Security-Scan | Setup-Start nach 14 Minuten abgelaufen | NICHT ABGESCHLOSSEN |

Hinweis: Health-Skill meldet nominell 10/11 Core-Imports, weil er das entfernte Modul `pb_studio.pacing.engine` erwartet. Aktiver Ersatz ist `advanced_pacing_engine`; dies ist Skill-Dokumentationsdrift, kein aktueller Importbruch.

## 3. Repository-, SDD- und Release-Gate

| Gate | Ist-Zustand |
|---|---|
| Git-HEAD | 2026-07-09; aktueller Produktzustand liegt überwiegend uncommittet vor |
| Dirty Worktree | 132 Dateien im unstaged Diff, 6 im staged Diff, 70 untracked, 33 Lösch-Einträge |
| Diff-Umfang | unstaged: 5.443 Einfügungen / 6.683 Löschungen; staged: 1.559 Löschungen |
| `git diff --check` | PASS; nur EOL-Konvertierungswarnungen |
| Spec | vorhanden |
| Plan | vorhanden |
| Tasks | 227/227 `[X]`, 0 offen |
| `.completed` | fehlt |
| `.qc-passed` | fehlt |
| QC-Bericht | „PRODUCT REGRESSION PASSED / CONTINUOUS AUDIT OPEN“ |

**Gate-Entscheid:** Tests und Build sind grün. Feature bleibt laut eigener SDD-Wahrheit im kontinuierlichen Audit und ist nicht QC-bestanden. Uncommitteter Umfang und fehlende Marker schließen Release-Freigabe aus.

## 4. Bereichsstatus

| Bereich | Status | Verifizierter Kern | Hauptlücke |
|---|---|---|---|
| Projekt | Rot | Create/Open/Save/Close-Routen, isolierter Open-Kandidat, DB-Integrität | Existing-Ordner kann als „neu“ überschrieben werden; laufende UI-Aktionen nicht vollständig projektgebunden |
| Media Import | Gelb | Projekt-Guard, kanonische Pfade, Idempotenztests | Audio-Import lädt Long-Mix für Subtracks vollständig |
| Audio-Bibliothek | Gelb | UI/API/State vorhanden; Tests grün | Projektwechsel-Continuation und Erfolgssemantik |
| Audio-Analyse | Rot | Beat-Fallback, Streaming-Energy, Trigger-Caches | Full-Load-Fallback, 600-s-Struktur/Key/Spektral, Teilfehler als Erfolg |
| Stem-Separation | Rot | DirectML-Flags/Provider für ONNX; Tests grün | falsche/doppelte Budgetierung; Reservefehler kann Inferenz nicht stoppen |
| Video-Bibliothek | Gelb | Import, Hash, Scenes, Progress, UI | SigLIP-UI-Status nutzt Datei-Hash statt Embedding-Erfolg |
| Video-Analyse | Rot | RAFT/SigLIP-Modelle vorhanden; DML-Flags korrekt | GPU-Fehler werden als valide Nullanalyse persistiert; keine nutzbaren Captions |
| Anchors | Gelb | Backend-/VM-Strukturen vorhanden | sichtbarer Tab fehlt; aktive Nutzung begrenzt |
| KI-Regie / Pacing | Rot | Basis-Cutlist, Trigger, Canvas, Tests | CPU-CLAP; Brain-Features fehlen; tote Request-Felder |
| Timeline | Gelb | Canvas, Assets, Save, UI vorhanden | Asset-Doppelload/keine Cancellation; alte Projekt-Continuations |
| Export / Render | Rot | Queue, Restart, Cancel, H.264/HEVC AMF | Output-Overwrite, Doppelplanung, fehlende Clips still übersprungen, AV1 defekt |
| HIRN | Rot | 17 Achsen, Stats live: 10 Klicks, 17 learned axes | Deep-Hook wirkungslos; Persistenz nicht atomar; Dimensions-Fallback |
| Settings | Rot | Speichern/Laden/Probe vorhanden | persistierte Env-Settings greifen erst nach Öffnen des Tabs |
| Performance / VRAM | Rot | RX 7800 XT erkannt; DML-Arbiter vorhanden | Eviction-/Commit-Races, stale Sensorwerte, Timeout nicht hart |
| Modelle | Rot | LM Studio erreichbar | nur Embedding-Modell; drei Models-Endpunkte hängen; UI bleibt „lädt“ |
| Chat | Rot | Streaming-Lifecycle/Tools vorhanden | kein Chatmodell; destruktive Tools ohne Enforcement; Pacing-Timeout falsch |
| Terminal | Gelb | begrenzter 100k-Buffer, Replay, SSE | keine Redaction; Exception-Details werden angezeigt |
| Backend / API / SSE | Gelb | Health, OpenAPI, 3 SSE-Streams live | Teilfehler-/Timeout-Wahrheit nicht durchgängig |
| Daten / SQLite / FAISS | Gelb | aktuelle Live-Integrität vollständig konsistent | Crash-Fenster, Save-Fehler, Cache-Atomarität |
| Build / Tests | Grün | 853/11/0; Release 0/0 | keine aktuelle Coverage; 11 Skip-Pfade |

## 5. Finding-Ledger — Kritisch und Hoch

### CRITICAL

| ID | Bereich | Befund | Evidenz / Auswirkung |
|---|---|---|---|
| C-01 | Pacing/AI | Aktiver Semantic-Pacing-Pfad instanziiert `CLAPPyTorch` mit CPU-Default; ONNX-Wrapper besitzt zusätzlichen CPU-Fallback. | `pacing_service.py:959-964` → `smart_director.py:292-310` → `clap_pytorch.py:58-69,88-91`; `clap_wrapper.py:138-144`. Verletzt Iron R1; unbudgetierte CPU/RAM-Last. |
| C-02 | Chat/Security | `destructive` wird nicht an LLM-Schema oder Dispatch-Enforcement gekoppelt. Mehrere mutierende Tools sind falsch als nicht-destruktiv markiert. | `tool_registry.py:94-103,135-146,649-662,795-855`; `chat_agent.py:327-376`. Modell kann Projekt-, Datei-, Render- und Feedback-Mutationen ohne Bestätigung ausführen. |

### HIGH

| ID | Bereich | Befund | Evidenz / Auswirkung |
|---|---|---|---|
| H-01 | Audio Import | Subtrack-Erkennung lädt Long-Mix beim Import vollständig; SSM kann quadratisch wachsen. | `audio_router.py:136-152`; `subtrack_detector.py:83-92,131-200`. OOM vor Streaming-Weiche. |
| H-02 | Audio Analyse | Probe-/Streamingfehler fällt auf Full-Load zurück. | `audio_router.py:718-727,782-798`. Schutz versagt genau im Fehlerfall. |
| H-03 | Audio Analyse | Struktur, Key und Spektral repräsentieren bei Long-Mix nur ersten 600-s-Snapshot. | `audio_router.py:780-781,945-990`; `structure_analyzer.py:192-203,323-351`. Rest des Mixes strukturell unsichtbar. |
| H-04 | Audio Analyse | Beat/Struktur/Spektral/Key-Exceptions werden verschluckt; Ergebnis wird trotzdem `is_analyzed=true`/completed. | `audio_router.py:341-387,884-885,953-992`. Falsche Erfolgsanzeige. |
| H-05 | Stems | Router reserviert immer `mdx_net_inst`; Separator reserviert modellabhängig nochmals; CPU-Demucs erhält äußeres GPU-Budget. | `audio_router.py:541-545`; `separator.py:118-126,279-289`. Falsche Ablehnung/Doppelbuchung. |
| H-06 | Stems | Direkter Separator-Pfad läuft bei Reservefehler weiter. | `separator.py:283-291,316-338`. Budgetschutz umgehbar; Datei ist LOCKED. |
| H-07 | GPU Timeout | `wait_for` timeoutet, `finally` wartet dennoch unbegrenzt auf denselben Thread. | `backend/dependencies.py:103-141`. Client-Timeout ist keine echte Laufzeitgrenze. |
| H-08 | VRAM | Eviction erklärt Budget vor Callback frei; Callbackfehler kann überbuchten Zustand hinterlassen. | `vram_budget_manager.py:599-645,753-799`. Nicht im Fehlerpfad getestet. |
| H-09 | VRAM | Sensorwerte werden bis 10 s gecacht und können schnelle Lastwechsel verpassen. | `system_monitor.py:124-166`; `vram_arbiter.py:85-107`. Fehlfreigaben/-ablehnungen möglich. |
| H-10 | Video | RAFT-/SigLIP-Fehler werden als 0/static/leeres Embedding in erfolgreiche Analyse übersetzt. | `raft.py:292-295,396-399`; `siglip_wrapper.py:158-168`; `video_router.py:525-549,831-966`. GPU-Ausfall nicht von echtem statischen Material unterscheidbar. |
| H-11 | Video/LLM | Kein nutzbares Vision-Modell: nur Embedding-Modell geladen, Ollama offline, Moondream-ONNX fehlt. | Live-Probe + `lmstudio_vision_wrapper.py:179-202`; `video_router.py:1059-1074`. Captioning liefert keine produktiven Tags. |
| H-12 | Brain | `use_brain` aktiviert nicht automatisch Advanced/ClipSelector; Defaultpfad bleibt Round-Robin. | `pacing_service.py:892-900,1062-1113`. Brain beeinflusst Auswahl nicht. |
| H-13 | Brain | Reranker erhält keine realen `brain_audio_features`/`brain_video_features_by_clip`; Threshold wird nicht weitergereicht. | `pacing_service.py:817-825`; `clip_selector.py:420-447`. 17-Achsen-Deep-Hook praktisch featureblind. |
| H-14 | Brain | Router lädt Videoanalyse nur für Motion-Matching, nicht für `use_brain`. | `pacing_router.py:70-75,94-126`. Brain-Kontext fällt auf Neutral-/Nullwerte. |
| H-15 | Brain Data | Feedback-Event und Weight-Update liegen in getrennten Transaktionen/DBs; Postprocessor-Batch ist bei Autocommit nicht atomar. | `feedback_logger.py:54-81`; `brain_service.py:64-66`; `post_processor.py:108-125`. Halbe Lernzustände möglich. |
| H-16 | Brain Embeddings | Exact-Miss fällt auf beliebiges Projektormodell zurück; Dimensionsfehler werden still gekürzt/gepaddet. | `post_processor.py:348-418`; `cross_modal_projector.py:268-295`. Falsche Similarity ohne Fehler. |
| H-17 | Chat | `pacing.generate` ist nicht `long_running`; Standardtimeout 60 s. | `tool_registry.py:795-816`; `chat_agent.py:123-128,351-366`. Chat timeoutet, Backend kann weiterlaufen. |
| H-18 | WPF Settings | Backend startet vor Erzeugung des Settings-VM; nur dessen Konstruktor setzt FFmpeg-/VRAM-Env. | `App.xaml.cs:58-75`; `SettingsView.xaml.cs:21-27`; `SettingsViewModel.cs:61-125`. Live: 16.384 MB initial, 15.872 MB erst nach SETTINGS-Tab. |
| H-19 | WPF Projekt | Audioanalyse/Stems/Pacing besitzen nach `await` keine Projektgeneration/CTS; ProjectClosing kommt erst nach REST-Close. | `ProjectService.cs:77-90`; `AudioLibraryViewModel.cs:323-455`; `DirectorViewModel.cs:262-364`. Alte Continuations können neuen State überschreiben. |
| H-20 | Projekt | Create akzeptiert bestehenden Ordner, überschreibt `project.json`; späteres Save kann vorhandene Timeline löschen. | `project_router.py:171-205,294-313`. Datenverlust-Risiko. |
| H-21 | Data | Video-Delete tombstoniert FAISS vor SQLite-Delete; DB-Fehler rollt Tombstone nicht zurück. | `app_state.py:257-274`; `vector_store.py:428-432`. Medium bleibt relational, wird semantisch unsichtbar. |
| H-22 | Render | `include_audio` und `quality` sind wirkungslose API-Felder; Audio wird immer gemappt. | `render_schemas.py:28-34`; `render_router.py:84-85,603-612`; `render_service.py:503,515-517`. Vertrag und Ergebnis widersprechen sich. |
| H-23 | Render | FFmpeg schreibt mit `-y` direkt auf Zielpfad. Fehler/Cancel zerstört vorhandenen erfolgreichen Export. | `render_service.py:491-528`; `render_router.py:569-578`. Kein atomarer Ersatz. |
| H-24 | Render | Queue-Deduplizierung liefert bestehende ID, Router plant dennoch neuen Runtime-Task. | `render_queue.py:196-226`; `render_router.py:285-318`. Doppelrender/Output-Race. |
| H-25 | Render | Fehlende Timeline-Clips werden still übersprungen. | `render_service.py:260-263,469-476`. „Erfolgreicher“ Export kann Segmente verlieren. |
| H-26 | Models | Models-Endpunkte warten seriell auf offline Ollama-Retries und überschreiten 10 s; UI bleibt im Laden. | Live-Reproduktion; `models_router.py:403-544`; Screenshot MODELLE. |

## 6. Finding-Ledger — Mittel und Niedrig

### Audio/Core

- **M-01:** Router lädt Audio mit 22,05 kHz, Spektralbänder reichen bis 20 kHz; Nyquist kappt `air`/Teile von `brilliance` (`audio_router.py:781,795,962-969`; `spectral_analyzer.py:24-90`).
- **M-02:** `/onsets` rekonstruiert Peaks aus RMS statt persistierte `onset_times` zu liefern (`audio_router.py:368-372,426-464`).
- **M-03:** Streaming-Temp-WAV wird nicht in echtem `finally` gelöscht; Transcodefehler fällt auf langsames Offset-Decoding zurück (`streaming_analyzer.py:314-336,408-482`).
- **M-04:** `ModelLoader.commit()`-Ergebnis wird ignoriert; `unload_all()` gibt Budget vor physischer GC-Freigabe frei (`model_loader.py:295-315,450-464`).
- **M-05:** Multi-GPU-Telemetrie kann Werte mischen (`system_monitor.py:239-247,328-459`).
- **L-01:** Waveform kann High-Band kappen und mehr als Zielpunkte liefern (`waveform_analyzer.py:26-43,75-90,235-251`).
- **L-02:** Waveform-Hash nutzt nur Größe + erstes MiB; Statistik liest teils ohne Lock (`waveform_cache.py:136-167,211-272`).

### Video

- **M-06:** `generate_captions=false` schaltet auch Farbanalyse ab (`video_schemas.py:43-50`; `video_router.py:501-510,1001-1003`).
- **M-07:** Hash wird persistiert, aber nicht zur Embedding-Wiederverwendung genutzt (`video_router.py:83-126,898-940`).
- **M-08:** RAFT ~2 FPS und SigLIP ~0,2 FPS ohne Obergrenze bei Langvideo (`video_router.py:765-790,866-888`).
- **M-09:** `peak_frames` enthält Scene-Changes statt Motion-Peaks (`video_router.py:821-839`; `video_schemas.py:103-110`).
- **L-03:** Szenen-Confidence ist konstant 0,85 (`video_router.py:728-735`).
- **L-04:** Import-Fortschritt zählt Erfolge statt Eingabeposition (`video_router.py:88-100`).

### Pacing/Brain/Chat

- **M-10:** `beat_trigger_mode` ist Request-/Modellfeld ohne aktiven Read (`pacing_schemas.py:29`; `pacing_models.py:98-136`; `advanced_pacing_engine.py:1127-1133`).
- **M-11:** Brain-Router führt synchrone Shared-Connection-Reads im Eventloop aus (`brain_router.py:48-53,89-139,277-282`).
- **M-12:** Chat-Tool behauptet `video_clip_ids=[]` bedeute alle; Backend lehnt leer mit 400 ab (`tool_registry.py:800-803,461-482`; `pacing_router.py:64-65`).
- **M-13:** Auto-Provider bewertet Erreichbarkeit statt geeigneter Chat-/Vision-Capability; Embedding-only LM Studio präemptiert Fallback (`lmstudio_client.py:748-754`; `llm_provider.py:127-140`).

### WPF

- **M-14:** SigLIP-Erfolg wird über `HasCacheHash` angezeigt; echte Embedding-Felder werden verworfen (`VideoLibraryView.xaml:385-399`; `VideoClip.cs:39-47`; `ApiClient.cs:967-983`).
- **M-15:** Timeline lädt Assets über Auswahl und Eager-Pfad doppelt; Asset-Loads haben keine Dispose-Cancellation (`TimelineViewModel.cs:213-307,413-420,870-879`).
- **M-16:** Brain-Lernliste hat kein `SelectedItem`-Binding; Bewertung verlangt manuelle Cut-ID (`BrainView.xaml:62-90,214-232`).
- **L-05:** `MediaIngestView`/`AnchorView` und Timeline-Vor/Zurück-Commands sind in aktueller Tabstruktur nicht erreichbar.
- **L-06:** Terminal zeigt `Exception.ToString()` ohne Redaction (`TerminalLoggerProvider.cs:37-54`).

### Project/Data

- **M-17:** `/project/save` meldet Erfolg, obwohl SQLite-Projekt-Sync-Exception verschluckt wird (`app_state.py:429-433`; `project_router.py:326-331`).
- **M-18:** Vector-Dedupe löscht relationalen Link vor Tombstone; Crashfenster erzeugt aktive Altvektoren ohne Mapping (`video_router.py:914-925`).
- **M-19:** VectorStore-Writer setzt Dirty vor Snapshot zurück und requeued bei Fehler nicht (`vector_store.py:621-628,662-701`).
- **M-20:** Suche fragt exakt `k` ab und filtert Tombstones erst danach; gültige Treffer hinter Top-k fehlen (`vector_store.py:520-530`).
- **M-21:** Brain-Backup kann partiell bleiben; Recovery erzeugt bei Korruption leeren Store statt Backup-Restore (`backup.py:33-48`; `brain_store.py:75-85`).
- **M-22:** Embedding-Cache schreibt `.npy` direkt und ohne Lock vor SQLite-Index (`embedding_cache.py:63-77,97-137`).
- **L-07:** Migration-Runner kann Versionslücken dauerhaft überspringen (`migration_runner.py:109-121`); aktueller Baum hat keine Lücke.

### Render

- **M-23:** Preview meldet 640×360, rendert 1920×1080 (`pacing_router.py:304-331,572-590`; `preview_renderer.py:49-51,118-123`).
- **M-24:** Cancel vor GPU-Lock wird erst nach Lock-Erwerb geprüft (`render_router.py:440-459`).
- **M-25:** Expliziter Encoder-Override wird nicht funktional vorgeprüft; AV1 wird angenommen und scheitert spät (`render_service.py:116-119`; `render_schemas.py:17-21`).

## 7. Verifizierte positive Eigenschaften

- Zentraler `ModelLoader` setzt beide DirectML-Flags und verlangt DML.
- ONNX-Separator-Patch setzt beide Flags und blockiert fehlendes DML.
- BeatNet-Ausfall fällt nachvollziehbar auf librosa zurück; temporärer PyAudio-Stub wird entfernt.
- Streaming-Energy erhält Zeitachse bei Chunk-Fehlern.
- Audio-/Video-/Pacing-Progress besitzt Task-/Clip-Korrelation.
- H.264- und HEVC-AMF funktionieren aktuell auf RX 7800 XT.
- OpenAPI-Snapshot-Drift-Test ist Teil der grünen Suite.
- Projekt-Open lädt Kandidatenkatalog isoliert vor Live-State-Swap.
- SQLite WAL/FK/Busy-Timeout aktiv.
- Live-DBs und Brain-DBs integer; 0 FK-Verstöße.
- FAISS-Index, Metadata, Tombstones und `vector_map` aktuell exakt konsistent.
- FAISS-Dreifach-Snapshot besitzt Journal/Backup-Rollback.
- Render-Restart rekonstruiert versionierte Snapshots.
- WPF Release kompiliert 0/0.
- Alle zwölf Tabs sind per UIA vorhanden und rendern.
- Terminal nutzt begrenzten zentralen Buffer mit Subscribe+Replay.
- Chat-, Model-, Settings-, Timeline- und Projekt-VMs besitzen mehrere neue CTS-/Generation-Guards; verbleibende Lücken stehen oben.

## 8. Nicht verifiziert / bewusst unbekannt

Folgende Aussagen werden nicht als PASS gewertet:

1. Echter 60–120-Minuten-DJ-Mix durch Import, Analyse, Stems, Pacing und Render.
2. Reale RAFT-/SigLIP-/Moondream-Inferenz in diesem Audit.
3. Sichtbarer Einfluss aller 17 Brain-Achsen auf reale Clip-Auswahl.
4. Chat-Completion und Tool-Use mit geeignetem geladenem LLM.
5. Vollständiger Final-Export bis fertiger Datei; nur AMF-Encoder-Mikroprobe und historische Cancel-Smokes.
6. Crash während Project-Save, FAISS-Publish, Writer-Diskfehler oder Embedding-Cache-Write.
7. Multi-GPU-Sensorzuordnung unter Last.
8. Cancel während GPU-Lock-Wartezeit und harter Worker-Timeout.
9. Formelle vollständige Security-Coverage; Codex-Security-Setup wurde nicht gestartet.
10. Test-Coverage-Prozent; keine aktuelle Coverage-Datenbasis.
11. Gründe der 11 übersprungenen Tests wurden nicht einzeln live aufgelöst.

## 9. Priorität

1. **P0:** C-01 DirectML-Verstoß; C-02 Chat-Mutationsgrenze; H-20 Projektordner-Overwrite; H-23 Render-Output-Verlust.
2. **P1:** Long-Mix H-01..H-04; Stem-/VRAM H-05..H-09; Video-Wahrheit H-10/H-11; Brain H-12..H-16.
3. **P1:** Projektwechsel H-19; Daten H-21; Render H-22/H-24/H-25; Models H-26.
4. **P2:** Medium-Ledger, besonders Spektral-Nyquist, Video-Farben, Timeline-Cancellation, Save-Wahrheit und VectorStore-Writer.
5. **Gate:** Erst nach Fix-/Verifikationszyklus, sauberem Git-Stand, `.completed`, erneuter QC und `.qc-passed` releasefähig.

## 10. Audit-Selbstkritik

- Keine Erfolgsaussage basiert nur auf altem Brain/Log; aktuelle Live- oder Code-Evidenz ist jeweils genannt.
- Grüne Tests wurden nicht mit vollständiger Produktfunktion gleichgesetzt.
- Statische Funde besitzen hohe Kontrollfluss-Konfidenz, aber keine behauptete Live-Reproduktion, sofern nicht ausdrücklich angegeben.
- Security-Scan-Setup-Timeout ist echte Coverage-Lücke.
- Umfang „gesamte App“ bedeutet: alle Produktzonen und UI-Bereiche geprüft; nicht jede historische/archivierte Datei semantisch Zeile für Zeile auditiert.

## 11. Artefakte

- GUI-Screenshots: `gui_screenshots/status_20260728_084011/`
- MODELLE-Livebeleg: `gui_screenshots/status_20260728_084011/tab_modelle.png`
- Aktiver SDD-Workspace: `specs/00013-system-wide-bug-hunting-audit/`
- Vorheriger Baseline-Report: `AUDIT_REPORT_PB_Studio_20260726.md`

