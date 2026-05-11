# Audit: Audio + Video Pipeline — Import bis Rendering

**Datum:** 2026-05-09
**Auftrag:** Komplette Verdrahtung von Audio- und Video-Daten von Import über Analyse, Pacing, Timeline bis Rendering. Stufen, Endpoints, Services, SSE, UI-Bindings, Bediennelemente, Anzeigen, Lücken.
**Mode:** READ-ONLY (kein Code-Fix). Audit-MD wird NICHT committet.
**Bezug:** Erweitert/verfeinert `AUDIT_DATA_FLOW_2026-05-09.md` (Audit Audio→Pacing-Daten-Mismatch). Dieser Audit deckt zusätzlich Video-Pipeline, Bediennelemente, Anzeigen, Render-Konsumenten und Cross-VM-Refresh ab.

---

## Executive Summary

| Bereich | Stufen | OK | Lücken |
|---|--:|--:|--:|
| Audio-Pipeline (Import → Cache) | 8 | 8 | 0 (Speicherung läuft) |
| Audio-Felder im Pacing-Konsum | 8 | 4 | 4 (key, Beat-Count, beats-Detail, energy_curve teilweise) |
| Video-Pipeline (Import → Cache) | 6 | 6 | 0 |
| Video-Felder im Pacing-Konsum | 8 | 6 | 2 (motion_curve injiziert aber nicht gewichtet, has_embedding indirekt) |
| Render-Konsum aus Pacing | 5 | 5 | n/a (saubere Schnittstelle: file_path + clip_start + duration + audio_path) |
| UI-Bediennelemente | 38 Buttons/Commands über 9 Tabs | 38 | 0 (alle haben Backend-Action) |
| UI-Anzeigen | 47 angezeigte VM-Properties | 33 | 14 Felder werden persistiert ohne UI-Anzeige |
| Cross-VM-Refresh | 11 Messenger-Records | 11 | 0 |

**Kern-Findings:**
1. **Audio-Pipeline persistiert 5 Felder, die kein Pacing-Konsument liest** (`subtrack_segments`, `tempo_curve`, `key`, energy_curve teilweise, structure_segments — letztere zwei sind seit Audit A2/A3 verdrahtet, vorher redundant berechnet).
2. **Video-Pipeline persistiert `motion_curve`, `dominant_colors`, `tags`** — werden seit Audit A4 in `clip_data` durchgereicht, aber `AdvancedPacingEngine`/`ClipSelector` werten sie nicht aktiv aus (Engine hat Helper-API, aber kein aktiver Use).
3. **Render-Pipeline ist clean** — konsumiert NUR `file_path`, `in_point`, `out_point`, `audio_path`. Keine Audio/Video-Analyse-Daten erreichen den Renderer (das ist by-design — Render ist reine FFmpeg-Concat-Ebene).
4. **`UseKeyMatching`-Pipeline ist als no-op verdrahtet** — Flag fließt UI → Schema → Service → Engine, aber Video-Clips haben kein `audio_key`-Feld ⇒ Score-Funktion immer 0.5 (neutral). Ehrliche Bewertung: feature-flag funktional getestet, aber wirkt nicht.
5. **Tab-Header Farbe gepatcht** (separater Mini-Task — siehe `MainWindow.xaml`).

---

# TEIL A — AUDIO PIPELINE

## Stage A1: Import (POST /audio/import)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /audio/import` (`backend/routers/audio_router.py:54-161`) |
| Service-Layer | `state.register_audio_clip` + `_probe_audio_info` (ffprobe) + `media_hash` (sha256-streaming) |
| Core-Module | `pb_studio.core.media_hash`, ffprobe |
| Persistenz | `state.audio_clips[id]` + SQLite via `state.persist_audio_clip` (MediaRepository, ai_data_json leer) |
| SSE-Events | `import_progress` mit step="hash", percent (0..100 per file), Final-Event 100% |
| UI-Binding (Audio-VM) | `AudioLibraryViewModel.OnSseProgressReceived` → `ImportProgress` (gemapped per_file → overall) + `StatusText` |
| UI-Anzeige | `AudioLibraryView.xaml:178-182` — `controls:ProgressBarWithLabel Percent="{Binding ImportProgress}" Visibility=IsImporting` |
| Pacing-Konsum | n/a (kein Pacing am Import) |
| Rendering-Konsum | n/a |
| Lücken | `audio_hash` und `has_audio_embedding` werden gespeichert aber UI zeigt keinen Indicator dafür |

**Detail-Workflow:**
1. Path-Existenz-Check + Suffix-Whitelist (`.mp3/.wav/.flac/.ogg/.m4a/.aac`).
2. ffprobe → duration, sample_rate, channels.
3. `media_hash` mit per-chunk SSE 0.01% Progress.
4. `register_audio_clip` (Reuse-Logik: gleiche Datei → gleiche ID).
5. **Subtrack-Detection für Mixe ≥60s** (`SubtrackDetector.detect`) → `clip["subtrack_segments"]` + `clip["tempo_curve"]` *im in-memory dict*. **Wird NICHT separat in SQLite persistiert** (nur via späteren `update_audio_analysis` falls überhaupt) — siehe Lücke L-A1.

## Stage A2: Analyse (POST /audio/analyze)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /audio/analyze` (`audio_router.py:237-342`) |
| Service-Layer | `_run_audio_analysis` via `asyncio.to_thread` (Worker-Thread) |
| Core-Module | `librosa.load` (sr=22050, mono), `BeatDetector` (singleton, BeatNet/librosa-Fallback), `StructureAnalyzer`, `SpectralAnalyzer`, `KeyDetector` |
| Persistenz | `state.set_audio_analysis(id, result)` + `state.update_audio_analysis` (MediaRepository ai_data_json: bpm, key, beat_count, beats_json, energy_curve, structure_segments, spectral_data, is_analyzed) |
| SSE-Events | 6 Phasen: `load 5%/15%`, `beat_chunk` (15..45% per BeatNet pct), `beats 45%`, `structure 70%`, `spectral 85%`, `key 95%`, completed 100% |
| UI-Binding (Audio-VM) | `OnSseProgressReceived` → `AnalysisProgress` + `CurrentStep` + `StatusText`. Nach Response: `Bpm`, `BeatCount`, `Key` direkt aus `result` |
| UI-Anzeige | TEMPO-Card (`Bpm` F1), TONART-Card (`Key`), BEATS-Card (`BeatCount`), DAUER-Card (`SelectedClip.DurationText`); CurrentStep-Indicator + AnalysisProgress (0.00%) |
| Pacing-Konsum | siehe Stage A8 (Pacing-Konsum-Matrix) |
| Rendering-Konsum | n/a (Render kennt nur audio_path) |
| Lücken | Phase-Naming-Inkonsistenz (`load`, `beats`, `beat_chunk`, `structure`, `spectral`, `key`, `complete`) — UI zeigt nur den Last-Step-Namen |

## Stage A3: Beats / Onsets / Waveform / Structure / Spectral (GET-Endpoints)

