# Tasks: OBJ-77 Vollstaendige Anforderungsremediation

**Status:** OPEN  
**Spec:** `specs/00022-complete-requirements-remediation/spec.md`  
**Plan:** `specs/00022-complete-requirements-remediation/plan.md`

## Audio - Wave 1 und Wave 2

- [ ] T001 [OBJ-77] {(FR-406)} {(FR-403)} A-01: Downbeats im Livepfad berechnen, in `src/pb_studio/audio/` persistieren und Nichtverfuegbarkeit begruenden
- [ ] T002 [OBJ-77] {(FR-406)} A-02: Fortlaufende bar_number erzeugen und in `PBStudio.UI/` als BAR 1, BAR 2 und folgende darstellen
- [ ] T003 [OBJ-77] {(FR-403)} {(TR-385)} A-03: Versionierte Audio-StageReceipts mit Fingerprints, Artefaktvaliditaet und Zeiten in `backend/routers/audio_router.py` umsetzen
- [ ] T004 [OBJ-77] {(FR-404)} A-04: Startup-Recovery laufender Audio-Stages in `backend/app_state.py` atomar auf interrupted setzen
- [ ] T005 [OBJ-77] {(FR-403)} {(FR-404)} A-05: Fruehe und globale Audiofehler vor terminalem SSE in `backend/routers/audio_router.py` pro Clip und Stage persistieren
- [ ] T006 [OBJ-77] {(FR-403)} {(TR-387)} A-06: Audio-Status und Fehler in `PBStudio.UI/ViewModels/` vollstaendig und retry-faehig anzeigen
- [ ] T007 [OBJ-77] {(FR-406)} A-07: Mel-Spektrogramm durch Producer, Persistenz, API und `PBStudio.UI/` verdrahten
- [ ] T008 [OBJ-77] {(FR-406)} A-08: Depth-Toggle, No Depth Data und gezielte Reanalyse in `PBStudio.UI/` und Audio-API implementieren
- [ ] T009 [OBJ-77] {(FR-406)} A-09: Long-Mix-Sektionen Intro, Verse, Chorus, Bridge, Outro und Drop in `src/pb_studio/audio/` erzeugen
- [ ] T010 [OBJ-77] {(FR-406)} A-10: Key-Ermittlung in `src/pb_studio/audio/` auf Originalmix oder Instrumental beschraenken und Drums ausschliessen
- [ ] T011 [OBJ-77] {(FR-406)} A-11: Clip-Spektrum aus Originalmix und getrennte Stem-Spektren in `src/pb_studio/audio/` sicherstellen
- [ ] T012 [OBJ-77] {(FR-406)} A-12: Audioimport und Invalidierung in `backend/routers/audio_router.py` an Inhalts- und Config-Hash binden
- [ ] T013 [OBJ-77] {(FR-406)} A-13: sub_bpm und sub_key pro Subtrack in `src/pb_studio/audio/` produzieren und persistieren
- [ ] T014 [OBJ-77] {(FR-406)} {(TR-388)} {(TR-389)} A-14: Subtrack-F1 und 2h-Lauf mit realen annotierten Medien unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T015 [OBJ-77] {(FR-406)} {(TR-388)} {(TR-389)} A-15: Reale 1-4h-Mixe unter 0,5x Echtzeit ohne Freeze messen und unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T016 [OBJ-77] {(FR-406)} {(TR-388)} {(TR-389)} A-16: Section-Alignment und Depth-Latenz/FPS unter `specs/00022-complete-requirements-remediation/evidence/` messen
- [ ] T017 [OBJ-77] {(FR-406)} {(TR-386)} A-17: Atomare komprimierte Depth-Sidecars in `src/pb_studio/storage/` speichern und migrieren
- [ ] T018 [OBJ-77] {(FR-406)} {(FR-404)} A-18: has_audio_embedding nach Write und Reload in `backend/app_state.py` und `PBStudio.UI/` aktualisieren
- [ ] T019 [OBJ-77] {(FR-406)} {(FR-404)} A-19: Waveformfehler in `backend/routers/audio_router.py` von legitimer Leere unterscheiden und Retrygrund liefern
- [ ] T020 [OBJ-77] {(FR-406)} A-20: Waveformvertrag fuer ein bis acht erzeugte Baender in `src/pb_studio/audio/` und API erfuellen
- [ ] T021 [OBJ-77] {(FR-406)} {(FR-412)} A-21: SDD-Dokumente unter `specs/` auf produktive structure-, spectral- und analyze-Vertraege korrigieren
- [ ] T022 [OBJ-77] {(FR-406)} {(FR-412)} A-22: Architekturkarte unter `docs/` auf direkten Routerpfad und 600s-Streaming-Schwelle korrigieren
- [ ] T023 [OBJ-77] {(FR-406)} {(FR-412)} A-23: Supersedete CPU-Retry- und madmom-Aussagen unter `docs/` entfernen

