# PB Studio Full-Stack-Tiefenaudit — 2026-08-08/09

## 1. Scope und Urteil

**Objective:** OBJ-74 — vollständiges Funktionsinventar, verlustfreies
Analyse-Resume, nachvollziehbare Clip-Auswahl und Konvergenz aller Branches.

**Geprüfte Schichten:** 14 WPF-Tabs, 16 ViewModels, REST/SSE, FastAPI-Router,
Audio-/Video-/Pacing-Core, SQLite/Cache/FAISS, Projekt-Lifecycle, Branch-Historie
und Build-/Testverträge. Ausgeschlossen blieben Datenmigrationen, neue
Dependencies, Produktionsdeployment und Änderungen an der gesperrten Datei
`src/pb_studio/audio/separator.py`.

**Urteil:** Alle im Audit gefundenen CRITICAL-/HIGH-Produktfehler wurden im
aktuellen Arbeitsstand repariert und verifiziert. Ein vollständiger
Python-Lauf deckte drei Regressionen an derselben neuen Lifecycle/HTTP-Grenze
auf; nach Minimalfix bestanden der exakte 11-Test-Cluster, der OpenAPI-Vertrag
4/4 und der finale vollständige Post-fix-Lauf mit 1371 PASS/13 SKIP/0 FAIL.

Primärquellen: [Spezifikation](specs/00019-deep-app-audit-resume-pacing/spec.md),
[Plan](specs/00019-deep-app-audit-resume-pacing/plan.md),
[Tasks](specs/00019-deep-app-audit-resume-pacing/tasks.md) und
[Funktionskatalog](test-report/function-catalog.md).

## 2. Systemverständnis und Datenfluss

```text
WPF View → ViewModel → ApiClient → FastAPI Router
         → project_operation/epoch → Analyzer/Selector/DirectML
         → DB-first Partial Update + Cache/FAISS
         → SSE Event-ID/Replay → ViewModel → sichtbarer Status

Director → Pacing-Preflight → PacingService → AdvancedPacingEngine
         → ClipSelector → SelectionProvenance → Cut-Metadaten/Timeline

Long Mix → StreamingAudioAnalyzer → validierter Chunk
         → Checkpoint-Callback → project_commit → gezieltes Chunk-Resume
```

Entscheidende Invariante: Eine Analyse schreibt nur tatsächlich ausgeführte
Stages/Chunks. `completed` wird nur mit gültigem Payload wiederverwendet;
`partial`, `failed` und `interrupted` bleiben retrybar. Projekt-Epoch und
Commit-Guard verhindern Cross-Project-Writes. Vertrag:
[analysis-stage-contract.md](specs/00019-deep-app-audit-resume-pacing/evidence/analysis-stage-contract.md).

## 3. Inventar und Prüftiefe

| Bereich | Bestand | Frischer Nachweis | Ergebnis |
|---|---|---|---|
| Projekt/Ingest | create/open/save/close, Import, Hash-/Reuse-Pfade | Python-Verträge + echter Projektwechsel | PASS |
| Audio | Beats, Struktur, Spektral, Key, Trigger, Waveform, Long-Mix, Stems | Resume-/Chunk-Tests + echte Teilanalyse | PASS; Stem-Artefakte nur stageweise |
| Video | Scenes, Motion, SigLIP, Farben, Captions, Audio-Key | Resume-Tests + Shutdown/Restart mit Realmedium | PASS |
| KI-Regie/Pacing | Preflight, Trigger, Struktur, Motion, Semantic, Key, Brain, Anchor, Diversität | Preflight-/Provenienztests + GUI-Zustände | PASS |
| Timeline/Export | Mehrspur, Preview, Validierung, AMF-Verträge | Python-Suite + C# + Release-Build + UIA | PASS im automatisierten Scope |
| Brain/Modelle/Chat | Lernen, Registry, Provider, Streaming, Tools | Python-Suite + 14-Tab-UIA | PASS im automatisierten Scope |
| Settings/Performance/Terminal | Config, DirectML/VRAM, Log-SSE | Python/C# + 14-Tab-UIA | PASS im automatisierten Scope |
| Anchor | Beat-Waveform, CRUD, Pacing-Übergabe | UIA/Keyboard/Sichtprüfung | PASS |

GUI-Nachweis: exakt 14/14 Tabs selektiert, kompletter `Ctrl+Tab`-Zyklus,
0 UIA-Fehler, je Tab Screenshot und UIA-Baum. Details:
[T023-summary.md](specs/00019-deep-app-audit-resume-pacing/evidence/gui/T023-summary.md)
und [Maschinenergebnis](specs/00019-deep-app-audit-resume-pacing/evidence/gui/obj74-t023-result.json).

## 4. Findings und Reparaturen

### C-01 — Video-Teilretry löschte gültige Analyse

