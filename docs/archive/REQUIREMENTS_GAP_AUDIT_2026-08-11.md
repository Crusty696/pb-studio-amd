# PB Studio — vollständiger Anforderungs-Lückenbericht

**Stand:** 2026-08-11  
**Audit-Ref:** `codex/obj76-runtime-truth@8328d492f8b1`  
**Verglichene Branch-Tips:** `main@a1a745829f78`, `obj74@f8e1ad67750f`, `obj75@958353b25575`, `obj76@8328d492f8b1` sowie identische `origin/*`-Refs  
**Arbeitsbaum vor und nach dem Audit:** unverändert; vorbestehend geändert: `Tests/test_video_analysis_resume.py`, `backend/app_state.py`, `config.json`

## 1. Wahrheitsgrenze und Zählregel

Dieser Bericht deckt alle im lokalen Repository und im aktuellen PB-Studio-Brain auffindbaren schriftlichen Anforderungen ab: PRD, SAD, DoD, Projektplan, 17 Feature-Workspaces, aktive ADRs, aktuelle Brain-Entscheidungen/-Pläne, README-Betriebsverträge sowie alle vier eindeutigen Branch-Tips. Unbekannte oder nirgends schriftlich festgehaltene Anforderungen können logisch nicht inventarisiert werden; für die genannte schriftliche Quellmenge wurde eine vollständige Source-to-Code/Test/Runtime-Prüfung durchgeführt.

Klassen:

- `MISSING`: geforderter Produktionspfad fehlt oder ist auf dem genannten Branch nicht vorhanden.
- `PARTIAL`: ein Teil ist vorhanden, aber mindestens ein geforderter Producer, Consumer, Zustand oder Lifecycle-Schritt fehlt.
- `UNVERIFIED`: Implementierung kann vorhanden sein, der ausdrücklich geforderte aktuelle Live-/Messnachweis fehlt.
- `DOC-CONFLICT`: normative Quellen, Marker, Tasks oder tatsächlicher Produktpfad widersprechen sich.

Die nummerierten Zeilen sind **Befunddatensätze**, nicht automatisch semantisch eindeutige Requirement-IDs. Bereichsübergreifende Anforderungen werden primär einmal geführt und in anderen Bereichen nur referenziert. Branch-Rückstände sind separat gekennzeichnet und werden nicht als zusätzliche aktuelle `main`-/`obj76`-Lücke gezählt.

## 2. Abdeckung und aktuelle Verifikation

| Prüfung | Ergebnis |
|---|---|
| Anforderungsinventar | 17 Feature-Workspaces; 324 feature-lokal eindeutige Requirement-/Objective-/SC-IDs; 250 explizite FR/TR/OR/RR/SC-Definitionen; 182 global eindeutige ID-Strings; 33 Kollisionsgruppen |
| Agenten-Audits | 10 read-only Durchgänge: Requirements, Branches, System/Dataflow, Audio, Video, Pacing, KI, Datenbank, WPF/Querschnitt, unabhängige Konvergenz |
| Python Collection | 1.508 Tests gesammelt, 1 Collection-Skip |
| Python Vollsuite | **1.494 PASS, 13 SKIP, 2 FAIL** in 30:30 min |
| Python Fehler 1 | `Tests/test_audit_sdd_gate.py::test_current_feature_workspace_passes_fail_closed_sdd_gate`: `QC_GATE_COMMIT` für `00019/.qc-passed` ist nicht aktuell für HEAD/direct PR merge |
| Python Fehler 2 | 9. Test in `test_recovery_owner_adapters.py` fiel nur in der Vollsuite; Datei isoliert 13/13 und Recovery-Cluster 60/60 PASS — Suite-Isolation/Kontamination unaufgelöst, kein reproduzierter Produktdefekt |
| Python Compile | `compileall backend src` PASS |
| WPF Release | 0 Fehler, 0 Warnungen |
| Native C# | 57/57 PASS |
| Runtime-Vertrag | Python 3.11.9, NumPy 1.26.4, RX 7800 XT DirectML/LHM-LUID konsistent, H.264/HEVC/AV1 AMF vorhanden |
| GUI-Matrix aktuell | 84 Screenshots; 14 Tabs × 2 Größen × 3 DPI; Keyboard-Zyklus PASS; Gesamtgate **FAIL** wegen 200-%-DPI-Größe und abgeschnittenem SETTINGS-`KI-Modus`-Slider |
| Live-Datenintegrität | 4 SQLite-Stores `quick_check=ok`, 0 FK-Fehler; FAISS 396/396, 1152-D, 0 Orphans; Recovery-Generation 386 Artefakte owner-validiert |
| Nicht erreichbar | LM Studio `127.0.0.1:1234` `/v1/models` und `/api/v0/models`; daher keine aktuelle Modell-/Tagging-Erfolgsbehauptung |

## 3. Audio