| Endpoint | Quelle | UI-Konsument |
|---|---|---|
| `GET /audio/beats/{id}` | `state.get_audio_analysis(id).beats` | `TimelineViewModel.LoadWaveformAsync` → `BeatMarkers` + `SnapMarkers` |
| `GET /audio/onsets/{id}` | Berechnet via scipy.find_peaks aus `energy_curve` (offline, run_in_threadpool) | `TimelineViewModel.LoadWaveformAsync` → `SnapMarkers` |
| `GET /audio/waveform/{id}?bands=N` | `WaveformAnalyzer.get_downsampled_waveform` (1000 points, 3 bands) | `TimelineViewModel.LoadWaveformAsync` → `WaveformBars` (band 1=mid only) |
| `GET /audio/structure/{id}` | `state.get_audio_analysis(id).structure_segments` | `TimelineViewModel.LoadWaveformAsync` → `SongSegments` |
| `GET /audio/spectral/{id}` | `state.get_audio_analysis(id).spectral_data` | `TimelineViewModel.LoadWaveformAsync` → `_rawSpectralData` → `SpectralPoints` (downsampled centroids) |

**Lücken:**
- Spectral `bands.low/mid/high` werden zur UI gesendet aber UI zeigt NUR Centroids — die 3-Band-Energie-Kurven sind ungenutzt im Frontend.
- `frequency_ranges` aus `SpectralData` wird nie angezeigt.

## Stage A4: Stem-Separation (POST /audio/stems/separate)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /audio/stems/separate` (`audio_router.py:428-475`) |
| Core | `StemSeparator.separate` (Demucs/MDX-Net via DirectML, GPU-Lock) |
| SSE | `stem_progress` per-stage (init/loading/inference/saving) 0..100% |
| UI-Binding | `IsSeparating`-Flag → `ProgressBarWithLabel Visibility` |
| UI-Anzeige | Nur StatusText `Stems getrennt: {ModelUsed}` — keine UI-Anzeige der Stem-Pfade |
| Pacing-Konsum | **Engine hat `generate_cut_list_with_stems(stems={...})` Methode**, aber `pacing_router._run_pacing_generation` ruft NUR `generate_cut_list` ohne Stems auf. **Stem-Pacing ist DEAD CODE im aktuellen Pfad** |
| Rendering-Konsum | n/a |
| Lücken | Stem-Pfade werden nirgends im UI angezeigt; kein Player; Stems-Datei-Liste nicht in `AudioClipModel`; Stem-Pacing in Pacing-Router nicht erreichbar |

## Stage A5: Subtrack-Detection (synchron während Import)

| Aspekt | Status |
|---|---|
| Trigger | `import_audio` Phase 6 für `duration ≥ 60s` |
| Core | `SubtrackDetector.detect(path)` |
| Output | `clip["subtrack_segments"]` (Liste von start/end/confidence) + `clip["tempo_curve"]` |
| Persistenz | NUR im in-memory `clip` dict. **Kein separater MediaRepository-Schreib-Pfad für subtrack_segments**. Erst beim ersten `update_audio_analysis` würden sie evtl. mit-persistiert (aber nur wenn explizit übergeben → wird sie nicht) |
| UI-Anzeige | Keine — `AudioClipModel` hat keine `Subtracks`-Property |
| Pacing-Konsum | `_run_pacing_generation` extrahiert `cached_analysis.subtrack_segments` → `_pre_cached_subtracks` → `_subtrack_boundary_anchors()`. ABER: `cached_analysis = state.get_audio_analysis(id)` — und das audio_analysis_cache enthält subtrack_segments NUR, wenn nach analyze ein update_audio_analysis sie geschrieben hat. **Heute werden subtrack_segments nicht im audio_analysis_cache abgelegt** — nur im in-memory clip-dict aus dem Import-Pfad. PacingService liest also `cached_analysis.subtrack_segments` und findet nichts. → siehe Lücke L-A2 |
| Engine-Konsum | `_subtrack_boundary_anchors` Helper-API existiert, aber **kein Code in `generate_cut_list_with_structure` oder `generate_cut_list` ruft es auf**. Nur Helper. → siehe Lücke L-A3 |
| Rendering-Konsum | n/a |
| Lücken | Subtracks gehen verloren — gespeichert in `clip` dict, nicht im `audio_analysis_cache`, nie an Pacing-Engine angekommen, nie in UI sichtbar |

## Stage A6: Beat-Detection (BeatNet/librosa-Fallback)

| Aspekt | Status |
|---|---|
| Trigger | innerhalb `_run_audio_analysis` Phase 1 |
| Core | `BeatDetector` Singleton (DBN inference). Per-chunk progress callback (15..45% mapped). Output: list[float] beat times |
| Persistenz | Als `beats: [{time, strength=1.0, beat_type="beat"}]` in `result` + `state.update_audio_analysis` mit `beats_json` |
| SSE | `beat_chunk` events |
| UI-Anzeige | `BeatCount` in BEATS-Card |
| Pacing-Konsum | **OK** — `pacing_service.py:215-220` extrahiert beats aus `cached_analysis.beats`, injiziert in `_pre_cached_beats`. Engine konsumiert via `pacing_engine._pre_cached_beats` (Zeile 1006-1007 in advanced_pacing_engine.py) |
| Rendering-Konsum | n/a |
| Lücken | `strength` ist immer 1.0 (BeatDetector liefert nur Zeiten) — keine Differenzierung zwischen starken/schwachen Beats |

## Stage A7: Key-Detection (Krumhansl-Kessler)

| Aspekt | Status |
|---|---|
| Trigger | `_run_audio_analysis` Phase 4, 95% |
| Core | `KeyDetector(librosa).detect_key(y, sr)` — chroma + Krumhansl profile |
| Persistenz | `result.key` → `clip.key` + `state.update_audio_analysis` |
| UI-Anzeige | TONART-Card grün (`Binding Key`) |
| Pacing-Konsum | **NUR via `use_key_matching`**. Wenn Flag, dann `pacing_engine.clip_selector.audio_key = cached_analysis.key`. Engine-Funktion `_key_compatibility_score(audio_key, video_key)` existiert, aber **Video-Clips haben kein `audio_key`-Feld** ⇒ Score immer 0.5 (neutral) ⇒ kein Effekt. → siehe Lücke L-A4 |
| Rendering-Konsum | n/a |
| Lücken | Tonart wird angezeigt aber pacing-mässig wirkungslos (no-op) |

## Stage A8: Audio→Pacing — Detail-Konsumenten-Matrix

