# MASTER AUDIT — Deep-Audit Sweep 2026-05-11

Konsolidiert 7 Domain-Audits (Audio, Video, Rendering, State+DB+Cache, Frontend, GPU+Threading, Timeline-Integrity) — 130+ Findings.

User-Direktive: tiefe Untersuchung. Bugs, kaputte Pipelines, falsche/unfertige Verdrahtungen, Daten-Weiterleitung. Read-only.

---

## 1. Audit-Files (alle committed)

| Domain | File | Findings | Commit |
|---|---|---|---|
| Timeline-Integrity | `AUDIT_TIMELINE_INTEGRITY_2026-05-11.md` | 12 (1 CRIT, 4 HIGH) | `5c21e51` |
| Rendering | `AUDIT_RENDERING_PIPELINE_2026-05-11.md` | 18-stage + R-N1..N6+ | `1709827` |
| Audio | `AUDIT_AUDIO_PIPELINE_2026-05-11.md` | 16 (2 CRIT, 3 HIGH) | `71bb926` |
| Video | `AUDIT_VIDEO_PIPELINE_2026-05-11.md` | 20 (5 HIGH) | `7846a75` |
| State+DB+Cache | `AUDIT_STATE_DB_CACHE_2026-05-11.md` | 17 (4 HIGH) | `33cdc5c` |
| Frontend-Wiring | `AUDIT_FRONTEND_WIRING_2026-05-11.md` | 33 (4 HIGH) | `6853f8b` |
| GPU+Threading | `AUDIT_GPU_THREADING_2026-05-11.md` | 12 (1 CRIT, 3 HIGH) | `8e10301` |

**Total:** ~130 Findings. ~4 CRITICAL, ~24 HIGH, plus MEDIUM/LOW/INFO.

---

## 2. Cross-Domain-Konvergenz (Same bug, multiple audits)

### CD-1 — `stems_paths` nicht persistiert
- **Audio L-AUDIO-8** + **State L-STATE-1**
- Demucs-Stems (10min GPU-Zeit) nur in `state.audio_clips[id]`, kein DB-Sync
- Nach Project-Close+Open: Stem-Pacing fällt silent zurück auf standard branch
- `persist_audio_clip.meta` + `load_from_db` kennen das Feld nicht
- (L-N4 hat UI-Layer + Detector-Side committed aber Persistierung wurde übersehen)

### CD-2 — FAISS-Index-Split
- **Video L-VIDEO-1** + **State L-STATE-3**
- `video_router.py:751` schreibt SigLIP nach `VectorStore("video_index")`
- `semantic_matcher.py:162` liest aus `VectorStore("main_index")`
- → Pacing-Semantic-Matching kann Video-Embeddings NIE nutzen
- Plus: VectorStore-Singleton invalidiert sich, atexit-Leak pro `__new__`

### CD-3 — `video_hash` nicht persistiert
- **Video L-VIDEO-3** + **State** (Drift zu Audio)
- `persist_video_clip` + `load_from_db` Video-Branch kennen `video_hash` nicht
- `repo.add_media` bekommt hardcoded `file_hash=""`
- EmbeddingCache-Hit-Rate 0% nach Restart
- L-N3 hat UI-Badge gebaut aber Backend-Persistierung war Annahme

### CD-4 — Subtrack/Tempo-Cache verloren beim Reload
- **Audio L-AUDIO-6** + **State** (load_from_db skip)
- Import schreibt ohne `is_analyzed=True`
- `load_from_db` skipped `is_analyzed=False`-Rows UND mapped Keys nicht
- L-K1 hat schreibt-Pfad gefixt aber Reload-Pfad bleibt broken

### CD-5 — Schema-Drift Pacing-Cache
- **State L-STATE-5** beats vs beats_json
- Nach Live-Analyse Cache-Key `beats_json`, nach DB-Reload `beats`
- `/audio/beats/{id}` liest `beats` → Fallback `[]` direkt nach Analyse

---

## 3. KRITISCHE Findings (sofort fix)

