# AUDIT Timeline-Integrität — 2026-05-11

User-Direktive: "Die Timeline muss richtig zusammengestellt werden, nicht
chaotisch/ungenau — egal ob Auto- oder manueller Generation-Modus."

Scope: Stage-by-Stage Audit der Cut-Generation-Pfade (auto + manuell)
auf Korrektheit, Konsistenz, Sicherheits-Mechanismen und Validation.

---

## 1. Auto-Generation Pfad

End-to-End Flow vom REST-Endpoint bis zur persistierten Timeline:

| # | Stage | File:Line | Was passiert |
|---|-------|-----------|--------------|
| 1 | HTTP-Entry | `backend\routers\pacing_router.py:40` | `POST /pacing/generate` empfängt `PacingConfigSchema` |
| 2 | Snapshot+Validate | `pacing_router.py:58-68` | thread-safe Snapshots aus AppState, 404 wenn audio_clip_id/video_clip_ids fehlen |
| 3 | Cache lookup | `pacing_router.py:71-74` | `state.get_audio_analysis(...)` liefert beats/bpm/energy/spectral/subtracks/key |
| 4 | Worker-Thread | `pacing_router.py:81-84` | `asyncio.to_thread(_run_pacing_generation,…)` — blockierende Engine läuft offload |
| 5 | Clip-Dict bau | `pacing_router.py:354-377` | Forwarded motion_score, motion_curve, scene_changes, dominant_colors, tags, audio_key |
| 6 | Routing | `pacing_router.py:412-438` | `use_stem_pacing+stems` → `generate_cut_list_with_stems`, sonst `generate_cut_list` |
| 7 | Service wrapper | `services\pacing_service.py:375-752` | `PacingService.generate_cut_list` injiziert pre-cached: beats, bpm, duration, energy, bass/mid/high, subtracks, tempo, key_match |
| 8 | Engine routing | `pacing_service.py:654-740` | `use_motion_matching OR use_semantic OR use_structure` → `generate_cut_list_with_structure` ODER `generate_cut_list_raw` (NV-API), sonst `_generate_simple_round_robin` |
| 9 | Engine work | `advanced_pacing_engine.py:868-1184` | (a) Beats laden, (b) Trigger sammeln (`_extract_other_triggers`, `_build_triggers_from_cache`, stem-trigger), (c) `_apply_structure_weights` skaliert Strength, (d) sort, (e) `_enforce_minimum_interval`, (f) end-of-song trigger anfügen, (g) `_enforce_clip_lengths` (auto-split lange Lücken) |
| 10 | Clip-Zuweisung | `pacing_service.py:712-733` (advanced) / `:754-808` (round-robin) | für jeden Cut `clip_selector.select_clip(...)` (motion/semantic/round-robin Strategie) |
| 11 | Cut-Materialisierung | `pacing_service.py:71-116` `_process_pacing_cuts_to_cutlist` | `CutListEntry` mit `start_time/end_time/clip_id/metadata` |
| 12 | Clip-Start sampling | `pacing_service.py:63-69` | `_get_random_clip_start` zieht zufälligen In-Point innerhalb `[0..clip_dur-required_duration]` |
| 13 | Out-of-bounds Cap | `pacing_service.py:93-97` | wenn `clip_start+duration > actual_clip_dur` → start=0, duration=`min(req_dur, actual_clip_dur)` |
| 14 | Brain post-proc | `pacing_router.py:89-137` | annotiert `brain_final_score`/`cut_id` falls `use_brain=true` (idempotent, schluckt Fehler) |
| 15 | Final Validation | `pacing_router.py:140-145` → `schemas\common.py:78-126` | `validate_timeline(cuts, audio_duration)` — errors blocken (HTTP 400), warnings nur Log |
| 16 | Persist | `pacing_router.py:148-153` | `state.set_timeline(cuts)` thread-safe |