| Audio-Output | Persist | Cache | An PacingService? | An Engine? | Engine-Konsum aktiv? | Status |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `bpm` | ✅ ai_data_json | ✅ | ✅ via `cached_analysis.bpm` → `_pre_cached_bpm` | ✅ Zeile 1072-1073 | ⚠️ NUR wenn `expected_bpm=None`. UI sendet ImmerWert — seit Director.OnSelectedAudioClipChanged-Fix sync zur SelectedClip.Bpm | 🟢 OK |
| `key` | ✅ | ✅ | ✅ via `cached_analysis.key` → `clip_selector.audio_key` (wenn use_key_matching) | ✅ `_key_compatibility_score` ready | ❌ Video-Clips haben kein `audio_key`-Feld → Score immer 0.5 | 🔴 NO-OP |
| `beat_count` | ✅ | ✅ | ❌ Reine Statistik | n/a | n/a | 🟡 INFO-only |
| `beats[]` | ✅ beats_json | ✅ | ✅ → `_pre_cached_beats` | ✅ Zeile 1006-1007 | ✅ Konsumiert | 🟢 OK |
| `energy_curve` | ✅ | ✅ | ✅ → `_pre_cached_energy` | ✅ Zeile 254-258 + 1576/1706 | ✅ skipt RMS-Neuberechnung | 🟢 OK (Audit A2) |
| `structure_segments` | ✅ | ✅ | ✅ → `pacing_engine.song_structure` (wenn use_structure_awareness) | ✅ `generate_cut_list_with_structure` skipt analyze_song_structure | ✅ Konsumiert | 🟢 OK (Audit A3) |
| `spectral_data.bands.low` | ✅ | ✅ | ✅ → `_pre_cached_bass_curve` | ✅ `_bass_weight_at_time` | ✅ in `_apply_structure_weights` für Drop-Sektionen | 🟢 OK (Audit E2) |
| `spectral_data.bands.mid` | ✅ | ✅ | ❌ Nicht gelesen | n/a | n/a | 🔴 PERSISTIERT UNGENUTZT |
| `spectral_data.bands.high` | ✅ | ✅ | ❌ Nicht gelesen | n/a | n/a | 🔴 PERSISTIERT UNGENUTZT |
| `spectral_data.centroids` | ✅ | ✅ | ❌ Nicht gelesen (nur UI Visualisierung) | n/a | n/a | 🟡 NUR UI |
| `subtrack_segments` | ⚠️ NUR clip dict | ❌ NICHT im audio_analysis_cache | ⚠️ Lookup wird versucht aber findet nichts | ⚠️ `_pre_cached_subtracks` Setter ready, niemals aufgerufen wegen leerer Quelle | ⚠️ `_subtrack_boundary_anchors()` Helper ready, kein Aufrufer | 🔴 BROKEN-CHAIN |
| `tempo_curve` | ⚠️ NUR clip dict | ❌ NICHT im audio_analysis_cache | ❌ Nicht gelesen | n/a | n/a | 🔴 PERSISTIERT UNGENUTZT |
| `frequency_ranges` | ✅ in spectral_data | ✅ | ❌ Nicht gelesen | n/a | n/a | 🔴 PERSISTIERT UNGENUTZT |

---

# TEIL B — VIDEO PIPELINE

## Stage V1: Import (POST /video/import — Multi-File)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /video/import` (`video_router.py:35-144`) |
| Service-Layer | Per-File-Loop: `_get_video_info` (ffprobe) + `media_hash` |
| Persistenz | `state.register_video_clip` (Reuse-Logik) + `state.persist_video_clip` (MediaRepository) |
| SSE | `import_progress` mit per-file overall mapping |
| UI-Binding | `VideoLibraryViewModel.OnSseProgressReceived` → `ImportProgress` direkt vom Backend |
| UI-Anzeige | `controls:ProgressBarWithLabel Percent="{Binding ImportProgress}" Visibility=IsImporting` |
| Pacing-Konsum | n/a |
| Rendering-Konsum | Indirekt über file_path im Clip-Datensatz |
| Lücken | `video_hash`, `has_video_embedding` werden gespeichert aber UI zeigt keinen Indicator |

## Stage V2: Thumbnail (GET /video/thumbnails/{id})

| Aspekt | Status |
|---|---|
| Endpoint | `GET /video/thumbnails/{id}` → `image/jpeg` Response |
| Core | `ffmpeg -ss 1 -frames:v 1 -vf scale=320:-1` (synchroner subprocess via `asyncio.to_thread`) |
| Persistenz | Nicht persistent — generiert on-demand. (`thumbnail_available` Flag im Clip wird nie auf True gesetzt) |
| UI-Binding | `VideoLibraryViewModel.LoadAllThumbnailsAsync` → `_thumbnailCache` (in-memory dict) → `clip.Thumbnail` (BitmapImage) |
| UI-Anzeige | `VideoLibraryView.xaml` Wrap-Panel mit `Image Source="{Binding Thumbnail}"` per Card |
| Lücken | Failed-Thumbnails werden in `_thumbnailFailureCache` gespeichert, aber UI zeigt kein Placeholder-Bild — Card bleibt leer |

## Stage V3: Analyse (POST /video/analyze)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /video/analyze` (`video_router.py:235-366`) |
| Service-Layer | `_run_video_analysis` via `with_gpu_task` (GPU-Lock + VRAM-Budget-Check `model_id=video_analysis_full`) |
| Core-Module | `SceneDetector` (PySceneDetect), `MotionAnalyzer` (RAFT ONNX/DirectML), `SigLIPWrapper` + `VectorStore` (FAISS) |
| Persistenz | `state.set_video_analysis(id, result)` + `state.update_video_analysis` mit scene_count, avg_motion, has_embedding, scenes, motion, dominant_colors, tags |
| SSE | 4-Phasen: `init 1%`, `scenes 15%`, `motion_embedding 35%` (mit `motion_frame` per-frame in 35..65), `finalize 90%`, `complete 100%` (BUG-204 Fix) |
| UI-Binding | `VideoLibraryViewModel.OnSseProgressReceived` → `CurrentClipProgress` + `CurrentStep` + `CurrentStepIndex/Total` + `StatusText` |
| UI-Anzeige | Pro Card: `IsAnalyzed`-Indikator (Häkchen). Toolbar: `AnalyzedCount` / `PendingCount`. CurrentStep nur im Status-Text |
| Pacing-Konsum | siehe Stage V8 |
| Rendering-Konsum | n/a (Render kennt nur file_path) |
| Lücken | `dominant_colors`, `tags` werden persistiert aber NICHT in der Card sichtbar — Tags-Property im Clip ist immer leer im Render-Path (siehe `VideoClipInfo` ListClips, Zeile 167) |

## Stage V4: Scene-Detection (PySceneDetect)

| Aspekt | Status |
|---|---|
| Phase | 1 in `_run_video_analysis` |
| Core | `SceneDetector.detect_scenes(path)` |
| Output | `result["scenes"] = [{start_time, end_time, scene_type="cut", confidence=0.85}]`, `result["scene_count"] = N` |
| GET-Endpoint | `GET /video/scenes/{id}` |
| UI-Konsument | `VideoLibraryViewModel.LoadScenesAsync` (wenn SelectedClip.IsAnalyzed) → `SelectedClipScenes` |
| UI-Anzeige | im Detail-Panel der VideoLibraryView (rechte Seite) |
| Pacing-Konsum | `pacing_router._run_pacing_generation:341` `clip_data["scene_changes"] = va.get("scenes", [])` — wird in Engine via `clip_selector` möglicherweise gewichtet |

## Stage V5: Motion-Analyse (RAFT)

| Aspekt | Status |
|---|---|
| Phase | 2 in `_run_video_analysis` (35..65% in SSE) |
| Core | `MotionAnalyzer.analyze_video_segment(frames, stride=1, on_progress=...)`. Frames extrahiert via cv2 (2 samples/s über GESAMTE Datei) |
| Output | `result["motion"] = {avg_motion, motion_curve, peak_frames, motion_category}`, `result["avg_motion"]`. Peak-Frames werden zu echten Video-Frame-Indizes übersetzt |
| GET-Endpoint | `GET /video/motion/{id}` |
| UI-Konsument | KEINER. Endpoint existiert, wird aber von keinem ViewModel aufgerufen |
| UI-Anzeige | KEINE — `avg_motion` ist im VideoAnalysisResult-Response, aber `VideoLibraryViewModel.AnalyzeSelectedAsync` zeigt es nur einmalig im StatusText (`$"Motion: {result.AvgMotion:F1}"`) |
| Pacing-Konsum | `_run_pacing_generation:336-340`: `motion_score`, `avg_motion`, `peak_motion`, `peak_frames`, `motion_curve` werden alle in clip_data injiziert. Engine `clip_selector.use_motion=True` wenn `use_motion_matching=True` |
| Lücken | Motion-Anzeige fehlt in der UI komplett (keine Card, kein Indicator). `motion_curve` injiziert aber Engine-Implementation für motion-curve-basierte Cut-Auswahl unklar (siehe Lücke L-V1) |

