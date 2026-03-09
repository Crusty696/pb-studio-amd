# Pacing Engine Integration Guide

## Overview

The **Pacing Engine** provides intelligent, rhythm-synchronized video editing capabilities for PB Studio. It analyzes audio structure (beats, energy, musical phrases) and generates optimal cut timelines that align with the music.

## Architecture

```
src/pb_studio/pacing/
├── __init__.py                    # Package exports
├── clip_selector.py               # Video clip selection and ranking
└── advanced_pacing_engine.py      # Timeline generation and synchronization
```

## Key Components

### 1. PacingConfig

Configuration dataclass compatible with VideoGenerator:

```python
from src.pb_studio.pacing import PacingConfig, SyncMode

config = PacingConfig(
    pacing=4,                    # 1-5 (slow to fast)
    precision=8,                 # 1-10 (beat snapping strength)
    energy_react=6,              # 0-10 (audio reactivity)
    chaos=3,                     # 0-10 (randomness)
    min_clip_length=2.0,         # seconds
    max_clip_length=8.0,         # seconds
    sync_mode=SyncMode.HYBRID,   # Sync strategy
    allow_transitions=True,
    prefer_downbeats=True
)
```

### 2. AdvancedPacingEngine

Main engine for timeline generation:

```python
from src.pb_studio.pacing import AdvancedPacingEngine
import librosa

# Initialize engine
engine = AdvancedPacingEngine(config)

# Analyze audio
audio_path = "song.mp3"
y, sr = librosa.load(audio_path, sr=22050, mono=True)
rms = librosa.feature.rms(y=y)[0]
times = librosa.times_like(rms, sr=sr)

# Get beat analysis from AudioAnalyzer
from src.pb_studio.audio.analyzer import AudioAnalyzer
analyzer = AudioAnalyzer()
analysis = analyzer.analyze_file(audio_path)

# Plan cuts
engine.analyze_audio_structure(analysis, rms, times)
cuts = engine.plan_cuts(total_duration=librosa.get_duration(y=y, sr=sr))

# Generate EDL
edl = engine.generate_edit_decision_list()
```

### 3. ClipSelector

Intelligent video clip selection using vector embeddings:

```python
from src.pb_studio.pacing import ClipSelector
from src.pb_studio.pacing.clip_selector import ClipMetadata
from src.pb_studio.data.vector_store import VectorStore

# Initialize with vector store
vector_store = VectorStore()
selector = ClipSelector(vector_store)

# Add clips with embeddings
clip = ClipMetadata(
    video_id=1,
    file_path="video.mp4",
    start_time=0.0,
    duration=5.0,
    motion_score=0.8,
    energy_score=0.7,
    tags=["action", "outdoor"],
    embedding=video_embedding  # 768-dim numpy array
)
selector.add_clip(clip)

# Select clips by similarity
query_embedding = get_scene_embedding("fast action scene")
similar_clips = selector.select_by_similarity(query_embedding, k=5)

# Select by energy
high_energy_clips = selector.select_by_energy(energy_level=0.8, tolerance=0.1)

# Hybrid selection
best_clips = selector.select_hybrid(
    query_embedding=query_embedding,
    energy_target=0.7,
    motion_threshold=0.5,
    weights={"similarity": 0.5, "energy": 0.3, "motion": 0.2}
)
```

## Integration with VideoGenerator

### Basic Integration

Replace the `_plan_cuts` method in `video/engine.py`:

```python
from src.pb_studio.pacing import AdvancedPacingEngine, PacingConfig

class VideoGenerator:
    def generate(self, config: dict, callback=None):
        # ... existing code ...

        # 2. Analyze Audio
        analysis = self.analyzer.analyze_file(master_audio)

        import librosa
        y, sr = librosa.load(master_audio, sr=22050, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        times = librosa.times_like(rms, sr=sr)

        # 3. Plan Cuts using Pacing Engine
        pacing_config = PacingConfig(
            pacing=config.get("pacing", 3),
            precision=config.get("precision", 8),
            energy_react=config.get("energy_react", 5),
            chaos=config.get("chaos", 2),
            min_clip_length=config.get("min_dur", 2.0),
            max_clip_length=config.get("max_dur", 8.0)
        )

        engine = AdvancedPacingEngine(pacing_config)
        engine.analyze_audio_structure(analysis, rms, times)
        cuts = engine.plan_cuts(duration)

        # Convert to legacy format
        cut_list = [
            {
                "time": cut.time,
                "duration": cut.duration,
                "energy": cut.energy
            }
            for cut in cuts
        ]

        # 4. Process Segments (existing code)
        processed_segments = self._render_segments(cut_list, source_videos, temp_dir, callback)

        # ... rest of pipeline ...
```

### Advanced Integration with ClipSelector

```python
class VideoGenerator:
    def __init__(self):
        self.analyzer = AudioAnalyzer()
        self.vector_store = VectorStore()
        self.clip_selector = ClipSelector(self.vector_store)

    def _render_segments(self, cut_list, video_sources, temp_dir, callback):
        processed = []

        for i, cut in enumerate(cut_list):
            # Select best clip based on energy level
            energy = cut["energy"]

            # Get clips matching energy
            matching_clips = self.clip_selector.select_by_energy(
                energy_level=energy,
                tolerance=0.2,
                k=5
            )

            if matching_clips:
                # Pick best match
                clip = matching_clips[0]
                src = clip.file_path
                in_point = clip.start_time
            else:
                # Fallback to random
                src = random.choice(video_sources)
                in_point = random.uniform(0, self._get_video_duration(src) - cut["duration"])

            # Render segment
            out_name = temp_dir / f"seg_{i:04d}.mp4"
            self._ffmpeg_extract(src, in_point, cut["duration"], out_name)
            processed.append(out_name)

        return processed
```

