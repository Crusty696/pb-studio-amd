# AUDIT Rendering-Pipeline — 2026-05-11

Scope: Deep-Audit des Rendering-Subsystems
(`src/pb_studio/rendering/*`, `backend/routers/render_router.py`,
`backend/schemas/render_schemas.py`). Read-only. AUDIO/VIDEO/UI/STATE/GPU
sind nicht Teil dieser Audit.

---

## 1. Pipeline-Flow (Quelle bis Output)

End-to-End Render-Pfad:

| # | Stage | File:Line | Was passiert |
|---|---|---|---|
| 1 | HTTP Entry | `render_router.py:106-201` | `POST /render/start` empfängt `RenderRequest` |
| 2 | Schema-Validate | `render_schemas.py:38-53` | `output_dir_must_exist` + `audio_path_must_exist` |
| 3 | Timeline-Snapshot | `render_router.py:117-119` | 400 wenn `state.get_timeline_snapshot()` leer |
| 4 | Path-Traversal | `render_router.py:121-125` (SEC-002) | `output_p.is_relative_to(project_root)` 403 sonst |
| 5 | Task-Cleanup | `render_router.py:127-128` | Hält `state.render_tasks` ≤ 50 |
| 6 | Queue-Enqueue | `render_router.py:139-153` (Aufgabe I) | `RenderQueue.enqueue(media_hash, output_path, settings)` idempotent über `job_hash=sha256` |
| 7 | Task-Spawn | `render_router.py:173` | `asyncio.create_task(_run_render_task(...))` mit Timeline-Snapshot |
| 8 | GPU-Lock | `render_router.py:294` | `async with gpu_lock:` (Lock aus `dependencies.py:19`) |
| 9 | Pre-Render-Validate | `render_router.py:534-538` | `validate_timeline(timeline)` errors → `RuntimeError` (L-TI-5 strict) |
| 10 | Entry-Transform | `render_router.py:540-556` | Pacing-Format `{clip_id, start_time, end_time, metadata.file_path, metadata.clip_start}` → Render-Format `{file_path, in_point, out_point}` |
| 11 | Encoder-Detect | `render_service.py:73-105` | Probe `hevc_amf → av1_amf → h264_amf → h264_mf → libx265 → libx264`, gecacht `_working_encoder` |
| 12 | Normalisierung | `render_service.py:211-269` | Pro Clip ffprobe; bei `width/height/fps` Mismatch transcode zu `.temp_render/norm_*.mp4` |
| 13 | Concat-File | `render_service.py:350-363` | `file 'path' / inpoint x / outpoint y` via FFmpeg concat demuxer |
| 14 | Final FFmpeg | `render_service.py:365-457` | `ffmpeg -f concat -i list -i audio -map 0:v -map 1:a -c:v {enc} -c:a aac 320k -movflags +faststart -t {dur} out.mp4` |
| 15 | Progress-Parse | `render_service.py:459-600` | `stderr_thread` liest char-by-char, Regex `time=`/`frame=`/`fps=`, throttled 1s/1pct, → SSE `render_progress` |
| 16 | Cleanup | `render_service.py:659-666` | Temp-Norms + `concat_list.txt` unlink |
| 17 | Queue-Update | `render_router.py:321/347/374` | `_safe_queue_update(queue_job_id, COMPLETED/FAILED)` |
| 18 | Cleanup-Cancel | `render_router.py:396-426` | mtime-guarded delete der Output-Datei (schützt Vor-Outputs) |

Parallele Strukturen ohne aktiven Pfad:
`final_renderer.BatchRenderer` (Chunk-30-Strategie), `render_engine.RenderEngine`,
`preview_renderer.PreviewGenerator`, `proxy_service.ProxyService`,
`src/pb_studio/video/video_renderer.VideoRenderer` — alle vom Router NICHT
verdrahtet (siehe R-N1).

---

## 2. Korrektheits-Garantien

