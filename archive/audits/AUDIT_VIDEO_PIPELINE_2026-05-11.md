# Audit: Video-Pipeline Deep-Audit

**Datum:** 2026-05-11
**Auftrag:** Read-only Deep-Audit der Video-Pipeline (Module, Backend, DB, Schemas).
**Scope:** `src/pb_studio/video/*`, `backend/routers/video_router.py`, `backend/schemas/video_schemas.py`, Video-Anteile in `backend/app_state.py` + `src/pb_studio/data/database_core.py`, `src/pb_studio/ai/siglip_wrapper.py`.

---

## Stage-Flow

```
POST /video/import  ──────────────────────────────────────────────────────┐
  validate (absolute_path, ext, exists)                                   │
  _get_video_info ── ffprobe (width/height/fps/codec/duration)            │
  media_hash (sha256, chunked + SSE Progress)                             │
  state.register_video_clip ── persist_video_clip (in-memory + SQLite)    │
  publish_event("import_progress")                                        │
                                                                          ▼
GET /video/thumbnails/{id} ── ffmpeg -ss 1 -frames:v 1 ── tmpfile ── JPEG bytes
                                                                          ▼
POST /video/analyze ── with_gpu_task("video_analysis_full") ── _run_video_analysis
  ├─ Phase 1: SceneDetector (PySceneDetect / AdaptiveDetector)
  ├─ Phase 2: 2 fps frame-sample loop → MotionAnalyzer.analyze_video_segment (RAFT)
  ├─ Phase 3: SigLIP encode_image × N frames → mean → L2-norm → VectorStore("video_index")
  ├─ Phase 4: KMeans dominant_colors + Moondream tags (mid-frame)
  └─ Phase 5: ffmpeg WAV-extract 30s → KeyDetector → audio_key
  state.set_video_analysis + state.update_video_analysis (DB persist ai_data_json)
  SSE: init → scenes → motion+embedding (per-frame) → finalize → complete
                                                                          ▼
GET /video/clips ── list_clips ── snapshot.values() + analysis_snap
GET /video/scenes/{id} ── analysis["scenes"]
GET /video/motion/{id} ── MotionData(**motion)   ◄── peak_motion silently dropped (schema mismatch)
DELETE /video/clips/{id} ── pop in-memory + MediaRepository.delete_media
```

---

## Per-Feld Lifecycle-Matrix (video_analysis_cache)

