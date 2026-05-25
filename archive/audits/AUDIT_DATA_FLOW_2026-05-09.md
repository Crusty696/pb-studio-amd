# Audit: Audio/Video-Analyse → Pacing Data-Flow

**Datum:** 2026-05-09
**Auftrag:** Nur prüfen + dokumentieren, KEIN Fix.
**Trigger:** User-Symptom "BPM musste ich von Hand anpassen, wurde nicht von Analyse übernommen".

---

## Kurz-Verdict

**4 von 8 Audio-Analyse-Outputs werden NICHT korrekt an Pacing weitergegeben.**
**3 von 5 Video-Analyse-Outputs werden NICHT korrekt weitergegeben.**

Root-Cause des User-Symptoms (BPM hand-adjust):
`DirectorViewModel.OnSelectedAudioClipChanged` setzt NICHT `ExpectedBpm = value.Bpm`. UI-`ExpectedBpm` bleibt auf default 120. Backend `expected_bpm=120` überschreibt den gecachten `pre_cached_bpm` aus Audio-Analyse.

---

## Audio-Analyse → Pacing — Detail-Matrix

| Audio-Output | Backend persist | Backend liest in pacing | Frontend nutzt | Status |
|---|:-:|:-:|:-:|---|
| **bpm** | ✅ `audio_analysis_cache` + SQLite `ai_data_json` | ⚠️ `pacing_service.py:210` liest aber nur als FALLBACK wenn `expected_bpm=None`; UI sendet IMMER `ExpectedBpm` (default 120) → cached BPM wird IGNORIERT | ❌ `OnSelectedAudioClipChanged` setzt NICHT `ExpectedBpm = value.Bpm` (DirectorViewModel.cs:195-196) | **🔴 BROKEN — BPM-Workflow unterbrochen** |
| **key** (Tonart) | ✅ `audio_analysis_cache.key` + SQLite | ❌ Kein `key`-Feld in `advanced_pacing_engine`, kein in `pacing_service`, kein in `PacingConfigSchema` | ❌ Nur Anzeige in AudioLibraryView Metric-Card | **🔴 NICHT VERWENDET** für Pacing trotz Persistenz |
| **beat_count** | ✅ | ❌ Reine Statistik | ❌ Nur Anzeige | **🟡 INFO-only** |
| **beats** (Liste mit time/strength) | ✅ `beats_json` in SQLite | ✅ `pacing_service.py:202-209` liest, injected via `pacing_engine._pre_cached_beats` | n/a | **🟢 OK** |
| **energy_curve** | ✅ persistiert in `ai_data_json` | ❌ `cached_analysis.get("energy_curve")` NIRGENDS gelesen in pacing_service. Engine berechnet RMS NEU aus `librosa.feature.rms()` | ❌ Nicht UI-relevant | **🔴 PERSISTIERT ABER REDUNDANT-NEUBERECHNET** |
| **structure_segments** | ✅ | ⚠️ NUR wenn `use_structure_awareness=True` → Engine ruft `analyze_song_structure(audio_path)` NEU auf statt cached zu nutzen → **2× librosa-Load** | n/a | **🔴 REDUNDANTE NEU-ANALYSE statt cached** |
| **spectral_data** | ✅ | ❌ Nirgends gelesen | ❌ Nur Anzeige in TimelineView | **🔴 NICHT VERWENDET** |
| **subtrack_segments** + **tempo_curve** | ✅ | ❌ Nirgends im Pacing-Path | ❌ | **🔴 NICHT VERWENDET** in Pacing |

---

## Video-Analyse → Pacing — Detail-Matrix

