# AUDIT Audio-Pipeline Deep — 2026-05-11

Read-only Deep-Audit der Audio-Pipeline (Module, Router, Schemas, AppState-Audio-Sektionen, DB-Schema). Andere Schichten (Video, Render, Frontend, GPU/State-General) bewusst ausgeklammert.

Scope:
- `src/pb_studio/audio/{beat_detector,spectral_analyzer,key_detector,structure_analyzer,waveform_analyzer,streaming_analyzer,subtrack_detector}.py`
- `backend/routers/audio_router.py`
- `backend/schemas/audio_schemas.py`
- `backend/app_state.py` (Audio-relevante Methoden + Caches)
- `src/pb_studio/data/database_core.py`

---

## 1. Pipeline-Flow

```
1. IMPORT  (POST /audio/import)
   ├── _probe_audio_info()             -> duration / sr / channels (ffprobe)
   ├── media_hash() (streaming)         -> audio_hash (sha256)
   ├── state.register_audio_clip()      -> in-memory + persist_audio_clip()
   │                                       -> DB media row (meta JSON inkl. audio_hash)
   ├── if duration >= 60s:
   │     SubtrackDetector().detect()    -> result.segments + result.tempo_curve
   │       L-AUDIO-9: result.boundaries (component-scores) discarded
   ├── clip["subtrack_segments"]/["tempo_curve"] = ...    (in-memory dict)
   ├── state.update_audio_analysis(subtrack_segments, tempo_curve)
   │     -> writes audio_analysis_cache + media.ai_data_json
   │       L-AUDIO-6: is_analyzed bleibt False -> load_from_db ueberspringt diese Eintraege
   └── SSE: import_progress {percent:100}

2. ANALYZE  (POST /audio/analyze)
   _run_audio_analysis(audio_path, clip_id, request):
   ├── librosa.load(audio_path, sr=22050, mono=True)      <- volles File in RAM!
   │     L-AUDIO-1: kein duration-Cap, kein Streaming, ignoriert
   │                StreamingAudioAnalyzer komplett
   ├── BeatDetector singleton (_get_beat_detector, offline/DBN)
   │     .detect_beats(audio_path, on_progress=...)        <- LAEDT FILE NOCHMAL
   │     L-AUDIO-2: zweiter Disk-Read + Resample im selben Call
   │   -> beat_times list[float]
   │   -> BeatDetector.compute_beat_strengths(y,sr,beat_times)  (jetzt real)
   │   -> bpm via local np.median(diff(beats))             <- L-AUDIO-3: BeatDetector.get_bpm() dupliziert
   │   -> energy_curve via librosa.feature.rms(y)
   ├── StructureAnalyzer().analyze_song_structure(y, sr)
   ├── SpectralAnalyzer(sr=sr).analyze_from_array(y, sr)
   │   spec_result hat: times, band_energies, centroids,
   │                    band_means, band_variances, events, duration, num_frames
   │   audio_router schreibt nur:
   │       {clip_id, times, bands(=band_energies), centroids, frequency_ranges}
   │     L-AUDIO-4: band_means + band_variances + events VERWORFEN
   ├── KeyDetector().detect_key(y, sr)
   └── return dict {bpm, beats[BeatData], key, energy_curve, structure_segments, spectral_data, ...}
   ^ AudioAnalysisResult schema enthaelt subtrack_segments/tempo_curve aber
     analyze() liefert sie NICHT (nur Import setzt sie)  -> L-AUDIO-5

   Persistence (in audio_router.analyze_audio):
   ├── state.set_audio_analysis(clip_id, result)            -> Cache: beats=list[dict]
   ├── state.update_audio_analysis(beats_json=json.dumps(...), ...)
   │     -> ai_data_json (DB) sowie cache_update["beats_json"]=list[dict]
   │     L-AUDIO-7: Cache hat danach BEIDE keys ("beats" und "beats_json")
   │                mit demselben Inhalt -> Pacing-Service liest "beats"
   │                aber load_from_db liest "beats_json"

3. CONSUME (pacing_router -> pacing_service -> AdvancedPacingEngine)
   cached_analysis = state.get_audio_analysis(clip_id) or {}
   -> beats, bpm, key, energy_curve, spectral_data, structure_segments,
      subtrack_segments, tempo_curve werden via PacingService injected
   -> AdvancedPacingEngine konsumiert:
      _pre_cached_energy / _pre_cached_spectral_bass/mid/high /
      _pre_cached_structure / _pre_cached_subtracks / _pre_cached_tempo_curve
   stems_paths-Branch (use_stem_pacing): pacing_router liest direkt
      audio_clips[id]["stems_paths"]  -> L-AUDIO-8: DB-Persistenz fehlt

4. RELOAD (state.load_from_db)
   -> rekonstruiert: bpm, key, beat_count, beats(parse beats_json),
      energy_curve, structure_segments, spectral_data, duration_seconds
   Nicht restored: subtrack_segments, tempo_curve, audio_hash-driven
      embedding-Status, stems_paths
```

