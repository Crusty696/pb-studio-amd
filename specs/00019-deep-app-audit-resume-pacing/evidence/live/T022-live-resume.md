# T022 Live API, Unterbruch und Resume

**Datum:** 2026-08-09
**Projekt:** `C:\Users\david\Documents\PBStudio\obj74_qc_20260809_001`
**Medien:** ausschließlich `C:\Users\david\Videos\test_data\audio` und `C:\Users\david\Videos\test_data\video`

## Audio Teilanalyse

- Quelle: `test_30s.wav`, Clip 2.
- Lauf 1: nur Beats; `beats=completed`, 57 Beats.
- Lauf 2: Beats + Struktur + Spektral + Key ohne `force`.
- Ergebnis: `beats/structure/spectral/key=completed`, Beats und BPM wertgleich bewahrt, 1 Struktursegment, 2584 Spektralpunkte, Key `F minor`.

## Video Backend-Neustart

- Quelle: `test_12s.mp4`, Clip 3.
- Analyse gestartet; nach 3 Sekunden owner-autorisierter `POST /shutdown`.
- Shutdown drainte die projektgebundene Analyse vor Prozessende.
- Nach Backend-Neustart und `POST /project/open`: `analysis_status=partial`, `scenes=completed`, `motion=interrupted`, `embedding=interrupted`.
- Retry mit identischem Request und `force=false`: Szenen wertgleich bewahrt; nur fehlende Stages fortgesetzt.
- Endstand: `scenes/motion/embedding/colors/audio_key=completed`, 23 Motion-Samples, SigLIP-Dimension 1152 mit 3 Samples, 5 Farben, Key `G major`.

## Projektwechsel-HTTP

- Vor Fix lieferte ein Lifecycle-Abbruch `500 No response returned`; Rohlogs liegen in `backend-before-lifecycle-fix.*.log`.
- Nach Fix: paralleles `POST /video/analyze` + `POST /project/close` liefert Analyse HTTP 409 und Close HTTP 200.
- Externe Cancellation bei weiterhin gültigem Projektkontext wird laut fokussiertem Vertrag weiterhin als `CancelledError` propagiert.

## Ergebnis

PASS: echte Medien, Teilretry, Backend-Shutdown, persistiertes `interrupted`, Restart und gezielte Fortsetzung belegt. Das isolierte Testprojekt wurde nicht gelöscht.
