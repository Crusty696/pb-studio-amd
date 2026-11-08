# PB Studio Full-Stack Double Audit — 2026-08-09

## Ergebnis

Zwei vollständige Auditrunden über WPF, REST/SSE, Projektlebenszyklus, Audio,
Video, Pacing, Brain, Render, Storage, Chat/Modelle, Config, Terminal und
DirectML wurden durchgeführt. Runde 1 fand **0 Critical, 25 High, 19 Medium und
6 Low/Info**. Runde 2 reparierte sieben neue oder wiederkehrende Vertragslücken.

Die drei früher offenen High-Risiken sind umgesetzt: Chat hält eine
projektgebundene Capability über den gesamten Turn, Projector V2 arbeitet mit
stabilen Projekt-/Event-UUIDs und exactly-once Publish, und Recovery koppelt die
persistierten Wahrheitsquellen in immutable, hashgeprüfte Generationen.

Implementierung und risikobasierte QC sind grün. Der abschließende A→B-
Videoauswahl-Smoke bestand ohne stale Auswahl oder destruktive Aktion.

## Umgesetzte Kernänderungen

| Bereich | Ergebnis |
|---|---|
| Recovery | Fester Control-Root vor Config, immutable Generationen, Journal, Hash-/Schema-Prüfung, Bootstrap-Roll-forward/-back und Owner-Barriere über Config, Catalog, Projekt, Chat, Brain, Vector, Stem und Render. |
| Projector | Stabile `project_uuid`/`event_uuid`, V2-Artefakt, Copy-on-write-Training, Pending-Events, Checkpoints, exactly-once Publish und V1-Rebuild/Rollback. |
| Chat | Projekt-Capability und Commit-Guard decken den vollständigen SSE-Turn einschließlich Toolrequests ab. |
| Audio/Video | Source-/modellgebundenes Stem-Resume, terminal verriegeltes SSE, dauergebundenes Sampling, ehrliche Partial-Tags und korrigierte VLM-Kaltstart-Synchronisierung. |
| Pacing/Brain | Wirksame Regler, echte Anchor-Identität, Semantic-/Key-Gates, unabhängiger Fallback, Mood-Kanonisierung und kein Lernkredit für fehlende Achsen. |
| Render/Core | Cancellable FFmpeg-Normalisierung, Video-only-Export, Temp-Cleanup, zentrale DirectML-Session-Ownership und korrigierter GPU-Cleanup. |
| WPF | Projektgebundene Chat-/Timeline-/Videozustände, geleerte Videoauswahl bei Projektwechsel, bounded Terminal und zweimal geprüfte 14-Hauptview-Navigation. |

## Verifikation

| Prüfung | Ergebnis |
|---|---:|
| Recovery/Lifespan | 44 passed |
| DirectML/Brain Embeddings | 42 passed, 5 skipped |
| Fehlernaher kombinierter Korridor | 76 passed, 1 skipped |
| Audio / Video / Pacing Zonen | 44 / 60 / 63 passed |
| Render/Core/GPU | 68 passed |
| Native C# | 55/55 passed |
| WPF Release | 0 Warnungen, 0 Fehler |
| GUI | 2 × 14/14 Hauptviews, Screenshot-Manifeste vorhanden |
| Live VLM | 4 Kandidaten erkannt; Screenshot und echtes Katalogvideoframe je 10 Tags |
| Live Recovery | 2 Generationen committed; Crash-PREPARING beim Neustart sicher verworfen |
| Breite Python-Suite | 1450 passed, 13 skipped, 1 Harness-Timeout; 1024,92 s |
| T412 nach Root-Cause-Korrektur | 3/3 lokal; 10/10 Stress |

Der einzige breite Suite-Ausreißer war
`test_cross_process_enqueue_returns_one_active_attempt` mit
`threading.BrokenBarrierError`. Die Render-Queue-Invariante blieb intakt; unter
Vollsuite-Last war die Harness-Barriere zu knapp. Nach der begrenzten Korrektur
bestanden der vollständige T412-Vertrag und zehn Stresswiederholungen.

Auf Nutzerentscheidung wurde die 17-Minuten-Suite nicht erneut ausgeführt. Der
Bericht behauptet deshalb keinen neuen grünen Gesamtlauf, sondern die in
TR-369/TR-371 registrierte risikobasierte Delta-Konvergenz.

## Live-Evidenz

- GUI-Screenshots: `gui_screenshots/obj75_round1` und
  `gui_screenshots/obj75_round2`; je 14 PNGs. Manifestdigests stehen in
  `specs/00020-obj75-open-bug-fixes/evidence/gui-view-matrix.md`.
- Der echte WPF-Lauf verband Log-, Progress- und GPU-SSE; Rohbelege stehen in
  `logs/wpf_app.log` und `logs/backend.log`.
- LM Studio lieferte vier lokale Vision-Kandidaten. Nur
  `qwen2.5-vl-7b-instruct` wurde für den Smoke geladen und danach entladen; keine
  Downloads oder Löschungen.
- Das echte Katalogvideoframe wurde in 2,172 s aktiver Phase getaggt; der
  Loading-Heartbeat kam nach 1,313 s.
- Die Recovery-Läufe endeten regulär über `/shutdown`; ein erzwungener Crash
  ließ die vorherige `CURRENT`-Generation unverändert nutzbar.

## IRON-Regeln

- Kein produktiver CUDA-/ROCm-/NVENC-/NVIDIA-Monitoringpfad wurde eingeführt.
- ONNX läuft über DirectML und den zentralen ModelLoader; die beiden
  Session-Memory-Flags bleiben gebunden.
- Render bleibt AMF-only. Historische Archivtreffer zu `libx264` gehören nicht
  zum Produktpfad.
- Python 3.11.9, NumPy 1.26.4, Windows-Pfade, `PYTHONPATH=src` und `Tests/`
  wurden beibehalten.

## Finaler Projektwechsel-Beleg

- Release-Regression: **1/1 PASS**.
- Live: A=3 Clips/2 selektiert; B=1 Clip mit reused `clip_id=1`; danach
  `target_selected=0`, Analyze/Delete deaktiviert.
- `destructive_actions_invoked=false`; App/Backend sauber beendet,
  `BACKEND_FORCED=0`.

## Releaseentscheidung

**PASSED / RELEASE-READY.** Alle registrierten Gates einschließlich Recovery,
Projector, Chat, risikobasierter Python-Konvergenz, C#/WPF, API/SSE, Realmedien,
2×14 Views und A→B-Projektwechsel sind erfüllt.
