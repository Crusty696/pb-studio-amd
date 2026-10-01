# 🔍 Code-Audit Report — PB Studio (AMD Premium Edition)

**Projekt:** `C:\Users\david\Documents\Pb_studio_AMD_version`
**Analysierte Schichten:** Python Backend (`src/pb_studio`) + FastAPI Backend (`backend/`)
**Sprache(n):** Python 3.11 (FastAPI, ONNX/DirectML, librosa, OpenCV, SQLite/FAISS)
**Datum:** 2026-07-24
**Methode:** Statische Analyse (py_compile, pyflakes, ruff) + tiefe forensische Logik-Analyse (9 parallele Auditoren) + manuelle Verifikation der kritischen Funde
**Status:** **41 Befunde** — 7 kritisch 🔴, 20 mittel 🟡, 14 niedrig 🟢
**⚠️ Es wurde KEIN Code verändert. Dieser Bericht dokumentiert ausschließlich.**

---

## Umfang & Methodik

Analysiert wurden **162 Python-Dateien** (137 in `src/pb_studio`, 25 im `backend/`), rund **1,55 MB** Quellcode über alle Schichten: Audio, Video, AI/LLM, Pacing, Core/VRAM, Rendering, Workers, Data/Storage/Brain und die FastAPI-Router.

Vorgehen in drei Stufen:

1. **Dynamische/statische Werkzeuge** im isolierten Container (Python 3.11.15, exakt die Projektversion): `py_compile` über alle Module, `pyflakes` und `ruff` (Regeln F821/F823/F811/E722/B006 u.a.).
2. **Tiefe Logik-Analyse** durch 9 spezialisierte Auditoren, je einem Modul-Cluster zugeordnet, mit vollständigem Lesen der Dateien.
3. **Manuelle Verifikation** der schwerwiegenden Funde (Scope-Analyse, Aufruf-Verfolgung), um Falsch-Positive auszuschließen.

**Nicht Teil dieses Durchlaufs:** die C#/WPF-UI (`PBStudio.UI`, ~100 Dateien) und das archivierte `ui_legacy_archived`. Die UI↔API-Verdrahtung wurde von der Backend-Seite geprüft; eine dedizierte C#-Analyse kann in einem Folgedurchlauf erfolgen.

---

## Zusammenfassung

| Typ | Anzahl |
|-----|--------|
| Syntaxfehler (py_compile) | 0 |
| 🔴 Kritisch (Crash / stiller Datenfehler / Ressourcen-Leak) | 7 |
| 🟡 Mittel (falsches Verhalten / latenter Bug) | 20 |
| 🟢 Niedrig (Robustheit / Style / kosmetisch) | 14 |
| **Gesamt** | **41** |

