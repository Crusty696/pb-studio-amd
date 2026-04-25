"""
Worker Orchestrator for PB Studio AMD

Provides high-level pipeline orchestration for audio, video, and generation tasks.
Handles worker dependencies, VRAM coordination, and progress aggregation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from .worker_registry import WorkerRegistry
from .base_worker import BaseWorker, CancelledError
from .registry_setup import setup_worker_registry

# Audio workers
from .audio import (
    AudioImportWorker,
    AudioAnalyzeWorker,
    AudioStemWorker,
    AudioEmbeddingWorker,
)

# Video workers
from .video import (
    VideoImportWorker,
    VideoSceneWorker,
    VideoMotionWorker,
    VideoVisionWorker,
)

# Generation workers
from .generation import (
    ExportWorker,
)

# Models
from ..models.audio import StemResult
from ..models.video import VideoMetadata, SceneInfo, MotionData

logger = logging.getLogger(__name__)


@dataclass
class AudioPipelineResult:
    """Result container for the audio analysis pipeline."""
    # Import phase
    temp_wav_path: str = ""
    metadata: Optional[Any] = None

    # Analysis phase
    bpm: float = 0.0
    beat_times: list[float] = field(default_factory=list)
    downbeat_times: list[float] = field(default_factory=list)
    energy_curve: list[float] = field(default_factory=list)
    energy_times: list[float] = field(default_factory=list)
    confidence: float = 0.0

    # Stem separation phase (optional)
    stems: Optional[StemResult] = None

    # Embedding phase (optional)
    embeddings: list[list[float]] = field(default_factory=list)
    embedding_timestamps: list[float] = field(default_factory=list)

    # Status
    success: bool = False
    error_message: str = ""
    phases_completed: list[str] = field(default_factory=list)


@dataclass
class VideoPipelineResult:
    """Result container for the video analysis pipeline."""
    # Import phase
    metadata: Optional[VideoMetadata] = None
    file_path: str = ""

    # Scene detection phase
    scenes: list[SceneInfo] = field(default_factory=list)

    # Motion analysis phase
    motion_data: list[MotionData] = field(default_factory=list)
    motion_analyzer_type: str = ""

    # Vision analysis phase
    captions: dict[int, dict[str, str]] = field(default_factory=dict)
    vision_model_type: str = ""

    # Status
    success: bool = False
    error_message: str = ""
    phases_completed: list[str] = field(default_factory=list)


class WorkerOrchestrator(QObject):
    """
    High-level orchestrator for running worker pipelines.

    Coordinates multiple workers in sequence, handles VRAM allocation via
    VRAMArbiter, and emits aggregated progress signals.

    Supports three main pipelines:
    - Audio Pipeline: Import -> Analyze -> [Stem] -> [Embedding]
    - Video Pipeline: Import -> Scene -> [Motion] -> [Vision]
    - Generation Pipeline: Pacing -> Render -> Concat -> Final

    Example:
        orchestrator = WorkerOrchestrator()
        orchestrator.progress_updated.connect(on_progress)
        orchestrator.pipeline_completed.connect(on_complete)

        # Run audio pipeline
        result = orchestrator.run_audio_pipeline(
            file_path="song.mp3",
            include_stems=True,
            include_embeddings=False
        )
    """

    # Signals
    progress_updated = pyqtSignal(dict)  # {percent, message, phase, worker}
    phase_completed = pyqtSignal(str)    # phase name
    pipeline_completed = pyqtSignal(object)  # result object
    error_occurred = pyqtSignal(str, str)  # phase, error_message

    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize the worker orchestrator.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)

        # Initialize registry if needed
        self._registry = WorkerRegistry()
        if not self._registry.list_workers():
            setup_worker_registry(self._registry)

        # VRAM arbiter (lazy load to avoid circular imports)
        self._vram_arbiter = None

        # Thread pool for async execution
        self._thread_pool = QThreadPool.globalInstance()

        # Cancellation flag
        self._cancelled = False

        # Referenz auf den aktuell laufenden Worker (fuer cancel()-Propagation)
        self._current_worker: Optional[BaseWorker] = None

    @property
    def vram_arbiter(self):
        """Lazy-load VRAM arbiter."""
        if self._vram_arbiter is None:
            try:
                from ..core.vram_arbiter import VRAMArbiter
                from ..core.system_monitor import SystemMonitor
                monitor = SystemMonitor()
                self._vram_arbiter = VRAMArbiter(monitor)
            except Exception as e:
                logger.warning(f"Could not initialize VRAMArbiter: {e}")
        return self._vram_arbiter

    def cancel(self) -> None:
        """Request cancellation of current pipeline and active worker."""
        self._cancelled = True
        if self._current_worker is not None:
            self._current_worker.cancel()
        logger.info("Pipeline cancellation requested")

    def _check_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def _emit_progress(
        self,
        percent: int,
        message: str,
        phase: str,
        worker: str = ""
    ) -> None:
        """Emit progress update signal."""
        self.progress_updated.emit({
            "percent": percent,
            "message": message,
            "phase": phase,
            "worker": worker
        })

    def _check_vram(self, worker_name: str) -> bool:
        """
        Check if VRAM is available for a worker.

        Args:
            worker_name: Registered worker name

        Returns:
            True if VRAM is available or check is not possible
        """
        if self.vram_arbiter is None:
            return True

        try:
            vram_needed = self._registry.get_vram_budget(worker_name)
            if vram_needed == 0:
                return True

            return self.vram_arbiter.can_allocate(vram_needed, model_id=worker_name)
        except Exception as e:
            logger.warning(f"VRAM check failed for {worker_name}: {e}")
            return True  # Allow to proceed on error

    def _run_worker_sync(self, worker: BaseWorker) -> Any:
        """
        Run a worker synchronously and return its result.

        Args:
            worker: Worker instance to run

        Returns:
            Result from the worker's _execute() method

        Raises:
            Exception: If worker fails
        """
        # Check cancellation
        if self._check_cancelled():
            raise InterruptedError("Pipeline was cancelled")

        # Worker-Referenz speichern fuer cancel()-Propagation
        self._current_worker = worker
        try:
            # BUG-083 FIX: Rufe .run() statt ._execute() auf, damit Signale (finished, error) emittiert werden
            return worker.run()
        finally:
            self._current_worker = None

    # =========================================================================
    # Audio Pipeline
    # =========================================================================

    def run_audio_pipeline(
        self,
        file_path: str,
        include_stems: bool = False,
        include_embeddings: bool = False,
        stem_model: str = "UVR-MDX-NET-Inst_HQ_3.onnx",
        project_id: Optional[str] = None,
    ) -> AudioPipelineResult:
        """
        Run the complete audio analysis pipeline.

        Pipeline phases:
        1. Import: Convert audio to WAV format
        2. Analyze: Beat detection and BPM analysis
        3. Stem (optional): Separate vocals/instruments
        4. Embedding (optional): Generate CLAP embeddings

        Args:
            file_path: Path to audio file
            include_stems: Whether to run stem separation
            include_embeddings: Whether to generate embeddings
            stem_model: Model name for stem separation
            project_id: Optional project ID for tracking

        Returns:
            AudioPipelineResult with all analysis data
        """
        self._cancelled = False
        result = AudioPipelineResult()

        try:
            # Phase 1: Import (0-20%)
            self._emit_progress(0, "Importing audio...", "import", "AudioImportWorker")

            if not self._check_vram("audio_import"):
                raise RuntimeError("Insufficient VRAM for audio import")

            import_worker = AudioImportWorker(file_path, project_id)
            import_result = self._run_worker_sync(import_worker)

            result.temp_wav_path = import_result.temp_wav_path
            result.metadata = import_result.metadata
            result.phases_completed.append("import")
            self.phase_completed.emit("import")

            # Phase 2: Analyze (20-50%)
            self._emit_progress(20, "Analyzing audio...", "analyze", "AudioAnalyzeWorker")

            if self._check_cancelled():
                raise InterruptedError("Pipeline cancelled")

            if not self._check_vram("audio_analyze"):
                raise RuntimeError("Insufficient VRAM for audio analysis")

            analyze_worker = AudioAnalyzeWorker(result.temp_wav_path)
            analysis_result = self._run_worker_sync(analyze_worker)

            result.bpm = analysis_result.bpm
            result.beat_times = analysis_result.beat_times
            result.downbeat_times = analysis_result.downbeat_times
            result.energy_curve = analysis_result.energy_curve
            result.energy_times = analysis_result.energy_times
            result.confidence = analysis_result.confidence
            result.phases_completed.append("analyze")
            self.phase_completed.emit("analyze")

            # Phase 3: Stem Separation (optional, 50-75%)
            if include_stems:
                self._emit_progress(50, "Separating stems...", "stem", "AudioStemWorker")

                if self._check_cancelled():
                    raise InterruptedError("Pipeline cancelled")

                if not self._check_vram("audio_stem"):
                    logger.warning("Insufficient VRAM for stem separation, skipping")
                else:
                    stem_worker = AudioStemWorker(
                        file_path=result.temp_wav_path,
                        model_name=stem_model
                    )
                    result.stems = self._run_worker_sync(stem_worker)
                    result.phases_completed.append("stem")
                    self.phase_completed.emit("stem")

            # Phase 4: Embeddings (optional, 75-100%)
            if include_embeddings:
                self._emit_progress(75, "Generating embeddings...", "embedding", "AudioEmbeddingWorker")

                if self._check_cancelled():
                    raise InterruptedError("Pipeline cancelled")

                if not self._check_vram("audio_embedding"):
                    logger.warning("Insufficient VRAM for embeddings, skipping")
                else:
                    embedding_worker = AudioEmbeddingWorker(result.temp_wav_path)
                    embedding_result = self._run_worker_sync(embedding_worker)
                    result.embeddings = embedding_result.embeddings
                    result.embedding_timestamps = embedding_result.timestamps
                    result.phases_completed.append("embedding")
                    self.phase_completed.emit("embedding")

            result.success = True
            self._emit_progress(100, "Audio pipeline complete", "complete", "")

        except (InterruptedError, CancelledError) as e:
            result.error_message = str(e)
            self.error_occurred.emit("cancelled", str(e))

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Audio pipeline failed: {e}", exc_info=True)
            self.error_occurred.emit("error", str(e))

        finally:
            self.pipeline_completed.emit(result)

        return result

    # =========================================================================
    # Video Pipeline
    # =========================================================================

    def run_video_pipeline(
        self,
        file_path: str,
        include_motion: bool = True,
        include_vision: bool = False,
        scene_threshold: float = 8.0,
        motion_sample_rate: int = 5,
        detailed_vision: bool = False,
        project_id: Optional[str] = None,
    ) -> VideoPipelineResult:
        """
        Run the complete video analysis pipeline.

        Pipeline phases:
        1. Import: Extract video metadata
        2. Scene: Detect scene boundaries
        3. Motion (optional): Analyze motion in scenes
        4. Vision (optional): Generate captions for scenes

        Args:
            file_path: Path to video file
            include_motion: Whether to run motion analysis
            include_vision: Whether to run vision analysis
            scene_threshold: Sensitivity for scene detection (1-50)
            motion_sample_rate: Analyze every N-th frame
            detailed_vision: Run multiple prompts per scene
            project_id: Optional project ID for tracking

        Returns:
            VideoPipelineResult with all analysis data
        """
        self._cancelled = False
        result = VideoPipelineResult()
        result.file_path = file_path

        try:
            # Phase 1: Import (0-15%)
            self._emit_progress(0, "Importing video...", "import", "VideoImportWorker")

            import_worker = VideoImportWorker(file_path, project_id or "")
            import_result = self._run_worker_sync(import_worker)

            result.metadata = import_result["metadata"]
            result.phases_completed.append("import")
            self.phase_completed.emit("import")

            # Phase 2: Scene Detection (15-40%)
            self._emit_progress(15, "Detecting scenes...", "scene", "VideoSceneWorker")

            if self._check_cancelled():
                raise InterruptedError("Pipeline cancelled")

            scene_worker = VideoSceneWorker(file_path, threshold=scene_threshold)
            scene_result = self._run_worker_sync(scene_worker)

            result.scenes = scene_result["scenes"]
            result.phases_completed.append("scene")
            self.phase_completed.emit("scene")

            # Phase 3: Motion Analysis (optional, 40-70%)
            if include_motion and result.scenes:
                self._emit_progress(40, "Analyzing motion...", "motion", "VideoMotionWorker")

                if self._check_cancelled():
                    raise InterruptedError("Pipeline cancelled")

                if not self._check_vram("video_motion"):
                    logger.warning("Insufficient VRAM for motion analysis, skipping")
                else:
                    motion_worker = VideoMotionWorker(
                        file_path=file_path,
                        scenes=result.scenes,
                        sample_rate=motion_sample_rate
                    )
                    motion_result = self._run_worker_sync(motion_worker)
                    result.motion_data = motion_result["motion_data"]
                    result.motion_analyzer_type = motion_result["analyzer_type"]
                    result.phases_completed.append("motion")
                    self.phase_completed.emit("motion")

            # Phase 4: Vision Analysis (optional, 70-100%)
            if include_vision and result.scenes:
                self._emit_progress(70, "Analyzing visual content...", "vision", "VideoVisionWorker")

                if self._check_cancelled():
                    raise InterruptedError("Pipeline cancelled")

                if not self._check_vram("video_vision"):
                    logger.warning("Insufficient VRAM for vision analysis, skipping")
                else:
                    vision_worker = VideoVisionWorker(
                        file_path=file_path,
                        scenes=result.scenes,
                        detailed_analysis=detailed_vision
                    )
                    vision_result = self._run_worker_sync(vision_worker)
                    result.captions = vision_result["captions"]
                    result.vision_model_type = vision_result["model_type"]
                    result.phases_completed.append("vision")
                    self.phase_completed.emit("vision")

            result.success = True
            self._emit_progress(100, "Video pipeline complete", "complete", "")

        except (InterruptedError, CancelledError) as e:
            result.error_message = str(e)
            self.error_occurred.emit("cancelled", str(e))

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Video pipeline failed: {e}", exc_info=True)
            self.error_occurred.emit("error", str(e))

        finally:
            self.pipeline_completed.emit(result)

        return result

    # =========================================================================
    # Generation Pipeline
    # =========================================================================

    def run_generation_pipeline(
        self,
        config: dict[str, Any]
    ) -> Optional[str]:
        """
        Run the complete video generation pipeline.

        This wraps ExportWorker with additional progress tracking and
        VRAM coordination. For most use cases, use ExportWorker directly.

        Args:
            config: Configuration dict with:
                Required:
                - audio_analysis: AudioAnalysisResult
                - source_videos: List of video paths
                - output_path: Final output path

                Optional:
                - master_audio: Audio track path
                - pacing_config: Pacing settings
                - codec: h264/hevc/av1
                - quality: speed/balanced/quality

        Returns:
            Path to final output video

        Raises:
            RuntimeError: If generation fails
        """
        self._cancelled = False

        try:
            self._emit_progress(0, "Starting generation...", "init", "ExportWorker")

            # Check VRAM
            if not self._check_vram("export"):
                raise RuntimeError("Insufficient VRAM for video generation")

            # Create and run export worker
            export_worker = ExportWorker(config)

            # Forward progress signals
            def on_export_progress(data):
                self._emit_progress(
                    data.get("percent", 0),
                    data.get("message", ""),
                    "generation",
                    data.get("worker", "ExportWorker")
                )

            export_worker.signals.progress.connect(on_export_progress)

            result = self._run_worker_sync(export_worker)

            self._emit_progress(100, "Generation complete", "complete", "")
            self.pipeline_completed.emit(result)

            return result.final_output_path

        except Exception as e:
            logger.error(f"Generation pipeline failed: {e}", exc_info=True)
            self.error_occurred.emit("generation", str(e))
            raise
