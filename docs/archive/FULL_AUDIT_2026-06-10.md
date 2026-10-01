# Full-Stack-Audit PB Studio (AMD Premium Edition) — 2026-06-10

**Methode:** 7 parallele Tiefenanalysen (Backend, Core+Data, Audio, Video/AI/Pacing/Rendering, WPF-Frontend, Verkabelung FE↔BE, Scripts/Config/IRON-RULES) + dynamische Checks (py_compile über 296 Dateien: 0 Fehler) + Stichproben-Verifikation aller per Sandbox prüfbaren 🔴-Funde durch den Hauptauditor.
**Regel:** Reines Audit — **keine einzige Datei wurde geändert.**
**Abdeckung:** backend/ vollständig (28 Dateien), src/pb_studio core/data/storage/utils/models vollständig (6259 LOC), audio/ vollständig (20 Dateien), pacing/rendering/video/ai/services tief + brain stichprobenartig, PBStudio.UI Services+16 ViewModels+Views vollständig, 58 Frontend-Calls gegen 61 Backend-Routen gematcht, alle Build-/Test-Scripts, Repo-weiter IRON-RULES-Grep.

---

## Executive Summary

Die Codebasis ist insgesamt überdurchschnittlich defensiv (viele dokumentierte Fix-Marker halten der Prüfung stand, HTTP-Verkabelung mit **0** harten 404/422-Mismatches), aber das Audit findet **11 kritische (🔴), ~49 hohe (🟠), ~79 mittlere (🟡) und ~23 niedrige (🟢) Befunde**. Die gravierendsten Probleme treffen genau das Kernversprechen des Produkts: **beat-genaue Schnitte** (wirkungsloses Duration-Capping → kumulativer Drift; Concat ohne `concatdec_select` → GOP-Versatz), **funktionierende Mixed-Footage-Renders** (Codec-Mismatch im Concat), **semantisches Pacing** (sucht im falschen FAISS-Index → degradiert still), und **Datenintegrität** (FAISS-Kompaktierung desynchronisiert `vector_map`; Projekt-Save beim App-Exit ist toter Code). Mehrere Befunde widersprechen direkt Code-Kommentaren, die das Gegenteil behaupten (IRON-Rule-10-relevant). Sechs der elf 🔴-Funde wurden vom Hauptauditor unabhängig nachverifiziert — alle bestätigt.

---

## 🔴 KRITISCH (11)

