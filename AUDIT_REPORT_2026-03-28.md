# PB Studio AMD – Full Audit Report
**Datum:** 2026-03-28
**Auditor:** Claude (Full-Stack-Auditor)
**Status:** ✅ FIXES ANGEWENDET

---

## STATISTIK

| Kategorie | Anzahl |
|-----------|--------|
| Python-Dateien geprüft | ~60 |
| C#-Dateien geprüft | ~20 |
| XAML-Views geprüft | 9 |
| Test-Dateien | ~25 |
| Kritische Fehler (IRON RULE) | 2 → ✅ gefixt |
| Warnings | 3 (1 offen, 1 gefixt, 1 Info) |
| OK / Korrekt implementiert | alles andere |

---

## 🔴 KRITISCHE FEHLER

### KRITISCH-001 – `clap_wrapper.py:151` ✅ GEFIXT (2026-03-28)
**Datei:** `src/pb_studio/ai/clap_wrapper.py`
**Zeile:** 151
**Code vorher:**
```python
sess_options.enable_cpu_mem_arena = True
```
**Code nachher:**
```python
sess_options.enable_cpu_mem_arena = False  # IRON RULE §2
```
**Problem:** IRON RULE §2 schreibt vor: `enable_cpu_mem_arena = False` UND `enable_mem_pattern = False` sind BEIDE Pflicht für DirectML. `enable_mem_pattern` war korrekt auf `False` (Zeile 145), aber `enable_cpu_mem_arena` stand auf `True`.
**Beweis:** Grep auf alle ONNX-Module zeigt: clap_wrapper.py war das einzige Modul mit `enable_cpu_mem_arena = True` in einer echten (nicht-Stub) Session-Initialisierung.
**Hinweis:** Zeile 33/35 (`_FallbackSessionOptions`) bleibt auf `True` – das ist ein Test-Stub ohne GPU, nie für echte DirectML-Sessions verwendet.

---

### KRITISCH-002 – `separator.py:173` ✅ GEFIXT (2026-03-28)
**Datei:** `src/pb_studio/audio/separator.py`
**Zeile:** 173–174 (nach Fix)
**Code vorher:**
```python
def _apply_directml_patch(self):
    ...
    def _patched_init(self_opts, *args, **kwargs):
        self._original_session_options_init(self_opts, *args, **kwargs)
        self_opts.enable_mem_pattern = False
        # enable_cpu_mem_arena fehlte komplett
    ort.SessionOptions.__init__ = _patched_init
```
**Code nachher:**
```python
        self_opts.enable_mem_pattern = False
        self_opts.enable_cpu_mem_arena = False  # IRON RULE §2 – beide Flags pflicht
```
**Problem:** `_apply_directml_patch()` ist ein SessionOptions-Monkey-Patch der für die Demucs Stem-Separation (Kern-Feature) verwendet wird. Er setzte nur `enable_mem_pattern = False`, ließ aber `enable_cpu_mem_arena` auf dem Default `True`. Das ist ein direkter IRON RULE §2 Verstoß für das wichtigste GPU-Modul der Anwendung.

---

## 🟡 WARNINGS

### WARN-001 – PyQt6 in requirements.txt (OFFEN – Entscheidung User)
**Datei:** `requirements.txt:3`
**Code:** `PyQt6==6.8.0`
**Problem:** Die Legacy Python-UI (`src/pb_studio/ui/`) ist noch vorhanden und PyQt6 ist in requirements.txt gebunden, obwohl die Produktions-UI vollständig auf C# WPF migriert wurde. Erhöht Installationsgröße um ~120 MB und erzeugt unnötiges Paket-Konflikt-Risiko.
**Empfehlung:** PyQt6 aus requirements.txt entfernen und `src/pb_studio/ui/` archivieren oder löschen. **Wartet auf explizite Entscheidung.**

### WARN-002 – faiss-cpu Version zu locker ✅ GEFIXT (2026-03-28)
**Datei:** `requirements.txt:37`
**Vorher:** `faiss-cpu>=1.7.0`
**Nachher:** `faiss-cpu==1.7.4`
**Problem:** CLAUDE.md §5 (Locked Versions) spezifiziert explizit `1.7.4 cp311-win_amd64`. Höhere Versionen haben möglicherweise kein Windows-Wheel für Python 3.11.

