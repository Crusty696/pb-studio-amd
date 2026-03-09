# Pacing Engine for PB Studio

## Overview

The **Pacing Engine** provides intelligent, rhythm-synchronized video editing for PB Studio AMD Edition. It analyzes audio structure (beats, tempo, energy) and generates optimal video cut timelines that align perfectly with musical elements.

## Features

- **Multiple Sync Modes**: Beat Sync, Energy Sync, Emotional Sync, and Hybrid
- **Sub-frame Precision**: Accurate beat alignment with configurable snapping
- **Energy Curve Analysis**: Dynamic pacing based on audio intensity
- **Vector-based Clip Selection**: FAISS-powered semantic clip matching
- **Transition Intelligence**: Automatic transition type selection
- **Musical Structure Recognition**: Detects downbeats and phrase boundaries
- **Genre-Specific Presets**: Optimized configurations for different music styles

## Quick Start

### Basic Timeline Generation

```python
from pb_studio.pacing import AdvancedPacingEngine, PacingConfig
from pb_studio.audio.analyzer import AudioAnalyzer
import librosa

# 1. Analyze audio
analyzer = AudioAnalyzer()
analysis = analyzer.analyze_file("song.mp3")

# 2. Get energy curve
y, sr = librosa.load("song.mp3", sr=22050)
rms = librosa.feature.rms(y=y)[0]
times = librosa.times_like(rms, sr=sr)
duration = librosa.get_duration(y=y, sr=sr)

# 3. Configure and generate
config = PacingConfig(pacing=4, precision=8)
engine = AdvancedPacingEngine(config)
engine.analyze_audio_structure(analysis, rms, times)
cuts = engine.plan_cuts(duration)

# 4. Use cuts for video generation
for cut in cuts:
    print(f"Cut at {cut.time:.2f}s, duration {cut.duration:.2f}s")
```

### Intelligent Clip Selection

```python
from pb_studio.pacing import ClipSelector
from pb_studio.pacing.clip_selector import ClipMetadata
from pb_studio.data.vector_store import VectorStore

# Initialize with vector store
selector = ClipSelector(VectorStore())

# Add clips with embeddings
clip = ClipMetadata(
    video_id=1,
    file_path="video.mp4",
    start_time=0.0,
    duration=10.0,
    motion_score=0.8,
    energy_score=0.7,
    tags=["action", "outdoor"],
    embedding=your_embedding_vector  # 768-dim numpy array
)
selector.add_clip(clip)

# Select best matching clips
query = get_embedding("fast action scene")
matches = selector.select_by_similarity(query, k=5)
```

## Configuration

### PacingConfig Parameters

| Parameter | Range | Description |
|-----------|-------|-------------|
| `pacing` | 1-5 | Overall edit speed (1=slow, 5=fast) |
| `precision` | 1-10 | Beat alignment strictness (10=perfect sync) |
| `energy_react` | 0-10 | Responsiveness to audio energy |
| `chaos` | 0-10 | Creative randomness/variation |
| `min_clip_length` | float | Minimum clip duration (seconds) |
| `max_clip_length` | float | Maximum clip duration (seconds) |
| `sync_mode` | enum | Synchronization strategy |

### Sync Modes

- **BEAT_SYNC**: Cuts exactly on beat boundaries (best for EDM, Hip-Hop)
- **ENERGY_SYNC**: Cuts on energy peaks/valleys (best for orchestral, cinematic)
- **EMOTIONAL_SYNC**: Cuts on musical phrases (best for ballads, slow content)
- **HYBRID**: Combines all strategies (recommended default)

## Integration with VideoGenerator

Replace the `_plan_cuts` method in `video/engine.py`:

```python
from pb_studio.pacing import AdvancedPacingEngine, PacingConfig

def _plan_cuts(self, config, analysis, rms, times, duration):
    # Create pacing config
    pacing_config = PacingConfig(
        pacing=config.get("pacing", 3),
        precision=config.get("precision", 8),
        energy_react=config.get("energy_react", 5),
        chaos=config.get("chaos", 2),
        min_clip_length=config.get("min_dur", 2.0),
        max_clip_length=config.get("max_dur", 8.0)
    )

    # Generate timeline
    engine = AdvancedPacingEngine(pacing_config)
    engine.analyze_audio_structure(analysis, rms, times)
    cuts = engine.plan_cuts(duration)

    # Convert to legacy format
    return [
        {
            "time": cut.time,
            "duration": cut.duration,
            "energy": cut.energy
        }
        for cut in cuts
    ]
```