Verbose Log-Evidenz (`logs\backend.log:630-4105`): 4 echte Runs auf
3745s-DJ-Set (Crusty_Progressive Psy Set2.mp3), BPM 142/143.6, 8696
Beats cached. Engine produziert 2184 Schnitte vor Clip-Zuweisung —
aber Service-Wrapper erzeugt am Ende nur **14** Cuts wegen
Fallback-Pfad (siehe L-TI-1 in Sektion 4).

---

## 2. Manuelle Edits Pfad

UI-Pfad für manuell editierte Cuts:

| # | Stage | File:Line | Was passiert |
|---|-------|-----------|--------------|
| 1 | Mouse-Down | `Views\TimelineView.xaml.cs:261-277` | Hit-Test innerhalb Clip-Border: x<10 → trim-left, x>w-10 → trim-right, sonst drag |
| 2 | Mouse-Move | `TimelineView.xaml.cs:279-344` | `_draggedEntry.StartTime += deltaTime`, `EndTime = newStart + duration`; Snap-Engine (Tolerance 8 px) snapt an beats/onsets/playhead/clip-edges falls Shift nicht gedrückt |
| 3 | UI-Update | `TimelineView.xaml.cs:338-341` | `NotifyPositionChanged()` → WPF refresht Canvas-Position; `_syncTimer.Start()` schedult 1s-Debounce |
| 4 | Auto-Sync | `TimelineView.xaml.cs:104-108` → `TimelineViewModel.cs:406-427` | Nach 1s Idle: `SyncTimelineCommand` ⇒ `_api.UpdateTimelineAsync(entries)` |
| 5 | API Call | `Services\ApiClient.cs:203-220` | POST `/pacing/timeline` mit allen Entries (keine Diff, voller Replace) |
| 6 | Backend Receive | `pacing_router.py:230-266` | `update_timeline` Endpoint reconvertiert Entries zu internem dict-Format |
| 7 | Validate | `pacing_router.py:256-258` → `schemas\common.py:78-126` | Gleicher `validate_timeline` wie Auto-Pfad — Errors → HTTP 400 |
| 8 | Persist | `pacing_router.py:260` | `state.set_timeline(internal_cuts)` |

**Asymmetrie zu Auto-Pfad:**
- Trimming-Logik (left/right resize) ist im Code-Behind nur als `_isTrimmingLeft / _isTrimmingRight` Flags angelegt — die eigentliche Verschiebung der StartTime/EndTime bei Trim ist **nicht implementiert** (Kommentar: "Trimming left/right omitted for brevity in this replace call", `TimelineView.xaml.cs:314-315`).
- Manuelle Edits speichern **keine** `cut_start`-Anpassung — wenn der User einen Cut verlängert, bleibt die In-Point/`clip_start` gleich, d.h. Renderer kann übers verfügbare Video hinaus lesen (siehe L-TI-5).

---

## 3. Korrektheits-Garantien