## Sync Modes

### BEAT_SYNC
Cuts only on beat boundaries. Best for:
- Electronic music
- Hip-hop
- High-energy content

```python
config = PacingConfig(sync_mode=SyncMode.BEAT_SYNC)
```

### ENERGY_SYNC
Cuts on energy peaks and valleys. Best for:
- Orchestral music
- Dynamic soundtracks
- Cinematic content

```python
config = PacingConfig(sync_mode=SyncMode.ENERGY_SYNC)
```

### EMOTIONAL_SYNC
Cuts on musical phrase boundaries (4-bar, 8-bar). Best for:
- Ballads
- Slow-paced content
- Narrative-driven videos

```python
config = PacingConfig(sync_mode=SyncMode.EMOTIONAL_SYNC)
```

### HYBRID (Recommended)
Combines all strategies for optimal results:

```python
config = PacingConfig(sync_mode=SyncMode.HYBRID)  # Default
```

## Pacing Parameters Explained

### Pacing (1-5)
Controls overall edit speed:
- **1**: Very slow, long clips (8-10s average)
- **3**: Balanced (4-6s average)
- **5**: Very fast, short clips (2-3s average)

### Precision (1-10)
Controls beat alignment strictness:
- **1-3**: Loose alignment, more organic
- **4-7**: Moderate alignment
- **8-10**: Strict alignment, perfect sync

### Energy React (0-10)
Controls responsiveness to audio energy:
- **0**: Ignore energy (constant pacing)
- **5**: Balanced (default)
- **10**: Maximum reactivity (drastic speed changes)

### Chaos (0-10)
Adds creative randomness:
- **0**: Perfectly predictable
- **5**: Moderate variation
- **10**: Maximum creative chaos

## Best Practices

### 1. Match Pacing to Music Genre

```python
# EDM / Electronic
config = PacingConfig(pacing=5, precision=10, energy_react=8)

# Classical / Orchestral
config = PacingConfig(pacing=2, precision=5, energy_react=7, sync_mode=SyncMode.ENERGY_SYNC)

# Hip-Hop / Rap
config = PacingConfig(pacing=3, precision=9, energy_react=6, sync_mode=SyncMode.BEAT_SYNC)

# Ambient / Chill
config = PacingConfig(pacing=1, precision=3, energy_react=4, chaos=1)
```

### 2. Pre-Analyze Video Clips

Generate embeddings for all source videos:

```python
from src.pb_studio.ai.moondream import MoondreamVision

vision = MoondreamVision()
selector = ClipSelector(vector_store)

for video_path in source_videos:
    # Extract keyframe
    frame = extract_keyframe(video_path)

    # Get embedding
    embedding = vision.encode_image(frame)

    # Calculate motion/energy
    motion_score = calculate_optical_flow(video_path)

    # Add to selector
    clip = ClipMetadata(
        video_id=video_id,
        file_path=video_path,
        start_time=0.0,
        duration=get_duration(video_path),
        motion_score=motion_score,
        energy_score=0.5,  # Can be calculated from audio if available
        embedding=embedding
    )
    selector.add_clip(clip)
```

### 3. Use Statistics for Quality Control

```python
# After planning cuts
stats = engine.get_statistics()

print(f"Total cuts: {stats['total_cuts']}")
print(f"Beat alignment: {stats['beat_alignment_ratio']:.1%}")
print(f"Avg clip duration: {stats['avg_cut_duration']:.2f}s")

# Quality check
if stats['beat_alignment_ratio'] < 0.5:
    logger.warning("Low beat alignment - consider increasing precision")
```

## Performance Considerations

- **Timeline generation**: O(n) where n = number of beats
- **Clip selection**: O(log n) with FAISS index
- **Memory usage**: ~100MB per 10,000 video embeddings

For large projects (1000+ source clips):
1. Pre-compute and cache embeddings
2. Use FAISS IndexIVFFlat for faster search
3. Enable parallel segment rendering

## Troubleshooting

### No beats detected
```python
if analysis.get("bpm", 0) == 0:
    # Fallback to time-based cuts
    config = PacingConfig(sync_mode=SyncMode.ENERGY_SYNC)
```

### Cuts too fast/slow
Adjust pacing and clip length constraints:
```python
config = PacingConfig(
    pacing=3,  # Try different values
    min_clip_length=3.0,  # Increase minimum
    max_clip_length=6.0   # Decrease maximum
)
```

### Poor clip selection
Check clip embeddings and energy scores:
```python
stats = selector.get_statistics()
print(f"Avg motion: {stats['avg_motion']}")
print(f"Unique tags: {stats['unique_tags']}")
```

## Future Enhancements

Planned features:
- [ ] Real-time preview with adjustable parameters
- [ ] Machine learning for optimal pacing prediction
- [ ] Advanced transition effects (zoom, slide, warp)
- [ ] Multi-camera synchronization
- [ ] Scene detection integration
- [ ] Genre-specific presets

## API Reference

Full API documentation: [docs/api/pacing.md](api/pacing.md)