## Stage V6: Embedding (SigLIP via DirectML)

| Aspekt | Status |
|---|---|
| Phase | 3 in `_run_video_analysis` |
| Core | `SigLIPWrapper.encode_image` über N gleichmäßig verteilte Frames (1 sample/5s, min 3) → Mittelwert L2-normalisiert → FAISS `VectorStore("video_index").add_embedding` |
| Output | `result["has_embedding"] = bool`, `result["embedding_dim"]`, `result["embedding_samples"]` |
| GET-Endpoint | KEINER (FAISS-Index nicht via REST exponiert; nur indirekt via `/brain/suggest`) |
| UI-Anzeige | KEINE — `has_embedding` wird persistiert aber kein Visual |
| Pacing-Konsum | NUR über `SmartDirector` wenn `use_semantic_matching=True` → semantischer Score-Boost im `clip_selector` |
| Lücken | Wenn ONNX-Modell fehlt, fallback ist silent (logger.info "übersprungen") — User sieht nichts. Embedding-Status nicht im UI |

## Stage V7: Dominant Colors / Tags (Moondream)

| Aspekt | Status |
|---|---|
| Trigger | TEILWEISE — `dominant_colors` und `tags` werden nur in `update_video_analysis` mit None-Default übergeben. **`_run_video_analysis` setzt sie NIE** ⇒ persistierte Werte sind immer leer |
| Persistenz | `state.update_video_analysis(...dominant_colors=None, tags=None)` → ai_data_json hat keine dominant_colors/tags Einträge |
| UI-Anzeige | `VideoClipModel.Tags` ist immer `[]` |
| Pacing-Konsum | `clip_data["dominant_colors"] = va.get("dominant_colors", [])` und `clip_data["tags"] = va.get("tags", [])` — beide immer leer in der Praxis |
| Lücken | **Moondream-Tagging ist gar nicht in den Video-Analyse-Pfad eingebaut**. Felder existieren in Schema + clip_data + Engine-Helpers (Audit E4: `_tags_overlap_score` + `_dominant_color_similarity`), werden aber NIE befüllt |

## Stage V8: Video→Pacing — Detail-Konsumenten-Matrix

| Video-Output | Persist | Cache | An clip_data? | Engine-Konsum aktiv? | Status |
|---|:-:|:-:|:-:|:-:|---|
| `scene_count` | ✅ | ✅ | n/a (Aggregat) | n/a | 🟡 INFO |
| `scenes[]` | ✅ | ✅ | ✅ `clip_data["scene_changes"]` | ⚠️ Engine `clip_selector` kann scene_changes verwenden, aber kein dezidierter Use-Path im Code | 🟡 TEILWEISE |
| `avg_motion` | ✅ | ✅ | ✅ `motion_score` + `avg_motion` | ✅ wenn `use_motion_matching=True` | 🟢 OK |
| `motion.peak_frames` | ✅ | ✅ | ✅ `peak_frames` | ⚠️ Verfügbar im selector aber kein dezidierter Use | 🟡 TEILWEISE |
| `motion.motion_curve` | ✅ | ✅ | ✅ `motion_curve` (Audit A4) | ⚠️ Im selector verfügbar, kein aktiver Konsument für curve-basierte Auswahl | 🟡 TEILWEISE |
| `motion.peak_motion` | ❌ Wird im _run_video_analysis NIE gesetzt | ❌ | ✅ `peak_motion` wird gemappt aber Quelle ist 0.0 default | n/a | 🔴 BROKEN |
| `dominant_colors` | ⚠️ Kann persistiert werden, wird aber im Code nie befüllt | ⚠️ | ✅ `clip_data["dominant_colors"]` (Audit A4) immer leer | ⚠️ `_dominant_color_similarity` Helper-API ready (Audit E4), kein Aufrufer da Daten leer | 🔴 NO-DATA |
| `tags` | ⚠️ Wie oben | ⚠️ | ✅ Audit A4 immer leer | ⚠️ `_tags_overlap_score` Helper-API ready (Audit E4), kein Aufrufer da Daten leer | 🔴 NO-DATA |
| `has_embedding` | ✅ | ✅ | ✅ Audit A4 | ⚠️ Indirekt über `SmartDirector` wenn `use_semantic_matching=True` | 🟡 BEDINGT |
| `embedding_dim` / `embedding_samples` | ❌ | ❌ | ❌ | n/a | 🟡 NUR im Analyse-Response |

---

# TEIL C — PACING / TIMELINE

## Stage P1: Cut-List-Generierung (POST /pacing/generate)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /pacing/generate` (`pacing_router.py:29-182`) |
| Schema | `PacingConfigSchema` (audio_clip_id, video_clip_ids, expected_bpm, use_motion_matching, use_semantic_matching, use_structure_awareness, use_key_matching, use_brain, brain_min_confidence, min_cut_interval, duration_limit, trigger_settings) |
| Service-Layer | `_run_pacing_generation` via `asyncio.to_thread` → `PacingService.generate_cut_list` |
| Core-Module | `AdvancedPacingEngine` + `ClipSelector` + (optional) `SmartDirector` für semantic + (optional) `BrainReranker` für brain |
| Persistenz | `state.set_timeline(cuts)` + `state.current_audio_path` |
| SSE | `analysis_progress` step="pacing" 100% am Ende. **Keine inkrementellen Pacing-Events** — UI sieht 0% bis fertig |
| UI-Binding | `DirectorViewModel.GenerateCutListAsync` → CutList befüllen + `TimelineRefreshMessage` an Subscriber |
| UI-Anzeige | Right Panel: Cut-List GridView (CLIP, ZEITRAUM, DAUER, TRIGGER) + CutCount + TotalDuration |
| Rendering-Konsum | `state.current_timeline` ist die Quelle für Render-Pipeline |
| Brain-Post-Processor | Wenn `use_brain=True`: nach `_run_pacing_generation` Aufruf von `annotate_cuts_with_brain` (BrainService.weights, EmbeddingCache, audio_hash, video_hashes_by_clip). Persistiert cut_id in DB für `/brain/explain` |

## Stage P2: Timeline GET/UPDATE (GET/POST /pacing/timeline)

| Endpoint | Funktion | Konsument |
|---|---|---|
| `GET /pacing/timeline` | Liefert `TimelineResponse` (entries, total_duration, audio_path) | `TimelineViewModel.RefreshTimelineAsync` |
| `POST /pacing/timeline` | `TimelineUpdateRequest` mit manueller Entry-Liste — ersetzt komplett | `TimelineViewModel.SyncTimelineAsync` (nach Manual-Edit) |

## Stage P3: Preview (POST /pacing/preview)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /pacing/preview` (640×360 ffmpeg-render slice) |
| Core | `PreviewGenerator.generate_preview(entries, start_sec, duration)` |
| UI-Konsument | `TimelineViewModel.GeneratePreviewAsync` → `PreviewVideoPath` + `PreviewReady` Event |

---

# TEIL D — RENDERING

## Stage R1: Render-Start (POST /render/start)