| ID | Klasse | Fehlende oder unvollständige Anforderung | Beleg | Scope |
|---|---|---|---|---|
| A-01 | MISSING | Geforderte Downbeats/rote Taktmarker werden nicht produziert. `get_downbeats()` existiert, der Live-Pfad ruft es nie auf und persistiert nur `beat_type="beat"`/`unavailable`. | `specs/00012.../spec.md:13-18,61`; `beat_detector.py:306-319`; `audio_router.py:2138-2229` | alle Branches |
| A-02 | PARTIAL | Taktlabels sollen `BAR 1`, `BAR 2`, … sein; Modell liefert nur `D`, XAML zeigt `BAR D`. | `00012/spec.md:85`; `BeatMarkerViewModel.cs:31-38`; `TimelineView.xaml:747-763` | alle |
| A-03 | PARTIAL | Audio-Stages haben Status/Fehler, aber keine geforderten Input-/Config-Fingerprints, Artefaktvalidität oder Stage-Zeitstempel. | `00019/spec.md:55-56`; `audio_router.py:863-940`; `audio_schemas.py:83-85` | alle |
| A-04 | PARTIAL | Harter Prozessabbruch hinterlässt keinen garantiert terminalen Audio-Stagezustand; `interrupted` wird nur im laufenden `CancelledError`-Handler geschrieben, Startup-Recovery ist renderbezogen. | `00019/spec.md:61-63,126-127`; `audio_router.py:1398-1417`; `backend/main.py:250-265` | alle |
| A-05 | PARTIAL | Frühe/globale Audiofehler publizieren Log/SSE, persistieren aber keinen Clip-/Stage-Fehler. | `00019/spec.md:61-65`; `audio_router.py:1452-1470` | alle |
| A-06 | PARTIAL | WPF verwirft `StageStatus`; `failed`, `interrupted` und `unavailable` können als „Analyse vollständig“ erscheinen, Fehlerdetails sind pro Clip nicht sichtbar. | `00019/spec.md:64-69`; `ApiClient.cs:1332-1402`; `AudioClip.cs:20-38`; `AudioLibraryViewModel.cs:369-380,529-537` | alle |
| A-07 | MISSING | Gefordertes Mel-Spektrogramm fehlt im produktiven Router/DTO; vorhanden sind STFT-Bänder und Zentroiden. | `00009/spec.md:77`; `spectral_analyzer.py:107-157`; `audio_router.py:2387-2423`; `audio_schemas.py:139-150` | alle |
| A-08 | PARTIAL | „Spectral Depth“-Toggle, „No Depth Data“ und Reanalyse-Aktion fehlen; Renderer ist dauerhaft eingebunden und Leerzustand leert nur Punkte. | `00009/spec.md:71,124`; `TimelineViewModel.cs:60-62,101-106`; `TimelineView.xaml:471-483` | alle |
| A-09 | PARTIAL | Long-Mix-Struktur liefert feste 60-s-Energiebins (`high_energy`, `rising`, `plateau`) statt geforderter Intro/Verse/Chorus/Bridge/Outro/Drop-Grenzen. | `00009/spec.md:78,122`; `structure_analyzer.py:297-350`; `audio_router.py:2346-2355` | alle |
| A-10 | PARTIAL | Key repräsentiert beim Instrumental-Stem nur 600 s; bei vorhandenen Drums ohne Instrumental kann Chroma aus dem Drum-Pfad statt Originalmix stammen. | `00013/history/spec...:90,462,472`; `audio_router.py:2000-2008,2446-2469` | alle |
| A-11 | PARTIAL | Bei langen Dateien mit Stems wird Drums-Spektrum als Clip-Spektrum persistiert; Originalmix-Pass ersetzt nur Energy, nicht Spektrum. | `00009/spec.md:77`; `audio_router.py:2000-2008,2385-2423` | alle |
| A-12 | MISSING | Reimport-Skip ist pfad-, nicht hashgebunden. Gleicher Inhalt unter neuem Pfad wird neu analysiert; geänderter Inhalt am gleichen Pfad invalidiert alte Stages nicht. | `Brain/_plan/06_PHASES.md:86-93`; `audio_router.py:568-630`; `app_state.py:795-837` | alle |
| A-13 | PARTIAL | Geplante Subtrack-Felder `sub_bpm`/`sub_key` existieren, beide Producer setzen immer `None`; Detector produziert sie nicht. | `Brain/_plan/06_PHASES.md:60-68`; `audio_schemas.py:37-43`; `audio_router.py:619-624,1697-1702`; `subtrack_detector.py:28-38` | alle |
| A-14 | UNVERIFIED | Fünf annotierte reale Mixe, F1 ≥0,65 und 2-h-Analyse <60 s sind nicht belegt; Ground-Truth-Test ist bedingungslos geskippt. | `Brain/_plan/06_PHASES.md:86-93`; `_plan/07_RISKS.md:138-155`; `test_subtrack_detector.py:52-58` | aktuell |
| A-15 | UNVERIFIED | 1–4-h-Mix, Audioanalyse <0,5× Echtzeit und Audioanteil des Zero-Freeze-Ziels haben keinen aktuellen gebundenen Messbeleg. | `prd.md:12,62,73-74`; `project-plan.md:83` | aktuell |
| A-16 | UNVERIFIED | Songsektionen >80 % Ground-Truth-Alignment und Depth-Framezeit <50 ms/>30 fps sind ungemessen. | `00009/spec.md:85,115-116` | aktuell |
| A-17 | MISSING | Depth-Arrays werden unkomprimiert in `ai_data_json` gespeichert; geforderte binäre Sidecars/komprimierte JSON-Arrays fehlen. | `00009/spec.md:130`; `app_state.py:964-1025` | alle |
| A-18 | PARTIAL | CLAP-Embedding wird gespeichert, aber `has_audio_embedding` danach nicht aktualisiert oder ins WPF-Modell übernommen. | `audio_router.py:596-610,794-854`; `audio_schemas.py:27`; `ApiClient.cs:1327` | alle |
| A-19 | PARTIAL | Waveformfehler werden zu erfolgreichem `[]`; legitimer Leerzustand und Fehler sind nicht unterscheidbar, Reanalysegrund fehlt. | `00009/spec.md:124`; `audio_router.py:1526-1533,2590-2595` | alle |
| A-20 | PARTIAL | Öffentlicher Waveform-Vertrag akzeptiert 1–8 Bänder, Implementation liefert für jeden Wert ≥3 nur drei. | `audio_router.py:1512-1520,2576-2588` | alle |
| A-21 | DOC-CONFLICT | Plan/Task behaupten `/audio/depth/{id}` und `/audio/analyze-depth/{id}`; produktiv existieren getrennte `/structure`, `/spectral` und `/analyze`-Pfade. | `00009/plan.md:59-65`; `tasks.md:19`; `audio_router.py:1784-1825` | alle |
| A-22 | DOC-CONFLICT | Modulkarte beschreibt `AudioService.analyze_audio`; Live-Router ruft `_run_audio_analysis()` direkt, `AudioService` hat nur Stem-Funktionen. Streaming-Schwelle ist >600 s, nicht >60 min. | `audio-expertise/SKILL.md:14-23`; `module-map.md:51,58`; `audio_service.py:17-60`; `audio_router.py:1081-1089,1919` | Doku vs alle |
| A-23 | DOC-CONFLICT | SAD-CPU-Retry widerspricht DirectML-only; Audio-Skill behauptet madmom/Python-3.11-Unvereinbarkeit, während aktueller Produktstand madmom/BeatNet aktiv führt. | `sad.md:86`; ADR-0002; `directml_adapter.py:425-463`; `CLAUDE.md:177-179,284-287` | Doku |

