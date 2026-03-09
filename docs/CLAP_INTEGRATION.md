# CLAP Audio Specialist - Integration Guide

## Overview

CLAP (Contrastive Language-Audio Pretraining) ist ein multimodales AI-Modell für Zero-Shot Audio Classification. Es verbindet Audio-Embeddings mit Text-Embeddings und ermöglicht flexible Audio-Analyse ohne Training auf spezifische Kategorien.

**Model:** `laion/clap-htsat-unfused`
**Architecture:**
- Audio Encoder: HTS-AT (Hierarchical Token-Semantic Audio Transformer)
- Text Encoder: RoBERTa-based transformer
- Embedding Dimension: 512

## Features

### 1. Zero-Shot Classification
Klassifiziere Audio mit beliebigen Text-Labels ohne vorheriges Training:
```python
from pb_studio.ai import CLAPAnalyzer

analyzer = CLAPAnalyzer()

# Eigene Labels definieren
labels = ["workout music", "meditation", "study background", "party"]
results = analyzer.classify_audio("song.mp3", labels, top_k=3)

for label, score in results:
    print(f"{label}: {score:.2f}")
```

### 2. Mood Detection
Erkenne Stimmung und Emotionen in Audio:
```python
moods = analyzer.get_mood_tags("song.mp3", top_k=5)
# Output: ["energetic", "uplifting", "happy", "rhythmic", "bright"]
```

### 3. Instrument Detection
Identifiziere vorhandene Instrumente:
```python
instruments = analyzer.get_instrument_tags("song.mp3", top_k=3)
# Output: ["guitar", "drums", "synthesizer"]
```

### 4. Genre Classification
Bestimme Musik-Genre:
```python
genres = analyzer.get_genre_tags("song.mp3", top_k=3)
# Output: ["rock", "pop", "electronic"]
```

### 5. Audio Similarity
Vergleiche zwei Audio-Dateien:
```python
similarity = analyzer.compute_similarity("song1.mp3", "song2.mp3")
# Output: 0.87 (0.0 = völlig unterschiedlich, 1.0 = identisch)
```

### 6. Comprehensive Analysis
Alle Analysen in einem Durchlauf:
```python
results = analyzer.analyze_audio_comprehensive("song.mp3")

print("Moods:", results["moods"])
print("Instruments:", results["instruments"])
print("Genres:", results["genres"])
print("Embedding:", results["embedding"].shape)  # (512,)
```

## DirectML Configuration

**KRITISCH für AMD GPUs:** Der CLAP-Wrapper verwendet die korrekte DirectML-Konfiguration:

```python
# Session Options (automatisch konfiguriert)
sess_options = ort.SessionOptions()
sess_options.enable_mem_pattern = False  # MANDATORY für DirectML!
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

# Providers (automatisch ausgewählt)
providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
```

Das Modell erkennt automatisch verfügbare Hardware und nutzt:
1. **DirectML** wenn AMD GPU verfügbar
2. **CPU** als Fallback

Prüfe aktiven Provider:
```python
analyzer = CLAPAnalyzer()
print(analyzer.active_provider)  # "DmlExecutionProvider" oder "CPUExecutionProvider"
```

## Model Files

### Required ONNX Files

Das CLAP-Modell kann in zwei Architekturen vorliegen:

**Option 1: Split Model (empfohlen)**
```
models/
├── clap_audio_encoder.onnx  # Audio Encoder (HTS-AT)
└── clap_text_encoder.onnx   # Text Encoder (RoBERTa)
```

**Option 2: Combined Model**
```
models/
└── clap_combined.onnx  # Kombiniertes Modell
```

### Model Download

```bash
# Option 1: Automatisches Download-Script
python scripts/download_clap_model.py

# Option 2: Manueller Export von Hugging Face
python scripts/export_clap_onnx.py
```

**Hinweis:** Die ONNX-Modelle müssen aus dem PyTorch-Original konvertiert werden. Details siehe `scripts/export_clap_onnx.py`.

## Audio Processing

