# Claude-Branch-Integration — OBJ-74

**Audit-Datum:** 2026-08-08

**Main:** `3be700d4214ba427567b63fe80d79f7f8dcf5284`

**Methode:** Drei disjunkte Read-only-Prüfungen; Ref-/Ancestry-, Patch-,
Tree-, Konfliktmarker- und Semantikvergleich gegen den aktuellen Main.

## Branch-Matrix

| Branch | Stand gegen Main | Entscheidung | Begründung |
|---|---:|---|---|
| `claude/competent-shaw` `843fef6` | 0 unique | ENTHALTEN | Branch-Tip ist exakter Ancestor von Main. |
| `claude/upbeat-liskov` `fb748f8` | 5 unique Patches | MERGE-HISTORIE + SELECTIVE PORT | Alter Tree enthält Konfliktmarker; Tip liegt 498 Main-Commits zurück. |
| `origin/claude/cranky-hodgkin` `07067bc` | 6 unique inkl. Report | MERGE-HISTORIE + SELECTIVE PORT | Alter Tree enthält Konflikt-/Regressionsrisiko; lokaler Tip ist zusätzlich 6 Commits hinter Remote. |
| `origin/claude/nifty-sammet` `79d4580` | 13 unique Patches | MERGE-HISTORIE + SELECTIVE PORT | 16 Merge-Konfliktbereiche, lokale Settings und vier Test-Symlinks; lokaler Tip ist 16 Commits hinter Remote. |

## Commit-Entscheidungen

### Selektiv auf aktuelle Architektur portieren

- `4d36225`: Windows-`STARTUPINFO` für die aktiven ffprobe-/ffmpeg-Aufrufe in
  `backend/routers/video_router.py`; übrige alte Hunks nicht übernehmen.
- `42c63a7`: Checkerboard-Novelty nur nach numerischer Parität und
  Peak-Memory-Prüfung modernisieren; kein blindes Cherry-pick.
- `c6a0ddd`: direkte Clip-Embedding-Auswahl als Fallback prüfen und passend zum
  heutigen `ClipSelector` mit Prompt-Override, Motion- und Audio-State portieren.
- `9786169`: weiterhin relevante Preview-Intervall-/Cleanup-Testideen an den
  heutigen obligatorischen AMF-Vertrag anpassen.

### Bereits im aktuellen Main stärker enthalten

- `6cd80dc`: Strukturgewichtung wird vor Sortierung/Filter inklusive Stems
  angewendet.
- `1ed3fb3`: CORS ist enger und Owner-Header-kompatibel umgesetzt.
- `dfb1b26`: DirectML-Flags sind zentralisiert; beide Pflichtflags sind aktiv.
- Health-/GPU-, AppState-, ffmpeg-Pfad- und API-Cancellation-Fixes der alten
  Auditstände sind durch neuere Implementierung und Tests abgedeckt.

### Nicht portieren

- `48e4a69`: zielt auf den entfernten `semantic_matcher.py`; heutiger Pfad ist
  `clip_selector.py` plus VectorStore.
- `362b27e`: `PRAGMA synchronous=NORMAL` ändert die Crash-/Stromausfall-
  Haltbarkeit und wird ohne eigene Durability-Entscheidung nicht übernommen.
- `5059851`: reine Formatierung/Dead-Code-Bereinigung ohne heutigen Nutzen.
- `40f86bf`: niedrige Audit-Skript-Optimierung, Commit enthält fremde Symlinks.
- `cdec9c5`, `6791213`: historische Berichte/Claude-Lokalsettings; Findings sind
  heute behoben oder werden im aktuellen Audit neu belegt.
- Alte Merge-Commits werden nicht als Quellcode-Tree übernommen, weil
  `.gitignore` und `.jules/bolt.md` echte Konfliktmarker enthalten.

## Integrationsregel

Die noch nicht in Main enthaltenen Branch-Tips werden erst nach den selektiven
Ports als bewusste Merge-Eltern mit unverändertem aktuellen Tree erfasst. Das
schließt die Branch-Historie nachvollziehbar, ohne 498 neuere Main-Commits,
Nutzerdateien oder parallel vorbereitete Arbeitsstände zurückzusetzen.

## Ausstehende Nachweise

- [ ] Selektive Ports und fokussierte Tests
- [ ] Konfliktmarker-/Diff-Prüfung
- [ ] Merge-Parent-Ancestry aller noch offenen Tips
- [ ] Python-Gesamtsuite, C#-Tests und WPF Release-Build