| Feld | Write (analyze) | Cache | Persist (ai_data_json) | Reload (load_from_db) | API/UI-Konsument | Pacing-Konsum | Status |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| `scene_count` | ✅ L610 | ✅ | ✅ L607-608 | ✅ L886 | ✅ `VideoAnalysisResult` | indirekt via `scenes` | **OK** |
| `scenes` (list[SceneInfo]) | ✅ L601-609 | ✅ | ✅ L617-618 | ✅ L889 | ✅ `/video/scenes/{id}` | ✅ als `scene_changes` (pacing_router:460) | **OK** |
| `avg_motion` | ✅ L695 | ✅ | ✅ L609-610 | ✅ L887 | ✅ Top-level + Motion | ✅ `motion_score` | **OK** |
| `motion.peak_motion` | ✅ L690 (L-K3 fix) | ✅ | indirekt im `motion`-Dict via L619-620 | ✅ als Teil von `motion` L890 | ❌ **FEHLT im `MotionData`-Schema** | ✅ pacing_router:457 | **🔴 Schema-Leak: API gibt es NIE zurueck** |
| `motion.motion_curve` | ✅ L691 | ✅ | ✅ via motion-dict | ✅ via motion-dict | ✅ MotionData.motion_curve | ✅ pacing_router:459 | **OK** |
| `motion.peak_frames` | ✅ L692 | ✅ | ✅ | ✅ | ✅ | ✅ | **OK** |
| `motion.motion_category` | ✅ L693 | ✅ | ✅ | ✅ | ✅ MotionData | ❌ nirgends gelesen | **🟡 INFO-only** |
| `motion.clip_id` | ✅ L688 | ✅ | ✅ | ✅ | ✅ | n/a | **OK** |
| `dominant_colors` | ✅ L812 | ✅ | ✅ L621-622 | ✅ L891 | ✅ VideoAnalysisResult | ✅ pacing_router:461 | **OK** |
| `tags` (Moondream) | ✅ L813 | ✅ | ✅ L623-624 | ✅ L892 | ✅ VideoAnalysisResult.tags | ✅ pacing_router:462 | **OK** (wenn Moondream verfuegbar) |
| `audio_key` (L-K4) | ✅ L836 | ✅ | ✅ L625-626 | ✅ L896 | ✅ VideoAnalysisResult.audio_key | ✅ pacing_router:464 | **OK** |
| `embedding_dim` (L-M8) | ✅ L760 | ✅ | ✅ L628-629 | ✅ L894 | ✅ | n/a | **OK** |
| `embedding_samples` (L-M8) | ✅ L761 | ✅ | ✅ L633-634 | ✅ L895 | ✅ | n/a | **OK** |
| `has_embedding` | ✅ L759 | ✅ | ✅ L611-612 + L632 derived | ✅ L888 | ✅ | ✅ pacing_router:463 | **OK** |
| `mood_tags` (Schema) | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ Schema-Default `[]` | ❌ | **🟡 DEAD-SCHEMA-FELD** |
| `style_tags` (Schema) | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ | ❌ | **🟡 DEAD-SCHEMA-FELD** |
| `object_tags` (Schema) | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ | ❌ | **🟡 DEAD-SCHEMA-FELD** |
| `brightness_curve` | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ | ❌ | **🟡 DEAD-SCHEMA-FELD** |
| `saturation_curve` | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ | ❌ | **🟡 DEAD-SCHEMA-FELD** |
| `color_temp_curve` | ❌ NIE geschrieben | ❌ | ❌ | ❌ | ⚠️ | ❌ | **🟡 DEAD-SCHEMA-FELD** |

## Per-Feld video_clips (Top-Level)

| Feld | Import-Write | Persist (`persist_video_clip`) | Reload (`load_from_db`) | API/UI | Status |
|---|:-:|:-:|:-:|:-:|---|
| `id, name, path, duration, width, height, fps, codec` | ✅ | ✅ | ✅ | ✅ | **OK** |
| `thumbnail_available` | ✅ L115 false | ❌ nicht persistiert | hardcoded `False` L875 (by design) | ✅ | **OK by design** |
| `tags` | ✅ L116 `[]` | ❌ | hardcoded `[]` L876 (analysis-tags landen separat in cache) | ✅ | **OK (Verwirrung)** |
| `video_hash` (L-N3) | ✅ L117 | ❌ **NIE im `persist_video_clip` (app_state.py:717-743)** | ❌ NIE in `load_from_db`-video-Branch (L866-877) | ✅ | **🔴 PERSISTENZ-LUECKE: nach Reload immer None** |
| `has_video_embedding` | ✅ L118 false | ❌ | ❌ | ❌ Schema-Feld VideoClipInfo, aber nie befuellt | **🟡 DEAD-FELD** |

---

## Findings

### L-VIDEO-1 [HIGH] — FAISS Index-Name Split: SigLIP-Embeddings unauffindbar fuer Pacing
- **Wo:** `backend/routers/video_router.py:751` schreibt nach `VectorStore(index_name="video_index")`. `src/pb_studio/pacing/semantic_matcher.py:162` liest aus `VectorStore(index_name="main_index")`.
- **Effekt:** SemanticMatcher liest NIE die in video-Analyse generierten Embeddings. `_query_vector_store()` liefert leere Kandidatenlisten → semantic_matching-Branch im Pacing ist faktisch tot, obwohl SigLIP korrekt encoded + persistiert wird.
- **Verifikation:** Grep nach `index_name=` ergibt nur "video_index" in video_router, "main_index" in semantic_matcher, "video_clips" in Docs/Demos.

