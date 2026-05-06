# PB Studio — QA Gesamt-Report

**Datum:** 2026-03-29 (Update)
**Backend:** FastAPI auf Port 8765
**GPU:** AMD Radeon RX 7800 XT (16GB VRAM, DirectML)
**Test-Modus:** API-Tests (httpx gegen laufendes Backend)
**Testdaten:** Echte Audio/Video-Dateien (60s WAV, 2x MP4 1280x720)

---

## Zusammenfassung

| Metrik | Wert |
|--------|------|
| Funktionen getestet | 43 |
| Sofort bestanden | 41 |
| Nach Fix bestanden | 2 |
| Bugs gefunden | 3 (1 KRITISCH, 2 MITTEL) |
| Fixes angewandt | 5 (3 Code, 1 Debug, 1 Test) |
| pytest Suite | 187 passed, 9 skipped, 0 failures |

**Ergebnis: 43/43 PASS**

---

## Bereiche

### Bereich 1: Health & System (3/3 PASS)
- Health-Check, GPU-Status (RX 7800 XT, 16GB), GPU-Cleanup

### Bereich 2: Projekt-Management (5/5 PASS)
- Create, Info, Save, Close, Open — alle korrekt

### Bereich 3: Audio-Import & Bibliothek (2/2 PASS)
- Import (WAV 60s, 48kHz, Stereo), Clip-Liste

### Bereich 4: Audio-Analyse (5/5 PASS)
- Analyze: BPM=123, Key=E minor, 122 Beats, 3 Struktur-Segmente
- Beats, Waveform (3-Band, 61KB), Struktur, Spektral (344KB)

### Bereich 5: Video-Import & Bibliothek (2/2 PASS)
- Import (2x MP4, 1280x720@30fps), Clip-Liste

### Bereich 6: Video-Analyse (4/4 PASS)
- Analyze (Motion=18.6), Thumbnail (12.7KB JPEG), Szenen, Motion-Daten

### Bereich 7: Pacing & Director (2/2 PASS)
- Cutlist (31 Cuts, 60s), Timeline abrufbar

### Bereich 8: Rendering (3/3 PASS nach Fix)
- Render (h264_amf, 640x360, 30fps) bis completion, Status-Polling, Cancel

### Bereich 9: SSE Events (3/3 PASS)
- GPU-Stream, Progress-Stream, Log-Stream

### Bereich 10: Persistenz (4/4 PASS)
- Close/Reopen, Audio-Clips persistent, Video-Clips persistent

### Bereich 11: Edge Cases (4/4 PASS nach Fix)
- Invalid Clip-ID (404), Path-Traversal (400), Empty Body (422), Missing File (404)

---

## Bugs gefunden & gefixt

### BUG-048: FFmpeg Concat Quoting (KRITISCH)

| Feld | Wert |
|------|------|
| **Datei** | `src/pb_studio/rendering/render_service.py` Zeile 349-350 |
| **Root Cause** | FFmpeg concat protocol behandelt `"` als Teil des Dateinamens, nicht als Delimiter |
| **Symptom** | Render scheitert bei 58% wenn Clips normalisiert werden (Resolution-Mismatch) |
| **Fix** | `file "path"` → `file 'path'` (FFmpeg-Standard mit single quotes) |
| **Warum vorher unentdeckt** | Nur ausgeloest bei Normalisierung (Quell != Ziel-Resolution) |

### BUG-049: Path-Traversal Audio-Import (MITTEL)

| Feld | Wert |
|------|------|
| **Datei** | `backend/routers/audio_router.py` Zeile 66 |
| **Root Cause** | Kein SEC-001 Schutz, relative Pfade loesen PermissionError → 500 aus |
| **Fix** | `is_absolute()` Check + PermissionError Handler → HTTP 400 |

### BUG-050: Path-Traversal Video-Import (MITTEL)

| Feld | Wert |
|------|------|
| **Datei** | `backend/routers/video_router.py` Zeile 52 |
| **Root Cause** | Gleicher fehlender SEC-001 Schutz |
| **Fix** | `is_absolute()` Check + PermissionError Handler |

---

## Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `src/pb_studio/rendering/render_service.py` | Single-Quote Concat + stderr tail statt head |
| `backend/routers/audio_router.py` | SEC-001 absolute-path Guard |
| `backend/routers/video_router.py` | SEC-001 absolute-path Guard |
| `Tests/test_backend_routers.py` | Windows-Pfad in Test + neuer relativer-Pfad-Test |

---

## Bereinigung

- 2 AutoQA-Projekte geloescht
- 7 Temp-Dateien + 1 Cache-Verzeichnis bereinigt

---

## Historie

| Datum | Tests | Pass | Bugs |
|-------|-------|------|------|
| 2026-03-09 | 30 | 29/30 | BUG-STEM-001 |
| 2026-03-16 | 29 | 29/29 | 0 |
| 2026-03-29 | 43 | 43/43 | BUG-048/049/050 |

---

## Stem-Separation E2E (3/3 PASS)
- DirectML GPU: 26s fuer 60s Audio
- Vocals WAV: 10.1MB, Instrumental WAV: 10.1MB
- Model: UVR-MDX-NET-Inst_HQ_3.onnx

## Pacing Preview E2E (3/3 PASS)
- Preview 640x360, 10s: 5.8MB MP4
- Offset-Preview (start=30s, dur=5s): 3.6MB
- No-Timeline-Guard: 400 korrekt