---

## 2. Findings

### L-AUDIO-1 [CRITICAL] — StreamingAudioAnalyzer wird nie aufgerufen
**File:Line:** `backend/routers/audio_router.py:616`, `src/pb_studio/audio/streaming_analyzer.py` gesamt.
**Problem:** `_run_audio_analysis` ruft unbedingt `librosa.load(audio_path, sr=22050, mono=True)` ohne `duration`-Limit. Bei 90min-Mix sind das ~120M float32-Samples = ~480MB RAM allein fuer das audio-Array, plus BeatNet/STFT/Chroma-Buffer. `StreamingAudioAnalyzer` (extra fuer >60min gebaut, in `__init__.py` exportiert, vollstaendig getestet `test_streaming_analyzer.py`) wird in keinem Router/Service/Worker referenziert.
**Evidence:** `grep -r StreamingAudioAnalyzer src/ backend/` -> nur self-reference und Test/Audit-Markdown. Zudem hat `BeatDetector.detect_beats()` einen eigenen `>600s -> librosa-Fallback`-Pfad (Zeile 221) der das Problem nur partiell loest (Beats), nicht aber Spectral/Structure/Key.
**Impact:** OOM-Risiko fuer 60+min Mixe. Hauptzielgruppe (DJ-Mixe) wird genau hier nicht skaliert.
**Fix:** In `_run_audio_analysis` Duration-Branch einfuehren: bei `duration > 600s` `StreamingAudioAnalyzer` fuer beats/energy nutzen und SpectralAnalyzer chunk-weise aufrufen oder `analyze(audio_path, duration=cap)` mit reduzierter Aufloesung.

### L-AUDIO-2 [HIGH] — Doppelter Audio-Load (Disk + Resample) pro Analyse
**File:Line:** `audio_router.py:616, 643`.
**Problem:** `_run_audio_analysis` laedt `y, sr = librosa.load(audio_path, sr=22050)`, ruft danach `detector.detect_beats(audio_path, ...)`. `BeatDetector.detect_beats` ruft intern wieder `librosa.get_duration(path=audio_path)` (Zeile 220 in beat_detector.py) und im Fallback `librosa.load(audio_path, ...)` erneut.
**Evidence:** `audio_router.py:616` und `beat_detector.py:312, 318`. SpectralAnalyzer wurde explizit auf `analyze_from_array(y, sr)` umgestellt (Zeile 689 router), BeatDetector aber nicht.
**Impact:** 2× Disk-Read + 2× Resample fuer jede Analyse — auf 90min-Mix laeuft das ~10s zusaetzlich.
**Fix:** `BeatDetector.detect_beats_from_array(y, sr, ...)` Variante einfuehren oder bei Vorhandensein des bereits geladenen `y` an `_run_audio_analysis` durchreichen.

### L-AUDIO-3 [LOW] — BPM-Berechnung in `_run_audio_analysis` dupliziert `BeatDetector.get_bpm`
**File:Line:** `audio_router.py:658-661`, `beat_detector.py:293-302`.
**Problem:** Inline-Median ueber `np.diff(arr)` ist exakt identisch zur `BeatDetector.get_bpm()`-Methode, die nicht genutzt wird.
**Impact:** Drift-Risiko wenn die Methode optimiert wird (z.B. trimmed mean).
**Fix:** `bpm = detector.get_bpm(arr.tolist()) or 0.0`.