### WARN-004 – render_service.py ohne Test-Coverage (INFO)
**Datei:** `src/pb_studio/services/render_service.py` (615 Zeilen)
**Problem:** Die gesamte FFmpeg-AMF-Render-Pipeline inkl. Cancel-Support, Progress-Parsing und Segment-Rendering hat keine automatisierten Tests.
**Risiko:** Regressionsfehler bei Änderungen nicht erkennbar.
**Empfehlung:** Mindest-Tests für: Encoder-Config, Progress-Parsing-Regex, Cancel-Signal.

---

## ✅ OK / VERIFIZIERT

| Bereich | Status | Details |
|---------|--------|---------|
| AMD DirectML Compliance | ✅ | Kein CUDA-Import, kein ROCm, kein pynvml in allen Python-Dateien |
| ONNX DirectML Pattern (außer Fixes) | ✅ | moondream.py, raft.py, clap_wrapper (nach Fix), alle anderen korrekt |
| NumPy <2.0 Kompatibilität | ✅ | numpy==1.26.4 in requirements.txt gepinnt |
| CPU-Fallback-Verbot | ✅ | Kein CPU-Fallback für GPU-Ops gefunden |
| shell=True | ✅ | Nicht vorhanden in gesamtem Codebase |
| Path-Traversal-Schutz | ✅ | `Path.is_relative_to()` in project_router + render_router korrekt |
| SQL-Injection-Schutz | ✅ | Alle Queries parametrisiert (SQLAlchemy ORM) |
| C# ViewModels MVVM | ✅ | Alle 9 VMs: [ObservableProperty], [RelayCommand], partial class korrekt |
| ApiClient.cs Port 8765 | ✅ | Alle Endpoints korrekt gemapped |
| SSEClient.cs | ✅ | Fan-out korrekt, alle Events empfangen |
| MaterialDesignThemes | ✅ | In allen XAML-Views korrekt eingebunden |
| publish_event Fan-out | ✅ | Broadcastet an alle registrierten Queues |
| Async-Korrektheit Backend | ✅ | Blocking calls via asyncio.to_thread() gewrapped |
| Pydantic Schemas | ✅ | Alle Endpoints typisiert |
| AppState Singleton | ✅ | current_project korrekt persistiert |
| with_gpu_task Arbiter | ✅ | VRAMBudgetManager korrekt eingebunden |
| testpaths = Tests | ✅ | Großbuchstabe korrekt in pyproject.toml |

---

## GEGENPRÜFUNG

**KRITISCH-001 nach Fix:**
`grep -n "enable_cpu_mem_arena" clap_wrapper.py` → Zeile 151: `= False` ✅
Zeile 33 (`_FallbackSessionOptions`) bleibt `True` – korrekt, da Test-Stub ohne GPU.

**KRITISCH-002 nach Fix:**
`grep -n "enable_cpu_mem_arena\|enable_mem_pattern" separator.py` → Zeile 173: `= False`, Zeile 174: `= False` ✅
Beide Flags gesetzt, Reihenfolge korrekt.

**WARN-002 nach Fix:**
`grep "faiss" requirements.txt` → `faiss-cpu==1.7.4` ✅

**Fehlende Befunde:**
Zweiter Durchlauf bestätigt: Kein weiterer IRON RULE Verstoß gefunden. WARN-001 (PyQt6) und WARN-004 (Tests) sind bekannte, nicht-kritische Punkte die explizite User-Entscheidung benötigen.

---

## FAZIT

**Was funktioniert:** Die gesamte Architektur ist solide. AMD DirectML ist korrekt implementiert. C# WPF MVVM-Pattern durchgängig korrekt. Backend async-sauber. Sicherheit (Path-Traversal, SQL) in Ordnung.

**Was war kaputt:** 2 IRON RULE §2 Verstöße (`enable_cpu_mem_arena = True`) in `clap_wrapper.py` und `separator.py`. Beide gefixt.

**Was offen ist:** PyQt6-Altlast in requirements.txt (WARN-001) und fehlende Tests für render_service.py (WARN-004). Beide brauchen explizite Entscheidung.

**Gesamtbewertung:** Produktionsreif nach den 3 Fixes. Keine weiteren kritischen Probleme.