## Video - Wave 1 und Wave 3

- [ ] T024 [OBJ-77] {(FR-403)} {(TR-385)} V-01: Video-Receipts mit Provider, Modell, Attempts, Zeiten und Clip-Korrelation in `backend/routers/video_router.py` persistieren
- [ ] T025 [OBJ-77] {(FR-407)} {(FR-404)} V-02: Persistierte Tags und tag_source nach Reload in `backend/routers/video_router.py` und `PBStudio.UI/` liefern
- [ ] T026 [OBJ-77] {(FR-404)} V-03: Angeforderte unavailable-Stages mit Grund als Partialstatus in `backend/routers/video_router.py` ableiten
- [ ] T027 [OBJ-77] {(FR-404)} V-04: Valide Partial-Stages nach Restart in `backend/app_state.py` laden und Pacing-DB-Fallback liefern
- [ ] T028 [OBJ-77] {(FR-407)} V-05: Lokale FAISS-1152-Content-Suche in `backend/routers/video_router.py` und `PBStudio.UI/` verdrahten
- [ ] T029 [OBJ-77] {(FR-407)} {(FR-411)} V-06: 10k-Library mit Paging, Recycling und Viewport-Thumbnails in `backend/` und `PBStudio.UI/` skalieren
- [ ] T030 [OBJ-77] {(FR-407)} V-07: Random-Seeks aus produktiven Extraktionsloops in `backend/routers/video_router.py` und `src/pb_studio/video/` entfernen
- [ ] T031 [OBJ-77] {(FR-407)} {(TR-384)} V-08: RAFT-DirectML-Framevergleich in `src/pb_studio/video/scene_detect.py` produktiv integrieren
- [ ] T032 [OBJ-77] {(FR-407)} {(FR-404)} V-09: Neu angeforderte Stages trotz IsAnalyzed in `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs` ergaenzen
- [ ] T033 [OBJ-77] {(FR-407)} {(TR-388)} {(TR-389)} V-10: Reales Tagging, Degradation, Shutdown und Resume unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T034 [OBJ-77] {(FR-407)} {(OR-364)} V-11: Nach eigenem Go zehn Clips mit 10/10 Receipts und stabilen Hashes unter `specs/00022-complete-requirements-remediation/evidence/` pruefen

## Pacing und Timeline - Wave 1 und Wave 4

