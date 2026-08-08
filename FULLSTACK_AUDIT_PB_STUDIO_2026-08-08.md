# PB Studio Tiefenaudit — 2026-08-08

## Status

**OBJ-74: ACTIVE / NICHT RELEASE-FERTIG**

Der vollständige Funktionskatalog umfasst 14 WPF-Views, 16 ViewModels und den
aktuellen REST-/SSE-/Core-Pfadbestand. Die vom Nutzer nachträglich angeordnete
Testreduktion wurde umgesetzt: ein vorhandener Gesamtlauf dient als Baseline;
danach liefen nur kombinierte, direkt betroffene Vertragscluster.

## Inventar

| Bereich | Bestand | Prüfung | Ergebnis |
|---|---|---|---|
| Project Overview | Projekt create/open/save/close, Persistenz | statisch + Baseline | kein neuer P1-Befund |
| Media Ingest | Audio-/Videoimport, Hash-/Reuse-Pfade | statisch + Baseline | kein neuer P1-Befund |
| Audio Library | Import, Analyse, Beats, Onsets, Struktur, Spektral, Stems | tief + Regression | Stage-Resume repariert; Chunk-Hard-Interrupt offen |
| Video Library | Import, Scenes, Motion, Farben, Tags, Embedding, Key | tief + Regression + WPF | Resume/Statusanzeige repariert |
| Director/Pacing | Preflight, Trigger, Struktur, Motion, Semantic, Key, Brain, Anchors | tief + Regression | fehlende Voraussetzungen blockieren vor Worker |
| Timeline | Mehrspur, Sync, Preview | statisch + Baseline | Baseline-RAM-Fehler offen |
| Production | AMF-Render, Jobstatus, Export | statisch + Baseline | Live-AMF-Abnahme offen |
| Brain | Reranking, Feedback, Explain, Lernstatus | statisch + Baseline | optionale Achsen dürfen degradieren |
| Chat | LM-Studio, Streaming, Tools | statisch + Baseline | Live-Modellabnahme offen |
| Model Manager | Registry, Auswahl, Downloadstatus | statisch + Baseline | Live-Runtime-Abnahme offen |
| Settings | Config, Verbindungen, Preferences | statisch + Baseline | Live-Persistenz-Abnahme offen |
| Terminal | Log-SSE, Filter, Anzeige | statisch + Baseline | GUI-Smoke offen |
| Anchor | Projektanker, Persistenz, Pacing-Übergabe | statisch + Baseline | kein neuer P1-Befund |
| VRAM Telemetry | DirectML-Budget, Monitoring, Cleanup | statisch + Baseline | Hardware-Live-Abnahme offen |

Detailkatalog: `test-report/function-catalog.md`.

## Baseline

- Main-Ausgang: `3be700d4214ba427567b63fe80d79f7f8dcf5284`.
- Python: 1320 Tests, 2 Failures, 13 Skips, 890.552 Sekunden.
- Failure 1: NSwag-mtime-Fehlalarm trotz erfolgreicher unveränderter Ausgabe;
  durch expliziten Build-Stamp repariert und mit 4 OpenAPI-Tests bestätigt.
- Failure 2: `test_auto_pacing_pipeline_chronological_no_violations` scheiterte
  nach rund 5 GiB Prozessspeicher an einer weiteren 2.52-MiB-NumPy-Allokation.
- WPF Release-Build: 0 Fehler, 0 Warnungen.
- Kombinierter Claude-Port-Cluster: 24/24 bestanden.
- Kombinierter Audio-/Video-Resume-Cluster: 5/5 bestanden.
- Pacing-Preflight: 8/8 bestanden.
- WPF Transport/UI-Vertrag: 5/5 bestanden; OpenAPI-Drift: 4/4 bestanden.

JUnit: `specs/00019-deep-app-audit-resume-pacing/evidence/pytest-full.xml`.

## Kritische Befunde und Maßnahmen

### F-74-01 — Video-Teilretry löschte vorhandene Analyse

**Schwere:** CRITICAL — behoben.

`backend/routers/video_router.py` startete jeden Lauf mit Default-Leerwerten und
persistierte sie auch für deaktivierte Stages. Ein Embedding-Retry konnte Scenes,
Motion, Farben und Tags löschen; eine fehlende Quelldatei überschrieb gute Daten.

Maßnahme: merge-only Resume-Basis, Payloadvalidierung, Stage-Planer,
`force`, Missing-File ohne Write und fokussierte Regressionsbeweise.

### F-74-02 — Audio-Teilretry löschte Beats/Struktur/Trigger