## 4. Video

| ID | Klasse | Fehlende oder unvollständige Anforderung | Beleg | Scope |
|---|---|---|---|---|
| V-01 | MISSING/PARTIAL | Video persistiert Status/Fehler, aber keine Provider-/Modell-/Attempt-Receipts, Fingerprints oder Zeitstempel; LM-Failover-`_attempts` wird verworfen, Wrapper-SSE hat keine Clip-Korrelation. | `00019/spec.md:55-56`; `00021/spec.md:101-102`; `video_schemas.py:95-97`; `video_router.py:300-325`; `lmstudio_vision_wrapper.py:120-131,465-478` | alle |
| V-02 | MISSING | Persistierte Analyse-Tags verschwinden aus `/video/clips` und WPF nach Reload; `tag_source` bleibt, `tags` werden leer rekonstruiert. Read-only-Probe: DB `['neon','club']` → API `[]`. | `prd.md:63`; `video_router.py:687-779`; `app_state.py:1575-1598`; `VideoLibraryViewModel.cs:948-970` | alle |
| V-03 | PARTIAL | Angeforderte Stage `unavailable` wird als Gesamt-`completed` bewertet; Audio-Key kann ohne Fehlergrund unavailable sein, WPF blendet diesen Zustand aus. | `00021/spec.md:103-105`; `video_router.py:217-224,1190-1206`; `VideoClip.cs:59-82` | alle |
| V-04 | PARTIAL | Valide completed Stages einer Partialanalyse werden nach Restart nicht in den Cache geladen; Pacing nutzt nur Cache-Snapshot und sieht Motion/Tags/Embedding dann als fehlend/default. | `00021/spec.md:106-107`; `app_state.py:1602-1628`; `pacing_router.py:337-363,867-901` | alle; dirty Änderung behebt Partialfall nicht |
| V-05 | MISSING | P1-Content-Search fehlt in Router, ApiClient, ViewModel und XAML, obwohl UI inhaltsbasierte Stichwortsuche behauptet. `VideoSpecialist`/`EmbeddingRepository.search_video` sind unverdrahtet. | `prd.md:63`; `VideoLibraryView.xaml:150-153`; `video_specialist.py:384-466`; `embedding_repository.py:300-307` | alle |
| V-06 | PARTIAL/DOC-CONFLICT | >10.000-Clips-Library ist nicht container-virtualisiert: normales `WrapPanel`, komplette Seitenakkumulation, eager Thumbnails für alle Clips; T011 behauptet Abschluss. | `00007/spec.md:73`; `sad.md:18`; `VideoLibraryView.xaml:250-259,295-298`; `VideoLibraryStateService.cs:63-85`; `VideoLibraryViewModel.cs:1185-1229` | alle |
| V-07 | MISSING/DOC-CONFLICT | TR-006 verbietet Random-Seeks in Extraktionsloops; drei produktive Schleifen verwenden `cap.set(CAP_PROP_POS_FRAMES)`; abgeschlossene Tasks mappen TR-006 fälschlich auf Audioarbeit. | `00011/spec.md:70`; `video_router.py:1657-1677,2244-2256`; `visual_curves.py:55-73`; `00011/tasks.md:4,6` | alle |
| V-08 | MISSING/DOC-CONFLICT | Geforderter DirectML-beschleunigter Scene-Frame-Vergleich fehlt; produktiv läuft PySceneDetect CPU, RAFT-Scene-Funktion hat keinen Produktionscaller; Task ist dennoch X. | `00009/spec.md:80,87`; `scene_detect.py:23-32`; `raft.py:528-566`; `video_router.py:1553`; `00009/tasks.md:16` | alle |
| V-09 | PARTIAL | Batchanalyse überspringt im OBJ74-Branch jeden `IsAnalyzed`-Clip; später neu angeforderte Caption-/Tag-Stages werden nicht ergänzt. | `00019/spec.md:66-67`; `obj74:VideoLibraryViewModel.cs:622-635,1015-1028` | nur OBJ74; neuere Branches geschlossen |
| V-10 | UNVERIFIED | OBJ76 T003: realer PB-Studio-Tag-Commit plus Provider-Degradation, Shutdown und erfolgreicher Restart/Resume fehlen; letzte Evidence endet mit `tags=[]`. | `00021/tasks.md:11`; `qc-report.md:5,10-11`; `evidence/live-tagging-restart-resume.md:11-16,48-56` | OBJ76 |
| V-11 | UNVERIFIED/NO-GO | OBJ76 T019: separater 10-Clip-Canary fehlt; kein 10/10-Receipt, Bulk bleibt korrekt verboten. | `00021/tasks.md:45-46`; `evidence/bulk-decision.md:3-14` | OBJ76 |

