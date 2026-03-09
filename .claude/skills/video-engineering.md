# Video Engineering Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Video", "FFmpeg", "Frame", "Keyframe", "CLIP", "Encoding"
- Arbeit an `src/pb_studio/video/`, `Bereiche/Video/`, `*video*.py`
- Fragen zu Video-Verarbeitung, Codec-Auswahl, Frame-Extraktion

## Cross-References
- → `ai-inference.md` (CLIP Model für Video-Analyse)
- → `hardware-control.md` (FFmpeg Hardware Encoder - AMD AMF)
- → `audio-engineering.md` (Audio aus Video extrahieren)
- → `offline-engineering.md` (Lokale Verarbeitung)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **Non-Blocking** | Video-Ops immer in Background Thread |
| **FFmpeg** | Engine für Decode/Encode/Transcode |
| **Memory-Safe** | Raw Frames fressen RAM - vorsichtig! |
| **AMD-Only** | h264_amf für Hardware Encoding |

---

## 1. FFmpeg Wrapper

```python
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Generator
import logging

logger = logging.getLogger(__name__)

@dataclass
class VideoInfo:
    path: Path
    duration_sec: float
    width: int
    height: int
    fps: float
    codec: str
    bitrate_kbps: int
    has_audio: bool
    audio_codec: Optional[str]
    file_size_mb: float

class FFmpegWrapper:
    """Wrapper für FFmpeg Operationen."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path
        
        self._verify_installation()
    
    def _verify_installation(self):
        """Prüft ob FFmpeg installiert ist."""
        try:
            subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                check=True,
                timeout=10
            )
        except Exception as e:
            raise RuntimeError(f"FFmpeg not found: {e}")
    
    def get_info(self, video_path: Path) -> VideoInfo:
        """Holt Video-Metadaten."""
        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise ValueError(f"FFprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        
        # Video Stream finden
        video_stream = None
        audio_stream = None
        
        for stream in data.get("streams", []):
            if stream["codec_type"] == "video" and video_stream is None:
                video_stream = stream
            elif stream["codec_type"] == "audio" and audio_stream is None:
                audio_stream = stream
        
        if video_stream is None:
            raise ValueError("No video stream found")
        
        format_info = data.get("format", {})
        
        # FPS berechnen (kann "30/1" oder "29.97" sein)
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den else 30.0
        else:
            fps = float(fps_str)
        
        return VideoInfo(
            path=video_path,
            duration_sec=float(format_info.get("duration", 0)),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            codec=video_stream.get("codec_name", "unknown"),
            bitrate_kbps=int(format_info.get("bit_rate", 0)) // 1000,
            has_audio=audio_stream is not None,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            file_size_mb=video_path.stat().st_size / (1024 * 1024)
        )
    
    def run_command(
        self,
        args: list[str],
        progress_callback: callable = None,
        timeout: int = 3600
    ) -> bool:
        """Führt FFmpeg-Befehl mit Progress aus."""
        
        full_cmd = [self.ffmpeg, "-y"] + args
        logger.debug(f"FFmpeg command: {' '.join(full_cmd)}")
        
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Progress Parsing (FFmpeg schreibt zu stderr)
        for line in process.stderr:
            if progress_callback and "time=" in line:
                # Parse "time=00:01:23.45"
                import re
                match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if match:
                    h, m, s = match.groups()
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    progress_callback(current_sec)
        
        process.wait(timeout=timeout)
        
        if process.returncode != 0:
            logger.error(f"FFmpeg failed with code {process.returncode}")
            return False
        
        return True
```

---

## 2. Frame Extraction Strategies