| Aspekt | Status |
|---|---|
| Endpoint | `POST /render/start` (`render_router.py:95-200`) |
| Schema | `RenderRequest` (output_path, audio_path, quality, resolution_width/height, fps, bitrate_mbps, encoder, include_audio) |
| Pre-Check | Timeline non-empty, Path-Traversal-Schutz für output_path |
| Persistente Queue | `RenderQueue.enqueue(media_hash, output_path, settings)` — Idempotency via media_hash über audio + timeline |
| Background-Task | `_run_render_task` mit GPU-Lock + Cancel-Support |
| Service-Layer | `RenderService.render_timeline(timeline, audio_path, output_filename, target_w/h/fps, bitrate, preset, progress_callback, cancel_callback)` |
| SSE | `render_progress` mit task_id, percent, status, message, current_frame, total_frames, fps, elapsed_seconds, eta_seconds. Throttled (1%/1s) |
| UI-Binding | `ProductionViewModel.OnRenderProgress` → `RenderProgress`, `EtaText`, `StatusText`. Final-Status: completed → IsRendering=false; failed/cancelled → ResetRenderState |
| UI-Anzeige | RENDER SETTINGS-Card (output_path, quality, w×h@fps), RENDER CONTROL-Card (Start/Cancel buttons + ProgressBarWithLabel + StatusText + EtaText), RENDER LOG ListBox |

## Stage R2: Render-Konsumenten — was nutzt der Renderer wirklich?

**Frage:** Welche Felder aus `state.current_timeline` (Pacing-Output) UND aus den Audio/Video-Analyse-Caches landen tatsächlich im Render-Output?

| Feld aus state | Konsumiert von Render? | Ort der Konsumtion |
|---|:-:|---|
| `state.current_timeline[i].metadata.file_path` | ✅ KRITISCH | `_execute_render` Zeile 546 |
| `state.current_timeline[i].metadata.clip_start` | ✅ KRITISCH | `_execute_render` Zeile 547 → `in_point` |
| `state.current_timeline[i].start_time` / `end_time` | ✅ KRITISCH | duration berechnet → `out_point` |
| `state.current_timeline[i].metadata.clip_name` | ⚠️ Nur fürs Logging | `render_timeline` Loop |
| `state.current_timeline[i].metadata.trigger_type` | ⚠️ Nur fürs Logging | `render_timeline` Loop |
| `state.current_timeline[i].metadata.segment_type` | ❌ Wird ignoriert | n/a |
| `state.current_timeline[i].metadata.brain_*` | ❌ Wird ignoriert | n/a |
| `state.current_audio_path` (aus Pacing) | ❌ NICHT! Render nimmt `request.audio_path` | UI muss audio_path mitschicken |
| `state.audio_clips` | ❌ Render kennt audio_clips nicht | n/a |
| `state.audio_analysis_cache` | ❌ Komplett ignoriert | Beats, BPM, Key, Spectral landen NIRGENDS im Render |
| `state.video_clips` | ❌ Render kennt video_clips nicht | n/a |
| `state.video_analysis_cache` | ❌ Komplett ignoriert | Scenes, Motion, Embedding landen NIRGENDS im Render |

**Render-Pipeline-Beobachtungen:**
1. **Render ist „dumm"** — er bekommt aus dem in-memory state NUR die finale Cut-Liste und macht ffmpeg-concat-demuxer. Alle Audio/Video-Intelligenz endet beim Pacing.
2. **`audio_path` kommt aus dem `RenderRequest`** (UI sendet es aus `ProductionViewModel.AudioPath`, das via `OnTimelineChanged` aus `TimelineResponse.AudioPath` synchronisiert wird).
3. **Normalisierung** in `_normalize_clips` prüft `width/height/fps` per Clip und transcodiert bei Mismatch — **die Video-Analyse-Daten werden hier NICHT genutzt** (ffprobe wird neu aufgerufen pro Clip). Das ist redundant: `state.video_clips[id]["width/height/fps"]` ist schon bekannt.
4. **Encoder-Override:** UI kann `encoder` im Request setzen → `RenderService(encoder_override=...)`. Default-Detection via `_detect_best_encoder` (cached class-level).
5. **Audio-Mux:** `_run_ffmpeg_render` mappt `0:v` (video aus concat) + `1:a` (audio aus audio_path-Datei). Audio-Cuts/Beats spielen keine Rolle — die ganze Audio-Datei wird ungekürzt unterlegt (mit `-t {audio_dur}` cap).
6. **Cancel-Support:** Cancel-Flag wird in `is_cancelled` callback bei jedem Progress-Update geprüft → `RenderCancelledError`.
7. **Output-Mtime-Schutz:** `_cleanup_render_temps` löscht output nur wenn mtime > `_output_mtime_before` (verhindert Löschen einer vorher fertigen Render-Ausgabe bei Cancel).

**Konsequenz:** Render hat sehr saubere Schnittstelle (nur 5 Felder). Alle Audio/Video-Smartness muss im Pacing landen, sonst geht sie verloren.

---

# TEIL E — UI BEDIENNELEMENTE-MATRIX

## Tab "PROJEKT" (ProjectOverviewView)

| Button/Command | Backend-Action | Visibility-Condition | CanExecute |
|---|---|---|---|
| Projekt erstellen | `POST /project/create` | always | always |
| Projekt öffnen | `POST /project/open` | always | always |
| Projekt schließen | `POST /project/close` | HasProject | always |
| Projekt speichern | `POST /project/save` | HasProject | always |

## Tab "AUDIO" (AudioLibraryView)

| Button/Command | Backend-Action | Visibility | CanExecute |
|---|---|---|---|
| ImportAudioCommand | `POST /audio/import` (Files) | always | always |
| ImportFolderCommand | Iterates folder + `POST /audio/import` | always | always |
| SelectAllCommand | UI-only (befüllt SelectedClips) | always | always |
| DeselectAllCommand | UI-only | always | always |
| DeleteSelectedCommand | `DELETE /audio/clips/{id}` oder `/audio/clips` (batch) | always | SelectedClips.Count > 0 && !IsDeleting |
| DeleteAllCommand | `DELETE /audio/clips` (alle) | always | AudioClips.Count > 0 && !IsDeleting |
| AnalyzeAllCommand | Loop `POST /audio/analyze` für jeden Clip | always | AudioClips.Count > 0 && !IsAnalyzing |
| AnalyzeSelectedCommand | `POST /audio/analyze/{SelectedClip.Id}` | always | SelectedClip != null && !IsAnalyzing |
| SeparateStemsCommand | `POST /audio/stems/separate` | always | SelectedClip != null (kein CanExecute-Guard) |

## Tab "VIDEO" (VideoLibraryView)

| Button/Command | Backend-Action | Visibility | CanExecute |
|---|---|---|---|
| ImportVideosCommand | `POST /video/import` (Multi-File) | always | always |
| ImportFolderCommand | Folder-Scan + `POST /video/import` | always | always |
| ImportVideoFromPathCommand | `POST /video/import` aus Text-Pfad | always | VideoImportPath nicht leer |
| BrowseVideoPathCommand | UI-only File-Dialog | always | always |
| AnalyzeSelectedCommand | `POST /video/analyze/{SelectedClip.Id}` | always | always (kein Guard) |
| AnalyzeAllCommand | Loop `POST /video/analyze` | always | always |
| AnalyzeMarkedCommand | Loop für SelectedClips | always | SelectedClips.Count > 0 && !IsAnalyzing |
| SelectAllVideosCommand | UI-only | always | always |
| DeleteSelectedCommand | `DELETE /video/clips/{id}` oder batch | always | SelectedClips.Count > 0 && !IsDeleting |
| DeleteAllVideosCommand | `DELETE /video/clips` (alle) | always | VideoClips.Count > 0 && !IsDeleting |
| LoadClipsCommand | `GET /video/clips?page=1&limit=200` | always | always |