| # | Fund | Ort | Kern | Verifiziert |
|---|------|-----|------|-------------|
| K1 | **Duration-Capping wirkungslos → kumulativer Beat-Drift** | `services/pacing_service.py:125–131` (+`:1069`) | `duration` wird nur lokal gekappt, `CutListEntry.end_time` bleibt `next_cut.time`; Renderer schreibt `out_point` > EOF → Segment kürzer als Slot → alle Folge-Cuts rutschen nach vorn, Beat-Sync bricht. Manueller Pfad (`_cap_entries_against_source`) macht es korrekt — Auto-Pfad nicht. | ✅ Code-Zitat nachgeprüft |
| K2 | **Concat-Codec-Mismatch bei Mixed Footage** | `rendering/render_service.py:247–309` | Normalisierung prüft nur Auflösung/FPS, nicht Codec/PixFmt/SAR/Audio-Streams. Default `hevc_amf` + unberührte H.264-Originale → gemischte Concat-Liste → Decode-Fehler/korruptes Output. Transkodierte Clips `-an`, Originale mit Audio → Stream-Count-Mismatch. | Statisch (FFmpeg-Semantik) |
| K3 | **Semantic-Pacing sucht im falschen FAISS-Index** | `pacing_service.py:525,772` vs. `semantic_matcher.py:166` | PacingService injiziert `VectorStore()` = `main_index`; Video-Embeddings liegen in `video_index` → semantischer Pfad findet nie etwas, degradiert still auf Motion. Singleton-mit-Index-Wechsel verursacht zusätzlich Index-Reload-Thrashing. | Statisch (Grep beide Seiten) |
| K4 | **FAISS-Kompaktierung renumbert IDs ohne vector_map-Sync** | `data/vector_store.py:283–318` | Auto-Kompaktierung (≥100 Tombstones, ≥20%) vergibt neue IDs, `vector_map` (faiss_id→media_id) wird nie aktualisiert → spätere Löschungen tombstonen die **falschen** Vektoren. Stille Suchindex-Korruption ab ~100 Löschungen. | ✅ kein `UPDATE vector_map` im Modul |
| K5 | **SubtrackDetector: S2/S4-Signale zeitlich falsch (Truncation statt Interpolation)** | `audio/subtrack_detector.py:262–268, 314–320` | Stem-Aktivität+Spectral-Flux (~43 fps) werden auf die 1-fps-Fusionsachse **abgeschnitten** statt interpoliert — bei 90-min-Mix landen nur die ersten ~125 s, über die ganze Timeline verteilt. 45 % des Fusionsgewichts sind temporal Garbage. | Statisch (Code-Zitat) |
| K6 | **GET /audio/onsets: ~4× gestauchte Zeiten bei Clips >10 min** | `audio_router.py:428–435` vs. `streaming_analyzer.py:127–135` | Onset-Endpoint nimmt fest 43.07 fps an, Streaming-Energy-Curve hat ~10.77 fps (downsample 4) → Onset bei 400 s wird als ~100 s gemeldet. | Statisch (beide Konstanten belegt) |
| K7 | **WPF: Projekt-Save beim App-Exit ist toter Code** | `App.xaml.cs:140–150`, `ApiClient.cs:34–41,698–715` | `BeginShutdown()` cancelt `_shutdownCts` VOR `SaveProjectAsync()`; `PostAsync` nutzt genau dieses Token → sofortige `TaskCanceledException`, geschluckt → Save-on-Exit geht **nie** raus. Datenverlust-Risiko. | ✅ Reihenfolge Z.140 vor Z.148 nachgeprüft |
| K8 | **AnchorViewModel: Collection-Updates ohne Dispatcher** | `AnchorViewModel.cs:101–117,185,221,304,343` | `ProjectOpenedMessage` kommt vom Background-Thread; AnchorVM mutiert ObservableCollections ohne `Dispatcher.InvokeAsync` (alle anderen VMs machen es korrekt) → Exception wird als unobserved geschluckt → Anchor-Tab lädt still nicht. | Statisch |
| K9 | **setup.bat & test.bat verlieren Exit-Codes (False-Green)** | `setup.bat:64–66`, `test.bat:33–35` | `powershell -Command "& $ps1 ...| ForEach..."` ohne `; exit $LASTEXITCODE` → Wrapper meldet Erfolg auch bei `exit 1` im Script. `start.bat:79` enthält das korrekte Pattern bereits — die anderen beiden nicht. Direkter Konflikt mit IRON Rule 10. | Statisch (PS-5.1-Semantik) |
| K10 | **Setup baut Debug; Launcher kann Debug-EXE laden** | `setup_pb_studio.ps1:683`, `launch.ps1:387–404` | `dotnet build` ohne `-c Release`; `Resolve-FrontendExe` wählt die *neueste* EXE und listet `bin\Debug\...` als Kandidat → exakt die Trust-Incident-Klasse 2026-05-08 (User testet altes/falsches Binary). | Statisch |
| K11 | **VRAMArbiter.evict_if_needed: Tuple-vs-Int-TypeError + verlorene Unload-Callbacks** | `core/vram_arbiter.py:256–257` | `_evict_for_space` liefert seit B-3 `tuple[int, list]`, Aufrufer vergleicht `freed >= required_mb` → TypeError; Callbacks laufen nie. Aktuell kein Caller (latent), aber öffentliche API. | Statisch |

---

## 🟠 HOCH (Auswahl der wichtigsten, vollständige Listen in den Schicht-Abschnitten unten)

**Cross-Layer / GPU:**
- **`with_gpu_task`: VRAM-Reservierungs-Leak bei Cancellation + Zombie-GPU-Thread nach Timeout** (`backend/dependencies.py:50–145`) — Reservierung vor Lock ohne try/finally; nach `wait_for`-Timeout läuft der Worker weiter auf der GPU während der Lock freigegeben wird → parallele DirectML-Inferenz, genau das, was der Lock verhindern soll. *(Von zwei Agenten unabhängig gefunden.)*
- **Eviction bucht VRAM aus ohne physisches Entladen** (`vram_budget_manager.py:784–831`) — Callback-Failure lässt Buchhaltung "frei", Modell bleibt im VRAM → Overcommit/OOM; 16 pre-registrierte Budgets haben gar keinen unload_callback.
- **GPU-Lock wird über lange CPU/LM-Studio-HTTP-Phasen gehalten** (`video_router.py:464–1065`) — Scene-Detection + Captioning blockieren Stems/Renders.
- **Toter Zombie-Watcher-Check:** `get_app_state().is_render_active()` existiert nicht; AttributeError wird als debug geschluckt → Schutz wirkungslos (`main.py:176`). ✅ verifiziert: einziger Treffer im Repo ist der Aufruf selbst.