### Supported Formats
- MP3, WAV, FLAC, OGG, M4A
- Alle von `librosa` unterstützten Formate

### Audio Preprocessing
- **Resampling:** Automatisch auf 48kHz
- **Duration:** 10 Sekunden (Trimming/Padding automatisch)
- **Channels:** Konvertierung zu Mono automatisch
- **Mel Spectrogram:** 64 Mel-Bänder, 1024 FFT

```python
# Wird automatisch durchgeführt
audio = analyzer.load_audio("any_format.mp3")
# Output: numpy array [480000 samples] @ 48kHz
```

## Integration mit MotionBeat XL

### Use Case: Mood-Based Video Pacing

```python
from pb_studio.ai import CLAPAnalyzer
from pb_studio.audio.analyzer import BeatAnalyzer

# 1. Audio Features extrahieren
beat_analyzer = BeatAnalyzer()
beats = beat_analyzer.analyze("music.mp3")

# 2. Mood erkennen
clap = CLAPAnalyzer()
moods = clap.get_mood_tags("music.mp3", top_k=5)

# 3. Pacing basierend auf Mood anpassen
if "energetic" in moods or "intense" in moods:
    # Schnelle Cuts, kurze Szenen
    avg_scene_duration = 2.0
elif "calm" in moods or "peaceful" in moods:
    # Langsame Übergänge, lange Szenen
    avg_scene_duration = 5.0
else:
    # Standard
    avg_scene_duration = 3.0
```

### Use Case: Audio Similarity Search

```python
# Finde ähnliche Musik-Stücke
reference_track = "user_selection.mp3"
music_library = ["track1.mp3", "track2.mp3", "track3.mp3"]

clap = CLAPAnalyzer()
similarities = []

for track in music_library:
    sim = clap.compute_similarity(reference_track, track)
    similarities.append((track, sim))

# Sortiere nach Ähnlichkeit
similarities.sort(key=lambda x: x[1], reverse=True)

print("Most similar tracks:")
for track, sim in similarities[:3]:
    print(f"{track}: {sim:.2f}")
```

### Use Case: Automatic Video Genre Detection

```python
def suggest_video_style(audio_path):
    """Schlage Video-Stil basierend auf Audio-Analyse vor."""
    clap = CLAPAnalyzer()

    # Analyse
    moods = clap.get_mood_tags(audio_path, top_k=5)
    genres = clap.get_genre_tags(audio_path, top_k=3)

    # Style-Empfehlung
    if "cinematic" in moods or "epic" in moods:
        return {
            "style": "Cinematic",
            "transitions": "Smooth fades",
            "effects": "Color grading, lens flares",
            "pacing": "Slow, dramatic"
        }
    elif "electronic" in genres and "energetic" in moods:
        return {
            "style": "EDM/Dance",
            "transitions": "Fast cuts, glitch effects",
            "effects": "Strobing, neon colors",
            "pacing": "Fast, rhythmic"
        }
    # ... weitere Styles
```

## Performance

### Inference Speed (AMD RX 6800 XT)
- **Audio Encoding:** ~50-100ms per 10-second chunk
- **Text Encoding:** ~10-20ms per label batch
- **Classification:** ~100ms total (audio + text + similarity)

### Memory Usage
- **VRAM:** ~1.5GB (DirectML)
- **RAM:** ~500MB (Audio loading + preprocessing)

### Optimization Tips

1. **Batch Processing:**
```python
# Encode audio once, classify multiple label sets
embedding = analyzer.encode_audio("song.mp3")

# Wiederverwendung für verschiedene Klassifikationen
moods = analyzer.classify_audio_with_embedding(embedding, mood_labels)
genres = analyzer.classify_audio_with_embedding(embedding, genre_labels)
```

2. **Lazy Loading:**
```python
# Modell erst bei Bedarf laden
analyzer = CLAPAnalyzer(lazy_load=True)
# Model wird beim ersten Aufruf geladen
```

3. **Unload nach Verwendung:**
```python
analyzer = CLAPAnalyzer()
# ... Analyse durchführen ...
analyzer.unload()  # Gibt VRAM frei
```

