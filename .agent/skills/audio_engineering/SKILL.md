---
name: Audio Engineering
description: Expert guidelines for processing audio, implementing stem separation, and analysis using clean, offline-safe libraries.
---

# Audio Engineering Expert Skill

## Core Principles
- **Offline First:** No APIs. All processing (Stem separation, BPM, formatting) happens locally.
- **Memory Safety:** Audio files can be huge. Never load 2 hours of WAV into RAM at once.
- **Libraries:** `librosa` (Analysis), `soundfile` (IO), `onnxruntime` (AI Models).

## 1. Large File Handling (The "Chunking" Rule)
When processing files > 100MB:
- Use `soundfile.blocks()` or `librosa.stream()` (if available/applicable).
- Process in windows (e.g., 30s chunks) and aggregate results.

## 2. Stem Separation (Demucs ONNX)
- **Model:** `htdemucs_ft.onnx` (Hybrid Transformer).
- **Input:** Must be resampled to 44.1kHz (or model native rate) *before* inference.
- **Output:** The model outputs float32 tensors. Convert to PCM16 only at the final write stage to preserve quality.

## 3. Analysis (BPM, Key)
- **BPM:** `librosa.beat.beat_track` is standard but can be slow. Use `hop_length=512` for speed.
- **Transient Detection:** Use `librosa.onset.onset_detect` for finding "Mix Points".

## 4. Error Handling
- **Corrupt Files:** Always wrap `sf.read()` in try/except. Users *will* try to load renamed `.exe` files as `.mp3`.
- **Duration Check:** Reject files < 1s or > 2GB (Project limits).

## 5. Metadata
- Do not trust file extensions. Use `magic` or header inspection if possible, otherwise rely on `soundfile.info()`.