- [ ] T035 [OBJ-77] {(FR-408)} P-01: Used-, Excluded- und Rejected-Clips samt Gruenden in `backend/routers/pacing_router.py` und `PBStudio.UI/` zeigen
- [ ] T036 [OBJ-77] {(FR-408)} P-02: Fehlende Stems in `backend/routers/pacing_router.py` als explizite Degradation melden
- [ ] T037 [OBJ-77] {(FR-408)} P-03: min_cut_interval in `backend/schemas/pacing_schemas.py` kanonisieren und Konflikte mit 422 ablehnen
- [ ] T038 [OBJ-77] {(FR-408)} {(FR-411)} P-04: Timeline-Collections in `PBStudio.UI/` viewport- und pixelbasiert begrenzen
- [ ] T039 [OBJ-77] {(FR-408)} {(FR-411)} P-05: Ruler in `PBStudio.UI/` nach Viewport, Zoom und DPI cachen
- [ ] T040 [OBJ-77] {(FR-408)} {(TR-388)} P-06: UI-Massenupdates in `PBStudio.UI/ViewModels/` auslagern und real messen
- [ ] T041 [OBJ-77] {(FR-408)} {(FR-412)} P-07: Dokumentation unter `docs/` ausschliesslich auf TriggerSettings und generate_cut_list ausrichten
- [ ] T042 [OBJ-77] {(FR-404)} P-08: Pending Timeline-Writes vor Save, Close, Wechsel und Exit in `PBStudio.UI/` awaiten
- [ ] T043 [OBJ-77] {(FR-408)} P-09: Drag, Trim, Snap, Playhead, Preview, Persistenz und Reload in `PBStudio.UI/` abnehmen
- [ ] T044 [OBJ-77] {(FR-408)} {(TR-388)} {(TR-389)} P-10: Cut-Accuracy ueber 98 Prozent unter `specs/00022-complete-requirements-remediation/evidence/` messen
- [ ] T045 [OBJ-77] {(FR-408)} {(TR-388)} {(TR-389)} P-11: Preview- und Export-Sync-Drift unter 10 ms unter `specs/00022-complete-requirements-remediation/evidence/` messen
- [ ] T046 [OBJ-77] {(FR-408)} {(TR-388)} {(TR-389)} P-12: Onset-, Kick-, Snare- und HiHat-Regler auf realem DJ-Mix unter `specs/00022-complete-requirements-remediation/evidence/` belegen

## KI, Modelle und UI - Wave 1 und Wave 5

- [ ] T047 [OBJ-77] {(FR-409)} K-01: Captioning und Modellkarten aus demselben Resolver in `src/pb_studio/ai/` und `PBStudio.UI/` speisen
- [ ] T048 [OBJ-77] {(FR-409)} K-02: KI-Modus debounced in `PBStudio.UI/` synchronisieren und bei Fehler zurueckrollen
- [ ] T049 [OBJ-77] {(FR-409)} K-03: Modellkarten in `PBStudio.UI/ViewModels/` nach erfolgreicher Synchronisierung aktualisieren
- [ ] T050 [OBJ-77] {(FR-409)} {(FR-412)} K-04: Status von Workspace 00014 additiv unter `specs/00022-complete-requirements-remediation/` aufloesen
- [ ] T051 [OBJ-77] {(FR-409)} K-05: Manifest- und Hashbindung in `config/directml-model-assets.json` im konvergierten Stand sichern
- [ ] T052 [OBJ-77] {(FR-409)} {(TR-388)} K-06: Live-Inventar, Capabilities, Overrides und verwendete Modelle unter `specs/00022-complete-requirements-remediation/evidence/` pruefen
- [ ] T053 [OBJ-77] {(FR-409)} {(TR-388)} K-07: Brain-Deep-Hook mit real geaenderter Clipauswahl unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T054 [OBJ-77] {(FR-409)} K-08: Feedback-Operation-ID und Achsenvertrag in `src/pb_studio/brain/` regressionssichern
- [ ] T055 [OBJ-77] {(FR-409)} K-09: Projektgebundene Chat-History und typisierte Streamfehler in `backend/routers/` regressionssichern
- [ ] T056 [OBJ-77] {(FR-409)} K-10: Projector-Generation, Pending Events, Checkpoint und Copy-on-write in `src/pb_studio/brain/` pruefen
- [ ] T057 [OBJ-77] {(FR-409)} {(OR-365)} K-11: Dormante PyTorch-Loader erst nach separater Freigabe in `src/pb_studio/` entfernen
- [ ] T058 [OBJ-77] {(FR-409)} {(TR-388)} K-12: llm_status fuer Chat und Brain-Explain real in `PBStudio.UI/` beobachten
- [ ] T059 [OBJ-77] {(FR-409)} K-13: Toten PauseCommand in `PBStudio.UI/` entfernen und Play/Pause-Vertrag testen
- [ ] T060 [OBJ-77] {(FR-409)} K-14: 200-Prozent-DPI-Groesse und KI-Modus-Slider in `PBStudio.UI/` reparieren
- [ ] T061 [OBJ-77] {(FR-409)} {(TR-388)} K-15: P95-UI-Latenz unter zwei Sekunden unter `specs/00022-complete-requirements-remediation/evidence/` messen
- [ ] T062 [OBJ-77] {(FR-409)} {(TR-384)} {(TR-388)} K-16: DirectML-Matrix auf realer AMD-, Intel- und NVIDIA-Hardware unter `specs/00022-complete-requirements-remediation/evidence/` ausfuehren
- [ ] T063 [OBJ-77] {(FR-409)} K-17: Gemeinsame Portkonfiguration und ConfigureAwait-Regeln in `PBStudio.UI/` umsetzen
- [ ] T064 [OBJ-77] {(FR-409)} K-18: Binding-Guard pro View und ViewModel in `Tests/` implementieren
- [ ] T065 [OBJ-77] {(FR-409)} {(TR-388)} K-19: Alle 14 Views in Normal, Loading, Empty, Error und High Contrast unter `specs/00022-complete-requirements-remediation/evidence/` pruefen

