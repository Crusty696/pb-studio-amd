# PB Studio AMD - Fix Plan

**Erstellt:** 2026-02-12
**Status:** ABGESCHLOSSEN
**Gesamtstand:** 100% - Alle Aufgaben erledigt

---

## Zusammenfassung

Die Kernarchitektur ist solide und die meisten Module sind vollständig implementiert:
- Audio-Pipeline (BeatNet, Demucs, Waveform): FERTIG
- Video-Pipeline (Scene Detection, Moondream ONNX, RAFT): FERTIG
- VRAM-Management (Budget, Arbiter): FERTIG
- Worker-System (Registry, Orchestrator, alle Worker): FERTIG
- Database + Media Service: FERTIG
- UI-Grundstruktur (Dashboard, Library, Editor, Analysis, Generation): FERTIG
- Config Manager: FERTIG
- DirectML-Integration: Korrekt in allen Modulen

## Offene Aufgaben (Priorität)

### P0 - Kritisch (App startet nicht / Kernfunktion kaputt)

- [x] **T01**: qt-material nicht in requirements.txt
  - `run_ui.py` importiert `qt_material`, aber es fehlt in requirements.txt
  - **Fix:** Zu requirements.txt hinzufügen
  - **Status:** ERLEDIGT (2026-02-12)

### P1 - Hoch (Feature-Lücken)

- [x] **T02**: Kein `install.ps1` Installer vorhanden
  - CLAUDE.md referenziert `install.ps1`, aber die Datei existiert nicht
  - Benötigt: venv erstellen, requirements installieren, FFmpeg + LHM prüfen
  - **Status:** ERLEDIGT (2026-02-12) - install.ps1 existiert und ist vollständig

- [x] **T03**: Test-Suite Stabilisierung
  - Tests in `Tests/` (Großbuchstabe) - pytest findet sie evtl. nicht
  - Einige Tests sind Stubs (test_siglip_video, test_clap_wrapper, test_vector_store)
  - conftest.py hat doppeltes Import-Pattern (pb_studio vs src.pb_studio)
  - **Status:** ERLEDIGT (2026-02-12) - Fixes:
    - pytest.ini: `testpaths = Tests` (Großbuchstabe, konsistent)
    - Alle Import-Pfade normalisiert: `from src.pb_studio.xxx` → `from pb_studio.xxx`
    - Redundante `sys.path.insert` aus allen Testdateien entfernt
    - conftest.py: try/except Import vereinfacht, sys.path.insert entfernt
    - pytest.ini `pythonpath = src` übernimmt jetzt allein die Pfad-Konfiguration
  - **Hinweis:** test_clap_wrapper.py hat vollständige Tests (nicht nur Stubs!)
    test_siglip_video.py und test_vector_store.py haben substanzielle Tests

### P2 - Mittel (Verbesserungen)

- [x] **T04**: CLAP-Wrapper vollständig testen
  - `src/pb_studio/ai/clap_wrapper.py` existiert
  - **Status:** ERLEDIGT (2026-02-12) - test_clap_wrapper.py hat 20+ vollständige Tests
    (Lazy Loading, DirectML Session Options, Provider Priority, Audio Loading,
    Encoding, Classification, Mood/Instrument/Genre Tags, Similarity, Integration)

- [x] **T05**: Smart Director Integration
  - `src/pb_studio/ai/smart_director.py` existiert und ist jetzt vollständig eingebunden
  - **Status:** ERLEDIGT (2026-02-12) - Integration in 3 Schichten:
    1. **GenerationService** (`services/generation_service.py`): Neue `_run_smart_generation`
       Pipeline - analysiert Audio (CLAP), Video-Clips (SigLIP), generiert AI-Timeline
    2. **VideoGenerator** (`video/engine.py`): Neue `generate_from_timeline` Methode -
       rendert Segmente basierend auf SmartDirector-Timeline statt zufälliger Clip-Auswahl
    3. **GenerationContainer UI** (`ui/widgets/generation/generation_container.py`):
       Checkbox "Use AI Smart Director (CLAP + SigLIP)" im Input/Output-Bereich
    - Config-Flag `use_smart_director: bool` steuert Pipeline-Auswahl
    - VRAM-Cleanup über `unload_models()` beim App-Close (main_window.py)
    - Tests: `Tests/test_smart_director_integration.py` (20+ Tests)

- [x] **T06**: Vector Store Tests erweitern
  - test_vector_store.py ist kein Stub mehr, hat 3 Tests (add, reject, search)
  - **Status:** ERLEDIGT (2026-02-12) - Tests vorhanden und Import-Pfade gefixt

### P3 - Niedrig (Nice-to-have)

- [x] **T07**: Dashboard "New Project" / "Open Project" Buttons funktionsfähig machen
  - Buttons existieren im UI, sind aber nicht verbunden
  - **Status:** ERLEDIGT (2026-02-12) - Implementation:
    1. **Dashboard** (`ui/widgets/dashboard.py`): Buttons als Instanzvariablen,
       `projectCreated`/`projectOpened` Signals, `_on_new_project` (InputDialog),
       `_on_open_project` (ProjectSelectDialog mit Projekt-Liste aus DB)
    2. **MainWindow** (`ui/main_window.py`): `_on_project_switch` Slot -
       aktualisiert Library `project_id`, refresht View, setzt Fenstertitel,
       wechselt zur Library-Ansicht
    - Nutzt existierenden `ProjectRepository` (create_project, get_all, get_by_id)

- [x] **T08**: Validierungs-Checkliste aktualisieren
  - `Tests/Validierung-Checkliste.md` an tatsächlichen Stand anpassen
  - **Status:** ERLEDIGT (2026-02-12) - Komplette Neufassung:
    - Veraltete Technologien ersetzt (CLIP→SigLIP, Phi-3.5→Moondream, ChromaDB→FAISS, RL→PacingEngine)
    - Neue Sektionen: CLAP, SigLIP, Smart Director, Worker-System, UI, LibreHardwareMonitor
    - Performance-Richtwerte aktualisiert (SigLIP statt CLIP, Moondream statt VLM)
    - Test-Suite-Referenzen mit allen 10 Test-Modulen
    - DirectML-spezifische Checks (enable_mem_pattern, Dimension, Fallback)

---

## Erledigte Aufgaben

| ID | Beschreibung | Datum |
|----|-------------|-------|
| T01 | qt-material zu requirements.txt hinzugefügt | 2026-02-12 |
| T02 | install.ps1 Installer erstellt (war bereits vorhanden) | 2026-02-12 |
| T03 | Test-Suite: Import-Pfade normalisiert, pytest.ini gefixt | 2026-02-12 |
| T04 | CLAP-Wrapper Tests waren bereits vollständig | 2026-02-12 |
| T05 | SmartDirector in GenerationService/Engine/UI integriert | 2026-02-12 |
| T06 | Vector Store Tests waren bereits vorhanden | 2026-02-12 |
| T07 | Dashboard Buttons (New/Open Project) verbunden | 2026-02-12 |
| T08 | Validierungs-Checkliste komplett neu geschrieben | 2026-02-12 |

---

## Notizen

- Python 3.10/3.11 PFLICHT (BeatNet-Kompatibilität)
- numpy==1.26.4 PFLICHT (< 2.0)
- Bash/Git funktioniert nicht direkt mit Leerzeichen im Pfad → cmd /c verwenden
