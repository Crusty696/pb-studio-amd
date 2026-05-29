# Spezifikation: System-wide Bug Hunting & Codebase Audit (Epic 00013)

## Problem Statement
Nach dem erfolgreichen Abschluss aller funktionalen Epics der Entwicklungs-Roadmap ist es von kritischer Bedeutung, die Codebase einer rigorosen, evidenzbasierten und lückenlosen Auditierung zu unterziehen. Stumme Ausnahmen (silent exceptions), unvollständige VRAM-Freigaben, Speicherlecks (memory leaks) bei WPF-ViewModels, SQLite-Lock-Contention im Concurrent-Betrieb, obsolete Dateileichen oder stumme Abbrüche in der Audio- und Videoverarbeitung können die Stabilität im Langzeitbetrieb gefährden. Ziel dieses Epics ist es, jegliche auch noch so kleine Lücke oder Schwachstelle in allen Code-Zonen klinisch zu identifizieren, zu analysieren und zu dokumentieren.

---

## Scope

### Included (Im Audit enthaltene Zonen)
* **Z-AUDIO:** BPM- und Key-Erkennung, Demucs Stem Separation, SpectralAnalyzer-Puffer, Floating-Point Berechnungen.
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
* **OBJ-2:** Aufspüren von Speicherlecks (unclosed resources, undisposed service scopes, static event leakage) in C#- und Python-Dateien.
* **OBJ-3:** Aufdecken von VRAM-Bottlenecks oder Modell-Evizierungslücken im `VRAMBudgetManager` unter hoher Stresslast.
* **OBJ-4:** Überprüfung der SQLite- WAL-Konfiguration und Lock-Contention-Sicherheit bei concurrent Requests.
* **OBJ-5:** Aufspüren von Dateileichen, veralteten Wrappern, toten Importen oder Code-Drifts.

---

## Success Criteria (SC)
* **SC-001 [OBJ-1]:** Ein lückenloser, klinischer Audit-Bericht (Audit-Report) listet alle echten Code-Schwachstellen (Findings) mit Dateipfad, Zeilennummern und nachweisbarem Risiko auf.
* **SC-002 [OBJ-2]:** 0 verbleibende IDisposable-Lecks bei WPF-ViewModels oder statischen Event-Handlern in der UI.
* **SC-003 [OBJ-3]:** Nachweisbare Stabilität aller DirectML-Fallbacks bei künstlicher VRAM-Reduktion.
* **SC-004 [OBJ-4]:** Keine ungesicherten SQLite-Schreibaufrufe im Backend.
