# SigLIP Video Specialist - Quick Start

## Installation

### 1. Ensure Dependencies
```bash
pip install onnxruntime-directml>=1.16.0
pip install transformers>=4.48.0
pip install pillow>=10.0.0
pip install opencv-python-headless>=4.9.0
```

### 2. Download Models

Place the following files in `models/` directory:
- `siglip_vision.onnx` (required)
- `siglip_text.onnx` (optional, for tagging)
- `siglip_tokenizer/` (optional, for text encoding)

## Quick Examples

### Image Encoding

```python
from src.pb_studio.ai import SigLIPWrapper
from PIL import Image

siglip = SigLIPWrapper()
image = Image.open("photo.jpg")
embedding = siglip.encode_image(image)  # [1152]
```

### Video Embedding

```python
from src.pb_studio.ai import VideoSpecialist

specialist = VideoSpecialist()
embedding = specialist.embed_video("video.mp4", interval=1.0)  # [1152]
```

### Video Tagging

```python
tags = ["action", "calm", "outdoor", "indoor"]
scores = specialist.tag_video("video.mp4", tags, threshold=0.3)

for tag, score in scores.items():
    print(f"{tag}: {score:.3f}")
```

### Clip Search

```python
# Add clips to database
clip1 = specialist.add_clip("video.mp4", start_time=0.0, end_time=5.0)
clip2 = specialist.add_clip("video.mp4", start_time=5.0, end_time=10.0)

# Find similar clips
query_emb = specialist.embed_video("query.mp4")
results = specialist.find_similar_clips(query_emb, k=5)

for clip, score in results:
    print(f"{clip}: {score:.3f}")
```

## Key Features

| Feature | Method | Description |
|---------|--------|-------------|
| Image Encoding | `encode_image()` | Convert image to 1152-dim embedding |
| Text Encoding | `encode_text()` | Convert text to 1152-dim embedding |
| Video Embedding | `embed_video()` | Average frame embeddings |
| Keyframe Extract | `extract_keyframes()` | Sample frames from video |
| Zero-shot Classification | `classify_image()` | Classify image with text labels |
| Video Tagging | `tag_video()` | Tag video with semantic labels |
| Clip Search | `find_similar_clips()` | Find similar video clips |

## Performance Tips

### Fast Processing
```python
# Use higher intervals and frame limits
embedding = specialist.embed_video(
    "video.mp4",
    interval=3.0,      # Sample every 3 seconds
    max_frames=15,     # Max 15 frames
    aggregation="mean" # Fast aggregation
)
```

### Quality Processing
```python
# Use lower intervals and more frames
embedding = specialist.embed_video(
    "video.mp4",
    interval=0.5,      # Sample every 0.5 seconds
    max_frames=50,     # Up to 50 frames
    aggregation="median" # Robust aggregation
)
```

## AMD DirectML Settings

All models use this critical configuration:

```python
import onnxruntime as ort

sess_options = ort.SessionOptions()
sess_options.enable_mem_pattern = False  # MANDATORY!

providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
```

## Testing

```bash
# Run tests
pytest tests/test_siglip_video.py -v

# Quick smoke test
python -c "from src.pb_studio.ai import SigLIPWrapper; print(SigLIPWrapper().is_ready)"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "DmlExecutionProvider not found" | `pip install onnxruntime-directml` |
| "Vision model not loaded" | Download `siglip_vision.onnx` to `models/` |
| "Tokenizer not initialized" | Install `transformers` or download tokenizer |
| Slow performance | Increase `interval`, reduce `max_frames` |
| High VRAM usage | Process videos sequentially, call `siglip.unload()` |

## Documentation

- Full documentation: [SIGLIP_VIDEO_SPECIALIST.md](SIGLIP_VIDEO_SPECIALIST.md)
- Usage examples: [examples/siglip_video_example.py](examples/siglip_video_example.py)
- Test suite: [tests/test_siglip_video.py](../tests/test_siglip_video.py)

## Integration

### With Vector Store
```python
from src.pb_studio.data.vector_store import VectorStore

vector_store = VectorStore(index_name="clips")
specialist = VideoSpecialist(vector_store=vector_store)

# Clips are automatically indexed
clip = specialist.add_clip("video.mp4", 0, 5, compute_embedding=True)
vector_store.save()
```

### With Video Engine
```python
from src.pb_studio.video.engine import VideoGenerator

# Use embeddings for intelligent clip selection
generator = VideoGenerator()
config = {
    "source_videos": ["video1.mp4", "video2.mp4"],
    # ... other config
}

# Compute embeddings for source videos
for video in config["source_videos"]:
    embedding = specialist.embed_video(video)
    # Use for semantic matching
```

## Model Information

| Property | Value |
|----------|-------|
| Model | google/siglip-so400m-patch14-384 |
| Input Size | 384x384 RGB |
| Embedding Dim | 1152 |
| Architecture | ViT-SO400M (patch 14) |
| Normalization | Mean/Std = 0.5 |

## Next Steps

1. Download SigLIP ONNX models
2. Run example script: `python docs/examples/siglip_video_example.py`
3. Integrate with your video pipeline
4. Read full documentation for advanced features