| Video-Output | Backend persist | An Pacing weitergegeben | Status |
|---|:-:|:-:|---|
| **scene_count** | ✅ | ✅ via `clip_data["scene_changes"] = va.get("scenes", [])` (pacing_router.py:340) | **🟢 OK** |
| **avg_motion** | ✅ | ✅ `clip_data["motion_score"] = va.get("avg_motion", 0.0)` + `clip_data["avg_motion"]` | **🟢 OK** |
| **motion.peak_frames** | ✅ | ✅ `clip_data["peak_frames"] = motion.get("peak_frames", [])` | **🟢 OK** |
| **motion.motion_curve** | ✅ | ❌ Nirgends gelesen in pacing_router clip_data | **🔴 PERSISTIERT ABER NICHT genutzt** |
| **dominant_colors** | ✅ | ❌ Nicht in clip_data weitergegeben | **🔴 NICHT VERWENDET** |
| **tags** (Moondream) | ✅ | ❌ Nicht in clip_data | **🔴 NICHT VERWENDET** |
| **has_embedding** + FAISS-Embedding | ✅ FAISS Vector-Store | ⚠️ Nur via SmartDirector → SemanticMatcher wenn `use_semantic_matching=True` | **🟡 BEDINGT** |

---

## ROOT CAUSE des User-Symptoms

`PBStudio.UI/ViewModels/DirectorViewModel.cs:195-196`:
```csharp
partial void OnSelectedAudioClipChanged(AudioClipModel? value)
    => GenerateCutListCommand.NotifyCanExecuteChanged();
```

**Was fehlt:** Kein `if (value != null) ExpectedBpm = value.Bpm;`. Wenn User Audio-Clip wählt, bleibt `ExpectedBpm` auf default 120 hängen. User muss BPM-Spinner manuell eintippen.

**Sekundär — Backend bevorzugt UI-Wert über Cached:**
`pacing_service.py:988-1002`:
```python
if expected_bpm is None:
    elif hasattr(self, "_pre_cached_bpm") and self._pre_cached_bpm:
        bpm = float(self._pre_cached_bpm)
else:
    bpm = expected_bpm  # UI-Wert wins
```

UI sendet `ExpectedBpm=120` immer (nie None), also `bpm = 120` ungeachtet pre_cached.

---

## Persistenz-Lücken

Audio-Analyse-Daten die in SQLite landen aber NIE wieder gelesen werden:
- `key` (komplett dead-end nach Anzeige)
- `energy_curve` (Pacing rechnet neu)
- `structure_segments` (Pacing analysiert neu wenn use_structure_awareness)
- `spectral_data` (kein Konsument außer TimelineView Anzeige)
- `subtrack_segments` + `tempo_curve` (kein Konsument)

→ **5 Felder werden persistiert ohne Konsumenten** = wasted compute + storage.

---

## Empfehlungen (NICHT angewendet — Audit-only per User-Anweisung)

1. **DirectorViewModel.OnSelectedAudioClipChanged**: bei `value != null` setzen `ExpectedBpm = value.Bpm` (UI sync zu Selected-Clip-BPM)
2. **DirectorView**: BPM-Spinner mit Read-Only-Checkbox "Analyse nutzen" → wenn Auto, bleibt synchron mit SelectedClip.Bpm
3. **PacingService**: `cached_analysis["energy_curve"]` lesen + an Engine injizieren statt RMS-Neuberechnung
4. **PacingService**: `cached_analysis["structure_segments"]` lesen + injizieren statt `analyze_song_structure(audio_path)` redundante Re-Analyse
5. **Video-Pacing**: `motion_curve`, `dominant_colors`, `tags` in `clip_data` durchreichen + Engine-Konsumenten ergänzen
6. **Audio-Key in Pacing**: optional Key-aware Cut-Auswahl wenn Key-Compatibility gewünscht (Mood-Matching erweitert)

---

## Sourcen

- `PBStudio.UI/ViewModels/DirectorViewModel.cs:195-196` (OnSelectedAudioClipChanged)
- `PBStudio.UI/ViewModels/DirectorViewModel.cs:228-251` (PacingConfig-Aufbau)
- `backend/routers/pacing_router.py:71` (`cached_analysis = state.get_audio_analysis(...)`)
- `backend/routers/pacing_router.py:301-372` (`_run_pacing_generation` → clip_data Mapping)
- `src/pb_studio/services/pacing_service.py:200-235` (pre_cached_beats + bpm injection)
- `src/pb_studio/services/pacing_service.py:988-1002` (BPM-Vorrang-Logik)
- `backend/routers/audio_router.py analyze_audio` (Persistenz aller Fields)
- `backend/schemas/pacing_schemas.py` (PacingConfigSchema — kein key, kein energy_curve, kein structure_segments)
