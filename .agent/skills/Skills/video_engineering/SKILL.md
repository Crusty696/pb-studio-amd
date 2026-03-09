---
name: Video Engineering
description: Expert guidelines for processing video, using CLIP for analysis, and managing ffmpeg subprocesses.
---

# Video Engineering Expert Skill

## Core Principles
- **No Blocking:** Video decoding is heavy. Always use threads or subprocesses.
- **FFmpeg:** The engine of PB Studio. Use it for decoding, encoding, and keyframe extraction.
- **Memory Management:** Raw video frames (Bitmap/ndarray) eat RAM fast.

## 1. Frame Extraction (The "Keyframe" Strategy)
- **Problem:** Decoding every frame of a 1hr video is too slow for analysis.
- **Solution:** Extract Keyframes (I-frames) or distinct scene changes.
- **Tool:** `ffmpeg -i input.mp4 -vf "select='gt(scene,0.4)'" -vsync vfr ...`

## 2. CLIP Analysis
- **Model:** `vision_model.onnx` (Visual Encoder) + `text_model.onnx` (Text Encoder).
- **Preprocessing:** Resize to 224x224 (or model specific), Normalize.
- **Batching:** If possible, batch frames for inference (CLIP works well with Batch Size 4-8 on DirectML).

## 3. Playback vs. Analysis
- **Playback:** Use platform native players (QMediaPlayer) or optimized widgets if possible. We process *files*, we don't build a player engine from scratch unless necessary.
- **Analysis:** Happens in the background. Does not affect playback performance.

## 4. Error Resilience
- **Variable Frame Rate (VFR):** iPhone videos are VFR. Always assume timestamps are messy.
- **Codecs:** If `h265` (HEVC) fails (licensing issues), suggest transcoding to `h264` automatically.