## Tab "KI-REGIE" (DirectorView)

| Button/Command | Backend-Action | Visibility | CanExecute |
|---|---|---|---|
| GenerateCutListCommand | `POST /pacing/generate` | always | !IsGenerating && SelectedAudioClip != null && SelectedVideoClipCount > 0 |
| LoadBrainSuggestionsCommand | `POST /brain/suggest` | always | !IsLoadingSuggestions |
| SelectAllVideoClipsCommand | UI-only (alle IsSelected=true) | always | always |
| DeselectAllVideoClipsCommand | UI-only | always | always |
| LoadClipsCommand | refresh Audio + Video lists | always | always |

**Sliders (Pacing-Settings, alle TwoWay binding):** ExpectedBpm (TextBox), BeatWeight, KickWeight, EnergyWeight, EnergyThreshold, OnsetWeight, MinCutInterval, DurationLimit (TextBox), BrainMinConfidence (only when UseBrain=true).

**Checkboxes:** UseMotionMatching, UseSemanticMatching, UseStructureAwareness, UseKeyMatching, UseBrain.

## Tab "TIMELINE" (TimelineView)

| Button/Command | Backend-Action | Visibility | CanExecute |
|---|---|---|---|
| RefreshTimelineCommand | `GET /pacing/timeline` | always | always |
| PreviousCutCommand | UI-only (selection) | always | SelectedEntry != null && Index > 0 |
| NextCutCommand | UI-only | always | Index < Count-1 |
| GeneratePreviewCommand | `POST /pacing/preview` | always | TimelineEntries.Count > 0 && !IsGeneratingPreview |
| SyncTimelineCommand | `POST /pacing/timeline` (Update) | always | always |

## Tab "EXPORT" (ProductionView)

| Button/Command | Backend-Action | Visibility | CanExecute |
|---|---|---|---|
| BrowseOutputCommand | UI-only Save-Dialog | always | always |
| StartRenderCommand | `POST /render/start` | always | HasProject && !IsRendering |
| CancelRenderCommand | `POST /render/cancel/{taskId}` | IsRendering=true | _currentTaskId != null |
| ClearRenderLogCommand | UI-only (clear log) | always | always |

## Tab "HIRN" (BrainView)

| Button/Command | Backend-Action |
|---|---|
| BrainStatsCommand | `GET /brain/stats` |
| BrainLearningSessionCommand | `POST /brain/learning_session` |
| BrainResetCommand | `POST /brain/reset` (mit confirm-token-flow) |
| BrainFeedbackCommand | `POST /brain/feedback` (4-Klick: love/like/dislike/hate) |

## Tab "SETTINGS" (SettingsView)

Mehrere Settings-Bindings (Theme, GPU-Mode, etc.) — read-only API-Status-Display + lokale persisted settings.

## Tab "PERFORMANCE" (VramTelemetryView)

`GET /health/vram` Polling für Multi-Model Snapshots.

---

# TEIL F — UI ANZEIGEN-MATRIX (gebundene VM-Properties)

## AudioLibraryView

| VM-Property | Backend-Source | Lücken-Risiko |
|---|---|---|
| AudioClips (List) | `GET /audio/clips` → `AudioClipModel` | OK |
| SelectedClip.Name | `clip.name` | OK |
| Bpm | `clip.bpm` aus AudioAnalysisResult | OK |
| Key | `clip.key` | OK (zeigt ohne Pacing-Wirkung) |
| BeatCount | `clip.beat_count` | OK |
| SelectedClip.DurationText | `clip.duration_seconds` | OK |
| ImportProgress | SSE `import_progress` | OK |
| AnalysisProgress | SSE `analysis_progress` | OK |
| CurrentStep | SSE `analysis_progress.step` | OK |
| StatusText | gemischt | OK |

**Persistiert aber nicht angezeigt in AudioLibraryView:**
- `subtrack_segments`, `tempo_curve` (Stage A5)
- `energy_curve`, `structure_segments`, `spectral_data` (nur in Timeline-Tab gezeigt)
- `audio_hash`, `has_audio_embedding` (kein Indicator)
- Stems-Pfade (nach Stem-Separation)

## VideoLibraryView

| VM-Property | Backend-Source | Lücken-Risiko |
|---|---|---|
| VideoClips (List) | `GET /video/clips` → `VideoClipModel` | OK |
| Thumbnail | `GET /video/thumbnails/{id}` | OK (Failed-Cache silent) |
| IsAnalyzed (per clip) | `clip.is_analyzed` | OK |
| AnalyzedCount / PendingCount | berechnet | OK |
| SelectedClipScenes | `GET /video/scenes/{id}` | OK |
| ImportProgress / CurrentClipProgress | SSE | OK |

**Persistiert aber nicht angezeigt in VideoLibraryView:**
- `avg_motion`, `motion.peak_frames`, `motion.motion_curve`, `motion_category` — Motion-Daten haben KEINE Card im UI
- `dominant_colors`, `tags` (auch wenn befüllt — wäre nicht sichtbar; sind eh leer)
- `has_embedding`, `embedding_dim`, `embedding_samples`
- `video_hash`, `width`, `height`, `fps`, `codec` (nur intern in Model verfügbar)
- `scene_count` (außer als Toolbar-Summary)

## DirectorView

| VM-Property | Backend-Source | Lücken-Risiko |
|---|---|---|
| AvailableAudioClips / AvailableVideoClips | refresh | OK |
| SelectedAudioClip | UI | OK |
| SelectedVideoClipCount | UI compute | OK |
| ExpectedBpm | UI/sync zu SelectedClip.Bpm | OK seit Phase A Fix |
| BeatWeight, KickWeight, etc. | UI | OK |
| Use*-Flags | UI | OK |
| CutList | `POST /pacing/generate` Response | OK |
| BrainSuggestions | `POST /brain/suggest` | OK |
| GenerationProgress | SSE | NUR 100% am Ende — keine inkrementellen Pacing-Events |
| CutCount / TotalDuration | Response | OK |

**Lücken:** Keine Anzeige von `bass_curve`-Aktivität, `subtrack_anchors`-Snap, ob structure_segments cached oder neu analysiert wurde, ob bass-boost angewendet wurde.

## TimelineView

| VM-Property | Backend-Source | Lücken-Risiko |
|---|---|---|
| TimelineEntries | `GET /pacing/timeline` | OK |
| WaveformBars | `GET /audio/waveform/{id}?bands=1` (mid only) | OK |
| BeatMarkers | `GET /audio/beats/{id}` | OK |
| SnapMarkers | beats + onsets | OK |
| SongSegments | `GET /audio/structure/{id}` | OK |
| SpectralPoints | `GET /audio/spectral/{id}` (nur centroids) | OK |
| BrainConfidence | TimelineResponse.brain_confidence | OK |
| BrainExplainTooltip | `GET /brain/explain/{cut_id}` lazy | OK |

**Lücken:**
- `Spectral.bands.low/mid/high` werden nicht angezeigt (nur Centroids)
- `tempo_curve` (DJ-Tempo-Kurve) wird nicht visualisiert
- Subtracks werden nicht visualisiert

## ProductionView

| VM-Property | Backend-Source | Lücken-Risiko |
|---|---|---|
| OutputPath, Width, Height, Fps, SelectedQuality | UI | OK |
| AudioPath | sync von Timeline | OK |
| RenderProgress | SSE `render_progress.percent` | OK |
| EtaText | berechnet aus elapsed/eta_seconds + frame counts | OK |
| StatusText | SSE message | OK |
| RenderLogEntries | accumulated SSE logs | OK |

