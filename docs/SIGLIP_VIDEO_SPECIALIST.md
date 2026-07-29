# SigLIP Video Specialist - Documentation

> **Current contract (2026-07-29):** Python 3.11.x, NumPy 1.26.4,
> SigLIP SO400M ONNX (1152 dimensions), `DmlExecutionProvider` only, and both
> DirectML memory flags disabled. Package-install/export commands and API
> examples below are historical reference; use the project runtime and active
> wrapper contracts. Missing DML/model artifacts fail closed.

## Overview

The SigLIP Video Specialist provides advanced video analysis capabilities for PB Studio AMD using SigLIP (Sigmoid Loss for Language-Image Pre-training) embeddings. All processing is optimized for AMD GPUs via DirectML.

## Architecture

### Components

1. **SigLIPWrapper** (`src/pb_studio/ai/siglip_wrapper.py`)
   - Image and text embedding using SigLIP model
   - Zero-shot image classification
   - ONNX Runtime with DirectML acceleration

2. **VideoSpecialist** (`src/pb_studio/ai/video_specialist.py`)
   - Keyframe extraction from videos
   - Video embedding computation
   - Clip similarity search
   - Video tagging with text labels

3. **VideoClip** (Data class)
   - Represents video clips with embeddings
   - Stores metadata and time ranges

## SigLIP Model

### Model Details
- **Model**: google/siglip-so400m-patch14-384
- **Input Size**: 384x384 RGB images
- **Embedding Dimension**: 1152
- **Architecture**: Vision Transformer (ViT-SO400M, patch size 14)

### Required Files
```
models/
├── siglip_vision.onnx      # Vision encoder (required)
├── siglip_text.onnx         # Text encoder (optional, for tagging)
└── siglip_tokenizer/        # Tokenizer files (optional)
```

## AMD DirectML Configuration

### Critical Settings

All models use the following DirectML pattern:

```python
import onnxruntime as ort

sess_options = ort.SessionOptions()
sess_options.enable_mem_pattern = False  # MANDATORY for DirectML!
sess_options.enable_cpu_mem_arena = False  # MANDATORY for DirectML!
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

providers = [
    'DmlExecutionProvider',  # AMD GPU; no CPU fallback
]

session = ort.InferenceSession(
    model_path,
    sess_options=sess_options,
    providers=providers
)
```

### Why `enable_mem_pattern = False`?

DirectML requires `enable_mem_pattern = False` to avoid memory corruption and crashes. This is a known requirement for DirectML execution.

## Usage

### 1. Image Encoding

```python
from pb_studio.ai import SigLIPWrapper
from PIL import Image

# Initialize wrapper
siglip = SigLIPWrapper()

# Load image
image = Image.open("frame.jpg")

# Encode to embedding [1152]
embedding = siglip.encode_image(image)

print(f"Embedding shape: {embedding.shape}")  # (1152,)
```

### 2. Batch Image Encoding

```python
images = [Image.open(f"frame_{i}.jpg") for i in range(10)]

# Encode batch
embeddings = siglip.encode_images_batch(images)

print(f"Batch shape: {embeddings.shape}")  # (10, 1152)
```

### 3. Text Encoding (Zero-shot Classification)

```python
# Encode text labels
texts = ["a photo of a cat", "a photo of a dog", "a landscape"]
text_embeddings = siglip.encode_text(texts)

# Classify image
results = siglip.classify_image(image, texts)

for label, score in results:
    print(f"{label}: {score:.3f}")
```

### 4. Video Analysis

```python
from pb_studio.ai import VideoSpecialist

# Initialize specialist
specialist = VideoSpecialist()

# Extract keyframes
frames = specialist.extract_keyframes("video.mp4", interval=1.0)
print(f"Extracted {len(frames)} keyframes")

# Compute video embedding
video_embedding = specialist.embed_video("video.mp4", interval=1.0)
print(f"Video embedding shape: {video_embedding.shape}")  # (1152,)
```

### 5. Clip Management

```python
# Add clips to database
clip1 = specialist.add_clip(
    video_path="video.mp4",
    start_time=0.0,
    end_time=5.0,
    metadata={"scene": "intro"},
    compute_embedding=True
)

clip2 = specialist.add_clip(
    video_path="video.mp4",
    start_time=5.0,
    end_time=10.0,
    metadata={"scene": "action"},
    compute_embedding=True
)

print(f"Total clips: {specialist.num_clips}")
```

### 6. Similarity Search

```python
# Find similar clips
query_embedding = specialist.embed_video("query_video.mp4")

similar_clips = specialist.find_similar_clips(
    query_embedding,
    k=5,
    min_score=0.5
)

for clip, score in similar_clips:
    print(f"{clip.video_path} [{clip.start_time:.1f}-{clip.end_time:.1f}s]: {score:.3f}")
```

### 7. Video Tagging

```python
# Tag video with text labels
tags = ["action", "calm", "outdoor", "indoor", "night", "day"]

tag_scores = specialist.tag_video(
    video_path="video.mp4",
    tags=tags,
    interval=2.0,
    threshold=0.3
)

for tag, score in tag_scores.items():
    print(f"{tag}: {score:.3f}")
```