| Stage | Garantie | Implementiert? | File:Line |
|---|---|---|---|
| Engine: Cuts an Beat-Positionen | Cut.time = Beat-Time wenn `beat_weight>0` | Ja | `advanced_pacing_engine.py:1129-1137` |
| Engine: Start-Trigger bei 0.0 | wenn erster Trigger > 0.5s → insert PacingCut(time=0.0) | Ja (S03/GUARD) | `advanced_pacing_engine.py:1139-1141` |
| Engine: End-Trigger bei duration | wenn letzter < duration → append PacingCut(time=duration) | Ja | `advanced_pacing_engine.py:1166-1167` |
| Engine: min-interval Filter | distanz < min_cut_interval → schwächeren Trigger droppen | Ja | `advanced_pacing_engine.py:1884-1904` |
| Engine: Cuts ≥ min_clip_length | `_enforce_clip_lengths` ruft erneut `_enforce_minimum_interval(min_length)` | Ja | `:1931` |
| Engine: Cuts ≤ max_clip_length | Auto-Split bei `clip_duration > current_max` | Ja, aber Bug L-TI-2 | `:1946-1961` |
| Engine: Vorwärts-Fortschritt | `proposed_end <= current_time + 0.1 → +min_clip_length` | Ja (S02b) | `:397-399` (hybrid_sync) |
| Service: duration ≥ 0.5 | continue wenn duration < 0.5s | Ja | `pacing_service.py:84-85, 776` |
| Service: Clip-Bounds-Cap | wenn `clip_start+duration > actual` → cap | Ja, aber nur Auto-Pfad | `pacing_service.py:92-97, 422-432, 786-791` |
| Service: file_path required | continue wenn leer | Ja | `pacing_service.py:86-87` |
| Service: Random clip_start | `random.uniform(0, max_start)` mit `max_start=max(0, dur-req)` | Ja | `pacing_service.py:63-69` |
| Service: Cached Audio-Dauer | Ad-hoc Probe wenn `total_duration <= 0` | Ja (S01/CRITICAL) | `pacing_service.py:449-455, 271-276` |
| Service: leere Clips → leere Liste | `if not clips: return []` (warn) | Ja | `pacing_service.py:253-254, 396-398` |
| Router: 404 wenn audio_clip fehlt | HTTPException(404) | Ja (BUG-027) | `pacing_router.py:62-63` |
| Router: 400 wenn 0 video_clips | HTTPException(400) | Ja | `pacing_router.py:64-65` |
| Router: 404 wenn unbekannte vid_id | HTTPException(404) mit Liste | Ja | `pacing_router.py:66-68` |
| Router: validate_timeline | end > start, ≥ 0.1s warn, file_path warn, Überlapp 1ms-Toleranz, audio_overflow 0.5s | Ja | `schemas\common.py:78-126` |
| Render: vor Render erneut validate | `validate_timeline(timeline)` raise wenn errors | Ja | `render_router.py:534-538` |
| Render: cap end_time aus metadata | `out_point = clip_start + (end_time-start_time)` | Ja (R12b/SEV-004) | `pacing_service.py:421-432` für Sequencer-Pfad |
| Manuell-Pfad: gleiche Validation | POST /pacing/timeline ruft `validate_timeline` | Ja | `pacing_router.py:256-258` |
| Manuell-Pfad: Snap-zu-Beats | SnapEngine 8px Tolerance | Ja | `TimelineView.xaml.cs:291-308` |
| Manuell-Pfad: Trim-Resize | Flags gesetzt, Logik fehlt | **NEIN** | `TimelineView.xaml.cs:269-272, 314-315` |
| Manuell-Pfad: clip_start update bei Resize | Auto-Anpassung an neue Duration | **NEIN** | n/a |
| Manuell-Pfad: Overlap-Prevention bei Drag | UI lässt überlappende Drags zu, Server-validate liefert nur Warning | Teilweise | `schemas\common.py:112-116` (nur warn) |
| Manuell-Pfad: Reorder (sortieren nach drag) | Nach Drag wird in TimelineEntries nicht resortiert | **NEIN** | `TimelineView.xaml.cs:311-313` |

---

## 4. Risiken / Lücken

### L-TI-1 [CRITICAL] `prompt=`-Kwarg-Fehler killt Semantic-/Brain-Pfad im Auto-Mode

**Symptom (aus `logs\backend.log:1327, 3556, 4047, 4079`):**
```
ERROR pb_studio.services.pacing_service: Cut-List-Generierung fehlgeschlagen:
ClipSelector.select_clip() got an unexpected keyword argument 'prompt'
```

**Root Cause:** `pacing_service.py:346-348` und `:719-721` rufen:
```python
sel = pacing_engine.clip_selector.select_clip(
    clips, cut.strength, cut.trigger_type, prompt=prompt
)
```
Aber die Signatur in `clip_selector.py:196-202` akzeptiert nur:
```python
def select_clip(self, available_clips, trigger_strength=0.5,
                trigger_type="beat", previous_clip_id=None) -> SelectedClip:
```
Es gibt **kein** `prompt`-Argument. `select_clip` raised `TypeError` → das landet im `except Exception as e:` von `generate_cut_list` (`pacing_service.py:741-752`) → Fallback `_generate_simple_round_robin`.