**Schwere:** CRITICAL, behoben.

**Ursache/Impact:** Default-Leerwerte nicht angeforderter Video-Stages konnten
Scenes, Motion, Farben, Tags oder Embedding überschreiben. Missing-File- und
Teilretry-Pfade gefährdeten damit bereits bezahlte Analysearbeit.

**Reparatur:** Stage-Plan `requested AND (force OR NOT valid_completed)`,
merge-only Ergebnis, Payloadvalidierung, DB-first Persistenz und
Embedding-Kompensation bei verworfenem Commit. Unterbruch markiert nur aktive
Stages `interrupted` ([video_router.py](backend/routers/video_router.py#L1238)).
Verlustbeweise liegen in `Tests/test_video_analysis_resume.py`.

### H-01 — Audio-Teilretry und Long-Mix verloren Arbeit

**Schwere:** HIGH, behoben.

**Ursache/Impact:** Deaktivierte Audio-Pfade lieferten Leerwerte; Key und teure
Long-Mix-Fenster konnten unnötig neu laufen. Ein Prozessabbruch verlor bereits
fertige Chunks.

**Reparatur:** Der Planer überspringt nur `completed` plus gültigen Payload
([audio_router.py](backend/routers/audio_router.py#L681)). Stage- und
schema-v2-Chunk-Checkpoints werden merge-only unter Projekt-Commit-Guard
persistiert ([audio_router.py](backend/routers/audio_router.py#L897)). Quelle,
Konfiguration, Dauer, Fensterzahl, Grenzen und Payload werden vor Reuse geprüft
([streaming_analyzer.py](src/pb_studio/audio/streaming_analyzer.py#L460)).
Primär- und Mix-Energy-Pass bleiben getrennt; private Chunk-Payloads erscheinen
nicht in öffentlicher Evidenz. Neun Long-Mix-Tests inklusive ungültigem Payload,
geänderter Quelle, Guard-Abbruch und Mix-Energy-Fehler bestehen.

### H-02 — Lifecycle-Abbruch erzeugte HTTP 500 oder falsche Wahrheit

**Schwere:** HIGH, behoben.

**Ursache/Impact:** Projektwechsel cancelte den Request nach Epoch-Wechsel.
`CancelledError` verließ den HTTP-Pfad ohne Response; Starlette meldete
`500 No response returned`. Gleichzeitig durfte ein veralteter Worker weder in
das neue Projekt schreiben noch einen späten Erfolg melden.

**Reparatur:** Nur FastAPI-injizierte Requests mit inzwischen ungültigem
Projektkontext werden zu HTTP 409 übersetzt; direkte Coroutine-Aufrufe,
Shutdown- und externe Cancellation propagieren weiter `CancelledError`
([video_router.py](backend/routers/video_router.py#L951), analog Audio).
`POST /shutdown` drainiert Projektoperationen vor dem Exit-Timer
([main.py](backend/main.py#L565)). Der Live-Projektwechsel liefert Analyse 409
und Close 200.

### H-03 — SSE konnte terminale Zustände verlieren

**Schwere:** HIGH, behoben.

**Ursache/Impact:** Ein `interrupted`-Event konnte im 100-ms-Filter verschwinden.
Wurde eine Event-ID vor erfolgreichem JSON-/Subscriber-Dispatch bestätigt,
übersprang Reconnect genau das nicht verarbeitete Terminalevent.

**Reparatur:** `interrupted` ist terminal und umgeht Throttling
([SSEClient.cs](PBStudio.UI/Services/SSEClient.cs#L417)). Die ID wird erst nach
erfolgreichem Dispatch gespeichert; ein fehlgeschlagener Dispatch erzwingt
Reconnect/Replay ([SSEClient.cs](PBStudio.UI/Services/SSEClient.cs#L188),
[SSEClient.cs](PBStudio.UI/Services/SSEClient.cs#L327)). Native C#-Verträge
prüfen Batchfortsetzung, Terminalstatus, Replay und Dispose.

### H-04 — Pacing wählte mit fehlenden Daten und ohne Erklärung

**Schwere:** HIGH, behoben.

**Ursache/Impact:** Semantic-, Motion- oder Key-Matching konnte ohne gültiges
Embedding, Motion oder Audio-Key starten; fehlende Beats scheiterten erst im
Worker. Auswahlgewichtung und adaptive Wiederholungsvermeidung waren im Ergebnis
nicht vollständig nachvollziehbar.

**Reparatur:** Pacing prüft vor Worker für aktive Modi Stage-Status und Payload;
HTTP 422 nennt Clip, Stage, Status und `payload_valid`
([pacing_router.py](backend/routers/pacing_router.py#L209)). Jede Auswahl erhält
JSON-stabile Provenienz mit Kandidatenpool, Unique-LRU-Ausschlüssen,
Fallbackgrund und Scorekomponenten
([pacing_models.py](src/pb_studio/pacing/pacing_models.py#L43),
[clip_selector.py](src/pb_studio/pacing/clip_selector.py#L340)). Brain-,
Semantic-/FAISS-, direkter Embedding-, Motion-, Key- und Anchor-Pfad sind durch
11 Provenienztests abgedeckt; Ranking und adaptive Diversität bleiben
unverändert.

### H-05 — WPF zeigte Teilanalyse und Batchfehler falsch

**Schwere:** HIGH, behoben.

**Ursache/Impact:** Backend-Stagezustände erreichten DTO/Model nicht vollständig;
partielle Clips erschienen als „nicht analysiert“. Audio-Batch konnte
Nullantwort oder Einzelfehler als Erfolg zählen beziehungsweise spätere Clips
nicht fortsetzen.

**Reparatur:** Status/Fehler/Stages laufen durch API-DTO und Models bis in Audio-,
Video- und Director-ViewModels. Batch verarbeitet verbleibende Clips und fordert
nur fehlende Stages an. GUI zeigt `ANALYSIERT`, `TEILANALYSE` und
`NICHT ANALYSIERT`; C#-Vertrag und UIA-Screenshots belegen den Pfad.

## 5. Branch-Konvergenz

24 lokale/Remote-Refs wurden per Ancestry, Patchidentität, Treevergleich,
Funktionsvergleich und Merge-Risiko geprüft. Bereits enthaltene Claude-Tips
blieben unverändert. Veraltete Trees mit Konfliktmarkern, lokalen Settings,
Test-Symlinks oder massiven Rückschritten wurden nicht blind eingespielt.

- Sinnvoll portiert: `PRAGMA synchronous=NORMAL`, eine korrelierte
  FK-Auditabfrage, Windows-hidden Video-Subprozesse und aktueller echter
  Clip-Embedding-Fallback.
- Verworfen: 32-Zeilen-Flask-Dummy statt aktueller Video-Pipeline,
  verhaltensändernde Checkerboard-Vektorisierung, obsolete
  `semantic_matcher.py`-Änderung, schwächere CORS-Policy und bereits stärkere
  heutige Implementierungen.
- Abgelehnte Branch-Trees wurden nur als geprüfte Historie mit identischem
  Tree-Hash verbunden. PR #25 und #26 brachten Konvergenz und Cleanup nach
  `main`; 8 lokale plus 16 Remote-Historienrefs wurden nach expliziter Freigabe
  entfernt.

Belege:
[Claude-Matrix](specs/00019-deep-app-audit-resume-pacing/evidence/claude-branch-integration.md)
und [All-Branch-Konvergenz](specs/00019-deep-app-audit-resume-pacing/evidence/all-branch-convergence.md).

## 6. Dynamische Verifikation

| Gate | Tatsächliches Ergebnis |
|---|---|
| Python-Gesamtsuite final | 1383 gesammelt, 1 Collection-Skip; 1371 bestanden, 13 übersprungen, 0 Fehler |
| Erster Gesamtlauf | 1368 bestanden, 13 übersprungen, 3 Lifecycle-Regressionen; als Vor-Fix-JUnit bewahrt |
| Exakter Fehlercluster nach Minimalfix | 11/11 bestanden |
| OpenAPI-Snapshot | 4/4 bestanden |
| Native C#-Tests | 54/54 bestanden |
| WPF Release-Build | 0 Warnungen, 0 Fehler |
| Live Audio | Beats-only → Vollretry ohne `force`; Beats/BPM wertgleich bewahrt, alle vier Stages completed |
| Live Video | Shutdown nach 3 s → `scenes=completed`, offene Stages `interrupted`; Restart setzt nur fehlende Stages fort |
| Live Projektwechsel | Analyse HTTP 409, Close HTTP 200 |
| GUI/UIA | 14/14 Tabs, kompletter Keyboard-Zyklus, 0 Fehler |

Unveränderte Zahlen und Artefakte:
[T021](specs/00019-deep-app-audit-resume-pacing/evidence/T021-full-test-convergence.md),
[Finales JUnit](specs/00019-deep-app-audit-resume-pacing/evidence/pytest-full-final.xml),
[Vor-Fix-JUnit](specs/00019-deep-app-audit-resume-pacing/evidence/pytest-full.xml),
[TRX](specs/00019-deep-app-audit-resume-pacing/evidence/dotnet-full.trx) und
[T022 Live-Resume](specs/00019-deep-app-audit-resume-pacing/evidence/live/T022-live-resume.md).

Ein erster Lauf mit `test_20s.mp4` wurde bei einem SigLIP-Frame-Read-Fehler
ehrlich als `partial` ausgewiesen, nicht als Erfolg; für diesen Clip wird kein
erfolgreicher Retry behauptet. Der gesonderte Shutdown/Restart-Beweis nutzt
`test_12s.mp4` und endete nach gezieltem Retry mit Motion,
1152-dimensionalem SigLIP, Farben und Audio-Key `completed`.

## 7. Restliche Risiken und Grenzen

1. **Stem-Separation:** Stage-Level-Resume vermeidet Wiederholung eines gültig
   abgeschlossenen Stem-Laufs. Einzelne Stem-Artefakte innerhalb eines
   abgebrochenen Separationslaufs besitzen keinen eigenen Partial-Checkpoint;
   `separator.py` blieb regelkonform unverändert.
2. **Externe Live-Systeme:** UIA belegt Erreichbarkeit, Darstellung und
   Zustandswahrheit aller Tabs, nicht jeden kosten-/hardwareabhängigen
   LM-Studio-, Modell-Download- oder Codecpfad mit jeder Konfiguration.
3. **Testprojekt:** Das isolierte Live-Projekt wurde absichtlich nicht gelöscht;
   keine Nutzerdaten wurden verändert.

Keine offene bekannte CRITICAL-/HIGH-Regression verbleibt im OBJ-74-Diff.
Verbleibende Grenzen sind Verifikationsbreite oder bewusst ausgeschlossener
Artefakt-Resume, keine als abgeschlossen versteckte Funktion.

## 8. Quellenbelegte Reparaturblöcke

### R-C01/H01 — Idempotentes Resume und atomare Wahrheit

**Entscheidung:** Validierte Stage-/Chunk-Ergebnisse wiederverwenden; nur neue
Ergebnisse merge-persistieren; Commit an Projekt-Epoch binden. Interne Belege:
`Tests/test_audio_analysis_resume.py`, `Tests/test_video_analysis_resume.py` und
`Tests/test_audio_long_mix_chunk_resume.py`. Das folgt dem Projektvertrag und
SQLites dokumentierter Transaktions-/WAL-Semantik: [SQLite Transactions](https://www.sqlite.org/lang_transaction.html),
[SQLite WAL](https://www.sqlite.org/wal.html). Risiko: mittel; Payloadvalidatoren
müssen bei Schemaänderung mitgeführt werden.

### R-H02 — Cancellation an der HTTP-Grenze

**Entscheidung:** Cancellation intern nicht verschlucken; nur den eindeutig
erkannten Projektkonflikt an der Request-Grenze als 409 darstellen. Quellen:
[Python 3.11 Task Cancellation](https://docs.python.org/3.11/library/asyncio-task.html#task-cancellation),
[RFC 9110, 409 Conflict](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.10)
und [Starlette Exceptions](https://www.starlette.io/exceptions/). Risiko:
niedrig; direkte/externe Cancellation ist durch getrennte Tests geschützt.

### R-H03 — SSE-Replay erst nach Verarbeitung bestätigen

**Entscheidung:** `Last-Event-ID` nur für erfolgreich verarbeitete Events
fortschreiben und terminale Events nie throtteln. Quelle:
[WHATWG Server-Sent Events — Last-Event-ID](https://html.spec.whatwg.org/multipage/server-sent-events.html#last-event-id).
Risiko: niedrig; malformed Event löst Replay statt stillen Verlust aus.

### R-H04/H05 — Vertragswahrheit vor kreativer Auswahl

**Entscheidung:** Pacing vor Worker gegen explizite, validierte Anforderungen
sperren; Auswahlentscheidung als stabiles Metadatum bis Timeline transportieren;
UI zeigt Backendstatus unverfälscht. Quellen:
[RFC 9110, 422 Unprocessable Content](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.21)
und die empirischen Projektverträge `Tests/test_pacing_*.py`,
`Tests/test_clip_selector_provenance.py` sowie
`PBStudio.UI.Tests/AnalysisResumeContractTests.cs`. Risiko: niedrig; neue
Matching-Modi müssen ihre benötigten Stages im Preflight registrieren.

## 9. Kennzahlen

- Inventar: 14 WPF-Tabs, 16 ViewModels, 60 API-Pfade, 65 Operationen.
- Branches: 24 Nebenrefs geprüft; 8 lokale und 16 Remote-Historienrefs bereinigt.
- Findings dieses Audits: CRITICAL/HIGH/MEDIUM/LOW = 1/5/0/0; alle sechs
  Produktfindings behoben und fokussiert verifiziert.
- Dynamik: final 1371 Python-Tests bestanden/13 übersprungen/0 fehlgeschlagen;
  54 C#-Tests bestanden; 14/14 Tabs UIA.
- Schutzregeln: Python 3.11, NumPy 1.26.4, DirectML-only, AMF-only und
  `separator.py`-Lock blieben unangetastet.
