# PB Studio — Funktionskatalog (Auto-QA-Loop)

Erstellt: 2026-03-09 | Aktualisiert: 2026-03-29

---

## Bereich 1: Health & System
- [x] F-1.1: Health-Check (`GET /health`)
- [x] F-1.2: GPU-Status (`GET /gpu/status`)
- [x] F-1.3: GPU-Cleanup (`POST /gpu/cleanup`)

## Bereich 2: Projekt-Management
- [x] F-2.1: Projekt erstellen (`POST /project/create`)
- [x] F-2.2: Projekt-Info (`GET /project/info`)
- [x] F-2.3: Projekt speichern (`POST /project/save`)
- [x] F-2.4: Projekt schliessen (`POST /project/close`)
- [x] F-2.5: Projekt oeffnen (`POST /project/open`)

## Bereich 3: Audio-Import & Bibliothek
- [x] F-3.1: Audio-Datei importieren (`POST /audio/import`)
- [x] F-3.2: Audio-Clips auflisten (`GET /audio/clips`)

## Bereich 4: Audio-Analyse
- [x] F-4.1: Audio analysieren — BPM/Beats/Key/Struktur/Spektral (`POST /audio/analyze`)
- [x] F-4.2: Beat-Daten abrufen (`GET /audio/beats/{clip_id}`)
- [x] F-4.3: Waveform abrufen (`GET /audio/waveform/{clip_id}`)
- [x] F-4.4: Struktur abrufen (`GET /audio/structure/{clip_id}`)
- [x] F-4.5: Spektral-Daten abrufen (`GET /audio/spectral/{clip_id}`)

## Bereich 5: Video-Import & Bibliothek
- [x] F-5.1: Video-Dateien importieren (`POST /video/import`)
- [x] F-5.2: Video-Clips auflisten (`GET /video/clips`)

## Bereich 6: Video-Analyse
- [x] F-6.1: Video analysieren (`POST /video/analyze`)
- [x] F-6.2: Thumbnail abrufen (`GET /video/thumbnails/{clip_id}`)
- [x] F-6.3: Szenen abrufen (`GET /video/scenes/{clip_id}`)
- [x] F-6.4: Motion-Daten abrufen (`GET /video/motion/{clip_id}`)

## Bereich 7: Pacing & Director
- [x] F-7.1: Cut-Liste generieren (`POST /pacing/generate`)
- [x] F-7.2: Timeline abrufen (`GET /pacing/timeline`)

## Bereich 8: Rendering
- [x] F-8.1: Render starten (`POST /render/start`)
- [x] F-8.2: Render-Status (`GET /render/status/{task_id}`)
- [x] F-8.3: Render abbrechen (`POST /render/cancel/{task_id}`)

## Bereich 9: SSE Events
- [x] F-9.1: GPU-Stream (`GET /events/gpu`)
- [x] F-9.2: Progress-Stream (`GET /events/progress`)
- [x] F-9.3: Log-Stream (`GET /events/log`)

## Bereich 10: Persistenz
- [x] F-10.1: Projekt schliessen und wieder oeffnen
- [x] F-10.2: Audio-Clips persistieren nach Reopen
- [x] F-10.3: Video-Clips persistieren nach Reopen

## Bereich 11: Edge Cases / Sicherheit
- [x] F-11.1: Ungueltige Clip-ID (erwartet 404)
- [x] F-11.2: Path-Traversal-Versuch (erwartet 400)
- [x] F-11.3: Leerer Request-Body (erwartet 422)
- [x] F-11.4: Nicht-existierende Datei (erwartet 404)

## Bereich 12: Stem-Separation (3/3 PASS)
- [x] F-12.1: Stem-Separation (`POST /audio/stems/separate`) — 26s GPU, Vocals+Instrumental korrekt
- [x] F-12.2: Vocals-Datei existiert und >1KB
- [x] F-12.3: Instrumental-Datei existiert und >1KB

## Bereich 13: Pacing Preview (3/3 PASS)
- [x] F-13.1: Preview generieren (`POST /pacing/preview`) — 640x360, 10s, 6MB
- [x] F-13.2: Preview mit Offset (start=30s, dur=5s) — korrekt
- [x] F-13.3: Preview ohne Timeline (erwartet 400) — Guard funktioniert

## Bereich 14: Noch nicht getestet
- [ ] F-14.1: Graceful Shutdown (`POST /shutdown`)

---

**Gesamt: 43 Funktionen getestet** in 13 Bereichen + 1 ausstehend
**Ergebnis 2026-03-29: 43/43 PASS | 3 Bugs gefixt (BUG-048/049/050)**