**Auswirkung (live verifiziert, log L4046 vs L4058):**
- Engine generiert 2184 saubere Beat-Cuts → Crash bei Clip-Zuweisung → Fallback erzeugt nur **14** Cuts.
- Verlust der Struktur-Awareness UND der semantischen Clip-Auswahl.
- Brain-Reranker im Pfad ohne Effekt, weil Fallback `_generate_simple_round_robin` keinen reranker nutzt.
- User sieht "weniger Cuts als erwartet" und ungenaue Clip-Auswahl ohne Hinweis, dass interner Pfad failt.

**Reproducierbar:** Tritt bei JEDEM `use_semantic_matching=True` OR `use_structure_awareness=True` auf.

**Fix:** entweder
- `clip_selector.select_clip(..., prompt: str|None = None)` als optionalen Parameter ergänzen und an `_select_semantic` durchreichen, oder
- in pacing_service.py die zwei `prompt=prompt` Aufrufe entfernen und stattdessen `clip_selector._select_semantic` direkt nutzen.

---

### L-TI-2 [HIGH] `_enforce_clip_lengths` Split-Logik kann Min-Length verletzen

`advanced_pacing_engine.py:1946-1961`:
```python
if clip_duration > current_max:
    num_splits = max(1, int(clip_duration / current_max))
    split_duration = clip_duration / (num_splits + 1)
    for j in range(num_splits):
        ...
        if (split_time > prev_time + min_length) and (split_time < audio_duration - 0.1):
            result.append(PacingCut(time=split_time, ...))
```

Probleme:
1. `split_duration = clip_duration / (num_splits+1)` kann **kleiner** als `min_length` werden — z.B. `clip_duration=10s`, `current_max=4s` → `num_splits=2`, `split_duration=10/3=3.33s` aber wenn `min_length=4` würde der Guard greifen — aber der Guard prüft nur das **letzte** insertete `prev_time`, nicht den **nächsten** echten Cut. Der letzte Split kann eine Lücke <`min_length` zum nächsten Original-Cut erzeugen.
2. `jitter * random.uniform(-variation*0.2, +variation*0.2)` mit `variation=...` (default 0?) kann split_time auf identische Position legen wie Vorgänger — wird nur per `prev_time+min_length`-Check gefiltert.

**Auswirkung:** Bei `min_length=2s`, `max_length=4s`, `variation>0` können in seltenen Fällen Cut-Paare mit `<2s` Distanz entstehen (gegen Spec).

---

### L-TI-3 [HIGH] Manueller Drag aktualisiert `clip_start` nicht — out-of-bounds Render

**Pfad:** `TimelineView.xaml.cs:294-313` (drag) ändert nur `StartTime/EndTime`. Wenn User einen Cut nach rechts zieht (delta_time > 0), Verschiebung ändert die Timeline-Position; aber wenn der User die **Dauer** ändert (durch Trim — wenn implementiert) ist `ClipStart` (= In-Point ins Quellvideo) **nicht** angepasst.

Konkret: Cut [Timeline 4-6s, ClipStart 30s, Video-Länge 40s] → User zieht End auf 10s → Renderer liest Video von 30s bis 36s (statt 34s) — kann **über** Video-Ende lesen wenn ClipStart+neue_Duration > Video-Länge.

Backend-Cap-Logik (`pacing_service.py:421-432` R12b/SEV-004) wird nur für **Sequencer**-Pfad ausgeführt, nicht für manuell editierte Cuts via `POST /pacing/timeline` (`pacing_router.py:236-260`). Manuelle Updates gehen ohne ffprobe-Cap durch.

**Auswirkung:** Schwarze Frames / FFmpeg-Errors beim Render nach manuellem Edit.

---

### L-TI-4 [HIGH] Trim-Logik ist Stub (left/right Resize tut nichts)