**Lücken:** Kein Encoder-Override-Selector im UI (Backend kann es, UI nutzt es nicht). Kein `bitrate_mbps`-Slider (Default 12 in `RenderRequest` ohne UI-Override).

---

# TEIL G — CROSS-VM-REFRESH (Messenger-Pattern)

| Aktion | Sender | Message | Subscriber → Action |
|---|---|---|---|
| Audio importiert | AudioLibraryViewModel.ProcessAudioImportAsync | AudioImportedMessage, AudioLibraryRefreshMessage, MediaLibraryRefreshMessage | AudioLibraryVM (LoadAudioClipsAsync), DirectorVM (RequestClipReloadAsync), MediaIngestVM, ProjectOverviewVM (count refresh) |
| Audio gelöscht | AudioLibraryViewModel.DeleteSelectedAsync/DeleteAllAsync | AudioLibraryRefreshMessage, MediaLibraryRefreshMessage | AudioLibraryVM, DirectorVM |
| Video importiert | VideoLibraryViewModel.ProcessVideoImportAsync, ImportVideoFromPathAsync | VideoImportedMessage, VideoLibraryRefreshMessage, MediaLibraryRefreshMessage | VideoLibraryVM (HandleReload), DirectorVM (RequestClipReloadAsync), MediaIngestVM, ProjectOverviewVM |
| Video gelöscht | VideoLibraryViewModel.DeleteSelectedAsync/DeleteAllVideosAsync | VideoLibraryRefreshMessage | VideoLibraryVM (LoadClipsAsync) |
| Cut-Liste generiert | DirectorViewModel.GenerateCutListAsync | TimelineRefreshMessage | TimelineVM (RequestTimelineRefreshAsync) |
| Projekt geöffnet | ProjectOverviewViewModel | ProjectOpenedMessage | ALLE VMs (load clips, refresh, set HasProject=true) |
| Projekt geschlossen | ProjectOverviewViewModel | ProjectClosingMessage, ProjectClosedMessage | ALLE VMs (clear, reset state) |
| App-Shutdown | App.xaml.cs OnExit | AppShutdownMessage | Alle VMs (BeginShutdown / Cancel pending operations) |
| Backend ready | MainViewModel | BackendReadyMessage | (verschiedene) |
| Director-Navigate | TimelineView (z.B. cut click) | NavigateDirectorMessage | MainVM (Tab-Switch) |
| Brain-Feedback | BrainViewModel/LearningSessionViewModel | BrainFeedbackAppliedMessage(CutId) | TimelineVM (OnBrainFeedbackAppliedAsync — invalidiert tooltip cache + lädt explain neu) |

**Beobachtung:** Cross-VM-Refresh ist sauber typed (Audit F4 hat string-keys → records refactored). Kein Drift, kein typo-risk.

---

# TEIL H — GEFUNDENE LÜCKEN (priorisiert)

## KRITISCH (Daten verloren oder Feature wirkungslos)

| ID | Lücke | Quelle | Impact |
|---|---|---|---|
| **L-K1** | Subtracks (Stage A5) gehen verloren — werden in `clip` dict gespeichert, NICHT im `audio_analysis_cache` → PacingService liest leere Liste | `audio_router.py:131-151` (set in clip), `app_state.py update_audio_analysis` (kein subtrack_segments Param) | Lange-Mix-Subtrack-Snap-Funktionalität tot |
| **L-K2** | Moondream-Tagging nicht angeschlossen — `_run_video_analysis` setzt `dominant_colors` und `tags` NIE | `video_router.py:_run_video_analysis` | Audit-E4 Helper-API ungenutzt; semantic similarity feature tot |
| **L-K3** | `motion.peak_motion` wird nie berechnet — `_run_video_analysis` schreibt nur avg_motion + motion_curve + peak_frames; pacing_router liest `motion.get("peak_motion", 0.0)` aber Source ist immer 0.0 | `video_router.py:589-597` | Peak-Motion-Score in clip_data immer 0 |
| **L-K4** | `UseKeyMatching` ist no-op — Video-Clips haben kein audio_key Feld → `_key_compatibility_score` immer 0.5 | `pacing_service.py:306-317`, `advanced_pacing_engine.py:_key_compatibility_score` | UI-Checkbox suggeriert Funktion, hat aber keinen Effekt |
| **L-K5** | Stem-Pacing Feature ist DEAD CODE — `pacing_router._run_pacing_generation` ruft `service.generate_cut_list` ohne Stems auf, obwohl `generate_cut_list_with_stems` in der Engine existiert | `pacing_router.py:361`, `advanced_pacing_engine.py:1283` | Stem-basierte Triggers (drum/bass) komplett ungenutzt |

## MITTEL (Feature funktioniert, aber UI/Pacing inkonsistent)

| ID | Lücke | Quelle | Impact |
|---|---|---|---|
| **L-M1** | `tempo_curve` (Subtrack-Detector Output) NIE konsumiert | `audio_router.py:144` (set), kein Reader | DJ-Tempo-Variation für Pacing ungenutzt |
| **L-M2** | `spectral.bands.mid/high` ungenutzt — nur `low` (bass) wird in Engine genutzt | `pacing_service.py:264-281` | mid/high Frequency-Reactive-Pacing fehlt |
| **L-M3** | `motion.motion_curve` als clip_data injiziert (Audit A4), aber Engine hat keine motion-curve-getriebene Selection-Logik | `pacing_router.py:340`, `advanced_pacing_engine.py` | Curve-Daten dort, aber ungenutzt |
| **L-M4** | Motion-Anzeige fehlt komplett in VideoLibraryView — keine Card für avg_motion / motion_category | `VideoLibraryView.xaml`, `VideoLibraryViewModel.cs` | User sieht Motion-Werte nur in StatusText |
| **L-M5** | `GET /video/motion/{id}` Endpoint existiert, hat keinen Konsumenten | `video_router.py:390-412`, kein Aufrufer in C# | Tote API |
| **L-M6** | `GET /video/scenes/{id}` wird nur OnSelectedClipChanged geladen — nach Analyse-Abschluss kein automatisches Reload | `VideoLibraryViewModel.OnSelectedClipChanged` | Scenes-Liste leer wenn man Clip vor der Analyse selektiert hat |
| **L-M7** | Pacing-Generierung sendet keine inkrementellen SSE-Events — UI zeigt 0% bis fertig (nur final 100%) | `pacing_router.py:156-160` | Schlechte UX bei langen Pacings (Stunden-Mixe) |
| **L-M8** | `embedding_dim`, `embedding_samples` werden im Analyse-Result zurückgegeben aber nirgends persistiert oder angezeigt | `video_router.py:662-663` | Diagnostics fehlt |

## NIEDRIG (Hygiene, kosmetisch)