## Genre Presets

```python
# EDM / Electronic
edm_config = PacingConfig(
    pacing=5, precision=10, energy_react=8, chaos=3,
    min_clip_length=1.5, max_clip_length=4.0,
    sync_mode=SyncMode.BEAT_SYNC
)

# Classical / Orchestral
classical_config = PacingConfig(
    pacing=2, precision=5, energy_react=7, chaos=1,
    min_clip_length=4.0, max_clip_length=10.0,
    sync_mode=SyncMode.ENERGY_SYNC
)

# Hip-Hop
hiphop_config = PacingConfig(
    pacing=3, precision=9, energy_react=6, chaos=4,
    sync_mode=SyncMode.BEAT_SYNC
)

# Ambient / Chill
ambient_config = PacingConfig(
    pacing=1, precision=3, energy_react=4, chaos=2,
    min_clip_length=5.0, max_clip_length=15.0,
    sync_mode=SyncMode.EMOTIONAL_SYNC
)
```

## Architecture

```
pacing/
├── __init__.py                    # Package exports
├── clip_selector.py               # Video clip selection (500 lines)
│   ├── ClipMetadata               # Clip information dataclass
│   └── ClipSelector               # Selection engine
└── advanced_pacing_engine.py      # Timeline generation (700 lines)
    ├── PacingConfig               # Configuration
    ├── CutPoint                   # Cut decision dataclass
    ├── SyncMode                   # Synchronization strategies
    ├── TransitionType             # Transition types
    └── AdvancedPacingEngine       # Main engine
```

## API Reference

### AdvancedPacingEngine

**Methods:**
- `analyze_audio_structure(analysis, rms, times)` - Process audio data
- `plan_cuts(total_duration)` - Generate cut timeline
- `generate_edit_decision_list()` - Export EDL format
- `get_statistics()` - Get timeline statistics

### ClipSelector

**Methods:**
- `add_clip(clip)` - Add clip to selection pool
- `select_by_similarity(query, k)` - Semantic similarity search
- `select_by_motion(threshold, operator, k)` - Motion filtering
- `select_by_energy(level, tolerance, k)` - Energy matching
- `select_by_tags(tags, any_match, k)` - Tag filtering
- `select_hybrid(...)` - Multi-criteria selection
- `get_statistics()` - Get pool statistics

## Examples

See `docs/examples/pacing_example.py` for complete working examples:
1. Basic timeline generation
2. Sync mode comparison
3. Intelligent clip selection
4. Genre-specific presets
5. Full VideoGenerator integration

## Performance

- **Timeline Generation**: O(n) where n = number of beats
- **Clip Selection**: O(log n) with FAISS index
- **Memory Usage**: ~100MB per 10,000 video embeddings

For optimal performance:
- Pre-compute and cache video embeddings
- Use FAISS IndexIVFFlat for large clip databases
- Enable parallel segment rendering

## Testing

```bash
# Run all tests
python -m pytest tests/test_pacing_engine.py -v

# Run specific test class
python -m pytest tests/test_pacing_engine.py::TestAdvancedPacingEngine -v

# Run with coverage
python -m pytest tests/test_pacing_engine.py --cov=src.pb_studio.pacing
```

## Troubleshooting

**Problem**: No beats detected
```python
# Solution: Use energy-based sync
if analysis.get("bpm", 0) == 0:
    config = PacingConfig(sync_mode=SyncMode.ENERGY_SYNC)
```

**Problem**: Cuts too fast/slow
```python
# Solution: Adjust pacing and clip constraints
config = PacingConfig(
    pacing=3,  # Try different values
    min_clip_length=3.0,
    max_clip_length=6.0
)
```

**Problem**: Poor clip matching
```python
# Solution: Check embeddings and scores
stats = selector.get_statistics()
print(f"Avg motion: {stats['avg_motion']}")
```

## Dependencies

- `numpy>=1.26.4` - Numerical operations
- `librosa>=0.10.0` - Audio analysis
- `faiss-cpu>=1.7.0` - Vector similarity search
- BeatNet (via AudioAnalyzer) - Beat detection

## License

Part of PB Studio AMD Edition - MIT License

## Contributing

When contributing to the pacing engine:
1. Maintain type hints on all functions
2. Add docstrings with parameter descriptions
3. Include unit tests for new features
4. Update documentation and examples
5. Ensure compatibility with VideoGenerator

## Support

For issues, questions, or feature requests:
- Check `docs/pacing_engine_integration.md`
- Review examples in `docs/examples/pacing_example.py`
- See main project README for support channels