### L-AUDIO-4 [HIGH] — SpectralAnalyzer-Output partiell verworfen
**File:Line:** `audio_router.py:690-696`, `spectral_analyzer.py:92-101, 155-163`.
**Problem:** `analyze_from_array()` liefert `band_means`, `band_variances`, `events` (Drop/Buildup/Breakdown). Im Router-Mapping werden nur `times`, `band_energies` (als `bands`), `centroids` uebernommen. `band_means`/`band_variances`/`events` werden nicht persistiert. `anchor_features.py:76-77` ruft `SpectralAnalyzer().analyze(path)` direkt nochmal (re-load + re-STFT) statt cached spectral_data.
**Evidence:** Schema `SpectralData` (audio_schemas.py:120-126) hat ebenfalls nur `bands`/`centroids`/`frequency_ranges` — kein Slot fuer events/means/variances.
**Impact:** (a) Drops/Buildups/Breakdowns aus SpectralAnalyzer._detect_events werden detected und sofort weggeworfen — Pacing/Brain bekommen sie nie. (b) anchor_features muss STFT komplett neu rechnen statt cached data zu lesen.
**Fix:** Schema `SpectralData` um `band_means: dict[str, float]`, `band_variances: dict[str, float]`, `events: list[dict]` erweitern; im Router uebernehmen; in `audio_router.py:686-696` `spec_result["events"]` mit-persistieren.

### L-AUDIO-5 [HIGH] — `subtrack_segments`/`tempo_curve` nicht in `AudioAnalysisResult` befuellt
**File:Line:** `audio_schemas.py:70-71`, `audio_router.py:712-722`.
**Problem:** Schema deklariert `subtrack_segments: list[SubtrackSegment]` und `tempo_curve: list[float]` als Felder von `AudioAnalysisResult`. `_run_audio_analysis` schreibt sie nicht. POST /audio/analyze liefert sie als `[]`. Sub-Tracks werden NUR beim Import in den Cache geschrieben (audio_router.py:137-161).
**Evidence:** `_run_audio_analysis` Rueckgabe-Dict (Zeile 712-722) enthaelt diese Keys nicht. `AudioAnalysisResult(**result)` (Zeile 347) propagiert daher Default-Listen.
**Impact:** UI/Konsumenten von POST /audio/analyze sehen nie sub-tracks, obwohl sie im Cache stehen. Wer nicht Import-flow laeuft (z.B. Re-Analyse), verliert Sub-Tracks komplett.
**Fix:** In `_run_audio_analysis` SubtrackDetector ebenfalls aufrufen (oder cached Werte vom Import durchreichen) und `result["subtrack_segments"]/["tempo_curve"]` setzen.

### L-AUDIO-6 [CRITICAL] — Subtrack-Cache geht beim Reload verloren
**File:Line:** `app_state.py:823-862` (load_from_db Audio-Block), `audio_router.py:157-161` (Import schreibt subtracks).
**Problem:** Beim Import wird `state.update_audio_analysis(subtrack_segments=..., tempo_curve=...)` aufgerufen ohne `is_analyzed=True`. `ai_data["is_analyzed"]` bleibt False. Beim Restart laedt `load_from_db` AudioAnalysis-Cache nur wenn `is_analyzed` True ist (Zeile 846 `if is_analyzed and ai_data:`). Selbst wenn man dorthin kommt, der Restore-Code in Zeile 852-861 mapped nur `bpm/key/beat_count/beats/energy_curve/structure_segments/spectral_data` — `subtrack_segments` und `tempo_curve` sind **nicht in der Map**.
**Evidence:** `app_state.py:852-862` Cache-Restore-Dict.
**Impact:** Jeder DJ-Mix verliert seine Sub-Tracks beim naechsten Backend-Start. Pacing-Service injiziert deshalb keine cached subtracks → Engine faellt auf Default zurueck. Reproduzierbar.
**Fix:** (a) Beim Import `is_analyzed=False` explizit zulassen aber Subtrack-Felder dennoch restoren. (b) `tmp_audio_analysis[clip_id]` um `"subtrack_segments": ai_data.get("subtrack_segments", [])` und `"tempo_curve": ai_data.get("tempo_curve", [])` ergaenzen — unabhaengig vom is_analyzed-Flag.

