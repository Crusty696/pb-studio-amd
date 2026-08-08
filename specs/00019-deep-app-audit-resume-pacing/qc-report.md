# QC Report: OBJ-74

## Authoritative OBJ-74 Gate

- **Overall result:** **REOPENED / NOT RELEASE-READY**.
- T001–T031 sind teilweise geschlossen; Long-Mix-Chunk-Resume, echte Medien,
  Live-Hardware, 14-View-GUI-Smoke und finale Konvergenz bleiben offen.
- `.completed` und `.qc-passed` fehlen absichtlich.
- Bestehende OBJ-72/OBJ-73-Release-Evidenz bleibt historisch gültig, beweist aber
  nicht den neuen Analyse-Resume- und Pacing-Vertrag.

## Aktuelle Evidenz

- Python-Baseline: 1320 Tests, 2 Failures, 13 Skips; JUnit archiviert.
- Claude-Integration: alle Tips Ancestors; Merge-Trees unverändert.
- Selektive Claude-Ports: kombinierter Cluster 24/24 PASS.
- Audio-/Video-Resume + Interrupted + Pacing-Preflight: 15/15 PASS.
- WPF Transport/UI-Vertrag: 5/5 PASS; Release-Build 0 Fehler/0 Warnungen.
- OpenAPI Snapshot/Generated-DTO-Drift: 4/4 PASS.

## Offene Gate-Gründe

- Long-Mix besitzt Stage-, aber noch keinen atomaren per-Chunk-Checkpoint.
- Gesamtbaseline enthält einen nicht erneut ausgeführten RAM-Fehler im
  Timeline-Integritätstest; erneute Gesamtsuite wurde im Caveman-Minimalmodus
  auf Nutzerwunsch ausgelassen.
- Live-API/SSE/AMF/DirectML und GUI-Abnahme wurden nicht als PASS belegt.