## 5. Pacing

| ID | Klasse | Fehlende oder unvollständige Anforderung | Beleg | Scope |
|---|---|---|---|---|
| P-01 | MISSING/PARTIAL | Response/UI nennen verwendete, ausgeschlossene und wegen fehlender Analyse abgelehnte Clips samt Gründen nicht; Selector-Provenienz erreicht das Produktmodell nicht. | `00019/spec.md:77-78`; `pacing_models.py:80`; `pacing_schemas.py:85-90`; `pacing_router.py:270-288,518-523`; `DirectorViewModel.cs:354-385,525-541` | alle |
| P-02 | PARTIAL | Aktiviertes Stem-Pacing ohne gültige Stems fällt nur per Log auf Standard-Pacing zurück; Nichtverfügbarkeit fehlt in Response/UI. | `00019/spec.md:70,77`; `pacing_router.py:922,975`; `pacing_schemas.py:85` | alle |
| P-03 | PARTIAL | `min_cut_interval` existiert verschachtelt und top-level; C# sendet/Engine liest nur top-level. Verschachtelter API-Wert validiert erfolgreich, wirkt aber nicht. | `pacing_schemas.py:33,67`; `ApiClient.cs:1496-1497`; `pacing_router.py:916`; `pacing_service.py:1204` | alle |
| P-04 | PARTIAL | Container-Recycling gilt nicht für alle Timeline-ItemsControls; Songsegmente, Thumbnailframes, A1-Segmente und Beatmarker sind normale Canvas-Listen. | `00008/spec.md:89`; `TimelineView.xaml:337,419,486,581,654,719`; `TimelineViewModel.cs:410` | alle |
| P-05 | PARTIAL | Ruler soll gecacht zeichnen; `DrawRuler()` leert Canvas und erzeugt Visual/Host bei jedem Aufruf neu. | `00008/spec.md:93`; `TimelineView.xaml.cs:246-250,289` | alle |
| P-06 | UNVERIFIED/DOC-CONFLICT | 60 fps, >1000 Items, Zero Freezes, <1-s UI und <100-ms Feedback sind nicht gemessen; Spectral-Zoom aktualisiert große Collections synchron auf UI-Thread, alter QC nennt Codeanalyse als PASS. | `prd.md:74,111`; `sad.md:16,121`; `00008/spec.md:123-125`; `TimelineViewModel.cs:83-145`; `00008/qc-report.md:12-18,35-40` | aktuell |
| P-07 | DOC-CONFLICT | README/Integrationsdoku stellen `SyncMode`/`plan_cuts()` als Live-API dar; produktiver REST-Service nutzt `TriggerSettings`/`generate_cut_list()` ohne `sync_mode`. | `pacing/README.md:87`; `docs/pacing_engine_integration.md:41`; `advanced_pacing_engine.py:126,291`; `pacing_schemas.py:45`; `pacing_service.py:1285` | Doku vs alle |
| P-08 | PARTIAL | Timeline-Edits werden erst nach 1-s-Debounce gespeichert; Project Save/Close und App-Exit flushen die Timeline nicht. Schnelles Save/Close/Reopen kann bestätigte manuelle Edits verlieren. | `00020/spec.md:72-73`; `TimelineView.xaml.cs:68-70,670-674`; `TimelineViewModel.cs:915-927`; `ProjectOverviewViewModel.cs:186-204`; `ProjectService.cs:124-132`; `App.xaml.cs:210-232` | alle |
| P-09 | PARTIAL | P1 CAP-004 ist ausdrücklich nicht vollständig: README bezeichnet den echten interaktiven Timeline-/Player-Editor als noch im Ausbau. | `prd.md:65`; `README.md:34,243` | aktuell |
| P-10 | UNVERIFIED | >98 % Cut-Accuracy hat keinen aktuellen Ground-Truth-Messbeleg. | `prd.md:72` | aktuell |
| P-11 | UNVERIFIED/DOC-CONFLICT | SAD fordert <10 ms Sync-Drift; Export-Spec nennt <33 ms, QC misst Drift nicht explizit. | `sad.md:123`; `00006/spec.md:78`; `00006/qc-report.md:24-31` | aktuell |
| P-12 | UNVERIFIED | Live-Wirkung der Onset/Kick/Snare/HiHat-Controller auf einen langen echten DJ-Mix ist ausdrücklich nicht belegt. | `CLAUDE.md:245-251` | aktuell |
| P-B01 | MISSING | `onset_sensitivity` beeinflusst im OBJ74-Livepfad die Onset-Neuberechnung nicht vollständig. | `00020/spec.md:52`; Gegenbeleg neuere `advanced_pacing_engine.py:1835` | nur OBJ74 |
| P-B02 | MISSING | `max_cut_interval` ist im OBJ74 nicht in beiden Cut-Längenpfaden harte Obergrenze. | `00020/spec.md:52`; neuere `advanced_pacing_engine.py:1215,1845` | nur OBJ74 |
| P-B03 | MISSING | OBJ74 snappt Subtracks nach Längenerzwingung und kann Mindestlänge erneut verletzen. | `00020/spec.md:65`; neuere `advanced_pacing_engine.py:1209` | nur OBJ74 |
| P-B04 | MISSING | OBJ74 erzeugt semantische FAISS-Kandidaten, nimmt Similarity aber nicht in finalen Hybridscore. | `00020/spec.md:65`; neuere `clip_selector.py:93` | nur OBJ74 |
| P-B05 | MISSING | OBJ74-Anker aktivieren Advanced-Pfad nicht sicher und verwenden Record-ID statt realer `clip_id`. | `00020/spec.md:65`; neuere `pacing_service.py:55,994` | nur OBJ74 |
| P-B06 | MISSING | OBJ74 fehlen aktuelle Timeline-Lifecycle-Gates, Zustandsversionierung und Viewport-Fensterung. | `00020/spec.md:72`; `prd.md:111`; neuere `TimelineViewModel.cs:44,150,410` | nur OBJ74 |