### L-AUDIO-7 [MEDIUM] — Cache-Inkonsistenz: `beats` vs `beats_json`
**File:Line:** `audio_router.py:308, 322-332`, `app_state.py:482-486, 514, 847-852`.
**Problem:** `set_audio_analysis(...result)` setzt Cache-Key `beats` als `list[dict]` (BeatData-aehnlich). `update_audio_analysis(beats_json=...)` parsed JSON und schreibt parallel `cache_update["beats_json"]=list`. Danach hat der Cache BEIDE Keys. `pacing_service.py:142` liest `cached_analysis.get("beats")`. `load_from_db:847-849` liest `ai_data.get("beats_json")` und schreibt das in Cache-Key `beats`. Race-/Drift-Risiko wenn `update_audio_analysis` ohne `beats_json` aufgerufen wird (Subtracks-only): `beats` bleibt unveraendert, `beats_json` fehlt.
**Impact:** Bei Subsequent-Update sieht Konsument inkonsistente Beats. Nicht direkt user-sichtbar, aber latente Drift.
**Fix:** Cache-Key vereinheitlichen — `update_audio_analysis` sollte `beats` (list[dict]) setzen, nicht `beats_json`. `load_from_db` sollte ebenso `beats` setzen (ist schon, Zeile 857). Den Parallel-Key `beats_json` im Cache komplett streichen (DB-Spaltenname ai_data_json["beats_json"] kann bleiben).

### L-AUDIO-8 [HIGH] — `stems_paths` nicht in DB persistiert
**File:Line:** `audio_router.py:499-506`, `app_state.py:687-715, 823-840`.
**Problem:** Nach POST /audio/stems/separate setzt der Router `clip["stems_paths"] = {...}` + `state.set_audio_clip(...)`. `set_audio_clip` schreibt nur in-memory. `persist_audio_clip` (Zeile 687-715) bildet `meta` Dict OHNE `stems_paths`. `load_from_db` (Zeile 825-840) baut Audio-Clip-Dict OHNE `stems_paths`.
**Evidence:** Grep `stems_paths` zeigt nur `audio_router.py`, `pacing_router.py`, Schema, AudioLibraryViewModel — kein Treffer in `app_state.persist_audio_clip` / `load_from_db`.
**Impact:** Stem-Pacing-Branch (`use_stem_pacing=True`) funktioniert nach Backend-Restart nicht, obwohl die Stem-Dateien physisch noch auf Disk liegen. User muss Demucs nochmal laufen lassen (3-10min GPU).
**Fix:** In `meta`-Dict beim `persist_audio_clip` `stems_paths` mit-aufnehmen. In `load_from_db` Audio-Clip-Dict (Zeile 825-840) `"stems_paths": meta.get("stems_paths")` aus meta lesen.

### L-AUDIO-9 [MEDIUM] — `SubtrackBoundary.components` (S1..S4-Scores) wird discarded
**File:Line:** `subtrack_detector.py:108-122`, `audio_router.py:137-143`.
**Problem:** `SubtrackDetector` produziert pro Boundary `components={"foote","stem","tempo","spectral"}` mit normalisierten Beitraegen je Signalpfad. Diese ermoeglichen Explainability ("Warum wurde hier ein Track-Wechsel detected?"). Der Router liest aber nur `result.segments` (tuples (s, e, c)) und ignoriert `result.boundaries` komplett.
**Impact:** Brain-Modul / UI bekommt nie die Component-Scores. Debugging und confidence-aware Pacing nicht moeglich.
**Fix:** Boundaries als Teil von `subtrack_segments`-Dicts mit-uebergeben oder als separate Liste `subtrack_boundaries`.

### L-AUDIO-10 [MEDIUM] — `has_audio_embedding` hardcoded auf False
**File:Line:** `audio_router.py:127`.
**Problem:** Beim Import-Default `"has_audio_embedding": False`. Wird nirgendwo upgedatet — Brain-Modul / EmbeddingCache schreibt nie zurueck. `app_state.load_from_db` rekonstruiert das Feld nicht (es steht nicht in `meta`).
**Evidence:** `grep -r has_audio_embedding`: nur Schema + Hardcode + Audit-Markdown.
**Impact:** Schema-Feld signalisiert User-relevante Info ("Embedding ready"), liegt aber permanent auf False.
**Fix:** Entweder in `brain_service` setzen wenn CLAP-Embedding berechnet wurde, oder Feld aus Schema entfernen.