| Stage | Garantie | Implementiert? | File:Line |
|---|---|---|---|
| Router: 400 wenn Timeline leer | `if not timeline_snapshot: 400` | Ja | `render_router.py:117-119` |
| Router: 403 bei Path-Traversal | `output_p.is_relative_to(project_root)` | Ja (SEC-002) | `render_router.py:121-125` |
| Router: 404 wenn unbekannte task_id | `state.get_render_task` None → 404 | Ja | `render_router.py:217-219` |
| Router: GPU-Lock während Render | `async with gpu_lock` | Ja | `render_router.py:294` |
| Router: Pre-Render Validation | `validate_timeline` errors → RuntimeError | Ja (L-TI-5) | `render_router.py:534-538` |
| Router: Cancel-Flag Check | `is_cancelled()` in `on_progress` + Frame-Loop | Ja | `render_router.py:460-461, render_service.py:519-523` |
| Router: Queue-Persistence | `enqueue(media_hash, output_path, settings)` Crash-Resume via `restore_running_as_interrupted` | Ja | `render_queue.py:352-391` |
| Router: Idempotenz | `compute_job_hash(media_hash|output_path|settings_hash)` UNIQUE | Ja | `render_queue.py:111-115` |
| Router: Cleanup nach Cancel/Fail | mtime-guarded `_cleanup_render_temps` | Ja | `render_router.py:396-426` |
| Service: Encoder-Auto-Detect | `_detect_best_encoder` cached + lock | Ja | `render_service.py:58-105` |
| Service: Concat-Escape | `path.replace("\\", "/")` + Single-Quote-Escape | Ja (BUG-069) | `render_service.py:358-361` |
| Service: ffprobe Mismatch-Check | width/height/fps ≥ 0.1 → normalize | Ja | `render_service.py:247-269` |
| Service: Audio-Dauer Cap | `-t min(audio_dur, total_dur)` | Ja | `render_service.py:415-423` |
| Service: faststart Container | `-movflags +faststart` | Ja | `render_service.py:411` |
| Service: AMD AMF Params | `-quality balanced -b:v {bitrate}` | Teilweise | `render_service.py:394-405` (siehe R-N2) |
| Service: SW-Fallback CRF | `libx264 -crf 18`, `libx265 -crf 22` | Ja | `render_service.py:402-405` |
| Service: Audio-File Guard | `FileNotFoundError` wenn `audio_path` fehlt | Ja (BUG-070) | `render_service.py:377-378` |
| Service: FFmpeg-Error Tail | letzte 1000 Bytes stderr in RuntimeError | Ja | `render_service.py:602-617` |
| Service: Audio-Dauer-Cache | `audio_dur` einmalig ffprobe + reuse | Ja (R19/LOW-019-3) | `render_service.py:125, 415-416` |
| Service: Cleanup im finally | `_cleanup_temp(normalized_clips)` | Ja | `render_service.py:200-201` |
| BatchRenderer: Chunk-30 | `len(timeline)//30+1` Chunks | Ja | `final_renderer.py:44, 161-162` |
| BatchRenderer: yuv420p | `-pix_fmt yuv420p` in Chunk-Encode | Ja | `final_renderer.py:206` |
| BatchRenderer: Concat copy | `-c copy` für Chunks (keine Re-Encode) | Ja | `final_renderer.py:243` |
| BatchRenderer: Cleanup-Files | `_cleanup_temp_files` + `cleanup_temp_dir` | Ja | `final_renderer.py:287-301` |
| Preview: ts-Concat | mpegts-Segmente via `concat:` protocol | Ja | `preview_renderer.py:139-148` |
| Preview: 90s Default | `DEFAULT_DURATION = 90.0` | Ja | `preview_renderer.py:43` |
| Proxy: Hash-Stable | `md5(absolute_path|mtime)` | Ja | `proxy_service.py:65-68` |
| Proxy: Needs-Probe | `w>1920 or h>1080 or fps≠30` | Ja | `proxy_service.py:70-78` |
| Proxy: Cache-Reuse | Existiert + size>0 → skip | Ja | `proxy_service.py:119-122` |
| RenderEngine: Concat-Escape | identisch zu RenderService | Ja (BUG-069) | `render_engine.py:138-140` |
| RenderEngine: Encoder-Probe | `ffmpeg -encoders` Substring-Match | Ja, schwach | `render_engine.py:64-93` (siehe R-N6) |
| RenderQueue: UNIQUE-Hash | `UNIQUE(job_hash)` constraint | Ja | `render_queue.py:73, 232-260` |
| RenderQueue: Resume-on-Start | `restore_running_as_interrupted` | Ja | `render_queue.py:352-391` |
| RenderQueue: WAL+busy_timeout | Über DatabaseCore | Ja | `render_queue.py:158-166` |

