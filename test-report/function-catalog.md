# PB Studio — Funktionskatalog (Auto-QA-Loop)

Erstellt: 2026-03-09 | Getestet: 2026-03-09

---

## Bereich 1: Projekt-Management
- [x] F-1.1: Projekt erstellen (`POST /project/create`) ✅
- [x] F-1.2: Projekt öffnen (`POST /project/open`) ✅
- [x] F-1.3: Projekt speichern (`POST /project/save`) ✅
- [x] F-1.4: Projekt schließen (`POST /project/close`) ✅
- [x] F-1.5: Projekt-Info abrufen (`GET /project/info`) ✅

## Bereich 2: Health & GPU
- [x] F-2.1: Health-Check (`GET /health`) ✅
- [x] F-2.2: GPU-Status (`GET /gpu/status`) ✅
- [x] F-2.3: GPU-Cleanup (`POST /gpu/cleanup`) ✅

## Bereich 3: Audio-Import & Bibliothek
- [x] F-3.1: Audio-Datei importieren (`POST /audio/import`) ✅
- [x] F-3.2: Audio-Clips auflisten (`GET /audio/clips`) ✅

## Bereich 4: Audio-Analyse
- [x] F-4.1: Audio analysieren — BPM/Beats (`POST /audio/analyze`) ✅
- [x] F-4.2: Beat-Daten abrufen (`GET /audio/beats/{clip_id}`) ✅
- [x] F-4.3: Waveform abrufen (`GET /audio/waveform/{clip_id}`) ✅
- [x] F-4.4: Struktur abrufen (`GET /audio/structure/{clip_id}`) ✅
- [x] F-4.5: Spektral-Daten abrufen (`GET /audio/spectral/{clip_id}`) ✅
- [x] F-4.6: Stem-Separation starten (`POST /audio/stems/separate`) ✅ (nach Fix BUG-STEM-001)

## Bereich 5: Video-Import & Bibliothek
- [x] F-5.1: Video-Dateien importieren (`POST /video/import`) ✅
- [x] F-5.2: Video-Clips auflisten (`GET /video/clips`) ✅
- [x] F-5.3: Thumbnail abrufen (`GET /video/thumbnails/{clip_id}`) ✅

## Bereich 6: Video-Analyse
- [x] F-6.1: Video analysieren (`POST /video/analyze`) ✅
- [x] F-6.2: Szenen abrufen (`GET /video/scenes/{clip_id}`) ✅
- [x] F-6.3: Motion-Daten abrufen (`GET /video/motion/{clip_id}`) ✅

## Bereich 7: Pacing & Director
- [x] F-7.1: Cut-Liste generieren (`POST /pacing/generate`) ✅
- [x] F-7.2: Timeline abrufen (`GET /pacing/timeline`) ✅
- [x] F-7.3: Preview generieren (`POST /pacing/preview`) ✅

## Bereich 8: Rendering
- [x] F-8.1: Render starten (`POST /render/start`) ✅
- [x] F-8.2: Render-Status abrufen (`GET /render/status/{task_id}`) ✅
- [x] F-8.3: Render abbrechen (`POST /render/cancel/{task_id}`) ✅

## Bereich 9: SSE Events
- [x] F-9.1: Progress-Stream (`GET /events/progress`) ✅
- [x] F-9.2: Log-Stream (`GET /events/log`) ✅
- [x] F-9.3: GPU-Stream (`GET /events/gpu`) ✅

## Bereich 10: Shutdown
- [ ] F-10.1: Graceful Shutdown (`POST /shutdown`) ⏭️ SKIP

---

**Gesamt: 30 Funktionen** in 10 Bereichen
**Ergebnis: 29 PASS | 0 FAIL | 1 SKIP | 1 Fix angewandt**