## Datenbank, Resilienz und Governance - Wave 1 und Wave 6

- [ ] T066 [OBJ-77] {(FR-405)} {(TR-386)} D-01: sqlite-vec in `src/pb_studio/storage/` produktiv an Brain-KNN verdrahten und FAISS beibehalten
- [ ] T067 [OBJ-77] {(FR-405)} D-02: Manifestdimension, dtype, Finite- und Nullvektorpruefung in `src/pb_studio/storage/` erzwingen
- [ ] T068 [OBJ-77] {(FR-405)} {(OR-366)} D-03: Vector-Writer in `src/pb_studio/storage/` owner-, media- und recovery-gebunden machen
- [ ] T069 [OBJ-77] {(FR-410)} D-04: Videoanalysefelder in `backend/app_state.py` vollstaendig aus SQLite rekonstruieren
- [ ] T070 [OBJ-77] {(FR-410)} {(FR-404)} D-05: Partial- und Failed-Analysen mit validen Stages in `backend/app_state.py` und UI laden
- [ ] T071 [OBJ-77] {(FR-410)} D-06: Projekt-ID zu Operationsbeginn in `backend/` erfassen und Fallback auf Projekt 1 entfernen
- [ ] T072 [OBJ-77] {(FR-410)} D-07: busy_timeout 5000 in allen Stores unter `src/pb_studio/storage/` vereinheitlichen
- [ ] T073 [OBJ-77] {(FR-410)} {(TR-388)} D-08: Versionierten 4h-Worker mit 4096-MB-Zwang unter `scripts/` implementieren und real ausfuehren
- [ ] T074 [OBJ-77] {(FR-410)} {(OR-366)} D-09: Suite-Kontamination in `Tests/` beseitigen und Recovery-Owner-Tests deterministisch machen

## OBJ74-Rueckstaende - Wave 4

- [ ] T075 [OBJ-77] {(FR-408)} P-B01: Sensitivity in `src/pb_studio/pacing/` auf Onset-Neuberechnung wirken lassen
- [ ] T076 [OBJ-77] {(FR-408)} P-B02: max_cut_interval in beiden Pacing-Pfaden unter `src/pb_studio/pacing/` als harte Obergrenze erzwingen
- [ ] T077 [OBJ-77] {(FR-408)} P-B03: Mindestlaenge nach Subtrack-Snap in `src/pb_studio/pacing/` erneut validieren
- [ ] T078 [OBJ-77] {(FR-408)} {(FR-405)} P-B04: FAISS-Similarity in `src/pb_studio/pacing/` in den finalen Hybridscore aufnehmen
- [ ] T079 [OBJ-77] {(FR-408)} P-B05: Anker in `backend/routers/pacing_router.py` mit realer clip_id und sicherem Advanced-Pfad verwenden
- [ ] T080 [OBJ-77] {(FR-408)} {(FR-411)} P-B06: Lifecycle, State-Version und Viewport-Fensterung im konvergierten `PBStudio.UI/`-Tree sichern

