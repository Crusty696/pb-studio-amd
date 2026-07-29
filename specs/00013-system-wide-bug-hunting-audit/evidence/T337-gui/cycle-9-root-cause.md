# T337 Cycle 9 — Router-Timeline-Finalisierung

Status: CONFIRMED

## Reproducer

Der reale Release-GUI-/Backend-Pfad startete Queue-Job
`851b5ccf-7f73-4866-8bd9-6e3845d512fd`, Render-Run
`94597ffd0b0b469aabf179287560494e`, H.264 AMF, 1.280×720,
30 fps und vollständiges Audioziel 6.335,027 s.

FFmpeg beendete mit Exitcode 0 und `progress=end`, erzeugte aber nur
189.948 statt 190.051 Frames und erreichte `out_time=6331.566667`.
Der Fail-closed-Validator verweigerte die Veröffentlichung und entfernte
das Staging-Artefakt. Der Zielpfad blieb abwesend.

## Root Cause und Datenfluss

1. `POST /render/start` fror die aktuelle Timeline korrekt als isolierten
   Queue-Snapshot ein.
2. `_execute_render` übergab diesen Snapshot nach Medienprüfung und
   Audioprobe direkt an `RenderService`.
3. Der gespeicherte Snapshot begann bei 1,9272562358276644 s. Seine
   Clipdauer summierte sich auf 6.333,099743764173 s.
4. Die erfolgreichen T335/T336-Runner hatten vor dem Rendern den bestehenden
   Architekturvertrag `PacingService._finalize_cut_list(..., 6335.027)`
   angewendet. Der produktive Router-Caller tat dies nicht.
5. Die unabhängige Gegenrechnung in
   `cycle-9-frame-gap-analysis.json` reproduziert exakt:
   ungefixt 189.973 Framefenster gegenüber 190.030 nach kanonischer
   Finalisierung; der korrigierte Snapshot reicht lückenlos von 0 bis
   6.335,027 s und entspricht den T335-Grenzmetriken.

## Architekturvertrag und Fix

`backend/routers/render_router.py::_finalize_timeline_for_render` kopiert
den isolierten Snapshot, adaptiert ihn auf `CutListEntry`, ruft den bereits
kanonischen Pacing-Abschluss auf und überträgt nur Start, Ende und Metadaten
zurück. `_execute_render` wendet ihn nach der Audioprobe und vor
`validate_timeline` an, wenn Audio eingebunden ist und eine positive
Zieldauer vorliegt.

Caller und Seiteneffekte:

- Der Queue-Snapshot und der globale Projektzustand werden nicht mutiert.
- Medienpfade, Clip-IDs und zusätzliche Eintragsfelder bleiben erhalten.
- Start-/Endgrenzen und Boundary-Provenienz folgen demselben Vertrag wie
  T318/T335/T336.
- Render ohne Audio behält sein bisheriges Timeline-Verhalten.
- Der Fix ändert Output und erzwingt daher gemäß Anti-Loop-Regel 9 neue
  vollständige H.264- und HEVC-Läufe.

Regression:
`Tests/test_render_router_validate_timeline.py::test_render_snapshot_uses_canonical_full_length_finalization`.

## Gesicherte Rohbelege

Unter `cycle-9-failed-render/`:

| Datei | Bytes | SHA-256 |
|---|---:|---|
| `ffmpeg.progress.log` | 182.080 | `D93ED497E926D1E9FAEAFD41C5C43C7B07F0ADAC66D41F9AF85DFE2A2B591F5C` |
| `ffmpeg.stderr.log` | 451.008 | `894FEC5729F6EC762D3CAD3A2A1E0E23C69180C3CE6EB14C56AF76D113B1FFB8` |
| `result.json` | 687 | `31561EE3DCFE31977BEABBB393E4B55677DDCE5A55384DDCA85FE03245D9ED3F` |
| `validation.json` | 398 | `11BDB8E0BE93B376FAA5CE20A2CD63E591F5B509557828F80564909871534660` |

Failure-Fingerprint:
`3faf4b21f02fab52ecfe5c065e317368b5c8b40a18bd977286b542ed0078f1a2`.