### 8. Video Metadata

```python
metadata = specialist.get_video_metadata("video.mp4")

print(f"Duration: {metadata['duration']:.2f}s")
print(f"Resolution: {metadata['width']}x{metadata['height']}")
print(f"FPS: {metadata['fps']:.2f}")
print(f"Frames: {metadata['frame_count']}")
```

## Integration with Vector Store

The VideoSpecialist can integrate with PB Studio's FAISS vector store for persistent storage:

```python
from pb_studio.data.vector_store import VectorStore

# Create vector store
vector_store = VectorStore(index_name="video_clips")

# Initialize specialist with vector store
specialist = VideoSpecialist(vector_store=vector_store)

# Add clips (automatically stored in vector store)
clip = specialist.add_clip("video.mp4", 0.0, 5.0, compute_embedding=True)

# Search using vector store
results = specialist.find_similar_clips(query_embedding, k=10)

# Save vector store
vector_store.save()
```

## Performance Optimization

### Keyframe Extraction

- **Interval**: Higher intervals (2-5 seconds) reduce processing time
- **Max Frames**: Limit frames for long videos (e.g., max_frames=20)

```python
# Fast: Extract every 3 seconds, max 15 frames
embedding = specialist.embed_video("long_video.mp4", interval=3.0, max_frames=15)
```

### Aggregation Methods

Choose aggregation method based on use case:

```python
# Mean: Smooth, balanced representation (default)
embedding = specialist.embed_video("video.mp4", aggregation="mean")

# Max: Emphasizes strongest features
embedding = specialist.embed_video("video.mp4", aggregation="max")

# Median: Robust to outliers
embedding = specialist.embed_video("video.mp4", aggregation="median")
```

### GPU Memory Management

The VideoSpecialist processes frames sequentially to minimize VRAM usage. For large batches, consider:

```python
# Process videos in chunks
video_paths = [f"video_{i}.mp4" for i in range(100)]

for video_path in video_paths:
    embedding = specialist.embed_video(video_path)
    # Store embedding
    # ...
    # Optionally: specialist.siglip.unload() to free VRAM
```

## Testing

Run the test suite:

```powershell
# All tests
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest Tests/test_siglip_video.py -v

# Specific test class
.\.venv\Scripts\python.exe -m pytest Tests/test_siglip_video.py::TestSigLIPWrapper -v

# With coverage
.\.venv\Scripts\python.exe -m pytest Tests/test_siglip_video.py --cov=src.pb_studio.ai -v
```

Note: Some tests require model files to be present. Tests will skip gracefully if models are not available.

## Error Handling

The modules provide comprehensive error handling:

```python
# Check if models are ready
if not siglip.is_ready:
    print("Vision model not loaded")

if not siglip.has_text_encoder:
    print("Text encoder not available")

# Safe encoding with error checking
embedding = siglip.encode_image(image)
if embedding is None:
    print("Encoding failed")
```

## Logging

Enable debug logging for troubleshooting:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("src.pb_studio.ai")
logger.setLevel(logging.DEBUG)
```

## Model Provisioning

SigLIP assets are external release inputs. This repository intentionally has
no downloader or exporter. Only an approved release artifact may provide
`siglip_vision.onnx` and optional `siglip_text.onnx`; missing assets remain an
explicit unavailable state.

## Compatibility

### Python Version
- **Required**: Python 3.11.x
- Python 3.12+ not supported (BeatNet compatibility)

### Dependencies
- `onnxruntime-directml==1.19.2` (AMD GPU acceleration)
- `transformers==4.49.0` (tokenizer)
- `pillow>=10.0.0` (image processing)
- `opencv-python==4.9.0.80` (video processing)
- `numpy==1.26.4` (numerical operations)

### Hardware
- **GPU**: AMD Radeon with DirectML support
- **VRAM**: Minimum 4GB recommended
- **CPU Fallback**: None. Missing DirectML is an explicit error.

## Troubleshooting

### "DmlExecutionProvider not found"

Do not install or replace packages from this guide. Verify the locked project
runtime and fail closed until `DmlExecutionProvider` is available.

### "Vision model not loaded"
Ensure `siglip_vision.onnx` exists in models directory.

### "Tokenizer not initialized"
- Restore the locked project environment from `requirements.txt`.
- Text encoding remains unavailable without the registered local tokenizer.

### "Failed to open video"
- Check video file exists
- Verify FFmpeg is installed
- Check video codec compatibility with OpenCV

## Future Enhancements

- [ ] Batch inference optimization for multiple frames
- [ ] Temporal aggregation methods (LSTM, attention)
- [ ] Scene segmentation integration
- [ ] Real-time video stream analysis
- [ ] Multi-video similarity matrix computation
- [ ] GPU memory pooling for large-scale processing

## References

- [SigLIP Paper](https://arxiv.org/abs/2303.15343)
- [ONNX Runtime DirectML](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html)
- [PB Studio Architecture](architecture/ADR-002-csharp-wpf-fastapi-hybrid.md)