### L-VIDEO-2 [HIGH] — `MotionData`-Schema fehlt `peak_motion`; API gibt es NIE aus
- **Wo:** `backend/schemas/video_schemas.py:84-91` `class MotionData` enthaelt `peak_motion` NICHT. `video_router.py:495` macht `MotionData(**motion)` — Pydantic v2 ignoriert das zusaetzliche `peak_motion`-Field silent → `/video/motion/{id}` liefert NIE peak_motion.
- **Effekt:** Backend persistiert + pacing liest direkt aus `analysis_cache.motion.peak_motion`, aber das `/video/motion`-REST-Endpoint + die C# `MotionData` (ApiClient.cs:492) zeigen es nicht. UI-Detail-Panel kann peak_motion nicht via Motion-Endpoint nutzen, nur via `VideoClipInfo.peak_motion` (list_clips L199-201).
- **Konsistenz-Bruch:** `VideoClipInfo.peak_motion` IS gepflegt (L33), aber `MotionData.peak_motion` fehlt.

### L-VIDEO-3 [HIGH] — `video_hash` (L-N3) wird NICHT persistiert + NICHT reloaded
- **Wo:**
  - Schreibt: `video_router.py:117` `"video_hash": video_hash_value`.
  - `app_state.register_video_clip` (L376) ruft `persist_video_clip(clip)` (L717).
  - `persist_video_clip` Meta-Dict (L725-733) enthaelt KEIN `video_hash`. `file_hash`-Argument zu `repo.add_media` ist hardcoded `""` (L737) — im Gegensatz zu `persist_audio_clip` wo `clip.get("audio_hash") or ""` (L709) gesetzt wird.
  - `load_from_db` Video-Branch (L865-877) baut clip-Dict ohne `video_hash`.
- **Effekt:** Nach Backend-Restart/Project-Reopen ist `video_hash` immer None. EmbeddingCache-Lookup (`pacing_router.py:106-110`) findet nichts → Embedding-Cache-Hits nur in aktueller Session.
- **DB-Reuse-Pfad (`register_video_clip` L390-410):** Beim Wiederfinden eines DB-Records wird `video_hash` NICHT aus Meta wiederhergestellt. `tags` wird hardcoded `[]` (L406).

### L-VIDEO-4 [HIGH] — Schema-Felder ohne Producer: `mood_tags`, `style_tags`, `object_tags`, `brightness_curve`, `saturation_curve`, `color_temp_curve`
- **Wo:** `backend/schemas/video_schemas.py:59-69` deklariert sechs Listen, die in `_run_video_analysis` NIE gesetzt werden. Auch keine Konsumenten in pacing/brain.
- **Effekt:** Tote Schema-Felder; API gibt sie immer leer zurueck; verleitet Konsumenten zu "Ich verlass mich auf Schema" und liefert dann leere Daten. Toter Code-Path verschleiert echte Datenfluesse.

### L-VIDEO-5 [HIGH] — Frame-Sample-Loop verpasst das letzte Sample
- **Wo:** `video_router.py:632` `for i in range(0, total - step, step)`. Bei `total - step` als oberer Grenze faellt das letzte gueltige Sample bei `i = total - step` raus (range schliesst es aus).
- **Effekt:** Letzter Time-Bucket des Videos wird ueber alle Phasen (Motion-Frame-Loop **und** Embedding-Frame-Loop L729) konsistent ausgelassen. Lange Outro-Aufnahmen werden nie analysiert → systematischer Bias.
- **Wiederholung:** Identischer Bug in SigLIP-Loop L729 `range(0, max(total_frames - sample_step, 1), sample_step)`.

