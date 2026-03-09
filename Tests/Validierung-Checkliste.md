# Validierung - Checkliste

**Stand:** 2026-02-12
**Projekt:** PB Studio AMD Premium Edition
**Status:** ~95% implementiert

---

## Umgebung

- [ ] Python 3.10 oder 3.11 installiert (NICHT 3.12+)
- [ ] numpy==1.26.4 installiert (< 2.0 Pflicht)
- [ ] onnxruntime-directml installiert (NICHT onnxruntime-gpu!)
- [ ] DmlExecutionProvider verfuegbar
- [ ] FFmpeg mit AMF-Support installiert (h264_amf, hevc_amf)
- [ ] AMD Adrenalin Treiber 24.x oder neuer
- [ ] LibreHardwareMonitorLib.dll in lib/ vorhanden
- [ ] qt-material installiert
- [ ] PyQt6 installiert
- [ ] `python verify_env_v2.py` laeuft ohne Fehler

---

## Audio Bereich

### Beat Detection (BeatNet)
- [ ] BeatNet importierbar (erfordert Python 3.10/3.11)
- [ ] BPM-Erkennung funktioniert (`AudioAnalyzer.analyze_file()`)
- [ ] Beat-Timestamps werden zurueckgegeben
- [ ] FFmpeg-Vorkonvertierung zu WAV funktioniert

### Stem Separation (Demucs via audio-separator)
- [ ] audio-separator installiert
- [ ] DirectML-Patch aktiv (`StemSeparator._init_engine()`)
- [ ] ONNX Session mit DmlExecutionProvider
- [ ] 4 Stems werden generiert (Vocals, Drums, Bass, Other)
- [ ] Qualitaet akzeptabel

### Waveform Analyse
- [ ] Waveform-Daten werden korrekt generiert
- [ ] Caching funktioniert (waveform_cache.py)

### CLAP Audio Embedding (AI)
- [ ] CLAP ONNX-Modell ladbar (clap_wrapper.py)
- [ ] DirectML Session mit `enable_mem_pattern = False`
- [ ] Audio-Embeddings 512-dimensional
- [ ] Mood/Genre/Instrument-Tags werden generiert
- [ ] Zero-Shot-Klassifikation funktioniert

---

## Video Bereich

### Scene Detection (PySceneDetect)
- [ ] PySceneDetect funktioniert (`SceneDetector.detect_scenes()`)
- [ ] Szenen werden als (start_sec, end_sec) Tupel zurueckgegeben
- [ ] ContentDetector mit konfigurierbarem Threshold

### Vision-Language Model (Moondream2 ONNX)
- [ ] Moondream ONNX-Modell geladen (moondream.py)
- [ ] DirectML Session mit `enable_mem_pattern = False`
- [ ] Bild-Captions werden generiert
- [ ] CPU-Fallback funktioniert
- [ ] VRAM-Verbrauch akzeptabel

### Optical Flow (RAFT ONNX)
- [ ] RAFT ONNX-Modell geladen (raft.py)
- [ ] DirectML Session mit `enable_mem_pattern = False`
- [ ] Flow zwischen zwei Frames berechenbar
- [ ] Motion-Magnitude als Skalar verfuegbar
- [ ] Scene-Change-Detection ueber Flow funktioniert

### SigLIP Image Embedding (AI)
- [ ] SigLIP ONNX-Modell ladbar (siglip_wrapper.py)
- [ ] DirectML Session mit `enable_mem_pattern = False`
- [ ] Bild-Embeddings 1152-dimensional (SO400M)
- [ ] Text-Embeddings fuer Zero-Shot verfuegbar
- [ ] Cosine-Similarity korrekt

### FAISS Vector Store
- [ ] FAISS Index erstellt/geladen (vector_store.py)
- [ ] Dimension konfigurierbar (Standard: 1152 fuer SigLIP)
- [ ] Add/Search funktioniert
- [ ] Metadata als JSON persistiert
- [ ] Dimensions-Mismatch wird abgefangen

---

## Pacing Bereich

### Advanced Pacing Engine
- [ ] Beat-Sync Modus funktioniert
- [ ] Energy-Sync Modus funktioniert
- [ ] Hybrid-Modus funktioniert
- [ ] Transitions (Cut, Fade, Crossfade) werden generiert
- [ ] EDL (Edit Decision List) kompatibel mit VideoGenerator

### Smart Director (AI Pipeline)
- [ ] CLAP-Analyse -> Mood/Energy-Kurve
- [ ] SigLIP-Analyse -> Clip-Embeddings + Content-Tags
- [ ] Audio-Video Semantic Matching
- [ ] Timeline-Generierung
- [ ] "Staffellauf" VRAM-Pattern (nur ein schweres Modell gleichzeitig)
- [ ] Integration in GenerationService
- [ ] Integration in VideoGenerator (generate_from_timeline)
- [ ] UI-Checkbox "Use AI Smart Director" vorhanden

---

## Rendering Bereich

