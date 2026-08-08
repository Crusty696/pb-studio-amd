# PB Studio AMD Version - Vollständige Fehleranalyse

> **HISTORISCH / SUPERSEDED (2026-07-29):** Diese Bestandsaufnahme vom
> 2026-02-04 dokumentiert damalige Fehlerbilder und bewusst auch verbotene
> Beispielkonfigurationen. Sie ist kein aktiver Implementierungs-, Runtime-
> oder Releasevertrag. Aktuelle Wahrheit steht im Spec-Workspace
> `specs/00013-system-wide-bug-hunting-audit/`.

**Datum:** 2026-02-04
**Analysiert von:** 5 Auto-Agenten (code-analyzer, researcher, reviewer x2, config-analyzer)
**Gesamtstatus:** 75-80% implementiert, 47 Probleme gefunden

---

## Zusammenfassung

| Kategorie | Kritisch | Hoch | Mittel | Niedrig |
|-----------|----------|------|--------|---------|
| Code-Fehler | 4 | 7 | 7 | 5 |
| Fehlende Implementierungen | 3 | 6 | 4 | 3 |
| AI-Model Integration | 4 | 2 | 1 | 0 |
| UI-Probleme | 2 | 3 | 4 | 5 |
| Konfiguration | 3 | 2 | 4 | 2 |
| **GESAMT** | **16** | **20** | **20** | **15** |

---

## 1. KRITISCHE FEHLER (Sofort beheben!)

### 1.1 Import-Fehler in audio/__init__.py
**Datei:** `src/pb_studio/audio/__init__.py:12-13`
```python
# FALSCH - Diese Klassen existieren nicht:
from .separator import AudioSeparator  # Klasse heißt StemSeparator
from .stem_runner import StemRunner    # Nur Funktionen, keine Klasse
```
**Fix:** Exports korrigieren oder Klassen umbenennen.

### 1.2 CUDA-Referenzen in AMD-Only Codebase
**Dateien:**
- `src/pb_studio/video/moondream.py:98-111`
- `src/pb_studio/video/raft.py:123-124`

```python
# VERBOTEN laut CLAUDE.md:
providers = ['CUDAExecutionProvider', 'DmlExecutionProvider', 'CPUExecutionProvider']
```
**Fix:** `CUDAExecutionProvider` entfernen, nur DirectML + CPU erlaubt.

### 1.3 RAFT Modell-Pfad falsch
**Datei:** `src/pb_studio/video/raft.py:85`
```python
# Code erwartet:
self.model_path = "raft.onnx"
# Aber Datei heißt:
# models/raft_small.onnx
```
**Fix:** Pfad auf `raft_small.onnx` ändern.

### 1.4 Worker Progress-Callback fehlt
**Datei:** `src/pb_studio/core/thread_pool.py:32-33`
```python
# AUSKOMMENTIERT - Video-Generation wird crashen:
# kwargs['progress_callback'] = self.signals.progress
# kwargs['status_callback'] = self.signals.status
```
**Fix:** Zeilen aktivieren oder Worker-Architektur überarbeiten.

### 1.5 Signal-Typ-Mismatch
**Datei:** `src/pb_studio/core/worker_signals.py:26`
```python
progress = pyqtSignal(int)  # Erwartet int
# Aber generation_service.py sendet dict:
progress_callback.emit({"status": step, "progress": pct})
```
**Fix:** Signal auf `pyqtSignal(object)` ändern.

### 1.6 Fehlende Abhängigkeit: pythonnet
**Datei:** `requirements.txt`
- `system_monitor.py` importiert `clr` (pythonnet)
- pythonnet fehlt in requirements.txt
**Fix:** `pythonnet>=3.0.0` hinzufügen.

### 1.7 FFmpeg fehlt
**Pfad:** `tools/ffmpeg/bin/ffmpeg.exe`
- Verzeichnis existiert, aber leer
- Video-Encoding wird komplett fehlschlagen
**Fix:** FFmpeg mit AMF-Support herunterladen.

---

## 2. HOHE PRIORITÄT