### L-AUDIO-11 [MEDIUM] — `get_downbeats`/`scan` von BeatDetector ungenutzt
**File:Line:** `beat_detector.py:255-285`, `audio_router.py`.
**Problem:** BeatDetector hat `get_downbeats()` und `scan()` Methoden, die Downbeats aus BeatNet extrahieren. Schema `BeatData.beat_type` unterstuetzt "downbeat"/"bar". Im Router-Code wird ausschliesslich `detect_beats()` aufgerufen — `beat_type` ist immer "beat".
**Impact:** Downbeat-aware Pacing nicht moeglich. Schema-Slot ungenutzt. Pacing-Engine kann keine 4-Takt-Phrasen erkennen.
**Fix:** In `_run_audio_analysis` `detector.scan(audio_path)` statt `detect_beats(...)` aufrufen und `beats`-Liste mit `beat_type="downbeat"` fuer Downbeat-Times anreichern.

### L-AUDIO-12 [LOW] — `WaveformAnalyzer.get_time_axis` nutzt hardcoded `self.sr`
**File:Line:** `waveform_analyzer.py:249-253`.
**Problem:** `frames_to_time(np.arange(num_frames), sr=self.sr, hop_length=hop_length)` — aber wenn `target_sr`-override in `extract_3band_waveform` (Zeile 73) genutzt wurde, ist `self.sr` falsch.
**Impact:** Latenter Bug bei zukuenftigen target_sr-Aufrufen. Aktuell nicht aktiv (Router nutzt Default 44100).
**Fix:** SR als Methodenparameter durchreichen oder analyze_with_sr Pattern.

### L-AUDIO-13 [LOW] — `analyze_frequency_content` nie aufgerufen
**File:Line:** `waveform_analyzer.py:263-292`.
**Problem:** Nur in einer Docstring referenziert, kein Router/Service-Caller.
**Impact:** Dead Code.
**Fix:** Entfernen oder als Route exposen.

### L-AUDIO-14 [LOW] — BeatNet-NumPy-Patches sind global side-effect
**File:Line:** `beat_detector.py:46-51`.
**Problem:** `np.float = float` etc. patch global das numpy-Modul (nicht lokal). Andere Module die `np.float` deprecation-aware sind, sehen jetzt einen Truthy-Wert statt AttributeError.
**Impact:** Maskierung von numpy 2.0 Inkompatibilitaeten in anderen Modulen.
**Fix:** Auf Try/Except scope-lokal eingrenzen oder NumPy auf 1.26.4 locken (ist es bereits) und Patches in `if NP_MAJOR < 2:` clausel.

### L-AUDIO-15 [LOW] — `set_audio_analysis` reinjiziert nicht in DB
**File:Line:** `app_state.py:200-203`, `audio_router.py:308-332`.
**Problem:** `analyze_audio` ruft beide hintereinander auf: `set_audio_analysis(clip_id, result)` (only-cache) UND `update_audio_analysis(...)` (DB + cache). Wenn nur eine API-Variante aufgerufen wird (z.B. extension-code), DB bleibt unsynchronisiert.
**Impact:** Latentes Drift-Risiko zwischen Cache und DB.
**Fix:** `set_audio_analysis` so umschreiben dass DB-Persistenz automatisch via `update_audio_analysis` erfolgt (oder umgekehrt — `update_audio_analysis` ist bereits dual).

### L-AUDIO-16 [LOW] — `audio_hash` Doppel-Schreibweg (file_hash vs meta.audio_hash)
**File:Line:** `app_state.py:706-712`.
**Problem:** `persist_audio_clip` schreibt `file_hash=clip.get("audio_hash") or ""` (DB-Spalte) UND `meta["audio_hash"]` (JSON). Beim Reload (Zeile 839) wird wieder beide gelesen `meta.get("audio_hash") or row.get("file_hash") or None`. Redundant — bei spaeterem Hash-Update kann Drift entstehen.
**Impact:** Minor: doppelte Wahrheitsquelle. Wenn jemand nur eine aktualisiert: Inkonsistenz.
**Fix:** Eine der beiden Quellen als Single-Source deklarieren (vermutlich `file_hash` Spalte da indexiert, `idx_media_hash`).