### M-1 [CRITICAL] — ModelLoader Eviction-Deadlock (GPU F1)
- `_session_lock` = `threading.Lock()` non-reentrant
- `load_model(force=True)` → `_evict_for_space` → re-acquire = Deadlock
- Mitigiert nur weil ModelLoader DEAD CODE im Hot-Path

### M-2 [CRITICAL] — StreamingAudioAnalyzer DEAD CODE (Audio L-AUDIO-1)
- Komplett gebaut + getestet + exportiert, aber `_run_audio_analysis` nutzt nicht
- DJ-Mixe (90min) komplett in RAM (~480MB peak) → OOM-Risiko Hauptzielgruppe
- L-F3 frühere Session hatte streaming-Komponente angelegt — aber nie wired

### M-3 [CRITICAL] — Subtrack-Cache geht beim Reload verloren (Audio L-AUDIO-6 / CD-4)

### M-4 [CRITICAL] — peak_motion silent dropped (Video L-VIDEO-2)
- `MotionData` Pydantic-Schema fehlt `peak_motion` Feld
- `MotionData(**motion)` macht silent-drop
- `/video/motion/{id}` REST + C# MotionData liefern peak_motion NIE
- L-K3 hat backend computation gefixt aber Schema-Forwarding broken

---

## 4. HIGH Findings (priorisiert)

### Audio (HIGH)
- L-AUDIO-4: SpectralAnalyzer `band_means`/`band_variances`/`_detect_events` verworfen im Mapping
- L-AUDIO-5: `_run_audio_analysis` befüllt `subtrack_segments`/`tempo_curve` nicht im Response
- L-AUDIO-8: stems_paths (siehe CD-1)

### Video (HIGH)
- L-VIDEO-4: 6 Schema-Felder ohne Producer (mood_tags, style_tags, object_tags, brightness/saturation/color_temp curves)
- L-VIDEO-5: `range(0, total - step, step)` letztes Sample fällt raus in Motion+Embedding-Loops

### State+DB (HIGH)
- L-STATE-2: `vector_map`-Tabelle DEAD SCHEMA (kein INSERT im Code) → Orphan-FAISS-Hits, unbegrenztes Wachstum
- L-STATE-4: Brain-State-Connection nicht freigegeben bei Project-Close → schreibt ins falsche Projekt

### Frontend (HIGH)
- L-FE-1: TimelineVM injiziert konkrete `ApiClient` statt `IApiClient` (Tests blockiert)
- L-FE-2: IApiClient fehlt `GetOnsetsAsync`
- L-FE-7: BrainVM + LearningSessionVM ohne `IDisposable` → Memory-Leak pro Dialog
- L-FE-13: Director ignoriert StemsPaths → UseStemPacing-Toggle BLIND
- L-FE-15: TimelineView abonniert `CompositionTarget.Rendering` ohne Unsubscribe → 60Hz CPU-Drain + echter Memory-Leak

### GPU+Threading (HIGH)
- F2: GPU-Lock hält für CPU-FFmpeg (L-K4 audio_key extract 30s) → blockt Stem/Render
- F3: Brain-Embedder (CLAP+SigLIP-2) umgehen VRAMBudgetManager — 1.1GB DML-VRAM unsichtbar
- F4: brain_router blockt Event-Loop (kein asyncio.to_thread)

### Rendering
- R-N1: 5 parallele Render-Strukturen (BatchRenderer, RenderEngine, PreviewGenerator, ProxyService, VideoRenderer) NICHT vom Router verdrahtet
- R-N2: AMD AMF nur teilweise parametrisiert

### IRON-Rule-Drift erkannt
- `siglip_wrapper.py:63` + `clap_wrapper.py:87`: explizit `CPUExecutionProvider` Fallback → verstößt §1 "AMD DirectML ONLY"
- torch-directml Brain-Embedder fallen silent auf CPU bei Init-Exception

---

## 5. User-Sichtbare Symptome ↔ Root-Cause-Map