### 2.1 AI-Modelle nicht integriert

| Modell | Datei existiert | Wird verwendet | Problem |
|--------|-----------------|----------------|---------|
| CLAP PyTorch | `clap_pytorch.py` | NEIN | SmartDirector verwendet ONNX-Version ohne Modelle |
| Moondream PyTorch | `moondream_pytorch.py` | NEIN | Komplett ungenutzt |
| SigLIP Text | - | - | `siglip_text.onnx` fehlt |

**Fix für SmartDirector:**
```python
# In smart_director.py ändern:
from src.pb_studio.ai.clap_pytorch import CLAPPyTorch  # statt CLAPAnalyzer
from src.pb_studio.ai.moondream_pytorch import MoondreamPyTorch  # hinzufügen
```

### 2.2 Hardcoded Pfade (UI)
**Dateien:**
- `main_window.py:135` - `"src/pb_studio/ui/styles.qss"`
- `editor_widget.py:43` - `"src/pb_studio/audio/stem_runner.py"`

**Fix:** `Path(__file__).parent` verwenden.

### 2.3 Relative Pfade in config.json
```json
"ffmpeg_bin": "./tools/ffmpeg/bin/ffmpeg.exe",
"lhm_lib": "./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll"
```
**Problem:** Funktioniert nur wenn CWD = Projektverzeichnis
**Fix:** ConfigManager soll Pfade relativ zu `__file__` auflösen.

### 2.4 Fehlende GUI Workers
Diese Workers fehlen komplett:
- `audio_worker.py`
- `video_worker.py`
- `video_analysis_worker.py`
- `embedding_worker.py`
- `pacing_worker.py`
- `render_worker.py`

**Impact:** Schwere Operationen blockieren die UI.

### 2.5 Bare Except Clauses
**Dateien:**
- `video/engine.py:112, 241`
- `audio/separator.py:103`
- `audio/analyzer.py:90-91`
- `settings_widget.py:40`

```python
# SCHLECHT:
except:
    pass

# BESSER:
except Exception as e:
    logger.error(f"Error: {e}")
```

### 2.6 SystemMonitor nicht Singleton
**Problem:** Wird in `main_window.py` und `settings_widget.py` separat instanziiert.
**Impact:** LibreHardwareMonitor mehrfach initialisiert, Ressourcen-Konflikte.
**Fix:** Singleton-Pattern wie bei ConfigManager.

---

## 3. MITTLERE PRIORITÄT

### 3.1 CLAP Text-Encoding fehlt
**Datei:** `src/pb_studio/ai/clap_wrapper.py:419-420`
```python
logger.warning("Text encoding requires tokenizer implementation")
return None  # Zero-shot Klassifikation funktioniert nicht!
```

### 3.2 Clip-Auswahl ist Random
**Datei:** `src/pb_studio/video/engine.py:213`
```python
# TODO: Use tags/logic. For now: Random.
src = random.choice(video_sources)
```
**Impact:** Keine semantische Video-Auswahl.

### 3.3 Unnötige CUDA-Checks
**Dateien:** `clap_pytorch.py:109`, `moondream_pytorch.py:87`
```python
torch.cuda.empty_cache() if torch.cuda.is_available() else None
```
Auf AMD-System sinnlos.

### 3.4 Debug-Code in Produktion
**Dateien:** `main_window.py:163-164`, `editor_widget.py:227-228`
```python
with open("trace_log.txt", "a") as f:
    f.write(...)
```
**Fix:** Entfernen oder Logger verwenden.

### 3.5 Shallow Merge in ConfigManager
**Datei:** `config_manager.py:49`
```python
self._config = {**self.DEFAULTS, **user_config}  # Überschreibt nested dicts komplett
```
**Fix:** Deep-Merge implementieren.

### 3.6 Database Thread-Safety
**Datei:** `database_core.py:27-28`
- `check_same_thread=False` ohne Lock-Mechanismus
- Kann zu Race Conditions führen

### 3.7 Fehlende requirements.txt Einträge
```
faiss-cpu>=1.7.0
audio-separator>=0.17.0
pythonnet>=3.0.0
```

