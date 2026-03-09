# Audio Engineering Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Audio", "Stem", "BPM", "WAV", "MP3", "Demucs", "librosa"
- Arbeit an `src/pb_studio/audio/`, `Bereiche/Audio/`, `*audio*.py`
- Fragen zu Stem Separation, Beat Detection, Audio-Analyse

## Cross-References
- → `ai-inference.md` (Demucs ONNX Model)
- → `offline-engineering.md` (Lokale Verarbeitung)
- → `python-backend.md` (Async Patterns)
- → `data-persistence.md` (Audio-Metadaten speichern)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Offline First** | Keine APIs - alles lokal verarbeiten |
| **Memory Safety** | Große Dateien chunked verarbeiten |
| **Libraries** | `librosa` (Analyse), `soundfile` (IO), `onnxruntime` (AI) |

---

## 1. Sichere Audio-Datei Handling

```python
import soundfile as sf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Projektgrenzen
MAX_FILE_SIZE_GB = 2.0
MIN_DURATION_SEC = 1.0
MAX_DURATION_SEC = 7200  # 2 Stunden

def validate_audio_file(file_path: Path) -> dict:
    """Validiert Audio-Datei vor Verarbeitung."""
    result = {
        "valid": False,
        "error": None,
        "info": None
    }
    
    if not file_path.exists():
        result["error"] = f"Datei nicht gefunden: {file_path}"
        return result
    
    # Größencheck
    size_gb = file_path.stat().st_size / (1024**3)
    if size_gb > MAX_FILE_SIZE_GB:
        result["error"] = f"Datei zu groß: {size_gb:.2f}GB (Max: {MAX_FILE_SIZE_GB}GB)"
        return result
    
    try:
        info = sf.info(str(file_path))
        result["info"] = {
            "duration": info.duration,
            "samplerate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
            "subtype": info.subtype
        }
        
        # Dauercheck
        if info.duration < MIN_DURATION_SEC:
            result["error"] = f"Datei zu kurz: {info.duration:.2f}s"
            return result
        
        if info.duration > MAX_DURATION_SEC:
            result["error"] = f"Datei zu lang: {info.duration:.2f}s"
            return result
        
        result["valid"] = True
        return result
        
    except Exception as e:
        result["error"] = f"Kann Datei nicht lesen: {e}"
        return result

def safe_audio_load(file_path: Path, target_sr: int = 44100) -> tuple[np.ndarray, int]:
    """Lädt Audio-Datei sicher mit Resampling."""
    import librosa
    
    validation = validate_audio_file(file_path)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    
    try:
        audio, sr = librosa.load(str(file_path), sr=target_sr, mono=False)
        logger.info(f"Audio geladen: {file_path.name}, {audio.shape}, {sr}Hz")
        return audio, sr
    except Exception as e:
        logger.error(f"Audio-Load fehlgeschlagen: {e}")
        raise
```

---

## 2. Chunked Processing für große Dateien

```python
import numpy as np
import soundfile as sf
from typing import Generator, Callable

def process_audio_chunked(
    file_path: Path,
    chunk_duration_sec: float = 30.0,
    processor: Callable[[np.ndarray, int], np.ndarray] = None,
    overlap_sec: float = 0.5
) -> Generator[np.ndarray, None, None]:
    """Verarbeitet Audio in Chunks für Memory-Effizienz."""
    
    info = sf.info(str(file_path))
    chunk_samples = int(chunk_duration_sec * info.samplerate)
    overlap_samples = int(overlap_sec * info.samplerate)
    
    with sf.SoundFile(str(file_path)) as f:
        position = 0
        total_samples = len(f)
        
        while position < total_samples:
            f.seek(position)
            chunk = f.read(chunk_samples)
            
            if processor:
                chunk = processor(chunk, info.samplerate)
            
            yield chunk
            
            # Nächste Position mit Overlap
            position += chunk_samples - overlap_samples
            
            # Progress logging
            progress = min(100, (position / total_samples) * 100)
            logger.debug(f"Audio Processing: {progress:.1f}%")

def aggregate_chunked_results(
    file_path: Path,
    analyzer: Callable[[np.ndarray, int], dict],
    chunk_duration_sec: float = 30.0
) -> dict:
    """Aggregiert Analyse-Ergebnisse aus Chunks."""
    
    results = []
    info = sf.info(str(file_path))
    
    for chunk in process_audio_chunked(file_path, chunk_duration_sec):
        chunk_result = analyzer(chunk, info.samplerate)
        results.append(chunk_result)
    
    # Aggregation (Beispiel: BPM als Median)
    return {
        "chunk_count": len(results),
        "aggregated": results
    }
```