---

## 3. Risiken / Lücken

### R-N1 [CRITICAL] Vier alternative Renderer DEAD CODE, keine Auswahl-Logik

`render_router._execute_render:442` instanziert **nur** `RenderService`.
`BatchRenderer` (Windows-8191-Limit-Schutz, Chunk-30), `RenderEngine`,
`VideoRenderer`, `PreviewGenerator`, `ProxyService` werden NIRGENDWO vom
Backend aufgerufen.

```
Grep "BatchRenderer|RenderEngine|VideoRenderer|PreviewGenerator|ProxyService"
in backend/ → 0 Hits
```

**Auswirkung:**
- Timelines > ~250 Clips werden vom Concat-Demuxer-Listenpfad mit
  riesiger `concat_list.txt` befüllt; das ist OK weil Windows-Limit
  greift bei argv (cmd.exe), nicht beim Konkatenations-File. **Aber**
  der Schutz-Renderer (`BatchRenderer.CHUNK_SIZE=30`) ist nie aktiv.
- Es gibt keinen Preview-Render-Endpoint (kein
  `POST /render/preview`) → User kann keine 90s-Preview erzeugen
  obwohl `PreviewGenerator` voll implementiert ist.
- Es gibt keinen Proxy-Service-Endpoint → bei 4K-Quellen läuft der
  finale Render auf Originalauflösung mit 4K-Re-Encode statt 1080p-Proxy.
- `RenderQuality.PREVIEW = "preview"` (720p) im Schema (`render_schemas.py:11`)
  wird nirgendwo gelesen (`Grep request.quality` → 0 funktionale Hits;
  nur in den Settings-Dict für Queue-Persistenz `:77`). Der UI-Toggle
  hat keinen Effekt.

**Fix-Optionen:** entweder die toten Module entfernen (DEAD-CODE-Cleanup)
oder Preview/Proxy-Endpoints aktivieren und `RenderQuality.PREVIEW`
durchschalten.

---

### R-N2 [HIGH] Bitrate aus Request wird ignoriert für Normalisierungs-Transcodes

`render_router._execute_render:447` baut `bitrate = f"{request.bitrate_mbps:.0f}M"` 
und reicht ihn an `service.render_timeline(bitrate=...)`. Im finalen
FFmpeg-Aufruf wird `bitrate` korrekt verwendet (`render_service.py:394-399`).

**Aber** im Normalisierungs-Pfad (`_transcode_clip:271-302`) ist die
Bitrate hardcoded auf `12M` für AMF, unabhängig vom Request:

```python
if encoder == "hevc_amf":
    enc_args = ["-c:v", "hevc_amf", "-quality", "balanced", "-b:v", "12M"]
```

Auswirkung: User mit `bitrate_mbps=50` (Ultra-Setting) bekommt seine
normalisierten Clips trotzdem mit 12M re-encodiert → der spätere finale
Concat von normalisierten Clips läuft auf 50M Container, aber das
Material wurde schon auf 12M qualitäts-clippt. Final-Quality < Request.

Außerdem: `_transcode_clip` setzt **kein** `-maxrate`/`-bufsize` und
**kein** `-rc vbr_peak` — anders als `video_renderer._get_encode_params`,
das `-rc vbr_peak` korrekt setzt. AMF ohne `-rc` Wahl nimmt CQP-Default,
ignoriert `-b:v` teilweise.

---

### R-N3 [HIGH] Bitrate-Mapping ohne maxrate/bufsize → AMF läuft im CQP-Mode

`render_service._run_ffmpeg_render:393-405`:

```python
if encoder == "hevc_amf":
    cmd.extend(["-c:v", "hevc_amf", "-quality", preset, "-b:v", bitrate])
```

Fehlt: `-rc vbr_peak` (oder `cbr`/`vbr_latency`) **und** `-maxrate`+`-bufsize`.
AMF-Treiber default rate-control ist `cqp` (constant quantizer) — das
ignoriert `-b:v` größtenteils und produziert unkontrollierte File-Größen.
`video_renderer.py:52-64` macht es richtig (`-rc vbr_peak`), aber der
ist nicht im aktiven Pfad (R-N1).

