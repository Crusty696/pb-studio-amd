# SigLIP Video Specialist - Quick Start

> **Current contract (2026-07-29):** Python 3.11.x, NumPy 1.26.4,
> project-managed dependencies, SigLIP SO400M ONNX with 1152-dimensional
> embeddings, and `DmlExecutionProvider` only. Missing DML or model artifacts
> is an explicit unavailable/error state; there is no CPU fallback.
> Approved source:
> `google/siglip-so400m-patch14-384@9fdffc58afc957d1a03a25b10dba0329ab15c2a3`,
> license `Apache-2.0`. Exact source/target hashes and transform:
> [`config/directml-model-assets.json`](../config/directml-model-assets.json).

## Installation

### 1. Ensure Dependencies

Use the locked project environment. Do not install or upgrade individual
packages from this guide.

### 2. Verify registered models

Model assets are accepted only through the approved, hash-bound model
registry/manifest workflow. Do not download, export or place arbitrary ONNX
files from this guide. Without registered `siglip_vision` the capability is
unavailable; without registered `siglip_text`, text tagging is unavailable.
The approved release archive is bound by
[`config/directml-asset-bundle.json`](../config/directml-asset-bundle.json);
this repository intentionally contains no arbitrary model downloader or
exporter.

## Quick Examples

### Image Encoding

```python
from pb_studio.ai import SigLIPWrapper
from PIL import Image

siglip = SigLIPWrapper()
image = Image.open("photo.jpg")
embedding = siglip.encode_image(image)  # [1152]
```

### Video Embedding

```python
from pb_studio.ai import VideoSpecialist

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
sess_options.enable_cpu_mem_arena = False  # MANDATORY!

providers = ['DmlExecutionProvider']
```

## Testing

```powershell
# Run tests
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest Tests/test_siglip_video.py -v

# Quick smoke test
.\.venv\Scripts\python.exe -c "from pb_studio.ai import SigLIPWrapper; print(SigLIPWrapper().is_ready)"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "DmlExecutionProvider not found" | Run the approved setup/runtime validation; do not mutate dependencies ad hoc |
| "Vision model not loaded" | Capability remains unavailable until an approved manifest registers the asset |
| "Tokenizer not initialized" | Text tagging remains unavailable; do not download at runtime |
| Slow performance | Increase `interval`, reduce `max_frames` |
| High VRAM usage | Process videos sequentially, call `siglip.unload()` |

## Documentation

- Full documentation: [SIGLIP_VIDEO_SPECIALIST.md](SIGLIP_VIDEO_SPECIALIST.md)
- Usage examples: [examples/siglip_video_example.py](examples/siglip_video_example.py)
- Test suite: [Tests/test_siglip_video.py](../Tests/test_siglip_video.py)

## Integration

> The direct `VectorStore`/`VideoGenerator` sketches below are historical
> prototypes and are not the active project-media or pacing integration.
> Production callers use registered media IDs through the backend services.

### With Vector Store
```python
from pb_studio.data.vector_store import VectorStore

vector_store = VectorStore(index_name="clips")
specialist = VideoSpecialist(vector_store=vector_store)

# Clips are automatically indexed
clip = specialist.add_clip("video.mp4", 0, 5, compute_embedding=True)
vector_store.save()
```

### With Video Engine
```python
from pb_studio.video.engine import VideoGenerator

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

1. Verify the approved model manifest and DirectML provider.
2. Import media into the active project catalog.
3. Run the T332 hardware/regression gates before treating the capability as
   operational.