---

## 3. BPM Detection (Optimiert)

```python
import librosa
import numpy as np

def detect_bpm(
    audio: np.ndarray,
    sr: int = 44100,
    method: str = "librosa"
) -> dict:
    """Erkennt BPM mit verschiedenen Methoden."""
    
    # Mono konvertieren falls nötig
    if audio.ndim > 1:
        audio = librosa.to_mono(audio)
    
    if method == "librosa":
        # Standard librosa (gut für die meisten Genres)
        tempo, beat_frames = librosa.beat.beat_track(
            y=audio,
            sr=sr,
            hop_length=512,  # Schneller als default 512
            start_bpm=120,
            tightness=100
        )
        
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=512)
        
        return {
            "bpm": float(tempo),
            "beat_frames": beat_frames.tolist(),
            "beat_times": beat_times.tolist(),
            "confidence": calculate_bpm_confidence(beat_times)
        }
    
    elif method == "onset":
        # Onset-basiert (besser für komplexe Rhythmen)
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        
        return {
            "bpm": float(tempo[0]),
            "confidence": 0.8  # Onset ist generell zuverlässig
        }
    
    else:
        raise ValueError(f"Unbekannte Methode: {method}")

def calculate_bpm_confidence(beat_times: np.ndarray) -> float:
    """Berechnet Konfidenz basierend auf Beat-Konsistenz."""
    if len(beat_times) < 4:
        return 0.0
    
    intervals = np.diff(beat_times)
    std_dev = np.std(intervals)
    mean_interval = np.mean(intervals)
    
    # Niedriger CV = konsistentere Beats = höhere Konfidenz
    cv = std_dev / mean_interval if mean_interval > 0 else 1.0
    confidence = max(0.0, min(1.0, 1.0 - cv))
    
    return round(confidence, 3)
```

---

## 4. Transient/Onset Detection

```python
def detect_transients(
    audio: np.ndarray,
    sr: int = 44100,
    sensitivity: float = 0.5
) -> dict:
    """Erkennt Transienten für Mix-Points."""
    
    if audio.ndim > 1:
        audio = librosa.to_mono(audio)
    
    # Onset Detection
    onset_frames = librosa.onset.onset_detect(
        y=audio,
        sr=sr,
        hop_length=512,
        backtrack=True,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=5,
        delta=sensitivity * 0.07,  # Threshold anpassen
        wait=10
    )
    
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    
    # Onset Strength für Visualisierung
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=512)
    
    return {
        "onset_frames": onset_frames.tolist(),
        "onset_times": onset_times.tolist(),
        "onset_count": len(onset_frames),
        "onset_envelope": onset_env.tolist()
    }

def find_mix_points(
    audio: np.ndarray,
    sr: int,
    min_gap_sec: float = 8.0
) -> list[float]:
    """Findet optimale Mix-Punkte basierend auf Transienten."""
    
    transients = detect_transients(audio, sr)
    onset_times = np.array(transients["onset_times"])
    
    # Filtere Punkte mit Mindestabstand
    mix_points = []
    last_point = -min_gap_sec
    
    for t in onset_times:
        if t - last_point >= min_gap_sec:
            mix_points.append(float(t))
            last_point = t
    
    return mix_points
```