**Backend:**
- HTTPException 400→500-Umwandlung in pacing_router (`:154,187`); `/shutdown` via SIGTERM = harter Kill auf Windows (Lifespan-Teardown läuft nie, Kommentar behauptet Gegenteil); blockierender ffprobe im Event-Loop (`pacing_router.py:272`); FAISS-Metadaten `duration`/`segment_end` immer 0.0 (`video_router.py:922–927`); Brain-`state_conn`-Write ohne `db_write_lock` (`pacing_router.py:145`).

**Core/Data:**
- **Migrations-Atomicity kaputt:** `executescript` committet das explizite BEGIN — "B-9 FIX" wirkungslos; **empirisch in Sandbox verifiziert** (Teilzustand nach Rollback persistiert). `migration_runner.py:36–44`, `embedding_repository.py:122–133`.
- LHM `Hardware.Update()` ohne Lock aus mehreren Threads (AccessViolation-Risiko, `system_monitor.py:181–222`); VectorStore-Background-Saves ohne Ordering (älterer Snapshot kann neueren überschreiben).

**Audio:**
- Korrupte/0-Byte-Drums-Stem killt Beat-Detection komplett, kein Mix-Fallback (Non-Streaming-Pfad); `stems_paths` als JSON-String → HTTP 500 in /audio/analyze; Energy-Curve wechselt bei Stems still auf Drums-only-Semantik; Beat-Strengths >600 s sind Bogus (Snapshot-Clamping); WaveformAnalyzer Full-Load @44.1 kHz + sosfiltfilt-float64 → OOM-Risiko bei 90-min-Mixen; **htdemucs läuft faktisch komplett auf CPU** (PyTorch 2.4.1+cpu — die CLAUDE.md-Aussage "Demucs patched for DirectML" gilt nur für die ONNX-MDX-Pfade) + versteckter CPU-EP-Fallback in separator.py (LOCKED, nur Befund); SubtrackDetector beim Import: ~5400 beat_track-Calls für 90 min synchron im Import-Request.
- **Strukturlücke:** Kein Stem-Modell liefert beide Feature-Hälften — htdemucs hat kein `instrumental` (Key läuft weiter auf Mix), MDX hat keine `drums` (Beats laufen weiter auf Mix). Der Fix vom 2026-06-09 ist im Happy-Path korrekt verdrahtet, aktiviert aber je Modell nur die halbe Pipeline.

**Pacing/Rendering:**
- `RAFTOpticalFlow` existiert nicht → ImportError geschluckt → Clip-Motion-Analyse nutzt immer den groben Frame-Diff-Fallback (✅ verifiziert: Klasse nirgends definiert); fehlender `Path`-Import in clip_selector.py → latenter NameError im Bridge-Pfad (✅ verifiziert: kein pathlib-Import, 4× `Path(`); stille libx264/CPU-Fallback-Kette im Final-Render (IRON-Rule-4-Spannung, kein User-Signal); Concat ohne `select=concatdec_select` → Schnitte bis 1 GOP zu früh; bare `"ffmpeg"` statt aufgelöstem Pfad in render_service; export_for_ffmpeg schreibt Double-Quote-Concat-Dateien (für FFmpeg unbrauchbar); hartkodierter `C:/Users/david/Desktop/...Crusty_Storyboard.canvas`-Default injiziert still Storyboard-Clips; VideoMotionWorker liefert stille Null-Motion-Daten wenn RAFT-Modell fehlt; RenderWorker-Pipeline drifted bei kurzen Clips (Zufalls-Seek + stilles Segment-Filtern).

**WPF:**
- HttpClient-Timeouts werden als "erwartete Cancellation" geschluckt (silent null, kein Log); 10-min-Timeout < 15-min-Backend-`stem_timeout` → UI meldet Fehler obwohl Backend erfolgreich fertig wird; `async void OnExit` racy → uvicorn-Zombie auf 8765 möglich (kein Job Object); `BackendReadyMessage`/`ProjectClosingMessage` werden nirgends gesendet (tote Verdrahtung, Settings-Tab zeigt "Offline"); tote Bindings `SceneIndex`/`MotionScore` in VideoLibraryView; Analyse-Commands ohne Reentry-Gates (parallele GPU-Jobs möglich); WaveformRenderer/DepthRenderer reagieren nicht auf in-place Collection-Mutationen (Waveform erscheint erst bei Zoom/Resize); TimelineViewModel injiziert konkreten `ApiClient` → zweite Instanz, `BeginShutdown` greift dort nicht; Chat-History `.Take(40)` sendet die **ältesten** statt neuesten Nachrichten; Video-Grid-Virtualisierung wirkungslos (WrapPanel).

