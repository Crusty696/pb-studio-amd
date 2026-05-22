"""
Smart Director - AI-Powered Video Generation Orchestrator

This module orchestrates CLAP (audio analysis), SigLIP (video analysis), and the
Pacing Engine to automatically generate video edits synchronized with music.

Architecture:
    Smart Director
    |-- Audio Analysis (CLAP) --> Mood Tags, Energy Curve
    |-- Video Analysis (SigLIP) --> Clip Embeddings, Content Tags
    |-- Pacing Engine --> Cut Points, Timeline
    +-- Matcher --> Audio-Video Semantic Matching

VRAM Management:
    Uses "Staffellauf" (relay race) pattern - only one heavy model loaded at a time.
    CLAP and SigLIP share VRAM budget, never loaded simultaneously.

Usage:
    director = SmartDirector()

    # Analyze audio
    audio_analysis = director.analyze_audio("track.mp3")

    # Analyze video clips
    clip_analyses = director.analyze_clips(["clip1.mp4", "clip2.mp4"])

    # Generate timeline
    timeline = director.generate_timeline(audio_analysis, clip_analyses, config)
"""

import logging
import threading
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class MoodCategory(Enum):
    """Mood categories for audio-video matching."""
    ENERGETIC = "energetic"
    CALM = "calm"
    DARK = "dark"
    BRIGHT = "bright"
    AGGRESSIVE = "aggressive"
    MELANCHOLIC = "melancholic"
    UPLIFTING = "uplifting"
    MYSTERIOUS = "mysterious"
    NEUTRAL = "neutral"


@dataclass
class AudioAnalysis:
    """Complete analysis results for an audio track."""
    file_path: str
    duration_sec: float
    bpm: float
    beat_times: List[float]           # Timestamps of detected beats
    downbeat_times: List[float]       # Timestamps of downbeats (measure starts)
    mood_tags: List[str]              # CLAP-detected moods
    mood_scores: Dict[str, float]     # Confidence scores per mood
    energy_curve: np.ndarray          # Energy over time (normalized 0-1)
    energy_timestamps: np.ndarray     # Timestamps for energy curve
    dominant_mood: MoodCategory       # Primary mood classification

    # Optional advanced features
    key: Optional[str] = None         # Musical key if detected
    time_signature: Optional[str] = None
    sections: List[Dict] = field(default_factory=list)  # Verse, chorus, etc.


@dataclass
class ClipAnalysis:
    """Analysis results for a single video clip."""
    file_path: str
    duration_sec: float
    embedding: np.ndarray             # SigLIP visual embedding (1152-dim for SO400M)
    content_tags: List[str]           # Detected visual content
    content_scores: Dict[str, float]  # Confidence per tag
    motion_score: float               # Average motion intensity (0-1)
    brightness: float                 # Average brightness (0-1)
    dominant_colors: List[Tuple[int, int, int]]  # RGB values

    # Scene information
    scene_count: int = 1
    scene_boundaries: List[float] = field(default_factory=list)

    # Metadata
    fps: float = 30.0
    resolution: Tuple[int, int] = (1920, 1080)


@dataclass
class TimelineClip:
    """A clip placement in the generated timeline."""
    source_path: str
    start_time: float           # Position in timeline (seconds)
    duration: float             # Duration in timeline (seconds)
    source_start: float         # Start position in source clip
    source_end: float           # End position in source clip

    # Matching metadata
    match_score: float = 0.0    # How well clip matches audio segment
    mood_alignment: float = 0.0 # Mood compatibility score
    energy_alignment: float = 0.0  # Energy level compatibility

    # Effects
    transition_in: str = "cut"   # cut, fade, dissolve
    transition_out: str = "cut"
    speed_factor: float = 1.0    # Playback speed multiplier


@dataclass
class Timeline:
    """Complete generated timeline."""
    audio_path: str
    duration_sec: float
    clips: List[TimelineClip]
    cut_points: List[float]     # All cut timestamps

    # Statistics
    total_clips: int = 0
    average_clip_duration: float = 0.0
    cuts_per_minute: float = 0.0

    # Export metadata
    resolution: Tuple[int, int] = (1920, 1080)
    fps: float = 30.0


# =============================================================================
# Smart Director Implementation
# =============================================================================

