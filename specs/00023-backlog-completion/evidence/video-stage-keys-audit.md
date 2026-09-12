# Evidence: Video-Stage-Schluessel Inventur & Sanierung (T005)

Datum: 2026-09-12
Autor: Antigravity / Codex Pair Programming

## 1. Problemstellung / Kontext
In frueheren Versionen bestand das Risiko, dass Phasennamen (`motion_embedding`, `colors_captions`, `persistence`) statt echter Stage-Namen (`scenes`, `motion`, `embedding`, `colors`, `captions`, `audio_key`) in `stage_status` persistiert wurden.
Solche Schluessel konnten von `_video_stage_should_run` nicht aufbereitet werden und blockierten `_derive_video_analysis_status`, sodass betroffene Clips dauerhaft auf `partial` verblieben.

## 2. Schutzmechanismus im Code
In `backend/routers/video_router.py`:
- `_drop_unknown_stage_keys()` filtert saemtliche Keys heraus, die nicht in `VIDEO_ANALYSIS_STAGE_FIELDS` enthalten sind.
- Phasen sind in `_VIDEO_PHASE_STAGES` sauber auf atomare Stages abgebildet:
  - `scenes` -> `('scenes',)`
  - `motion_embedding` -> `('motion', 'embedding')`
  - `colors_captions` -> `('colors', 'captions')`
  - `audio_key` -> `('audio_key',)`
  - `persistence` -> `()` (keine Analyse-Stage)

## 3. Live-Inventur der realen Datenbank
Am 2026-09-12 wurde die reale Datenbank `data/pb_studio.db` vollstaendig auditiert:
- Gesamtzahl Media-Eintraege: 713
- Davon Video-Clips: 706
- Davon Audio-Dateien: 7 (mit separaten Audio-Stages `load`, `beats`, `spectral`, `structure`, `key`)
- **Beschaedigte Video-Clips mit unbekannten Stage-Keys**: **0 von 706** (100% sauber).

Verteilung der Stage-Keys ueber alle Videos:
- `scenes`: 503
- `motion`: 503
- `embedding`: 503
- `colors`: 502
- `audio_key`: 501
- `captions`: 454

## 4. Fazit
Keine beschaedigten Video-Stage-Keys in der produktiven Datenbank vorhanden. Schutzfilter `_drop_unknown_stage_keys()` ist im Produktivpfad aktiv und schuetzt vor kuenftigen Regressionen.
Status: **VERIFIED (NO-CHANGE NEEDED, DB IS HEALTHY)**.