```python
import numpy as np
from PIL import Image
from typing import Generator
import tempfile
import shutil

class FrameExtractor:
    """Extrahiert Frames aus Videos."""
    
    def __init__(self, ffmpeg: FFmpegWrapper = None):
        self.ffmpeg = ffmpeg or FFmpegWrapper()
    
    def extract_keyframes(
        self,
        video_path: Path,
        output_dir: Path,
        scene_threshold: float = 0.4,
        max_frames: int = 100
    ) -> list[Path]:
        """Extrahiert Keyframes basierend auf Szenenwechsel."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg Scene Detection Filter
        output_pattern = output_dir / "keyframe_%04d.jpg"
        
        args = [
            "-i", str(video_path),
            "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
            "-vsync", "vfr",
            "-frames:v", str(max_frames),
            "-q:v", "2",  # JPEG Qualität (2 = hoch)
            str(output_pattern)
        ]
        
        success = self.ffmpeg.run_command(args)
        
        if not success:
            raise RuntimeError("Keyframe extraction failed")
        
        # Extrahierte Frames sammeln
        frames = sorted(output_dir.glob("keyframe_*.jpg"))
        logger.info(f"Extracted {len(frames)} keyframes")
        
        return frames
    
    def extract_at_intervals(
        self,
        video_path: Path,
        output_dir: Path,
        interval_sec: float = 1.0,
        max_frames: int = 1000
    ) -> list[Path]:
        """Extrahiert Frames in regelmäßigen Intervallen."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = output_dir / "frame_%06d.jpg"
        
        # fps=1/interval_sec für Extraktion alle N Sekunden
        fps = 1.0 / interval_sec
        
        args = [
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-frames:v", str(max_frames),
            "-q:v", "2",
            str(output_pattern)
        ]
        
        self.ffmpeg.run_command(args)
        
        return sorted(output_dir.glob("frame_*.jpg"))
    
    def extract_single_frame(
        self,
        video_path: Path,
        timestamp_sec: float,
        output_path: Path = None
    ) -> Path:
        """Extrahiert einen einzelnen Frame."""
        
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".jpg"))
        
        args = [
            "-ss", str(timestamp_sec),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]
        
        self.ffmpeg.run_command(args)
        
        return output_path
    
    def stream_frames(
        self,
        video_path: Path,
        fps: float = 1.0,
        resize: tuple[int, int] = None
    ) -> Generator[np.ndarray, None, None]:
        """Streamt Frames als numpy Arrays (memory-efficient)."""
        
        import subprocess
        
        # Output Format: raw RGB frames
        vf_filters = [f"fps={fps}"]
        if resize:
            vf_filters.append(f"scale={resize[0]}:{resize[1]}")
        
        cmd = [
            self.ffmpeg.ffmpeg,
            "-i", str(video_path),
            "-vf", ",".join(vf_filters),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-"  # Output to stdout
        ]
        
        # Hole Video-Info für Frame-Größe
        info = self.ffmpeg.get_info(video_path)
        width = resize[0] if resize else info.width
        height = resize[1] if resize else info.height
        frame_size = width * height * 3
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        try:
            while True:
                raw_frame = process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    break
                
                frame = np.frombuffer(raw_frame, dtype=np.uint8)
                frame = frame.reshape((height, width, 3))
                
                yield frame
        finally:
            process.terminate()
            process.wait()
```

---

## 3. CLIP Video Analysis

```python
import numpy as np
from pathlib import Path
from typing import Optional
import onnxruntime as ort

class CLIPVideoAnalyzer:
    """Analysiert Video-Frames mit CLIP."""
    
    FRAME_SIZE = (224, 224)  # CLIP Input Size
    BATCH_SIZE = 8           # Frames pro Batch (VRAM-abhängig)
    
    def __init__(
        self,
        vision_model_path: Path,
        text_model_path: Path
    ):
        from .ai_inference import get_optimal_providers
        
        providers = get_optimal_providers()
        
        self.vision_session = ort.InferenceSession(
            str(vision_model_path),
            providers=providers
        )
        
        self.text_session = ort.InferenceSession(
            str(text_model_path),
            providers=providers
        )
        
        logger.info(f"CLIP loaded on {self.vision_session.get_providers()}")
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocessed Frame für CLIP."""
        from PIL import Image
        
        # Resize
        if frame.shape[:2] != self.FRAME_SIZE:
            img = Image.fromarray(frame)
            img = img.resize(self.FRAME_SIZE, Image.Resampling.LANCZOS)
            frame = np.array(img)
        
        # Normalize (CLIP-spezifisch)
        frame = frame.astype(np.float32) / 255.0
        mean = np.array([0.48145466, 0.4578275, 0.40821073])
        std = np.array([0.26862954, 0.26130258, 0.27577711])
        frame = (frame - mean) / std
        
        # HWC -> CHW
        frame = frame.transpose(2, 0, 1)
        
        return frame
    
    def encode_frames(self, frames: list[np.ndarray]) -> np.ndarray:
        """Encodiert Frames zu Embeddings."""
        
        # Preprocessing
        processed = np.stack([
            self.preprocess_frame(f) for f in frames
        ]).astype(np.float32)
        
        # Inference
        input_name = self.vision_session.get_inputs()[0].name
        output = self.vision_session.run(None, {input_name: processed})
        
        embeddings = output[0]
        
        # L2 Normalization
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        return embeddings
    
    def analyze_video(
        self,
        video_path: Path,
        frame_interval_sec: float = 1.0,
        progress_callback: callable = None
    ) -> list[dict]:
        """Analysiert Video und gibt Frame-Embeddings zurück."""
        
        extractor = FrameExtractor()
        results = []
        
        frame_batch = []
        timestamps = []
        current_time = 0.0
        
        for frame in extractor.stream_frames(video_path, fps=1/frame_interval_sec):
            frame_batch.append(frame)
            timestamps.append(current_time)
            current_time += frame_interval_sec
            
            # Batch voll?
            if len(frame_batch) >= self.BATCH_SIZE:
                embeddings = self.encode_frames(frame_batch)
                
                for i, (ts, emb) in enumerate(zip(timestamps, embeddings)):
                    results.append({
                        "timestamp": ts,
                        "embedding": emb.tolist()
                    })
                
                frame_batch = []
                timestamps = []
                
                if progress_callback:
                    progress_callback(current_time)
        
        # Restliche Frames
        if frame_batch:
            embeddings = self.encode_frames(frame_batch)
            for ts, emb in zip(timestamps, embeddings):
                results.append({
                    "timestamp": ts,
                    "embedding": emb.tolist()
                })
        
        logger.info(f"Analyzed {len(results)} frames from {video_path.name}")
        return results
```