| User-Symptom | Root-Cause Finding(s) |
|---|---|
| Stem-Pacing-Toggle "macht nichts" | L-FE-13 (Director ignoriert StemsPaths) + CD-1 (stems_paths nicht persistiert) |
| BPM/Subtracks weg nach Reload | CD-4 (Subtrack-Cache verloren) + L-STATE-5 (beats-key-drift) |
| Stems-Separation muss nach Restart erneut laufen | CD-1 + L-AUDIO-8 |
| Cache-Badge zeigt CACHED aber Analyse läuft erneut | CD-3 (video_hash null) + L-AUDIO-* (audio_hash analog) |
| App-CPU steigt nach Tab-Wechsel | L-FE-15 (CompositionTarget-Leak) |
| Pacing-Semantic-Matching wirkt nicht | CD-2 (FAISS-Index-Split) |
| Render-UI "frozen" während Audio-Analyse-FFmpeg | F2 (GPU-Lock hält für CPU-Arbeit) |
| Settings-Tab updated nicht nach Backend-Restart | L-FE-9 (BackendReadyMessage never fired) |
| Letzte Frames eines Videos ohne Analyse | L-VIDEO-5 (range-Bug) |
| MOTION-Card zeigt PEAK 0 | L-VIDEO-2 (peak_motion silent-drop in Schema) |

---

## 6. Empfehlungs-Pfad — Plan-Skeleton

### Phase X (CRITICAL fix, ~3-4h)
- X1: Fix L-VIDEO-2 — `MotionData` schema `peak_motion` field
- X2: Fix CD-1 — stems_paths in `persist_audio_clip` + `load_from_db`
- X3: Fix CD-2 — FAISS-Index-Split (entweder "main_index" überall ODER semantic_matcher liest video_index zusätzlich)
- X4: Fix CD-3 — video_hash in persist + load
- X5: Fix CD-4 — Subtrack/Tempo Reload-Pfad fixen
- X6: Fix L-FE-13 — Director StemsPaths-Wiring zum UseStemPacing-toggle

### Phase Y (HIGH-impact UX, ~4-6h)
- Y1: L-FE-15 CompositionTarget unsubscribe
- Y2: L-FE-7 Brain/LearningSession IDisposable
- Y3: F2 GPU-Lock NICHT für CPU-FFmpeg (release vor subprocess.run)
- Y4: L-AUDIO-1 StreamingAnalyzer verkabeln (oder explizit deprecate)
- Y5: L-VIDEO-5 range-Bug korrekt schließen
- Y6: L-STATE-2 vector_map nutzen oder löschen
- Y7: L-STATE-4 Brain-Connection bei Project-Close reset

### Phase Z (HIGH-impact backend, ~2-3h)
- Z1: F3 Brain-Embedder bei VRAMBudgetManager registrieren
- Z2: F4 brain_router asyncio.to_thread
- Z3: M-1 ModelLoader RLock oder DEAD-CODE-removal
- Z4: L-AUDIO-4 SpectralAnalyzer band_means/variances forwarden
- Z5: L-AUDIO-5 _run_audio_analysis subtrack/tempo Response-fill
- Z6: L-VIDEO-4 6 leere Schema-Felder entweder fill oder remove

### IRON-Rule-Compliance (separate)
- IRC-1: siglip_wrapper + clap_wrapper CPUExecutionProvider entfernen
- IRC-2: torch-directml silent-CPU-fallback entfernen

---

## 7. Test-Status

- **Aktueller Stand:** 503 passed / 8 skipped / 0 failed (Session 2026-05-11)
- **Erwarteter Stand nach Phase X+Y+Z:** ~530+ Tests (jeder Fix bringt eigene Regression-Tests)

---

## 8. Methodik-Vermerk

- 6 parallele Subagents (read-only)
- ~3500 Files gescannt
- ~140 Findings aggregated
- 1 vorheriger Audit (Timeline-Integrity 2026-05-11) bereits in TI-1..TI-7 abgearbeitet (commits 700fedd..adfe28a)

**User-Direktive 2026-05-11 erfüllt:** tiefe Untersuchung jede Funktion / jeder Speicher / jeder Zwischenspeicher / Daten-Weiterleitung. Read-only, NICHT in Source modifiziert.

**Nächster Schritt:** User-Decision welche Phase (X / Y / Z) zuerst — oder neuer Plan via `/plan`.