`TimelineView.xaml.cs:269-272`:
```cs
var hitPosition = e.GetPosition(element).X;
if (hitPosition < 10) _isTrimmingLeft = true;
else if (hitPosition > element.ActualWidth - 10) _isTrimmingRight = true;
else _isDragging = true;
```

Die Flags werden gesetzt — aber in `Clip_MouseMove:279-344` gibt es **nur** einen `if (_isDragging)` Branch. Comment:
```cs
// (Trimming left/right omitted for brevity in this replace call,
// but logic follows same SnapEngine pattern)
```

XAML zeigt die Drag-Handles (`Views\TimelineView.xaml:522-523`):
```xml
<Rectangle Width="4" HorizontalAlignment="Left"  Fill="..." Cursor="SizeWE" Opacity="0.5"/>
<Rectangle Width="4" HorizontalAlignment="Right" Fill="..." Cursor="SizeWE" Opacity="0.5"/>
```

**Auswirkung:** User sieht Resize-Cursor an Edges, klickt und zieht — **nichts passiert**. Trim ist UI-only "feature" ohne Funktion. Manueller Workflow zur Cut-Dauer-Anpassung fehlt.

---

### L-TI-5 [HIGH] Drag ändert nicht die TimelineEntries-Reihenfolge

`TimelineView.xaml.cs:294-313` updatet das gedraggte Entry direkt im Live-Position aber sortiert die `ObservableCollection<TimelineEntryModel>` nicht neu. Wenn User Cut #3 vor Cut #1 zieht, hat der Index nicht-monoton zu Zeit — und `NextCut`/`PreviousCut` (TimelineViewModel:263-283) navigiert nach Index, nicht nach Zeit.

Server-side `validate_timeline` sortiert beim Overlap-Check (`schemas\common.py:103`) — meldet aber nur Warnings, keine Errors. Render-Pipeline kann daher mit zeitlich verworrener Reihenfolge starten.

---

### L-TI-6 [MEDIUM] Strict-Limit fehlt für "Cuts > Audio-Dauer"

`validate_timeline` (`common.py:119-124`):
```python
if last_end > audio_duration + 0.5:
    warnings.append("Timeline überschreitet Audio-Dauer")
```
Nur **warning**, kein error. Render läuft mit über-Audio-Dauer Timeline → letzter Clip wird ohne Audio gerendert / FFmpeg-Concat behaviour undefined.

Engine-seitig endet die Generation bei `audio_duration` (`advanced_pacing_engine.py:1166-1167`), aber manuelle Edits können das beliebig überschreiten.

---

### L-TI-7 [MEDIUM] `_enforce_minimum_interval` ersetzt Trigger, behält aber `last_time` falsch

`advanced_pacing_engine.py:1896-1903`:
```python
for trigger in triggers[1:]:
    if trigger.time - last_time >= min_interval:
        filtered.append(trigger)
        last_time = trigger.time
    elif trigger.strength > filtered[-1].strength:
        filtered[-1] = trigger
        last_time = trigger.time   # CRITICAL FIX comment
```

Edge case: Wenn der ersetzte Trigger zeitlich **vor** dem vorletzten gespeicherten ist und der nächste eingehende Trigger zwischen den beiden liegt, kann `min_interval` verletzt werden weil `filtered[-2]` jetzt zu nah dran ist. Kein Bug bei sortierten Triggern — `triggers.sort(key=lambda x: x.time)` läuft vorher (`:1159`), aber der `_apply_structure_weights`-Pfad könnte (theoretisch) Triggers in falscher Reihenfolge erzeugen — wird heute durch Sort gefangen.

**Reduktion auf Beobachtung:** Aktuell durch Sort vor Filter abgesichert. Risiko nur wenn jemand die Sort-Linie entfernt.

---

### L-TI-8 [MEDIUM] `_get_random_clip_start` produziert Non-Determinismus

`pacing_service.py:63-69`:
```python
return random.uniform(0.0, max_start)
```
Gleicher Cut, gleiche Pacing-Config, zweimal aufgerufen → unterschiedlicher `clip_start` jedes Mal. Auch das `_enforce_clip_lengths`-Auto-Split (`:1951`) und `_plan_hybrid_sync` Chaos-Jitter (`:358-362`) nutzen `random.random()` ohne Seed.