## 6. KI

| ID | Klasse | Fehlende oder unvollständige Anforderung | Beleg | Scope |
|---|---|---|---|---|
| K-01 | DOC-CONFLICT/PARTIAL | 00014 T004 fordert `default_mode` für Captioning und Modelle-`active_tasks`. Video liest dynamisch; Modelle markieren nur explizite Overrides. Spätere Architektur erklärt Overrides zur Autorität. | `00014/tasks.md:6`; `video_router.py:2286`; `models_router.py:448-478,978` | alle |
| K-02 | PARTIAL | KI-Modus synchronisiert Backend nur beim Speichern; `OnKiModeIndexChanged` ändert nur Label/Preview. | `00014/tasks.md:8`; `SettingsViewModel.cs:153,485-496` | alle |
| K-03 | PARTIAL | Modelllisten-Refresh nach Modusänderung erfolgt nur nach erfolgreichem Save-Sync, nicht beim Sliderwechsel. | `00014/tasks.md:9`; `SettingsViewModel.cs:153,486`; `ModelManagerViewModel.cs:54` | alle |
| K-04 | DOC-CONFLICT | 00014 T001–T009 stehen offen, während QC, `.completed` und `.qc-passed` PASS behaupten; T004/T006 sind nach Codeprüfung tatsächlich nur teilweise. | `00014/tasks.md:3-11`; `qc-report.md:11-30`; Marker | alle |
| K-05 | MISSING | FR-398-Manifest-/Hashbindung für SigLIP-Text-Assets existiert nur in OBJ76; main/OBJ74/OBJ75 aktivieren anhand vorhandener Datei. | `00021/spec.md:116`; `obj76:siglip_wrapper.py:55,69,105` | main/OBJ74/OBJ75; OBJ76 geschlossen |
| K-06 | UNVERIFIED | Aktuelle LM-Studio-Modell-/Capability-/Override-Wirksamkeit ist nicht belegbar; beide Inventarendpunkte waren offline. Keine Behauptung einer veralteten Modell-ID. | `00020/spec.md:74`; `00021/spec.md:110`; `model_registry.py:341`; `lmstudio_client.py:455` | aktueller Runtimezustand |
| K-07 | UNVERIFIED | Brain-Deep-Hook ist statisch/Unit-verdrahtet, aber laut maßgeblicher ADR ohne aktuellen Live-Pacing-Run nicht vollständig getestet. | `Brain/.../brain-architecture.md:27,58`; `clip_selector.py:235`; `pacing_service.py:502` | main/OBJ75/OBJ76 |
| K-08 | MISSING | OBJ74 fehlt FR-386: request-idempotente Feedback-Operation-ID und aktueller Achsen-/Projector-Eventvertrag. | `00020/spec.md:76`; neuere `brain_router.py:155,186`; `bridge_dimensions.py:46` | nur OBJ74 |
| K-09 | MISSING | OBJ74 fehlt FR-387: projekt-/epoch-/rootgebundener Chat-Turn, per-project History und typisierte Streamfehler. | `00020/spec.md:79`; neuere `chat_router.py:71,334`; `ChatViewModel.cs:47` | nur OBJ74 |
| K-10 | MISSING | OBJ74 fehlen FR-388/389: Projector-Generation/Event-UUID, Pending Events, Projektcheckpoint und Copy-on-write Publish. | `00020/spec.md:82,85`; neuere `cross_modal_projector.py:82,252`; `projector_trainer.py:253` | nur OBJ74 |
| K-11 | DOC-CONFLICT | Dormante `moondream_pytorch.py`/`clap_pytorch.py` Vollmodellloader bleiben im Produktbaum und widersprechen DirectML-only/Hash-Policy; kein Produktionscaller, daher kein aktiver Runtime-Verstoß. | ADR-0002; `moondream_pytorch.py:183,189`; `clap_pytorch.py:84` | alle |
| K-12 | UNVERIFIED | Chat-/Brain-Explain-`llm_status` wurde nicht aktuell live in WPF beobachtet. | `CLAUDE.md:252-261` | aktuell |
| K-13 | PARTIAL | Generierter `PauseCommand` der Learning Session ist tot; Dialog verwendet nur `PlayPauseCommand`/`RestartCommand`. Pausefunktion bleibt über Toggle erreichbar. | `LearningSessionViewModel.cs:220-235`; `LearningSessionDialog.xaml:95-100` | alle |
| K-14 | PARTIAL/LIVE-FAIL | Aktuelles GUI-Gate: bei 200 % DPI/1400×900 wurde nur 2580×1460 erreicht; SETTINGS-`KI-Modus`-Slider ist am unteren Rand abgeschnitten. | `C:\Users\david\AppData\Local\Temp\pb_requirements_audit_gui_20260811_2157\gui-release-gate.json`; Screenshot `...\screenshots\dpi192-1400x900-settings.png` | aktueller OBJ76-Tree |
| K-15 | UNVERIFIED | P95-UI-Latenz <2 s ist nicht gemessen; siehe auch P-06. | `sad.md:121` | aktuell |
| K-16 | UNVERIFIED | SAD-Kompatibilitätsmatrix AMD/Intel/NV via DirectML ist nur auf RX 7800 XT belegt. | `sad.md:122` | aktuell |
| K-17 | PARTIAL/MISSING | Accepted ADR-002 ist nicht abgeschlossen: `ConfigureAwait(false)` nur bei 140 von 311 `await`-Zeilen; Port 8765 bleibt in `App.xaml.cs`/`PythonBridgeService.cs` fest statt über `appsettings.json` konfigurierbar. Andere drei ADR-Actions sind inzwischen umgesetzt. | Accepted ADR-002 Action Items; `App.xaml.cs:148`; `PythonBridgeService.cs:32` | alle |
| K-18 | UNVERIFIED | Der grüne Binding-Guard beweist keine view-spezifische Command-/Property-Verdrahtung: er verkettet sämtliches XAML, akzeptiert einen Namensfund in irgendeiner View und lässt deklarierte Altlasten durch. | `00019/spec.md:53-54`; `test_viewmodel_binding_wiring.py:45-65,81-85,110-120` | alle |
| K-19 | UNVERIFIED | DoD fordert Fehlerzustände und High-Contrast-Prüfung aller 14 Views. Das aktuelle 84-Screenshot-Gate variiert Größe/DPI, injiziert aber keine vollständige Fehlerzustandsmatrix und schaltet High Contrast nicht um; explizite Trigger existieren nur in Anchor/Terminal, globale Palette ist statisch. | `dod.md:64-71`; `AnchorView.xaml:85`; `TerminalView.xaml:66,94`; `App.xaml:30-51` | aktueller UI-Tree |