**Verkabelung (SSE-Schicht — HTTP ist sauber):**
- `pacing_progress` wird published, aber vom Server-Filter verworfen UND vom Client nicht geparst → L-M7-Feature komplett tot (✅ Filter-Set verifiziert); `stem_progress` erreicht den Client, aber **kein** ViewModel konsumiert es → kein Fortschritt während bis zu 15-min-Demucs; `POST /pacing/timeline` droppt `brain_confidence`+`cut_id` → Brain-Daten gehen bei jedem manuellen Timeline-Save verloren, Feedback unmöglich; Timeout-Gefälle Stems (s.o.).

**Scripts/Config:**
- `--no-elevation` leckt als positionaler `$LogFile`-Parameter; run_full_test.ps1 verschluckt UI-Agent-Exit-Code + räumt GUI-Prozess nie auf; verify_release_smoke.ps1 setzt `$global:LASTEXITCODE = 0` im finally (maskiert Fehler) + hartkodierter User-Pfad; coverage_run_v2.bat nutzt Unix-`head` + falsche Redirect-Reihenfolge; **torchaudio ungepinnt** — .venv enthält torchaudio 2.11.0 neben torch 2.4.1 (verletzt LOCKED-VERSIONS-Logik, Laufzeitwirkung unverifiziert); `tools/hooks/preflight.ps1`+`project.json` referenzieren `C:\Users\david\Dokumente\...` statt `Documents`.

---

## 🟡 / 🟢 (Zusammenfassung — Details in den Agenten-Protokollen)

~79 mittlere und ~23 niedrige Funde, u. a.: httpx-Client-Leaks in models_router; Reset-Tokens ohne TTL; tote tiktoken-Logik (Doku ≠ Verhalten); `register_audio_clip`-Reuse verliert `stems_paths`; SSE-Queue-Leak bei nie gestartetem Generator; CORS `"null"`-Origin + fehlendes DELETE in allow_methods; Render-Complete-vs-Cancel-Race kann fertiges Output löschen; VRAMBudgetManager-`__init__`-Race; DatabaseCore-Connections toter Threads; BrainStore `patterns_conn` ohne Lock; EmbeddingRepository stale Thread-locals nach close(); EmbeddingCache 16-Zeichen-Hash-Kollision; Migration-Version = Listenindex; `bulk_update_status([])` → invalides SQL; TaskQueue = totes Modul ohne Worker; `torch.cuda` in recovery_handler (Rule-1-Verstoß, funktional harmlos); Streaming-Beat-Dedup zu schwach an Chunk-Grenzen; DJ-Mix-Branch im Backend unerreichbar (`600.0 > 600` = False); Modellnamen-Drift Worker `htdemucs_ft` vs. Schema `htdemucs.yaml`; VRAM-Doppel-Reservierung bei Stems; libx264 als Preview-Primär-Encoder obwohl `get_preview_encoder()` existiert; `_plan_beat_sync`-Endlosschleifen-Risiko bei Beat-Duplikaten; Theme-Bonus +1000 dominiert alle Heuristiken; SMPTE-Timecode rundet fps auf int; AnchorManager-JSON nicht atomar; WeightStore-Writes ohne Lock; `persist_error`-Event versandet serverseitig; `gpu_error` erreicht Client, kein VM reagiert; Video-Analyse ohne Timeout-Override gegen 300-s-Default; SSEClient stirbt endgültig nach 50 Fehlversuchen; Anchors werden nie persistiert (Feature-Torso); 4 Model-Download-Scripts setzen nur 1 von 2 DirectML-Flags; systemweites `taskkill /F /IM python.exe`; 3 tote Backend-Endpoints.

---

## Verifiziert OK (Highlights)