**Auswirkung:** Der UI-Bitrate-Slider hat geringen Effekt auf die
Output-Größe; AMD-AMF entscheidet selbst über die Quantisierung. L-N5
"`f"{:.0f}M"` korrekt?" Antwort: Format ja, Wirkung nein.

---

### R-N4 [HIGH] `preset`-Parameter im Final-FFmpeg ignoriert Request.quality

`render_router._execute_render` reicht **keinen** `preset` an `render_timeline`
weiter. `RenderService.render_timeline:116` hat Default `preset="balanced"`.
`request.quality` (PREVIEW/STANDARD/HIGH/ULTRA) wird **nur** in das
Queue-Settings-Dict geschrieben (`render_router.py:77`), aber nicht in
`-quality {preset}` mapped. Heißt: Quality-Enum hat 0 Wirkung auf
FFmpeg-AMF-Parameter.

Identische Lücke für `resolution_width/height`: ULTRA solle 4K sein
(`render_schemas.py:14`), aber `request.resolution_width=1920` Default
wird einfach unverändert genutzt. Keine Mapping-Logik.

**Auswirkung:** `RenderQuality` ist ein UI-Cosmetic-Feld; alle 4 Levels
produzieren identische Encoder-Parameter.

---

### R-N5 [MEDIUM] `output_path` Validation hardcoded gegen Projekt-Root

`render_router.py:121-125` (SEC-002):

```python
output_p_check = Path(request.output_path).resolve()
allowed_render = resolve_active_project_root(state, config.project_dir)
if not output_p_check.is_relative_to(allowed_render):
    raise HTTPException(status_code=403, ...)
```

Der User kann nicht in `~/Desktop/render.mp4` oder einen externen Ordner
exportieren — alle Renders müssen im Projekt-Root liegen. Für ein
Production-Studio-Tool ist das eine harte Friktion. UI-seitig fehlt
ein Dialog, der den Pfad in die erlaubte Zone klemmt.

Andererseits ist `Path.is_relative_to` Windows-symlink-blind: wenn ein
Symlink innerhalb des Projekts auf eine externe Location zeigt, geht
das Render dorthin — `resolve()` followed den Symlink, aber
`is_relative_to` vergleicht nur den resolveten Pfad. Kein konkreter
Exploit aber Edge-Case.

---

### R-N6 [MEDIUM] Drei separate Encoder-Detection-Implementierungen, divergent

- `RenderService._detect_best_encoder:73-105` testet via
  `ffmpeg -c:v {enc} -f null -` (echter Encode-Lauf).
- `BatchRenderer._detect_encoder:55-70` macht identisches Schema, aber
  ohne `av1_amf` und ohne `libx265`.
- `ProxyService._detect_encoder:37-55` testet nur `h264_amf, h264_mf, libx264`.
- `RenderEngine._detect_encoder:64-93` testet **nicht** echt — nur
  String-Match in `ffmpeg -encoders` Output. `hevc_amf` taucht in
  jedem FFmpeg-Build mit `--enable-amf` auf, **auch wenn die AMD-Karte
  fehlt**. Das produziert `AMF_ERROR_NO_DEVICE` zur Render-Laufzeit
  statt zur Detect-Zeit.

L-N6 "`encoder_override` None → backend default vs libx264 → CPU":
`render_router.py:452-453` macht das richtig (`None` → kein Override
→ Default `_working_encoder`; explizit `libx264` → CPU). Aber der
`_working_encoder` ist beim ersten Import **process-global cached**
(`render_service.py:58-71`), nie invalidiert. Tauscht der User die GPU
oder updatet den Treiber zur Laufzeit → stale Encoder.

---

### R-N7 [MEDIUM] Audio-Offset nur einseitig im Final-Renderer

`render_service._run_ffmpeg_render:386-389`:

```python
if audio_offset > 0:
    cmd.extend(["-ss", f"{audio_offset:.3f}", "-i", audio_path])
else:
    cmd.extend(["-i", audio_path])
```

`render_router._execute_render` reicht aber **nie** einen `audio_offset`
durch (siehe `:559-569`, kein `audio_offset`-Kwarg). Defaults zu 0.0.
Das Feature ist im Service implementiert aber im Router tot.