Querverweise: Der reale Tagging-Erfolg/Canary stehen einmal unter V-10/V-11; deren KI- und Datenbankanteile werden nicht erneut gezählt.

## 7. Datenbank

| ID | Klasse | Fehlende oder unvollständige Anforderung | Beleg | Scope |
|---|---|---|---|---|
| D-01 | MISSING/DOC-CONFLICT | Normativ beschriebener sqlite-vec-Projektstore ist unverdrahtet; `EmbeddingRepository` hat nur Script-/Testcaller, produktiv läuft FAISS und Recovery enthält kein `embeddings.db`. | `Brain/_plan/02_DECISIONS.md:12`; `brain-architecture.md:47`; `embedding_repository.py:67-72`; `video_router.py:415-425` | alle |
| D-02 | PARTIAL | Unverdrahtetes Repository ist 768-D statt aktueller 1152-D und lehnt Zero-/NaN-/Inf-Vektoren nicht explizit ab; Live-FAISS/Cache sind 1152-D. | `semantic-embedding-store-split.md:13-24`; `embedding_repository.py:24-25,422-428`; Migration `001_initial.sql:41` | alle |
| D-03 | PARTIAL | Öffentlicher `VectorStore.add_embedding()` schreibt ohne Media-Link, Recovery-Barrier oder Finite-/Zero-Prüfung; sicherer Writer ist separat. Aktuelle direkten Caller sind selbst unverdrahtet, Livebestand hat 0 Orphans. | `00019/spec.md:79-80`; `vector_store.py:385-447`; `video_specialist.py:302-316`; `clip_selector.py:1378-1391` | alle |
| D-04 | PARTIAL | Kein Branch-Commit rekonstruiert bei Video-Reload `tag_source`, `analysis_status`, `stage_status`, `stage_errors`. Dirty Worktree enthält Kandidat/Test, aber keine versionierte Umsetzung. | `00013/spec.md:78-80`; `00019/spec.md:61-68`; committed `app_state.py:1602-1628`; dirty Diff `:1613-1627`; dirty Test `test_video_analysis_resume.py:90-185` | alle Branches |
| D-05 | PARTIAL | Auch dirty Änderung lädt Cache nur bei `is_analyzed=True`; persistierte partial/failed Analysen bleiben nach Projektöffnung aus RAM/API/UI. Analyse-Retry kann DB separat nachladen. | `app_state.py:1602-1604`; `video_router.py:157-185,240-325` | alle + dirty |
| D-06 | PARTIAL | `resolve_project_db_id()` fällt auf Projekt 1 zurück; mehrere Persistenz-/Restore-Wege nutzen nicht-strikten Getter statt unveränderlicher erfasster Projekt-ID. Kein realer Cross-Project-Write reproduziert. | `00013/spec.md:73-77`; `app_state.py:124-133,955,1150,1382` | alle |
| D-07 | DOC-CONFLICT | Brain-Entscheidung nennt einheitlich `busy_timeout=5000`; Brain/sqlite-vec nutzt 5000 ms, Haupt-DB 30000 ms. Kein Live-Lockfehler. | `Brain/_plan/02_DECISIONS.md:25`; `storage/sqlite_init.py:10-18`; `database_core.py:256-259` | alle |
| D-08 | MISSING | E010-4-h/4-GB-Stress ist nicht ausführbar wie dokumentiert: Worker ist durch `/src/tools/` ignoriert und in keinem Branch versioniert; lokale Datei läuft nur 3×3, kein Launcher setzt `PB_STUDIO_FORCED_VRAM=4096`. | `00010/spec.md:31,47,62`; `project-plan.md:77-84`; `.gitignore:71`; `stress_4h.bat:24-27`; lokale `execute_4h_stress_test.py:163-164` | alle Branches |
| D-09 | UNVERIFIED | Recovery-Fault-Injection ist suite-order-abhängig: Vollsuite ein Fehler im 9. Owner-Adapter-Test; isoliert 13/13 und Recovery-Cluster 60/60 PASS. Kein Produktdefekt reproduziert. | Vollsuite; `test_recovery_owner_adapters.py` Test 9 | aktueller Worktree |