---

## 4. Video Transcoding (AMD AMF)

```python
from dataclasses import dataclass
from enum import Enum

class VideoQuality(Enum):
    LOW = "low"       # 480p, CRF 28
    MEDIUM = "medium" # 720p, CRF 23
    HIGH = "high"     # 1080p, CRF 18
    ORIGINAL = "original"

@dataclass
class TranscodeSettings:
    quality: VideoQuality
    codec: str = "h264"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"

class VideoTranscoder:
    """Video Transcoding mit AMD AMF Hardware-Acceleration."""
    
    def __init__(self, ffmpeg: FFmpegWrapper = None):
        self.ffmpeg = ffmpeg or FFmpegWrapper()
        
        # Hardware Encoder Detection (AMD)
        from .hardware_control import get_optimal_encoder_config
        self.encoder_config = get_optimal_encoder_config()
    
    def transcode(
        self,
        input_path: Path,
        output_path: Path,
        settings: TranscodeSettings,
        progress_callback: callable = None
    ) -> bool:
        """Transcodiert Video mit AMD AMF Encoder."""
        
        # Basis-Argumente
        args = []
        
        # Hardware Decoding
        if self.encoder_config.hwaccel:
            args.extend(["-hwaccel", self.encoder_config.hwaccel])
        
        # Input
        args.extend(["-i", str(input_path)])
        
        # Quality Settings
        quality_settings = self._get_quality_settings(settings.quality)
        
        # Video Encoder (AMD AMF priorisiert)
        args.extend(["-c:v", self.encoder_config.video_encoder])
        args.extend(quality_settings["video_args"])
        args.extend(self.encoder_config.extra_params)
        
        # Scale wenn nicht original
        if settings.quality != VideoQuality.ORIGINAL:
            args.extend(["-vf", f"scale={quality_settings['width']}:-2"])
        
        # Audio
        args.extend(["-c:a", settings.audio_codec])
        args.extend(["-b:a", settings.audio_bitrate])
        
        # Output
        args.append(str(output_path))
        
        # Get duration for progress
        info = self.ffmpeg.get_info(input_path)
        
        def progress_wrapper(current_sec):
            if progress_callback and info.duration_sec > 0:
                percent = min(100, int((current_sec / info.duration_sec) * 100))
                progress_callback(percent)
        
        return self.ffmpeg.run_command(args, progress_callback=progress_wrapper)
    
    def _get_quality_settings(self, quality: VideoQuality) -> dict:
        """Gibt Qualitäts-spezifische Einstellungen zurück."""
        settings = {
            VideoQuality.LOW: {
                "width": 854,
                "video_args": ["-crf", "28"]
            },
            VideoQuality.MEDIUM: {
                "width": 1280,
                "video_args": ["-crf", "23"]
            },
            VideoQuality.HIGH: {
                "width": 1920,
                "video_args": ["-crf", "18"]
            },
            VideoQuality.ORIGINAL: {
                "width": None,
                "video_args": ["-crf", "18"]
            }
        }
        return settings[quality]
    
    def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        format: str = "wav"
    ) -> bool:
        """Extrahiert Audio-Spur aus Video."""
        
        args = [
            "-i", str(video_path),
            "-vn",  # Kein Video
            "-acodec", "pcm_s16le" if format == "wav" else "aac",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]
        
        return self.ffmpeg.run_command(args)
```

---

## 5. Thumbnail Generation

