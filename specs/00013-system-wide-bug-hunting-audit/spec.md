# Spezifikation: System-wide Bug Hunting & Codebase Audit (Epic 00013)

## Problem Statement
Nach dem erfolgreichen Abschluss aller funktionalen Epics der Entwicklungs-Roadmap ist es von kritischer Bedeutung, die Codebase einer rigorosen, evidenzbasierten und lückenlosen Auditierung zu unterziehen. Stumme Ausnahmen (silent exceptions), unvollständige VRAM-Freigaben, Speicherlecks (memory leaks) bei WPF-ViewModels, SQLite-Lock-Contention im Concurrent-Betrieb, obsolete Dateileichen oder stumme Abbrüche in der Audio- und Videoverarbeitung können die Stabilität im Langzeitbetrieb gefährden.

Zusätzlich wurden zwei kritische Probleme im Audio-Bereich identifiziert:
1. **Stem-Separation Crash:** Die Generierung von Stems über die App schlägt mit einem RuntimeError fehl, weil für das `htdemucs`-Modell in `audio_schemas.py` der ungültige Name `"htdemucs"` anstelle des korrekten Dateinamens `"htdemucs.yaml"` definiert ist.
2. **Audio-Analyse Lücke:** Die Audio-Analyse (Beats und Key) verwendet stur das Original-Audio, anstatt bei Vorhandensein von Stems die präziseren Spuren (Drums für Beats, Instrumental für Key) zu nutzen, was die Analyseergebnisse signifikant verschlechtert.

---

## Scope

## Included (Im Audit enthaltene Zonen)
* **Z-AUDIO:** BPM- und Key-Erkennung, Demucs Stem Separation, SpectralAnalyzer-Puffer, Floating-Point Berechnungen.
  * *Ergänzung:* Korrektur des `htdemucs.yaml` Strings in `audio_schemas.py` und Umleitung von Beat-Detection auf `drums_path` und Key-Detection auf `instrumental_path` in `audio_router.py`, falls Stems im Clip vorhanden sind.
* **Z-VIDEO + Z-RENDER:** MotionAnalyzer (RAFT), Vision LLM (Moondream FP16 ONNX), FrameGrabber, FFmpeg-Subprozesse, AMF-Hardware-Encoding-Fallbacks.
* **Z-CORE:** `VRAMBudgetManager`, aktive Modell-Registrierung, Threadpool-Grenzwerte, DirectML-Speicherlimits.
* **Z-DATA:** SQLite WAL-Journaling, FAISS-Index-Lebenszyklen, base64-gzip Serialisierung, `sqlite-vec` KNN-Anfragen.
* **Shared-Zones & Z-INFRA:** `main.py`, `app_state.py`, WPF-to-Python SSE Bridge, REST-Routen.
* **Z-UI-VM & Z-UI-SERVICES:** IDisposable ViewModels, Memory Leakage Probes, eventbasierte UI-Routing-Leaks.

### Excluded
* Externe Hardware-Installationen oder Treiber-Aktualisierungen.

---

## Technical Objectives
* **OBJ-1:** Identifikation aller stillen Exceptions oder stummen Pipeline-Abbrüche in backend/routers/ und src/pb_studio/.
* **OBJ-2:** Aufspüren von Speicherlecks in C#- und Python-Dateien.
* **OBJ-3:** Aufdecken von VRAM-Bottlenecks oder Modell-Evizierungslücken im `VRAMBudgetManager`.
* **OBJ-4:** Überprüfung der SQLite- WAL-Konfiguration und Lock-Contention-Sicherheit.
* **OBJ-5:** Aufspüren von Dateileichen, veralteten Wrappern, toten Importen oder Code-Drifts.
* **OBJ-6:** Behebung des htdemucs Modellauswahl-Crashes bei der Stem-Separation.
* **OBJ-7:** Integration der Stems (Drums für Beats, Instrumental für Key) in die Audio-Analyse-Pipeline.

---

## Success Criteria (SC)
* **SC-001 [OBJ-1]:** Ein lückenloser, klinischer Audit-Bericht listet alle echten Code-Schwachstellen auf.
* **SC-002 [OBJ-2]:** 0 verbleibende IDisposable-Lecks bei WPF-ViewModels.
* **SC-003 [OBJ-3]:** Nachweisbare Stabilität aller DirectML-Fallbacks bei künstlicher VRAM-Reduktion.
* **SC-004 [OBJ-4]:** Keine ungesicherten SQLite-Schreibaufrufe im Backend.
* **SC-005 [OBJ-6]:** Erfolgreiche Stem-Separation mit `htdemucs.yaml` ohne Model-NotFound-RuntimeError.
* **SC-006 [OBJ-7]:** Die Audio-Analyse führt die Beat-Detection auf der Drums-Spur und die Key-Detection auf der Instrumental-Spur durch, wenn diese Stems existieren.