Querverweise: Stage-Fingerprint/Timestamp-Persistenz steht unter A-03/V-01; Timeline-Flush unter P-08; OBJ76 Restart/Canary unter V-10/V-11.

## 8. Branch-Matrix

| Ref | Verhältnis zu `main` | Aktuelle Bewertung |
|---|---|---|
| `codex/obj74-finish-open-tasks@f8e1ad67750f` | 19 Commits hinter, 0 voraus | keine exklusiven Requirements; zusätzliche P-B01–P-B06, V-09, K-08–K-10 Rückstände |
| `codex/obj75-open-bug-fixes@958353b25575` | 1 hinter, 0 voraus | keine exklusiven Requirements; UI-Tree identisch zu main/OBJ76 |
| `main@a1a745829f78` | Basis | enthält OBJ74/75-Integration |
| `codex/obj76-runtime-truth@8328d492f8b1` | 8 voraus | einzig neuer Requirement-Scope 00021; T003/T019 offen |

Alle lokalen Branches entsprechen ihren `origin/*`-Refs. Es wurde kein Checkout durchgeführt.

## 9. SDD-/Traceability-Wahrheit

Alle 17 Workspaces sind mit dem aktuellen Release-Validator ungültig. Das beweist Governance-Drift, nicht automatisch Produktfehler.