**Wann gewollt:** Re-Generation soll Variation produzieren ("verschiedene Mixes").
**Wann Bug:** Tests vergleichen Output auf Determinismus → flaky. Reproducierbarkeit bei Bug-Reports schwierig. Kein Seed-Param in `pacing_config`.

---

### L-TI-9 [LOW] `validate_timeline` Overlap nur Warning, nicht Error

`schemas\common.py:112-116`:
```python
if curr_start < prev_end - 0.001:  # 1ms Toleranz
    warnings.append(f"Cut {i}: Überlappung...")
```

Render-Pipeline akzeptiert überlappende Cuts. FFmpeg-Concat erwartet aber non-overlapping segments — Behavior ist undefined (entweder visueller Sprung oder Frame-Crash).

---

### L-TI-10 [LOW] `validate_timeline` warnt nicht bei Gaps (= schwarze Frames)

`validate_timeline` prüft Überlapps, prüft aber **keine** Gaps zwischen Cuts. Wenn manueller Edit Cut [0-5s] und Cut [7-10s] erzeugt, ist die Lücke 5-7s nicht erkannt — Renderer rendert ggf. schwarz oder bricht ab.

---

### L-TI-11 [LOW] Trigger an exakter Beat-Position via `t in downbeats` (Float-Vergleich)

`advanced_pacing_engine.py:1131`:
```python
is_downbeat = t in downbeat_set
```
`downbeat_set = set(downbeats)` und `t` kommt aus `beats` — beides aus derselben Liste, also exakt gleicher Float-Wert. **Aber** bei Pre-cached Beats und separat geladenen Downbeats (verschiedene Quellen) könnten Float-Repräsentations-Drifts auftreten → kein Downbeat-Match.

Heute durch shared source (`audio_router` setzt beide gleichzeitig) abgesichert.

---

### L-TI-12 [LOW] Sequencer-Pfad mit `clip_start` außerhalb des Clips löst leise ValueError-Schlucker

`pacing_service.py:422-432`:
```python
try:
    actual_clip_dur = self._get_clip_duration(fp)
    ...
except ValueError:
    pass  # ffprobe failed — let render handle it
```
Wenn ffprobe ausfällt (z.B. fehlende Datei): Cap-Logik überspringt — Render wird mit potentiell ungültigen out-points starten und erst dort scheitern. Kein early warning.

---

## 5. Empfehlungen

**Priorität 1 — Sofort (User-Trust):**

1. **Fix L-TI-1:** `prompt`-Kwarg in `ClipSelector.select_clip` als optionalen Parameter ergänzen + an `_select_semantic` durchreichen.  Verifizieren: re-run mit `use_semantic_matching=True` und prüfen, dass Cut-Count ≈ Engine-Output (2184 statt 14).
2. **Fix L-TI-4 + L-TI-3 + L-TI-5:** Manuell-Edit-Pipeline vervollständigen:
   - Trim-Left/Right Logik implementieren (Delta auf `ClipStart` und `Duration` anwenden).
   - Backend `POST /pacing/timeline` muss `clip_start+(end-start) <= actual_clip_dur` cappen (Auto-Pfad-Logik bei R12b/SEV-004 wiederverwenden).
   - Nach jedem Drag/Trim: `TimelineEntries` nach `StartTime` sortieren.

**Priorität 2 — Korrektheit:**

3. **Fix L-TI-6 + L-TI-9 + L-TI-10:** `validate_timeline` strenger machen:
   - Audio-Overflow zu Error (oder Cap) statt Warning.
   - Overlapping cuts (>10ms) zu Error.
   - Gaps zwischen aufeinanderfolgenden Cuts melden (Warning ≥ 0.1s, Error ≥ 1s).