**Schwere:** HIGH — behoben.

Deaktivierte Analysepfade lieferten `[]`, `0` oder `None`; der Router persistierte
diese Werte über bereits gültige Beats, Energie, Struktur, Spektral- und
Drumtriggerdaten. Key lief immer erneut.

Maßnahme: kanonische Audio-Stages, Payloadvalidierung, merge-only Ergebnis,
`detect_key`, `force` und automatische Planung `requested - valid completed`.

### F-74-03 — Pacing nutzte still fehlende Analysewerte

**Schwere:** HIGH — behoben.

Nur Motion/Brain luden Videoanalyse; Semantic und Key konnten ohne Embedding bzw.
Video-Key starten. Fehlende Beats erreichten den Worker und endeten spät als 500.

Maßnahme: modeabhängiger Preflight für Audio-Beats/Struktur/Key und
Video-Motion/Embedding/Audio-Key; HTTP 422 enthält Clip-IDs, Status und
Payloadgültigkeit. Der Director zeigt den Backend-Grund.

### F-74-04 — WPF versteckte partielle Videoanalyse

**Schwere:** HIGH — behoben.

Der Backend-Listenvertrag enthielt Analyse-/Stagezustände, der handgeschriebene
WPF-DTO und das Model nicht. Partiell analysierte Clips erschienen nur als
„nicht analysiert“; Audio-Batch zählte Nullantworten als Erfolg.

Maßnahme: Status-/Fehlertransport, sichtbare Teilanalyse-/Unterbruchzustände,
Resume über vorhandene Buttons und Batchfortsetzung mit ehrlicher Zählung.

### F-74-05 — Echte Unterbrechung checkpointete nicht jede Stage

**Schwere:** HIGH — auf Stage-Ebene behoben.

`asyncio.to_thread` beendet den nativen Audio-Worker nicht. Ohne Stage-Checkpoint
gehen Ergebnisse verloren, die im aktuellen Lauf bereits fertig, aber noch nicht
final persistiert waren. Video besitzt getrennte Stages, persistierte sie bei
`CancelledError` jedoch bisher ebenfalls nicht.

Maßnahme: kooperative Audio-Stage-Checkpoints, Stop-Signal gegen späte
Worker-Commits, Video-Interrupted-Persistenz und terminale SSE-Zustände. Fertige
Stages bleiben erhalten; nur offene Stages werden `interrupted`. Keine
DB-Migration und keine Änderung an der gesperrten Separator-Datei.

### F-74-06 — Long-Mix-Chunk-Resume

**Schwere:** HIGH — offen.

Chunk-Evidenz wird erst nach Rückkehr des kompletten Audio-Workers persistiert.
Ein Prozess-Kill innerhalb eines langen Mixes kann deshalb abgeschlossene Chunks
nicht zuverlässig wiederverwenden. Eine ehrliche Lösung benötigt atomare
Chunk-Checkpoints außerhalb `separator.py`; dies ist nicht durch den Stage-Fix
vorgetäuscht.

## Claude-Branches

- `claude/competent-shaw` war bereits exakter Main-Ancestor.
- `claude/upbeat-liskov` und die lokalen veralteten Tips sind über den neueren
  Remote-Tip abgedeckt.
- `origin/claude/nifty-sammet` und `origin/claude/cranky-hodgkin` sind als
  geprüfte Merge-Eltern erfasst; ihre Trees wurden wegen Konfliktmarkern,
  lokalen Settings, Test-Symlinks und 498 neueren Main-Commits nicht eingespielt.
- Gültig portiert: Windows-hidden Video-Subprozesse und direkter echter
  Clip-Embedding-Fallback.
- Verworfen: alter Checkerboard-Vektorhunk; er änderte ungerade Kernel und konnte
  rund 154 MiB zusätzlichen temporären Speicher materialisieren.

Vollständige Matrix:
`specs/00019-deep-app-audit-resume-pacing/evidence/claude-branch-integration.md`.

## Offene Abnahme

- Long-Mix-Chunk-Checkpointing und Kill/Restart-Beweis.
- echte Medienanalyse aus `C:\Users\david\Videos\test_data\audio` und `video`.
- Live-REST/SSE, AMF-Render und DirectML-Hardwarepfade.
- GUI-/Keyboard-/UIA-Smoke aller 14 Views.
- erneuter Gesamt-QC-Lauf erst auf ausdrückliche Anforderung; Caveman-Minimalmodus
  bleibt aktiv.

`.completed` und `.qc-passed` wurden nicht erzeugt.