| Workspace | Findings | Hauptursache |
|---|---:|---|
| 00005 | 18 | Legacy-Format, Marker/QC nicht aktuelles JSON-Schema |
| 00006 | 18 | Legacy-Format |
| 00007 | 17 | fehlender QC-Bericht/Marker plus Legacy-Format |
| 00008 | 15 | Legacy-Format |
| 00009 | 13 | Legacy-Taskformat, QC-Heading/Marker |
| 00010 | 14 | Legacy-Format |
| 00011 | 10 | Legacy-Format |
| 00012 | 11 | Legacy-Format |
| 00013 | 1 | `QC_GATE_COMMIT` gegen aktuellen dirty Worktree |
| 00014 | 15 | offene Tasks, ungültige Marker, Legacy-Format |
| 00015 | 17 | Legacy-Format/Markerfelder |
| 00016 | 32 | Legacy-Format |
| 00017 | 1 | `spec.md` fehlt |
| 00018 | 3 | Markerfelder/QC-Heading |
| 00019 | 1 | `QC_GATE_COMMIT` gegen aktuellen HEAD; reproduzierter Vollsuite-Fehler |
| 00020 | 1 | `QC_GATE_COMMIT` gegen aktuellen dirty Worktree |
| 00021 | 3 | Release-Marker fehlen; T003/T019 offen |

Zusätzliche Statuskonflikte:

- `00007`: 13/13 Tasks X, aber kein QC-Bericht und keine Abschlussmarker.
- `00009`: Tasks/QC weitgehend X, aber Spec Draft und Marker fehlen. Der offene CHL001–003-Index ist stale; alle 16 eigentlichen Child-Checks sind X und werden **nicht** als drei Produktlücken gezählt.
- `00014`: T001–T009 offen, Planphasen offen, gleichzeitig QC PASS und Marker vorhanden. Nur T004/T006/T007 sind durch Codebeleg als partial klassifiziert; „neun Funktionen fehlen“ wäre unehrlich.
- `00017`: `spec.md` fehlt; 13 Tasks X. Das ist eine Traceability-Lücke, nicht 13 offene Requirements.
- README `179-193`: 13 ungecheckte Smoke-Punkte sind eine ungeführte Betriebscheckliste, nicht automatisch 13 Defekte.
- Brain-Plan `2026-06-10-fix-full-audit`: vier Phasen offen, während Repository/CLAUDE Abschluss behaupten.
- GUI-QA-Tool: `scripts/run_gui_release_gate.py --help` crasht reproduzierbar mit `ValueError: incomplete format` wegen unescaped `%`; explizite Argumente funktionieren.

## 10. Requirement-ID-Kollisionen

33 ID-Gruppen werden feature-lokal wiederverwendet. Besonders kritisch sind 17 semantisch verschiedene IDs in `00018` und `00019`:

```text
FR-354 FR-355 FR-356 FR-357 FR-358 FR-359
TR-356 TR-357 TR-358 TR-359 TR-360
OR-338 OR-339 OR-340
SC-084 SC-085 SC-086
```

Beispiele:

- `00018/FR-354` = Beat-Cache; `00019/FR-354` = Funktionskatalog.
- `00018/OR-338` = CUDA/ROCm/NVENC-Verbot; `00019/OR-338` = Write-Scope.
- `00018/SC-084` = Regressionen/HIGH-Funde; `00019/SC-084` = Funktionskatalog-Abdeckung.

Ältere feature-lokale Wiederverwendungen betreffen `FR-001..006`, `TR-001..006`, `SC-001..004`. In diesem Bericht gilt deshalb immer `Workspace/Objective/ID` statt ID allein.

## 11. Nicht als offene Produktanforderung gezählt

- LOCKED Stem-DirectML-Pfad: beide ORT-Speicherflags, CPU-EP-Sperre, Patch-Serialisierung und `finally`-Restore sind belegt.
- Stem-Artefakt-Reuse prüft Source-/Modellidentität, Rollen, Dateigröße und Decode-Vollständigkeit.
- Long-Mix-Chunking/Resume und DB-first terminales Audio-SSE sind vorhanden.
- Live-SQLite/FAISS/Recovery-Integrität ist aktuell grün; D-03/D-09 sind deshalb Risiko/Nachweisgap, kein behaupteter Live-Datenfehler.
- Historische FAILED-Sektionen alter Auditberichte werden nicht erneut gezählt, wenn aktueller Code/Tests sie widerlegen.
- 00009-Checklist-Index, 00017-Tasks, README-Smoke-Checkboxen und alte Branches werden nicht künstlich als Produktlücken vervielfacht.
- Supersedete Brain-768-D/torch-directml- und SAD-CPU-Fallback-Aussagen gelten nur als Dokumentkonflikt, nicht als zulässige aktuelle Architektur.
- VFX/Live-VJ/Cloud-/Kollaborationsideen sind laut PRD/ADRs außerhalb des aktuellen Scopes und werden nicht als fehlend geführt.

## 12. Schlussstatus

Der aktuelle Stand ist **nicht requirements-complete und nicht release-ready**. Die sicher kanonisch offenen Gates sind OBJ76 T003/T019 und E010. Darüber hinaus belegt der Source-to-Consumer-Audit die oben einzeln aufgeführten Missing-/Partial-Pfade in allen fünf verlangten Bereichen. Build und große Teile der Tests sind grün, aber zwei Python-Vollsuite-Fehler, das aktuelle GUI-DPI-Gate, die 17 ungültigen SDD-Workspaces und mehrere ausdrücklich ungemessene PRD/SAD-KPIs verhindern eine ehrliche Vollständigkeits- oder Releasebehauptung.
