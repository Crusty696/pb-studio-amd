# CLAP Audio Specialist - Quick Start Guide

## 5-Minute Setup

### 1. Install Dependencies
```bash
# Already in requirements.txt
pip install -r requirements.txt
```

Benötigte Packages:
- `onnxruntime-directml>=1.16.0` (AMD GPU support)
- `librosa>=0.10.1` (Audio processing)
- `soundfile>=0.12.1` (Audio I/O)
- `transformers>=4.48.0` (Model loading)

### 2. Download CLAP Model
```bash
# Automatic download and ONNX export
python scripts/download_clap_model.py
```

Output Files:
- `models/clap_audio_encoder.onnx` (Audio Encoder)
- `models/clap_text_encoder.onnx` (Text Encoder)

**Note:** Download benötigt ~2GB und dauert ca. 5-10 Minuten beim ersten Mal.

### 3. Test Installation
```python
from pb_studio.ai import CLAPAnalyzer

analyzer = CLAPAnalyzer()
print(f"Ready: {analyzer.is_ready}")
print(f"Provider: {analyzer.active_provider}")
```

Expected Output:
```
Ready: True
Provider: DmlExecutionProvider  # AMD GPU
```

## Basic Usage Examples

### Example 1: Mood Detection (30 seconds)
```python
from pb_studio.ai import CLAPAnalyzer

# Initialize
analyzer = CLAPAnalyzer()

# Get mood tags
moods = analyzer.get_mood_tags("my_song.mp3", top_k=5)

print("Detected moods:", moods)
# Output: ['energetic', 'uplifting', 'happy', 'rhythmic', 'bright']
```

### Example 2: Custom Classification (1 minute)
```python
from pb_studio.ai import CLAPAnalyzer

analyzer = CLAPAnalyzer()

# Define your own labels
labels = [
    "background music for coding",
    "workout music",
    "meditation music",
    "party music"
]

# Classify
results = analyzer.classify_audio("song.mp3", labels, top_k=3)

for label, score in results:
    print(f"{label}: {score:.2%}")
```

Output:
```
workout music: 89.3%
party music: 67.2%
background music for coding: 45.1%
```

### Example 3: Full Analysis (2 minutes)
```python
from pb_studio.ai import CLAPAnalyzer

analyzer = CLAPAnalyzer()

# Comprehensive analysis
results = analyzer.analyze_audio_comprehensive("song.mp3")

print("=== Audio Analysis ===")
print(f"Moods: {', '.join(results['moods'])}")
print(f"Instruments: {', '.join(results['instruments'])}")
print(f"Genres: {', '.join(results['genres'])}")
print(f"Embedding: {results['embedding'].shape}")
```

Output:
```
=== Audio Analysis ===
Moods: energetic, uplifting, bright, rhythmic, powerful
Instruments: guitar, drums, synthesizer
Genres: rock, electronic, pop
Embedding: (512,)
```

## Integration Patterns

### Pattern 1: Batch Processing
```python
from pathlib import Path
from pb_studio.ai import CLAPAnalyzer

def analyze_music_library(music_dir):
    """Analyze all songs in a directory."""
    analyzer = CLAPAnalyzer()
    results = []

    for audio_file in Path(music_dir).glob("*.mp3"):
        moods = analyzer.get_mood_tags(str(audio_file))
        results.append({
            "file": audio_file.name,
            "moods": moods
        })

    return results

# Usage
library_analysis = analyze_music_library("./music")
```

### Pattern 2: Similarity Search
```python
from pb_studio.ai import CLAPAnalyzer

def find_similar_tracks(reference_track, library_tracks):
    """Find tracks similar to reference."""
    analyzer = CLAPAnalyzer()

    similarities = []
    for track in library_tracks:
        sim = analyzer.compute_similarity(reference_track, track)
        similarities.append((track, sim))

    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities

# Usage
similar = find_similar_tracks(
    "my_favorite.mp3",
    ["track1.mp3", "track2.mp3", "track3.mp3"]
)
```

### Pattern 3: Real-time Mood Tracking
```python
from pb_studio.ai import CLAPAnalyzer
import numpy as np

def analyze_song_progression(audio_path, chunk_duration=10):
    """Analyze mood changes throughout song."""
    analyzer = CLAPAnalyzer()

    # Load full audio
    import librosa
    audio, sr = librosa.load(audio_path, sr=48000)

    # Split into chunks
    chunk_samples = int(chunk_duration * sr)
    num_chunks = len(audio) // chunk_samples

    mood_progression = []

    for i in range(num_chunks):
        # Extract chunk
        start = i * chunk_samples
        end = start + chunk_samples
        chunk = audio[start:end]

        # Save chunk temporarily
        import soundfile as sf
        chunk_path = f"temp_chunk_{i}.wav"
        sf.write(chunk_path, chunk, sr)

        # Analyze chunk
        moods = analyzer.get_mood_tags(chunk_path, top_k=3)
        mood_progression.append({
            "time": i * chunk_duration,
            "moods": moods
        })

    return mood_progression

# Usage
progression = analyze_song_progression("long_track.mp3")
```

## Advanced Features