`RenderRequest`-Schema hat **kein** `audio_offset` Field. Wenn ein User
in der UI den Audio-Start-Offset setzt (z.B. "Audio startet erst nach
Intro"), wird das nicht persistiert oder übertragen.

---

### R-N8 [MEDIUM] FFmpeg-Process: kein `nice`/`priority`, kein Memory-Cap

Final-FFmpeg läuft mit Default-Priority. Bei einem 4K-AV1-Render saugt
das die ganze GPU + CPU; während gleichzeitig das WPF-Frontend
SSE-Updates rendert. Bei langen Renders blockiert der einzige `gpu_lock`
**alle** anderen GPU-Tasks (Audio-Analyse, RAFT-Motion, SigLIP-Embed,
Brain-Inference) für die Render-Dauer. Kein Lock-Timeout sichtbar in
`with_gpu_task` für Renders, der Lock ist über `async with gpu_lock`
direkt.

`_run_ffmpeg_render:436` setzt `process.wait(timeout=60)` aber das ist
nur die Cleanup-Wait nach EOF. Effektiv kann ein hängender FFmpeg
unbegrenzt im Lock sitzen. (`RenderEngine` hat `timeout=3600`,
`BatchRenderer` 3600 — `RenderService` aber **keinen** Hard-Timeout
auf den Render selbst.)

---

### R-N9 [MEDIUM] Concat-Demuxer + AMF: keine Re-Encode-Boundary-Synchronisation

`render_service._run_ffmpeg_render:379-384`:

```python
cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
       "-segment_time_metadata", "1", "-i", str(list_path)]
```

Concat-Demuxer mit `inpoint`/`outpoint` verlangt, dass alle Inputs
**identische Codec-Parameter** haben (cfr, codec, pix_fmt, timebase).
`_normalize_clips` prüft nur `width/height/fps` (`:247-269`), nicht
`pix_fmt` (yuv420p vs nv12 vs yuv444), nicht `color_primaries`, nicht
`field_order`. Mischmedien mit gleichem `1920x1080@30` aber
unterschiedlichem pix_fmt führen zu Re-Encode-Artefakten.

`-segment_time_metadata 1` ist gesetzt, gut. Aber `_transcode_clip:280`
fehlt `-pix_fmt yuv420p` Forcing (vorhanden nur in `BatchRenderer:206`
und `preview_renderer:123`). Heißt: Normalisierte Clips könnten ein
abweichendes pix_fmt erben → AMF kann beim Concat-Pass Artefakte
produzieren.

---

### R-N10 [LOW] Container-Codec-Mismatch nicht geprüft

`render_schemas.py` hat keine Container-Validierung. User kann
`output_path=foo.mkv` mit `encoder=hevc_amf` setzen → `+faststart`
ist MKV nicht relevant, aber FFmpeg akzeptiert. Wenn User
`output_path=foo.webm` + `encoder=h264_amf` schickt → WebM braucht
VP8/VP9/AV1, H.264 schlägt fehl. Keine Pre-Validation.

---

### R-N11 [LOW] Progress-Parser: `\r\n` vs `\n` Drift

`render_service.enqueue_stderr:472-491` liest char-by-char und splittet
auf `'\r'` ODER `'\n'`. Windows-FFmpeg sendet `\r` als
Progress-Update-Trenner. OK. Aber bei jeder normalen Log-Zeile kommt
`\r\n` → zwei Tokens in der Queue (eines leer). Die `time_pattern`
Regex matcht nichts auf leeren Strings, also harmlos — verursacht
aber zusätzliche `queue.put` Calls und ist verschwenderisch in Loop-Time.

---

### R-N12 [LOW] BatchRenderer und RenderEngine concat-list verwenden doppelte Anführungszeichen

`final_renderer._concatenate_chunks:236-237`:

```python
safe_path = str(chunk_file.absolute()).replace("\\", "/")
f.write(f'file "{safe_path}"\n')
```

FFmpeg concat-Demuxer erwartet **single quotes** (BUG-069 Fix in
`render_service.py:361`). Mit double quotes interpretiert FFmpeg den
Inhalt als literal — bei Pfaden ohne Sonderzeichen funktioniert das,
weil `-safe 0` "alles erlauben" setzt; aber sobald ein Apostrophe im
Pfad ist (z.B. `D'David/clips`) bricht es. Inkonsistent zum Rest der
Codebase.

---

### R-N13 [LOW] Concat-File für Chunks im `temp_dir` race-sicher, aber nicht atomic

`final_renderer._render_chunk:169` baut `concat_file` mit `time.time()*1000`
ms-Suffix. Zwei parallele BatchRenderer im selben ms (kein
Hardware-Render-Lock, der das aktuell ausschließt) → Kollision.
Aktuell durch sequentielle Chunk-Schleife im selben Prozess gewährleistet,
aber bei zukünftigem Parallelisieren broken.

---

### R-N14 [INFO] RenderQueue-Resume-Pfad nicht im Audit-Scope verifiziert

`render_queue.restore_running_as_interrupted:352-391` markiert `running`
→ `interrupted`. Im Backend-Lifespan müsste das gerufen werden — habe
in `backend/main.py` nicht geprüft, da Scope. Falls Lifespan diesen
Call vergisst, bleibt der Job auf `running` nach Restart → Worker
liest `list_pending()` (`RESTARTABLE_STATES = {QUEUED, INTERRUPTED}`)
→ findet ihn nicht → Job verschwindet aus der Worker-Sicht aber bleibt
in der DB. Empfehlung: Verifikation, dass `restore_running_as_interrupted`
im Lifespan-Startup tatsächlich gerufen wird.

---

### R-N15 [INFO] preview_renderer: concat: Protokoll vs concat-Demuxer

`preview_renderer:139-148` nutzt `-i "concat:seg1.ts|seg2.ts"`
(concat-PROTOCOL, nicht demuxer). Funktioniert nur für mpegts/MP3 — OK,
weil Inputs `.ts` sind. Aber kein `-vsync cfr`/`setpts` Reset nach dem
ersten Pass — segments wurden mit `setpts=PTS-STARTPTS` re-timestamped,
aber zwischen ihnen kann Drift entstehen bei 23.976fps Source und
30fps Target.

---

## 4. Total-Count

| Severity | Anzahl |
|---|---|
| CRITICAL | 1 |
| HIGH | 3 |
| MEDIUM | 5 |
| LOW | 4 |
| INFO | 2 |
| **TOTAL** | **15** |

---

## 5. Report (Summary)

**Pipeline funktioniert für den Happy-Path** (`hevc_amf`, 1080p@30,
12 Mbps Default, sauberer Timeline-Snapshot), aber das Subsystem ist
**unterspezifiziert** und **mit DEAD-CODE durchsetzt**.

Top-5-Findings:

1. **R-N1 CRITICAL** — vier alternative Renderer (`BatchRenderer`,
   `RenderEngine`, `VideoRenderer`, `PreviewGenerator`, `ProxyService`)
   sind voll implementiert aber vom Router nirgends aufgerufen. Kein
   `/render/preview`-Endpoint, kein Proxy-Pass für 4K-Quellen, kein
   Chunk-30-Schutz bei riesigen Timelines. `RenderQuality.PREVIEW`
   ist ein totes Enum.
2. **R-N2 HIGH** — `request.bitrate_mbps` wirkt nur auf den finalen
   Encode; Normalisierungs-Transcodes laufen hartkodiert auf 12M
   unabhängig vom Request → finale Quality < Request bei High/Ultra.
3. **R-N3 HIGH** — AMF-Bitrate ohne `-rc vbr_peak`/`-maxrate`/`-bufsize`
   → Treiber-Default cqp ignoriert `-b:v` weitgehend, File-Größen
   unkontrolliert. `video_renderer.py` macht es richtig, ist aber tot.
4. **R-N4 HIGH** — `request.quality` (4 Enum-Levels) hat 0 Wirkung;
   wird nur in das Queue-Settings-Dict für Idempotenz geschrieben,
   nicht in `-quality` oder Auflösungs-Mapping übersetzt.
5. **R-N6 MEDIUM** — vier divergente Encoder-Detection-Funktionen,
   `RenderEngine` testet nur String-Match in `ffmpeg -encoders` (nicht
   echter Lauf) → False-Positive bei AMD-AMF-FFmpeg-Build ohne GPU.

15 Findings gesamt. Pre-Render-Validation L-TI-5 strict greift korrekt.
Path-Traversal-Schutz greift. Cancel + Cleanup mit mtime-Guard sind
robust. Queue-Persistence solide.

