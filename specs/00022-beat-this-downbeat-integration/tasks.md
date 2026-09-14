# Tasks: OBJ-79 Beat-This-Downbeat-Integration

**Status:** COMPLETE
**Spec:** `specs/00022-beat-this-downbeat-integration/spec.md`
**Plan:** `specs/00022-beat-this-downbeat-integration/plan.md`

- [X] T001 [OBJ-79] {(FR-402)} {(OR-362)} Registriere Modell, Konfiguration, Mel-Filterbank und Lizenz in `config/beat-this-assets.json`; Release-Bundle unverändert.
- [X] T002 [OBJ-79] {(FR-402)} {(FR-403)} {(FR-406)} {(OR-363)} Implementiere hashgebundenen DirectML-Tracker in `src/pb_studio/audio/beat_this_tracker.py`.
- [X] T003 [OBJ-79] {(FR-404)} {(FR-405)} {(FR-406)} Verdrahte Tracker in `backend/routers/audio_router.py` mit Fail-Closed-Provenance und Streaming-Grenzen.
- [X] T004 [OBJ-79] {(FR-407)} Prüfe Persistenz/API/Pacing-Vertrag in `Tests/test_beat_this_integration.py`; bestehende Produktionsverträge benötigen keine Änderung.
- [X] T005 [OBJ-79] {(TR-384)} {(TR-385)} Ergänze und verifiziere Asset-, Tracker-, Router-, GPU-Lifecycle- und Pacing-Tests unter `Tests/`.
- [X] T006 [OBJ-79] {(TR-386)} Führe deterministische Echttrack-/Snare-Gegenproben mit Produkt-Pacing durch; dokumentiere Receipts unter `specs/00022-beat-this-downbeat-integration/evidence/`.
- [X] T007 [OBJ-79] {(TR-387)} Führe Vollsuite, fokussierte Nachprüfung, WPF-Release-Build und DB-Prüfung aus; Bericht unter `specs/00022-beat-this-downbeat-integration/evidence/`.
- [X] T008 [OBJ-79] {(TR-386)} {(TR-387)} Erstelle vollständige Abschluss- und QC-Evidenz in `specs/00022-beat-this-downbeat-integration/qc-report.md`.