### L-VIDEO-6 [MEDIUM] — `load_from_db` ueberschreibt `tags` mit `[]` trotz Cache-Restore
- **Wo:** `app_state.py:876` `"tags": []` in der video-clip-Dict. Im Cache wird `tags` aus `ai_data` korrekt geladen (L892). UI-Pfade die `vc.get("tags")` lesen sehen leere Liste, da der TOP-LEVEL-clip immer leere Tags hat.
- **Effekt:** Doppel-Speicherung von "tags" (clip vs. analysis_cache) ist semantisch unklar. UI-`VideoClipInfo.tags` (Schema-Feld L23) wird aus `c["tags"]` befuellt → IMMER leer, selbst wenn analyse-tags existieren.
- **Konsistenz-Bruch zu Audio:** Audio macht das nicht so — `tags` ist nur im analysis-cache.

### L-VIDEO-7 [MEDIUM] — Moondream `_init_model()` mit Private-API-Zugriff
- **Wo:** `moondream_wrapper.py:117` `analyzer._init_model()` direkt aufgerufen — public API ist `is_ready` (lazy). Kein Funktionsbruch, aber abstraktionsverletzend; bei Refactor des Init-Pfads bricht der Wrapper.
- **Zusatz:** Wenn Moondream encoder-only ONNX vorhanden ist (decoder fehlt), gibt `is_ready` False zurueck (`moondream.py:719-722`: braucht entweder combined oder encoder+decoder). Es gibt keinen Codepfad in dem encoder-only sinnvoll zu Tags fuehrt — Tags werden dann immer `[]`. Auch wenn der user `request.generate_captions=True` sendet ist die Wahrscheinlichkeit `[]` zu sehen hoch.
- **`request.generate_captions` Default:** `VideoAnalyzeRequest.generate_captions=False` (L49) — Tags + dominant_colors werden bei Standardanalyse NIE generiert. Wenn UI das Flag nicht aktiv setzt, sind `tags` + `dominant_colors` immer `[]`.

### L-VIDEO-8 [MEDIUM] — `_get_video_info` ohne `cwd`-Schutz oder Path-Quoting bei ffprobe
- **Wo:** `video_router.py:506-512` baut Command-Args. Pfad als unquoted Argument an `subprocess.check_output(..., shell=False)` — gut. Aber `timeout=30` ohne Retry/Logging des stderr → schwer zu diagnostizieren wenn ffprobe haengt.
- **Edge:** `data.get("streams", [{}])[0]` crasht wenn `streams` leer ist (z.B. Audio-only-File mit .mp4-Endung). Try-Block faengt das im Caller (L72-74) aber loggt nur `"Video-Info fehlgeschlagen"` ohne weitere Telemetrie. Niedrige Prio.

### L-VIDEO-9 [MEDIUM] — `audio_key_detector` Tempfile-Handling auf Windows
- **Wo:** `audio_key_detector.py:52-83`. `NamedTemporaryFile(suffix=".wav", delete=False)` mit `with`-Block, der nur den Open-Handle schliesst (delete=False also kein Auto-Cleanup). Danach `ffmpeg -y ... str(tmp_wav)` ueberschreibt das (jetzt geschlossene) File.
- **Race:** Auf Windows kann der Handle in seltenen Faellen noch durch Antivirus/Indexer gehalten werden zwischen `with`-exit und ffmpeg-Open. `-y` wuerde dann fehlschlagen. Best-Practice: temp-name generieren mit `tempfile.mkstemp()` und Handle SOFORT schliessen.
- **Empfehlung:** Path-Race ist nicht 100% theoretisch — `tempfile.mkstemp` + os.close + use.