---

## 5. Stem Separation (Demucs ONNX)

```python
import onnxruntime as ort
import numpy as np
from pathlib import Path

class StemSeparator:
    """Stem Separation mit Demucs ONNX Model."""
    
    STEMS = ["drums", "bass", "vocals", "other"]
    TARGET_SR = 44100
    
    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Demucs Model nicht gefunden: {model_path}")
        
        from .ai_inference import get_optimal_providers
        
        self.session = ort.InferenceSession(
            str(model_path),
            providers=get_optimal_providers()
        )
        logger.info(f"StemSeparator initialisiert auf {self.session.get_providers()}")
    
    def separate(
        self,
        audio: np.ndarray,
        sr: int,
        output_dir: Path
    ) -> dict[str, Path]:
        """Trennt Audio in Stems und speichert sie."""
        
        # Resample falls nötig
        if sr != self.TARGET_SR:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.TARGET_SR)
        
        # Stereo sicherstellen
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=0)
        
        # Inference vorbereiten
        input_data = audio[np.newaxis, ...].astype(np.float32)
        
        # Inference
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: input_data})
        
        # Stems speichern
        stems_output = outputs[0][0]  # Shape: [4, 2, samples]
        output_paths = {}
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, stem_name in enumerate(self.STEMS):
            stem_audio = stems_output[i]
            output_path = output_dir / f"{stem_name}.wav"
            
            sf.write(
                str(output_path),
                stem_audio.T,  # [2, samples] -> [samples, 2]
                self.TARGET_SR,
                subtype='PCM_16'
            )
            
            output_paths[stem_name] = output_path
            logger.info(f"Stem gespeichert: {output_path}")
        
        return output_paths
```

---

## 6. Audio Export

```python
def export_audio(
    audio: np.ndarray,
    sr: int,
    output_path: Path,
    format: str = "wav",
    quality: str = "high"
) -> Path:
    """Exportiert Audio in verschiedene Formate."""
    
    format_settings = {
        "wav": {"subtype": "PCM_24" if quality == "high" else "PCM_16"},
        "flac": {"subtype": "PCM_24" if quality == "high" else "PCM_16"},
        "ogg": {"subtype": None}  # Vorbis
    }
    
    if format not in format_settings:
        raise ValueError(f"Unbekanntes Format: {format}")
    
    output_path = output_path.with_suffix(f".{format}")
    
    sf.write(
        str(output_path),
        audio.T if audio.ndim > 1 else audio,
        sr,
        subtype=format_settings[format].get("subtype")
    )
    
    logger.info(f"Audio exportiert: {output_path}")
    return output_path
```

---

## Checkliste: Audio Engineering

### Vor der Verarbeitung
- [ ] Datei validiert (`validate_audio_file`)?
- [ ] Dateigröße < 2GB?
- [ ] Dauer > 1s und < 2h?
- [ ] Format unterstützt (WAV, MP3, FLAC, OGG)?

### Bei der Verarbeitung
- [ ] Große Dateien (>100MB) chunked verarbeiten?
- [ ] Mono/Stereo korrekt behandelt?
- [ ] Sample Rate konsistent (44.1kHz)?
- [ ] Memory-Nutzung überwacht?

### Nach der Verarbeitung
- [ ] Output-Dateien validiert?
- [ ] Metadaten gespeichert?
- [ ] Temporäre Dateien aufgeräumt?
- [ ] Logs geschrieben?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `MemoryError` | Große Datei komplett geladen | Chunked Processing verwenden |
| `Corrupt file` | Datei beschädigt/falsches Format | `validate_audio_file()` vorher aufrufen |
| `BPM = 0` | Stille oder Rauschen | Audio validieren, Mindestlänge prüfen |
| `Sample rate mismatch` | Model erwartet andere SR | Resample vor Verarbeitung |
| `librosa slow` | Unnötig hohe Auflösung | `hop_length=512` verwenden |