## Foundation, Konvergenz und Release

- [X] T081 [OBJ-77] {(FR-402)} {(OR-361)} Wave 0: Audit-Baseline und 80-zeiliges Ledger unter `specs/00022-complete-requirements-remediation/evidence/` registrieren
- [X] T082 [P] [OBJ-77] {(OR-363)} Wave 0: Hardware, LM Studio, Testmedien und 4h-Fenster unter `specs/00022-complete-requirements-remediation/evidence/` inventarisieren
- [X] T083 [P] [OBJ-77] {(OR-363)} {(TR-389)} Wave 0: Reale Ground-Truth-Manifeste unter `specs/00022-complete-requirements-remediation/evidence/` registrieren und hashen
- [X] T084 [P] [OBJ-77] {(TR-390)} Wave 0: Python-, C#-, WPF-, OpenAPI-, GUI-, Store- und Recovery-Baselines unter `specs/00022-complete-requirements-remediation/evidence/` erfassen
- [X] T085 [P] [OBJ-77] {(TR-384)} Wave 0: Vollstaendigen DirectML-Session- und Run-Contracttest unter `Tests/` erstellen
- [X] T086 [OBJ-77] {(FR-412)} Wave 0: Historische SDD-Artefakte hashgebunden unter `specs/00022-complete-requirements-remediation/evidence/` inventarisieren
- [ ] T087 [OBJ-77] {(TR-387)} Wave 1: OpenAPI-, Pydantic-, C#-DTO- und Persistenzparitaet in `Tests/` beweisen
- [X] T088 [OBJ-77] {(TR-386)} Wave 1: Backup, Dry-run, Crash-Injection, Restore und Rollback unter `specs/00022-complete-requirements-remediation/evidence/` beweisen
- [ ] T089 [OBJ-77] {(OR-362)} {(TR-390)} Wave 1 bis 6: Jedes gruene Wave-Gate und Merge-SHA unter `specs/00022-complete-requirements-remediation/evidence/` registrieren
- [ ] T090 [P] [OBJ-77] {(FR-412)} Wave 6: Compliance- und qualifizierten Requirement-Registry-Validator unter `scripts/` implementieren
- [ ] T091 [P] [OBJ-77] {(FR-409)} {(FR-412)} Wave 6: GUI-CLI-Hilfe, README-Smokes und Brain-Status in `scripts/` und Dokumentation synchronisieren
- [ ] T092 [OBJ-77] {(TR-391)} Wave 6: Python-Vollsuite zweimal und Recovery-Reihenfolgen unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T093 [OBJ-77] {(TR-387)} {(TR-391)} Wave 6: Native C#-Tests, WPF Release und OpenAPI-Drift unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T094 [OBJ-77] {(TR-388)} {(TR-391)} Wave 6: GUI-, KPI-, LM-Studio-, DirectML-Hardware- und 4h-Live-Gates unter `specs/00022-complete-requirements-remediation/evidence/` belegen
- [ ] T095 [OBJ-77] {(FR-402)} {(TR-391)} Wave 6: Jede Ledgerzeile mit Commit, Test und Evidence unter `specs/00022-complete-requirements-remediation/evidence/` finalisieren
- [ ] T096 [OBJ-77] {(TR-391)} {(OR-362)} Wave 6: PR, Review, Main-Merge, Remote-SHA und Release-Binary unter `specs/00022-complete-requirements-remediation/evidence/` verifizieren