4. **Fix L-TI-2:** `_enforce_clip_lengths` Split-Logik: prüfe Min-Length-Distanz zum **nächsten** echten Cut, nicht nur zum vorletzten Split.

**Priorität 3 — Determinismus:**

5. **L-TI-8:** Optional `seed: int|None` in PacingConfigSchema → `random.Random(seed)` Local-Instance in Engine + Service. Default `None` (heutiges Verhalten). Test-Determinismus möglich.

**Priorität 4 — Robustheit:**

6. **L-TI-12:** ffprobe-Failure soll Warning loggen + cut markieren (z.B. `metadata.warn_ffprobe_failed=True`), nicht stumm passieren.
7. **L-TI-11:** Downbeat-Match auf 5ms-Toleranz statt exact-Float-Equality.

**Priorität 5 — Test-Coverage:**

8. Integration-Test: 30s-Mix mit `use_semantic=True` → erwartet >5 Cuts (heute: 14 fallback statt ~30). Würde L-TI-1 sofort fangen.
9. UI-Test: Drag-Cut-Past-Audio-End → Server soll 400 zurückgeben (heute: 200 mit Warning).

---

## Top-5 Critical Findings

1. **L-TI-1 [CRITICAL] `prompt=`-Kwarg-Crash kills Semantic/Structure-Pfad live in production.** Log-Evidenz: 4× errors in `logs\backend.log`. Engine erzeugt 2184 saubere Cuts → Crash → Fallback liefert nur 14. User sieht falsche Cut-Liste ohne Fehlermeldung.

2. **L-TI-4 [HIGH] Trim-Resize ist Stub — UI suggests Funktion die nicht existiert.** Drag-Handles sichtbar, Cursor ändert sich, Click+Drag tut nichts. Workflow-Loch im manuellen Mode.

3. **L-TI-3 [HIGH] Manuelle Edits cappen `clip_start+duration` nicht gegen Video-Länge.** Nur Auto-Pfad hat R12b-Schutz; `POST /pacing/timeline` ist ungeschützt. Render bricht ab oder zeigt schwarze Frames.

4. **L-TI-5 [HIGH] Drag re-orderet TimelineEntries-Collection nicht.** Reihenfolge != Zeit-Reihenfolge möglich. `NextCut`/`PreviousCut` Navigation bricht. Render-Pipeline könnte chronologisch verworrene Timeline rendern.

5. **L-TI-2 [HIGH] `_enforce_clip_lengths` Split-Logik kann unterhalb min_length splitten.** Random-Jitter im Auto-Split + Distanz-Check nur gegen letzte split-Position, nicht gegen nächsten echten Cut. Spec-Verletzung in seltenen Fällen.

---

## Empfehlungs-Pfad (Next-Step Tasks)

1. **TASK-TI-1 (Hot-Fix, 30min):** L-TI-1 fixen — `prompt`-kwarg ergänzen. Verify mit echtem `use_semantic=True` Run.
2. **TASK-TI-2 (1-2h):** L-TI-4 — Trim-Resize implementieren (StartTime+ClipStart bei left-trim, EndTime+Duration bei right-trim, Snap, MouseUp commit).
3. **TASK-TI-3 (45min):** L-TI-3 — `_run_pacing_generation`-Cap-Logik (R12b) auch in `update_timeline`-Endpoint einbauen.
4. **TASK-TI-4 (30min):** L-TI-5 — Nach `Clip_MouseUp` `TimelineEntries.OrderBy(e=>e.StartTime)` reapplyien.
5. **TASK-TI-5 (1h):** L-TI-6/L-TI-9/L-TI-10 — `validate_timeline` erweitern (audio_overflow als error, overlap as error, gap detection).
6. **TASK-TI-6 (2h):** L-TI-2 — `_enforce_clip_lengths` Distanz-Check auf nächsten echten Cut erweitern + Edge-Case Tests.
7. **TASK-TI-7 (1h):** Integration-Tests für jeden Fix.

Geschätzter Gesamt-Aufwand: ~7h Eng-Time für volle Timeline-Integrität.