class SmartDirector:
    """
    AI-Powered Video Generation Orchestrator.

    Coordinates CLAP (audio), SigLIP (video), and Pacing Engine to create
    automatically edited videos synchronized with music.

    VRAM Management:
        Uses the "Staffellauf" (relay race) pattern where only one heavy model
        is loaded at a time. CLAP and SigLIP share the same VRAM budget.
    """

    # Singleton-Instanz (für ClipSelector.encode_text Zugriff)
    _instance: Optional['SmartDirector'] = None
    _instance_lock: threading.Lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'SmartDirector':
        """
        Gibt die globale Singleton-Instanz zurück (lazy-init, thread-safe).

        WARN-01 FIX: Double-Checked Locking verhindert Race Condition bei
        parallelen SSE-Verbindungen oder gleichzeitigen FastAPI-Requests.
        Ohne Lock könnten 2 Threads gleichzeitig 'cls._instance is None'
        als True sehen → 2 Instanzen → 2× VRAM-Reservierung.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:  # Zweite Prüfung innerhalb des Locks
                    cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        clap_wrapper=None,
        siglip_wrapper=None,
        pacing_engine=None,
        lazy_load: bool = True
    ):
        """
        Initialize the Smart Director.

        Args:
            clap_wrapper: CLAPAnalyzer instance (optional, created if None)
            siglip_wrapper: SigLIPWrapper instance (optional, created if None)
            pacing_engine: AdvancedPacingEngine instance (optional, created if None)
            lazy_load: If True, defer model loading until first use
        """
        from pb_studio.core import get_vram_manager
        from pb_studio.config_manager import ConfigManager

        self.config = ConfigManager()
        self.vram_manager = get_vram_manager()

        # Model wrappers (lazy initialized)
        self._clap: Optional[Any] = clap_wrapper
        self._siglip: Optional[Any] = siglip_wrapper
        self._pacing_engine = pacing_engine

        # Track which model is currently loaded
        self._active_model: Optional[str] = None  # "clap" or "siglip"

        # B-12 FIX: Thread-Sicherheit bei Inferenz & Eviction
        self._inference_lock = threading.Lock()

        # VRAM budgets (MB)
        # CLAPPyTorch laeuft auf CPU - kein VRAM noetig
        self._clap_budget = 0     # CLAP PyTorch laeuft auf CPU, nicht GPU
        self._siglip_budget = 900  # SigLIP SO400M needs more VRAM

        # Register models with VRAM manager
        self._register_models_with_vram_manager()

        # Mood-to-visual mapping for semantic matching
        self._mood_visual_mapping = self._build_mood_visual_mapping()

        # Standard prompts for content detection
        self._content_prompts = self._build_content_prompts()

        if not lazy_load:
            self._ensure_clap_loaded()

        logger.info("SmartDirector initialized (lazy_load=%s)", lazy_load)

    def _register_models_with_vram_manager(self):
        """Register SmartDirector models with the central VRAM manager."""
        from pb_studio.core import ModelPriority

        # Register CLAP model
        self.vram_manager.register_model(
            model_id="smart_director_clap",
            name="SmartDirector CLAP",
            estimated_vram_mb=self._clap_budget,
            priority=ModelPriority.MEDIUM,
            unload_callback=self._unload_clap
        )

        # Register SigLIP model
        self.vram_manager.register_model(
            model_id="smart_director_siglip",
            name="SmartDirector SigLIP",
            estimated_vram_mb=self._siglip_budget,
            priority=ModelPriority.MEDIUM,
            unload_callback=self._unload_siglip
        )

    # =========================================================================
    # VRAM Management (Staffellauf Pattern)
    # =========================================================================

    def _ensure_clap_loaded(self) -> bool:
        """
        Ensure CLAP model is loaded, unloading SigLIP if necessary.

        Returns:
            True if CLAP is ready
        """
        if self._active_model == "clap" and self._clap is not None:
            return True

        # Unload SigLIP first
        if self._active_model == "siglip":
            self._unload_siglip()

        return self._load_clap()

    def _ensure_siglip_loaded(self) -> bool:
        """
        Ensure SigLIP model is loaded, unloading CLAP if necessary.

        Returns:
            True if SigLIP is ready
        """
        if self._active_model == "siglip" and self._siglip is not None:
            return True

        # Unload CLAP first
        if self._active_model == "clap":
            self._unload_clap()

        return self._load_siglip()

    def _load_clap(self) -> bool:
        """Load CLAP model with VRAM management."""
        if self._clap is not None and self._active_model == "clap":
            return True

        try:
            logger.info("Loading CLAP model...")

            # Reserve VRAM
            if not self.vram_manager.reserve("smart_director_clap", force=True):
                logger.error("Cannot reserve VRAM for CLAP model")
                return False

            # Import and create CLAP wrapper (PyTorch version - ONNX models not available)
            from pb_studio.ai.clap_pytorch import CLAPPyTorch

            self._clap = CLAPPyTorch()

            if self._clap.load():
                self.vram_manager.commit("smart_director_clap")
                self._active_model = "clap"
                # BUG-052 FIX: CLAPPyTorch hat kein active_provider Attribut
                logger.info("CLAP model loaded successfully")
                return True
            else:
                logger.warning("CLAP model failed to initialize")
                self.vram_manager.cancel_reservation("smart_director_clap")
                self._clap = None
                return False

        except ImportError as e:
            logger.error("Failed to import CLAPPyTorch: %s", e)
            self.vram_manager.cancel_reservation("smart_director_clap")
            return False
        except Exception as e:
            logger.error("Failed to load CLAP: %s", e)
            self.vram_manager.cancel_reservation("smart_director_clap")
            return False

    def _unload_clap(self):
        """Unload CLAP model to free VRAM."""
        with self._inference_lock:
            if self._clap is not None:
                logger.info("Unloading CLAP model...")
                try:
                    if hasattr(self._clap, 'unload'):
                        self._clap.unload()
                except Exception as e:
                    logger.warning("Error unloading CLAP: %s", e)

                self._clap = None
                self.vram_manager.release("smart_director_clap")
                if self._active_model == "clap":
                    self._active_model = None

    def _load_siglip(self) -> bool:
        """Load SigLIP model with VRAM management."""
        if self._siglip is not None and self._active_model == "siglip":
            return True

        try:
            logger.info("Loading SigLIP model...")

            # Reserve VRAM
            if not self.vram_manager.reserve("smart_director_siglip", force=True):
                logger.error("Cannot reserve VRAM for SigLIP model")
                return False

            # Import and create SigLIP wrapper
            from pb_studio.ai.siglip_wrapper import SigLIPWrapper

            self._siglip = SigLIPWrapper(lazy_load=False)

            if self._siglip.is_ready:
                self.vram_manager.commit("smart_director_siglip")
                self._active_model = "siglip"
                logger.info("SigLIP model loaded successfully (Provider: %s)",
                           self._siglip.active_provider)
                return True
            else:
                logger.warning("SigLIP model failed to initialize")
                self.vram_manager.cancel_reservation("smart_director_siglip")
                self._siglip = None
                return False

        except ImportError as e:
            logger.error("Failed to import SigLIPWrapper: %s", e)
            self.vram_manager.cancel_reservation("smart_director_siglip")
            return False
        except Exception as e:
            logger.error("Failed to load SigLIP: %s", e)
            self.vram_manager.cancel_reservation("smart_director_siglip")
            return False

    def _unload_siglip(self):
        """Unload SigLIP model to free VRAM."""
        with self._inference_lock:
            if self._siglip is not None:
                logger.info("Unloading SigLIP model...")
                try:
                    if hasattr(self._siglip, 'unload'):
                        self._siglip.unload()
                except Exception as e:
                    logger.warning("Error unloading SigLIP: %s", e)

                self._siglip = None
                self.vram_manager.release("smart_director_siglip")
                if self._active_model == "siglip":
                    self._active_model = None

    def _run_with_vram_budget(self, task: str):
        """
        Context manager pattern for VRAM-safe model switching.

        Args:
            task: "audio" (uses CLAP) or "video" (uses SigLIP)
        """
        if task == "audio":
            self._unload_siglip()
            self._load_clap()
        elif task == "video":
            self._unload_clap()
            self._load_siglip()

    # =========================================================================
    # Audio Analysis
    # =========================================================================

    def get_dominant_mood(self, audio_path: str) -> str:
        """Returns the dominant mood as a string for use in prompts."""
        moods = self._analyze_mood(audio_path)
        if not moods:
            return "energetic music"
        # Get mood with highest probability
        dominant = max(moods.items(), key=lambda x: x[1])[0]
        return f"{dominant} music"

    def analyze_audio(self, audio_path: str) -> AudioAnalysis:
        """
        Analyze an audio file for BPM, beats, mood, and energy.

        Uses BeatNet for rhythm detection and CLAP for mood classification.

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)

        Returns:
            AudioAnalysis with all extracted features
        """
        logger.info("Analyzing audio: %s", audio_path)

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Step 1: Beat detection with BeatNet
        beat_data = self._analyze_beats(audio_path)

        # Step 2: Mood classification with CLAP
        self._ensure_clap_loaded()
        mood_data = self._analyze_mood(audio_path)

        # Step 3: Energy curve extraction
        energy_curve, energy_timestamps = self._extract_energy_curve(audio_path)

        # Step 4: Determine dominant mood
        dominant_mood = self._classify_dominant_mood(mood_data)

        # Get audio duration
        duration = self._get_audio_duration(audio_path)

        return AudioAnalysis(
            file_path=audio_path,
            duration_sec=duration,
            bpm=beat_data.get("bpm", 120.0),
            beat_times=beat_data.get("beat_times", []),
            downbeat_times=beat_data.get("downbeat_times", []),
            mood_tags=list(mood_data.keys()),
            mood_scores=mood_data,
            energy_curve=energy_curve,
            energy_timestamps=energy_timestamps,
            dominant_mood=dominant_mood
        )

    def _analyze_beats(self, audio_path: str) -> Dict[str, Any]:
        """Extract beat and rhythm information using BeatNet."""
        try:
            from pb_studio.audio.analyzer import AudioAnalyzer

            analyzer = AudioAnalyzer()
            result = analyzer.analyze_file(audio_path)

            if "error" in result:
                logger.warning("Beat analysis error: %s", result["error"])
                return {"bpm": 120.0, "beat_times": [], "downbeat_times": []}

            # Extract beat times from BeatNet output
            beat_times = []
            downbeat_times = []

            if "beat_data" in result and result["beat_data"]:
                for beat in result["beat_data"]:
                    time_sec = beat[0]
                    beat_type = beat[1] if len(beat) > 1 else 1

                    beat_times.append(time_sec)

                    # Downbeat markers (beat_type == 1 typically indicates downbeat)
                    if beat_type == 1:
                        downbeat_times.append(time_sec)

            return {
                "bpm": result.get("bpm", 120.0),
                "beat_times": beat_times,
                "downbeat_times": downbeat_times
            }

        except Exception as e:
            logger.error("Beat analysis failed: %s", e)
            return {"bpm": 120.0, "beat_times": [], "downbeat_times": []}

    def _analyze_mood(self, audio_path: str) -> Dict[str, float]:
        """Classify audio mood using CLAP zero-shot classification."""
        if self._clap is None:
            logger.warning("CLAP not loaded, returning neutral mood")
            return {"neutral": 1.0}

        try:
            # Define mood categories for CLAP classification
            mood_labels = [
                "energetic upbeat music",
                "calm relaxing music",
                "dark atmospheric music",
                "bright happy music",
                "aggressive intense music",
                "melancholic sad music",
                "uplifting inspirational music",
                "mysterious ambient music"
            ]

            # Map results to mood categories
            mood_mapping = {
                "energetic upbeat music": "energetic",
                "calm relaxing music": "calm",
                "dark atmospheric music": "dark",
                "bright happy music": "bright",
                "aggressive intense music": "aggressive",
                "melancholic sad music": "melancholic",
                "uplifting inspirational music": "uplifting",
                "mysterious ambient music": "mysterious"
            }

            # Run CLAP classification - returns List[Tuple[str, float]]
            with self._inference_lock:
                if self._clap is None:
                    return {"neutral": 1.0}
                results = self._clap.classify_audio(
                    audio_path,
                    labels=mood_labels,
                    top_k=len(mood_labels)
                )

            mood_scores = {}
            for label, score in results:
                mood_name = mood_mapping.get(label, label)
                mood_scores[mood_name] = score

            return mood_scores

        except Exception as e:
            logger.error("Mood analysis failed: %s", e)
            return {"neutral": 1.0}

    def _extract_energy_curve(
        self,
        audio_path: str,
        hop_length: int = 512,
        sr: int = 22050
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract energy/loudness curve from audio.

        Returns:
            Tuple of (energy_values, timestamps) as numpy arrays
        """
        try:
            import librosa

            # Load audio
            y, sr = librosa.load(audio_path, sr=sr, mono=True)

            # Compute RMS energy
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

            # Normalize to 0-1
            if rms.max() > 0:
                rms_normalized = rms / rms.max()
            else:
                rms_normalized = rms

            # Create timestamps
            times = librosa.times_like(rms, sr=sr, hop_length=hop_length)

            return rms_normalized.astype(np.float32), times.astype(np.float32)

        except ImportError:
            logger.warning("librosa not available, using fallback energy extraction")
            return self._extract_energy_fallback(audio_path)
        except Exception as e:
            logger.error("Energy extraction failed: %s", e)
            return np.array([0.5], dtype=np.float32), np.array([0.0], dtype=np.float32)

    def _extract_energy_fallback(self, audio_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """Fallback energy extraction without librosa."""
        try:
            import subprocess
            import tempfile
            import wave

            # Convert to WAV using FFmpeg
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            subprocess.run([
                "ffmpeg", "-y", "-i", audio_path,
                "-ac", "1", "-ar", "22050", "-acodec", "pcm_s16le",
                tmp_path
            ], capture_output=True, timeout=120)

            # Read WAV
            with wave.open(tmp_path, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                sr = wf.getframerate()

            # Compute RMS in windows
            window_size = 2048
            hop = 512

            rms_values = []
            for i in range(0, len(samples) - window_size, hop):
                window = samples[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                rms_values.append(rms)

            rms_array = np.array(rms_values, dtype=np.float32)
            if rms_array.max() > 0:
                rms_array = rms_array / rms_array.max()

            times = np.arange(len(rms_array)) * hop / sr

            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)

            return rms_array, times.astype(np.float32)

        except Exception as e:
            logger.error("Fallback energy extraction failed: %s", e)
            return np.array([0.5], dtype=np.float32), np.array([0.0], dtype=np.float32)

    def _classify_dominant_mood(self, mood_scores: Dict[str, float]) -> MoodCategory:
        """Determine the dominant mood category."""
        if not mood_scores:
            return MoodCategory.NEUTRAL

        # Find highest scoring mood
        dominant = max(mood_scores.items(), key=lambda x: x[1])
        mood_name = dominant[0].lower()

        # Map to MoodCategory enum
        mood_map = {
            "energetic": MoodCategory.ENERGETIC,
            "calm": MoodCategory.CALM,
            "dark": MoodCategory.DARK,
            "bright": MoodCategory.BRIGHT,
            "aggressive": MoodCategory.AGGRESSIVE,
            "melancholic": MoodCategory.MELANCHOLIC,
            "uplifting": MoodCategory.UPLIFTING,
            "mysterious": MoodCategory.MYSTERIOUS
        }

        return mood_map.get(mood_name, MoodCategory.NEUTRAL)

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration in seconds."""
        try:
            import subprocess

            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ], capture_output=True, text=True, timeout=15)

            stdout = result.stdout.strip()
            if not stdout or result.returncode != 0:
                return 180.0
            return float(stdout)

        except Exception as e:
            logger.warning("Could not determine audio duration: %s", e)
            return 180.0  # Default 3 minutes

    # =========================================================================
    # Video Analysis
    # =========================================================================

    def analyze_clips(self, video_paths: List[str]) -> List[ClipAnalysis]:
        """
        Analyze multiple video clips for visual content and motion.

        Uses SigLIP for visual embeddings and content classification.

        Args:
            video_paths: List of paths to video files

        Returns:
            List of ClipAnalysis objects
        """
        logger.info("Analyzing %d video clips", len(video_paths))

        # Switch to SigLIP model
        self._ensure_siglip_loaded()

        results = []
        for path in video_paths:
            try:
                analysis = self._analyze_single_clip(path)
                results.append(analysis)
            except Exception as e:
                logger.error("Failed to analyze clip %s: %s", path, e)

        return results

    def _analyze_single_clip(self, video_path: str) -> ClipAnalysis:
        """Analyze a single video clip."""
        import cv2

        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Open video
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Sample frames for analysis
            sample_frames = self._sample_frames(cap, num_samples=5)
        finally:
            cap.release()

        if not sample_frames:
            raise RuntimeError(f"No frames extracted from: {video_path}")

        # Get visual embedding using SigLIP
        embedding = self._get_clip_embedding(sample_frames)

        # Classify content
        content_tags, content_scores = self._classify_clip_content(sample_frames)

        # Analyze motion
        motion_score = self._analyze_motion(video_path)

        # Analyze visual properties
        brightness = self._analyze_brightness(sample_frames)
        dominant_colors = self._analyze_colors(sample_frames)

        return ClipAnalysis(
            file_path=video_path,
            duration_sec=duration,
            embedding=embedding,
            content_tags=content_tags,
            content_scores=content_scores,
            motion_score=motion_score,
            brightness=brightness,
            dominant_colors=dominant_colors,
            fps=fps,
            resolution=(width, height)
        )

    def _sample_frames(
        self,
        cap,
        num_samples: int = 5
    ) -> List[np.ndarray]:
        """Sample evenly distributed frames from video."""
        import cv2

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < num_samples:
            num_samples = max(1, total_frames)

        # Calculate frame indices
        indices = np.linspace(0, total_frames - 1, num_samples, dtype=int)

        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)

        return frames

    def _get_clip_embedding(self, frames: List[np.ndarray]) -> np.ndarray:
        """Get visual embedding for clip using SigLIP."""
        from PIL import Image

        # SigLIP SO400M uses 1152-dim embeddings
        embedding_dim = 1152

        if self._siglip is None:
            logger.warning("SigLIP not loaded, returning zero embedding")
            return np.zeros(embedding_dim, dtype=np.float32)

        try:
            # Use middle frame for primary embedding
            middle_frame = frames[len(frames) // 2]

            # Convert BGR (OpenCV) to RGB PIL Image
            rgb_frame = middle_frame[:, :, ::-1]  # BGR to RGB
            pil_image = Image.fromarray(rgb_frame)

            with self._inference_lock:
                if self._siglip is None:
                    return np.zeros(embedding_dim, dtype=np.float32)
                embedding = self._siglip.encode_image(pil_image)

            if embedding is None:
                return np.zeros(embedding_dim, dtype=np.float32)

            return embedding

        except Exception as e:
            logger.error("Failed to get clip embedding: %s", e)
            return np.zeros(embedding_dim, dtype=np.float32)

    def _classify_clip_content(
        self,
        frames: List[np.ndarray]
    ) -> Tuple[List[str], Dict[str, float]]:
        """Classify visual content using SigLIP zero-shot."""
        from PIL import Image

        if self._siglip is None:
            return [], {}

        try:
            # Use middle frame
            middle_frame = frames[len(frames) // 2]

            # Convert BGR (OpenCV) to RGB PIL Image
            rgb_frame = middle_frame[:, :, ::-1]  # BGR to RGB
            pil_image = Image.fromarray(rgb_frame)

            # Classify with content prompts - returns List[Tuple[str, float]]
            with self._inference_lock:
                if self._siglip is None:
                    return [], {}
                results = self._siglip.classify_image(
                    pil_image,
                    labels=self._content_prompts
                )

            # Convert to dict and filter to high-confidence tags
            threshold = 0.3
            content_scores = {label: score for label, score in results}
            tags = [label for label, score in results if score > threshold]

            return tags, content_scores

        except Exception as e:
            logger.error("Content classification failed: %s", e)
            return [], {}

    def _analyze_motion(self, video_path: str) -> float:
        """Analyze average motion intensity in clip."""
        try:
            from pb_studio.video.raft import FarnebackFlowAnalyzer
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return 0.5

            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                # Sample frame pairs for motion analysis
                motion_scores = []
                analyzer = FarnebackFlowAnalyzer()  # Use CPU fallback to save VRAM

                prev_frame = None
                sample_interval = max(1, total_frames // 10)

                for i in range(0, total_frames, sample_interval):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if prev_frame is not None:
                        motion = analyzer.get_motion_magnitude(prev_frame, frame)
                        # Normalize motion score (typical range 0-100)
                        normalized = min(1.0, motion / 50.0)
                        motion_scores.append(normalized)

                    prev_frame = frame
            finally:
                cap.release()

            if motion_scores:
                return float(np.mean(motion_scores))
            return 0.5

        except Exception as e:
            logger.warning("Motion analysis failed: %s", e)
            return 0.5

    def _analyze_brightness(self, frames: List[np.ndarray]) -> float:
        """Calculate average brightness (0-1)."""
        import cv2

        brightness_values = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_values.append(np.mean(gray) / 255.0)

        return float(np.mean(brightness_values)) if brightness_values else 0.5

    def _analyze_colors(
        self,
        frames: List[np.ndarray],
        num_colors: int = 3
    ) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from frames."""
        import cv2

        try:
            # Combine frames
            combined_pixels = []
            for frame in frames:
                small = cv2.resize(frame, (50, 50))
                pixels = small.reshape(-1, 3)
                combined_pixels.append(pixels)

            all_pixels = np.vstack(combined_pixels)

            # K-means clustering
            from sklearn.cluster import KMeans

            kmeans = KMeans(n_clusters=num_colors, n_init=10, random_state=42)
            kmeans.fit(all_pixels)

            colors = []
            for center in kmeans.cluster_centers_:
                # BGR to RGB
                colors.append((int(center[2]), int(center[1]), int(center[0])))

            return colors

        except ImportError:
            # Fallback without sklearn
            return [(128, 128, 128)] * num_colors
        except Exception as e:
            logger.warning("Color analysis failed: %s", e)
            return [(128, 128, 128)] * num_colors

    # =========================================================================
    # Timeline Generation
    # =========================================================================

    def generate_timeline(
        self,
        audio: AudioAnalysis,
        clips: List[ClipAnalysis],
        config: Optional[Any] = None
    ) -> Timeline:
        """
        Generate a video timeline synchronized with audio.

        Uses semantic matching to pair audio moods with visual content,
        and the Pacing Engine for cut timing based on beats.

        Args:
            audio: AudioAnalysis from analyze_audio()
            clips: List of ClipAnalysis from analyze_clips()
            config: PacingConfig (optional, uses defaults if None)

        Returns:
            Timeline with clip placements and cut points
        """
        logger.info("Generating timeline for %.1fs audio with %d clips",
                    audio.duration_sec, len(clips))

        if not clips:
            raise ValueError("No clips provided for timeline generation")

        # Initialize pacing engine if needed
        if self._pacing_engine is None:
            self._init_pacing_engine()

        # Step 1: Generate cut points from beats
        cut_points = self._generate_cut_points(audio, config)

        # Step 2: Calculate clip match scores
        match_matrix = self._calculate_match_matrix(audio, clips)

        # Step 3: Assign clips to segments
        timeline_clips = self._assign_clips_to_segments(
            audio, clips, cut_points, match_matrix
        )

        # Step 4: Optimize transitions
        timeline_clips = self._optimize_transitions(timeline_clips, audio)

        # Step 5: Lücken füllen damit Video = Audio-Dauer (NV-kompatibel)
        if timeline_clips and audio.duration_sec > 0:
            timeline_clips = self._fill_timeline_gaps(timeline_clips, audio.duration_sec)

        # Calculate statistics
        total_clips = len(timeline_clips)
        avg_duration = np.mean([c.duration for c in timeline_clips]) if timeline_clips else 0
        cuts_per_min = len(cut_points) / (audio.duration_sec / 60) if audio.duration_sec > 0 else 0

        return Timeline(
            audio_path=audio.file_path,
            duration_sec=audio.duration_sec,
            clips=timeline_clips,
            cut_points=cut_points,
            total_clips=total_clips,
            average_clip_duration=float(avg_duration),
            cuts_per_minute=float(cuts_per_min)
        )

    def _init_pacing_engine(self):
        """Initialize the pacing engine."""
        try:
            from pb_studio.pacing import AdvancedPacingEngine
            self._pacing_engine = AdvancedPacingEngine()
        except ImportError:
            logger.warning("AdvancedPacingEngine not available")
            self._pacing_engine = None

    def _generate_cut_points(
        self,
        audio: AudioAnalysis,
        config: Optional[Any] = None
    ) -> List[float]:
        """Generate cut points based on audio beats and energy."""
        cut_points = [0.0]  # Start at beginning

        if self._pacing_engine is not None:
            try:
                # Prepare audio analysis dict for pacing engine
                analysis_dict = {
                    "bpm": audio.bpm,
                    "beat_data": [[t, 1 if t in audio.downbeat_times else 2]
                                  for t in audio.beat_times]
                }

                # Feed analysis to pacing engine
                self._pacing_engine.analyze_audio_structure(
                    analysis=analysis_dict,
                    rms=audio.energy_curve,
                    times=audio.energy_timestamps
                )

                # Apply config if provided
                if config is not None:
                    self._pacing_engine.config = config

                # Generate cuts using pacing engine
                cut_point_objs = self._pacing_engine.plan_cuts(audio.duration_sec)

                # Extract timestamps from CutPoint objects
                for cp in cut_point_objs:
                    cut_points.append(cp.time)
                    if cp.end_time < audio.duration_sec:
                        cut_points.append(cp.end_time)

                cut_points = sorted(set(cut_points))
                return cut_points

            except Exception as e:
                logger.warning("Pacing engine failed, using fallback: %s", e)

        # Fallback: Cut on every 2nd or 4th beat
        beat_interval = 4 if audio.bpm > 100 else 2

        for i, beat_time in enumerate(audio.beat_times):
            if i % beat_interval == 0:
                cut_points.append(beat_time)

        # Ensure end point
        if cut_points[-1] < audio.duration_sec:
            cut_points.append(audio.duration_sec)

        return sorted(set(cut_points))

    def _calculate_match_matrix(
        self,
        audio: AudioAnalysis,
        clips: List[ClipAnalysis]
    ) -> np.ndarray:
        """
        Calculate mood-to-content match scores for all clips.

        Returns:
            Matrix of shape (num_moods, num_clips) with match scores
        """
        mood_tags = list(audio.mood_scores.keys())
        num_moods = len(mood_tags)
        num_clips = len(clips)

        match_matrix = np.zeros((num_moods, num_clips), dtype=np.float32)

        for i, mood in enumerate(mood_tags):
            for j, clip in enumerate(clips):
                score = self._calculate_mood_clip_match(mood, clip)
                match_matrix[i, j] = score

        return match_matrix

    def _calculate_mood_clip_match(
        self,
        mood: str,
        clip: ClipAnalysis
    ) -> float:
        """Calculate how well a clip matches a mood."""
        score = 0.5  # Neutral baseline

        # Get visual keywords for this mood
        mood_visuals = self._mood_visual_mapping.get(mood.lower(), [])

        # Check clip content tags for matches
        for tag in clip.content_tags:
            tag_lower = tag.lower()
            for visual in mood_visuals:
                if visual in tag_lower:
                    score += 0.2

        # Energy matching
        if mood.lower() in ["energetic", "aggressive"]:
            score += clip.motion_score * 0.3
        elif mood.lower() in ["calm", "melancholic"]:
            score += (1 - clip.motion_score) * 0.3

        # Brightness matching
        if mood.lower() in ["bright", "uplifting"]:
            score += clip.brightness * 0.2
        elif mood.lower() in ["dark", "mysterious"]:
            score += (1 - clip.brightness) * 0.2

        return min(1.0, max(0.0, score))

    def _assign_clips_to_segments(
        self,
        audio: AudioAnalysis,
        clips: List[ClipAnalysis],
        cut_points: List[float],
        match_matrix: np.ndarray
    ) -> List[TimelineClip]:
        """Assign clips to timeline segments based on match scores."""
        timeline_clips = []

        # Get weighted mood for each segment
        mood_weights = np.array(list(audio.mood_scores.values()))
        if mood_weights.sum() > 0:
            mood_weights = mood_weights / mood_weights.sum()
        else:
            mood_weights = np.ones(len(mood_weights)) / len(mood_weights)

        # Weighted clip scores
        clip_scores = np.dot(mood_weights, match_matrix)

        # Track clip usage to avoid repetition
        clip_usage = {i: 0 for i in range(len(clips))}

        for i in range(len(cut_points) - 1):
            start_time = cut_points[i]
            end_time = cut_points[i + 1]
            segment_duration = end_time - start_time

            # Get energy at this point
            energy_idx = np.searchsorted(audio.energy_timestamps, start_time)
            energy_idx = min(energy_idx, len(audio.energy_curve) - 1)
            segment_energy = audio.energy_curve[energy_idx]

            # Select best clip (penalize recently used clips)
            adjusted_scores = clip_scores.copy()
            for j, usage in clip_usage.items():
                adjusted_scores[j] *= (1 / (1 + usage * 0.5))

            best_clip_idx = int(np.argmax(adjusted_scores))
            clip_usage[best_clip_idx] += 1

            selected_clip = clips[best_clip_idx]

            # Determine source segment
            source_duration = selected_clip.duration_sec
            if source_duration > segment_duration:
                # Pick a random start point
                max_start = source_duration - segment_duration
                source_start = np.random.uniform(0, max_start)
                source_end = source_start + segment_duration
            else:
                # Use entire clip
                source_start = 0
                source_end = source_duration

            # Calculate match metrics
            mood_alignment = clip_scores[best_clip_idx]
            energy_alignment = 1 - abs(selected_clip.motion_score - segment_energy)
            match_score = (mood_alignment + energy_alignment) / 2

            timeline_clips.append(TimelineClip(
                source_path=selected_clip.file_path,
                start_time=start_time,
                duration=segment_duration,
                source_start=source_start,
                source_end=source_end,
                match_score=float(match_score),
                mood_alignment=float(mood_alignment),
                energy_alignment=float(energy_alignment)
            ))

        return timeline_clips

    def _optimize_transitions(
        self,
        clips: List[TimelineClip],
        audio: AudioAnalysis
    ) -> List[TimelineClip]:
        """Optimize transitions between clips based on audio features."""
        for i, clip in enumerate(clips):
            # Find if cut point falls on a downbeat
            on_downbeat = any(
                abs(clip.start_time - dt) < 0.05
                for dt in audio.downbeat_times
            )

            # High energy = hard cut, low energy = fade
            energy_idx = np.searchsorted(audio.energy_timestamps, clip.start_time)
            energy_idx = min(energy_idx, len(audio.energy_curve) - 1)
            energy = audio.energy_curve[energy_idx]

            if on_downbeat or energy > 0.7:
                clip.transition_in = "cut"
            elif energy < 0.3:
                clip.transition_in = "fade"
            else:
                clip.transition_in = "dissolve"

            # Set transition out based on next clip
            if i < len(clips) - 1:
                next_energy_idx = np.searchsorted(
                    audio.energy_timestamps,
                    clips[i + 1].start_time
                )
                next_energy_idx = min(next_energy_idx, len(audio.energy_curve) - 1)
                next_energy = audio.energy_curve[next_energy_idx]

                if next_energy > 0.7:
                    clip.transition_out = "cut"
                elif next_energy < 0.3:
                    clip.transition_out = "fade"
                else:
                    clip.transition_out = "dissolve"

        return clips

    def _fill_timeline_gaps(
        self,
        clips: List[TimelineClip],
        audio_duration: float,
        min_gap: float = 0.1
    ) -> List[TimelineClip]:
        """
        Füllt Lücken in der Timeline durch Recycling vorhandener Clips.

        Stellt sicher, dass die Video-Timeline lückenlos von 0 bis audio_duration reicht.
        AMD-Adapter: arbeitet mit TimelineClip-Dataclasses statt Dicts (wie NV-Version).

        Args:
            clips: Bestehende TimelineClip-Liste
            audio_duration: Ziel-Dauer (= Audio-Länge)
            min_gap: Minimale Lücke die gefüllt wird (Sekunden)

        Returns:
            Erweiterte Timeline ohne Lücken
        """
        if not clips:
            return clips

        # Nach start_time sortieren
        clips = sorted(clips, key=lambda c: c.start_time)

        # Lücken identifizieren
        gaps = []

        # Lücke am Anfang
        if clips[0].start_time > min_gap:
            gaps.append((0.0, clips[0].start_time))

        # Lücken zwischen Clips
        for i in range(len(clips) - 1):
            curr_end = clips[i].start_time + clips[i].duration
            next_start = clips[i + 1].start_time
            if next_start - curr_end > min_gap:
                gaps.append((curr_end, next_start))

        # Lücke am Ende
        last_end = clips[-1].start_time + clips[-1].duration
        if audio_duration - last_end > min_gap:
            gaps.append((last_end, audio_duration))

        if not gaps:
            return clips

        total_gap = sum(end - start for start, end in gaps)
        logger.info("Gap-Filling: %d Lücken gefunden, gesamt %.1fs", len(gaps), total_gap)

        # Füller-Clips per Round-Robin aus vorhandenen erzeugen
        fill_index = 0
        last_fill_path = None
        for gap_start, gap_end in gaps:
            pos = gap_start
            while pos < gap_end - min_gap:
                source = clips[fill_index % len(clips)]
                fill_index += 1
                # Direkte Wiederholung vermeiden (Variety)
                if len(clips) > 1 and source.source_path == last_fill_path:
                    source = clips[fill_index % len(clips)]
                    fill_index += 1

                remaining = gap_end - pos
                
                # BUG-077 FIX: Prüfe verfügbare Quelldauer und verhindere Null-Schritte
                src_avail = source.source_end - source.source_start
                if src_avail <= 0.001:
                    fill_index += 1
                    continue

                fill_dur = min(src_avail, remaining)
                if fill_dur <= 0.001:
                    break

                filler = TimelineClip(
                    source_path=source.source_path,
                    start_time=pos,
                    duration=fill_dur,
                    source_start=source.source_start,
                    source_end=source.source_start + fill_dur,
                    match_score=source.match_score,
                    mood_alignment=source.mood_alignment,
                    energy_alignment=source.energy_alignment,
                    transition_in="cut",
                    transition_out="cut",
                    speed_factor=source.speed_factor,
                )
                clips.append(filler)
                last_fill_path = filler.source_path
                pos += fill_dur

        # Neu sortieren
        clips = sorted(clips, key=lambda c: c.start_time)
        logger.info("Timeline nach Gap-Filling: %d Clips (lückenlos bis %.1fs)",
                    len(clips), audio_duration)
        return clips

    def encode_text(self, text: str) -> Optional[np.ndarray]:
        """
        Kodiert einen Text-String mit SigLIP zu einem Embedding.

        Wird von ClipSelector._get_text_embedding() genutzt.
        Stellt sicher, dass SigLIP geladen ist (Staffellauf-Pattern).

        Args:
            text: Mood-Text oder Prompt-String

        Returns:
            numpy-Array (1152-dim) oder None bei Fehler
        """
        if not self._ensure_siglip_loaded():
            logger.warning("encode_text: SigLIP nicht geladen, gebe None zurück")
            return None

        try:
            with self._inference_lock:
                if self._siglip is None:
                    return None
                embedding = self._siglip.encode_text(text)
            if embedding is None:
                return None

            # PyTorch Tensor → numpy (HINT-02 FIX: korrekte Reihenfolge .detach()→.cpu()→.numpy())
            # .detach() muss VOR .cpu() kommen, weil .numpy() bei requires_grad=True-Tensors
            # sonst mit RuntimeError fehlschlägt.
            if hasattr(embedding, "detach"):
                embedding = embedding.detach()
            if hasattr(embedding, "cpu"):
                embedding = embedding.cpu()
            if hasattr(embedding, "numpy"):
                embedding = embedding.numpy()

            embedding = np.array(embedding, dtype=np.float32)

            # 2D → 1D
            if len(embedding.shape) > 1:
                embedding = embedding[0]

            return embedding

        except Exception as e:
            logger.warning("encode_text fehlgeschlagen: %s", e)
            return None

    # =========================================================================
    # Semantic Matching
    # =========================================================================

    def match_mood_to_content(
        self,
        mood_tags: List[str],
        clip_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Cross-modal matching between audio moods and video embeddings.

        Args:
            mood_tags: List of mood descriptions
            clip_embeddings: Array of shape (num_clips, embedding_dim)

        Returns:
            Match scores of shape (num_moods, num_clips)
        """
        if self._siglip is None or not self._siglip.has_text_encoder:
            logger.warning("SigLIP text encoder not loaded, returning uniform scores")
            num_moods = len(mood_tags)
            num_clips = clip_embeddings.shape[0] if len(clip_embeddings.shape) > 1 else 1
            return np.ones((num_moods, num_clips), dtype=np.float32) / num_clips

        try:
            # Get text embeddings for mood tags (as visual descriptions)
            visual_descriptions = [self._mood_to_visual_prompt(mood) for mood in mood_tags]

            # SigLIP.encode_text can handle a list of strings
            with self._inference_lock:
                if self._siglip is None:
                    raise RuntimeError("SigLIP model unexpectedly unloaded")
                mood_embeddings = self._siglip.encode_text(visual_descriptions)

            if mood_embeddings is None:
                logger.warning("Failed to encode mood descriptions")
                num_clips = clip_embeddings.shape[0] if len(clip_embeddings.shape) > 1 else 1
                return np.ones((len(mood_tags), num_clips), dtype=np.float32) / num_clips

            # Ensure clip_embeddings is 2D
            if len(clip_embeddings.shape) == 1:
                clip_embeddings = clip_embeddings.reshape(1, -1)

            # Cosine similarity
            # Normalize
            mood_norm = mood_embeddings / (np.linalg.norm(mood_embeddings, axis=1, keepdims=True) + 1e-8)
            clip_norm = clip_embeddings / (np.linalg.norm(clip_embeddings, axis=1, keepdims=True) + 1e-8)

            # Similarity matrix
            similarity = np.dot(mood_norm, clip_norm.T)

            # Convert to scores (0-1)
            scores = (similarity + 1) / 2

            return scores.astype(np.float32)

        except Exception as e:
            logger.error("Cross-modal matching failed: %s", e)
            num_clips = clip_embeddings.shape[0] if len(clip_embeddings.shape) > 1 else 1
            return np.ones((len(mood_tags), num_clips), dtype=np.float32)

    def _mood_to_visual_prompt(self, mood: str) -> str:
        """Convert mood tag to visual description for SigLIP matching."""
        prompts = {
            "energetic": "fast action, vibrant colors, movement, dancing",
            "calm": "peaceful scenery, slow motion, nature, tranquil",
            "dark": "shadows, night scene, dramatic lighting, moody",
            "bright": "sunny day, colorful, happy people, outdoor",
            "aggressive": "intense action, fast cuts, sports, explosions",
            "melancholic": "rain, solitude, empty spaces, contemplative",
            "uplifting": "sunrise, celebration, achievement, joy",
            "mysterious": "fog, silhouettes, abstract, cinematic"
        }
        return prompts.get(mood.lower(), mood)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _build_mood_visual_mapping(self) -> Dict[str, List[str]]:
        """Build mapping from audio moods to visual keywords."""
        return {
            "energetic": ["action", "sports", "dance", "party", "movement", "fast"],
            "calm": ["nature", "water", "sky", "peaceful", "slow", "gentle"],
            "dark": ["night", "shadow", "dark", "gothic", "noir", "dramatic"],
            "bright": ["sun", "colorful", "happy", "day", "outdoor", "vibrant"],
            "aggressive": ["action", "intense", "sports", "explosion", "power"],
            "melancholic": ["rain", "alone", "empty", "sad", "contemplative"],
            "uplifting": ["sunrise", "celebration", "happy", "success", "joy"],
            "mysterious": ["fog", "abstract", "cinematic", "artistic", "surreal"]
        }

    def _build_content_prompts(self) -> List[str]:
        """Build standard prompts for video content classification."""
        return [
            "people dancing",
            "nature scenery",
            "city skyline",
            "sports action",
            "concert performance",
            "abstract visuals",
            "faces and portraits",
            "cars and vehicles",
            "water and ocean",
            "night scene",
            "aerial view",
            "slow motion",
            "crowd of people",
            "empty landscape",
            "indoor scene",
            "outdoor scene"
        ]

    @property
    def is_ready(self) -> bool:
        """Check if director is ready for analysis."""
        return True  # We can always do beat analysis at minimum

    @property
    def active_model(self) -> Optional[str]:
        """Get currently loaded model name."""
        return self._active_model

    def get_vram_usage(self) -> Dict[str, int]:
        """Get current VRAM usage estimate."""
        usage = {"total": 0}

        if self._active_model == "clap":
            usage["clap"] = self._clap_budget
            usage["total"] = self._clap_budget
        elif self._active_model == "siglip":
            usage["siglip"] = self._siglip_budget
            usage["total"] = self._siglip_budget

        return usage

    def unload_all(self):
        """Unload all models to free VRAM."""
        self._unload_clap()
        self._unload_siglip()
        logger.info("All SmartDirector models unloaded")

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance so next get_instance() creates a fresh one.

        Call this after unload_all() to ensure VRAM is fully freed
        and models will be re-initialized on next access.
        """
        with cls._instance_lock:
            cls._instance = None
            logger.info("SmartDirector singleton instance reset")