### FFmpeg AMF Encoding
- [ ] h264_amf verfuegbar und funktioniert
- [ ] hevc_amf verfuegbar und funktioniert
- [ ] av1_amf verfuegbar (nur RDNA3+, optional)
- [ ] Software-Fallback (libx264) bei fehlendem AMF
- [ ] Quality-Presets (speed/balanced/quality)
- [ ] Rate-Control-Modi (CQP, CBR, VBR)
- [ ] 1080p Encoding ohne Artefakte
- [ ] VideoGenerator.render_segment() funktioniert
- [ ] VideoGenerator.concat_segments() funktioniert

---

## GPU Monitoring

### LibreHardwareMonitor Integration
- [ ] DLL wird geladen (SystemMonitor._initialize_lhm())
- [ ] GPU erkannt (AMD Radeon)
- [ ] VRAM-Nutzung abfragbar
- [ ] GPU-Temperatur abfragbar
- [ ] CPU/RAM-Monitoring funktioniert

### VRAM Arbiter
- [ ] VRAM-Budget korrekt konfiguriert (vram_arbiter.py)
- [ ] Model-Allokation funktioniert
- [ ] Automatische VRAM-Bereinigung

---

## Worker-System

### Orchestrator
- [ ] Worker-Registry korrekt initialisiert
- [ ] Audio-Import-Worker funktioniert
- [ ] Video-Import-Worker funktioniert
- [ ] Scene-Detection-Worker funktioniert
- [ ] Motion-Analysis-Worker funktioniert
- [ ] Vision-Worker (Moondream) funktioniert
- [ ] Pacing-Worker funktioniert
- [ ] Render-Worker funktioniert
- [ ] Concat-Worker funktioniert
- [ ] Export-Worker funktioniert

---

## UI Bereich

### Hauptfenster
- [ ] App startet mit `python run_ui.py`
- [ ] qt-material Dark Theme geladen
- [ ] Navigation zwischen Tabs funktioniert (Dashboard/Library/Editor/Analysis/Generation)

### Dashboard
- [ ] "New Project" Button funktioniert (erstellt Projekt in DB)
- [ ] "Open Project" Button funktioniert (zeigt Projektauswahl)
- [ ] Projekt-Wechsel aktualisiert Library und Fenstertitel

### Library Browser
- [ ] Dateien importierbar (Audio + Video)
- [ ] Dateiliste wird angezeigt

### Analysis
- [ ] Audio-Analyse-Step funktioniert
- [ ] Video-Analyse-Step funktioniert
- [ ] AI-Analyse-Step funktioniert
- [ ] Analyse-Queue verwaltet Auftraege

### Generation
- [ ] Pacing-Config einstellbar
- [ ] Smart Director Checkbox vorhanden
- [ ] Render-Progress wird angezeigt
- [ ] Export funktioniert

---

## End-to-End Test

- [ ] Vollstaendiger Pipeline-Durchlauf
- [ ] Audio importieren -> BeatNet Analyse -> Stems -> CLAP Embedding
- [ ] Video importieren -> Scene Detection -> Moondream Captions -> RAFT Flow -> SigLIP Embedding
- [ ] Pacing Engine -> Timeline -> VideoGenerator -> Output-Video
- [ ] Smart Director Modus (CLAP + SigLIP -> AI Timeline -> Render)

---

## Performance (Richtwerte)

| Komponente | Ziel | Erreicht |
|------------|------|----------|
| SigLIP Inferenz | <200ms/Bild | [ ] |
| Moondream Inferenz | <3s/Bild | [ ] |
| CLAP Audio-Encoding | <500ms/10s Audio | [ ] |
| RAFT Optical Flow | <200ms/Frame-Paar | [ ] |
| Stem Separation | <Echtzeit | [ ] |
| AMF Encoding | >30 FPS (1080p) | [ ] |

---

## VRAM Monitoring

Peak VRAM waehrend Pipeline: _______ GB / 16 GB
Staffellauf-Muster korrekt (max 1 schweres Modell): [ ] Ja / [ ] Nein

---

## Test-Suite

```bash
# Alle Tests ausfuehren
pytest Tests/ -v

# Verfuegbare Test-Module
pytest Tests/test_config_manager.py -v      # Config Manager
pytest Tests/test_audio_analyzer.py -v       # BeatNet Audio Analyse
pytest Tests/test_separator.py -v            # Stem Separation
pytest Tests/test_waveform_analyzer.py -v    # Waveform
pytest Tests/test_vram_arbiter.py -v         # VRAM Management
pytest Tests/test_pacing_engine.py -v        # Pacing Engine
pytest Tests/test_clap_wrapper.py -v         # CLAP Audio AI
pytest Tests/test_siglip_video.py -v         # SigLIP Video AI
pytest Tests/test_vector_store.py -v         # FAISS Vector Store
pytest Tests/test_smart_director_integration.py -v  # Smart Director
```

---

*Checkliste aktualisiert: 2026-02-12*
*Basierend auf tatsaechlichem Codebase-Stand*