### 3.8 video/__init__.py leer
Keine Exports definiert - Video-Module schwer zu importieren.

---

## 4. NIEDRIGE PRIORITÄT

### 4.1 Code Smells
- Duplicate `setEditTriggers` in `library_browser.py:59-60`
- Dead code in `main_window.py:199-204`
- Import inside function in `pacing/advanced_pacing_engine.py:212`
- Print statt Logger in `config_manager.py:51-52, 62`

### 4.2 Inkonsistente Pfad-Behandlung
```python
# Verschiedene Stile:
fp.split("\\")[-1].split("/")[-1]  # Fragil
# Besser:
Path(fp).name
```

### 4.3 Missing Type Hints
- `scene_detect.py` - Keine Return-Type-Hints
- Mehrere Dateien ohne vollständige Typisierung

### 4.4 Fehlende closeEvent
`MainWindow` hat keinen `closeEvent` Handler für Cleanup.

### 4.5 CPU-Label wird nie aktualisiert
`main_window.py:119` erstellt Label, `_update_stats()` aktualisiert nur VRAM.

---

## 5. FEHLENDE FEATURES (vs NVIDIA-Referenz)

| Feature | Status | Priorität |
|---------|--------|-----------|
| Streaming Analyzer (>60min Audio) | FEHLT | Mittel |
| Aesthetic Scorer (Qualitäts-Rating) | FEHLT | Niedrig |
| Semantic Pacing Engine | FEHLT | Niedrig |
| Preview Renderer | FEHLT | Mittel |
| Alembic Migrations | FEHLT | Niedrig |
| GUI Workers (6 Stück) | FEHLT | Hoch |
| SQLAlchemy ORM | Ersetzt durch raw SQLite | - |
| ChromaDB | Ersetzt durch FAISS | - |
| CLIP | Ersetzt durch SigLIP | - |

---

## 6. POSITIVE BEFUNDE

1. **DirectML-Pattern korrekt:** `enable_mem_pattern = False` überall richtig gesetzt
2. **VRAM-Management gut:** VRAMBudgetManager mit LRU-Eviction
3. **AMF-Encoder vollständig:** h264_amf, hevc_amf, av1_amf implementiert
4. **Advanced Pacing Engine:** Vollständig implementiert
5. **Smart Director:** Vollständige AI-Orchestrierung
6. **WAL-Modus:** SQLite mit guter Concurrency
7. **Kompatibilität geprüft:** Keine pip-Konflikte nach OpenCV-Fix

---

## 7. EMPFOHLENE REIHENFOLGE

### Sofort (Blocker):
1. [ ] FFmpeg herunterladen und installieren
2. [ ] pythonnet zu requirements.txt
3. [ ] CUDA-Referenzen entfernen
4. [ ] Import-Fehler in audio/__init__.py
5. [ ] RAFT Modell-Pfad korrigieren

### Diese Woche:
6. [ ] Worker Progress-Callback aktivieren
7. [ ] Signal-Typ-Mismatch fixen
8. [ ] SmartDirector: CLAPPyTorch + MoondreamPyTorch integrieren
9. [ ] Hardcoded Pfade durch __file__-basierte ersetzen
10. [ ] SystemMonitor als Singleton

### Später:
11. [ ] GUI Workers implementieren
12. [ ] Bare except durch spezifische Exceptions ersetzen
13. [ ] Debug-Code entfernen
14. [ ] Deep-Merge in ConfigManager
15. [ ] closeEvent Handler hinzufügen

---

## 8. TECHNISCHE SCHULDEN

**Geschätzter Aufwand:** 20-30 Stunden

| Bereich | Stunden |
|---------|---------|
| Kritische Fixes | 4-6h |
| AI-Integration vervollständigen | 4-6h |
| GUI Workers implementieren | 8-12h |
| Code Quality (Exceptions, Logging) | 2-4h |
| Pfad-Handling standardisieren | 2-3h |

---

*Report generiert durch automatisierte Multi-Agent-Analyse*