### L-VIDEO-10 [MEDIUM] — `RAFT` `is_ready` ohne `_init_failed`-Pfad-Reset
- **Wo:** `raft.py:135-190`. Nach `_init_failed=True` (z.B. fehlende DirectML) kann `MotionAnalyzer` nicht neu initialisiert werden ohne neue Instanz — by-design. Aber `factory create_motion_analyzer` (L743) gibt einen `lazy_load=False` Analyzer zurueck. Bei kalt-Start ohne RAFT-Modell ist `is_ready=False`, video_router-Phase 2 macht `if len(frames) >= 2: MotionAnalyzer()` direkt → frischer Analyzer der wieder versucht zu laden. Im Hot-Path NICHT cached.
- **Wirkung:** Pro analyze-Call wird RAFT-Init versucht. Bei fehlendem Modell: Log-Spam vermieden durch `_init_failed`-Flag, aber jeder analyze-Call zahlt den ONNX-Init-Versuch.

### L-VIDEO-11 [LOW] — `VideoClipInfo.has_video_embedding` Feld nie befuellt
- **Wo:** Schema L29 `has_video_embedding: bool = False`. Backend setzt es nur beim Import (L118 = False). Nach Embedding-Generierung (L759 `result["has_embedding"]=True`) wird NICHT in `update_video_clip` zurueckpropagiert. `list_clips` injiziert `has_embedding` (anderes Feld) aus video_analysis_cache (L221).
- **Konsequenz:** `has_video_embedding` und `has_embedding` sind zwei unterschiedliche Felder im Schema — verwirrend. Vermutlich Duplikat. C# Record (ApiClient.cs:440-458) hat KEINS davon. Tote Spalte im Schema.

### L-VIDEO-12 [LOW] — `tags` vom Backend ist Frame-1-Single-Sample (mid-frame)
- **Wo:** `video_router.py:801-808` extrahiert NUR den mittleren Frame fuer dominant_colors + tags. Im Gegensatz zu Embeddings (N gleichmaessig verteilte Frames) und Motion (2 fps Grid).
- **Effekt:** Lange Videos mit Szenenwechsel werden nicht repraesentiert. Konzept "ueber gesamte Datei" wurde fuer Motion + Embedding angewendet, aber nicht fuer Tags/Colors.

### L-VIDEO-13 [LOW] — `SceneDetector` Threshold-Konstante hardcoded
- **Wo:** `scene_detect.py:7` `threshold=8.0`. Kein UI-Toggle, kein Konfig-Override. `AdaptiveDetector` mit `min_scene_len=15` (frames). Bei 25fps = 0.6s minimale Szene → harmlos.
- **Aber:** kein `_classify_scene_type`. Alle Cuts werden hartcoded `scene_type="cut"` (video_router.py:605), confidence `0.85` (L606). Schema-Feld `confidence: float = 0.0` wird nie aus echten Daten befuellt.

### L-VIDEO-14 [LOW] — `MotionAnalyzer.calculate_flow` nicht-initialisierter Pfad gibt Null-Flow zurueck
- **Wo:** `raft.py:265-268`. Bei `_init_failed=True` (z.B. fehlendes Modell) kommt fuer JEDES frame-pair ein `np.zeros`-Tupel zurueck → motion-Metrics alle 0.0 → `motion_category="static"` (L848) selbst bei rauschintensiven Videos.
- **Effekt:** Stille Default-Ergebnis bei fehlendem RAFT. `_run_video_analysis` loggt zwar warn, aber Endresult sieht aus wie "valides Static-Video". Falls UI das anzeigt: User sieht "all static" und versteht nicht, dass RAFT fehlt.

### L-VIDEO-15 [LOW] — SigLIP-Embedding Sample-Cap
- **Wo:** `video_router.py:727` `n_emb_samples = max(3, int(duration_sec / 5.0))`. Fuer 60min Video = 720 samples × SigLIP forward → ~12min Compute auf DirectML. Kein Cap. CLAUDE-Rule sagt "kein Sampling-Cap", aber fuer Embeddings koennte das den Throughput im Long-Mix-Pfad killen.
- **Risiko:** Single-call kann das mit-VRAM-Budget reservierte `video_analysis_full` Lock fuer beliebig lange Zeit halten.