### Feature 1: Custom Mood Vocabulary
```python
from pb_studio.ai import CLAPAnalyzer

# Define domain-specific moods
fitness_moods = [
    "high intensity workout",
    "cardio motivation",
    "strength training",
    "yoga flow",
    "cool down stretching"
]

analyzer = CLAPAnalyzer()
results = analyzer.classify_audio(
    "workout_mix.mp3",
    fitness_moods,
    top_k=2
)
```

### Feature 2: Embedding-based Search
```python
from pb_studio.ai import CLAPAnalyzer
import numpy as np

def build_audio_index(audio_files):
    """Build searchable index of audio embeddings."""
    analyzer = CLAPAnalyzer()
    index = {}

    for audio_file in audio_files:
        embedding = analyzer.encode_audio(audio_file)
        index[audio_file] = embedding

    return index

def search_by_description(query_text, audio_index):
    """Search audio library by text description."""
    analyzer = CLAPAnalyzer()

    # Encode query (placeholder - needs tokenizer)
    # query_embedding = analyzer.encode_text([query_text])[0]

    # In production: compute similarity between query and all audio
    # results = sorted(audio_index.items(),
    #                  key=lambda x: cosine_sim(query_embedding, x[1]),
    #                  reverse=True)

    return results

# Usage
index = build_audio_index(["song1.mp3", "song2.mp3"])
# results = search_by_description("energetic rock music", index)
```

### Feature 3: Genre Distribution
```python
from pb_studio.ai import CLAPAnalyzer
from collections import Counter

def analyze_library_genres(audio_files):
    """Get genre distribution across music library."""
    analyzer = CLAPAnalyzer()
    all_genres = []

    for audio_file in audio_files:
        genres = analyzer.get_genre_tags(audio_file, top_k=2)
        all_genres.extend(genres)

    # Count genres
    genre_counts = Counter(all_genres)

    return genre_counts.most_common()

# Usage
distribution = analyze_library_genres(["song1.mp3", "song2.mp3"])
print(distribution)
# Output: [('rock', 15), ('pop', 12), ('electronic', 8), ...]
```

## Performance Tips

### Tip 1: Lazy Loading for Faster Startup
```python
# Load model only when needed
analyzer = CLAPAnalyzer(lazy_load=True)

# Model loads on first use
moods = analyzer.get_mood_tags("song.mp3")  # Model loads here
```

### Tip 2: Reuse Embeddings
```python
analyzer = CLAPAnalyzer()

# Encode once
embedding = analyzer.encode_audio("song.mp3")

# Use for multiple classifications
moods = analyzer.classify_with_embedding(embedding, mood_labels)
genres = analyzer.classify_with_embedding(embedding, genre_labels)
instruments = analyzer.classify_with_embedding(embedding, instrument_labels)
```

### Tip 3: Unload After Batch
```python
analyzer = CLAPAnalyzer()

# Process batch
for audio_file in large_batch:
    results = analyzer.get_mood_tags(audio_file)
    save_results(results)

# Free VRAM
analyzer.unload()
```

## Troubleshooting

### Issue: Model not found
```bash
python scripts/download_clap_model.py
```

### Issue: DirectML not working
```bash
pip uninstall onnxruntime onnxruntime-gpu -y
pip install onnxruntime-directml>=1.16.0

# Verify
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

### Issue: Audio loading fails
```bash
pip install librosa soundfile --upgrade
```

### Issue: Out of memory
```python
# Use lazy loading
analyzer = CLAPAnalyzer(lazy_load=True)

# Unload after use
analyzer.unload()
```

## Next Steps

1. **Read Full Documentation:** `docs/CLAP_INTEGRATION.md`
2. **Run Demo:** `python examples/clap_demo.py song.mp3`
3. **Write Tests:** `pytest tests/test_clap_wrapper.py -v`
4. **Integrate into App:** See integration patterns above

## Common Use Cases

### Video Production (MotionBeat XL)
```python
# 1. Analyze audio mood
moods = analyzer.get_mood_tags("soundtrack.mp3")

# 2. Adjust video pacing based on mood
if "energetic" in moods:
    scene_duration = 2.0  # Fast cuts
elif "calm" in moods:
    scene_duration = 5.0  # Slow pacing
```

### Music Library Organization
```python
# Tag all tracks
for track in music_library:
    moods = analyzer.get_mood_tags(track)
    genres = analyzer.get_genre_tags(track)

    # Save tags to database
    db.save_tags(track, moods=moods, genres=genres)
```

### Playlist Generation
```python
# Find tracks matching desired mood
target_mood = "workout motivation"
candidates = []

for track in library:
    results = analyzer.classify_audio(track, [target_mood])
    score = results[0][1]

    if score > 0.7:
        candidates.append((track, score))

# Generate playlist
playlist = sorted(candidates, key=lambda x: x[1], reverse=True)
```

## Support

- **Documentation:** `docs/CLAP_INTEGRATION.md`
- **Examples:** `examples/clap_demo.py`
- **Tests:** `tests/test_clap_wrapper.py`
- **Issues:** GitHub Issues

## License

Code: MIT License
Model: Creative ML Open RAIL-M License