## API Reference

### CLAPAnalyzer

```python
class CLAPAnalyzer:
    def __init__(
        self,
        models_dir: Optional[str] = None,
        lazy_load: bool = False
    )

    def encode_audio(
        self,
        audio_path: Union[str, Path]
    ) -> Optional[np.ndarray]
    """
    Encodiere Audio zu 512-dim Embedding.
    Returns: numpy array [512] oder None
    """

    def encode_text(
        self,
        text_list: List[str]
    ) -> Optional[np.ndarray]
    """
    Encodiere Text-Labels zu Embeddings.
    Returns: numpy array [num_labels, 512] oder None
    """

    def classify_audio(
        self,
        audio_path: Union[str, Path],
        labels: List[str],
        top_k: int = 5
    ) -> List[Tuple[str, float]]
    """
    Zero-Shot Klassifikation.
    Returns: List von (label, score) tuples
    """

    def get_mood_tags(
        self,
        audio_path: Union[str, Path],
        top_k: int = 5,
        custom_labels: Optional[List[str]] = None
    ) -> List[str]
    """
    Extrahiere Mood-Tags.
    Returns: List von Mood-Labels
    """

    def get_instrument_tags(
        self,
        audio_path: Union[str, Path],
        top_k: int = 3
    ) -> List[str]
    """
    Erkenne Instrumente.
    Returns: List von Instrument-Labels
    """

    def get_genre_tags(
        self,
        audio_path: Union[str, Path],
        top_k: int = 3
    ) -> List[str]
    """
    Klassifiziere Genre.
    Returns: List von Genre-Labels
    """

    def analyze_audio_comprehensive(
        self,
        audio_path: Union[str, Path]
    ) -> Dict[str, Any]
    """
    Umfassende Analyse.
    Returns: Dict mit moods, instruments, genres, embedding
    """

    def compute_similarity(
        self,
        audio_path_1: Union[str, Path],
        audio_path_2: Union[str, Path]
    ) -> float
    """
    Berechne Audio-Ähnlichkeit.
    Returns: Similarity score [0.0, 1.0]
    """

    @property
    def is_ready(self) -> bool
    """Prüfe ob Modell initialisiert."""

    @property
    def active_provider(self) -> str
    """Aktiver Execution Provider."""

    def unload(self)
    """Gebe Model-Ressourcen frei."""
```

### Convenience Functions

```python
def analyze_audio_mood(
    audio_path: Union[str, Path],
    top_k: int = 5
) -> List[str]
"""Quick mood analysis."""

def classify_audio_genre(
    audio_path: Union[str, Path],
    top_k: int = 3
) -> List[str]
"""Quick genre classification."""
```

## Troubleshooting

### Problem: "DirectML provider not available"
```bash
pip uninstall onnxruntime onnxruntime-gpu -y
pip install onnxruntime-directml>=1.16.0
```

### Problem: "Model not found"
```bash
# Download und konvertiere CLAP-Modell
python scripts/download_clap_model.py
```

### Problem: Audio loading fails
```bash
# Installiere benötigte Audio-Libraries
pip install librosa soundfile
```

### Problem: Langsame Inference
- Prüfe ob DirectML aktiv: `print(analyzer.active_provider)`
- Falls "CPUExecutionProvider": DirectML installieren
- Falls "DmlExecutionProvider" aber langsam: GPU-Treiber updaten

## Testing

```bash
# Unit Tests
pytest tests/test_clap_wrapper.py -v

# Integration Tests (benötigt ONNX-Modelle)
pytest tests/test_clap_wrapper.py -v -m integration

# Demo ausführen
python examples/clap_demo.py test_audio/sample.mp3
```

## References

- CLAP Paper: https://arxiv.org/abs/2211.06687
- LAION CLAP: https://github.com/LAION-AI/CLAP
- HTS-AT: https://arxiv.org/abs/2202.00874
- ONNX Runtime DirectML: https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html

## License

Code: MIT License
Model: Creative ML Open RAIL-M License (siehe LAION CLAP repository)