### L-VIDEO-16 [LOW] — `extract_dominant_colors` ImportError-Fallback erreicht ggf. unbenutzt
- **Wo:** `moondream_wrapper.py:58-65`. `ImportError` branch fuer `sklearn` — aber `sklearn` ist im requirements.txt locked. Toter Fallback (nicht falsch, nur dead code path).

### L-VIDEO-17 [LOW] — Video-Embedding-Insert ohne `clip_id` Idempotenz-Check
- **Wo:** `video_router.py:752-758` `vs.add_embedding(...)`. Wenn ein Clip mehrfach analysiert wird, gibt es N FAISS-Eintraege fuer dieselbe `clip_id`. Kein Dedupe.
- **Effekt:** Re-analyze fluegt redundante Embeddings ins Index → Suche liefert duplizierte Treffer mit gleicher metadata.

### L-VIDEO-18 [LOW] — `VideoAnalysisResult.embedding_dim` Default `0`, C# Record Default `1152`
- **Wo:** Pydantic schema L62 `embedding_dim: int = 0`. C# Record (ApiClient.cs:460) `EmbeddingDim = 1152`. Bei `has_embedding=False` (kein Embedding generiert) liefert Backend `0`, C# zeigt aber Default `1152` falls Field fehlt — Type-Mismatch nur bei alten Server-Versionen ohne Field.

### L-VIDEO-19 [INFO] — `MotionAnalyzer.analyze_video_segment` ruft 2× RAFT pro Pair auf
- **Wo:** `raft.py:632-633` `get_motion_magnitude(f1, f2)` + L635 `detect_scene_change(f1, f2)`. Beide Methoden rufen intern `calculate_flow` (L373, L424) auf — d.h. 2x ONNX-Inference pro Frame-Pair. Effektive Frame-Rate halbiert sich.
- **Optimization:** Flow einmal berechnen, beiden Konsumenten reichen.

### L-VIDEO-20 [INFO] — `_classify_motion` Thresholds magic numbers
- **Wo:** `video_router.py:846-854`. Thresholds 2/8/20. Keine config, keine Tests die Verteilung verifizieren. Bei RAFT-DirectML in 448×256 normalisierten Pixelkoordinaten — Realistische Magnitudes liegen meist <10 → "high"-Bucket selten erreicht.

---

## Top 5

1. **L-VIDEO-1 (HIGH)** — FAISS-Indizes split: SigLIP-Video-Embeddings landen in `video_index`, SemanticMatcher liest aber `main_index`. Pacing-Semantic-Matching kann NIE Video-Embeddings nutzen.
2. **L-VIDEO-3 (HIGH)** — `video_hash` wird NICHT persistiert und NICHT reloaded. Nach Backend-Restart immer None → EmbeddingCache-Hit-Rate auf 0%.
3. **L-VIDEO-2 (HIGH)** — `MotionData`-Pydantic-Schema fehlt `peak_motion`, das `/video/motion/{id}`-Endpoint liefert das Feld NIE (Pydantic-Drop). C# `MotionData` ebenso. Backend-Cache + Pacing nutzen es, aber UI hat keinen Zugriff via Motion-API.
4. **L-VIDEO-5 (HIGH)** — Frame-Sampling-Loops (Motion **und** Embedding) verpassen systematisch das letzte Sample. Long-Outro-Segmente werden nie analysiert.
5. **L-VIDEO-4 (HIGH)** — Sechs Pydantic-Schema-Felder (`mood_tags`, `style_tags`, `object_tags`, `brightness_curve`, `saturation_curve`, `color_temp_curve`) ohne Producer. Permanent leer, irrefuehrend.

**Total Count:** 20 Findings (5 HIGH, 5 MEDIUM, 8 LOW, 2 INFO).

---

## Empfehlung (NICHT angewendet — Audit-only)