```python
class ThumbnailGenerator:
    """Generiert Video-Thumbnails."""
    
    def __init__(self, ffmpeg: FFmpegWrapper = None):
        self.ffmpeg = ffmpeg or FFmpegWrapper()
    
    def generate_thumbnail(
        self,
        video_path: Path,
        output_path: Path,
        timestamp_sec: float = None,
        size: tuple[int, int] = (320, 180)
    ) -> Path:
        """Generiert einzelnes Thumbnail."""
        
        # Timestamp: 10% ins Video falls nicht angegeben
        if timestamp_sec is None:
            info = self.ffmpeg.get_info(video_path)
            timestamp_sec = info.duration_sec * 0.1
        
        args = [
            "-ss", str(timestamp_sec),
            "-i", str(video_path),
            "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]
        
        self.ffmpeg.run_command(args)
        return output_path
    
    def generate_sprite(
        self,
        video_path: Path,
        output_path: Path,
        columns: int = 5,
        rows: int = 5,
        thumb_size: tuple[int, int] = (160, 90)
    ) -> Path:
        """Generiert Sprite-Sheet für Video-Preview."""
        
        info = self.ffmpeg.get_info(video_path)
        total_thumbs = columns * rows
        interval = info.duration_sec / total_thumbs
        
        # Sprite-Sheet mit FFmpeg
        args = [
            "-i", str(video_path),
            "-vf", f"fps=1/{interval},scale={thumb_size[0]}:{thumb_size[1]},tile={columns}x{rows}",
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]
        
        self.ffmpeg.run_command(args)
        return output_path
```

---

## 6. Error Handling für Video

```python
class VideoError(Exception):
    """Basis-Exception für Video-Fehler."""
    pass

class CodecNotSupportedError(VideoError):
    """Codec wird nicht unterstützt."""
    pass

class CorruptVideoError(VideoError):
    """Video-Datei ist beschädigt."""
    pass

def handle_video_errors(func):
    """Decorator für Video-Fehlerbehandlung."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except subprocess.TimeoutExpired:
            raise VideoError("Video processing timed out")
        except subprocess.CalledProcessError as e:
            if "Invalid data" in str(e.stderr):
                raise CorruptVideoError("Video file appears to be corrupt")
            elif "codec" in str(e.stderr).lower():
                raise CodecNotSupportedError(f"Unsupported codec: {e.stderr}")
            raise VideoError(f"FFmpeg error: {e.stderr}")
        except Exception as e:
            logger.error(f"Video processing error: {e}", exc_info=True)
            raise
    
    return wrapper

# VFR (Variable Frame Rate) Handling
def detect_vfr(video_path: Path) -> bool:
    """Erkennt Variable Frame Rate Videos (z.B. iPhone)."""
    ffmpeg = FFmpegWrapper()
    
    cmd = [
        ffmpeg.ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,avg_frame_rate",
        "-of", "json",
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    stream = data.get("streams", [{}])[0]
    r_fps = stream.get("r_frame_rate", "30/1")
    avg_fps = stream.get("avg_frame_rate", "30/1")
    
    # Wenn r_frame_rate und avg_frame_rate signifikant unterschiedlich sind
    def parse_fps(fps_str):
        if "/" in fps_str:
            num, den = map(float, fps_str.split("/"))
            return num / den if den else 30.0
        return float(fps_str)
    
    r = parse_fps(r_fps)
    avg = parse_fps(avg_fps)
    
    # Mehr als 5% Unterschied = VFR
    return abs(r - avg) / max(r, avg) > 0.05
```

---

## Checkliste: Video Engineering

### Vor der Verarbeitung
- [ ] FFmpeg installiert und erreichbar?
- [ ] Video-Info erfolgreich geholt?
- [ ] Codec unterstützt?
- [ ] Genug Speicherplatz für Output?

### Bei der Verarbeitung
- [ ] In Background Thread/Process?
- [ ] Progress-Feedback aktiv?
- [ ] Timeout gesetzt?
- [ ] Temporäre Dateien werden aufgeräumt?

### Hardware Acceleration (AMD)
- [ ] h264_amf verfügbar?
- [ ] Fallback zu Software-Encoder?
- [ ] Encoding-Qualität akzeptabel?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `FFmpeg not found` | Nicht im PATH | FFmpeg installieren, PATH setzen |
| `Invalid data` | Korrupte Datei | Video mit anderem Tool prüfen |
| `Unknown encoder` | HW-Encoder fehlt | Treiber updaten oder SW-Fallback |
| Timing-Probleme | VFR Video | `detect_vfr()`, ggf. vorher konvertieren |
| Out of Memory | Zu viele Frames im RAM | Streaming statt Batch-Load |
| h264_amf nicht verfügbar | Alte AMD Treiber | AMD Treiber >= 21.10 installieren |