---

## 3. Daten-Pipeline-Matrix

| Feld | Schreiber | Konsument | Persistiert? | Load? | Status |
|---|---|---|---|---|---|
| beats | `audio_router._run_audio_analysis` → `set_audio_analysis` | `pacing_service._inject_cached_into_engine` (`cached_analysis["beats"]`) | DB ai_data_json.beats_json | ✅ (load_from_db parses beats_json → cache["beats"]) | OK (aber siehe L-AUDIO-7) |
| bpm | `_run_audio_analysis` (local np.median) | clip + cache + pacing | DB ai_data_json.bpm | ✅ | OK (L-AUDIO-3 dup compute) |
| key | `KeyDetector.detect_key(y,sr)` | clip + cache + pacing key_matching | DB ai_data_json.key | ✅ | OK |
| energy_curve | `_run_audio_analysis` (librosa.rms) | `AdvancedPacingEngine._pre_cached_energy` | DB ai_data_json.energy_curve | ✅ | OK |
| structure_segments | `StructureAnalyzer.analyze_song_structure` | `_inject_cached_into_engine → song_structure` | DB ai_data_json.structure_segments | ✅ | OK |
| spectral_data.band_energies | `SpectralAnalyzer.analyze_from_array → bands` | `_pre_cached_spectral_bass/mid/high` (via `bands["low/mid/high"]`) | DB ai_data_json.spectral_data | ✅ | OK |
| spectral_data.centroids | SpectralAnalyzer | `brain.post_processor` | DB | ✅ | OK |
| spectral_data.band_means | SpectralAnalyzer (computed) | (nur `anchor_features` der direkt SpectralAnalyzer ruft) | ❌ (audio_router strippt) | ❌ | 🔴 L-AUDIO-4 |
| spectral_data.band_variances | SpectralAnalyzer (computed) | `anchor_features` (direkter Call) | ❌ | ❌ | 🔴 L-AUDIO-4 |
| spectral_data.events (drop/buildup/breakdown) | SpectralAnalyzer._detect_events | KEINER | ❌ | ❌ | 🔴 L-AUDIO-4 |
| subtrack_segments | `audio_router.import_audio` (Import-only!) → update_audio_analysis | `pacing_service` _pre_cached_subtracks | DB ai_data_json.subtrack_segments | ❌ (load_from_db skipped & not in cache-restore map) | 🔴 L-AUDIO-6 |
| tempo_curve | `audio_router.import_audio` (Import-only) | `_pre_cached_tempo_curve` (engine `get_local_bpm`) | DB ai_data_json.tempo_curve | ❌ | 🔴 L-AUDIO-6 |
| stems_paths | `audio_router.separate_stems` (in-memory only) | `pacing_router` use_stem_pacing branch | ❌ NICHT in persist_audio_clip meta | ❌ | 🔴 L-AUDIO-8 |
| audio_hash | `audio_router.import_audio` (media_hash) | brain.post_processor (CLAP-cache lookup) | DB media.file_hash + meta.audio_hash | ✅ | OK (L-AUDIO-16 double) |
| has_audio_embedding | Hardcoded False at import | (Schema only) | ❌ (nur via has_embedding video?) | ❌ | 🟡 L-AUDIO-10 |
| beat strengths | `BeatDetector.compute_beat_strengths` (real onset_strength) | `BeatData.strength` field → pacing trigger-weight | DB ai_data_json.beats_json[i].strength | ✅ | OK |
| downbeats | `BeatDetector.get_downbeats / scan` (existiert) | KEINER | ❌ | ❌ | 🟡 L-AUDIO-11 |
| onsets | `audio_router._calculate_onsets_sync` (derived from energy_curve on-demand) | GET /audio/onsets | ❌ (recomputed each call) | n/a | OK (minor: kein cache) |
| waveform bands (3-band RMS) | `WaveformAnalyzer.extract_3band_waveform` (on-demand) | GET /audio/waveform | ❌ (recomputed each call) | n/a | OK (minor: kein cache) |
| subtrack boundaries.components | `SubtrackDetector.detect → boundaries[i].components` | KEINER | ❌ (Router liest nur segments) | ❌ | 🟡 L-AUDIO-9 |
| StreamingAudioAnalyzer output | (Modul exportiert, getestet) | KEINER (nicht aufgerufen) | n/a | n/a | 🔴 L-AUDIO-1 |