**Quick-Wins (low risk, high impact):**
1. **L-VIDEO-1:** Index-Name vereinheitlichen — entweder beides "main_index" oder beides "video_index". Bestehende Indizes migrieren oder neu builden.
2. **L-VIDEO-3:** `persist_video_clip` Meta erweitern um `video_hash`, `file_hash` an `repo.add_media` durchreichen analog zu `persist_audio_clip`. `load_from_db` video-Branch um `video_hash` aus meta erweitern. DB-Reuse-Pfad (L390-410) `video_hash` aus meta + `file_hash` rekonstruieren.
3. **L-VIDEO-2:** `MotionData`-Schema um `peak_motion: float = 0.0` erweitern. C# Record an C#-Backend-Schemata anpassen. ApiClient.cs:492 angleichen.
4. **L-VIDEO-5:** `range(0, total, step)` statt `range(0, total - step, step)`. Identisch in Embedding-Loop.
5. **L-VIDEO-4:** Entweder Producer fuer die sechs toten Felder schreiben (z.B. `brightness_curve` aus OpenCV-Histogram pro Frame), oder Felder aus dem Schema entfernen.

**Mittel:**
6. **L-VIDEO-6:** `tags` aus `video_clip`-Top-Level entfernen (Single-Source-of-Truth = `analysis_cache.tags`).
7. **L-VIDEO-19:** RAFT-Flow einmal berechnen + an `motion_statistics` + `detect_scene_change` weitergeben — halbiert ONNX-Calls.
8. **L-VIDEO-17:** Video-Embedding-Insert: erst pruefen ob `clip_id` schon im Index, sonst skippen oder ueberschreiben.

**Low:**
9. **L-VIDEO-9:** `tempfile.mkstemp()` statt `NamedTemporaryFile(delete=False)`-with-block in `audio_key_detector`.
10. **L-VIDEO-12:** `tags`/`dominant_colors` analog zu Motion ueber N verteilte Frames mitteln.

---

## Cross-Modul-Hinweise

- **`backend/app_state.py:557-685` `update_video_analysis`** ist defensiv (partielle Updates), aber `audio_key` wird ohne expliziten `if`-Check beruechsichtigt (L625) — `None`-Werte wuerden `ai_data["audio_key"]=None` setzen, was `is None`-Check oben (`if audio_key is not None`) sauber blockt. OK.
- **`scene_detect.py:67-73`** Video-Handle-Release ueber `release()`/`close()`-Probe — defensiv gut.
- **SigLIP `siglip_wrapper.py:114-123` `encode_image`** macht `emb.ndim==2 → np.mean(axis=0)`. Pruefung der vision-Output-Shape erfolgt nur defensiv; bei OOM/DirectML-Fehler returnt None silent — Video-Embedding-Loop (video_router.py:736-738) faengt das ab.
- **VRAM-Budget:** `with_gpu_task(_run_video_analysis, ..., model_id="video_analysis_full")` reserviert VRAM fuer RAFT **+** SigLIP **+** Moondream gemeinsam. Wenn nur Moondream verfuegbar ist, ist der Budget-Check evtl. ueberhoeht.

## Quellen

- `backend/routers/video_router.py:1-855`
- `backend/schemas/video_schemas.py:1-95`
- `backend/app_state.py:120-138, 175-193, 205-218, 547-686, 717-743, 745-922`
- `src/pb_studio/video/raft.py:1-775`
- `src/pb_studio/video/scene_detect.py:1-74`
- `src/pb_studio/video/moondream_wrapper.py:1-151`
- `src/pb_studio/video/moondream.py:171-722`
- `src/pb_studio/video/audio_key_detector.py:1-91`
- `src/pb_studio/video/frame_extractor.py:1-124`
- `src/pb_studio/ai/siglip_wrapper.py:1-181`
- `src/pb_studio/pacing/semantic_matcher.py:156-200`
- `src/pb_studio/data/database_core.py:34-123`
- `PBStudio.UI/Services/ApiClient.cs:440-495`
- `backend/routers/pacing_router.py:95-130, 442-465`