| ID | Lücke | Quelle | Impact |
|---|---|---|---|
| **L-N1** | `frequency_ranges` aus SpectralData nirgends genutzt — wird im Schema mitgesendet | `audio_router.py:653` | Schema-Bloat |
| **L-N2** | `audio_hash` / `has_audio_embedding` Felder im Audio-Clip persistiert, aber keine UI-Indikator | `audio_router.py:126-127`, `app_state.py` | Keine User-sichtbare Cache-Hit-Anzeige |
| **L-N3** | `video_hash` / `has_video_embedding` analog | `video_router.py:117-118` | Keine User-sichtbare Cache-Hit-Anzeige |
| **L-N4** | Stem-Separation Output-Pfade (vocals_path, drums_path, etc.) werden nicht gespeichert (nur einmalig im Response) | `audio_router.py:741-768` | User kann Stems nicht wiederfinden ohne Disk-Scan |
| **L-N5** | `ProductionView` hat kein UI für `bitrate_mbps` Override — Default 12 wird hartcoded gesendet | `ProductionView.xaml`, `RenderRequest` | Kein User-Control über Bitrate |
| **L-N6** | `ProductionView` hat kein UI für `encoder` Override — `RenderRequest.Encoder = null` immer | analog | Encoder-Detection ist server-side, nicht überschreibbar |
| **L-N7** | `thumbnail_available` Flag im Video-Clip wird nie auf True gesetzt (immer false in `register_video_clip`) | `video_router.py:115`, kein Update | Cosmetic — Flag ist nie true |
| **L-N8** | `BeatData.strength` ist immer 1.0 (BeatDetector liefert keine Strength-Differenzierung) | `audio_router.py:613` | Keine Differenzierung schwacher/starker Beats für Pacing |

---

# TEIL I — UNGENUTZT-PERSISTIERTE FELDER (Komplettliste)

**Audio (im audio_analysis_cache oder ai_data_json gespeichert, kein aktiver Konsument):**
1. `key` — angezeigt in TONART-Card, aber `use_key_matching` ist no-op (L-K4)
2. `beat_count` — INFO-only (Anzeige in BEATS-Card)
3. `spectral_data.bands.mid` (L-M2)
4. `spectral_data.bands.high` (L-M2)
5. `spectral_data.frequency_ranges` (L-N1)
6. `subtrack_segments` (L-K1) — kommt nicht mal in den Cache
7. `tempo_curve` (L-M1) — kommt nicht mal in den Cache
8. `audio_hash` (L-N2) — keine UI

**Video (im video_analysis_cache oder ai_data_json gespeichert, kein aktiver Konsument):**
1. `motion.peak_motion` (L-K3) — gar nicht berechnet
2. `motion.motion_curve` (L-M3) — injiziert ohne Engine-Konsument
3. `motion.peak_frames` — injiziert, kein dezidierter Engine-Use
4. `motion.motion_category` — nicht in UI
5. `dominant_colors` (L-K2) — gar nicht berechnet, Helper-API ungenutzt
6. `tags` (L-K2) — gar nicht berechnet, Helper-API ungenutzt
7. `has_embedding` — UI hat keinen Indikator (nur indirekt via SmartDirector)
8. `embedding_dim` / `embedding_samples` (L-M8) — nicht persistiert
9. `video_hash` (L-N3)
10. `width`, `height`, `fps`, `codec` — nur intern, keine Card

---

# TEIL J — Top-10 KRITISCHE LÜCKEN (Priorisierung)

| Rank | ID | Beschreibung | Severity |
|---|---|---|---|
| 1 | L-K1 | Subtracks gehen verloren (in Cache nicht persistiert) — BROKEN-CHAIN von Stage A5 zu Pacing | KRITISCH |
| 2 | L-K2 | Moondream-Tagging nicht angeschlossen — `dominant_colors` + `tags` immer leer trotz Helper-API + clip_data-Pipeline | KRITISCH |
| 3 | L-K4 | `UseKeyMatching` ist no-op — UI suggeriert Funktion, ist aber wirkungslos | KRITISCH |
| 4 | L-K5 | Stem-Pacing Feature DEAD CODE — `generate_cut_list_with_stems` nicht erreichbar | KRITISCH |
| 5 | L-K3 | `motion.peak_motion` immer 0 — wird im Analyse-Code nie gesetzt | MITTEL-HOCH |
| 6 | L-M3 | `motion.motion_curve` injiziert aber Engine konsumiert es nicht aktiv | MITTEL |
| 7 | L-M4 | Motion-Anzeige fehlt komplett in VideoLibraryView | MITTEL |
| 8 | L-M2 | `spectral.bands.mid/high` ungenutzt — nur `low` für Pacing | MITTEL |
| 9 | L-M1 | `tempo_curve` ungenutzt | MITTEL |
| 10 | L-M7 | Pacing sendet keine inkrementellen SSE-Events — UX-Problem bei langen Mixen | MITTEL |

---

# TEIL K — RENDER-PIPELINE BEOBACHTUNGEN (zusammengefasst)

1. **Render konsumiert NUR 5 Felder** aus state: `metadata.file_path`, `metadata.clip_start`, `start_time`, `end_time`, `request.audio_path`. ALLES andere wird ignoriert (Audio-Analyse, Video-Analyse, Embeddings).
2. **Audio wird ungekürzt gemuxt** — `-t {audio_dur}` cap. Audio-Cuts/Beats spielen im finalen Output keine Rolle, nur die Video-Schnittliste.
3. **Normalisierung ist redundant** — `_normalize_clips` ruft pro Clip `_check_needs_normalization` mit eigenem ffprobe auf, obwohl `state.video_clips[id]` width/height/fps schon kennt.
4. **Encoder-Detection ist class-level cached** — guter Pattern, einmal beim ersten RenderService-Init.
5. **Cancel-Support sauber** — Polling über `cancel_callback` bei jedem Progress-Tick + finale Kontrolle nach GPU-Lock release.
6. **Persistente Render-Queue** mit Idempotency (media_hash über audio_path + timeline) — Crash-Recovery via `restore_render_queue_on_startup`.
7. **Output-Mtime-Schutz** verhindert Löschen einer vorher fertigen Render-Ausgabe bei Cancel.

**Sauberer Architektur-Decision:** Render-Pipeline ist absichtlich „dumm". Alle Audio/Video-Intelligenz muss spätestens im Pacing landen, sonst geht sie verloren. Das ist by-design — Render = pure FFmpeg-Concat-Demuxer-Layer.

---

# TEIL L — Bezug zu vorherigem Audit

`AUDIT_DATA_FLOW_2026-05-09.md` (BPM-Workflow + Audio→Pacing Mismatch) ist seit Phase A (Commits 6f4de96..5b05915) abgearbeitet:
- DirectorViewModel sync Bpm zu SelectedClip ✅
- energy_curve cached injection (Audit A2) ✅
- structure_segments cached injection (Audit A3) ✅
- spectral.bands.low (bass curve) injection (Audit E2) ✅
- subtrack_segments injection (Audit E3) — **wirkt aber NICHT** weil L-K1 (subtracks landen nicht im cache)
- key_matching pipeline (Audit E1) — **wirkt aber NICHT** weil L-K4 (Video-Clips haben kein audio_key)
- Video-clip_data motion_curve/dominant_colors/tags/has_embedding (Audit A4) — gepiped, aber Engine-Konsumenten unvollständig (L-M3, L-K2)

**Neue Findings dieses Audits:**
- L-K1 (subtracks chain broken) — vorher nur als „NICHT VERWENDET" notiert, jetzt detektiert dass die Cache-Population die Ursache ist
- L-K2 (Moondream nie aufgerufen) — neu: dominant_colors/tags Pipeline ist leer trotz Engine-Helpers
- L-K3 (peak_motion immer 0) — neu
- L-K5 (Stem-Pacing DEAD CODE) — neu
- L-M5 (`/video/motion` API ohne UI-Konsument) — neu
- L-M7 (Pacing keine inkrementellen SSE) — neu

---

**Audit Ende.** Status: HONEST. Alle Felder geprüft mit konkreten file:line Referenzen.