- **IRON Rule 1/4/5:** Kein pynvml/nvidia-smi/gpustat/CUDAExecutionProvider im aktiven Code (repo-weiter Grep, 0 Treffer); `torch.cuda` nur als harmloser Negativ-Check in recovery_handler; nvenc/cuda-Treffer nur in mitgelieferter FFmpeg-Doku; Encoder-Priorität korrekt AMF-first.
- **IRON Rule 2:** Alle produktiven `InferenceSession`-Erstellungen (clap, siglip, model_loader, moondream, raft, separator) setzen **beide** Flags. Ausnahme: 4 Download-/Export-Scripts (🟡).
- **IRON Rule 3/8:** numpy==1.26.4 ✓, alle LOCKED-Versionen bis auf torchaudio ✓, `testpaths = Tests` großgeschrieben ✓.
- **HTTP-Verkabelung:** 58/58 Frontend-Calls matchen Backend-Routen, 0 Methoden-/Pfad-/Schema-Mismatches; snake_case-Naming-Policy deckungsgleich; Enum-Werte (Quality/Encoder/StemModel) konsistent.
- **Sicherheit:** Path-Traversal-Schutz in project/render-Routern hält; kein `shell=True`, kein SQL-String-Concat im gesamten Repo; Concat-Escaping in render_service korrekt.
- **Kein Deadlock-Muster** (.Result/.Wait) im WPF-Code; MVVM-Hygiene durchgängig CommunityToolkit; SSE-Parsing/Reconnect robust; py_compile: 296 Dateien, 0 Syntaxfehler.

---

## Selbstkritik / Limitierungen (Pflichtteil)

1. **Keine Live-Ausführung auf dem Zielsystem:** pytest/DirectML/WPF konnten in der Linux-Sandbox nicht laufen (onnxruntime-directml, .NET 9 WPF, AMF sind Windows/AMD-gebunden). Alle Laufzeit-Aussagen (FFmpeg-Concat-Symptomatik, LHM-AccessViolations, PowerShell-Exit-Code-Verhalten, torchaudio-Kompatibilität) sind aus Code/Spezifikation hergeleitet, nicht reproduziert. Einzige Ausnahme: der executescript-Migrations-Befund wurde **empirisch in der Sandbox verifiziert**.
2. **Stichproben-Verifikation:** 6 der 11 🔴-Funde habe ich selbst per Grep/Read nachgeprüft (alle bestätigt); die übrigen 5 (K2, K3, K5, K6, K8) beruhen auf Agent-Evidenz mit Code-Zitaten — Restrisiko von Fehlinterpretationen bleibt.
3. **Nicht tief geprüft:** `src/pb_studio/brain/` (nur Stichprobe weight_store), `Generated/ApiTypes.g.cs` (3836 Zeilen, nur Stichproben), moondream-Decoder-Loop, chat_agent-Internals, `scripts/qa/*`, Tests/-Inhalte selbst, Bestands-Datenbanken.
4. **Doppelzählung möglich:** Die Gesamtzahlen sind nach bestem Wissen dedupliziert (1 bekannte Überschneidung: `with_gpu_task`), Restüberschneidungen zwischen Schichten nicht ausgeschlossen.
5. **Obsidian-Vault (IRON Rule 11):** In dieser Session kein Zugriff auf `C:\Users\david\Brain\...` (außerhalb des gemounteten Ordners, keine obsidian-MCP-Tools verfügbar) — Vault-Sync zu diesem Audit steht aus und muss nachgeholt werden.
6. **Annahme:** `ui_legacy_archived/`, `archive/`, `bin/`, `obj/`, `__pycache__` wurden bewusst ausgeklammert.

---

## Empfohlene Fix-Reihenfolge (Vorschlag, NICHT umgesetzt)

1. **K1 + K2** (Beat-Drift + Codec-Mismatch) — Kernfunktion Rendern/Sync.
2. **K4** (vector_map-Drift) — stille Datenkorruption, wächst mit Nutzung.
3. **K7 + K9 + K10** (Save-on-Exit, Exit-Codes, Debug-Build) — Datenverlust + Trust-Incident-Klasse.
4. **K3 + RAFT-Importfehler + Path-Import** (Semantic-Pacing-Kette) — drei kleine Fixes, großer Feature-Gewinn.
5. **with_gpu_task-Leak + Eviction-Buchhaltung** — GPU-Stabilität unter Last.
6. **K5 + K6 + Stems-Folgeprobleme** — Audio-Analyse-Qualität.
7. SSE-Lücken (pacing_progress, stem_progress, brain_confidence-Roundtrip) — sichtbare UX-Gewinne, kleine Fixes.