**IRON-RULE-Status:** Keine harten Verstöße (kein CUDA/`torch.cuda`/`pynvml`/NVENC gefunden; DirectML-Sessions setzen durchgängig `enable_mem_pattern=False` **und** `enable_cpu_mem_arena=False`; GPU-Monitoring via LibreHardwareMonitor). **Eine dokumentierte Abweichung:** Der Software-Encoder-Fallback nutzt `libx264/libx265/libsvtav1` (siehe FINDING #26) — kein NVENC, aber eine Abweichung von „Hardware-Encoding MUSS AMF sein".

---

## 🔴 Kritische Befunde

### ❌ FINDING #1 — `UnboundLocalError`: Audio-Embedding stürzt bei jedem Lauf ab
**Datei:** `src/pb_studio/workers/audio/audio_embedding_worker.py`
**Zeile:** 84 (Ursache: Zeile 121)
**Schweregrad:** 🔴 Kritisch — **von mir manuell bestätigt**

```python
# Zeile 15 (Modul-Ebene):
from ...ai.clap_pytorch import CLAPPyTorch, CLAP_SAMPLE_RATE
...
def _execute(self) -> AudioEmbeddingResult:
    ...
    # Zeile 84 — erste Verwendung:
    audio, sr = librosa.load(self.wav_path, sr=CLAP_SAMPLE_RATE, mono=True)
    ...
    for i, start_time in enumerate(chunk_positions):
        # Zeile 121 — lokaler Re-Import IM SELBEN Funktions-Scope:
        from ...ai.clap_pytorch import CLAP_DURATION, CLAP_SAMPLE_RATE
```

**Problem:** Weil `CLAP_SAMPLE_RATE` in Zeile 121 innerhalb von `_execute()` neu importiert (= zugewiesen) wird, behandelt Python den Namen für die **gesamte Funktion** als lokal. Die frühere Verwendung in Zeile 84 greift damit auf eine noch nicht zugewiesene lokale Variable zu → **`UnboundLocalError` bei jedem Aufruf**, noch bevor die Schleife erreicht wird. Die Audio-Embedding-Erzeugung (CLAP) ist damit vollständig gebrochen. Eingeführt durch den Kommentar-markierten „BUG-092 FIX".
**Fix-Richtung (nur Hinweis):** Den lokalen Re-Import in Zeile 121 entfernen (das Modul-Level-Import genügt) oder `CLAP_DURATION` separat importieren.

---

### ❌ FINDING #2 — VRAM wird nie freigegeben: globales Budget-Leck im Vision-Worker
**Datei:** `src/pb_studio/workers/video/video_vision_worker.py`
**Zeile:** 156 (Reserve/Commit bei 112)
**Schweregrad:** 🔴 Kritisch

```python
arbiter.commit(model_id)          # ~Zeile 112: 2500 MB committed
...
finally:
    if cap is not None: cap.release()
    self._unload_model()          # ~Zeile 156 — KEIN arbiter.release(...)
```

**Problem:** Der Vision-Worker reserviert/committed 2500 MB für Moondream, ruft im `finally` aber **niemals `arbiter.release()`** auf — anders als der Motion- und der Stem-Worker, die korrekt freigeben. Der `VRAMArbiter` delegiert an einen prozessweiten Singleton, d.h. die 2500 MB bleiben nach jedem Vision-Lauf dauerhaft „belegt". Nach ein bis zwei Läufen verweigert der Budget-Manager alle weiteren GPU-Aufgaben (Stem, Motion, nächster Vision) mit „Insufficient VRAM", bis der Prozess neu startet. Verstößt gegen die VRAM-Freigabe-Regel.

---

### ❌ FINDING #3 — VRAM-Leck + Buchungsdrift in `update_max_vram` bei unzureichender Verdrängung
**Datei:** `src/pb_studio/core/vram_budget_manager.py`
**Zeile:** 395–418
**Schweregrad:** 🔴 Kritisch

```python
freed, callbacks_to_invoke = self._evict_for_space(shortfall)   # 397: senkt _committed_mb, sammelt Unload-Callbacks
if new_usable < self._committed_mb:
    raise ValueError(...)                                       # 399-403: bricht ab
...
for cb in callbacks_to_invoke:                                  # 413-418: wird nie erreicht
    cb()
```

**Problem:** `_evict_for_space` verändert die Buchhaltung (`_committed_mb` verringern, `is_loaded=False` setzen) **und** sammelt die physischen Unload-Callbacks — *bevor* die Machbarkeit erneut geprüft wird. Reicht die Verdrängung nicht (z.B. weil ein CRITICAL-Modell nicht verdrängt werden darf), wird `ValueError` geworfen und der Code erreicht die Callback-Schleife (413) nie. Folge: Das verdrängte Modell ist physisch **noch im VRAM**, aber `_committed_mb` wurde bereits reduziert → echtes VRAM-Leck **plus** dauerhafte Unterzählung des Budgets. Die Operation ist zudem ein verlustbehafteter No-Op (Limit bleibt unverändert).

---

### ❌ FINDING #4 — `reserve(force=True)` kann VRAM überbuchen, wenn ein Eviction-Callback wirft
**Datei:** `src/pb_studio/core/vram_budget_manager.py`
**Zeile:** 622–645
**Schweregrad:** 🔴 Kritisch (OOM-Risiko)

```python
self._reserved_mb += budget.estimated_vram_mb        # 626: Reservierung gewährt
# ... Callbacks laufen außerhalb des Locks ...
except ...:
    budget.is_loaded = True
    self._committed_mb += budget.estimated_vram_mb    # 641-643: verdrängtes Modell zurückbuchen
```

**Problem:** Bei `force=True` wird ein Modell verdrängt und die neue Reservierung gewährt (`_reserved_mb += …`). Wirft danach der Unload-Callback des verdrängten Modells eine Ausnahme, bucht der `except`-Zweig dessen VRAM wieder als committed — **rollt die neue Reservierung aber nicht zurück**. Nun sind sowohl das (weiterhin residente) verdrängte Modell als auch die neue Reservierung gegen ein Budget gezählt, das nur für eines Platz hatte → der Manager autorisiert mehr VRAM als physisch existiert. Genau das, was er verhindern soll → reales DirectML-OOM-Risiko beim nächsten echten Load.

---

### ❌ FINDING #5 — Spektral-Band „air" (12–20 kHz) ist bei 22050 Hz permanent tot
**Datei:** `src/pb_studio/audio/spectral_analyzer.py`
**Zeile:** 33 / 137–139
**Schweregrad:** 🔴 Kritisch (garantiert falsches Kern-Feature)

```python
"air": (12000, 20000)                     # Zeile 33
...
freqs = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)
freq_mask = (freqs >= low_freq) & (freqs < high_freq)   # Zeile 139
```

**Problem:** `SpectralAnalyzer` läuft standardmäßig mit `sr=22050` (Nyquist = **11025 Hz**). Kein einziger FFT-Bin erfüllt jemals `freqs >= 12000`, daher ist `band_energies['air']` **auf jedem Lauf ein Null-Array** (`mean=0`, `var=0`). Das Band `brilliance` (6000–12000) wird bei 11025 Hz ebenfalls abgeschnitten. Das beworbene 8-Band-Modell ist real ein 7-Band-Modell mit einem konstanten Null-Kanal — jeder daraus abgeleitete Feature-Vektor und jede Event-Erkennung ist systematisch falsch, kein Edge-Case.

---

### ❌ FINDING #6 — Cold-Start-Gewichte `min/max_clip_length` sprengen den [0,1]-Bereich und dominieren jeden Brain-Score
**Datei:** `src/pb_studio/brain/cold_start.py`
**Zeile:** 18–19 (Wirkung: `weight_store.py:217`, `post_processor.py:215-218`, `scorer.py:32-37`)
**Schweregrad:** 🔴 Kritisch (stiller Ranking-Fehler)

```python
"min_clip_length": 1.0,
"max_clip_length": 8.0,     # als Posterior-GEWICHT verwendet
```

**Problem:** Im Cold-Start (weniger als `MIN_CONFIDENT_SAMPLES=10` Samples pro Bucket — also fast immer in der Anfangsphase) liefert `_compute_posterior_mean` diese Defaults direkt als Achsengewicht. `sub_score = bridge_value * weight` ergibt für `max_clip_length` bis zu **8.0**, während alle anderen der 17 Achsen ≤ ~1.2 beitragen. Der `final_score = mean(17 Achsen)` wird dadurch von der Clip-Länge dominiert und liegt auf einer anderen Skala als die dokumentierten 0..1 — das `final_score < min_confidence`-Filtern (post_processor.py:222) wird dadurch bedeutungslos. Cold-Start-Ranking kollabiert praktisch zu „sortiere nach Clip-Dauer".

---

### ❌ FINDING #7 — `WorkerOrchestrator`-Pipelines brechen sofort ab (`run()` liefert `None`)
**Datei:** `src/pb_studio/workers/orchestrator.py:238` + `src/pb_studio/workers/base_worker.py:131`
**Schweregrad:** 🔴 Kritisch **im Code** — **aber derzeit ungenutzter Pfad** (siehe Hinweis)

```python
# base_worker.py:131 — run() ist -> None und gibt NICHTS zurück:
def run(self) -> None:
    ...
    result = self._execute()
    if not self._is_cancelled:
        self.emit_result(result)     # Ergebnis verlässt run() nur per Signal
    # kein return

# orchestrator.py:238:
return worker.run()                  # => liefert None
```

**Problem:** `_run_worker_sync` gibt `worker.run()` zurück, aber `run()` ist ein fire-and-forget-Einstiegspunkt (`-> None`); das Ergebnis wird nur über das `result`-Signal emittiert. Damit erhalten `run_audio_pipeline` / `run_video_pipeline` / `run_generation_pipeline` `None` und die Folgezeile (`import_result.temp_wav_path` bzw. `import_result["metadata"]`) wirft `AttributeError`/`TypeError`. Der „BUG-083 FIX"-Kommentar hat `._execute()` auf `.run()` umgestellt, was die synchrone Orchestrierung strukturell inkompatibel macht.
**Verifizierter Hinweis (Ehrlichkeit):** `WorkerOrchestrator` wird zwar in `workers/__init__.py` exportiert, hat aber **keinen Aufrufer** im `backend/` oder sonst im geprüften Code — der FastAPI-Backend nutzt die Router direkt. Der Defekt ist real, der Pfad aber aktuell **verwaist** (Rest der PyQt→WPF-Migration). Reale Auswirkung erst, sobald etwas die Orchestrator-Pipelines aufruft.

---

## 🟡 Mittlere Befunde

### ⚠️ FINDING #8 — `_stretch_last_cut_to_audio` hebt die Clip-Längen-Absicherung wieder auf
**Datei:** `src/pb_studio/services/pacing_service.py:171` (Cap bei 128–131)
**Schweregrad:** 🟡 Mittel (grenzwertig kritisch)

`_process_pacing_cuts_to_cutlist` deckelt den letzten Cut auf die echte Clip-Länge (`duration = min(duration, actual_clip_dur)`), aber `_finalize_cut_list` → `_stretch_last_cut_to_audio` setzt danach `last.end_time = audio_duration` **bedingungslos**. Ist der letzte Clip kürzer als sein Slot (z.B. 3 s Clip in 12 s Slot), wird der Out-Point wieder 9 s über das Clip-Ende hinausgezogen → eingefrorenes/schwarzes Ende oder FFmpeg-Out-of-range-Read im letzten Segment, auf dem normalen Auto-Pacing-Pfad.

### ⚠️ FINDING #9 — Multiplikativer Key-Score invertiert das Ranking bei negativem `total_score`
**Datei:** `src/pb_studio/pacing/clip_selector.py:699`
**Schweregrad:** 🟡 Mittel

`total_score *= key_score` mit `key_score ∈ [0.3, 1.0]`. In „break"-Sektionen kann `total_score` negativ sein (Zeile 663: `-= 0.50`). Ein multiplikativer Faktor < 1 zieht negative Werte **Richtung Null**, d.h. der schlechtere Key-Match (`0.3`) ergibt einen *höheren* Score als der perfekte (`1.0`). Key-Matching bevorzugt dann in jeder Sektion mit negativer Basis genau den unpassendsten Clip.

### ⚠️ FINDING #10 — `Path(None)` `TypeError`, wenn ein Clip `file_path=None` hat
**Datei:** `src/pb_studio/pacing/pacing_service.py:454-455`
**Schweregrad:** 🟡 Mittel

`Path(c.get("file_path", c.get("path", "")))` — `dict.get(key, default)` liefert bei vorhandenem Schlüssel mit Wert `None` eben `None` (nicht den Default). Bei einer DB-Zeile mit NULL-Pfad wird also `Path(None)` gebaut → `TypeError`. Der Code liegt außerhalb des `try`, daher bricht die Cutlist-Generierung ab.

### ⚠️ FINDING #11 — Injiziertes `_pre_cached_energy` desynchronisiert `energy_curve`/`energy_times` → `IndexError`
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:258 / 656-667`
**Schweregrad:** 🟡 Mittel

`analyze_audio_structure` überschreibt `rms` mit der gecachten Kurve, behält aber die vom Aufrufer gelieferten `times`. Ist der Cache länger als `times`, iteriert `_detect_energy_peaks` (ENERGY_SYNC-Modus) bis `len(energy_curve)-1` und greift auf `energy_times[i]` außerhalb der Grenzen zu → `IndexError`; in der Gegenrichtung: falsche Energie an falscher Zeitposition.

### ⚠️ FINDING #12 — Fixes `hop_length=512` auf Index in gecachte Energie-Arrays
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:1975-1995` (gleiches Muster 1793-1800)
**Schweregrad:** 🟡 Mittel

`best` ist ein Index in `_pre_cached_energy`, aber `librosa.frames_to_time(best, sr=sr, hop_length=512)` nimmt eine feste Framing-Auflösung an. Wurde die gecachte Kurve mit anderem Hop/anderer sr erzeugt, landen alle Energie-Trigger auf falschen Zeitstempeln (stille Desynchronisation zur Musik).

### ⚠️ FINDING #13 — Bass-Trigger-Stärken aus Full-Mix-Energie statt Bass-Energie
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:1793-1800`
**Schweregrad:** 🟡 Mittel

`frame` stammt aus Onset-Detection auf dem **Bass-Stem**, aber bei vorhandenem `_pre_cached_energy` wird die Stärke aus der **Full-Mix**-RMS am Bass-Frame-Index gelesen. Bass-„Drop"-Trigger bekommen so Stärken des gesamten Mixes; die `min(frame, len-1)`-Klammer maskiert zusätzlich den Längen-Mismatch.

### ⚠️ FINDING #14 — Structure-Weights-Clamp beruht auf falscher Annahme, staucht High-Energy-Dynamik
**Datei:** `src/pb_studio/pacing/advanced_pacing_engine.py:1419-1437`
**Schweregrad:** 🟡 Mittel

Kommentar behauptet `energy_level ≤ 1.0`, tatsächlich enthält `STRUCTURE_INTENSITY_MULTIPLIERS`/`ENERGY_PHASE_MULTIPLIERS` Werte wie `chorus:1.2`, `drop:1.5`. `min(strength*energy_level, 1.0)` sättigt daher Chorus- und Drop-Trigger gleichermaßen auf 1.0 → Chorus und Drop werden ununterscheidbar, die beabsichtigte Gewichtung verschwindet.

### ⚠️ FINDING #15 — `_detect_events` nutzt `self.sr` statt der tatsächlichen Sample-Rate
**Datei:** `src/pb_studio/audio/spectral_analyzer.py:216 / 247`
**Schweregrad:** 🟡 Mittel

`window = int(self.sr / hop_length)` und `buildup_window = int(4*self.sr/hop_length)`, während `analyze_from_array(y, sr)` ein beliebiges `sr` bekommt. Bei `sr=44100` auf einem `SpectralAnalyzer(sr=22050)` sind die „1-Sekunden"- und „4-Sekunden"-Fenster real halb so lang → Drop/Breakdown/Buildup-Erkennung verschiebt sich, Event-Zeiten sind sample-rate-abhängig falsch.

### ⚠️ FINDING #16 — `get_time_axis` fest auf `self.sr`, aber lange Dateien mit reduzierter Rate analysiert
**Datei:** `src/pb_studio/audio/waveform_analyzer.py:254-273`
**Schweregrad:** 🟡 Mittel

`extract_3band_waveform` setzt `use_sr=11025` für Dateien > 30 min (bzw. `target_sr`-Override), aber `get_time_axis` mappt Frame→Zeit mit `self.sr=22050`. Bei einem 40-min-Mix ist jede Zeitmarke ~2× zu klein (Beat bei 20:00 wird bei 10:00 gemeldet).

### ⚠️ FINDING #17 — Energie-Dip-Zeitstempel aus falschem Array indiziert
**Datei:** `src/pb_studio/audio/dj_mix_analyzer.py:113-120`
**Schweregrad:** 🟡 Mittel

`energy_changes.append((chroma_times[min(i, len-1)], …))`, wobei `i` über `rms_windows` läuft. `chroma_windows` (Filter `>= sr_a`) und `rms_windows` (Filter `>= window_frames`) haben unterschiedliche Längen/Index→Zeit-Mappings → ein bei RMS-Fenster `i` gefundener Dip wird mit einer unzusammenhängenden Chroma-Zeit versehen (Transition-Zeiten falsch).

### ⚠️ FINDING #18 — Checkerboard-Novelty per Off-by-one bei ungeradem Kernel komplett null
**Datei:** `src/pb_studio/audio/structure_analyzer.py:127-133`
**Schweregrad:** 🟡 Mittel

`sub = rec_matrix[i-half_k : i+half_k, …]` liefert Breite `2*half_k = kernel_size-1`, nie gleich `kernel.shape`. Bei ungeradem `kernel_size` (kurze Clips < ~15 s) ist die `if sub.shape == kernel.shape`-Bedingung immer False → `novelty` bleibt null → Segmentgrenzen kollabieren zu `[0, duration]` (stille Fehlanalyse).

### ⚠️ FINDING #19 — LHM-Fallback greift ohne `_lhm_lock` auf native Objekte zu (Data Race)
**Datei:** `src/pb_studio/core/system_monitor.py:369-391`
**Schweregrad:** 🟡 Mittel

`_query_temperature_alternative` ruft `hardware.Update()` **ohne** `_lhm_lock` aus dem Daemon-Thread, während `_collect_lhm_stats` dasselbe unter Lock tut. LibreHardwareMonitorLib ist nicht thread-safe; gleichzeitige `Update()`/Sensor-Enumeration auf denselben CLR-Objekten kann Werte korrumpieren oder den pythonnet-Interop crashen — der Lock garantiert also nicht wirklich Single-Thread-Zugriff.

### ⚠️ FINDING #20 — Blockierende OpenCV-Dekodierung + KMeans auf dem Event-Loop-Thread
**Datei:** `backend/routers/video_router.py:1000-1018` (awaited bei 471)
**Schweregrad:** 🟡 Mittel

`_run_color_and_caption_analysis` ist `async def` und wird direkt awaited, führt aber `cv2.VideoCapture`/`cap.read` und `extract_dominant_colors(k=5)` **synchron auf dem Loop-Thread** aus (nur der LM-Studio-Call ist `to_thread`-gewrappt). Bei 1080p+ blockiert das den einzigen Event-Loop für hunderte ms bis ~1 s → SSE-Streams (`/events/gpu`, `/events/progress`, Heartbeat) pausieren, alle in-flight Requests stallen. Kontrast: Scene-Detection nebenan ist korrekt `to_thread`-gewrappt.

### ⚠️ FINDING #21 — SQLite-Reads synchron auf dem Event-Loop, geteilte Connection mit Threadpool-Writern
**Datei:** `backend/routers/brain_router.py:48-53, 89-92, 135-139, 275-280`
**Schweregrad:** 🟡 Mittel

`svc.state_conn.execute(...).fetchall()` läuft direkt (ohne `to_thread`) in `suggest/feedback/learning_session/explain`, während Writes in `to_thread` unter `db_write_lock` laufen. Die Connection ist `check_same_thread=False` und wird aus Loop- **und** Worker-Threads genutzt. Ein `GET /brain/explain` (Loop) parallel zu `POST /brain/feedback` (Worker) kann den Loop blockieren oder `sqlite3.OperationalError/ProgrammingError` an den Client zurückgeben; `db_write_lock` serialisiert nur Writer gegen Writer.

### ⚠️ FINDING #22 — Committed VRAM leckt, wenn `VideoCapture` nicht öffnet (Motion-Worker)
**Datei:** `src/pb_studio/workers/video/video_motion_worker.py:121`
**Schweregrad:** 🟡 Mittel

`arbiter.commit(model_id)` (RAFT, 1500 MB) bei 113, dann `cv2.VideoCapture`/`if not cap.isOpened(): raise` bei 121-123 — **außerhalb** des `try` (ab 125). Bei nicht öffenbarer Datei propagiert der `RuntimeError` vor Eintritt in `try/finally`, sodass `arbiter.release()` (156) und `unload()` nie laufen → 1500 MB bleiben committed, RAFT bleibt geladen.

### ⚠️ FINDING #23 — Reserviertes VRAM leckt bei Cancel/Fehler vor dem `try` (Stem/Motion/Vision)
**Datei:** `src/pb_studio/workers/audio/audio_stem_worker.py:73` (analog Motion/Vision)
**Schweregrad:** 🟡 Mittel

`arbiter.reserve(4000, …)` (70), danach `_check_cancelled()` (73/88/96) und `StemSeparator()` (81) **vor** dem `try` (98), dessen `finally` (125) freigibt. Cancel im Reserve→try-Fenster (sehr häufig, da Reserve zuerst passiert) wirft `CancelledError`, die hier nicht gefangen wird → Reservierung nie freigegeben. Gleiches Strukturmuster in Motion- und Vision-Worker.

### ⚠️ FINDING #24 — Cancellation wird während der langen Render-/Concat-Phasen nicht beachtet
**Datei:** `src/pb_studio/workers/generation/export_worker.py:224`
**Schweregrad:** 🟡 Mittel

`ExportWorker.cancel()` setzt nur das eigene `_is_cancelled`. Kinder (`RenderWorker`/`ConcatWorker`) sind separate `BaseWorker`-Instanzen mit eigenem `_is_cancelled=False` und werden nie über den Parent-Cancel informiert; `_check_cancelled()` erfolgt nur *zwischen* Phasen. Während der längsten Phase (per-Segment-FFmpeg, bis 300 s je Segment) wird ein Cancel effektiv ignoriert.

### ⚠️ FINDING #25 — `engine._ffmpeg_extract` schluckt Encode-Fehler; kaputte Segmente werden trotzdem concatenated
**Datei:** `src/pb_studio/video/engine.py:296-318`
**Schweregrad:** 🟡 Mittel

Der Software-Retry (318) prüft **keinen** Return-Code, und ist der Erst-Encoder bereits Software (`is_hardware=False`), gibt es gar keinen Fallback. In beiden Fällen kehrt `_ffmpeg_extract` normal zurück und `_render_segments` (243) hängt den Segment-Pfad **bedingungslos** an → `_concat_segments` bekommt eine nicht existierende/0-Byte-Datei in die Concat-Liste.

### ⚠️ FINDING #26 — Software-Encoder-Fallback nutzt `libx264/libx265/libsvtav1` (IRON-RULE-Abweichung)
**Datei:** `src/pb_studio/video/engine.py:293,301-304` + `encoder_utils.py:287-367`
**Schweregrad:** 🟡 Mittel (dokumentierte, bewusste Abweichung)

Ist AMF nicht verfügbar (`check_amf_available()` false), fällt das Rendering still auf CPU-`libx264/libx265/libsvtav1` zurück. Kein NVENC/VideoToolbox — aber eine reale Abweichung von „Hardware-Encoding MUSS AMF sein". Sollte mindestens sichtbar an den Nutzer gemeldet werden, statt still CPU zu encodieren.

### ⚠️ FINDING #27 — RAFT `calculate_flow` liefert bei jedem Fehler All-Zeros (fehlgeschlagen ≠ „keine Bewegung")
**Datei:** `src/pb_studio/video/raft.py:296-399`
**Schweregrad:** 🟡 Mittel

Jeder Fehlerpfad `return np.zeros(...)`; der äußere `except Exception` fängt alles. Modell fehlt / DirectML weg / Inferenz wirft → `avg_motion=0`, `peak_motion=0`, `scene_changes=[]`. Aufrufer können „Analyse fehlgeschlagen" nicht von „statisches Material" unterscheiden; das nachgelagerte Pacing bekommt still keine Trigger.

---

## 🟢 Niedrige Befunde

### FINDING #28 — `siglip_wrapper.encode_text` gibt für Einzel-String nie 1-D-Vektor zurück
`src/pb_studio/ai/siglip_wrapper.py:224` — `return embeddings[0] if len(texts)==1 and not isinstance(texts, list) else embeddings`. Da `texts` in Zeile 211 stets zur Liste gemacht wird, ist `not isinstance(texts, list)` immer False → immer 2-D. Latenter API-Bug für neue Einzel-String-Aufrufer (aktuelle Aufrufer kompensieren). 🟢

### FINDING #29 — CLAP-ONNX-Pfad liefert erfundene Klassifikation / `None`-Text-Embeddings still
`src/pb_studio/ai/clap_wrapper.py:190,197` — Bei vorhandenen ONNX-Dateien liefert `classify_audio` deterministische Mock-Tags und `encode_text` `None`, ohne Fehler. Aktuell latent (PyTorch-CPU-Fallback ist der übliche Pfad), aber sobald ONNX-Dateien vorliegen, degradiert die Mood-Analyse still zu Konstantdaten. 🟢

### FINDING #30 — LLM-Fehler-Triage matcht auf Substring `"tools"/"function"` vor Verbindungs-/Timeout-Checks
`src/pb_studio/ai/chat_agent.py:452` — Jede Fehlermeldung, die zufällig „function" enthält, wird als „Modell unterstützt keine Tools" gewertet und still ohne Tools erneut versucht → tool-lose Antwort statt echter Fehler. 🟢

### FINDING #31 — Tool-Result-Message ohne `tool_call_id`, wenn Modell keine ID liefert
`src/pb_studio/ai/chat_agent.py:664` — `tool_call_id` wird nur bei Truthy gesetzt. Strikte OpenAI-Backends lehnen die Message-Array-Paarung im nächsten Turn ab (400) → Turn bricht mit irreführender „History zu lang"-Meldung ab. 🟢

### FINDING #32 — Moondream „latest snapshot" alphabetisch statt nach mtime gewählt
`src/pb_studio/ai/moondream_pytorch.py:65` — `sorted(...)[-1]` über Commit-Hash-Ordner liefert den lexikografisch größten, nicht den neuesten. Kann ältere Weights/Remote-Code laden. 🟢

### FINDING #33 — Stille `except Exception: return None` in SigLIP verbergen Inferenz-Fehler
`src/pb_studio/ai/siglip_wrapper.py:167,225,148` — Fehlerhafter Frame/OOM → stilles `None`; `SmartDirector` ersetzt durch `np.zeros(1152)`, der Clip wird als valide behandelt („alle Clips gleich"-Diagnose sehr schwer). 🟢

### FINDING #34 — `lmstudio_client._raise_for_status` liest `response.text` auf ungelesenem Stream
`src/pb_studio/ai/lmstudio_client.py:375` (Aufruf 590) — Bei streaming-Fehler (400/404) wirft `.text` `ResponseNotRead`, wird von `except: pass` geschluckt → Fehlermeldung ohne Diagnose-Body. 🟢

### FINDING #35 — `_seconds_to_smpte` bricht bei `fps=0` und trunkiert NTSC-Raten
`src/pb_studio/pacing/export_handler.py:257-258` — `int(fps)` → `ZeroDivisionError` bei 0; bei 29.97/23.976 falsche SMPTE-Timecodes im EDL. 🟢

### FINDING #36 — `cv2.VideoCapture`-Handles leaken bei Fehler außerhalb `finally`
`clip_selector.py:828-855`, `video_embedder.py:139-141`, `visual_curves.py:45-47` — Capture-Objekt vor dem `try` erzeugt bzw. Release nur im Happy-Path; wirft eine Frame-Op mittendrin, wird nie released (Handle-Leck über Batches). 🟢

### FINDING #37 — Tombstone-Filterung nach FAISS-Top-k verkleinert Ergebnismenge still
`src/pb_studio/data/vector_store.py:365-375` — `search(q, k)` liefert k, danach werden tombstonte IDs entfernt → weniger als k Live-Treffer, obwohl valide Treffer bei Rang k+1 existieren. Sollte over-fetchen. 🟢

### FINDING #38 — `create_project` schluckt `OperationalError` und macht den Retry-Decorator tot
`src/pb_studio/data/repositories/project_repository.py:73-75` — `except Exception: return -1` verhindert, dass `@_retry_on_database_lock` den Lock-Fehler sieht (kein Backoff/Retry). `update/delete_project` re-raisen korrekt — Inkonsistenz. 🟢

### FINDING #39 — `feedback_logger` `BEGIN IMMEDIATE` auf geteilter Connection nicht nebenläufigkeitssicher
`src/pb_studio/brain/feedback_logger.py:66-81` — Zwei parallele `log_feedback` auf derselben prozessweiten Connection → „cannot start a transaction within a transaction"; zudem committet das Roh-Event auf `state_conn` vor der Weights-Transaktion → State/Weights-Divergenz bei Rollback. 🟢

### FINDING #40 — `with persist_to_state_conn:` bietet keine Atomarität (Autocommit-Connection)
`src/pb_studio/brain/post_processor.py:111` — `state_conn` läuft mit `isolation_level=None`; `with conn:` committet nur beim Verlassen, ohne implizites `BEGIN` → kein Batching/keine Transaktion; ein späterer Cut-Insert-Fehler hinterlässt eine teilweise persistierte „current"-Timeline. 🟢

### FINDING #41 — `cancel_flags` / unbeschränkter Projektions-Cache wachsen unbegrenzt
`backend/app_state.py:349-371` (`cancel_flags` wird bei `reset()` nie geleert, nur auf True gesetzt; Reaper greift über `render_tasks`, das `reset()` vorher leert → verwaiste Flags) und `src/pb_studio/brain/cross_modal_projector.py:60,80-105` (`_projection_cache` ohne Größenlimit/Lock im Singleton). Langsames Memory-Creep über lange Sessions. 🟢

---

## Ausführungs-Log

```
Python: 3.11.15 (Container, entspricht Projekt-Pin Python 3.11)
py_compile über 162 Module ......... 0 Syntaxfehler
pyflakes ........................... 81 Meldungen (überwiegend ungenutzte Imports/lokale Variablen)
  → 1 echter Laufzeit-Bug isoliert: F823 CLAP_SAMPLE_RATE (FINDING #1)
  → 24× "undefined name" in advanced_pacing_engine → verifiziert als STRING-Annotationen
    (-> List["PacingCut"]) mit lokalen Imports → KEINE Laufzeit-NameErrors (nicht gemeldet)
  → ModelRegistry (models_router:184) ebenfalls String-Annotation → kein Bug
ruff (F821/F823/F811/E722/B006/B008 …):
  → F823 (1) bestätigt FINDING #1
  → B008 (33) = FastAPI Depends()/Query() → idiomatisch, KEIN Bug (verworfen)
9 forensische Auditoren über alle Modul-Cluster: 41 verifizierte Befunde
Manuelle Verifikation: FINDING #1 (Scope-Analyse), #7 (run()-Signatur + Aufrufer-Suche)
```

---

## Selbst-Überprüfung

- [x] Alle 162 Python-Dateien (src + backend) gelesen/analysiert
- [x] Statische **und** werkzeuggestützte **und** logische Analyse durchgeführt
- [x] Jeder Befund mit exakter Datei- und Zeilenangabe
- [x] Code-Ausschnitte direkt aus den Dateien übernommen
- [x] Falsch-Positive aktiv ausgeschlossen (String-Annotationen, FastAPI-`Depends`, NumPy-1-Shims)
- [x] Kritische Funde manuell verifiziert (#1, #7)
- [x] Bericht ehrlich und vollständig — **kein Code verändert**

**Kritische Reflexion / Grenzen dieser Analyse:**

1. **Ehrlichkeit zu FINDING #7:** Der Orchestrator-Bug ist im Code eindeutig, aber `WorkerOrchestrator` hat aktuell keinen Aufrufer. Ich habe ihn bewusst als „kritisch im Code, ungenutzter Pfad" eingestuft statt ihn zu dramatisieren.
2. **Statische Grenzen:** Die Tests (`pytest`) konnten **nicht** ausgeführt werden — die reale Laufzeitumgebung (DirectML/`onnxruntime-directml`, Torch-DirectML, LibreHardwareMonitor via pythonnet, AMF-FFmpeg) existiert nur auf dem Windows-Zielsystem, nicht im Linux-Analyse-Container. Die VRAM-/Threading-/Race-Befunde (#2–#4, #19, #22–#24) sind durch Code-Lesen belegt, aber nicht dynamisch reproduziert. Ein Lauf von `pytest Tests/ -x -q` auf dem Zielrechner würde einige davon (v.a. #1) sofort bestätigen.
3. **Skalen-Annahme bei #6:** Die Kritikalität hängt davon ab, dass `min/max_clip_length` als Multiplikator-Gewicht (nicht als absolute Sekunden-Konstante in einem separaten Feld) verwendet wird — das ist über `weight_store.py:217` + `scorer.py:32-37` belegt.
4. **Nicht abgedeckt:** C#/WPF-UI (`PBStudio.UI`, ~100 Dateien) und `ui_legacy_archived`. Empfehlung für einen Folgedurchlauf, insbesondere die `Services/ApiClient.cs` ↔ Backend-Schema-Verdrahtung und `SSEClient.cs`.
5. **Wahrscheinlich unvollständig bei Low-Severity:** Der Fokus lag auf echten Bugs mit konkretem Fehlerszenario; rein stilistische pyflakes-Treffer (ungenutzte Imports/Variablen) sind im Log zusammengefasst, aber nicht einzeln als Befund gelistet.

---

*Erstellt durch Code-Auditor (statisch + 9 forensische Auditoren + manuelle Verifikation). Es wurden keine Dateien verändert.*
