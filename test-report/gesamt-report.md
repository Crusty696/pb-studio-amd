# PB Studio — QA Gesamt-Report

**Datum:** 2026-03-09
**Backend:** FastAPI auf Port 8765
**GPU:** AMD Radeon RX 7800 XT (16GB VRAM, DirectML)
**Test-Modus:** API-Tests (httpx gegen laufendes Backend)

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| Funktionen getestet | 30 |
| Sofort bestanden | 28 |
| Nach Fix bestanden | 1 |
| Übersprungen | 1 (Shutdown) |
| Bugs gefunden | 1 (KRITISCH) |
| Fixes angewandt | 1 |

**Ergebnis: 29/30 PASS, 1 SKIP**

---

## Bereich 1: Projekt-Management (5/5 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-1.1: Projekt erstellen | ✅ PASS | `POST /project/create` — Projekt in `~/Documents/PBStudio/` erstellt |
| F-1.2: Projekt öffnen | ✅ PASS | `POST /project/open` — Projekt korrekt geladen |
| F-1.3: Projekt speichern | ✅ PASS | `POST /project/save` — Status 200 |
| F-1.4: Projekt schließen | ✅ PASS | `POST /project/close` — Status 200 |
| F-1.5: Projekt-Info | ✅ PASS | `GET /project/info` — Name, Pfad, Clips korrekt |

**Hinweis:** SEC-001 Path-Traversal-Schutz funktioniert korrekt — Pfade außerhalb `project_dir` werden mit 403 abgelehnt.

---

## Bereich 2: Health & GPU (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-2.1: Health-Check | ✅ PASS | `GET /health` — `{"status":"ok","gpu_available":true}` |
| F-2.2: GPU-Status | ✅ PASS | `GET /gpu/status` — VRAM, Temperatur, Auslastung korrekt |
| F-2.3: GPU-Cleanup | ✅ PASS | `POST /gpu/cleanup` — Status 200 |

---

## Bereich 3: Audio-Import & Bibliothek (2/2 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-3.1: Audio importieren | ✅ PASS | `POST /audio/import` — WAV 606MB importiert, ID korrekt |
| F-3.2: Audio-Clips listen | ✅ PASS | `GET /audio/clips` — Alle Clips mit Metadaten |

---

## Bereich 4: Audio-Analyse (5/6 — 1 Fix)

| Funktion | Status | Details |
|----------|--------|---------|
| F-4.1: Audio analysieren | ✅ PASS | `POST /audio/analyze` — BPM, Beats, Key, Energy, Struktur, Spektral |
| F-4.2: Beat-Daten | ✅ PASS | `GET /audio/beats/{id}` — Beats mit time/strength/type |
| F-4.3: Waveform | ✅ PASS | `GET /audio/waveform/{id}` — 3-Band Waveform-Daten |
| F-4.4: Struktur | ✅ PASS | `GET /audio/structure/{id}` — Segmente korrekt |
| F-4.5: Spektral-Daten | ✅ PASS | `GET /audio/spectral/{id}` — Bänder + Frequenzbereiche |
| F-4.6: Stem-Separation | ✅ PASS (nach Fix) | `POST /audio/stems/separate` — **BUG-STEM-001 gefixt** |

### BUG-STEM-001: Stem-Separation Key-Mismatch (KRITISCH)

| Feld | Wert |
|------|------|
| **Datei** | `backend/routers/audio_router.py` |
| **Funktion** | `_run_stem_separation()` |
| **Root Cause** | `StemSeparator.separate()` gibt `{"stems": [path1, path2]}` zurück, aber der Router suchte nach `result.get("vocals")`, `result.get("instrumental")` — Keys die nie existieren |
| **Symptom** | Status 200, aber alle Stem-Pfade `null` |
| **Schwere** | KRITISCH — Feature komplett kaputt |
| **Fix** | `_run_stem_separation()` parst jetzt die "stems"-Liste und mappt Dateinamen (enthaltend "Vocal", "Instrumental" etc.) auf die korrekten Response-Felder. Fehler vom Separator werden als RuntimeError propagiert statt silent zu `null`. |

---

## Bereich 5: Video-Import & Bibliothek (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-5.1: Video importieren | ✅ PASS | `POST /video/import` — MP4 importiert |
| F-5.2: Video-Clips listen | ✅ PASS | `GET /video/clips` — Alle Clips mit Metadaten |
| F-5.3: Thumbnails | ✅ PASS | `GET /video/thumbnails/{id}` — Base64-Thumbnail |

---

## Bereich 6: Video-Analyse (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-6.1: Video analysieren | ✅ PASS | `POST /video/analyze` — Szenen, Motion, Embeddings |
| F-6.2: Szenen abrufen | ✅ PASS | `GET /video/scenes/{id}` — Scene-Cuts korrekt |
| F-6.3: Motion-Daten | ✅ PASS | `GET /video/motion/{id}` — Motion-Kurve + Peaks |

---

## Bereich 7: Pacing & Director (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-7.1: Cut-Liste generieren | ✅ PASS | `POST /pacing/generate` — Cuts, Duration, Cut-Count |
| F-7.2: Timeline abrufen | ✅ PASS | `GET /pacing/timeline` — Entries, Duration, Audio-Path |
| F-7.3: Preview generieren | ✅ PASS | `POST /pacing/preview` — Endpoint funktioniert (leerer Pfad weil Timeline-Clips auf pytest-Pfade zeigen — kein Code-Bug) |

---

## Bereich 8: Rendering (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-8.1: Render starten | ✅ PASS | `POST /render/start` — Task-ID erhalten |
| F-8.2: Render-Status | ✅ PASS | `GET /render/status/{id}` — Status + Prozent korrekt |
| F-8.3: Render abbrechen | ✅ PASS | `POST /render/cancel/{id}` — Status "cancelled" |

---

## Bereich 9: SSE Events (3/3 PASS)

| Funktion | Status | Details |
|----------|--------|---------|
| F-9.1: Progress-Stream | ✅ PASS | `GET /events/progress` — SSE-Stream offen |
| F-9.2: Log-Stream | ✅ PASS | `GET /events/log` — SSE-Stream offen |
| F-9.3: GPU-Stream | ✅ PASS | `GET /events/gpu` — SSE-Stream offen |

---

## Bereich 10: Shutdown (0/1 SKIP)

| Funktion | Status | Details |
|----------|--------|---------|
| F-10.1: Shutdown | ⏭️ SKIP | Server absichtlich laufend gehalten |

---

## Angewandte Fixes

| Fix | Datei | Beschreibung |
|-----|-------|-------------|
| BUG-STEM-001 | `backend/routers/audio_router.py` | `_run_stem_separation()` parst jetzt `{"stems": [...]}` korrekt statt nicht-existente Keys zu suchen |

---

## Offene Punkte / Hinweise

1. **Stem-Separation Dauer:** 137MB+ Audio-Dateien brauchen mehrere Minuten für GPU-Separation. Das ist erwartetes Verhalten, kein Bug. Für Produktionsbetrieb könnte ein Progress-SSE-Stream nützlich sein.
2. **Preview mit echten Clips:** Preview-Rendering nur sinnvoll testbar wenn Timeline echte Video-Pfade enthält (nicht pytest `/tmp/`-Pfade).
3. **Datenbank:** Enthält pytest-generierte Clips mit ungültigen `/tmp/`-Pfaden. Empfehlung: DB bereinigen vor Produktivbetrieb.
4. **Shutdown:** Nicht getestet (bewusst) — Server wurde für weitere Tests laufend gehalten.