Legende: ✅ in Ordnung · 🟡 dead-write oder Minor · 🔴 broken/critical

---

## 4. Top 5 Critical Bugs

1. **L-AUDIO-1 [CRITICAL] — StreamingAudioAnalyzer wird nie aufgerufen.** Komplettes Modul gebaut+getestet, aber `_run_audio_analysis` laedt jedes Audio (auch 90min-DJ-Mix) komplett in RAM (`librosa.load(sr=22050, mono=True)` ohne Duration-Limit). Hauptzielgruppe (lange Mixe) OOM-anfaellig.
2. **L-AUDIO-6 [CRITICAL] — Subtrack-Cache nach Reload weg.** Import schreibt subtrack_segments/tempo_curve nur mit `is_analyzed=False`. `load_from_db` springt `is_analyzed=False`-Eintraege uebersprungen und mapped diese beiden Keys ohnehin nicht. Sub-Tracks gehen bei jedem Backend-Restart verloren.
3. **L-AUDIO-8 [HIGH] — stems_paths nicht persistiert.** Demucs-Output (10min GPU-Zeit) wird in-memory gehalten, nicht in DB-Meta geschrieben, nicht in `load_from_db` restored. Nach Restart erscheint `use_stem_pacing` als kaputt obwohl Dateien physisch da sind.
4. **L-AUDIO-4 [HIGH] — SpectralAnalyzer.events verworfen.** Drops/Buildups/Breakdowns werden detected (`_detect_events`) und Pacing/Brain nie zugaenglich gemacht. Schema `SpectralData` hat den Slot nicht; audio_router strippt das Feld.
5. **L-AUDIO-5 [HIGH] — POST /audio/analyze liefert subtrack/tempo_curve immer leer.** `AudioAnalysisResult` deklariert diese Felder, `_run_audio_analysis` schreibt sie nicht. UI/extern-Caller sehen leere Listen.

---

## 5. Empfehlungs-Pfad

**Phase 1 (Persistenz-Fixes, geringes Risiko, hoher Impact):**
1. L-AUDIO-8: `persist_audio_clip` + `load_from_db` um `stems_paths` ergaenzen.
2. L-AUDIO-6: `load_from_db` Audio-Block: subtrack/tempo unabhaengig von `is_analyzed` restoren, Cache-Map ergaenzen.

**Phase 2 (Data-Loss-Fixes, mittleres Risiko):**
3. L-AUDIO-4: Schema `SpectralData` um `events`/`band_means`/`band_variances` ergaenzen, audio_router mit-persistieren.
4. L-AUDIO-5: `_run_audio_analysis` ruft `SubtrackDetector` (bei >=60s) und befuellt `result["subtrack_segments"]/["tempo_curve"]`.

**Phase 3 (Performance/RAM, hohes Risiko aber notwendig fuer DJ-Mixe):**
5. L-AUDIO-1: `_run_audio_analysis` Branch `duration > 600s → StreamingAudioAnalyzer + chunked SpectralAnalyzer`. SubtrackDetector aehnlich (oder schon OK bei aggregated chroma).
6. L-AUDIO-2: BeatDetector `detect_beats_from_array` einfuehren, doppel-load entfernen.

**Phase 4 (Cleanup, kein User-Impact):**
7. L-AUDIO-7: Cache-Key `beats_json` aus In-Memory-Cache streichen (nur DB).
8. L-AUDIO-3: Inline-BPM durch `detector.get_bpm()` ersetzen.
9. L-AUDIO-11: Downbeats via `detector.scan()` mit-uebernehmen.
10. L-AUDIO-9/L-AUDIO-10/L-AUDIO-13/L-AUDIO-14: Component-Scores propagieren, has_audio_embedding entweder befuellen oder entfernen, dead code raus, NumPy-Patches scope-lokal.
