# ADR-007: Feature-Implementierungsplan — Fehlende Core-Logik

**Status:** Accepted
**Datum:** 2026-03-04
**Kontext:** Full-Stack-Audit hat ergeben dass ~75% der Core-Logik Stubs sind.

## Priorisierte Phasen

### Phase A: Audio Foundation (SOFORT — Blocking alles andere)
- spectral_analyzer.py: librosa STFT/Mel-Spectrogram (echte Impl.)
- structure_analyzer.py: librosa segment.agglomerative
- key_detection.py: librosa chroma_cqt + essentia (NEU)
- audio_analyzer.py: aggregate alle 4 Analysen in einem Result-Objekt
- waveform_analyzer.py: Fix + Test

### Phase B: Video Foundation
- frame_extractor.py: PySceneDetect echte detect_scenes() Impl.
- MotionAnalyzer: RAFT ONNX Inference (echte Impl.)
- Thumbnail-Rendering im C# Frontend

### Phase C: AI / Smart Director
- clap_wrapper.py: echte CLAP ONNX Inference
- siglip_wrapper.py: echte SigLIP ONNX Inference
- semantic_matcher.py: FAISS-basiertes Cosine-Similarity (kein Mock)

### Phase D: Frontend Interaktivität
- TimelineView: Drag/Trim/Reorder
- Waveform-Visualisierung in C# (SkiaSharp oder WritableBitmap)
- Render-Progress via SSE

## Entscheidungen

**Audio-Libraries:** librosa (MIT) + essentia (Apache 2.0) statt rekordbox
**Motion:** RAFT ONNX (bereits geplant) — implementieren statt Stub lassen
**AI-Inference:** CLAP + SigLIP via onnxruntime-directml (bereits in requirements)
**Frontend-Waveform:** SkiaSharp (NuGet) für GPU-beschleunigte Waveform-Darstellung
