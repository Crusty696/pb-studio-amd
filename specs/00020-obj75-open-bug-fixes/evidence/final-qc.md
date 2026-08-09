# T044 Risk-Based Final QC

**Result:** PASS

## Breite Bestandsaufnahme

```text
1450 passed, 13 skipped, 1 failed, 60 warnings in 1024.92s
```

Einziger Fehler war
`test_t412_render_release_contracts.py::test_cross_process_enqueue_returns_one_active_attempt`
mit `threading.BrokenBarrierError`. Die Root-Cause-Prüfung ergab eine zu knappe
Barrier-Frist unter Vollsuite-Last; die Render-Queue-Invariante selbst blieb
intakt.

## Minimale Delta-Konvergenz

- Vollständiger T412-Vertrag nach Korrektur: **3/3 passed**.
- Zehn aufeinanderfolgende T412-Stressläufe: **10/10 passed**.
- Fehlernaher kombinierter Korridor: **76 passed, 1 skipped**.
- Recovery/Lifespan: **44 passed**.
- DirectML/Brain Embeddings: **42 passed, 5 skipped**.
- Native C#: **55/55 passed**; WPF Release: **0 Warnungen, 0 Fehler**.
- IRON- und Truncation-Scan: statisch sauber.

Die Nutzerentscheidung ersetzt einen zweiten 17-Minuten-Lauf durch diese
risikobasierte Delta-Konvergenz. Es wird kein grüner neuer Gesamtlauf behauptet.

## Live-QC

- Recovery: zwei vollständige Generationen committed; Crash-PREPARING beim
  Folgestart verworfen; letzter bestätigter Stand blieb nutzbar.
- API/SSE: drei Health-/Shutdown-Endpunkte HTTP 200; WPF verband Log-, Progress-
  und GPU-SSE.
- Realmedien/VLM: vier Kandidaten erkannt, echtes Katalogvideoframe erfolgreich
  mit zehn Tags verarbeitet, Heartbeats unter fünf Sekunden.
- GUI: zweimal 14/14 Hauptviews; Digests siehe `gui-view-matrix.md`.

## Finaler Projektwechsel-Smoke

- C# Release-Regression: **1/1 PASS**.
- Live A→B: A hatte 3 Clips/2 selektiert; B hatte 1 Clip mit wiederverwendeter
  ID 1. Danach waren 0 Clips selektiert und Analyze/Delete deaktiviert.
- Keine destruktive Aktion; App/Backend sauber beendet (`BACKEND_FORCED=0`).

T044 und T049 sind erfüllt. Alle registrierten Release-Gates sind grün.
